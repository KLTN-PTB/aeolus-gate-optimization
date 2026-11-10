"""Execution-only reliability controls for Week-5 HPO production runs."""

from __future__ import annotations

import ctypes
import json
import math
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar


ES_SYSTEM_REQUIRED = 0x00000001
ES_CONTINUOUS = 0x80000000
ENVIRONMENTAL_EXECUTION_INVALID = "ENVIRONMENTAL_EXECUTION_INVALID"


class HPOExecutionError(RuntimeError):
    """Raised when production execution reliability cannot be guaranteed."""


class EnvironmentalExecutionInvalid(HPOExecutionError):
    """Raised at a safe boundary after suspension invalidates an attempt."""


@dataclass
class ExecutionGuardMetadata:
    platform: str
    guard_requested: bool = True
    guard_activated: bool = False
    guard_cleanup_attempted: bool = False
    guard_cleanup_success: bool = False


def _query_unbiased_interrupt_time() -> tuple[bool, int]:
    value = ctypes.c_ulonglong()
    function = ctypes.windll.kernel32.QueryUnbiasedInterruptTime  # type: ignore[attr-defined]
    function.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
    function.restype = ctypes.c_ubyte
    success = bool(function(ctypes.byref(value)))
    return success, int(value.value)


def query_unbiased_interrupt_time(
    *, query: Callable[[], tuple[bool, int]] | None = None
) -> int:
    """Return Windows active-system time in native 100-nanosecond ticks."""

    success, ticks = (query or _query_unbiased_interrupt_time)()
    if not success or type(ticks) is not int or ticks < 0:
        raise HPOExecutionError("QueryUnbiasedInterruptTime failed")
    return ticks


def unbiased_active_seconds(ticks: int) -> float:
    if type(ticks) is not int or ticks < 0:
        raise HPOExecutionError("unbiased active-time ticks must be nonnegative")
    return ticks / 10_000_000.0


@dataclass
class UnbiasedActiveTimeClock:
    reader: Callable[[], int] = query_unbiased_interrupt_time
    _previous: int | None = field(default=None, init=False)

    def observe(self) -> int:
        ticks = self.reader()
        if type(ticks) is not int or ticks < 0:
            raise HPOExecutionError("unbiased active-time sample is corrupt")
        if self._previous is not None and ticks < self._previous:
            raise HPOExecutionError("unbiased active-time sample decreased")
        self._previous = ticks
        return ticks


@dataclass(frozen=True)
class ExecutionObservation:
    wall_seconds: float
    unbiased_active_ticks: int
    process_cpu_seconds: float


@dataclass(frozen=True)
class SuspendAssessment:
    wall_delta_seconds: float
    active_delta_seconds: float
    process_cpu_delta_seconds: float
    suspend_gap_seconds: float
    environment_state: str


class SuspendGapDetector:
    def __init__(self, *, threshold_seconds: float) -> None:
        if not math.isfinite(threshold_seconds) or threshold_seconds <= 0:
            raise HPOExecutionError("suspend-gap threshold must be positive")
        self.threshold_seconds = float(threshold_seconds)
        self._previous: ExecutionObservation | None = None

    def observe(self, observation: ExecutionObservation) -> SuspendAssessment:
        if (
            not math.isfinite(observation.wall_seconds)
            or not math.isfinite(observation.process_cpu_seconds)
            or type(observation.unbiased_active_ticks) is not int
        ):
            raise HPOExecutionError("execution observation is corrupt")
        previous = self._previous
        if previous is None:
            if (
                observation.wall_seconds < 0
                or observation.unbiased_active_ticks < 0
                or observation.process_cpu_seconds < 0
            ):
                raise HPOExecutionError("execution observation is corrupt")
            self._previous = observation
            return SuspendAssessment(0.0, 0.0, 0.0, 0.0, "VALID")
        wall_delta = observation.wall_seconds - previous.wall_seconds
        tick_delta = observation.unbiased_active_ticks - previous.unbiased_active_ticks
        cpu_delta = observation.process_cpu_seconds - previous.process_cpu_seconds
        if wall_delta < 0 or tick_delta < 0 or cpu_delta < 0:
            raise HPOExecutionError("execution observation is non-monotonic")
        active_delta = unbiased_active_seconds(tick_delta)
        suspend_gap = wall_delta - active_delta
        state = (
            ENVIRONMENTAL_EXECUTION_INVALID
            if suspend_gap >= self.threshold_seconds
            else "VALID"
        )
        self._previous = observation
        return SuspendAssessment(
            wall_delta_seconds=wall_delta,
            active_delta_seconds=active_delta,
            process_cpu_delta_seconds=cpu_delta,
            suspend_gap_seconds=suspend_gap,
            environment_state=state,
        )


@dataclass(frozen=True)
class HeartbeatRecord:
    timestamp_utc: str
    protocol_version: str
    protocol_hash: str
    study_id: str
    study_name: str
    trial_number: int | None
    wall_clock_seconds: float
    unbiased_active_ticks: int
    process_cpu_seconds: float
    guard_active: bool
    suspend_gap_seconds: float
    environment_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HeartbeatJournal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, record: HeartbeatRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")


@dataclass(frozen=True)
class GuardEventRecord:
    timestamp_utc: str
    protocol_version: str
    study_id: str
    event: str
    requested_flags: int
    set_thread_execution_state_return_value: int | None
    success: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GuardEventJournal:
    """Append-only operational telemetry for the Windows execution guard."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, record: GuardEventRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")


class ExecutionReliabilityMonitor:
    def __init__(
        self,
        *,
        protocol_version: str,
        protocol_hash: str,
        study_id: str,
        study_name: str,
        detector: SuspendGapDetector,
        journal: HeartbeatJournal,
    ) -> None:
        self.protocol_version = protocol_version
        self.protocol_hash = protocol_hash
        self.study_id = study_id
        self.study_name = study_name
        self.detector = detector
        self.journal = journal
        self.trial_number: int | None = None
        self.environment_state = "VALID"

    def record_observation(
        self,
        observation: ExecutionObservation,
        *,
        timestamp_utc: str,
        guard_active: bool,
    ) -> SuspendAssessment:
        assessment = self.detector.observe(observation)
        if assessment.environment_state == ENVIRONMENTAL_EXECUTION_INVALID:
            self.environment_state = ENVIRONMENTAL_EXECUTION_INVALID
        self.journal.append(
            HeartbeatRecord(
                timestamp_utc=timestamp_utc,
                protocol_version=self.protocol_version,
                protocol_hash=self.protocol_hash,
                study_id=self.study_id,
                study_name=self.study_name,
                trial_number=self.trial_number,
                wall_clock_seconds=observation.wall_seconds,
                unbiased_active_ticks=observation.unbiased_active_ticks,
                process_cpu_seconds=observation.process_cpu_seconds,
                guard_active=guard_active,
                suspend_gap_seconds=assessment.suspend_gap_seconds,
                environment_state=self.environment_state,
            )
        )
        return assessment

    def raise_if_invalid(self) -> None:
        if self.environment_state == ENVIRONMENTAL_EXECUTION_INVALID:
            raise EnvironmentalExecutionInvalid(ENVIRONMENTAL_EXECUTION_INVALID)


class HeartbeatController:
    """Own one low-overhead background sampler for a production study."""

    def __init__(
        self,
        monitor: ExecutionReliabilityMonitor,
        *,
        interval_seconds: float,
        wall_clock: Callable[[], float],
        active_tick_reader: Callable[[], int],
        process_cpu: Callable[[], float],
        utc_now: Callable[[], str],
        guard_active: Callable[[], bool],
    ) -> None:
        if not math.isfinite(interval_seconds) or interval_seconds <= 0:
            raise HPOExecutionError("heartbeat interval must be positive")
        self.monitor = monitor
        self.interval_seconds = float(interval_seconds)
        self.wall_clock = wall_clock
        self.active_clock = UnbiasedActiveTimeClock(reader=active_tick_reader)
        self.process_cpu = process_cpu
        self.utc_now = utc_now
        self.guard_active = guard_active
        self.first_sample_completed = threading.Event()
        self._stop = threading.Event()
        self._failure: Exception | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"hpo-heartbeat-{monitor.study_id}",
            daemon=True,
        )

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def raise_if_invalid(self) -> None:
        self.monitor.raise_if_invalid()
        if self._failure is not None:
            raise HPOExecutionError("heartbeat monitor failed") from self._failure

    def _sample(self) -> None:
        self.monitor.record_observation(
            ExecutionObservation(
                wall_seconds=float(self.wall_clock()),
                unbiased_active_ticks=self.active_clock.observe(),
                process_cpu_seconds=float(self.process_cpu()),
            ),
            timestamp_utc=self.utc_now(),
            guard_active=bool(self.guard_active()),
        )

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._sample()
                self.first_sample_completed.set()
                if self._stop.wait(self.interval_seconds):
                    break
        except Exception as error:
            self._failure = error
            self.monitor.environment_state = ENVIRONMENTAL_EXECUTION_INVALID
            self.first_sample_completed.set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def heartbeat_monitor(
    monitor: ExecutionReliabilityMonitor,
    *,
    interval_seconds: float,
    wall_clock: Callable[[], float] = time.time,
    active_tick_reader: Callable[[], int] = query_unbiased_interrupt_time,
    process_cpu: Callable[[], float] = time.process_time,
    utc_now: Callable[[], str] = _utc_now,
    guard_active: Callable[[], bool] = lambda: True,
) -> Iterator[HeartbeatController]:
    """Start one heartbeat before study creation and always join it on exit."""

    controller = HeartbeatController(
        monitor,
        interval_seconds=interval_seconds,
        wall_clock=wall_clock,
        active_tick_reader=active_tick_reader,
        process_cpu=process_cpu,
        utc_now=utc_now,
        guard_active=guard_active,
    )
    controller.start()
    try:
        yield controller
    finally:
        controller.stop()


ObjectiveValue = TypeVar("ObjectiveValue")


def run_guarded_objective(
    objective: Callable[[], ObjectiveValue],
    *,
    monitor: ExecutionReliabilityMonitor,
    trial_number: int,
) -> ObjectiveValue:
    """Reject invalid environments before and after an uninterruptible objective."""

    monitor.raise_if_invalid()
    monitor.trial_number = trial_number
    value = objective()
    monitor.raise_if_invalid()
    return value


def _set_thread_execution_state(flags: int) -> int:
    function = ctypes.windll.kernel32.SetThreadExecutionState  # type: ignore[attr-defined]
    function.argtypes = [ctypes.c_uint]
    function.restype = ctypes.c_uint
    return int(function(flags))


@contextmanager
def windows_hpo_execution_guard(
    *,
    platform_name: str | None = None,
    set_execution_state: Callable[[int], int] | None = None,
    event_journal: GuardEventJournal | None = None,
    protocol_version: str | None = None,
    study_id: str | None = None,
    utc_now: Callable[[], str] = _utc_now,
) -> Iterator[ExecutionGuardMetadata]:
    """Prevent automatic Windows sleep and always restore normal state."""

    platform = platform_name or sys.platform
    if platform != "win32":
        raise HPOExecutionError("production HPO execution guard requires Windows")
    if event_journal is not None and (not protocol_version or not study_id):
        raise HPOExecutionError(
            "guard event telemetry requires protocol_version and study_id"
        )
    invoke = set_execution_state or _set_thread_execution_state
    metadata = ExecutionGuardMetadata(platform=platform)

    def record(
        event: str,
        *,
        requested_flags: int,
        return_value: int | None,
        success: bool | None,
    ) -> None:
        if event_journal is None:
            return
        event_journal.append(
            GuardEventRecord(
                timestamp_utc=utc_now(),
                protocol_version=str(protocol_version),
                study_id=str(study_id),
                event=event,
                requested_flags=requested_flags,
                set_thread_execution_state_return_value=return_value,
                success=success,
            )
        )

    entry_flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    record(
        "GUARD_ACTIVATION_ATTEMPT",
        requested_flags=entry_flags,
        return_value=None,
        success=None,
    )
    try:
        entry_return = invoke(entry_flags)
    except BaseException:
        record(
            "GUARD_ACTIVATION_FAILURE",
            requested_flags=entry_flags,
            return_value=None,
            success=False,
        )
        raise
    if entry_return == 0:
        record(
            "GUARD_ACTIVATION_FAILURE",
            requested_flags=entry_flags,
            return_value=entry_return,
            success=False,
        )
        raise HPOExecutionError("Windows sleep-prevention request failed")
    metadata.guard_activated = True
    try:
        record(
            "GUARD_ACTIVATION_SUCCESS",
            requested_flags=entry_flags,
            return_value=entry_return,
            success=True,
        )
        yield metadata
    finally:
        active_exception = sys.exc_info()[0] is not None
        metadata.guard_cleanup_attempted = True
        telemetry_error: BaseException | None = None
        try:
            record(
                "GUARD_CLEANUP_ATTEMPT",
                requested_flags=ES_CONTINUOUS,
                return_value=None,
                success=None,
            )
        except BaseException as error:
            telemetry_error = error
        cleanup_return: int | None = None
        try:
            cleanup_return = invoke(ES_CONTINUOUS)
            metadata.guard_cleanup_success = cleanup_return != 0
        except BaseException:
            metadata.guard_cleanup_success = False
            if not active_exception:
                raise
        try:
            record(
                (
                    "GUARD_CLEANUP_SUCCESS"
                    if metadata.guard_cleanup_success
                    else "GUARD_CLEANUP_FAILURE"
                ),
                requested_flags=ES_CONTINUOUS,
                return_value=cleanup_return,
                success=metadata.guard_cleanup_success,
            )
        except BaseException as error:
            telemetry_error = telemetry_error or error
        if not metadata.guard_cleanup_success and not active_exception:
            raise HPOExecutionError("Windows execution-state cleanup failed")
        if telemetry_error is not None and not active_exception:
            raise HPOExecutionError("Windows guard telemetry persistence failed") from telemetry_error
