from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import optuna
import pytest
import scripts.run_week5_random_forest_hpo_v1_1 as rf_runner

from scripts.run_week5_random_forest_hpo_v1_1 import (
    RF_STUDY_IDS,
    create_fresh_study,
    optimize_fresh_study,
    preflight_v1_1,
    run_rf_sequence,
    run_with_windows_guard,
    stop_study_if_environment_invalid,
)
from src.models.week5_contracts import load_week5_study_specs
from src.models.week5_hpo_execution import (
    ENVIRONMENTAL_EXECUTION_INVALID,
    ExecutionReliabilityMonitor,
    GuardEventJournal,
    HeartbeatJournal,
    HPOExecutionError,
    SuspendGapDetector,
)
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import (
    deterministic_v1_1_storage_path,
    deterministic_v1_1_study_name,
    validate_fresh_v1_1_storage,
    load_week5_hpo_protocol_v1_1,
)


def test_v1_1_study_identity_is_new_and_deterministic(tmp_path: Path) -> None:
    """Catches accidental reuse of the blocked v1 study identity."""

    study_id = "random_forest_classification"
    name = deterministic_v1_1_study_name(study_id)
    path = deterministic_v1_1_storage_path(tmp_path, study_id)

    assert name == "week5_hpo_protocol_v1_1__random_forest_classification"
    assert path == tmp_path / "artifacts" / "optuna_studies" / f"{name}.sqlite3"
    assert "week5_hpo_protocol_v1__" not in name


def test_v1_1_rejects_parent_storage_name_and_any_collision(tmp_path: Path) -> None:
    """Catches resuming v1 or treating a populated v1.1 DB as a fresh attempt."""

    study_id = "random_forest_classification"
    expected_name = deterministic_v1_1_study_name(study_id)
    expected_path = deterministic_v1_1_storage_path(tmp_path, study_id)
    parent_path = tmp_path / "artifacts" / "optuna_studies" / (
        "week5_hpo_protocol_v1__random_forest_classification.sqlite3"
    )

    with pytest.raises(Week5ProtocolViolation, match="v1 parent"):
        validate_fresh_v1_1_storage(
            project_root=tmp_path,
            study_id=study_id,
            study_name="week5_hpo_protocol_v1__random_forest_classification",
            storage_path=parent_path,
        )

    expected_path.parent.mkdir(parents=True)
    expected_path.write_bytes(b"existing evidence")
    with pytest.raises(Week5ProtocolViolation, match="collision"):
        validate_fresh_v1_1_storage(
            project_root=tmp_path,
            study_id=study_id,
            study_name=expected_name,
            storage_path=expected_path,
        )


def test_runner_enters_windows_guard_before_production_callback() -> None:
    """Catches study/storage creation before sleep prevention is active."""

    events: list[str] = []

    @contextmanager
    def fake_guard() -> Any:
        events.append("guard-enter")
        yield SimpleNamespace(guard_activated=True)
        events.append("guard-exit")

    result = run_with_windows_guard(
        lambda metadata: events.append("production-callback") or metadata.guard_activated,
        guard_factory=fake_guard,
    )

    assert result is True
    assert events == ["guard-enter", "production-callback", "guard-exit"]


def test_runner_wires_future_guard_event_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a telemetry-capable guard that the production runner never enables."""

    captured: dict[str, object] = {}

    @contextmanager
    def fake_guard(**kwargs: object) -> Any:
        captured.update(kwargs)
        yield SimpleNamespace(guard_activated=True)

    monkeypatch.setattr(rf_runner, "windows_hpo_execution_guard", fake_guard)
    journal = GuardEventJournal(tmp_path / "future.guard.jsonl")

    result = run_with_windows_guard(
        lambda metadata: metadata.guard_activated,
        guard_factory=None,
        event_journal=journal,
        protocol_version="week5_hpo_protocol_v1_1",
        study_id="random_forest_hpo_sequence",
    )

    assert result is True
    assert captured == {
        "event_journal": journal,
        "protocol_version": "week5_hpo_protocol_v1_1",
        "study_id": "random_forest_hpo_sequence",
    }


def test_fresh_study_creation_starts_at_zero_and_rejects_collision(tmp_path: Path) -> None:
    """Catches v1 trial carry-forward, load_if_exists, and silent fresh-DB reuse."""

    protocol = load_week5_hpo_protocol_v1_1()
    spec = load_week5_study_specs(protocol)["random_forest_classification"]
    storage_path = deterministic_v1_1_storage_path(tmp_path, spec.study_id)

    study = create_fresh_study(
        tmp_path,
        protocol,
        spec,
        storage_path=storage_path,
        guard_active=True,
    )

    assert study.study_name == spec.study_name
    assert len(study.trials) == 0
    assert study.user_attrs["protocol_hash"] == protocol.protocol_hash
    assert study.user_attrs["parent_trials_carried_forward"] is False
    assert isinstance(study.sampler, optuna.samplers.TPESampler)
    assert isinstance(study.pruner, optuna.pruners.NopPruner)
    with pytest.raises(Week5ProtocolViolation, match="collision"):
        create_fresh_study(
            tmp_path,
            protocol,
            spec,
            storage_path=storage_path,
            guard_active=True,
        )


def test_fresh_study_creation_requires_active_sleep_guard(tmp_path: Path) -> None:
    """Catches storage creation when SetThreadExecutionState was not activated."""

    protocol = load_week5_hpo_protocol_v1_1()
    spec = load_week5_study_specs(protocol)["random_forest_classification"]
    storage_path = deterministic_v1_1_storage_path(tmp_path, spec.study_id)

    with pytest.raises(HPOExecutionError, match="guard"):
        create_fresh_study(
            tmp_path,
            protocol,
            spec,
            storage_path=storage_path,
            guard_active=False,
        )
    assert storage_path.exists() is False


def test_optimize_uses_one_frozen_invocation_without_timeout_reset() -> None:
    """Catches altered trial budget, timeout, parallelism, or repeated optimize calls."""

    protocol = load_week5_hpo_protocol_v1_1()

    class FakeStudy:
        trials: list[Any] = []

        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def optimize(self, objective: Any, **kwargs: Any) -> None:
            self.calls.append({"objective": objective, **kwargs})

    study = FakeStudy()
    objective = lambda trial: 0.0

    optimize_fresh_study(study, protocol=protocol, objective=objective)

    assert len(study.calls) == 1
    assert study.calls[0] == {
        "objective": objective,
        "n_trials": 10,
        "timeout": 14400,
        "n_jobs": 1,
        "catch": (),
    }


def test_rf_sequence_never_starts_regression_after_incomplete_classification() -> None:
    """Catches workflow progression after a blocked classification study."""

    called: list[str] = []

    def run_study(study_id: str) -> dict[str, str]:
        called.append(study_id)
        return {"status": "BLOCKED_INCOMPLETE"}

    result = run_rf_sequence(run_study)

    assert RF_STUDY_IDS == (
        "random_forest_classification",
        "random_forest_regression",
    )
    assert called == ["random_forest_classification"]
    assert result == [{"status": "BLOCKED_INCOMPLETE"}]


def test_optuna_callback_stops_scheduling_after_environment_invalidation(
    tmp_path: Path,
) -> None:
    """Catches a suspend event between trials allowing another trial to start."""

    monitor = ExecutionReliabilityMonitor(
        protocol_version="week5_hpo_protocol_v1_1",
        protocol_hash="abc",
        study_id="random_forest_classification",
        study_name="week5_hpo_protocol_v1_1__random_forest_classification",
        detector=SuspendGapDetector(threshold_seconds=120),
        journal=HeartbeatJournal(tmp_path / "execution.jsonl"),
    )
    monitor.environment_state = ENVIRONMENTAL_EXECUTION_INVALID

    class FakeStudy:
        def __init__(self) -> None:
            self.stopped = False
            self.attrs: dict[str, str] = {}

        def stop(self) -> None:
            self.stopped = True

        def set_user_attr(self, name: str, value: str) -> None:
            self.attrs[name] = value

    study = FakeStudy()

    stop_study_if_environment_invalid(study, monitor=monitor)

    assert study.stopped is True
    assert study.attrs["status"] == ENVIRONMENTAL_EXECUTION_INVALID


def test_preflight_validates_without_creating_storage_or_heartbeat(tmp_path: Path) -> None:
    """Catches dry validation accidentally starting a production attempt."""

    protocol = load_week5_hpo_protocol_v1_1()

    payload = preflight_v1_1(tmp_path, protocol)

    assert payload["status"] == "PREFLIGHT_PASS"
    assert payload["production_hpo_run"] == "NO"
    assert list(tmp_path.rglob("*.sqlite3")) == []
    assert list(tmp_path.rglob("*.execution.jsonl")) == []
