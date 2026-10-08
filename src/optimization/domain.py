"""Domain Objects and Typed Structures for Gate Assignment Optimization (V2 Repaired).

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. FlightTimeWindow: gate occupancy interval [start, end) and overlap detection.
2. Gate: contact gate, finite remote stand, or unbounded overflow apron with availability and compatibility rules.
3. Flight: operational flight turn entity with timeline parameters (arrival, departure, turnaround, dwell).
4. GateResourceType: explicit enum {CONTACT_GATE, FINITE_REMOTE_STAND, UNBOUNDED_OVERFLOW_APRON}.
5. GateAssignmentState: explicit enum {CONTACT_GATE, REMOTE_STAND, UNASSIGNED}.
6. SolverStatus: normalized status {OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, TIMEOUT_NO_SOLUTION}.
7. TerminationReason: explicit solver termination reason enum.
8. GateAssignment: assigned flight-to-gate mapping with explicit state semantics.
9. ConstraintDiagnostic: independent verification of hard constraints outside the solver.
10. ObjectiveBreakdown: separated decision-dependent vs exogenous reporting cost components.
11. OptimizationResult: standardized solver status, runtime, diagnostics, and assignments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Mapping, Sequence

import numpy as np


class GateResourceType(str, Enum):
    """Categorization of gate resources in airfield topology."""

    CONTACT_GATE = "CONTACT_GATE"
    FINITE_REMOTE_STAND = "FINITE_REMOTE_STAND"
    UNBOUNDED_OVERFLOW_APRON = "UNBOUNDED_OVERFLOW_APRON"


class GateAssignmentState(str, Enum):
    """Explicit operational state of a flight's gate assignment."""

    CONTACT_GATE = "CONTACT_GATE"
    CONTACT = "CONTACT_GATE"
    REMOTE_STAND = "REMOTE_STAND"
    REMOTE_OVERFLOW = "REMOTE_STAND"
    UNASSIGNED = "UNASSIGNED"


class SolverStatus(str, Enum):
    """Normalized solver termination and solution status."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    TIMEOUT_NO_SOLUTION = "TIMEOUT_NO_SOLUTION"


class TerminationReason(str, Enum):
    """Explicit reason for solver run termination."""

    OPTIMAL_PROVEN = "OPTIMAL_PROVEN"
    OPTIMAL = "OPTIMAL_PROVEN"
    FEASIBLE_FOUND = "FEASIBLE_FOUND"
    FEASIBLE = "FEASIBLE_FOUND"
    TIME_LIMIT = "TIME_LIMIT"
    ITERATION_LIMIT = "ITERATION_LIMIT"
    HEURISTIC_STOP = "HEURISTIC_STOP"
    PROVEN_INFEASIBLE = "PROVEN_INFEASIBLE"
    INFEASIBLE = "PROVEN_INFEASIBLE"
    MODEL_ERROR = "MODEL_ERROR"
    MODEL_INVALID = "MODEL_ERROR"
    NO_FEASIBLE_SOLUTION = "NO_FEASIBLE_SOLUTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FlightTimeWindow:
    """Gate occupancy interval [start_min, end_min) in minutes from reference epoch."""

    start_min: int
    end_min: int
    buffer_min: int = 0

    def __post_init__(self) -> None:
        for field_name, val in [("start_min", self.start_min), ("end_min", self.end_min), ("buffer_min", self.buffer_min)]:
            if val is None or not math.isfinite(val):
                raise ValueError(f"FlightTimeWindow.{field_name} must be finite numeric, got {val}")
        if self.end_min < self.start_min:
            raise ValueError(
                f"end_min ({self.end_min}) must be >= start_min ({self.start_min})"
            )
        if self.buffer_min < 0:
            raise ValueError(f"buffer_min ({self.buffer_min}) must be >= 0")

    @property
    def duration_min(self) -> int:
        """Total duration of occupancy in minutes."""
        return int(self.end_min - self.start_min)

    def overlaps(self, other: FlightTimeWindow) -> bool:
        """Determine if this interval overlaps with another interval [s, e).

        Two half-open intervals [s1, e1) and [s2, e2) overlap iff max(s1, s2) < min(e1, e2).
        """
        return max(self.start_min, other.start_min) < min(self.end_min, other.end_min)

    def overlap_duration(self, other: FlightTimeWindow) -> int:
        """Calculate overlap duration in minutes (0 if disjoint)."""
        overlap = min(self.end_min, other.end_min) - max(self.start_min, other.start_min)
        return int(max(0, overlap))

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_min": int(self.start_min),
            "end_min": int(self.end_min),
            "buffer_min": int(self.buffer_min),
            "duration_min": int(self.duration_min),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FlightTimeWindow:
        return cls(
            start_min=int(data["start_min"]),
            end_min=int(data["end_min"]),
            buffer_min=int(data.get("buffer_min", 0)),
        )


@dataclass(frozen=True)
class Gate:
    """Gate or parking stand entity."""

    gate_id: str
    gate_index: int = 0
    is_overflow: bool = False
    allowed_carriers: frozenset[str] | None = None
    allowed_aircraft_types: frozenset[str] | None = None
    available_windows: tuple[tuple[int, int], ...] | None = None
    resource_type: GateResourceType | str | None = None
    capacity: int | float = 1

    def __post_init__(self) -> None:
        if not self.gate_id or not isinstance(self.gate_id, str) or not self.gate_id.strip():
            raise ValueError(f"Gate.gate_id must be a non-empty string, got '{self.gate_id}'")
        if self.gate_index is not None and self.gate_index < 0:
            raise ValueError(f"Gate.gate_index must be >= 0, got {self.gate_index}")

        # Capacity validation
        if self.capacity is not None and math.isfinite(self.capacity) and self.capacity <= 0:
            raise ValueError(f"Gate.capacity must be >= 1, got {self.capacity}")

        # Resolve resource_type
        if self.resource_type is not None:
            if isinstance(self.resource_type, str):
                resolved_res = GateResourceType(self.resource_type)
                object.__setattr__(self, "resource_type", resolved_res)
            else:
                resolved_res = self.resource_type
        else:
            if self.is_overflow:
                upper_id = str(self.gate_id).upper()
                if any(c.isdigit() for c in upper_id) and any(k in upper_id for k in ("STAND", "REMOTE")) and "APRON" not in upper_id:
                    resolved_res = GateResourceType.FINITE_REMOTE_STAND
                elif any(k in upper_id for k in ("APRON", "OVF", "OVERFLOW")):
                    resolved_res = GateResourceType.UNBOUNDED_OVERFLOW_APRON
                elif "STAND" in upper_id or "REMOTE" in upper_id:
                    resolved_res = GateResourceType.FINITE_REMOTE_STAND
                else:
                    resolved_res = GateResourceType.FINITE_REMOTE_STAND
            else:
                resolved_res = GateResourceType.CONTACT_GATE
            object.__setattr__(self, "resource_type", resolved_res)

        # Synchronize is_overflow and capacity
        if self.resource_type == GateResourceType.CONTACT_GATE:
            object.__setattr__(self, "is_overflow", False)
            object.__setattr__(self, "capacity", 1)
        elif self.resource_type == GateResourceType.FINITE_REMOTE_STAND:
            object.__setattr__(self, "is_overflow", True)
            cap = int(self.capacity) if (self.capacity is not None and math.isfinite(self.capacity)) else 1
            if cap < 1:
                raise ValueError(f"FINITE_REMOTE_STAND capacity must be >= 1, got {self.capacity}")
            object.__setattr__(self, "capacity", cap)
        elif self.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON:
            object.__setattr__(self, "is_overflow", True)
            object.__setattr__(self, "capacity", math.inf)

        if self.available_windows is not None:
            for w in self.available_windows:
                if len(w) != 2 or not math.isfinite(w[0]) or not math.isfinite(w[1]) or w[0] > w[1]:
                    raise ValueError(f"Invalid available_window tuple: {w}")

    @property
    def is_remote_stand(self) -> bool:
        """True if gate is a remote stand/apron rather than a physical contact terminal gate."""
        return bool(self.resource_type in (GateResourceType.FINITE_REMOTE_STAND, GateResourceType.UNBOUNDED_OVERFLOW_APRON))

    @property
    def is_finite(self) -> bool:
        """True if gate has finite discrete capacity."""
        return math.isfinite(self.capacity) and self.capacity > 0

    @property
    def is_unbounded(self) -> bool:
        """True if gate has infinite overflow capacity."""
        return not math.isfinite(self.capacity)

    def is_compatible_carrier(self, carrier: str) -> bool:
        """Check if carrier is allowed at this gate."""
        if self.allowed_carriers is None:
            return True
        return carrier in self.allowed_carriers

    def is_compatible_aircraft(self, aircraft_type: str | None) -> bool:
        """Check if aircraft type is allowed at this gate.

        Declared policy: If aircraft_type is None or gate specifies no constraints,
        the flight is considered compatible (unconstrained).
        """
        if self.allowed_aircraft_types is None or aircraft_type is None:
            return True
        return aircraft_type in self.allowed_aircraft_types

    def can_accommodate(self, aircraft_type: str | None) -> bool:
        """Check if gate can accommodate the aircraft type (alias to is_compatible_aircraft)."""
        return self.is_compatible_aircraft(aircraft_type)

    def is_available_during(self, window: FlightTimeWindow) -> bool:
        """Check if gate is operational and open during the required flight time window."""
        if self.available_windows is None:
            return True
        for w_start, w_end in self.available_windows:
            if w_start <= window.start_min and window.end_min <= w_end:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_index": self.gate_index,
            "is_overflow": self.is_overflow,
            "resource_type": self.resource_type.value if isinstance(self.resource_type, GateResourceType) else str(self.resource_type),
            "capacity": float(self.capacity) if math.isfinite(self.capacity) else "unbounded",
            "allowed_carriers": sorted(list(self.allowed_carriers)) if self.allowed_carriers is not None else None,
            "allowed_aircraft_types": sorted(list(self.allowed_aircraft_types)) if self.allowed_aircraft_types is not None else None,
            "available_windows": list(self.available_windows) if self.available_windows is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Gate:
        res_t = data.get("resource_type")
        raw_cap = data.get("capacity", 1)
        cap = math.inf if (raw_cap == "unbounded" or raw_cap is None) else float(raw_cap)
        carriers = frozenset(data["allowed_carriers"]) if data.get("allowed_carriers") is not None else None
        types_ = frozenset(data["allowed_aircraft_types"]) if data.get("allowed_aircraft_types") is not None else None
        windows = tuple(tuple(w) for w in data["available_windows"]) if data.get("available_windows") is not None else None
        return cls(
            gate_id=str(data["gate_id"]),
            gate_index=int(data["gate_index"]),
            is_overflow=bool(data.get("is_overflow", False)),
            allowed_carriers=carriers,
            allowed_aircraft_types=types_,
            available_windows=windows,
            resource_type=res_t,
            capacity=cap,
        )


@dataclass(frozen=True)
class Flight:
    """Operational flight turn entity with timeline and schedule attributes."""

    flight_id: str
    flight_index: int
    carrier: str
    flight_number: str
    scheduled_arrival_min: int
    scheduled_departure_min: int
    predicted_arrival_min: int
    aircraft_type: str | None = None
    nominal_gate_id: str | None = None
    min_turnaround_min: int = 45
    default_dwell_min: int = 60
    buffer_min: int = 15
    is_paired: bool = False
    precomputed_gate_out_min: int | None = None

    def __post_init__(self) -> None:
        if not self.flight_id or not isinstance(self.flight_id, str) or not self.flight_id.strip():
            raise ValueError(f"Flight.flight_id must be a non-empty string, got '{self.flight_id}'")
        if self.flight_index is not None and self.flight_index < 0:
            raise ValueError(f"Flight.flight_index must be >= 0, got {self.flight_index}")

        for field_name, val in [
            ("scheduled_arrival_min", self.scheduled_arrival_min),
            ("scheduled_departure_min", self.scheduled_departure_min),
            ("predicted_arrival_min", self.predicted_arrival_min),
            ("min_turnaround_min", self.min_turnaround_min),
            ("default_dwell_min", self.default_dwell_min),
            ("buffer_min", self.buffer_min),
        ]:
            if val is None or not math.isfinite(val):
                raise ValueError(f"Flight.{field_name} must be finite numeric, got {val}")

        if self.min_turnaround_min <= 0:
            raise ValueError(f"Flight.min_turnaround_min must be positive (> 0), got {self.min_turnaround_min}")
        if self.default_dwell_min <= 0:
            raise ValueError(f"Flight.default_dwell_min must be positive (> 0), got {self.default_dwell_min}")
        if self.buffer_min < 0:
            raise ValueError(f"Flight.buffer_min must be non-negative (>= 0), got {self.buffer_min}")

        # Missing aircraft type normalization (empty or whitespace string becomes None)
        if self.aircraft_type is not None and not str(self.aircraft_type).strip():
            object.__setattr__(self, "aircraft_type", None)

        if self.precomputed_gate_out_min is not None:
            if not math.isfinite(self.precomputed_gate_out_min):
                raise ValueError(f"Flight.precomputed_gate_out_min must be finite, got {self.precomputed_gate_out_min}")
            min_turn = self.predicted_arrival_min + self.min_turnaround_min
            if self.precomputed_gate_out_min < min_turn:
                raise ValueError(
                    f"precomputed_gate_out_min ({self.precomputed_gate_out_min}) violates physical minimum "
                    f"turnaround: must be >= predicted_arrival_min ({self.predicted_arrival_min}) + "
                    f"min_turnaround_min ({self.min_turnaround_min}) = {min_turn}"
                )

    @property
    def arrival_delay_min(self) -> int:
        """Signed arrival delay in minutes."""
        return int(self.predicted_arrival_min - self.scheduled_arrival_min)

    @property
    def gate_in_min(self) -> int:
        """Gate-in time when aircraft enters the gate (alias to predicted_arrival_min)."""
        return int(self.predicted_arrival_min)

    @property
    def gate_out_min(self) -> int:
        """Physical gate-out / pushback time (alias to simulated_departure_min)."""
        return int(self.simulated_departure_min)

    @property
    def occupancy_start_min(self) -> int:
        """Start of gate occupancy interval."""
        return int(self.predicted_arrival_min)

    @property
    def occupancy_end_min(self) -> int:
        """End of gate occupancy interval (including separation buffer)."""
        return int(self.gate_release_min)

    @property
    def physical_dwell_min(self) -> int:
        """Physical turnaround / dwell duration at gate before separation buffer: gate_out - gate_in."""
        return int(max(0, self.simulated_departure_min - self.predicted_arrival_min))

    @property
    def scheduled_dwell_min(self) -> int:
        """Scheduled turnaround / dwell duration according to timetable: D_sched - A_sched."""
        return int(max(0, self.scheduled_departure_min - self.scheduled_arrival_min))

    @property
    def turnaround_slack_min(self) -> int:
        """Turnaround slack above minimum physical turnaround: physical_dwell - min_turnaround."""
        return int(self.physical_dwell_min - self.min_turnaround_min)

    @property
    def simulated_departure_min(self) -> int:
        """Simulated departure time respecting minimum turnaround.

        Timeline semantics:
        1. If precomputed_gate_out_min is provided (from certified Dual Turn Engine), return it directly.
        2. Otherwise (legacy mode):
           D_min = A_pred + min_turnaround_min (physical turnaround requirement)
           D_sched = scheduled_departure_min if (paired or explicit departure) else A_sched + default_dwell_min
           D_pred = max(D_sched, D_min)
        """
        if self.precomputed_gate_out_min is not None:
            return int(self.precomputed_gate_out_min)

        a_pred = self.predicted_arrival_min
        d_min = a_pred + self.min_turnaround_min

        if self.is_paired or (
            self.scheduled_departure_min is not None
            and self.scheduled_departure_min != self.scheduled_arrival_min + self.default_dwell_min
            and self.scheduled_departure_min > self.scheduled_arrival_min
        ):
            d_sched = self.scheduled_departure_min
        else:
            d_sched = self.scheduled_arrival_min + self.default_dwell_min

        return int(max(d_sched, d_min))

    @property
    def gate_release_min(self) -> int:
        """Gate release time including separation buffer."""
        return int(self.simulated_departure_min + self.buffer_min)

    @property
    def time_window(self) -> FlightTimeWindow:
        """Exact occupancy window [predicted_arrival, gate_release)."""
        return FlightTimeWindow(
            start_min=int(self.predicted_arrival_min),
            end_min=int(self.gate_release_min),
            buffer_min=int(self.buffer_min),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "flight_index": int(self.flight_index),
            "carrier": self.carrier,
            "flight_number": self.flight_number,
            "scheduled_arrival_min": int(self.scheduled_arrival_min),
            "scheduled_departure_min": int(self.scheduled_departure_min),
            "predicted_arrival_min": int(self.predicted_arrival_min),
            "aircraft_type": self.aircraft_type,
            "nominal_gate_id": self.nominal_gate_id,
            "min_turnaround_min": int(self.min_turnaround_min),
            "default_dwell_min": int(self.default_dwell_min),
            "buffer_min": int(self.buffer_min),
            "is_paired": bool(self.is_paired),
            "precomputed_gate_out_min": int(self.precomputed_gate_out_min) if self.precomputed_gate_out_min is not None else None,
            "occupancy_start_min": int(self.occupancy_start_min),
            "occupancy_end_min": int(self.occupancy_end_min),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Flight:
        return cls(
            flight_id=str(data["flight_id"]),
            flight_index=int(data["flight_index"]),
            carrier=str(data["carrier"]),
            flight_number=str(data["flight_number"]),
            scheduled_arrival_min=int(data["scheduled_arrival_min"]),
            scheduled_departure_min=int(data["scheduled_departure_min"]),
            predicted_arrival_min=int(data["predicted_arrival_min"]),
            aircraft_type=data.get("aircraft_type"),
            nominal_gate_id=data.get("nominal_gate_id"),
            min_turnaround_min=int(data.get("min_turnaround_min", 45)),
            default_dwell_min=int(data.get("default_dwell_min", 60)),
            buffer_min=int(data.get("buffer_min", 15)),
            is_paired=bool(data.get("is_paired", False)),
            precomputed_gate_out_min=int(data["precomputed_gate_out_min"]) if data.get("precomputed_gate_out_min") is not None else None,
        )


@dataclass(frozen=True)
class GateAssignment:
    """Resulting assignment of a flight to a gate with explicit operational state."""

    flight_id: str
    gate_id: str
    flight_index: int = 0
    gate_index: int = 0
    is_overflow: bool = False
    is_reassignment: bool = False
    occupancy_start_min: int = 0
    occupancy_end_min: int = 0
    assignment_state: str = GateAssignmentState.CONTACT_GATE.value

    def __post_init__(self) -> None:
        if not self.flight_id or not isinstance(self.flight_id, str) or not self.flight_id.strip():
            raise ValueError(f"GateAssignment.flight_id must be a non-empty string, got '{self.flight_id}'")

        for name, val in [("occupancy_start_min", self.occupancy_start_min), ("occupancy_end_min", self.occupancy_end_min)]:
            if val is None or not math.isfinite(val):
                raise ValueError(f"GateAssignment.{name} must be a finite numeric value, got {val}")

        # Resolve assignment_state if passed as Enum or string
        if isinstance(self.assignment_state, GateAssignmentState):
            state_val = self.assignment_state.value
        else:
            state_val = str(self.assignment_state)
        object.__setattr__(self, "assignment_state", state_val)

        if state_val not in tuple(s.value for s in GateAssignmentState):
            raise ValueError(f"Invalid assignment_state '{state_val}'")

        if state_val != GateAssignmentState.UNASSIGNED.value:
            if not self.gate_id or not isinstance(self.gate_id, str) or not self.gate_id.strip():
                raise ValueError(f"GateAssignment.gate_id must be a non-empty string, got '{self.gate_id}'")
            if self.occupancy_end_min <= self.occupancy_start_min:
                raise ValueError(
                    f"occupancy_end_min ({self.occupancy_end_min}) must be strictly greater than "
                    f"occupancy_start_min ({self.occupancy_start_min})"
                )

        # Synchronize is_overflow and assignment_state
        if self.is_overflow and state_val == GateAssignmentState.CONTACT_GATE.value:
            object.__setattr__(self, "assignment_state", GateAssignmentState.REMOTE_STAND.value)
        elif not self.is_overflow and state_val == GateAssignmentState.REMOTE_STAND.value:
            object.__setattr__(self, "is_overflow", True)
        elif state_val == GateAssignmentState.UNASSIGNED.value:
            object.__setattr__(self, "is_overflow", True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "gate_id": self.gate_id,
            "flight_index": int(self.flight_index),
            "gate_index": int(self.gate_index),
            "is_overflow": bool(self.is_overflow),
            "is_reassignment": bool(self.is_reassignment),
            "occupancy_start_min": int(self.occupancy_start_min),
            "occupancy_end_min": int(self.occupancy_end_min),
            "assignment_state": self.assignment_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GateAssignment:
        return cls(
            flight_id=str(data["flight_id"]),
            gate_id=str(data["gate_id"]),
            flight_index=int(data["flight_index"]),
            gate_index=int(data["gate_index"]),
            is_overflow=bool(data["is_overflow"]),
            is_reassignment=bool(data["is_reassignment"]),
            occupancy_start_min=int(data["occupancy_start_min"]),
            occupancy_end_min=int(data["occupancy_end_min"]),
            assignment_state=str(data.get("assignment_state", GateAssignmentState.CONTACT_GATE.value)),
        )


@dataclass(frozen=True)
class ConstraintDiagnostic:
    """Independent audit diagnostics for hard constraint verification."""

    all_flights_assigned: bool
    no_contact_gate_conflicts: bool
    gate_availability_satisfied: bool
    gate_compatibility_satisfied: bool
    turnaround_valid: bool
    conflict_count: int  # Total planned overlaps (contact + finite remote)
    conflict_pairs: list[dict[str, Any]]
    incompatibility_violations: list[dict[str, Any]]
    availability_violations: list[dict[str, Any]]
    # R8 distinct state counts and hard violations
    contact_count: int = 0
    remote_count: int = 0
    unassigned_count: int = 0
    hard_constraint_violations_count: int = 0
    turnaround_violations: list[dict[str, Any]] = field(default_factory=list)
    buffer_violations: list[dict[str, Any]] = field(default_factory=list)
    realized_post_hoc_conflicts_count: int = 0
    realized_conflict_details: list[dict[str, Any]] = field(default_factory=list)
    # P01 standard diagnostics
    unknown_gate_violations: list[dict[str, Any]] = field(default_factory=list)
    orphan_flight_violations: list[dict[str, Any]] = field(default_factory=list)
    timeline_mismatch_violations: list[dict[str, Any]] = field(default_factory=list)
    # P02 capacity correctness diagnostics
    duplicate_gate_violations: list[dict[str, Any]] = field(default_factory=list)
    planned_contact_violations: int = 0
    planned_remote_violations: int = 0
    realized_contact_violations: int = 0
    realized_remote_violations: int = 0
    max_concurrent_remote_usage: int = 0
    resource_capacity_policy: str = "FINITE_ENFORCED"

    @property
    def is_valid(self) -> bool:
        """True if and only if all hard constraints are strictly satisfied."""
        return (
            self.all_flights_assigned
            and self.no_contact_gate_conflicts
            and (self.planned_remote_violations == 0)
            and self.gate_availability_satisfied
            and self.gate_compatibility_satisfied
            and self.turnaround_valid
            and (self.unassigned_count == 0)
            and (self.hard_constraint_violations_count == 0)
            and len(self.unknown_gate_violations) == 0
            and len(self.orphan_flight_violations) == 0
            and len(self.timeline_mismatch_violations) == 0
            and len(self.duplicate_gate_violations) == 0
        )

    @property
    def orphan_flight_count(self) -> int:
        return len(self.orphan_flight_violations)

    @property
    def unknown_gate_count(self) -> int:
        return len(self.unknown_gate_violations)

    @property
    def timeline_mismatch_count(self) -> int:
        return len(self.timeline_mismatch_violations)

    @property
    def violation_details(self) -> list[str]:
        """Human-readable descriptions of all active violations."""
        details: list[str] = []
        for pair in self.conflict_pairs:
            res_t = pair.get("resource_type", "gate")
            if "flight_1" in pair:
                details.append(f"{res_t} overlap on {pair.get('gate_id')}: {pair.get('flight_1')} and {pair.get('flight_2')}")
            else:
                details.append(f"{res_t} capacity exceeded on {pair.get('gate_id')} at t={pair.get('time_min')}: excess={pair.get('excess')}")
        for incomp in self.incompatibility_violations:
            details.append(f"Incompatibility on {incomp.get('gate_id')} for {incomp.get('flight_id')}: {incomp.get('reason')}")
        for avail in self.availability_violations:
            details.append(f"Availability violation on {avail.get('gate_id')} for {avail.get('flight_id')}")
        for unk in self.unknown_gate_violations:
            details.append(f"Unknown gate violation: {unk.get('flight_id')} -> {unk.get('gate_id')}")
        for orp in self.orphan_flight_violations:
            details.append(f"Orphan flight violation: {orp.get('flight_id')}")
        for mis in self.timeline_mismatch_violations:
            details.append(f"Timeline mismatch for {mis.get('flight_id')}")
        for turn in self.turnaround_violations:
            details.append(f"Turnaround violation for {turn.get('flight_id')}")
        for buf in self.buffer_violations:
            details.append(f"Buffer violation on {buf.get('gate_id')}: {buf.get('flight_1')} and {buf.get('flight_2')}")
        return details

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "feasible": self.is_valid,
            "all_flights_assigned": self.all_flights_assigned,
            "no_contact_gate_conflicts": self.no_contact_gate_conflicts,
            "gate_availability_satisfied": self.gate_availability_satisfied,
            "gate_compatibility_satisfied": self.gate_compatibility_satisfied,
            "turnaround_valid": self.turnaround_valid,
            "contact_count": self.contact_count,
            "remote_count": self.remote_count,
            "unassigned_count": self.unassigned_count,
            "hard_constraint_violations_count": self.hard_constraint_violations_count,
            "conflict_count": self.conflict_count,
            "conflict_pairs": self.conflict_pairs,
            "incompatibility_violations": self.incompatibility_violations,
            "availability_violations": self.availability_violations,
            "turnaround_violations": self.turnaround_violations,
            "buffer_violations": self.buffer_violations,
            "unknown_gate_violations": self.unknown_gate_violations,
            "orphan_flight_violations": self.orphan_flight_violations,
            "timeline_mismatch_violations": self.timeline_mismatch_violations,
            "duplicate_gate_violations": self.duplicate_gate_violations,
            "realized_post_hoc_conflicts_count": self.realized_post_hoc_conflicts_count,
            "planned_contact_violations": self.planned_contact_violations,
            "planned_remote_violations": self.planned_remote_violations,
            "realized_contact_violations": self.realized_contact_violations,
            "realized_remote_violations": self.realized_remote_violations,
            "max_concurrent_remote_usage": self.max_concurrent_remote_usage,
            "resource_capacity_policy": self.resource_capacity_policy,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConstraintDiagnostic:
        return cls(
            all_flights_assigned=bool(data["all_flights_assigned"]),
            no_contact_gate_conflicts=bool(data["no_contact_gate_conflicts"]),
            gate_availability_satisfied=bool(data["gate_availability_satisfied"]),
            gate_compatibility_satisfied=bool(data["gate_compatibility_satisfied"]),
            turnaround_valid=bool(data["turnaround_valid"]),
            conflict_count=int(data.get("conflict_count", 0)),
            conflict_pairs=list(data.get("conflict_pairs", [])),
            incompatibility_violations=list(data.get("incompatibility_violations", [])),
            availability_violations=list(data.get("availability_violations", [])),
            contact_count=int(data.get("contact_count", 0)),
            remote_count=int(data.get("remote_count", 0)),
            unassigned_count=int(data.get("unassigned_count", 0)),
            hard_constraint_violations_count=int(data.get("hard_constraint_violations_count", 0)),
            turnaround_violations=list(data.get("turnaround_violations", [])),
            buffer_violations=list(data.get("buffer_violations", [])),
            unknown_gate_violations=list(data.get("unknown_gate_violations", [])),
            orphan_flight_violations=list(data.get("orphan_flight_violations", [])),
            timeline_mismatch_violations=list(data.get("timeline_mismatch_violations", [])),
            duplicate_gate_violations=list(data.get("duplicate_gate_violations", [])),
            realized_post_hoc_conflicts_count=int(data.get("realized_post_hoc_conflicts_count", 0)),
            realized_conflict_details=list(data.get("realized_conflict_details", [])),
            planned_contact_violations=int(data.get("planned_contact_violations", 0)),
            planned_remote_violations=int(data.get("planned_remote_violations", 0)),
            realized_contact_violations=int(data.get("realized_contact_violations", 0)),
            realized_remote_violations=int(data.get("realized_remote_violations", 0)),
            max_concurrent_remote_usage=int(data.get("max_concurrent_remote_usage", 0)),
            resource_capacity_policy=str(data.get("resource_capacity_policy", "FINITE_ENFORCED")),
        )


@dataclass(frozen=True)
class ObjectiveBreakdown:
    """Decomposed soft objective cost components with explicit classification."""

    total_cost: float
    reassignment_cost: float
    overflow_cost: float
    delay_cost: float
    conflict_cost: float
    risk_cost: float
    weights: dict[str, float]
    objective_version: str = "v1"

    def __post_init__(self) -> None:
        if math.isfinite(self.total_cost):
            expected = self.decision_cost + self.reporting_cost
            if abs(self.total_cost - expected) > 1e-4:
                raise ValueError(
                    f"ObjectiveBreakdown total_cost ({self.total_cost}) must equal "
                    f"decision_cost ({self.decision_cost}) + reporting_cost ({self.reporting_cost}) = {expected}"
                )

    @property
    def remote_cost(self) -> float:
        """Alias for overflow_cost representing remote apron/stand usage."""
        return float(self.overflow_cost)

    @property
    def exogenous_delay_cost(self) -> float:
        """Alias for delay_cost representing exogenous flight arrival delay penalty."""
        return float(self.delay_cost)

    @property
    def exogenous_risk_cost(self) -> float:
        """Alias for risk_cost representing exogenous turnaround slack risk penalty."""
        return float(self.risk_cost)

    @property
    def decision_cost(self) -> float:
        """Cost components that strictly depend on gate assignment decision variables."""
        return float(self.reassignment_cost + self.overflow_cost + self.conflict_cost)

    @property
    def reporting_cost(self) -> float:
        """Cost components that are exogenous flight-level constants with respect to gate decisions."""
        return float(self.delay_cost + self.risk_cost)

    @property
    def total_reported_cost(self) -> float:
        """Full reported cost: decision_cost + reporting_cost."""
        return float(self.total_cost)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_version": str(self.objective_version),
            "total_cost": float(self.total_cost),
            "total_reported_cost": float(self.total_cost),
            "decision_cost": float(self.decision_cost),
            "reporting_cost": float(self.reporting_cost),
            "reassignment_cost": float(self.reassignment_cost),
            "overflow_cost": float(self.overflow_cost),
            "remote_cost": float(self.overflow_cost),
            "delay_cost": float(self.delay_cost),
            "exogenous_delay_cost": float(self.delay_cost),
            "conflict_cost": float(self.conflict_cost),
            "risk_cost": float(self.risk_cost),
            "exogenous_risk_cost": float(self.risk_cost),
            "weights": {
                k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                for k, v in self.weights.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObjectiveBreakdown:
        return cls(
            total_cost=float(data["total_cost"]),
            reassignment_cost=float(data["reassignment_cost"]),
            overflow_cost=float(data.get("overflow_cost", data.get("remote_cost", 0.0))),
            delay_cost=float(data.get("delay_cost", data.get("exogenous_delay_cost", 0.0))),
            conflict_cost=float(data["conflict_cost"]),
            risk_cost=float(data.get("risk_cost", data.get("exogenous_risk_cost", 0.0))),
            weights={
                k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                for k, v in data.get("weights", {}).items()
            },
            objective_version=str(data.get("objective_version", "v1")),
        )


@dataclass(frozen=True)
class OptimizationResult:
    """Comprehensive outcome produced by gate assignment solvers, verified independently."""

    status: str  # "OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN", "TIMEOUT_NO_SOLUTION"
    objective_value: float
    objective_breakdown: ObjectiveBreakdown
    feasible: bool
    runtime_ms: float
    optimality_gap: float | None
    assignments: dict[str, GateAssignment]
    constraint_diagnostics: ConstraintDiagnostic
    solver_configuration: dict[str, Any]
    best_bound: float | None = None
    # P01 Standardized contract fields
    optimality_proven: bool = False
    raw_solver_status: str | None = None
    normalized_status: str | None = None
    termination_reason: str | None = None

    @property
    def ranking_cost(self) -> float:
        """Effective objective value for ranking candidate solutions.

        Guarantees that an infeasible solution is assigned infinite cost,
        preventing it from being ranked ahead of any feasible solution.
        """
        if not self.feasible:
            return float("inf")
        return float(self.objective_value)

    @property
    def ranking_key(self) -> tuple[int, float]:
        """Tuple key for sorting solutions: (0 if feasible else 1, objective_value)."""
        return (0 if self.feasible else 1, self.objective_value if self.feasible else float("inf"))

    def __post_init__(self) -> None:
        if self.raw_solver_status is None:
            object.__setattr__(self, "raw_solver_status", str(self.status))

        # Check solver heuristic family
        solver_name = str(self.solver_configuration.get("solver_name", "")).lower()
        is_heuristic = any(h in solver_name for h in ["anneal", "greedy", "heuristic"])

        # Auto-infer optimality proof if not explicitly set
        if not self.optimality_proven:
            if (
                not is_heuristic
                and self.status == "OPTIMAL"
                and self.feasible
                and self.optimality_gap == 0.0
            ):
                object.__setattr__(self, "optimality_proven", True)

        # Invariant: optimality_proven cannot be True if infeasible
        if not self.feasible and self.optimality_proven:
            raise ValueError("optimality_proven cannot be True for an infeasible result.")

        # Invariant: heuristic solvers can NEVER claim optimality_proven == True or provide optimality_gap
        if is_heuristic:
            object.__setattr__(self, "optimality_proven", False)
            object.__setattr__(self, "optimality_gap", None)

        # Gap must be None if not finite
        if self.optimality_gap is not None and not math.isfinite(self.optimality_gap):
            object.__setattr__(self, "optimality_gap", None)

        # Determine normalized_status
        if self.normalized_status is None:
            if self.status == "OPTIMAL":
                if self.optimality_proven and self.feasible:
                    norm = SolverStatus.OPTIMAL.value
                else:
                    norm = SolverStatus.FEASIBLE.value if self.feasible else SolverStatus.UNKNOWN.value
            elif self.status in ("FEASIBLE", SolverStatus.FEASIBLE.value):
                norm = SolverStatus.FEASIBLE.value if self.feasible else SolverStatus.UNKNOWN.value
            elif self.status in ("INFEASIBLE", SolverStatus.INFEASIBLE.value):
                norm = SolverStatus.INFEASIBLE.value
            elif self.status in ("MODEL_INVALID", SolverStatus.MODEL_INVALID.value):
                norm = SolverStatus.MODEL_INVALID.value
            elif self.status in ("TIMEOUT_NO_SOLUTION", SolverStatus.TIMEOUT_NO_SOLUTION.value):
                norm = SolverStatus.TIMEOUT_NO_SOLUTION.value
            elif self.status in ("UNKNOWN", SolverStatus.UNKNOWN.value):
                norm = SolverStatus.FEASIBLE.value if self.feasible else SolverStatus.UNKNOWN.value
            else:
                norm = SolverStatus.FEASIBLE.value if self.feasible else SolverStatus.UNKNOWN.value
            object.__setattr__(self, "normalized_status", norm)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "normalized_status": self.normalized_status,
            "raw_solver_status": self.raw_solver_status,
            "optimality_proven": bool(self.optimality_proven),
            "termination_reason": self.termination_reason,
            "objective_value": float(self.objective_value),
            "feasible": self.feasible,
            "runtime_ms": float(self.runtime_ms),
            "optimality_gap": float(self.optimality_gap) if self.optimality_gap is not None else None,
            "best_bound": float(self.best_bound) if self.best_bound is not None else None,
            "assignment_count": len(self.assignments),
            "assignments": {k: v.to_dict() for k, v in self.assignments.items()},
            "contact_count": self.constraint_diagnostics.contact_count,
            "remote_count": self.constraint_diagnostics.remote_count,
            "unassigned_count": self.constraint_diagnostics.unassigned_count,
            "hard_constraint_violations": self.constraint_diagnostics.hard_constraint_violations_count,
            "objective_breakdown": self.objective_breakdown.to_dict(),
            "constraint_diagnostics": self.constraint_diagnostics.to_dict(),
            "solver_configuration": self.solver_configuration,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OptimizationResult:
        breakdown = ObjectiveBreakdown.from_dict(data["objective_breakdown"])
        diagnostics = ConstraintDiagnostic.from_dict(data["constraint_diagnostics"])
        assignments = {k: GateAssignment.from_dict(v) for k, v in data.get("assignments", {}).items()}
        gap = float(data["optimality_gap"]) if data.get("optimality_gap") is not None else None
        bb = float(data["best_bound"]) if data.get("best_bound") is not None else None
        return cls(
            status=str(data["status"]),
            objective_value=float(data["objective_value"]),
            objective_breakdown=breakdown,
            feasible=bool(data["feasible"]),
            runtime_ms=float(data["runtime_ms"]),
            optimality_gap=gap,
            assignments=assignments,
            constraint_diagnostics=diagnostics,
            solver_configuration=dict(data.get("solver_configuration", {})),
            best_bound=bb,
            optimality_proven=bool(data.get("optimality_proven", False)),
            raw_solver_status=data.get("raw_solver_status"),
            normalized_status=data.get("normalized_status"),
            termination_reason=data.get("termination_reason"),
        )


def validate_flights_collection(flights: Sequence[Flight]) -> bool:
    """Validate that a flight sequence satisfies scenario uniqueness contracts."""
    seen_ids: set[str] = set()
    seen_indices: set[int] = set()
    for f in flights:
        if f.flight_id in seen_ids:
            raise ValueError(f"Duplicate flight_id detected in flights collection: '{f.flight_id}'")
        seen_ids.add(f.flight_id)
        if f.flight_index in seen_indices:
            raise ValueError(f"Duplicate flight_index detected in flights collection: {f.flight_index}")
        seen_indices.add(f.flight_index)
    return True


def validate_gates_collection(gates: Sequence[Gate]) -> bool:
    """Validate that a gate sequence satisfies inventory uniqueness contracts."""
    seen_ids: set[str] = set()
    for g in gates:
        if g.gate_id in seen_ids:
            raise ValueError(f"Duplicate gate_id detected in gates inventory: '{g.gate_id}'")
        seen_ids.add(g.gate_id)
    return True


def validate_assignments_contract(
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    assignments: Mapping[str, GateAssignment],
) -> list[str]:
    """Validate integrity of assignment mapping against flights and gates."""
    errors: list[str] = []
    flight_map = {f.flight_id: f for f in flights}
    gate_map = {g.gate_id: g for g in gates}

    # 0. Duplicate gate IDs
    seen_gids: set[str] = set()
    for g in gates:
        if g.gate_id in seen_gids:
            errors.append(f"DUPLICATE_GATE: Duplicate gate_id '{g.gate_id}' in gates inventory")
        seen_gids.add(g.gate_id)

    # 1. Orphan assignments
    for f_id in assignments:
        if f_id not in flight_map:
            errors.append(f"ORPHAN_ASSIGNMENT: Assignment references unknown flight_id '{f_id}'")

    # 2. Gate existence and timeline matching
    for f_id, assign in assignments.items():
        if assign.assignment_state == GateAssignmentState.UNASSIGNED.value:
            continue

        if assign.gate_id not in gate_map:
            errors.append(f"UNKNOWN_GATE: Flight '{f_id}' assigned to unknown gate '{assign.gate_id}'")
            continue

        gate = gate_map[assign.gate_id]
        fl = flight_map.get(f_id)

        # State matching
        if gate.is_remote_stand and assign.assignment_state == GateAssignmentState.CONTACT_GATE.value:
            errors.append(f"STATE_MISMATCH: Remote gate '{gate.gate_id}' has CONTACT_GATE assignment state")
        elif not gate.is_remote_stand and assign.assignment_state == GateAssignmentState.REMOTE_STAND.value:
            errors.append(f"STATE_MISMATCH: Contact gate '{gate.gate_id}' has REMOTE_STAND assignment state")

        # Timeline matching
        if fl is not None:
            if assign.occupancy_start_min != fl.time_window.start_min or assign.occupancy_end_min != fl.time_window.end_min:
                errors.append(
                    f"TIMELINE_MISMATCH: Flight '{f_id}' assignment window "
                    f"[{assign.occupancy_start_min}, {assign.occupancy_end_min}) does not match flight window "
                    f"[{fl.time_window.start_min}, {fl.time_window.end_min})"
                )

    return errors


def verify_hard_constraints_independently(
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    assignments: Mapping[str, GateAssignment],
    *,
    realized_flights: Sequence[Flight] | None = None,
) -> ConstraintDiagnostic:
    """Execute rigorous independent hard-constraint verification outside the solver.

    Verifies:
    1. Every flight gets exactly one valid assignment state:
       - CONTACT_GATE
       - REMOTE_STAND
       - UNASSIGNED
       (distinct, not merged).
    2. Overlapping occupancy intervals cannot use the same contact gate.
    3. Gate operational availability during occupancy window.
    4. Gate carrier and aircraft type compatibility.
    5. Turnaround duration validity (>= min_turnaround_min).
    6. Separation buffer enforcement between consecutive flights.
    7. Evaluates post-hoc realized conflicts if realized_flights are provided.
    8. Flags orphan assignments, unknown gates, duplicate gates, and timeline mismatches.
    """
    flight_map = {f.flight_id: f for f in flights}
    gate_map: dict[str, Gate] = {}
    duplicate_gate_violations: list[dict[str, Any]] = []
    for g in gates:
        if g.gate_id in gate_map:
            duplicate_gate_violations.append({"gate_id": g.gate_id, "gate_index": g.gate_index})
        else:
            gate_map[g.gate_id] = g

    # 1. State Classification: Contact vs Remote vs Unassigned
    n_contact = 0
    n_remote = 0
    n_unassigned = 0

    for f in flights:
        assign = assignments.get(f.flight_id)
        if assign is None:
            n_unassigned += 1
        else:
            g = gate_map.get(assign.gate_id)
            if (g is not None and g.is_overflow) or assign.is_overflow:
                n_remote += 1
            else:
                n_contact += 1

    all_assigned = (n_unassigned == 0) and (len(assignments) == len(flights))

    # Group assignments by gate
    gate_to_flights: dict[str, list[Flight]] = {g.gate_id: [] for g in gates}
    for f_id, assign in assignments.items():
        if assign.gate_id in gate_to_flights and f_id in flight_map:
            gate_to_flights[assign.gate_id].append(flight_map[f_id])

    # 2. Non-overlapping occupancy and capacity enforcement
    conflict_pairs: list[dict[str, Any]] = []
    buffer_violations: list[dict[str, Any]] = []
    planned_contact_violations = 0
    planned_remote_violations = 0

    remote_events: list[tuple[int, int]] = []

    for g in gates:
        assigned_list = gate_to_flights.get(g.gate_id, [])
        n_assigned = len(assigned_list)
        if n_assigned == 0:
            continue

        is_unbounded = (g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON)
        is_contact = (g.resource_type == GateResourceType.CONTACT_GATE)
        is_finite_remote = (g.resource_type == GateResourceType.FINITE_REMOTE_STAND)

        if is_finite_remote or is_unbounded:
            for fl in assigned_list:
                remote_events.append((fl.time_window.start_min, 1))
                remote_events.append((fl.time_window.end_min, -1))

        if is_unbounded:
            # Unbounded apron allows concurrent occupancy without conflict
            continue

        cap = int(g.capacity) if (g.capacity is not None and math.isfinite(g.capacity)) else 1

        if cap == 1:
            sorted_fl = sorted(assigned_list, key=lambda f: f.time_window.start_min)
            for i in range(n_assigned - 1):
                f1 = sorted_fl[i]
                w1 = f1.time_window
                for j in range(i + 1, n_assigned):
                    f2 = sorted_fl[j]
                    w2 = f2.time_window
                    if w1.overlaps(w2):
                        overlap = w1.overlap_duration(w2)
                        res_str = g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type)
                        conflict_pairs.append(
                            {
                                "gate_id": g.gate_id,
                                "resource_type": res_str,
                                "flight_1": f1.flight_id,
                                "flight_2": f2.flight_id,
                                "overlap_min": overlap,
                                "window_1": (w1.start_min, w1.end_min),
                                "window_2": (w2.start_min, w2.end_min),
                            }
                        )
                        if is_contact:
                            planned_contact_violations += 1
                        else:
                            planned_remote_violations += 1
                    elif w2.start_min < f1.gate_release_min:
                        res_str = g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type)
                        buffer_violations.append(
                            {
                                "gate_id": g.gate_id,
                                "resource_type": res_str,
                                "flight_1": f1.flight_id,
                                "flight_2": f2.flight_id,
                                "buffer_deficit_min": f1.gate_release_min - w2.start_min,
                            }
                        )
        else:
            # Pooled capacity K > 1
            events: list[tuple[int, int, str]] = []
            for fl in assigned_list:
                events.append((fl.time_window.start_min, 1, fl.flight_id))
                events.append((fl.time_window.end_min, -1, fl.flight_id))
            events.sort(key=lambda ev: (ev[0], ev[1]))
            current_occupancy = 0
            active_flights: set[str] = set()
            res_str = g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type)
            for t, delta, f_id in events:
                if delta == 1:
                    current_occupancy += 1
                    active_flights.add(f_id)
                    if current_occupancy > cap:
                        excess = current_occupancy - cap
                        conflict_pairs.append(
                            {
                                "gate_id": g.gate_id,
                                "resource_type": res_str,
                                "time_min": t,
                                "concurrent_occupancy": current_occupancy,
                                "capacity": cap,
                                "active_flights": list(active_flights),
                                "excess": excess,
                            }
                        )
                        planned_remote_violations += excess
                else:
                    current_occupancy -= 1
                    active_flights.discard(f_id)

    max_concurrent_remote_usage = 0
    if remote_events:
        remote_events.sort(key=lambda ev: (ev[0], ev[1]))
        curr_rem = 0
        for _, delta in remote_events:
            curr_rem += delta
            if curr_rem > max_concurrent_remote_usage:
                max_concurrent_remote_usage = curr_rem

    no_contact_conflicts = (planned_contact_violations == 0)

    # 3. Gate availability check
    availability_violations: list[dict[str, Any]] = []
    for f_id, assign in assignments.items():
        g = gate_map.get(assign.gate_id)
        f = flight_map.get(f_id)
        if g is not None and f is not None:
            if not g.is_available_during(f.time_window):
                availability_violations.append(
                    {
                        "flight_id": f_id,
                        "gate_id": g.gate_id,
                        "window": (f.time_window.start_min, f.time_window.end_min),
                    }
                )

    availability_ok = len(availability_violations) == 0

    # 4. Gate compatibility check
    incompatibility_violations: list[dict[str, Any]] = []
    for f_id, assign in assignments.items():
        g = gate_map.get(assign.gate_id)
        f = flight_map.get(f_id)
        if g is not None and f is not None:
            if not g.is_compatible_carrier(f.carrier):
                incompatibility_violations.append(
                    {
                        "flight_id": f_id,
                        "gate_id": g.gate_id,
                        "carrier": f.carrier,
                        "reason": "carrier_incompatible",
                    }
                )
            if not g.is_compatible_aircraft(f.aircraft_type):
                incompatibility_violations.append(
                    {
                        "flight_id": f_id,
                        "gate_id": g.gate_id,
                        "aircraft_type": f.aircraft_type,
                        "reason": "aircraft_type_incompatible",
                    }
                )

    compatibility_ok = len(incompatibility_violations) == 0

    # 5. Turnaround validity
    turnaround_violations: list[dict[str, Any]] = []
    for f in flights:
        stay = f.simulated_departure_min - f.predicted_arrival_min
        if stay < f.min_turnaround_min:
            turnaround_violations.append(
                {
                    "flight_id": f.flight_id,
                    "stay_min": stay,
                    "min_required_min": f.min_turnaround_min,
                }
            )

    turnaround_valid = len(turnaround_violations) == 0

    # 6. Integrity checks (Unknown gates, orphan flights, timeline mismatches)
    unknown_gate_violations: list[dict[str, Any]] = []
    orphan_flight_violations: list[dict[str, Any]] = []
    timeline_mismatch_violations: list[dict[str, Any]] = []

    for f_id, assign in assignments.items():
        if f_id not in flight_map:
            orphan_flight_violations.append({"flight_id": f_id, "gate_id": assign.gate_id})
            continue

        f = flight_map[f_id]
        if assign.assignment_state != GateAssignmentState.UNASSIGNED.value:
            if assign.gate_id not in gate_map:
                unknown_gate_violations.append({"flight_id": f_id, "gate_id": assign.gate_id})
            else:
                if (
                    assign.occupancy_start_min != f.time_window.start_min
                    or assign.occupancy_end_min != f.time_window.end_min
                ):
                    timeline_mismatch_violations.append(
                        {
                            "flight_id": f_id,
                            "assignment_window": (assign.occupancy_start_min, assign.occupancy_end_min),
                            "flight_window": (f.time_window.start_min, f.time_window.end_min),
                        }
                    )

    # 7. Post-hoc realized conflicts (if realized_flights provided)
    realized_conflicts: list[dict[str, Any]] = []
    realized_contact_violations = 0
    realized_remote_violations = 0
    if realized_flights is not None:
        real_map = {f.flight_id: f for f in realized_flights}
        real_gate_to_flights: dict[str, list[Flight]] = {g.gate_id: [] for g in gates}
        for f_id, assign in assignments.items():
            if assign.gate_id in real_gate_to_flights and f_id in real_map:
                real_gate_to_flights[assign.gate_id].append(real_map[f_id])

        for g in gates:
            if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON:
                continue
            r_assigned = real_gate_to_flights[g.gate_id]
            if len(r_assigned) <= 1:
                continue
            cap = int(g.capacity) if (g.capacity is not None and math.isfinite(g.capacity)) else 1
            res_str = g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type)
            if cap == 1:
                r_sorted = sorted(r_assigned, key=lambda f: f.time_window.start_min)
                for i in range(len(r_sorted) - 1):
                    f1 = r_sorted[i]
                    for j in range(i + 1, len(r_sorted)):
                        f2 = r_sorted[j]
                        if f1.time_window.overlaps(f2.time_window):
                            realized_conflicts.append(
                                {
                                    "gate_id": g.gate_id,
                                    "resource_type": res_str,
                                    "flight_1": f1.flight_id,
                                    "flight_2": f2.flight_id,
                                    "overlap_min": f1.time_window.overlap_duration(f2.time_window),
                                }
                            )
                            if g.resource_type == GateResourceType.CONTACT_GATE:
                                realized_contact_violations += 1
                            else:
                                realized_remote_violations += 1
            else:
                r_events: list[tuple[int, int]] = []
                for fl in r_assigned:
                    r_events.append((fl.time_window.start_min, 1))
                    r_events.append((fl.time_window.end_min, -1))
                r_events.sort(key=lambda ev: (ev[0], ev[1]))
                curr_occ = 0
                for t, delta in r_events:
                    if delta == 1:
                        curr_occ += 1
                        if curr_occ > cap:
                            realized_conflicts.append({
                                "gate_id": g.gate_id,
                                "time_min": t,
                                "excess": curr_occ - cap,
                            })
                            realized_remote_violations += (curr_occ - cap)
                    else:
                        curr_occ -= 1

    total_hard_violations = (
        len(conflict_pairs)
        + len(incompatibility_violations)
        + len(availability_violations)
        + len(turnaround_violations)
        + len(unknown_gate_violations)
        + len(orphan_flight_violations)
        + len(timeline_mismatch_violations)
        + len(duplicate_gate_violations)
    )

    return ConstraintDiagnostic(
        all_flights_assigned=all_assigned,
        no_contact_gate_conflicts=no_contact_conflicts,
        gate_availability_satisfied=availability_ok,
        gate_compatibility_satisfied=compatibility_ok,
        turnaround_valid=turnaround_valid,
        conflict_count=len(conflict_pairs),
        conflict_pairs=conflict_pairs,
        incompatibility_violations=incompatibility_violations,
        availability_violations=availability_violations,
        contact_count=n_contact,
        remote_count=n_remote,
        unassigned_count=n_unassigned,
        hard_constraint_violations_count=total_hard_violations,
        turnaround_violations=turnaround_violations,
        buffer_violations=buffer_violations,
        unknown_gate_violations=unknown_gate_violations,
        orphan_flight_violations=orphan_flight_violations,
        timeline_mismatch_violations=timeline_mismatch_violations,
        duplicate_gate_violations=duplicate_gate_violations,
        realized_post_hoc_conflicts_count=len(realized_conflicts),
        realized_conflict_details=realized_conflicts,
        planned_contact_violations=planned_contact_violations,
        planned_remote_violations=planned_remote_violations,
        realized_contact_violations=realized_contact_violations,
        realized_remote_violations=realized_remote_violations,
        max_concurrent_remote_usage=max_concurrent_remote_usage,
    )
