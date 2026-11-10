"""Fresh-only Week-5 Random Forest HPO runner for protocol v1.1.

The execution amendment keeps all statistical HPO semantics unchanged while
preventing automatic Windows sleep and invalidating attempts that exhibit a
suspend-like wall-clock gap.  Importing this module never starts a study.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import optuna
from optuna.study import Study
from optuna.trial import TrialState


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_week4_linear_production import _load_fold, _process_memory  # noqa: E402
from src.data.load_aeolus import resolve_project_root  # noqa: E402
from src.models.artifacts import write_json_artifact  # noqa: E402
from src.models.hpo import run_hpo_trial  # noqa: E402
from src.models.week5_contracts import Week5StudySpec, load_week5_study_specs  # noqa: E402
from src.models.week5_hpo_execution import (  # noqa: E402
    ENVIRONMENTAL_EXECUTION_INVALID,
    EnvironmentalExecutionInvalid,
    ExecutionReliabilityMonitor,
    GuardEventJournal,
    HeartbeatJournal,
    HPOExecutionError,
    SuspendGapDetector,
    heartbeat_monitor,
    run_guarded_objective,
    windows_hpo_execution_guard,
)
from src.models.week5_hpo_protocol import (  # noqa: E402
    Week5HPOProtocol,
    Week5ProtocolViolation,
    build_optuna_components,
)
from src.models.week5_hpo_protocol_v1_1 import (  # noqa: E402
    assert_hpo_year_allowed,
    deterministic_v1_1_storage_path,
    load_week5_hpo_protocol_v1_1,
    validate_fresh_v1_1_storage,
)
from src.models.week5_random_forest_hpo import (  # noqa: E402
    build_week5_random_forest_estimator,
)


RUN_VERSION = "week5_random_forest_hpo_v1_1"
RF_STUDY_IDS = ("random_forest_classification", "random_forest_regression")
SUMMARY_MANIFEST = Path("artifacts/manifests") / f"{RUN_VERSION}_summary.json"
ResultT = TypeVar("ResultT")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _completed_trials(study: Study) -> int:
    return sum(trial.state == TrialState.COMPLETE for trial in study.trials)


def _journal_path(storage_path: Path) -> Path:
    return storage_path.with_suffix(".execution.jsonl")


def run_with_windows_guard(
    action: Callable[[Any], ResultT],
    *,
    guard_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    event_journal: GuardEventJournal | None = None,
    protocol_version: str | None = None,
    study_id: str | None = None,
) -> ResultT:
    """Activate sleep prevention before any production callback can run."""

    context = (
        guard_factory()
        if guard_factory is not None
        else windows_hpo_execution_guard(
            event_journal=event_journal,
            protocol_version=protocol_version,
            study_id=study_id,
        )
    )
    with context as metadata:
        if not bool(metadata.guard_activated):
            raise HPOExecutionError("Windows execution guard is not active")
        return action(metadata)


def create_fresh_study(
    project_root: Path,
    protocol: Week5HPOProtocol,
    spec: Week5StudySpec,
    *,
    storage_path: Path,
    guard_active: bool,
) -> Study:
    """Create exactly one zero-trial v1.1 study; resume/import is impossible."""

    if not guard_active:
        raise HPOExecutionError("Windows execution guard must be active before storage")
    if spec.study_id not in RF_STUDY_IDS:
        raise Week5ProtocolViolation("RF v1.1 runner permits only two RF studies")
    validate_fresh_v1_1_storage(
        project_root=project_root,
        study_id=spec.study_id,
        study_name=spec.study_name,
        storage_path=storage_path,
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    sampler, pruner = build_optuna_components(protocol)
    study = optuna.create_study(
        study_name=spec.study_name,
        storage=_storage_url(storage_path),
        direction=spec.direction,
        sampler=sampler,
        pruner=pruner,
        load_if_exists=False,
    )
    if study.trials:
        raise Week5ProtocolViolation("fresh v1.1 study did not start at zero trials")
    study.set_user_attr("protocol_version", protocol.protocol_version)
    study.set_user_attr("protocol_hash", protocol.protocol_hash)
    study.set_user_attr("study_id", spec.study_id)
    study.set_user_attr("status", "RUNNING")
    study.set_user_attr("parent_trials_carried_forward", False)
    study.set_user_attr("parent_best_params_enqueued", False)
    return study


def optimize_fresh_study(
    study: Any,
    *,
    protocol: Week5HPOProtocol,
    objective: Callable[[Any], float],
    callbacks: list[Callable[[Any, Any], None]] | None = None,
) -> None:
    """Issue the single frozen invocation-wide Optuna optimization call."""

    if len(study.trials) != 0:
        raise Week5ProtocolViolation("v1.1 production study must start with zero trials")
    arguments: dict[str, Any] = {
        "n_trials": int(protocol.config["budget"]["completed_trials_required"]),
        "timeout": int(protocol.config["budget"]["timeout_seconds_per_study"]),
        "n_jobs": 1,
        "catch": (),
    }
    if callbacks is not None:
        arguments["callbacks"] = callbacks
    study.optimize(objective, **arguments)


def stop_study_if_environment_invalid(
    study: Any, *, monitor: ExecutionReliabilityMonitor
) -> None:
    """Stop Optuna at its post-trial safe boundary after invalidation."""

    if monitor.environment_state == ENVIRONMENTAL_EXECUTION_INVALID:
        study.set_user_attr("status", ENVIRONMENTAL_EXECUTION_INVALID)
        study.stop()


def run_rf_sequence(
    run_study: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run regression only after classification legitimately completes."""

    summaries: list[dict[str, Any]] = []
    for study_id in RF_STUDY_IDS:
        summary = run_study(study_id)
        summaries.append(summary)
        if summary.get("status") != "COMPLETED":
            break
    return summaries


def preflight_v1_1(
    project_root: Path, protocol: Week5HPOProtocol
) -> dict[str, Any]:
    """Validate identities and negative production state without creating files."""

    specs = load_week5_study_specs(protocol)
    expected: list[dict[str, str]] = []
    for study_id in RF_STUDY_IDS:
        spec = specs[study_id]
        storage_path = deterministic_v1_1_storage_path(project_root, study_id)
        journal_path = _journal_path(storage_path)
        if storage_path.exists() or journal_path.exists():
            raise Week5ProtocolViolation(
                f"fresh v1.1 production artifact collision for {study_id}"
            )
        expected.append(
            {
                "study_id": study_id,
                "study_name": spec.study_name,
                "storage": str(storage_path),
                "heartbeat": str(journal_path),
            }
        )
    return {
        "status": "PREFLIGHT_PASS",
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "studies": expected,
        "production_hpo_run": "NO",
        "row_level_2023_accessed": "NO",
        "row_level_2024_accessed": "NO",
    }


def _load_hpo_fold(root: Path, fold: Any) -> Any:
    for year in (*fold.train_years, fold.validation_year):
        assert_hpo_year_allowed(int(year))
    return _load_fold(root, fold)


def _study_summary(
    protocol: Week5HPOProtocol,
    spec: Week5StudySpec,
    study: Study,
    storage_path: Path,
    *,
    status: str,
    started: float,
) -> dict[str, Any]:
    complete = _completed_trials(study)
    failed = sum(trial.state == TrialState.FAIL for trial in study.trials)
    best: dict[str, Any] | None = None
    if complete:
        trial = study.best_trial
        best = {"number": trial.number, "params": trial.params, "objective": trial.value}
    return {
        "run_version": RUN_VERSION,
        "status": status,
        "created_at_utc": _utc_now(),
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "study_id": spec.study_id,
        "study_name": spec.study_name,
        "storage": str(storage_path),
        "expected_complete_trials": 10,
        "complete_trials": complete,
        "failed_trials": failed,
        "best_trial": best,
        "wall_seconds": time.perf_counter() - started,
        "process_memory": _process_memory(),
        "row_level_2023_accessed": "NO",
        "row_level_2024_accessed": "NO",
    }


def _run_production_study(
    root: Path,
    protocol: Week5HPOProtocol,
    spec: Week5StudySpec,
    guard_metadata: Any,
) -> dict[str, Any]:
    storage_path = deterministic_v1_1_storage_path(root, spec.study_id)
    journal_path = _journal_path(storage_path)
    if journal_path.exists():
        raise Week5ProtocolViolation("fresh v1.1 heartbeat journal collision")
    execution = protocol.config["execution"]
    monitor = ExecutionReliabilityMonitor(
        protocol_version=protocol.protocol_version,
        protocol_hash=protocol.protocol_hash,
        study_id=spec.study_id,
        study_name=spec.study_name,
        detector=SuspendGapDetector(
            threshold_seconds=float(execution["suspend_gap_threshold_seconds"])
        ),
        journal=HeartbeatJournal(journal_path),
    )
    started = time.perf_counter()
    with heartbeat_monitor(
        monitor,
        interval_seconds=float(execution["heartbeat_interval_seconds"]),
        guard_active=lambda: bool(guard_metadata.guard_activated),
    ) as controller:
        if not controller.first_sample_completed.wait(timeout=5.0):
            raise HPOExecutionError("initial heartbeat sample timed out")
        controller.raise_if_invalid()
        study = create_fresh_study(
            root,
            protocol,
            spec,
            storage_path=storage_path,
            guard_active=bool(guard_metadata.guard_activated),
        )

        def objective(trial: Any) -> float:
            return run_guarded_objective(
                lambda: run_hpo_trial(
                    spec,
                    trial=trial,
                    fold_data_provider=lambda fold: _load_hpo_fold(root, fold),
                    estimator_factory=build_week5_random_forest_estimator,
                    protocol=protocol,
                ),
                monitor=monitor,
                trial_number=int(trial.number),
            )

        try:
            optimize_fresh_study(
                study,
                protocol=protocol,
                objective=objective,
                callbacks=[
                    lambda active_study, _trial: stop_study_if_environment_invalid(
                        active_study, monitor=monitor
                    )
                ],
            )
            controller.raise_if_invalid()
        except EnvironmentalExecutionInvalid:
            study.set_user_attr("status", ENVIRONMENTAL_EXECUTION_INVALID)
            raise
        except BaseException:
            study.set_user_attr("status", "INTERRUPTED")
            raise
        finally:
            gc.collect()

        if _completed_trials(study) != 10:
            study.set_user_attr("status", "BLOCKED_INCOMPLETE")
            return _study_summary(
                protocol,
                spec,
                study,
                storage_path,
                status="BLOCKED_INCOMPLETE",
                started=started,
            )
        study.set_user_attr("status", "COMPLETED")
        return _study_summary(
            protocol,
            spec,
            study,
            storage_path,
            status="COMPLETED",
            started=started,
        )


def _run_production_sequence(
    root: Path, protocol: Week5HPOProtocol, guard_metadata: Any
) -> list[dict[str, Any]]:
    specs = load_week5_study_specs(protocol)
    return run_rf_sequence(
        lambda study_id: _run_production_study(
            root, protocol, specs[study_id], guard_metadata
        )
    )


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
    if args.preflight:
        print(json.dumps(preflight_v1_1(root, protocol), indent=2))
        return 0

    summary_path = root / SUMMARY_MANIFEST
    if summary_path.exists():
        raise Week5ProtocolViolation(f"refusing to overwrite summary {summary_path}")
    summaries = run_with_windows_guard(
        lambda metadata: _run_production_sequence(root, protocol, metadata),
        event_journal=GuardEventJournal(
            root
            / "artifacts/optuna_studies"
            / f"{protocol.protocol_version}__random_forest_hpo_sequence.guard.jsonl"
        ),
        protocol_version=protocol.protocol_version,
        study_id="random_forest_hpo_sequence",
    )
    status = "COMPLETED" if len(summaries) == 2 and all(
        item["status"] == "COMPLETED" for item in summaries
    ) else "BLOCKED_INCOMPLETE"
    payload = {
        "run_version": RUN_VERSION,
        "status": status,
        "created_at_utc": _utc_now(),
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "study_summaries": summaries,
        "row_level_2023_accessed": "NO",
        "row_level_2024_accessed": "NO",
    }
    write_json_artifact(summary_path, payload)
    print(json.dumps(payload, indent=2))
    return 0 if status == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
