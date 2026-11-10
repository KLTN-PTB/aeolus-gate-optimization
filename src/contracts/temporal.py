"""Temporal information contract, cutoff validation, and causality barriers for Aeolus.

Protocol: Aeolus Dual Core Architecture Protocol V4
Task: AEOLUS-G1 Temporal Information Contract & Non-Leakage Boundary Enforcement
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Final, Optional
from zoneinfo import ZoneInfo

from src.data.leakage_rules import (
    ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS,
    ARRIVAL_SAFE_COLUMNS,
    ARRIVAL_TARGET_COLUMNS,
    CORE_DEPARTURE_APPROVED_FEATURES,
    DEPARTURE_SAFE_COLUMNS,
    DEPARTURE_TARGET_COLUMNS,
    PREDICTION_CUTOFF_HOURS,
    SIMULATION_COLUMNS,
    WEATHER_COLUMNS,
)


class TemporalPointType(str, Enum):
    """Categorization of operational and computational points in time."""

    SCHEDULED_EVENT = "SCHEDULED_EVENT"
    PREDICTION_CUTOFF = "PREDICTION_CUTOFF"
    PREDICTION_ISSUED = "PREDICTION_ISSUED"
    FEATURE_AVAILABLE = "FEATURE_AVAILABLE"
    PLANNING_DECISION = "PLANNING_DECISION"
    ACTUAL_OBSERVATION = "ACTUAL_OBSERVATION"


class TemporalLeakageError(ValueError):
    """Raised when a feature or data element post-dates the prediction or decision cutoff."""


class TemporalUncertaintyError(ValueError):
    """Raised when timestamp or information availability cannot be verified fail-closed."""


class TemporalBoundaryError(ValueError):
    """Raised when time zones, date boundaries, or clock arithmetic are invalid."""


# Default Hub Timezone
DEFAULT_HUB_TIMEZONE: Final[str] = "America/New_York"
DEFAULT_CUTOFF_HOURS: Final[float] = float(PREDICTION_CUTOFF_HOURS)


def ensure_utc_datetime(dt: datetime, default_tz: str = DEFAULT_HUB_TIMEZONE) -> datetime:
    """Ensure datetime is timezone-aware UTC. Naive datetimes are localized via default_tz."""
    if dt is None:
        raise ValueError("Cannot convert None to UTC datetime")
    if dt.tzinfo is None:
        # Localize naive to default_tz first, then convert to UTC
        local_tz = ZoneInfo(default_tz)
        localized = dt.replace(tzinfo=local_tz)
        return localized.astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_prediction_cutoff_utc(
    scheduled_event_dt: datetime,
    hours_before: float = DEFAULT_CUTOFF_HOURS,
    event_tz: str = DEFAULT_HUB_TIMEZONE,
) -> datetime:
    """Calculate the authoritative UTC prediction cutoff (T - 2h by default)."""
    event_utc = ensure_utc_datetime(scheduled_event_dt, default_tz=event_tz)
    return event_utc - timedelta(hours=hours_before)


def validate_feature_temporal_availability(
    feature_name: str,
    available_at_utc: datetime | None,
    decision_cutoff_utc: datetime,
    *,
    allow_unverified: bool = False,
) -> None:
    """Enforce the fundamental temporal contract: available_at <= decision_cutoff.

    Args:
        feature_name: Column or feature identifier.
        available_at_utc: Timestamp when feature became observable/accessible.
        decision_cutoff_utc: The strict information boundary timestamp.
        allow_unverified: If False, missing available_at_utc raises TemporalUncertaintyError.

    Raises:
        TemporalLeakageError: If feature became available after decision cutoff.
        TemporalUncertaintyError: If available_at_utc is None and unverified access is disallowed.
    """
    if available_at_utc is None:
        if not allow_unverified:
            raise TemporalUncertaintyError(
                f"Feature '{feature_name}' has unknown/unverified availability timestamp. "
                f"Failing closed under Protocol V4 zero-leakage rules."
            )
        return

    cutoff = ensure_utc_datetime(decision_cutoff_utc)
    avail = ensure_utc_datetime(available_at_utc)

    if avail > cutoff:
        delta_sec = (avail - cutoff).total_seconds()
        raise TemporalLeakageError(
            f"TEMPORAL LEAKAGE DETECTED: Feature '{feature_name}' available at {avail.isoformat()} "
            f"which post-dates decision cutoff {cutoff.isoformat()} by {delta_sec:.1f}s."
        )


def is_column_provably_safe_at_cutoff(
    col_name: str,
    direction: str = "ARR",
) -> tuple[bool, str]:
    """Check if a raw or derived column is provably safe before T-2h cutoff without actual timestamps.

    Returns:
        (is_safe, rationale)
    """
    name = col_name.strip()
    upper = name.upper()

    # Immediate red flags: actual operational metrics
    if upper in ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS:
        return False, f"Post-cutoff actual operation column: {upper}"
    if upper in ARRIVAL_TARGET_COLUMNS or upper in DEPARTURE_TARGET_COLUMNS:
        return False, f"Ground-truth prediction target label: {upper}"
    if upper in SIMULATION_COLUMNS:
        return False, f"Simulation realization column: {upper}"
    if upper in WEATHER_COLUMNS:
        return False, f"Raw observed weather column without point-in-time timestamp proof: {upper}"

    # Approved schedule features
    if direction.upper() == "ARR":
        if name in ARRIVAL_SAFE_COLUMNS or upper in ARRIVAL_SAFE_COLUMNS:
            return True, "Approved baseline arrival schedule feature"
    else:
        if name in DEPARTURE_SAFE_COLUMNS or upper in DEPARTURE_SAFE_COLUMNS:
            return True, "Approved baseline departure schedule feature"
        if name in CORE_DEPARTURE_APPROVED_FEATURES:
            return True, "Approved core departure schedule feature"

    return False, f"Column '{name}' is not in certified safe list at T-2h"


@dataclass(frozen=True)
class OperationalTemporalProfile:
    """Authoritative operational timeline for a flight leg under the temporal contract."""

    flight_id: str
    direction: str  # ARR or DEP
    scheduled_event_local: datetime
    event_timezone: str = DEFAULT_HUB_TIMEZONE
    scheduled_event_utc: Optional[datetime] = None
    prediction_cutoff_utc: Optional[datetime] = None
    prediction_issued_at_utc: Optional[datetime] = None
    planning_snapshot_utc: Optional[datetime] = None

    def __post_init__(self) -> None:
        sched_utc = ensure_utc_datetime(self.scheduled_event_local, default_tz=self.event_timezone)
        cutoff_utc = self.prediction_cutoff_utc or (sched_utc - timedelta(hours=DEFAULT_CUTOFF_HOURS))

        # We must use object.__setattr__ because the dataclass is frozen
        if self.scheduled_event_utc is None:
            object.__setattr__(self, "scheduled_event_utc", sched_utc)
        if self.prediction_cutoff_utc is None:
            object.__setattr__(self, "prediction_cutoff_utc", cutoff_utc)

    def validate_causality(self) -> tuple[bool, list[str]]:
        """Validate all temporal causality constraints on this operational profile."""
        violations: list[str] = []
        assert self.scheduled_event_utc is not None
        assert self.prediction_cutoff_utc is not None

        # 1. Cutoff <= Scheduled Event
        if self.prediction_cutoff_utc > self.scheduled_event_utc:
            violations.append(
                f"Cutoff {self.prediction_cutoff_utc.isoformat()} is after scheduled event {self.scheduled_event_utc.isoformat()}."
            )

        # 2. Prediction issued must be at or after cutoff
        # (predictions are computed using data up to cutoff)
        if self.prediction_issued_at_utc is not None:
            if self.planning_snapshot_utc is not None and self.prediction_issued_at_utc > self.planning_snapshot_utc:
                violations.append(
                    f"Prediction issued at {self.prediction_issued_at_utc.isoformat()} post-dates planning snapshot {self.planning_snapshot_utc.isoformat()}."
                )

        return len(violations) == 0, violations
