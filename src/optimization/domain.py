"""Domain Objects and Typed Structures for Gate Assignment Optimization (V2 Repaired).

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. FlightTimeWindow: gate occupancy interval [start, end) and overlap detection.
2. Gate: contact gate or overflow apron with availability and compatibility rules.
3. Flight: operational flight record with timeline parameters (arrival, departure, turnaround, dwell).
4. GateAssignmentState: explicit enum {CONTACT_GATE, REMOTE_STAND, UNASSIGNED}.
5. GateAssignment: assigned flight-to-gate mapping with explicit state semantics.
6. ConstraintDiagnostic: independent verification of hard constraints outside the solver.
7. ObjectiveBreakdown: separated decision-dependent vs exogenous reporting cost components.
8. OptimizationResult: solver status, runtime, diagnostics, and assignments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np


class GateAssignmentState(str, Enum):
    """Explicit operational state of a flight's gate assignment."""
    CONTACT_GATE = "CONTACT_GATE"
    REMOTE_STAND = "REMOTE_STAND"
    UNASSIGNED = "UNASSIGNED"


@dataclass(frozen=True)
class FlightTimeWindow:
    """Gate occupancy interval [start_min, end_min) in minutes from start of day."""

    start_min: int
    end_min: int
    buffer_min: int = 0

    def __post_init__(self) -> None:
        if self.end_min < self.start_min:
            raise ValueError(
                f"end_min ({self.end_min}) must be >= start_min ({self.start_min})"
            )

    @property
    def duration_min(self) -> int:
        """Total duration of occupancy in minutes."""
        return self.end_min - self.start_min

    def overlaps(self, other: FlightTimeWindow) -> bool:
        """Determine if this interval overlaps with another interval [s, e).

        Two half-open intervals [s1, e1) and [s2, e2) overlap iff max(s1, s2) < min(e1, e2).
        """
        return max(self.start_min, other.start_min) < min(self.end_min, other.end_min)

    def overlap_duration(self, other: FlightTimeWindow) -> int:
        """Calculate overlap duration in minutes (0 if disjoint)."""
        overlap = min(self.end_min, other.end_min) - max(self.start_min, other.start_min)
        return max(0, overlap)


@dataclass(frozen=True)
class Gate:
    """Gate or parking stand entity."""

    gate_id: str
    gate_index: int
    is_overflow: bool = False
    allowed_carriers: frozenset[str] | None = None
    allowed_aircraft_types: frozenset[str] | None = None
    available_windows: tuple[tuple[int, int], ...] | None = None

    @property
    def is_remote_stand(self) -> bool:
        """True if gate is a remote overflow apron/stand rather than a physical contact terminal gate."""
        return self.is_overflow

    def is_compatible_carrier(self, carrier: str) -> bool:
        """Check if carrier is allowed at this gate."""
        if self.allowed_carriers is None:
            return True
        return carrier in self.allowed_carriers

    def is_compatible_aircraft(self, aircraft_type: str | None) -> bool:
        """Check if aircraft type is allowed at this gate."""
        if self.allowed_aircraft_types is None or aircraft_type is None:
            return True
        return aircraft_type in self.allowed_aircraft_types

    def is_available_during(self, window: FlightTimeWindow) -> bool:
        """Check if gate is operational and open during the required flight time window."""
        if self.available_windows is None:
            return True
        for w_start, w_end in self.available_windows:
            if w_start <= window.start_min and window.end_min <= w_end:
                return True
        return False


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

    @property
    def arrival_delay_min(self) -> int:
        """Signed arrival delay in minutes."""
        return self.predicted_arrival_min - self.scheduled_arrival_min

    @property
    def gate_in_min(self) -> int:
        """Gate-in time when aircraft enters the gate (alias to predicted_arrival_min)."""
        return self.predicted_arrival_min

    @property
    def gate_out_min(self) -> int:
        """Physical gate-out / pushback time (alias to simulated_departure_min)."""
        return self.simulated_departure_min

    @property
    def physical_dwell_min(self) -> int:
        """Physical turnaround / dwell duration at gate before separation buffer: gate_out - gate_in."""
        return max(0, self.simulated_departure_min - self.predicted_arrival_min)

    @property
    def scheduled_dwell_min(self) -> int:
        """Scheduled turnaround / dwell duration according to timetable: D_sched - A_sched."""
        return max(0, self.scheduled_departure_min - self.scheduled_arrival_min)

    @property
    def turnaround_slack_min(self) -> int:
        """Turnaround slack above minimum physical turnaround: physical_dwell - min_turnaround."""
        return self.physical_dwell_min - self.min_turnaround_min

    @property
    def simulated_departure_min(self) -> int:
        """Simulated departure time respecting minimum turnaround.

        Timeline semantics:
        1. D_min = A_pred + min_turnaround_min (physical turnaround requirement)
        2. D_sched = scheduled_departure_min if (paired or explicit departure) else A_sched + default_dwell_min
        3. D_pred = max(D_sched, D_min)
        """
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
        return self.simulated_departure_min + self.buffer_min

    @property
    def time_window(self) -> FlightTimeWindow:
        """Exact occupancy window [predicted_arrival, gate_release)."""
        return FlightTimeWindow(
            start_min=self.predicted_arrival_min,
            end_min=self.gate_release_min,
            buffer_min=self.buffer_min,
        )


@dataclass(frozen=True)
class GateAssignment:
    """Resulting assignment of a flight to a gate with explicit operational state."""

    flight_id: str
    gate_id: str
    flight_index: int
    gate_index: int
    is_overflow: bool
    is_reassignment: bool
    occupancy_start_min: int
    occupancy_end_min: int
    assignment_state: str = GateAssignmentState.CONTACT_GATE.value

    def __post_init__(self) -> None:
        if self.is_overflow and self.assignment_state == GateAssignmentState.CONTACT_GATE.value:
            object.__setattr__(self, "assignment_state", GateAssignmentState.REMOTE_STAND.value)


@dataclass(frozen=True)
class ConstraintDiagnostic:
    """Independent audit diagnostics for hard constraint verification."""

    all_flights_assigned: bool
    no_contact_gate_conflicts: bool
    gate_availability_satisfied: bool
    gate_compatibility_satisfied: bool
    turnaround_valid: bool
    conflict_count: int  # Planned contact gate overlaps
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

    @property
    def is_valid(self) -> bool:
        """True if and only if all hard constraints are strictly satisfied."""
        return (
            self.all_flights_assigned
            and self.no_contact_gate_conflicts
            and self.gate_availability_satisfied
            and self.gate_compatibility_satisfied
            and self.turnaround_valid
            and (self.unassigned_count == 0)
            and (self.hard_constraint_violations_count == 0)
        )

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
            "realized_post_hoc_conflicts_count": self.realized_post_hoc_conflicts_count,
        }


@dataclass(frozen=True)
class ObjectiveBreakdown:
    """Decomposed soft objective cost components with explicit classification.

    Classification:
    1. Decision-dependent terms (change when gate decisions x[f, g] or y[f] change):
       - reassignment_cost
       - overflow_cost
       - conflict_cost
    2. Constant reporting terms (exogenous flight schedule/delay context, invariant to gate decisions):
       - delay_cost
       - risk_cost
    """

    total_cost: float
    reassignment_cost: float
    overflow_cost: float
    delay_cost: float
    conflict_cost: float
    risk_cost: float
    weights: dict[str, float]

    @property
    def decision_cost(self) -> float:
        """Cost components that strictly depend on gate assignment decision variables."""
        return float(self.reassignment_cost + self.overflow_cost + self.conflict_cost)

    @property
    def reporting_cost(self) -> float:
        """Cost components that are exogenous flight-level constants with respect to gate decisions."""
        return float(self.delay_cost + self.risk_cost)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cost": float(self.total_cost),
            "decision_cost": float(self.decision_cost),
            "reporting_cost": float(self.reporting_cost),
            "reassignment_cost": float(self.reassignment_cost),
            "overflow_cost": float(self.overflow_cost),
            "delay_cost": float(self.delay_cost),
            "conflict_cost": float(self.conflict_cost),
            "risk_cost": float(self.risk_cost),
            "weights": {k: float(v) for k, v in self.weights.items()},
        }


@dataclass(frozen=True)
class OptimizationResult:
    """Comprehensive outcome produced by gate assignment solvers, verified independently."""

    status: str  # "OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"
    objective_value: float
    objective_breakdown: ObjectiveBreakdown
    feasible: bool
    runtime_ms: float
    optimality_gap: float | None
    assignments: dict[str, GateAssignment]
    constraint_diagnostics: ConstraintDiagnostic
    solver_configuration: dict[str, Any]
    best_bound: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "objective_value": float(self.objective_value),
            "feasible": self.feasible,
            "runtime_ms": float(self.runtime_ms),
            "optimality_gap": float(self.optimality_gap) if self.optimality_gap is not None else None,
            "best_bound": float(self.best_bound) if self.best_bound is not None else None,
            "assignment_count": len(self.assignments),
            "contact_count": self.constraint_diagnostics.contact_count,
            "remote_count": self.constraint_diagnostics.remote_count,
            "unassigned_count": self.constraint_diagnostics.unassigned_count,
            "hard_constraint_violations": self.constraint_diagnostics.hard_constraint_violations_count,
            "objective_breakdown": self.objective_breakdown.to_dict(),
            "constraint_diagnostics": self.constraint_diagnostics.to_dict(),
            "solver_configuration": self.solver_configuration,
        }


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
    """
    flight_map = {f.flight_id: f for f in flights}
    gate_map = {g.gate_id: g for g in gates}

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

    # 2. Non-overlapping occupancy check on contact gates
    conflict_pairs: list[dict[str, Any]] = []
    buffer_violations: list[dict[str, Any]] = []

    for g in gates:
        if g.is_overflow:
            continue  # Remote stand allows concurrent occupancy / bussing

        assigned_list = gate_to_flights[g.gate_id]
        n_assigned = len(assigned_list)
        if n_assigned <= 1:
            continue

        sorted_fl = sorted(assigned_list, key=lambda f: f.time_window.start_min)
        for i in range(n_assigned - 1):
            f1 = sorted_fl[i]
            w1 = f1.time_window
            for j in range(i + 1, n_assigned):
                f2 = sorted_fl[j]
                w2 = f2.time_window
                if w1.overlaps(w2):
                    overlap = w1.overlap_duration(w2)
                    conflict_pairs.append(
                        {
                            "gate_id": g.gate_id,
                            "flight_1": f1.flight_id,
                            "flight_2": f2.flight_id,
                            "overlap_min": overlap,
                            "window_1": (w1.start_min, w1.end_min),
                            "window_2": (w2.start_min, w2.end_min),
                        }
                    )
                elif w2.start_min < f1.gate_release_min:
                    # Buffer violation (no physical overlap, but separation buffer violated)
                    buffer_violations.append(
                        {
                            "gate_id": g.gate_id,
                            "flight_1": f1.flight_id,
                            "flight_2": f2.flight_id,
                            "buffer_deficit_min": f1.gate_release_min - w2.start_min,
                        }
                    )

    no_conflicts = len(conflict_pairs) == 0

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

    # 6. Post-hoc realized conflicts (if realized_flights provided)
    realized_conflicts: list[dict[str, Any]] = []
    if realized_flights is not None:
        real_map = {f.flight_id: f for f in realized_flights}
        real_gate_to_flights: dict[str, list[Flight]] = {g.gate_id: [] for g in gates}
        for f_id, assign in assignments.items():
            if assign.gate_id in real_gate_to_flights and f_id in real_map:
                real_gate_to_flights[assign.gate_id].append(real_map[f_id])

        for g in gates:
            if g.is_overflow:
                continue
            r_assigned = real_gate_to_flights[g.gate_id]
            if len(r_assigned) <= 1:
                continue
            r_sorted = sorted(r_assigned, key=lambda f: f.time_window.start_min)
            for i in range(len(r_sorted) - 1):
                f1 = r_sorted[i]
                for j in range(i + 1, len(r_sorted)):
                    f2 = r_sorted[j]
                    if f1.time_window.overlaps(f2.time_window):
                        realized_conflicts.append(
                            {
                                "gate_id": g.gate_id,
                                "flight_1": f1.flight_id,
                                "flight_2": f2.flight_id,
                                "overlap_min": f1.time_window.overlap_duration(f2.time_window),
                            }
                        )

    total_hard_violations = (
        len(conflict_pairs)
        + len(incompatibility_violations)
        + len(availability_violations)
        + len(turnaround_violations)
    )

    return ConstraintDiagnostic(
        all_flights_assigned=all_assigned,
        no_contact_gate_conflicts=no_conflicts,
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
        realized_post_hoc_conflicts_count=len(realized_conflicts),
        realized_conflict_details=realized_conflicts,
    )
