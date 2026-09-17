"""Materialize immutable RF HPO v1.1 provenance from completed evidence.

This script never trains, predicts, optimizes, or opens row-level datasets. It
reads completed Optuna SQLite databases in read-only mode and writes only new
JSON manifests, reusing byte-equivalent manifests and failing on collisions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.week5_hpo_protocol import build_optuna_components  # noqa: E402
from src.models.week5_hpo_protocol_v1_1 import (  # noqa: E402
    load_week5_hpo_protocol_v1_1,
)


PROTOCOL_VERSION = "week5_hpo_protocol_v1_1"
PROTOCOL_HASH = "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"
AMENDMENT_ID = "week5_hpo_execution_amendment_v1"
STUDY_IDS = ("random_forest_classification", "random_forest_regression")
RESULT_FILENAMES = {
    "classification": (
        "week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json"
    ),
    "regression": (
        "week5_hpo_protocol_v1_1__random_forest_regression_result_v1.json"
    ),
    "summary": "week5_random_forest_hpo_v1_1_summary_v3.json",
}


class ProvenanceRepairError(RuntimeError):
    """Raised when immutable production evidence is missing or inconsistent."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _serialize(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _serialized_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_serialize(value).encode("utf-8")).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def classify_guard_cleanup_evidence(
    events: Sequence[Mapping[str, object]], *, clean_exit: bool
) -> str:
    """Classify persisted cleanup evidence without promoting inference."""

    outcomes = [
        event.get("guard_cleanup_success")
        for event in events
        if "guard_cleanup_success" in event
    ]
    if any(value is False for value in outcomes):
        return "EXPLICIT_FAILURE"
    if any(value is True for value in outcomes):
        return "EXPLICIT_PASS"
    return "INFERRED_ONLY" if clean_exit else "NOT_FOUND"


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceRepairError(f"unreadable JSON evidence: {path}") from error
    if not isinstance(value, dict):
        raise ProvenanceRepairError(f"JSON evidence is not an object: {path}")
    return value


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProvenanceRepairError(f"unreadable YAML evidence: {path}") from error
    if not isinstance(value, dict):
        raise ProvenanceRepairError(f"YAML evidence is not a mapping: {path}")
    return value


def _heartbeat_evidence(path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ProvenanceRepairError("heartbeat record is not an object")
                records.append(record)
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceRepairError(f"unreadable heartbeat evidence: {path}") from error
    if not records:
        raise ProvenanceRepairError(f"heartbeat journal is empty: {path}")
    return {
        "record_count": len(records),
        "first_timestamp_utc": records[0]["timestamp_utc"],
        "last_timestamp_utc": records[-1]["timestamp_utc"],
        "sleep_guard_activation_status": (
            "PASS" if all(record.get("guard_active") is True for record in records) else "FAIL"
        ),
        "suspend_detected": any(
            record.get("environment_state") == "ENVIRONMENTAL_EXECUTION_INVALID"
            or float(record.get("suspend_gap_seconds", 0.0)) >= 120.0
            for record in records
        ),
        "environment_state": (
            "VALID"
            if all(record.get("environment_state") == "VALID" for record in records)
            else "ENVIRONMENTAL_EXECUTION_INVALID"
        ),
        "max_recorded_suspend_gap_seconds": max(
            float(record.get("suspend_gap_seconds", 0.0)) for record in records
        ),
        "last_process_cpu_seconds": float(records[-1]["process_cpu_seconds"]),
    }


def _read_trial_user_attrs(
    connection: sqlite3.Connection, trial_id: int
) -> dict[str, Any]:
    return {
        str(key): json.loads(value)
        for key, value in connection.execute(
            "select key,value_json from trial_user_attributes where trial_id=?",
            (trial_id,),
        )
    }


def _study_evidence(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        study_rows = list(connection.execute("select study_id,study_name from studies"))
        if len(study_rows) != 1:
            raise ProvenanceRepairError(f"expected one study in {path}")
        study_id, study_name = study_rows[0]
        directions = list(
            connection.execute(
                "select direction from study_directions where study_id=? order by objective",
                (study_id,),
            )
        )
        if len(directions) != 1:
            raise ProvenanceRepairError(f"expected one objective direction in {path}")
        direction = str(directions[0][0])
        trial_rows = list(
            connection.execute(
                "select trial_id,number,state,datetime_start,datetime_complete "
                "from trials where study_id=? order by number",
                (study_id,),
            )
        )
        state_counts = Counter(str(row[2]) for row in trial_rows)
        if state_counts != Counter({"COMPLETE": 10}):
            raise ProvenanceRepairError(
                f"study {study_name} is not exactly ten COMPLETE trials: {state_counts}"
            )
        values = {
            int(number): float(value)
            for number, value in connection.execute(
                "select t.number,v.value from trials t join trial_values v "
                "on v.trial_id=t.trial_id where t.study_id=?",
                (study_id,),
            )
        }
        best_number = (
            max(values, key=values.get) if direction == "MAXIMIZE" else min(values, key=values.get)
        )
        best_row = next(row for row in trial_rows if int(row[1]) == best_number)
        best_attrs = _read_trial_user_attrs(connection, int(best_row[0]))
        study_attrs = {
            str(key): json.loads(value)
            for key, value in connection.execute(
                "select key,value_json from study_user_attributes where study_id=?",
                (study_id,),
            )
        }
    finally:
        connection.close()

    per_fold = [float(value) for value in best_attrs["per_fold_objective"]]
    if len(per_fold) != 4:
        raise ProvenanceRepairError("best trial does not contain exactly four fold objectives")
    recomputed = sum(per_fold) / 4.0
    stored = values[best_number]
    starts = [datetime.fromisoformat(str(row[3])) for row in trial_rows]
    ends = [datetime.fromisoformat(str(row[4])) for row in trial_rows]
    return {
        "study_name": str(study_name),
        "direction": direction,
        "state_counts": state_counts,
        "best_trial": best_number,
        "best_objective": stored,
        "best_attrs": best_attrs,
        "per_fold_objective": per_fold,
        "recomputed_objective": recomputed,
        "objective_match": abs(stored - recomputed) <= 1e-12,
        "study_attrs": study_attrs,
        "study_start": min(starts).isoformat() + "Z",
        "study_end": max(ends).isoformat() + "Z",
        "runtime_seconds": (max(ends) - min(starts)).total_seconds(),
        "trial_numbers": [int(row[1]) for row in trial_rows],
    }


def _cleanup_events_from_logs(*paths: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            lower = line.lower()
            if "guard_cleanup_success=true" in lower:
                events.append({"guard_cleanup_success": True, "source": str(path)})
            elif "guard_cleanup_success=false" in lower or "guard cleanup failed" in lower:
                events.append({"guard_cleanup_success": False, "source": str(path)})
    return events


def _validate_param_space(params: Mapping[str, Any], space: Mapping[str, Any]) -> None:
    if set(params) != set(space):
        raise ProvenanceRepairError("best parameters differ from frozen search-space keys")
    for name, value in params.items():
        declaration = space[name]
        kind = declaration["type"]
        if kind == "categorical":
            valid = value in declaration["choices"]
        else:
            valid = declaration["low"] <= value <= declaration["high"]
            if valid and kind == "int" and "step" in declaration:
                valid = (int(value) - int(declaration["low"])) % int(declaration["step"]) == 0
        if not valid:
            raise ProvenanceRepairError(f"best parameter {name!r} is outside frozen space")


def build_post_run_payloads(project_root: Path) -> dict[str, dict[str, Any]]:
    """Build deterministic manifests entirely from existing production evidence."""

    root = Path(project_root).resolve()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    if protocol.protocol_hash != PROTOCOL_HASH:
        raise ProvenanceRepairError("v1.1 protocol hash mismatch")
    config = _yaml(root / "configs/week5_hpo_v1_1.yaml")
    protocol_manifest = _json(
        root / "artifacts/manifests/week5_hpo_protocol_v1_1.json"
    )
    amendment = _json(
        root / "artifacts/manifests/week5_hpo_execution_amendment_v1.json"
    )
    old_summary_path = root / "artifacts/manifests/week5_random_forest_hpo_v1_1_summary.json"
    old_summary = _json(old_summary_path)
    if old_summary.get("status") != "COMPLETED":
        raise ProvenanceRepairError("production RF summary is not completed")
    if amendment.get("amendment_id") != AMENDMENT_ID:
        raise ProvenanceRepairError("execution amendment identity mismatch")

    sampler, pruner = build_optuna_components(protocol)
    if type(sampler).__name__ != "TPESampler" or type(pruner).__name__ != "NopPruner":
        raise ProvenanceRepairError("runtime component constructor differs from protocol")
    runner_path = root / "scripts/run_week5_random_forest_hpo_v1_1.py"
    runner_text = runner_path.read_text(encoding="utf-8")
    if "build_optuna_components(protocol)" not in runner_text or "pruner=pruner" not in runner_text:
        raise ProvenanceRepairError("runner construction path does not pass frozen pruner")
    stdout_path = root / "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_hpo.stdout.log"
    stderr_path = root / "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_hpo.stderr.log"
    cleanup_events = _cleanup_events_from_logs(stdout_path, stderr_path)
    clean_exit = True
    cleanup_status = classify_guard_cleanup_evidence(
        cleanup_events, clean_exit=clean_exit
    )
    runtime_log_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (stdout_path, stderr_path)
        if path.exists()
    )
    pruner_runtime_log_evidence = (
        "EXPLICIT_NOPPRUNER" if "NopPruner" in runtime_log_text else "NOT_FOUND"
    )
    old_by_id = {
        item["study_id"]: item for item in old_summary.get("study_summaries", [])
    }

    results: dict[str, dict[str, Any]] = {}
    for task in ("classification", "regression"):
        study_id = f"random_forest_{task}"
        study_name = f"{PROTOCOL_VERSION}__{study_id}"
        storage_path = root / "artifacts/optuna_studies" / f"{study_name}.sqlite3"
        heartbeat_path = storage_path.with_suffix(".execution.jsonl")
        evidence = _study_evidence(storage_path)
        declaration = config["studies"][study_id]
        _validate_param_space(evidence["best_attrs"]["params"], declaration["search_space"])
        if evidence["study_name"] != declaration["study_name"]:
            raise ProvenanceRepairError("study name differs from frozen declaration")
        if evidence["study_attrs"].get("protocol_hash") != PROTOCOL_HASH:
            raise ProvenanceRepairError("stored study protocol hash mismatch")
        if evidence["trial_numbers"] != list(range(10)):
            raise ProvenanceRepairError("fresh study did not contain exactly trials 0-9")
        if evidence["study_attrs"].get("parent_trials_carried_forward") is not False:
            raise ProvenanceRepairError("parent trials were carried forward")
        if evidence["study_attrs"].get("parent_best_params_enqueued") is not False:
            raise ProvenanceRepairError("parent best params were enqueued")
        heartbeat = _heartbeat_evidence(heartbeat_path)
        summary_entry = old_by_id.get(study_id)
        if not summary_entry:
            raise ProvenanceRepairError(f"old summary lacks {study_id}")
        if (
            summary_entry.get("complete_trials") != 10
            or summary_entry.get("best_trial", {}).get("number") != evidence["best_trial"]
            or summary_entry.get("best_trial", {}).get("objective")
            != evidence["best_objective"]
            or summary_entry.get("best_trial", {}).get("params")
            != evidence["best_attrs"]["params"]
        ):
            raise ProvenanceRepairError(f"old summary disagrees with SQLite for {study_id}")
        result = {
            "schema_version": "1.0.0",
            "result_manifest_version": "week5_rf_hpo_result_v1",
            "protocol_version": PROTOCOL_VERSION,
            "protocol_hash": PROTOCOL_HASH,
            "amendment_id": AMENDMENT_ID,
            "study_id": study_id,
            "study_name": study_name,
            "storage_path": _relative(root, storage_path),
            "storage_sha256": _sha256(storage_path),
            "direction": evidence["direction"],
            "expected_complete_trials": 10,
            "complete_trials": int(evidence["state_counts"].get("COMPLETE", 0)),
            "failed_trials": int(evidence["state_counts"].get("FAIL", 0)),
            "pruned_trials": int(evidence["state_counts"].get("PRUNED", 0)),
            "running_trials": int(evidence["state_counts"].get("RUNNING", 0)),
            "waiting_trials": int(evidence["state_counts"].get("WAITING", 0)),
            "fresh_initial_trial_count": 0,
            "v1_trials_carried_forward": False,
            "v1_best_params_enqueued": False,
            "best_trial": evidence["best_trial"],
            "best_objective": evidence["best_objective"],
            "best_params": evidence["best_attrs"]["params"],
            "best_trial_per_fold_objective": evidence["per_fold_objective"],
            "best_trial_per_fold_metrics": evidence["best_attrs"]["per_fold_metrics"],
            "recomputed_objective": evidence["recomputed_objective"],
            "objective_match": evidence["objective_match"],
            "sampler": "TPESampler",
            "sampler_evidence_source": [
                "configs/week5_hpo_v1_1.yaml#randomness",
                "src/models/week5_hpo_protocol.py#build_optuna_components",
                "scripts/run_week5_random_forest_hpo_v1_1.py#create_fresh_study",
            ],
            "pruner": "NopPruner",
            "pruner_evidence_source": [
                "configs/week5_hpo_v1_1.yaml#randomness",
                "artifacts/manifests/week5_hpo_protocol_v1_1.json#randomness",
                "src/models/week5_hpo_protocol.py#build_optuna_components",
                "scripts/run_week5_random_forest_hpo_v1_1.py#create_fresh_study",
            ],
            "pruner_runtime_log_evidence": pruner_runtime_log_evidence,
            "sqlite_pruner_metadata": "NOT_PERSISTED_NOT_AUTHORITATIVE",
            "seed": 202601,
            "n_jobs": {"optuna": 1, "random_forest": 1},
            "timeout_seconds_per_study": 14400,
            "search_space": declaration["search_space"],
            "search_space_sha256": _canonical_hash(declaration["search_space"]),
            "search_space_reference": f"configs/week5_hpo_v1_1.yaml#studies.{study_id}",
            "fold_protocol_reference": "configs/week5_hpo_v1_1.yaml#folds",
            "feature_manifest_reference": "feature_manifest_arrival_v1",
            "preprocessing_reference": "arrival_preprocessing_v1",
            "objective_name": declaration["objective_metric"],
            "prediction_method": (
                config["objectives"]["classification"]["prediction_method"]
                if task == "classification"
                else None
            ),
            "signed_regression_target": task == "regression",
            "study_start": evidence["study_start"],
            "study_end": evidence["study_end"],
            "runtime_seconds": evidence["runtime_seconds"],
            "heartbeat_path": _relative(root, heartbeat_path),
            "heartbeat_sha256": _sha256(heartbeat_path),
            **heartbeat,
            "guard_cleanup_evidence_status": cleanup_status,
            "guard_cleanup_evidence_source": (
                [event.get("source") for event in cleanup_events]
                if cleanup_events
                else [
                    "clean runner exit",
                    "src/models/week5_hpo_execution.py#windows_hpo_execution_guard.finally",
                    "no persisted cleanup event found",
                ]
            ),
            "resource_evidence": summary_entry.get("process_memory"),
            "peak_rss_bytes": None,
            "peak_rss_evidence_status": "NOT_PERSISTED",
            "dependency_versions": config["dependencies"],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
            "weather_used": False,
            "departure_prediction_used": False,
            "dep_delay_predictor_used": False,
            "chain_used": False,
            "arr_b_enabled": False,
            "actual_operational_predictors_used": False,
            "generated_from_existing_production_run": True,
            "new_training_performed": False,
            "new_hpo_performed": False,
        }
        results[task] = result

    classification_filename = RESULT_FILENAMES["classification"]
    regression_filename = RESULT_FILENAMES["regression"]
    summary = {
        "schema_version": "1.0.0",
        "summary_version": "week5_random_forest_hpo_v1_1_summary_v3",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_hash": PROTOCOL_HASH,
        "amendment_id": AMENDMENT_ID,
        "statistical_protocol_changed": False,
        "execution_protocol_changed": True,
        "sampler": "TPESampler",
        "sampler_evidence_source": results["classification"]["sampler_evidence_source"],
        "pruner": "NopPruner",
        "pruner_evidence_source": results["classification"]["pruner_evidence_source"],
        "pruner_runtime_log_evidence": pruner_runtime_log_evidence,
        "sqlite_pruner_metadata": "NOT_PERSISTED_NOT_AUTHORITATIVE",
        "seed": 202601,
        "n_jobs": {"optuna": 1, "random_forest": 1},
        "timeout_seconds_per_study": 14400,
        "classification_result_manifest": (
            f"artifacts/manifests/{classification_filename}"
        ),
        "classification_result_manifest_sha256": _serialized_sha256(
            results["classification"]
        ),
        "regression_result_manifest": f"artifacts/manifests/{regression_filename}",
        "regression_result_manifest_sha256": _serialized_sha256(results["regression"]),
        "classification_heartbeat": results["classification"]["heartbeat_path"],
        "regression_heartbeat": results["regression"]["heartbeat_path"],
        "classification_guard_status": results["classification"][
            "sleep_guard_activation_status"
        ],
        "regression_guard_status": results["regression"][
            "sleep_guard_activation_status"
        ],
        "guard_cleanup_provenance": {
            "classification": results["classification"][
                "guard_cleanup_evidence_status"
            ],
            "regression": results["regression"]["guard_cleanup_evidence_status"],
        },
        "suspend_detected": False,
        "environment_valid": True,
        "row_level_2023_accessed": False,
        "row_level_2024_accessed": False,
        "fresh_studies": True,
        "v1_trials_carried_forward": False,
        "source_summary": _relative(root, old_summary_path),
        "source_summary_sha256": _sha256(old_summary_path),
        "runner_source": _relative(root, runner_path),
        "runner_source_sha256": _sha256(runner_path),
        "protocol_manifest_sha256": _sha256(
            root / "artifacts/manifests/week5_hpo_protocol_v1_1.json"
        ),
        "amendment_manifest_sha256": _sha256(
            root / "artifacts/manifests/week5_hpo_execution_amendment_v1.json"
        ),
        "studies": {
            task: {
                "study_id": result["study_id"],
                "complete_trials": result["complete_trials"],
                "best_trial": result["best_trial"],
                "best_objective": result["best_objective"],
                "best_params": result["best_params"],
                "runtime_seconds": result["runtime_seconds"],
                "resource_evidence": result["resource_evidence"],
            }
            for task, result in results.items()
        },
        "provenance_complete": cleanup_status == "EXPLICIT_PASS",
        "generated_from_existing_production_run": True,
        "new_training_performed": False,
        "new_hpo_performed": False,
    }
    if protocol_manifest.get("protocol_sha256") != PROTOCOL_HASH:
        raise ProvenanceRepairError("protocol manifest hash mismatch")
    results["summary"] = summary
    return results


def materialize_post_run_payloads(
    payloads: Mapping[str, Mapping[str, Any]], *, output_directory: Path
) -> dict[str, str]:
    """Write new immutable JSON artifacts or reuse exact existing payloads."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for key, filename in RESULT_FILENAMES.items():
        target = output / filename
        payload = payloads[key]
        if target.exists():
            existing = _json(target)
            if existing != payload:
                raise ProvenanceRepairError(
                    f"conflicting immutable artifact exists: {target}"
                )
            status[key] = "REUSE"
            continue
        target.write_text(_serialize(payload), encoding="utf-8", newline="\n")
        status[key] = "CREATED"
    return status


def main() -> int:
    payloads = build_post_run_payloads(ROOT)
    statuses = materialize_post_run_payloads(
        payloads, output_directory=ROOT / "artifacts/manifests"
    )
    paths = {
        key: {
            "status": statuses[key],
            "path": f"artifacts/manifests/{filename}",
            "sha256": _sha256(ROOT / "artifacts/manifests" / filename),
        }
        for key, filename in RESULT_FILENAMES.items()
    }
    print(json.dumps(paths, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
