from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

import pytest

from src.models.week5_hpo_execution import (
    ES_CONTINUOUS,
    ES_SYSTEM_REQUIRED,
    ENVIRONMENTAL_EXECUTION_INVALID,
    EnvironmentalExecutionInvalid,
    ExecutionObservation,
    GuardEventJournal,
    ExecutionReliabilityMonitor,
    HeartbeatJournal,
    HeartbeatRecord,
    HPOExecutionError,
    SuspendGapDetector,
    UnbiasedActiveTimeClock,
    query_unbiased_interrupt_time,
    heartbeat_monitor,
    run_guarded_objective,
    unbiased_active_seconds,
    windows_hpo_execution_guard,
)


def _api_recorder(results: list[int]) -> tuple[list[int], Callable[[int], int]]:
    calls: list[int] = []

    def invoke(flags: int) -> int:
        calls.append(flags)
        return results.pop(0)

    return calls, invoke


def test_windows_guard_requests_sleep_prevention_and_restores_on_normal_exit() -> None:
    """Catches wrong SetThreadExecutionState flags or missing normal cleanup."""

    calls, invoke = _api_recorder([1, 1])
    with windows_hpo_execution_guard(
        platform_name="win32", set_execution_state=invoke
    ) as metadata:
        assert metadata.guard_activated is True

    assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]
    assert metadata.guard_cleanup_attempted is True
    assert metadata.guard_cleanup_success is True


@pytest.mark.parametrize("raised", [RuntimeError("boom"), KeyboardInterrupt()])
def test_windows_guard_restores_on_exception_paths(raised: BaseException) -> None:
    """Catches leaked execution state after an exception or KeyboardInterrupt."""

    calls, invoke = _api_recorder([1, 1])
    with pytest.raises(type(raised)):
        with windows_hpo_execution_guard(platform_name="win32", set_execution_state=invoke):
            raise raised

    assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]


def test_windows_guard_entry_failure_blocks_before_protected_callback() -> None:
    """Catches fail-open execution after Windows rejects sleep prevention."""

    reached: list[bool] = []
    calls, invoke = _api_recorder([0])

    with pytest.raises(HPOExecutionError, match="sleep-prevention"):
        with windows_hpo_execution_guard(platform_name="win32", set_execution_state=invoke):
            reached.append(True)

    assert reached == []
    assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED]


def _guard_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_windows_guard_persists_activation_and_cleanup_success_events(
    tmp_path: Path,
) -> None:
    """Catches a successful Win32 cleanup whose return value is not persisted."""

    calls, invoke = _api_recorder([17, 23])
    timestamps = iter(
        [
            "2026-09-17T10:00:00+00:00",
            "2026-09-17T10:00:01+00:00",
            "2026-09-17T11:00:00+00:00",
            "2026-09-17T11:00:01+00:00",
        ]
    )
    path = tmp_path / "future.execution.jsonl"

    with windows_hpo_execution_guard(
        platform_name="win32",
        set_execution_state=invoke,
        event_journal=GuardEventJournal(path),
        protocol_version="week5_hpo_protocol_v1_1",
        study_id="hist_gradient_boosting_classification",
        utc_now=lambda: next(timestamps),
    ):
        pass

    events = _guard_events(path)
    assert [record["event"] for record in events] == [
        "GUARD_ACTIVATION_ATTEMPT",
        "GUARD_ACTIVATION_SUCCESS",
        "GUARD_CLEANUP_ATTEMPT",
        "GUARD_CLEANUP_SUCCESS",
    ]
    cleanup = events[-1]
    assert cleanup == {
        "event": "GUARD_CLEANUP_SUCCESS",
        "protocol_version": "week5_hpo_protocol_v1_1",
        "requested_flags": ES_CONTINUOUS,
        "set_thread_execution_state_return_value": 23,
        "study_id": "hist_gradient_boosting_classification",
        "success": True,
        "timestamp_utc": "2026-09-17T11:00:01+00:00",
    }
    assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]


def test_windows_guard_persists_cleanup_failure_and_fails_operationally(
    tmp_path: Path,
) -> None:
    """Catches a zero cleanup return being silently labelled successful."""

    _, invoke = _api_recorder([1, 0])
    path = tmp_path / "future.execution.jsonl"

    with pytest.raises(HPOExecutionError, match="cleanup failed"):
        with windows_hpo_execution_guard(
            platform_name="win32",
            set_execution_state=invoke,
            event_journal=GuardEventJournal(path),
            protocol_version="week5_hpo_protocol_v1_1",
            study_id="xgboost_regression",
        ):
            pass

    events = _guard_events(path)
    assert [record["event"] for record in events][-2:] == [
        "GUARD_CLEANUP_ATTEMPT",
        "GUARD_CLEANUP_FAILURE",
    ]
    assert events[-1]["set_thread_execution_state_return_value"] == 0
    assert events[-1]["success"] is False


@pytest.mark.parametrize("raised", [RuntimeError("boom"), KeyboardInterrupt()])
def test_windows_guard_persists_cleanup_outcome_on_exception_paths(
    tmp_path: Path, raised: BaseException
) -> None:
    """Catches exception paths that restore state without auditable telemetry."""

    _, invoke = _api_recorder([1, 1])
    path = tmp_path / f"{type(raised).__name__}.execution.jsonl"

    with pytest.raises(type(raised)):
        with windows_hpo_execution_guard(
            platform_name="win32",
            set_execution_state=invoke,
            event_journal=GuardEventJournal(path),
            protocol_version="week5_hpo_protocol_v1_1",
            study_id="future_study",
        ):
            raise raised

    events = _guard_events(path)
    assert [record["event"] for record in events][-2:] == [
        "GUARD_CLEANUP_ATTEMPT",
        "GUARD_CLEANUP_SUCCESS",
    ]


def test_windows_guard_persists_activation_failure_before_blocking(
    tmp_path: Path,
) -> None:
    """Catches entry failure with no durable explanation for the fail-closed run."""

    _, invoke = _api_recorder([0])
    path = tmp_path / "entry-failure.execution.jsonl"

    with pytest.raises(HPOExecutionError, match="sleep-prevention"):
        with windows_hpo_execution_guard(
            platform_name="win32",
            set_execution_state=invoke,
            event_journal=GuardEventJournal(path),
            protocol_version="week5_hpo_protocol_v1_1",
            study_id="future_study",
        ):
            pytest.fail("entry failure must block the protected action")

    events = _guard_events(path)
    assert [record["event"] for record in events] == [
        "GUARD_ACTIVATION_ATTEMPT",
        "GUARD_ACTIVATION_FAILURE",
    ]


def test_non_windows_production_guard_fails_closed() -> None:
    """Catches an unsupported platform silently running without sleep protection."""

    with pytest.raises(HPOExecutionError, match="Windows"):
        with windows_hpo_execution_guard(platform_name="linux"):
            pytest.fail("unsupported production platform entered protected block")


def test_unbiased_active_time_retrieval_and_unit_conversion() -> None:
    """Catches ignored API values or an incorrect 100-nanosecond conversion."""

    ticks = query_unbiased_interrupt_time(query=lambda: (True, 123_456_789))

    assert ticks == 123_456_789
    assert unbiased_active_seconds(ticks) == pytest.approx(12.3456789)


def test_unbiased_active_time_api_failure_fails_closed() -> None:
    """Catches fallback to an unreliable clock after the Windows API fails."""

    with pytest.raises(HPOExecutionError, match="QueryUnbiasedInterruptTime"):
        query_unbiased_interrupt_time(query=lambda: (False, 0))


def test_unbiased_active_time_clock_rejects_decreasing_samples() -> None:
    """Catches corrupt/non-monotonic active-time telemetry being accepted."""

    samples = iter([200, 201, 199])
    clock = UnbiasedActiveTimeClock(reader=lambda: next(samples))

    assert clock.observe() == 200
    assert clock.observe() == 201
    with pytest.raises(HPOExecutionError, match="decreased"):
        clock.observe()


@pytest.mark.parametrize(
    ("wall_delta", "active_delta", "expected_invalid"),
    [
        (30.0, 30.0, False),
        (300.0, 300.0, False),
        (300.0, 30.0, True),
        (149.0, 30.0, False),
        (150.0, 30.0, True),
        (151.0, 30.0, True),
    ],
)
def test_suspend_detector_uses_frozen_gap_boundary(
    wall_delta: float, active_delta: float, expected_invalid: bool
) -> None:
    """Catches wall-time-only detection and off-by-one threshold errors."""

    detector = SuspendGapDetector(threshold_seconds=120)
    detector.observe(ExecutionObservation(0.0, 0, 0.0))
    assessment = detector.observe(
        ExecutionObservation(
            wall_delta,
            int(active_delta * 10_000_000),
            active_delta,
        )
    )

    assert assessment.suspend_gap_seconds == pytest.approx(wall_delta - active_delta)
    assert assessment.environment_state == (
        ENVIRONMENTAL_EXECUTION_INVALID if expected_invalid else "VALID"
    )


@pytest.mark.parametrize(
    "corrupt",
    [
        ExecutionObservation(-1.0, 10, 1.0),
        ExecutionObservation(1.0, -1, 1.0),
        ExecutionObservation(1.0, 10, -1.0),
    ],
)
def test_suspend_detector_rejects_non_monotonic_observations(
    corrupt: ExecutionObservation,
) -> None:
    """Catches corrupt telemetry being silently treated as a valid environment."""

    detector = SuspendGapDetector(threshold_seconds=120)
    detector.observe(ExecutionObservation(0.0, 0, 0.0))

    with pytest.raises(HPOExecutionError, match="non-monotonic"):
        detector.observe(corrupt)


@pytest.mark.parametrize(
    "corrupt",
    [
        ExecutionObservation(-1.0, 0, 0.0),
        ExecutionObservation(0.0, -1, 0.0),
        ExecutionObservation(0.0, 0, -1.0),
    ],
)
def test_suspend_detector_rejects_corrupt_initial_observation(
    corrupt: ExecutionObservation,
) -> None:
    """Catches invalid clock baselines that would poison all later deltas."""

    detector = SuspendGapDetector(threshold_seconds=120)

    with pytest.raises(HPOExecutionError, match="corrupt"):
        detector.observe(corrupt)


def test_heartbeat_journal_appends_deterministic_execution_only_records(
    tmp_path: Path,
) -> None:
    """Catches journal overwrite and accidental model-metric persistence."""

    path = tmp_path / "study.execution.jsonl"
    journal = HeartbeatJournal(path)
    records = [
        HeartbeatRecord(
            timestamp_utc="2026-09-17T00:00:00+00:00",
            protocol_version="week5_hpo_protocol_v1_1",
            protocol_hash="abc",
            study_id="random_forest_classification",
            study_name="week5_hpo_protocol_v1_1__random_forest_classification",
            trial_number=None,
            wall_clock_seconds=10.0,
            unbiased_active_ticks=100_000_000,
            process_cpu_seconds=1.0,
            guard_active=True,
            suspend_gap_seconds=0.0,
            environment_state="VALID",
        ),
        HeartbeatRecord(
            timestamp_utc="2026-09-17T00:00:30+00:00",
            protocol_version="week5_hpo_protocol_v1_1",
            protocol_hash="abc",
            study_id="random_forest_classification",
            study_name="week5_hpo_protocol_v1_1__random_forest_classification",
            trial_number=0,
            wall_clock_seconds=40.0,
            unbiased_active_ticks=400_000_000,
            process_cpu_seconds=30.0,
            guard_active=True,
            suspend_gap_seconds=0.0,
            environment_state="VALID",
        ),
    ]

    journal.append(records[0])
    first_bytes = path.read_bytes()
    journal.append(records[1])
    lines = path.read_text(encoding="utf-8").splitlines()

    assert path.read_bytes().startswith(first_bytes)
    assert [json.loads(line)["trial_number"] for line in lines] == [None, 0]
    assert all("objective" not in json.loads(line) for line in lines)
    assert lines[0] == json.dumps(records[0].to_dict(), sort_keys=True, separators=(",", ":"))


def test_heartbeat_monitor_samples_immediately_and_stops_cleanly(tmp_path: Path) -> None:
    """Catches a journal that starts too late or leaks a worker after cleanup."""

    journal_path = tmp_path / "execution.jsonl"
    monitor = ExecutionReliabilityMonitor(
        protocol_version="week5_hpo_protocol_v1_1",
        protocol_hash="abc",
        study_id="random_forest_classification",
        study_name="week5_hpo_protocol_v1_1__random_forest_classification",
        detector=SuspendGapDetector(threshold_seconds=120),
        journal=HeartbeatJournal(journal_path),
    )

    with heartbeat_monitor(
        monitor,
        interval_seconds=3600,
        wall_clock=lambda: 10.0,
        active_tick_reader=lambda: 100_000_000,
        process_cpu=lambda: 1.0,
        utc_now=lambda: "2026-09-17T00:00:00+00:00",
        guard_active=lambda: True,
    ) as controller:
        assert controller.first_sample_completed.wait(timeout=1.0)
        assert controller.is_alive is True

    assert controller.is_alive is False
    record = json.loads(journal_path.read_text(encoding="utf-8"))
    assert record["guard_active"] is True
    assert record["environment_state"] == "VALID"


def test_environmental_invalidation_waits_for_safe_boundary_then_rejects_result(
    tmp_path: Path,
) -> None:
    """Catches promotion of a result produced during an invalid execution environment."""

    monitor = ExecutionReliabilityMonitor(
        protocol_version="week5_hpo_protocol_v1_1",
        protocol_hash="abc",
        study_id="random_forest_classification",
        study_name="week5_hpo_protocol_v1_1__random_forest_classification",
        detector=SuspendGapDetector(threshold_seconds=120),
        journal=HeartbeatJournal(tmp_path / "execution.jsonl"),
    )
    monitor.record_observation(
        ExecutionObservation(0.0, 0, 0.0),
        timestamp_utc="2026-09-17T00:00:00+00:00",
        guard_active=True,
    )
    effects: list[str] = []

    def objective() -> float:
        effects.append("current-call-finished")
        monitor.record_observation(
            ExecutionObservation(300.0, 300_000_000, 30.0),
            timestamp_utc="2026-09-17T00:05:00+00:00",
            guard_active=True,
        )
        return 0.5

    with pytest.raises(EnvironmentalExecutionInvalid):
        run_guarded_objective(objective, monitor=monitor, trial_number=2)

    assert effects == ["current-call-finished"]
    assert monitor.environment_state == ENVIRONMENTAL_EXECUTION_INVALID
    with pytest.raises(EnvironmentalExecutionInvalid):
        run_guarded_objective(
            lambda: effects.append("next-call-started") or 0.0,
            monitor=monitor,
            trial_number=3,
        )
    assert "next-call-started" not in effects
