"""Fresh-only, provenance-complete XGBoost Week-5 HPO runner for protocol v1.1."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import optuna
import psutil
import xgboost
from optuna.study import Study
from optuna.trial import TrialState

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_week4_linear_production import _load_fold, _process_memory  # noqa: E402
from scripts.run_week5_hist_gradient_boosting_hpo_v1_1 import (  # noqa: E402
    _guard_activation_success,
    _heartbeat_evidence,
    _journal_paths,
    _sha256,
    _sqlite_state_evidence,
    _storage_url,
    _utc_now,
    _validate_params,
    explicit_guard_cleanup_success,
)
from src.data.load_aeolus import resolve_project_root  # noqa: E402
from src.models.artifacts import write_json_artifact  # noqa: E402
from src.models.hpo import run_hpo_trial  # noqa: E402
from src.models.week5_contracts import (  # noqa: E402
    Week5StudySpec,
    assert_week5_result_artifact_writable,
    load_week5_study_specs,
)
from src.models.week5_hpo_execution import (  # noqa: E402
    ENVIRONMENTAL_EXECUTION_INVALID,
    EnvironmentalExecutionInvalid,
    ExecutionReliabilityMonitor,
    GuardEventJournal,
    HPOExecutionError,
    HeartbeatJournal,
    SuspendGapDetector,
    heartbeat_monitor,
    run_guarded_objective,
    windows_hpo_execution_guard,
)
from src.models.week5_hpo_protocol import (  # noqa: E402
    Week5HPOProtocol,
    Week5ProtocolViolation,
    aggregate_classification_objective,
    aggregate_regression_objective,
    build_optuna_components,
)
from src.models.week5_hpo_protocol_v1_1 import (  # noqa: E402
    assert_hpo_year_allowed,
    deterministic_v1_1_storage_path,
    load_week5_hpo_protocol_v1_1,
    validate_fresh_v1_1_storage,
)
from src.models.week5_xgboost_hpo import build_week5_xgboost_hpo_estimator  # noqa: E402


RUN_VERSION = "week5_xgboost_hpo_v1_1"
XGB_STUDY_IDS = ("xgboost_classification", "xgboost_regression")
RESULT_PATHS = {
    "xgboost_classification": Path("artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_classification_result_v1.json"),
    "xgboost_regression": Path("artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"),
}
SUMMARY_PATH = Path("artifacts/manifests/week5_xgboost_hpo_v1_1_summary_v1.json")


def _active_xgb_runner() -> bool:
    marker = "run_week5_xgboost_hpo_v1_1.py"
    current = psutil.Process()
    excluded = {current.pid, *(parent.pid for parent in current.parents())}
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            if process.info["pid"] not in excluded and marker in " ".join(process.info.get("cmdline") or []):
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False


def create_fresh_study(
    project_root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec, *, storage_path: Path, guard_active: bool
) -> Study:
    """Create precisely one zero-trial fresh XGBoost v1.1 study."""

    if not guard_active:
        raise HPOExecutionError("Windows execution guard must be active before storage")
    if spec.study_id not in XGB_STUDY_IDS:
        raise Week5ProtocolViolation("XGBoost runner permits only XGBoost studies")
    validate_fresh_v1_1_storage(project_root=project_root, study_id=spec.study_id, study_name=spec.study_name, storage_path=storage_path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    sampler, pruner = build_optuna_components(protocol)
    study = optuna.create_study(study_name=spec.study_name, storage=_storage_url(storage_path), direction=spec.direction, sampler=sampler, pruner=pruner, load_if_exists=False)
    if study.trials:
        raise Week5ProtocolViolation("fresh XGBoost v1.1 study did not start at zero trials")
    for name, value in {
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "study_id": spec.study_id,
        "status": "RUNNING",
        "parent_trials_carried_forward": False,
        "parent_best_params_enqueued": False,
    }.items():
        study.set_user_attr(name, value)
    return study


def optimize_fresh_study(study: Study, *, protocol: Week5HPOProtocol, objective: Callable[[Any], float], callbacks: list[Callable[[Study, Any], None]]) -> None:
    if study.trials:
        raise Week5ProtocolViolation("XGBoost production study must start with zero trials")
    study.optimize(objective, n_trials=int(protocol.config["budget"]["completed_trials_required"]), timeout=int(protocol.config["budget"]["timeout_seconds_per_study"]), n_jobs=1, catch=(), callbacks=callbacks)


def _load_hpo_fold(root: Path, fold: Any) -> Any:
    for year in (*fold.train_years, fold.validation_year):
        assert_hpo_year_allowed(int(year))
    return _load_fold(root, fold)


def _run_guarded_study(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec, *, guard_active: bool, heartbeat_path: Path) -> dict[str, Any]:
    execution = protocol.config["execution"]
    monitor = ExecutionReliabilityMonitor(
        protocol_version=protocol.protocol_version,
        protocol_hash=protocol.protocol_hash,
        study_id=spec.study_id,
        study_name=spec.study_name,
        detector=SuspendGapDetector(threshold_seconds=float(execution["suspend_gap_threshold_seconds"])),
        journal=HeartbeatJournal(heartbeat_path),
    )
    started = time.perf_counter()
    resource_samples = [_process_memory()]
    storage_path = deterministic_v1_1_storage_path(root, spec.study_id)
    with heartbeat_monitor(monitor, interval_seconds=float(execution["heartbeat_interval_seconds"]), guard_active=lambda: guard_active) as controller:
        if not controller.first_sample_completed.wait(timeout=5.0):
            raise HPOExecutionError("initial heartbeat sample timed out")
        controller.raise_if_invalid()
        study = create_fresh_study(root, protocol, spec, storage_path=storage_path, guard_active=guard_active)

        def objective(trial: Any) -> float:
            return run_guarded_objective(
                lambda: run_hpo_trial(spec, trial=trial, fold_data_provider=lambda fold: _load_hpo_fold(root, fold), estimator_factory=build_week5_xgboost_hpo_estimator, protocol=protocol),
                monitor=monitor,
                trial_number=int(trial.number),
            )

        def after_trial(active_study: Study, _trial: Any) -> None:
            resource_samples.append(_process_memory())
            if monitor.environment_state == ENVIRONMENTAL_EXECUTION_INVALID:
                active_study.set_user_attr("status", ENVIRONMENTAL_EXECUTION_INVALID)
                active_study.stop()

        try:
            optimize_fresh_study(study, protocol=protocol, objective=objective, callbacks=[after_trial])
            controller.raise_if_invalid()
        except EnvironmentalExecutionInvalid:
            study.set_user_attr("status", ENVIRONMENTAL_EXECUTION_INVALID)
            return {"status": ENVIRONMENTAL_EXECUTION_INVALID}
        except BaseException:
            study.set_user_attr("status", "INTERRUPTED")
            raise
        finally:
            gc.collect()
            resource_samples.append(_process_memory())
    complete = sum(item.state == TrialState.COMPLETE for item in study.trials)
    if complete != 10:
        study.set_user_attr("status", "BLOCKED_INCOMPLETE")
        return {"status": "BLOCKED_INCOMPLETE", "complete_trials": complete}
    study.set_user_attr("status", "COMPLETED")
    return {"status": "COMPLETED", "complete_trials": complete, "runtime_seconds": time.perf_counter() - started, "resource_samples": resource_samples}


def run_one_xgb_study(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec) -> dict[str, Any]:
    storage_path = deterministic_v1_1_storage_path(root, spec.study_id)
    heartbeat_path, guard_path = _journal_paths(storage_path)
    with windows_hpo_execution_guard(event_journal=GuardEventJournal(guard_path), protocol_version=protocol.protocol_version, study_id=spec.study_id) as metadata:
        if not metadata.guard_activated:
            raise HPOExecutionError("Windows execution guard is not active")
        outcome = _run_guarded_study(root, protocol, spec, guard_active=True, heartbeat_path=heartbeat_path)
    outcome.update({"guard_path": guard_path, "heartbeat_path": heartbeat_path})
    return outcome


def run_xgboost_sequence(run_study: Callable[[str], dict[str, Any]]) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for study_id in XGB_STUDY_IDS:
        outcome = run_study(study_id)
        outcomes.append(outcome)
        if outcome.get("status") != "COMPLETED":
            break
    return outcomes


def run_and_materialize_xgboost_sequence(run_study: Callable[[str], dict[str, Any]], materialize: Callable[[str, dict[str, Any]], None]) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for study_id in XGB_STUDY_IDS:
        outcome = run_study(study_id)
        outcomes.append(outcome)
        if outcome.get("status") != "COMPLETED":
            break
        materialize(study_id, outcome)
    return outcomes


def preflight_v1_1(project_root: Path, protocol: Week5HPOProtocol) -> dict[str, Any]:
    if _active_xgb_runner():
        return {"status": "IN_PROGRESS", "active_runner": True}
    if (project_root / SUMMARY_PATH).exists():
        raise Week5ProtocolViolation("conflicting completed XGBoost summary exists")
    specs = load_week5_study_specs(protocol)
    studies: list[dict[str, str]] = []
    for study_id in XGB_STUDY_IDS:
        spec = specs[study_id]
        storage_path = deterministic_v1_1_storage_path(project_root, study_id)
        heartbeat_path, guard_path = _journal_paths(storage_path)
        result_path = project_root / RESULT_PATHS[study_id]
        if any(path.exists() for path in (storage_path, heartbeat_path, guard_path, result_path)):
            raise Week5ProtocolViolation(f"fresh XGBoost production artifact collision for {study_id}")
        studies.append({"study_id": study_id, "study_name": spec.study_name, "storage": str(storage_path), "heartbeat": str(heartbeat_path), "guard_journal": str(guard_path), "initial_trial_count": "0"})
    return {"status": "PREFLIGHT_PASS", "active_runner": False, "protocol_version": protocol.protocol_version, "protocol_hash": protocol.protocol_hash, "studies": studies, "production_hpo_run": "NO", "row_level_2023_accessed": "NO", "row_level_2024_accessed": "NO"}


def _build_result_payload(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec, outcome: dict[str, Any]) -> dict[str, Any]:
    storage_path = deterministic_v1_1_storage_path(root, spec.study_id)
    heartbeat_path, guard_path = _journal_paths(storage_path)
    evidence = _sqlite_state_evidence(storage_path, spec.study_name)
    required_direction = "MAXIMIZE" if spec.task == "classification" else "MINIMIZE"
    states = evidence["state_counts"]
    if evidence["direction"] != required_direction or states["COMPLETE"] != 10 or any(states[key] != 0 for key in ("RUNNING", "FAIL", "PRUNED", "WAITING")):
        raise Week5ProtocolViolation("SQLite XGBoost states or direction do not satisfy production completion")
    study = optuna.load_study(study_name=spec.study_name, storage=_storage_url(storage_path))
    if study.user_attrs.get("protocol_hash") != protocol.protocol_hash or study.user_attrs.get("status") != "COMPLETED":
        raise Week5ProtocolViolation("SQLite XGBoost study provenance is invalid")
    best = study.best_trial
    fold_values = [float(value) for value in best.user_attrs.get("per_fold_objective", [])]
    if len(fold_values) != 4:
        raise Week5ProtocolViolation("best XGBoost trial does not contain four fold objectives")
    recomputed = aggregate_classification_objective(fold_values) if spec.task == "classification" else aggregate_regression_objective(fold_values)
    if abs(float(best.value) - recomputed) > 1e-12:
        raise Week5ProtocolViolation("stored XGBoost objective differs from four-fold recomputation")
    _validate_params(best.params, spec.search_space)
    heartbeat = _heartbeat_evidence(heartbeat_path, protocol=protocol, study_id=spec.study_id)
    activation = _guard_activation_success(guard_path, protocol_version=protocol.protocol_version, study_id=spec.study_id)
    cleanup = explicit_guard_cleanup_success(guard_path, protocol_version=protocol.protocol_version, study_id=spec.study_id)
    samples = outcome.get("resource_samples", [])
    rss = [int(item.get("process_rss_bytes", 0)) for item in samples if isinstance(item, dict)]
    starts = [datetime.fromisoformat(item["datetime_start"]) for item in evidence["trials"] if item["datetime_start"]]
    ends = [datetime.fromisoformat(item["datetime_complete"]) for item in evidence["trials"] if item["datetime_complete"]]
    return {
        "schema_version": "1.0.0", "result_manifest_version": "week5_xgboost_hpo_result_v1", "status": "COMPLETED", "created_at_utc": _utc_now(),
        "protocol_version": protocol.protocol_version, "protocol_hash": protocol.protocol_hash, "study_id": spec.study_id, "study_name": spec.study_name,
        "storage_path": str(storage_path.relative_to(root)), "storage_sha256": _sha256(storage_path), "initial_trial_count": 0, "expected_complete_trials": 10,
        "actual_trial_states": states, "direction": evidence["direction"], "best_trial": int(best.number), "best_params": best.params, "best_objective": float(best.value),
        "best_trial_per_fold_objective": fold_values, "best_trial_per_fold_metrics": best.user_attrs["per_fold_metrics"], "recomputed_objective": recomputed, "objective_match": True,
        "sampler": "TPESampler", "sampler_provenance": ["configs/week5_hpo_v1_1.yaml#randomness", "src/models/week5_hpo_protocol.py#build_optuna_components", "scripts/run_week5_xgboost_hpo_v1_1.py#create_fresh_study"],
        "pruner": "NopPruner", "pruner_provenance": ["configs/week5_hpo_v1_1.yaml#randomness", "artifacts/manifests/week5_hpo_protocol_v1_1.json#randomness", "src/models/week5_hpo_protocol.py#build_optuna_components", "scripts/run_week5_xgboost_hpo_v1_1.py#create_fresh_study"],
        "seed": 202601, "timeout_seconds_per_study": 14400, "optuna_parallelism": 1, "n_jobs": {"optuna": 1, "xgboost": 1}, "xgboost_version": xgboost.__version__,
        "search_space": dict(spec.search_space), "search_space_reference": f"configs/week5_hpo_v1_1.yaml#studies.{spec.study_id}", "fold_protocol_reference": "configs/week5_hpo_v1_1.yaml#folds",
        "feature_manifest_reference": spec.feature_manifest_version, "preprocessing_reference": spec.preprocessing_version, "objective_name": spec.objective_metric,
        "prediction_method": "predict_proba" if spec.task == "classification" else None, "signed_regression_target": spec.task == "regression",
        "study_start": min(starts).isoformat() if starts else None, "study_end": max(ends).isoformat() if ends else None,
        "runtime_seconds": outcome.get("runtime_seconds", (max(ends) - min(starts)).total_seconds() if starts and ends else None), "runtime_resources": {"samples": samples, "peak_rss_bytes": max(rss) if rss else None},
        **heartbeat, "guard_journal_path": str(guard_path.relative_to(root)), "guard_journal_sha256": _sha256(guard_path), "guard_activation_evidence": activation, "guard_cleanup_evidence": cleanup,
        "suspend_status": "NOT_DETECTED", "environment_valid": True, "row_level_2023_accessed": False, "row_level_2024_accessed": False,
        "weather_used": False, "departure_prediction_used": False, "dep_delay_predictor_used": False, "chain_used": False, "arr_b_enabled": False,
        "new_training_performed": True, "new_hpo_performed": True, "production_hpo": True,
    }


def _materialize_result(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec, outcome: dict[str, Any]) -> dict[str, Any]:
    payload = _build_result_payload(root, protocol, spec, outcome)
    target = root / RESULT_PATHS[spec.study_id]
    assert_week5_result_artifact_writable(target, protocol_hash=protocol.protocol_hash)
    write_json_artifact(target, payload)
    return payload


def verify_completed_xgb_run(root: Path, protocol: Week5HPOProtocol) -> dict[str, dict[str, Any]]:
    specs = load_week5_study_specs(protocol)
    results: dict[str, dict[str, Any]] = {}
    for study_id in XGB_STUDY_IDS:
        path = root / RESULT_PATHS[study_id]
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise Week5ProtocolViolation("XGBoost result manifest is unreadable") from error
        spec = specs[study_id]
        evidence = _sqlite_state_evidence(deterministic_v1_1_storage_path(root, study_id), spec.study_name)
        if result.get("protocol_hash") != protocol.protocol_hash or result.get("direction") != evidence["direction"] or evidence["state_counts"]["COMPLETE"] != 10 or any(evidence["state_counts"][key] != 0 for key in ("RUNNING", "FAIL", "PRUNED", "WAITING")) or result.get("objective_match") is not True:
            raise Week5ProtocolViolation("XGBoost post-run verification failed")
        _validate_params(dict(result["best_params"]), spec.search_space)
        _, guard_path = _journal_paths(deterministic_v1_1_storage_path(root, study_id))
        explicit_guard_cleanup_success(guard_path, protocol_version=protocol.protocol_version, study_id=study_id)
        results[study_id] = {"result_manifest": str(RESULT_PATHS[study_id]), "result_manifest_sha256": _sha256(path), "heartbeat": result["heartbeat_path"], "complete_trials": evidence["state_counts"]["COMPLETE"], "best_trial": result["best_trial"], "best_objective": result["best_objective"], "best_params": result["best_params"]}
    return results


def _write_summary(root: Path, protocol: Week5HPOProtocol) -> dict[str, Any]:
    payload = {"schema_version": "1.0.0", "summary_version": "week5_xgboost_hpo_v1_1_summary_v1", "status": "COMPLETED", "created_at_utc": _utc_now(), "protocol_version": protocol.protocol_version, "protocol_hash": protocol.protocol_hash, "method": "xgboost", "sampler": "TPESampler", "pruner": "NopPruner", "seed": 202601, "timeout_seconds_per_study": 14400, "optuna_parallelism": 1, "xgboost_n_jobs": 1, "xgboost_version": xgboost.__version__, "studies": verify_completed_xgb_run(root, protocol), "row_level_2023_accessed": False, "row_level_2024_accessed": False, "weather_used": False, "departure_prediction_used": False, "chain_used": False, "arr_b_enabled": False, "suspend_detected": False, "environment_valid": True, "result_manifests": "PASS", "guard_cleanup_explicit": "PASS", "new_training_performed": True, "production_hpo": True}
    write_json_artifact(root / SUMMARY_PATH, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--production", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = resolve_project_root()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    preflight = preflight_v1_1(root, protocol)
    if args.preflight or preflight["status"] == "IN_PROGRESS":
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0 if preflight["status"] == "PREFLIGHT_PASS" else 3
    specs = load_week5_study_specs(protocol)
    outcomes = run_and_materialize_xgboost_sequence(lambda study_id: run_one_xgb_study(root, protocol, specs[study_id]), lambda study_id, outcome: _materialize_result(root, protocol, specs[study_id], outcome))
    if len(outcomes) != 2 or any(item.get("status") != "COMPLETED" for item in outcomes):
        print(json.dumps({"status": "BLOCKED_INCOMPLETE", "outcomes": outcomes}, indent=2))
        return 2
    print(json.dumps(_write_summary(root, protocol), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
