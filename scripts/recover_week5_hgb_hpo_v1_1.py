"""Recover the HGB post-study artifact failure and continue Regression only."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import optuna


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_week5_hist_gradient_boosting_hpo_v1_1 import (  # noqa: E402
    RESULT_PATHS,
    SUMMARY_PATH,
    _guard_activation_success,
    _heartbeat_evidence,
    _journal_paths,
    _materialize_result,
    _sha256,
    _sqlite_state_evidence,
    _storage_url,
    _validate_params,
    explicit_guard_cleanup_success,
    run_one_hgb_study,
    verify_completed_hgb_run,
)
from src.data.load_aeolus import resolve_project_root  # noqa: E402
from src.models.artifacts import write_json_artifact  # noqa: E402
from src.models.week5_contracts import load_week5_study_specs  # noqa: E402
from src.models.week5_hpo_protocol import (  # noqa: E402
    Week5HPOProtocol,
    Week5ProtocolViolation,
    aggregate_classification_objective,
)
from src.models.week5_hpo_protocol_v1_1 import (  # noqa: E402
    deterministic_v1_1_storage_path,
    load_week5_hpo_protocol_v1_1,
)


RECOVERY_AMENDMENT_ID = "week5_hgb_poststudy_recovery_amendment_v1"
INCIDENT_TYPE = "POST_STUDY_ARTIFACT_MATERIALIZATION_FAILURE"
ROOT_CAUSE = "OPTUNA_SQLITE_SCHEMA_ASSUMPTION"
AMENDMENT_PATH = Path(
    "artifacts/manifests/week5_hgb_poststudy_recovery_amendment_v1.json"
)
CLASSIFICATION_ID = "hist_gradient_boosting_classification"
REGRESSION_ID = "hist_gradient_boosting_regression"
CLASSIFICATION_EVIDENCE_HASHES = {
    "sqlite_sha256": "663f6c81d55ed53b46900c67ebd8fec066d3789612deecb61fc1cd3f2cce12f4",
    "heartbeat_sha256": "207669331cf5650e4820f47d3fbfc69c9d14aa1e17c4ab782b6b7c3f872ccdc4",
    "guard_journal_sha256": "1b04ec9606ef2b8a2dfbc06f302258743ea88f1af215f3a6f7891e5f70e0b230",
}
PRE_RECOVERY_SOURCE_HASHES = {
    "protocol_manifest_sha256": "b7eed99fd42f5e6c907cb9fc57e0c48c8e53f1806134f91741a7042cd1e740a6",
    "protocol_config_sha256": "bcb6263f8a030fc149d72f409a912b17f1b4db20c638eb50a396c959726b973a",
    "hgb_runner_sha256": "a272b4d820fb62fff7817462d6906d583401f7200d25f31e12e5cbc847b51bf2",
    "hgb_estimator_factory_sha256": "8e13bf3dddb260d9799345e0871a83698c66941bc037fe982284ed2d3189ffec",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_classification_adoption(
    root: Path, protocol: Week5HPOProtocol
) -> dict[str, Any]:
    """Prove that the existing completed Classification study is adoptable."""

    specs = load_week5_study_specs(protocol)
    spec = specs[CLASSIFICATION_ID]
    storage_path = deterministic_v1_1_storage_path(root, CLASSIFICATION_ID)
    heartbeat_path, guard_path = _journal_paths(storage_path)
    observed_hashes = {
        "sqlite_sha256": _sha256(storage_path),
        "heartbeat_sha256": _sha256(heartbeat_path),
        "guard_journal_sha256": _sha256(guard_path),
    }
    if observed_hashes != CLASSIFICATION_EVIDENCE_HASHES:
        raise Week5ProtocolViolation("immutable Classification evidence hash mismatch")

    evidence = _sqlite_state_evidence(storage_path, spec.study_name)
    if evidence["direction"] != "MAXIMIZE" or evidence["state_counts"] != {
        "RUNNING": 0,
        "COMPLETE": 10,
        "PRUNED": 0,
        "FAIL": 0,
        "WAITING": 0,
    }:
        raise Week5ProtocolViolation("Classification trial-state adoption gate failed")
    best = evidence["best_trial"]
    if best["number"] != 7 or abs(best["value"] - 0.19206058881695232) > 1e-12:
        raise Week5ProtocolViolation("Classification best-trial adoption gate failed")
    _validate_params(best["params"], spec.search_space)
    fold_values = [float(item) for item in best["user_attrs"].get("per_fold_objective", [])]
    if len(fold_values) != 4:
        raise Week5ProtocolViolation("Classification lacks four fold objectives")
    recomputed = aggregate_classification_objective(fold_values)
    if abs(recomputed - best["value"]) > 1e-12:
        raise Week5ProtocolViolation("Classification objective recomputation failed")

    study = optuna.load_study(
        study_name=spec.study_name,
        storage=_storage_url(storage_path),
    )
    if (
        study.user_attrs.get("protocol_hash") != protocol.protocol_hash
        or study.user_attrs.get("protocol_version") != protocol.protocol_version
        or study.user_attrs.get("status") != "COMPLETED"
    ):
        raise Week5ProtocolViolation("Classification stored protocol/status mismatch")
    heartbeat = _heartbeat_evidence(
        heartbeat_path, protocol=protocol, study_id=CLASSIFICATION_ID
    )
    activation = _guard_activation_success(
        guard_path,
        protocol_version=protocol.protocol_version,
        study_id=CLASSIFICATION_ID,
    )
    cleanup = explicit_guard_cleanup_success(
        guard_path,
        protocol_version=protocol.protocol_version,
        study_id=CLASSIFICATION_ID,
    )
    after_hashes = {
        "sqlite_sha256": _sha256(storage_path),
        "heartbeat_sha256": _sha256(heartbeat_path),
        "guard_journal_sha256": _sha256(guard_path),
    }
    if after_hashes != observed_hashes:
        raise Week5ProtocolViolation("Classification evidence changed during adoption")
    evidence.update(
        {
            "recomputed_objective": recomputed,
            "objective_match": True,
            "per_fold_objective": fold_values,
            "evidence_hashes": observed_hashes,
            "heartbeat_evidence": heartbeat,
            "guard_activation_evidence": activation,
            "guard_cleanup_evidence": cleanup,
            "environment_valid": True,
            "suspend_detected": False,
        }
    )
    return evidence


def build_recovery_amendment_payload(
    protocol: Week5HPOProtocol, evidence: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "amendment_id": RECOVERY_AMENDMENT_ID,
        "amendment_type": "NON_STATISTICAL_EXECUTION_RECOVERY",
        "created_at_utc": _utc_now(),
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "incident_type": INCIDENT_TYPE,
        "root_cause": ROOT_CAUSE,
        "classification_study_status": "VALID_COMPLETE_PRODUCTION_STUDY",
        "classification_hpo_complete": True,
        "classification_complete_trials": evidence["state_counts"]["COMPLETE"],
        "classification_rerun": False,
        "classification_resume": False,
        "classification_optimize_called_again": False,
        "classification_new_trials": 0,
        "adopt_existing_completed_classification": True,
        "regression_status_before_recovery": "NOT_STARTED",
        "regression_started_before_failure": False,
        "statistical_protocol_changed": False,
        "model_results_changed": False,
        "row_level_2023_accessed": False,
        "row_level_2024_accessed": False,
        "classification_evidence_hashes": dict(CLASSIFICATION_EVIDENCE_HASHES),
        "pre_recovery_source_hashes": dict(PRE_RECOVERY_SOURCE_HASHES),
    }


def verify_fresh_regression_paths(root: Path, protocol: Week5HPOProtocol) -> dict[str, Any]:
    specs = load_week5_study_specs(protocol)
    spec = specs[REGRESSION_ID]
    storage_path = deterministic_v1_1_storage_path(root, REGRESSION_ID)
    heartbeat_path, guard_path = _journal_paths(storage_path)
    result_path = root / RESULT_PATHS[REGRESSION_ID]
    collisions = [
        str(path)
        for path in (storage_path, heartbeat_path, guard_path, result_path)
        if path.exists()
    ]
    if collisions:
        raise Week5ProtocolViolation(
            f"Regression artifact collision: {', '.join(collisions)}"
        )
    return {
        "study_id": REGRESSION_ID,
        "study_name": spec.study_name,
        "storage_path": str(storage_path),
        "initial_trial_count": 0,
    }


def continue_regression_only(
    run_study: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Expose a control flow in which Classification cannot be optimized."""

    return run_study(REGRESSION_ID)


def _write_recovery_amendment(
    root: Path, protocol: Week5HPOProtocol, evidence: dict[str, Any]
) -> dict[str, Any]:
    payload = build_recovery_amendment_payload(protocol, evidence)
    payload["fixed_source_hashes"] = {
        "hgb_runner_sha256": _sha256(
            root / "scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py"
        ),
        "recovery_runner_sha256": _sha256(
            root / "scripts/recover_week5_hgb_hpo_v1_1.py"
        ),
    }
    write_json_artifact(root / AMENDMENT_PATH, payload)
    return payload


def _materialize_adopted_classification(
    root: Path, protocol: Week5HPOProtocol, evidence: dict[str, Any]
) -> dict[str, Any]:
    specs = load_week5_study_specs(protocol)
    payload = _materialize_result(
        root,
        protocol,
        specs[CLASSIFICATION_ID],
        {"status": "COMPLETED", "resource_samples": []},
        recovery_amendment_id=RECOVERY_AMENDMENT_ID,
        generated_from_existing_completed_study=True,
        new_hpo_performed=False,
    )
    if (
        payload["actual_trial_states"] != evidence["state_counts"]
        or payload["best_trial"] != evidence["best_trial"]["number"]
        or abs(payload["best_objective"] - evidence["recomputed_objective"])
        > 1e-12
    ):
        raise Week5ProtocolViolation("Classification recovery manifest disagrees with evidence")
    return payload


def _verify_classification_manifest(root: Path, protocol: Week5HPOProtocol) -> dict[str, Any]:
    path = root / RESULT_PATHS[CLASSIFICATION_ID]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week5ProtocolViolation("Classification recovery manifest is unreadable") from error
    if (
        payload.get("protocol_hash") != protocol.protocol_hash
        or payload.get("recovery_amendment_id") != RECOVERY_AMENDMENT_ID
        or payload.get("generated_from_existing_completed_study") is not True
        or payload.get("new_hpo_performed") is not False
        or payload.get("classification_rerun") is not False
        or payload.get("classification_new_trials") != 0
        or payload.get("objective_match") is not True
    ):
        raise Week5ProtocolViolation("Classification recovery manifest gate failed")
    return payload


def _write_recovery_summary(
    root: Path, protocol: Week5HPOProtocol
) -> dict[str, Any]:
    verified = verify_completed_hgb_run(root, protocol)
    classification_path = root / RESULT_PATHS[CLASSIFICATION_ID]
    regression_path = root / RESULT_PATHS[REGRESSION_ID]
    classification = json.loads(classification_path.read_text(encoding="utf-8"))
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    payload = {
        "schema_version": "1.0.0",
        "summary_version": "week5_hist_gradient_boosting_hpo_v1_1_summary_v1",
        "status": "COMPLETED",
        "created_at_utc": _utc_now(),
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "method": "hist_gradient_boosting",
        "recovery_amendment": str(AMENDMENT_PATH),
        "recovery_amendment_sha256": _sha256(root / AMENDMENT_PATH),
        "incident_type": INCIDENT_TYPE,
        "root_cause": ROOT_CAUSE,
        "classification_rerun": False,
        "classification_new_trials": 0,
        "classification_adopted_existing_completed_study": True,
        "sampler": "TPESampler",
        "pruner": "NopPruner",
        "seed": 202601,
        "timeout_seconds_per_study": 14400,
        "optuna_parallelism": 1,
        "studies": verified,
        "classification_result_manifest": str(RESULT_PATHS[CLASSIFICATION_ID]),
        "classification_result_manifest_sha256": _sha256(classification_path),
        "classification_heartbeat": classification["heartbeat_path"],
        "classification_guard_journal": classification["guard_journal_path"],
        "regression_result_manifest": str(RESULT_PATHS[REGRESSION_ID]),
        "regression_result_manifest_sha256": _sha256(regression_path),
        "regression_heartbeat": regression["heartbeat_path"],
        "regression_guard_journal": regression["guard_journal_path"],
        "classification_evidence_hashes": dict(CLASSIFICATION_EVIDENCE_HASHES),
        "row_level_2023_accessed": False,
        "row_level_2024_accessed": False,
        "weather_used": False,
        "departure_prediction_used": False,
        "chain_used": False,
        "arr_b_enabled": False,
        "suspend_detected": False,
        "environment_valid": True,
        "result_manifests": "PASS",
        "guard_cleanup_explicit": "PASS",
        "new_training_performed": True,
        "production_hpo": True,
    }
    write_json_artifact(root / SUMMARY_PATH, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--recover-and-continue", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.preflight and not args.recover_and_continue:
        raise Week5ProtocolViolation("recovery mode is required")
    root = resolve_project_root()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    evidence = verify_classification_adoption(root, protocol)
    payload = {
        "status": "RECOVERY_PREFLIGHT_PASS",
        "incident_type": INCIDENT_TYPE,
        "root_cause": ROOT_CAUSE,
        "classification": {
            "status": "ADOPTED_COMPLETE",
            "complete": evidence["state_counts"]["COMPLETE"],
            "best_trial": evidence["best_trial"]["number"],
            "best_objective": evidence["best_trial"]["value"],
            "objective_match": evidence["objective_match"],
            "rerun": False,
            "new_trials": 0,
        },
    }
    if args.preflight:
        payload["regression"] = verify_fresh_regression_paths(root, protocol)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    _write_recovery_amendment(root, protocol, evidence)
    _materialize_adopted_classification(root, protocol, evidence)
    _verify_classification_manifest(root, protocol)
    regression = verify_fresh_regression_paths(root, protocol)
    specs = load_week5_study_specs(protocol)
    outcome = continue_regression_only(
        lambda study_id: run_one_hgb_study(root, protocol, specs[study_id])
    )
    if outcome.get("status") != "COMPLETED":
        print(
            json.dumps(
                {
                    "status": outcome.get("status", "BLOCKED_INCOMPLETE"),
                    "classification": "ADOPTED_COMPLETE",
                    "regression": outcome,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    _materialize_result(
        root,
        protocol,
        specs[REGRESSION_ID],
        outcome,
        recovery_amendment_id=RECOVERY_AMENDMENT_ID,
        generated_from_existing_completed_study=False,
        new_hpo_performed=True,
    )
    summary = _write_recovery_summary(root, protocol)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
