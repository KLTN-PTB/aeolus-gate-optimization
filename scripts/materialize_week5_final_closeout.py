"""Audit and immutably materialize the Week-5 final closeout evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import optuna
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.load_aeolus import resolve_project_root  # noqa: E402
from src.models.week5_hpo_protocol_v1_1 import (  # noqa: E402
    load_week5_hpo_protocol_v1_1,
)


PROTOCOL_VERSION = "week5_hpo_protocol_v1_1"
PROTOCOL_HASH = "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"
FINAL_MANIFEST = Path(
    "artifacts/manifests/week5_core_arrival_xgboost_optuna_summary_v1.json"
)
FINAL_REPORT = Path("docs/experiments/week5_core_arrival_xgboost_optuna.md")
MANIFEST_DIR = Path("artifacts/manifests")

METHODS = ("random_forest", "hist_gradient_boosting", "xgboost")
TASKS = ("classification", "regression")
EXPECTED_STUDY_IDS = tuple(f"{method}_{task}" for method in METHODS for task in TASKS)
EXPECTED_FOLDS = (
    ("fold_1", (2016, 2017, 2018), 2019),
    ("fold_2", (2016, 2017, 2018, 2019), 2020),
    ("fold_3", (2016, 2017, 2018, 2019, 2020), 2021),
    ("fold_4", (2016, 2017, 2018, 2019, 2020, 2021), 2022),
)
EXPECTED_OOF_ROWS = 1_254_518
OOF_MANIFESTS = {
    "linear_ridge": Path("artifacts/manifests/arrival_linear_rolling_run_v1.json"),
    "random_forest": Path(
        "artifacts/manifests/arrival_random_forest_tuned_rolling_run_v1_1.json"
    ),
    "hist_gradient_boosting": Path(
        "artifacts/manifests/arrival_hist_gradient_boosting_tuned_rolling_run_v1_1.json"
    ),
    "xgboost": Path(
        "artifacts/manifests/arrival_xgboost_tuned_rolling_run_v1_1.json"
    ),
}
SUMMARY_MANIFESTS = {
    "random_forest": Path(
        "artifacts/manifests/week5_random_forest_hpo_v1_1_summary_v4.json"
    ),
    "hist_gradient_boosting": Path(
        "artifacts/manifests/week5_hist_gradient_boosting_hpo_v1_1_summary_v1.json"
    ),
    "xgboost": Path(
        "artifacts/manifests/week5_xgboost_hpo_v1_1_summary_v1.json"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"required JSON evidence is unreadable: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"required JSON evidence is not an object: {path}")
    return value


def _path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _artifact(root: Path, path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"required artifact is missing: {path}")
    return {
        "path": _relative(root, path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def validate_study_contract(studies: Sequence[Mapping[str, Any]]) -> None:
    expected = {(method, task) for method in METHODS for task in TASKS}
    observed = {(str(item.get("method")), str(item.get("task"))) for item in studies}
    if len(studies) != 6 or observed != expected:
        raise RuntimeError("Week 5 requires exactly the six fixed production studies")
    for study in studies:
        label = f"{study.get('method')}/{study.get('task')}"
        if (
            study.get("complete_trials") != 10
            or study.get("failed_trials") != 0
            or study.get("running_trials") != 0
        ):
            raise RuntimeError(f"{label} does not have 10 COMPLETE and zero active/failed trials")
        if study.get("protocol_version") != PROTOCOL_VERSION or study.get("protocol_hash") != PROTOCOL_HASH:
            raise RuntimeError(f"{label} protocol mismatch")
        expected_direction = "MAXIMIZE" if study.get("task") == "classification" else "MINIMIZE"
        if study.get("direction") != expected_direction:
            raise RuntimeError(f"{label} direction mismatch")
        if study.get("sampler") != "TPESampler" or study.get("seed") != 202601:
            raise RuntimeError(f"{label} sampler/seed mismatch")
        if study.get("pruner") != "NopPruner":
            raise RuntimeError(f"{label} pruner mismatch")
        if study.get("n_jobs") != 1 or study.get("timeout_seconds_per_study") != 14400:
            raise RuntimeError(f"{label} execution budget mismatch")
        if study.get("objective_match") is not True:
            raise RuntimeError(f"{label} stored/recomputed objective mismatch")
        cleanup = study.get("cleanup")
        if study.get("method") == "random_forest":
            if cleanup != "ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT":
                raise RuntimeError("RF cleanup provenance amendment is not authoritative")
        elif cleanup != "GUARD_CLEANUP_SUCCESS":
            raise RuntimeError(f"{label} lacks direct GUARD_CLEANUP_SUCCESS")


def validate_week6_boundary(boundary: Mapping[str, Any]) -> None:
    started = [name for name, value in boundary.items() if bool(value)]
    if started:
        raise RuntimeError(f"Week 6 work has already started: {', '.join(started)}")


def _journal_has_explicit_cleanup(path: Path, study_id: str) -> bool:
    found_attempt = False
    found_success = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(f"guard journal is unreadable: {path}") from error
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("study_id") != study_id:
            continue
        found_attempt |= event.get("event") == "GUARD_CLEANUP_ATTEMPT"
        found_success |= (
            event.get("event") == "GUARD_CLEANUP_SUCCESS"
            and event.get("success") is True
            and event.get("set_thread_execution_state_return_value") is not None
        )
    return found_attempt and found_success


def _study_state_counts(study: optuna.Study) -> dict[str, int]:
    counts = Counter(trial.state.name for trial in study.trials)
    return {name: int(counts.get(name, 0)) for name in ("COMPLETE", "FAIL", "PRUNED", "RUNNING", "WAITING")}


def _normalize_n_jobs(result: Mapping[str, Any]) -> int:
    value = result.get("n_jobs")
    if not isinstance(value, Mapping) or value.get("optuna") != 1:
        raise RuntimeError("result manifest does not prove Optuna n_jobs=1")
    method_keys = [key for key in ("random_forest", "xgboost") if key in value]
    if method_keys and value[method_keys[0]] != 1:
        raise RuntimeError("result manifest does not prove estimator n_jobs=1")
    if result.get("optuna_parallelism", 1) != 1:
        raise RuntimeError("result manifest parallelism mismatch")
    return 1


def _result_counts(result: Mapping[str, Any]) -> dict[str, int]:
    states = result.get("actual_trial_states")
    if isinstance(states, Mapping):
        return {
            "COMPLETE": int(states.get("COMPLETE", 0)),
            "FAIL": int(states.get("FAIL", 0)),
            "PRUNED": int(states.get("PRUNED", 0)),
            "RUNNING": int(states.get("RUNNING", 0)),
            "WAITING": int(states.get("WAITING", 0)),
        }
    return {
        "COMPLETE": int(result.get("complete_trials", 0)),
        "FAIL": int(result.get("failed_trials", 0)),
        "PRUNED": int(result.get("pruned_trials", 0)),
        "RUNNING": int(result.get("running_trials", 0)),
        "WAITING": int(result.get("waiting_trials", 0)),
    }


def _load_study_record(
    root: Path,
    protocol_manifest: Mapping[str, Any],
    study_id: str,
    rf_cleanup_amendment: Mapping[str, Any],
) -> dict[str, Any]:
    method, task = study_id.rsplit("_", 1)
    result_path = root / MANIFEST_DIR / f"{PROTOCOL_VERSION}__{study_id}_result_v1.json"
    result = _read_json(result_path)
    protocol_study = protocol_manifest["studies"][study_id]
    storage_path = _path(root, str(result["storage_path"]))
    result_storage_sha = str(result.get("storage_sha256", ""))
    if _sha256(storage_path) != result_storage_sha:
        raise RuntimeError(f"{study_id} storage SHA-256 mismatch")
    storage_url = f"sqlite:///{storage_path.resolve().as_posix()}"
    study = optuna.load_study(study_name=str(result["study_name"]), storage=storage_url)
    direct_states = _study_state_counts(study)
    manifest_states = _result_counts(result)
    if direct_states != manifest_states:
        raise RuntimeError(f"{study_id} SQLite/result trial-state mismatch")
    if study.direction.name != result.get("direction"):
        raise RuntimeError(f"{study_id} SQLite/result direction mismatch")
    if study.best_trial.number != result.get("best_trial"):
        raise RuntimeError(f"{study_id} SQLite/result best-trial mismatch")
    if not math.isclose(float(study.best_value), float(result["best_objective"]), rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"{study_id} SQLite/result best-objective mismatch")
    if study.best_params != result.get("best_params"):
        raise RuntimeError(f"{study_id} SQLite/result best-params mismatch")
    if result.get("search_space") != protocol_study.get("search_space"):
        raise RuntimeError(f"{study_id} frozen search-space mismatch")
    if result.get("objective_name") != protocol_study.get("objective_metric"):
        raise RuntimeError(f"{study_id} objective mismatch")
    if result.get("protocol_version") != PROTOCOL_VERSION or result.get("protocol_hash") != PROTOCOL_HASH:
        raise RuntimeError(f"{study_id} protocol mismatch")
    if result.get("sampler") != "TPESampler" or result.get("seed") != 202601 or result.get("pruner") != "NopPruner":
        raise RuntimeError(f"{study_id} sampler/seed/pruner mismatch")
    if result.get("timeout_seconds_per_study") != 14400:
        raise RuntimeError(f"{study_id} timeout mismatch")
    _normalize_n_jobs(result)
    if result.get("objective_match") is not True or not math.isclose(
        float(result["best_objective"]), float(result["recomputed_objective"]), rel_tol=0.0, abs_tol=1e-12
    ):
        raise RuntimeError(f"{study_id} objective recomputation mismatch")
    if any(bool(result.get(key)) for key in (
        "row_level_2023_accessed", "row_level_2024_accessed", "weather_used",
        "departure_prediction_used", "dep_delay_predictor_used", "chain_used", "arr_b_enabled",
    )):
        raise RuntimeError(f"{study_id} temporal/leakage contract violation")
    if result.get("suspend_detected") is not False:
        raise RuntimeError(f"{study_id} suspend evidence is invalid")
    environment_valid = result.get("environment_valid", result.get("environment_state") == "VALID")
    if environment_valid is not True:
        raise RuntimeError(f"{study_id} environment evidence is invalid")
    if task == "classification" and result.get("prediction_method") != "predict_proba":
        raise RuntimeError(f"{study_id} did not use probabilities")
    if task == "regression" and result.get("signed_regression_target") is not True:
        raise RuntimeError(f"{study_id} did not preserve the signed target")

    heartbeat_path = _path(root, str(result["heartbeat_path"]))
    heartbeat = _artifact(root, heartbeat_path)
    if heartbeat["sha256"] != result.get("heartbeat_sha256"):
        raise RuntimeError(f"{study_id} heartbeat SHA-256 mismatch")

    guard_journal: dict[str, Any] | None = None
    if method == "random_forest":
        if rf_cleanup_amendment.get("cleanup_acceptance") != "ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT":
            raise RuntimeError("RF cleanup amendment is not acceptable")
        cleanup = "ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT"
    else:
        guard_path = _path(root, str(result["guard_journal_path"]))
        guard_journal = _artifact(root, guard_path)
        if guard_journal["sha256"] != result.get("guard_journal_sha256"):
            raise RuntimeError(f"{study_id} guard-journal SHA-256 mismatch")
        event = result.get("guard_cleanup_evidence", {}).get("event", {})
        if (
            result.get("guard_cleanup_evidence", {}).get("status") != "EXPLICIT_PASS"
            or event.get("event") != "GUARD_CLEANUP_SUCCESS"
            or event.get("success") is not True
            or not _journal_has_explicit_cleanup(guard_path, study_id)
        ):
            raise RuntimeError(f"{study_id} lacks direct GUARD_CLEANUP_SUCCESS")
        cleanup = "GUARD_CLEANUP_SUCCESS"

    return {
        "study_id": study_id,
        "study_name": result["study_name"],
        "method": method,
        "task": task,
        "protocol_version": result["protocol_version"],
        "protocol_hash": result["protocol_hash"],
        "direction": result["direction"],
        "objective": result["objective_name"],
        "complete_trials": direct_states["COMPLETE"],
        "failed_trials": direct_states["FAIL"],
        "pruned_trials": direct_states["PRUNED"],
        "running_trials": direct_states["RUNNING"],
        "waiting_trials": direct_states["WAITING"],
        "best_trial": result["best_trial"],
        "best_objective": result["best_objective"],
        "recomputed_objective": result["recomputed_objective"],
        "objective_match": True,
        "best_params": result["best_params"],
        "search_space": result["search_space"],
        "sampler": "TPESampler",
        "seed": 202601,
        "pruner": "NopPruner",
        "n_jobs": 1,
        "timeout_seconds_per_study": 14400,
        "prediction_method": result.get("prediction_method"),
        "signed_regression_target": result.get("signed_regression_target"),
        "cleanup": cleanup,
        "suspend_detected": False,
        "environment_valid": True,
        "result_manifest": _artifact(root, result_path),
        "storage": _artifact(root, storage_path),
        "heartbeat": heartbeat,
        "guard_journal": guard_journal,
        "dependency_versions": result.get("dependency_versions", {}),
        "runtime_seconds": result.get("runtime_seconds"),
        "resource_evidence": result.get("runtime_resources", result.get("resource_evidence", {})),
    }


def _verify_method_summary(root: Path, method: str, studies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    path = root / SUMMARY_MANIFESTS[method]
    summary = _read_json(path)
    if summary.get("protocol_version") != PROTOCOL_VERSION or summary.get("protocol_hash") != PROTOCOL_HASH:
        raise RuntimeError(f"{method} authoritative summary protocol mismatch")
    if method != "random_forest" and summary.get("status") != "COMPLETED":
        raise RuntimeError(f"{method} authoritative summary is not completed")
    for study in (item for item in studies if item["method"] == method):
        summary_study = summary["studies"].get(study["study_id"])
        if summary_study is None and method == "random_forest":
            summary_study = summary["studies"].get(study["task"])
        if not isinstance(summary_study, Mapping):
            raise RuntimeError(f"{method} summary lacks {study['study_id']}")
        if (
            summary_study.get("complete_trials") != 10
            or summary_study.get("best_trial") != study["best_trial"]
            or summary_study.get("best_params") != study["best_params"]
            or not math.isclose(float(summary_study["best_objective"]), float(study["best_objective"]), rel_tol=0.0, abs_tol=1e-12)
            or summary_study.get("result_manifest_sha256", study["result_manifest"]["sha256"])
            != study["result_manifest"]["sha256"]
        ):
            raise RuntimeError(f"{method} summary/result mismatch for {study['study_id']}")
    return _artifact(root, path)


def _validate_oof(root: Path, studies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result_hashes = {
        (study["method"], study["task"]): study["result_manifest"]["sha256"]
        for study in studies
    }
    methods: dict[str, Any] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for method, rel_path in OOF_MANIFESTS.items():
        path = root / rel_path
        manifest = _read_json(path)
        manifests[method] = manifest
        if manifest.get("status") != "PASS":
            raise RuntimeError(f"{method} OOF manifest is not PASS")
        if method != "linear_ridge":
            if (
                manifest.get("protocol_version") != PROTOCOL_VERSION
                or manifest.get("protocol_hash") != PROTOCOL_HASH
                or manifest.get("hpo_rerun") is not False
                or manifest.get("champion_selected") is not False
            ):
                raise RuntimeError(f"{method} tuned OOF provenance mismatch")
            source = manifest.get("hpo_result_source", {})
            if (
                source.get("classification_result_sha256") != result_hashes[(method, "classification")]
                or source.get("regression_result_sha256") != result_hashes[(method, "regression")]
            ):
                raise RuntimeError(f"{method} tuned OOF HPO linkage mismatch")
        if any(bool(manifest.get(key)) for key in (
            "row_level_2023_accessed", "row_level_2024_accessed", "weather_used",
            "departure_prediction_used", "dep_delay_predictor_used", "chain_used", "arr_b_enabled",
        )):
            raise RuntimeError(f"{method} OOF temporal/leakage violation")
        fold_reports = manifest.get("folds", [])
        observed_folds = tuple(
            (
                item.get("fold_id"),
                tuple(item.get("train_years", [])),
                item.get("validation_year"),
            )
            for item in fold_reports
        )
        if observed_folds != EXPECTED_FOLDS:
            raise RuntimeError(f"{method} OOF fold identity mismatch")
        total_rows = sum(int(item.get("oof_rows", 0)) for item in fold_reports)
        if total_rows != EXPECTED_OOF_ROWS:
            raise RuntimeError(f"{method} OOF row-count mismatch")
        methods[method] = {
            "manifest": _artifact(root, path),
            "folds": [
                {
                    "fold_id": item["fold_id"],
                    "train_years": item["train_years"],
                    "validation_year": item["validation_year"],
                    "rows": item["oof_rows"],
                    "development_metrics": item["metrics"],
                }
                for item in fold_reports
            ],
            "pooled_development_metrics": manifest.get(
                "aggregate_development_metrics", manifest.get("aggregate_metrics")
            ),
            "rows": total_rows,
            "oof_artifacts": [],
        }

    parity_columns = ["flight_key", "y_arr_cls", "y_arr_reg"]
    for fold_index, (fold_id, _, _) in enumerate(EXPECTED_FOLDS):
        anchor_path = _path(root, manifests["linear_ridge"]["folds"][fold_index]["oof_artifact"])
        anchor = pq.read_table(anchor_path, columns=parity_columns).combine_chunks()
        if anchor.num_rows != manifests["linear_ridge"]["folds"][fold_index]["oof_rows"]:
            raise RuntimeError(f"Linear OOF row metadata mismatch for {fold_id}")
        for method in OOF_MANIFESTS:
            report = manifests[method]["folds"][fold_index]
            path = _path(root, report["oof_artifact"])
            candidate = pq.read_table(path, columns=parity_columns).combine_chunks()
            if not anchor.equals(candidate):
                raise RuntimeError(f"exact OOF row/target parity failed for {method}/{fold_id}")
            prediction = pq.read_table(
                path, columns=["p_arr_delay_15", "predicted_arr_delay_min"]
            )
            probabilities = prediction["p_arr_delay_15"].to_numpy(zero_copy_only=False)
            regression = prediction["predicted_arr_delay_min"].to_numpy(zero_copy_only=False)
            if (
                not np.isfinite(probabilities).all()
                or not ((probabilities >= 0.0) & (probabilities <= 1.0)).all()
                or not np.isfinite(regression).all()
            ):
                raise RuntimeError(f"invalid OOF predictions for {method}/{fold_id}")
            methods[method]["oof_artifacts"].append(_artifact(root, path))

    if not any(
        pq.read_table(item["path"] if Path(item["path"]).is_absolute() else root / item["path"], columns=["predicted_arr_delay_min"])["predicted_arr_delay_min"].to_numpy(zero_copy_only=False).min() < 0
        for item in methods["xgboost"]["oof_artifacts"]
    ):
        raise RuntimeError("XGBoost signed regression predictions appear clipped")
    return {
        "methods": methods,
        "common_folds": 4,
        "common_rows": EXPECTED_OOF_ROWS,
        "row_parity": "PASS",
        "target_parity": "PASS",
        "probability_bounds": "PASS",
        "signed_regression_preserved": True,
    }


def _week6_boundary(root: Path, oof_manifests: Mapping[str, Any]) -> dict[str, bool]:
    artifact_roots = (root / "artifacts/manifests", root / "artifacts/predictions")
    patterns = {
        "weighted_ensemble_started": ("*weighted_ensemble*",),
        "selection_2023_started": ("*model_comparison_2023*", "*2023_selection*"),
        "shap_started": ("*shap*",),
        "arr_ablation_started": ("*arrival_ablation*", "*arr_ablation*"),
        "dep_weather_ablation_started": ("*departure_weather*", "*dep_weather*"),
    }
    boundary: dict[str, bool] = {}
    for key, globs in patterns.items():
        boundary[key] = any(
            path.is_file()
            for base in artifact_roots
            for pattern in globs
            for path in base.glob(pattern)
        )
    boundary["core_champion_selected"] = any(
        manifest.get("champion_selected") is True for manifest in oof_manifests.values()
    )
    validate_week6_boundary(boundary)
    return boundary


def build_week5_closeout(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    if protocol.protocol_version != PROTOCOL_VERSION or protocol.protocol_hash != PROTOCOL_HASH:
        raise RuntimeError("frozen protocol loader mismatch")
    protocol_path = root / MANIFEST_DIR / "week5_hpo_protocol_v1_1.json"
    protocol_manifest = _read_json(protocol_path)
    if (
        protocol_manifest.get("protocol_version") != PROTOCOL_VERSION
        or protocol_manifest.get("protocol_sha256") != PROTOCOL_HASH
        or protocol_manifest.get("statistical_protocol_changed") is not False
    ):
        raise RuntimeError("frozen protocol manifest mismatch")

    rf_execution_path = root / MANIFEST_DIR / "week5_hpo_execution_amendment_v1.json"
    rf_cleanup_path = root / MANIFEST_DIR / "week5_hpo_guard_cleanup_provenance_amendment_v1.json"
    hgb_recovery_path = root / MANIFEST_DIR / "week5_hgb_poststudy_recovery_amendment_v1.json"
    rf_execution = _read_json(rf_execution_path)
    rf_cleanup = _read_json(rf_cleanup_path)
    hgb_recovery = _read_json(hgb_recovery_path)
    if (
        rf_execution.get("original_attempt") != "BLOCKED_INCOMPLETE"
        or rf_execution.get("root_cause") != "ENVIRONMENTAL_WALL_CLOCK_INTERRUPTION"
        or rf_execution.get("statistical_protocol_changed") is not False
        or rf_cleanup.get("statistical_protocol_changed") is not False
        or hgb_recovery.get("statistical_protocol_changed") is not False
    ):
        raise RuntimeError("Week-5 incident/amendment provenance mismatch")

    result_files = sorted((root / MANIFEST_DIR).glob(f"{PROTOCOL_VERSION}__*_result_v1.json"))
    expected_result_names = {
        f"{PROTOCOL_VERSION}__{study_id}_result_v1.json" for study_id in EXPECTED_STUDY_IDS
    }
    if {path.name for path in result_files} != expected_result_names:
        raise RuntimeError("Week 5 does not have exactly six authoritative result manifests")

    studies = [
        _load_study_record(root, protocol_manifest, study_id, rf_cleanup)
        for study_id in EXPECTED_STUDY_IDS
    ]
    validate_study_contract(studies)
    summaries = {
        method: _verify_method_summary(root, method, studies) for method in METHODS
    }
    oof = _validate_oof(root, studies)
    oof_raw = {method: _read_json(root / path) for method, path in OOF_MANIFESTS.items()}
    boundary = _week6_boundary(root, oof_raw)

    weather_path = root / MANIFEST_DIR / "weather_point_in_time_contract_v1.json"
    weather = _read_json(weather_path)
    if weather.get("audit_status") != "AUDIT_REQUIRED":
        raise RuntimeError("Weather provenance state unexpectedly changed")
    chain_path = root / MANIFEST_DIR / "reconstructed_chain_feature_availability_audit_v1.json"
    chain = _read_json(chain_path)
    if chain.get("audit_decision") != "NO_KEEP_SAFE_FEATURES_YET" or chain.get("classification_counts", {}).get("KEEP_SAFE", 0) != 0:
        raise RuntimeError("reconstructed Chain KEEP_SAFE policy unexpectedly changed")

    historical_v1_storage = _path(root, rf_execution["original_v1_storage"])
    if not historical_v1_storage.exists():
        raise RuntimeError("historical interrupted RF v1 storage is missing")

    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "summary_id": "week5_core_arrival_xgboost_optuna_summary_v1",
        "generated_at_utc": _utc_now(),
        "week5_final_status": "PASS",
        "week5_completed": True,
        "ready_for_week_6": True,
        "protocol": {
            "version": PROTOCOL_VERSION,
            "hash": PROTOCOL_HASH,
            "statistical_protocol": "FROZEN_UNCHANGED",
            "manifest": _artifact(root, protocol_path),
            "config": _artifact(root, root / "configs/week5_hpo_v1_1.yaml"),
            "hpo_years": list(range(2016, 2023)),
            "trials_per_study": 10,
            "sampler": "TPESampler",
            "seed": 202601,
            "pruner": "NopPruner",
            "parallelism": 1,
            "timeout_seconds_per_study": 14400,
            "classification_objective": "maximize equal-fold macro mean PR-AUC from predict_proba",
            "regression_objective": "minimize equal-fold macro mean MAE on signed ARR_DELAY",
            "reporting_threshold": 0.5,
            "threshold_tuned": False,
        },
        "core_methods": {
            "linear_ridge": "AVAILABLE_WEEK4_PRESERVED",
            "random_forest": "AVAILABLE_TUNED_WEEK5",
            "hist_gradient_boosting": "AVAILABLE_TUNED_WEEK5",
            "xgboost": "AVAILABLE_BASELINE_AND_TUNED_WEEK5",
            "weighted_ensemble": "NOT_STARTED_WEEK6",
        },
        "studies": studies,
        "all_six_fixed_budget_complete": True,
        "authoritative_summaries": summaries,
        "oof": oof,
        "temporal": {
            "hpo_years": list(range(2016, 2023)),
            "row_level_2023_hpo_accessed": False,
            "selection_2023_performed": False,
            "ensemble_2023_fitted": False,
            "row_level_2024_accessed": False,
        },
        "leakage": {
            "population": "inbound DEST=ATL",
            "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
            "weather_used": False,
            "departure_prediction_used": False,
            "dep_delay_predictor_used": False,
            "actual_operational_outcomes_used": False,
            "chain_feature_used": False,
            "arr_b_status": "DISABLED",
            "chain_ml_status": "BLOCKED_PENDING_NEW_EVIDENCE",
        },
        "auxiliary_weather": {
            "status": "NOT_RUN_WEEK5",
            "point_in_time_weather_provenance": "AUDIT_REQUIRED",
            "contract": _artifact(root, weather_path),
        },
        "execution_provenance": {
            "rf_final_basis": "VALID_PRODUCTION_HPO + NON_STATISTICAL_CLEANUP_PROVENANCE_AMENDMENT",
            "rf_original_v1_attempt": {
                "status": "BLOCKED_INCOMPLETE",
                "root_cause": "ENVIRONMENTAL_WALL_CLOCK_INTERRUPTION",
                "complete_trials": rf_execution["original_rf_classification_complete_trials"],
                "storage": _artifact(root, historical_v1_storage),
                "counted_as_completed_week5_study": False,
            },
            "prompt_status_history": {
                "PROMPT_04F": "FAIL_HISTORICAL_UNCHANGED",
                "PROMPT_04G": "FAIL_HISTORICAL_UNCHANGED",
                "PROMPT_04H": "PASS_AUTHORITATIVE",
                "STEP_04E_FINAL_STATUS": "PASS_AUTHORITATIVE",
            },
            "amendments": {
                "execution": _artifact(root, rf_execution_path),
                "rf_cleanup_provenance": _artifact(root, rf_cleanup_path),
                "hgb_poststudy_recovery": _artifact(root, hgb_recovery_path),
                "xgb_tuned_oof_contract_recovery": _artifact(
                    root, root / MANIFEST_DIR / "week5_step07_xgb_contract_recovery_v1.json"
                ),
            },
            "hgb_cleanup_provenance": "EXPLICIT_GUARD_CLEANUP_SUCCESS",
            "xgb_cleanup_provenance": "EXPLICIT_GUARD_CLEANUP_SUCCESS",
        },
        "runtime_dependencies": {
            **next(
                (study["dependency_versions"] for study in studies if study["dependency_versions"]),
                {},
            ),
            "optuna_runtime": optuna.__version__,
        },
        "week6_boundary": boundary,
        "limitations": [
            "All reported model metrics are 2016-2022 development OOF diagnostics, not final test results.",
            "Weighted Ensemble, 2023 selection, SHAP, ARR ablation, and conditional DEP Weather ablation remain Week-6 work.",
            "ARR-B remains disabled because E006 has KEEP_SAFE=[].",
            "DEP-A/DEP-B remains blocked until point-in-time Weather provenance passes audit.",
        ],
        "acceptance": {
            "week4_historical_evidence_intact": True,
            "four_base_methods_available": True,
            "xgboost_baseline_complete": True,
            "six_hpo_studies_complete": True,
            "fixed_protocol_reproducible": True,
            "tuned_oof_complete": True,
            "oof_row_target_parity": True,
            "probability_metrics_use_probability": True,
            "signed_regression_preserved": True,
            "threshold_tuned": False,
            "temporal_and_leakage_contract": True,
            "week6_not_started": True,
        },
    }
    return summary


def _metric_text(metrics: Mapping[str, Any]) -> str:
    classification = metrics.get("classification", {})
    regression = metrics.get("regression", {})
    return (
        f"PR-AUC {classification.get('pr_auc'):.10f}; ROC-AUC {classification.get('roc_auc'):.10f}; "
        f"Brier {classification.get('brier_score'):.10f}; MAE {regression.get('mae'):.10f}; "
        f"RMSE {regression.get('rmse'):.10f}; R2 {regression.get('r2'):.10f}"
    )


def render_week5_report(summary: Mapping[str, Any]) -> str:
    protocol = summary["protocol"]
    lines = [
        "# Week 5 Core Arrival: XGBoost and Fixed-Budget Optuna Closeout",
        "",
        "## Purpose",
        "",
        "This report closes Week 5 after validating the four Core Arrival base methods, six fixed-budget HPO studies, and tuned rolling development OOF evidence. No Week-6 activity is performed here.",
        "",
        "## Frozen protocol",
        "",
        f"- Version: `{protocol['version']}`",
        f"- Hash: `{protocol['hash']}`",
        "- Four equal-weight temporal folds spanning validation years 2019-2022.",
        "- Classification maximizes macro mean PR-AUC from probabilities; regression minimizes macro mean MAE on signed ARR_DELAY.",
        "- Ten COMPLETE trials per study, TPESampler seed 202601, NopPruner, single-study parallelism, and 14,400 seconds per study.",
        "",
        "## Methods",
        "",
        "1. Logistic / Ridge - preserved Week-4 evidence.",
        "2. Random Forest - tuned Week-5 evidence.",
        "3. HistGradientBoosting - tuned Week-5 evidence.",
        "4. XGBoost - baseline plus tuned Week-5 evidence.",
        "5. Weighted Ensemble - not started; belongs to Week 6.",
        "",
        "## Production HPO studies",
        "",
        "| Study | Direction | COMPLETE | Best trial | Best objective | Cleanup provenance |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for study in summary.get("studies", []):
        lines.append(
            f"| `{study['study_id']}` | {study['direction']} | {study['complete_trials']} | "
            f"{study['best_trial']} | {study['best_objective']:.12g} | {study['cleanup']} |"
        )
    lines.extend(
        [
            "",
            "## RF environmental incident and amendments",
            "",
            "The original RF protocol-v1 Classification attempt remains `BLOCKED_INCOMPLETE` with three COMPLETE trials after an environmental wall-clock interruption. It was not resumed or counted as a completed production study. Fresh RF v1.1 Classification and Regression studies each reached 10 COMPLETE trials. The execution amendment and non-statistical cleanup-provenance amendment remain part of the authoritative history; historical Prompt 04F/04G failures are not rewritten.",
            "",
            "## Tuned development OOF",
            "",
            "All four methods use the same four validation folds and exact 1,254,518-row `flight_key`, `y_arr_cls`, and signed `y_arr_reg` universe.",
            "",
            "| Method | Rows | Pooled development OOF metrics |",
            "|---|---:|---|",
        ]
    )
    for method, evidence in summary.get("oof", {}).get("methods", {}).items():
        pooled = evidence.get("pooled_development_metrics") or {}
        lines.append(f"| {method} | {evidence['rows']:,} | {_metric_text(pooled)} |")
    lines.extend(
        [
            "",
            "These are 2016-2022 development OOF diagnostics, not final test results. No champion was selected from them.",
            "",
            "## Information and temporal boundaries",
            "",
            "- Population is inbound `DEST=ATL`; prediction cutoff is `CRS_DEP_TIME - 2 hours`.",
            "- HPO and OOF use 2016-2022 only. No row-level 2023 HPO access, 2023 selection, ensemble fitting, or row-level 2024 access occurred.",
            "- Arrival inputs exclude Weather, predicted Departure, DEP_DELAY, realized operations, and Chain predictors.",
            "- ARR-B remains disabled and Chain ML remains blocked pending new point-in-time evidence (`KEEP_SAFE=[]`).",
            "- External point-in-time Weather remains `AUDIT_REQUIRED`; no DEP-A/DEP-B Weather experiment ran in Week 5.",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary.get("limitations", []))
    lines.extend(
        [
            "",
            "## Week-6 readiness",
            "",
            "Week 5 is complete and the evidence is ready for the controlled Week-6 stage. Weighted Ensemble, 2023 comparison/selection, SHAP, ARR ablation, and conditional DEP Weather ablation remain not started. This report does not start Week 6 or open 2023/2024 row-level data.",
            "",
        ]
    )
    return "\n".join(lines)


def _materialize(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    manifest_path = root / FINAL_MANIFEST
    report_path = root / FINAL_REPORT
    collisions = [path for path in (manifest_path, report_path) if path.exists()]
    if collisions:
        raise FileExistsError(
            "refusing to overwrite immutable Week-5 closeout deliverable(s): "
            + ", ".join(str(path) for path in collisions)
        )
    summary = build_week5_closeout(root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_path.write_text(render_week5_report(summary), encoding="utf-8")
    return {
        "week5_final_status": summary["week5_final_status"],
        "manifest": _relative(root, manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "report": _relative(root, report_path),
        "report_sha256": _sha256(report_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    args = parser.parse_args()
    if args.verify == args.materialize:
        parser.error("choose exactly one of --verify or --materialize")
    root = resolve_project_root()
    result = (
        _materialize(root)
        if args.materialize
        else {
            "week5_final_status": build_week5_closeout(root)["week5_final_status"],
            "materialized": False,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
