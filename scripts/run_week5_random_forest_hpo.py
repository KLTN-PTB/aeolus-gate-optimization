"""Production Week-5 Random Forest Optuna HPO under the frozen protocol.

The runner intentionally evaluates exactly the two Random Forest studies.  It
does not generate tuned OOF predictions, refit a final model, or select a
champion; those are later-week responsibilities.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import optuna
from optuna.study import Study
from optuna.trial import TrialState


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.load_aeolus import resolve_project_root  # noqa: E402
from src.models.artifacts import write_json_artifact  # noqa: E402
from src.models.hpo import run_hpo_trial  # noqa: E402
from src.models.week5_contracts import Week5StudySpec, load_week5_study_specs  # noqa: E402
from src.models.week5_hpo_protocol import (  # noqa: E402
    Week5HPOProtocol,
    Week5ProtocolViolation,
    assert_hpo_year_allowed,
    assert_study_resume_allowed,
    build_optuna_components,
    load_week5_hpo_protocol,
)
from src.models.week5_random_forest_hpo import build_week5_random_forest_estimator  # noqa: E402
from scripts.run_week4_linear_production import _load_fold, _process_memory  # noqa: E402


RUN_VERSION = "week5_random_forest_hpo_v1"
RF_STUDY_IDS = ("random_forest_classification", "random_forest_regression")
MANIFEST_DIR = Path("artifacts/manifests")
SUMMARY_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}_summary.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_url(storage_path: Path) -> str:
    return f"sqlite:///{storage_path.resolve().as_posix()}"


def _completed_trials(study: Study) -> int:
    return sum(trial.state == TrialState.COMPLETE for trial in study.trials)


def mark_study_status(study: Study, status: str) -> None:
    """Persist an explicit resumability status alongside the protocol hash."""

    if status not in {"RUNNING", "INTERRUPTED", "BLOCKED_INCOMPLETE", "COMPLETED"}:
        raise Week5ProtocolViolation(f"unsupported Week-5 study status {status!r}")
    study.set_user_attr("status", status)


def open_or_resume_study(
    protocol: Week5HPOProtocol,
    spec: Week5StudySpec,
    *,
    storage_path: Path,
) -> Study:
    """Create a new frozen study or fail-closed before a permitted resume."""

    if spec.study_id not in RF_STUDY_IDS:
        raise Week5ProtocolViolation("Prompt 04 permits only the two Random Forest studies")
    storage_path = Path(storage_path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_url = _storage_url(storage_path)
    if not storage_path.exists():
        sampler, pruner = build_optuna_components(protocol)
        study = optuna.create_study(
            study_name=spec.study_name,
            storage=storage_url,
            direction=spec.direction,
            sampler=sampler,
            pruner=pruner,
            load_if_exists=False,
        )
        study.set_user_attr("protocol_hash", protocol.protocol_hash)
        study.set_user_attr("study_id", spec.study_id)
        mark_study_status(study, "RUNNING")
        return study

    study = optuna.load_study(study_name=spec.study_name, storage=storage_url)
    assert_study_resume_allowed(
        protocol,
        study_name=study.study_name,
        stored_protocol_hash=str(study.user_attrs.get("protocol_hash", "")),
        study_status=str(study.user_attrs.get("status", "")),
        completed_trials=_completed_trials(study),
    )
    sampler, pruner = build_optuna_components(protocol)
    # A resumed study must preserve its historical sampler/pruner settings.
    if not isinstance(study.sampler, type(sampler)) or not isinstance(study.pruner, type(pruner)):
        raise Week5ProtocolViolation("stored RF study sampler/pruner differs from frozen protocol")
    mark_study_status(study, "RUNNING")
    return study


def _storage_path(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec) -> Path:
    config = protocol.config
    directory = Path(str(config["storage"]["directory"]))
    expected_template = f"sqlite:///{directory.as_posix()}/{{study_name}}.sqlite3"
    if str(config["storage"]["url_template"]) != expected_template:
        raise Week5ProtocolViolation("unexpected frozen Optuna storage URL template")
    return root / directory / f"{spec.study_name}.sqlite3"


def _load_hpo_fold(root: Path, fold: Any) -> Any:
    """Assert the HPO temporal guard before the historical row loader is invoked."""

    for year in (*fold.train_years, fold.validation_year):
        assert_hpo_year_allowed(int(year))
    return _load_fold(root, fold)


def _resource_totals(study: Study, storage_path: Path, started: float) -> dict[str, Any]:
    completed = [trial for trial in study.trials if trial.state == TrialState.COMPLETE]
    runtimes = [float(trial.user_attrs.get("runtime_seconds", 0.0)) for trial in completed]
    return {
        "wall_seconds": time.perf_counter() - started,
        "sum_completed_trial_seconds": sum(runtimes),
        "completed_trial_count": len(completed),
        "study_db_bytes": storage_path.stat().st_size if storage_path.exists() else 0,
        "process_memory": _process_memory(),
        "execution_parallelism": 1,
    }


def _study_summary(
    protocol: Week5HPOProtocol,
    spec: Week5StudySpec,
    study: Study,
    storage_path: Path,
    resource_totals: dict[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    complete = _completed_trials(study)
    best: dict[str, Any] | None = None
    if complete:
        trial = study.best_trial
        best = {"number": trial.number, "params": trial.params, "objective": trial.value}
    return {
        "run_version": RUN_VERSION,
        "status": status,
        "created_at_utc": _utc_now(),
        "protocol_hash": protocol.protocol_hash,
        "protocol_version": protocol.protocol_version,
        "study_id": spec.study_id,
        "study_name": spec.study_name,
        "study_storage": str(storage_path),
        "study_storage_url": _storage_url(storage_path),
        "dependency_versions": protocol.config["dependencies"],
        "expected_trials": int(protocol.config["budget"]["completed_trials_required"]),
        "completed_trials": complete,
        "direction": spec.direction,
        "objective_metric": spec.objective_metric,
        "best_trial": best,
        "resource_totals": resource_totals,
        "row_level_2023_access": "NO",
        "row_level_2024_access": "NO",
        "final_tuned_oof_refit": "NO",
        "champion_selected": "NO",
    }


def _run_study(root: Path, protocol: Week5HPOProtocol, spec: Week5StudySpec) -> dict[str, Any]:
    storage_path = _storage_path(root, protocol, spec)
    study = open_or_resume_study(protocol, spec, storage_path=storage_path)
    target = int(protocol.config["budget"]["completed_trials_required"])
    completed_before = _completed_trials(study)
    remaining = target - completed_before
    if remaining <= 0:
        raise Week5ProtocolViolation("completed RF study cannot be executed again")
    started = time.perf_counter()
    try:
        study.optimize(
            lambda trial: run_hpo_trial(
                spec,
                trial=trial,
                fold_data_provider=lambda fold: _load_hpo_fold(root, fold),
                estimator_factory=build_week5_random_forest_estimator,
                protocol=protocol,
            ),
            n_trials=remaining,
            timeout=int(protocol.config["budget"]["timeout_seconds_per_study"]),
            n_jobs=1,
            catch=(),
        )
    except BaseException:
        mark_study_status(study, "INTERRUPTED")
        raise
    finally:
        gc.collect()
    completed = _completed_trials(study)
    if completed != target:
        mark_study_status(study, "BLOCKED_INCOMPLETE")
        return _study_summary(
            protocol,
            spec,
            study,
            storage_path,
            _resource_totals(study, storage_path, started),
            status="BLOCKED_INCOMPLETE",
        )
    mark_study_status(study, "COMPLETED")
    return _study_summary(
        protocol,
        spec,
        study,
        storage_path,
        _resource_totals(study, storage_path, started),
        status="COMPLETED",
    )


def main() -> int:
    root = resolve_project_root()
    protocol = load_week5_hpo_protocol(project_root=root)
    specs = load_week5_study_specs(protocol)
    if (root / SUMMARY_MANIFEST).exists():
        raise FileExistsError(f"refusing to overwrite HPO summary: {root / SUMMARY_MANIFEST}")
    summaries: list[dict[str, Any]] = []
    for study_id in RF_STUDY_IDS:
        summary = _run_study(root, protocol, specs[study_id])
        summaries.append(summary)
        if summary["status"] != "COMPLETED":
            print(json.dumps(summary, indent=2), file=sys.stderr)
            return 2
    payload = {
        "run_version": RUN_VERSION,
        "status": "COMPLETED",
        "created_at_utc": _utc_now(),
        "protocol_hash": protocol.protocol_hash,
        "study_summaries": summaries,
        "row_level_2023_access": "NO",
        "row_level_2024_access": "NO",
        "final_tuned_oof_refit": "NO",
        "champion_selected": "NO",
    }
    write_json_artifact(root / SUMMARY_MANIFEST, payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
