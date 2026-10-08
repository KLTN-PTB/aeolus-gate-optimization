"""Turn contracts and flight leg models for Aeolus Gate Optimization.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P6 Time Normalization & Arrival-Departure Pairing
Task: TurnPair and FlightLeg schema definition, pairing enums, and integrity constraints.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Final


class LegDirection(str, Enum):
    """Flight leg operational direction at the hub airport (ATL)."""

    ARR = "ARR"
    DEP = "DEP"


class PairType(str, Enum):
    """Classification of turn pair association.

    Rules:
    - VERIFIED_PAIR: ONLY permitted when physical airframe / tail rotation is verified.
    - SYNTHETIC_PAIR: Created by simulation generator, optimization session, or scenario fixture.
    - UNMATCHED_ARR: Inbound arrival without a scheduled/associated outbound flight.
    - UNMATCHED_DEP: Outbound departure without a scheduled/associated inbound flight.
    """

    VERIFIED_PAIR = "VERIFIED_PAIR"
    SYNTHETIC_PAIR = "SYNTHETIC_PAIR"
    UNMATCHED_ARR = "UNMATCHED_ARR"
    UNMATCHED_DEP = "UNMATCHED_DEP"


class ValidationStatus(str, Enum):
    """Audit and validation status of a turn pair or flight leg."""

    VALID = "VALID"
    INVALID = "INVALID"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    QUARANTINED = "QUARANTINED"


class LinkageSource(str, Enum):
    """Origin of the leg-to-leg pairing evidence."""

    VERIFIED_ROTATION = "VERIFIED_ROTATION"
    SIMULATION_SESSION = "SIMULATION_SESSION"
    SCHEDULE_CHAIN_HEURISTIC = "SCHEDULE_CHAIN_HEURISTIC"
    UNPAIRED = "UNPAIRED"


@dataclass(frozen=True)
class FlightLeg:
    """Immutable representation of a single flight leg (arrival or departure).

    Ensures explicit provenance, timezone tracking, and temporal causality boundaries.
    """

    flight_id: str
    direction: LegDirection
    carrier: str
    flight_number: str
    origin: str
    destination: str
    scheduled_event_local: datetime
    scheduled_event_utc: datetime | None = None
    event_timezone: str = "America/New_York"
    scheduled_elapsed_min: float | None = None
    model_prediction_cutoff_utc: datetime | None = None
    planning_snapshot_at_utc: datetime | None = None
    prediction_generated_at_utc: datetime | None = None
    prediction_provenance: str | None = None
    scenario_id: str | None = None
    session_id: str | None = None
    aircraft_type: str | None = None
    tail_number: str | None = None
    normalized_timeline_min: int | None = None
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_arrival(self) -> bool:
        return self.direction == LegDirection.ARR

    @property
    def is_departure(self) -> bool:
        return self.direction == LegDirection.DEP

    @property
    def has_verified_aircraft(self) -> bool:
        return self.tail_number is not None and len(self.tail_number.strip()) > 0


@dataclass(frozen=True)
class TurnPair:
    """Immutable representation of an aircraft turn pair at the hub gate.

    Governs the linkage between an inbound arrival and an outbound departure.
    """

    pair_id: str
    arrival_leg_id: str | None = None
    departure_leg_id: str | None = None
    pair_type: PairType = PairType.SYNTHETIC_PAIR
    linkage_source: LinkageSource = LinkageSource.SIMULATION_SESSION
    validation_status: ValidationStatus = ValidationStatus.VALID
    scheduled_turnaround_min: float | None = None
    scenario_id: str | None = None
    session_id: str | None = None
    evidence_metadata: Mapping[str, Any] = field(default_factory=dict)
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_paired(self) -> bool:
        return self.pair_type in (PairType.VERIFIED_PAIR, PairType.SYNTHETIC_PAIR)

    @property
    def is_valid(self) -> bool:
        return self.validation_status == ValidationStatus.VALID

    @property
    def is_synthetic(self) -> bool:
        return self.pair_type == PairType.SYNTHETIC_PAIR

    @property
    def is_verified(self) -> bool:
        return self.pair_type == PairType.VERIFIED_PAIR
