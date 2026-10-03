"""Simulated Annealing State Representation for Gate Assignment.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Explicit discrete assignment: flight -> gate.
- Maintains bidirectional lookup for fast neighborhood queries and overlap checks.
- Validates hard constraints to guarantee the state is strictly feasible.
- Never allows silent acceptance of an infeasible state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    verify_hard_constraints_independently,
)


@dataclass
class SAState:
    """State representation for Simulated Annealing: flight -> gate mapping.

    Attributes:
        assignments: Dict mapping flight_id to gate_id.
        flights: Sequence of all Flight domain entities.
        gates: Sequence of all Gate entities.
    """

    assignments: dict[str, str]
    flights: Sequence[Flight]
    gates: Sequence[Gate]

    def __post_init__(self) -> None:
        self.flight_map: dict[str, Flight] = {f.flight_id: f for f in self.flights}
        self.gate_map: dict[str, Gate] = {g.gate_id: g for g in self.gates}
        self.gate_to_flights: dict[str, list[Flight]] = {g.gate_id: [] for g in self.gates}
        for f_id, g_id in self.assignments.items():
            if g_id in self.gate_to_flights and f_id in self.flight_map:
                self.gate_to_flights[g_id].append(self.flight_map[f_id])

    def get_gate_id(self, flight_id: str) -> str:
        """Return gate ID assigned to a given flight."""
        return self.assignments[flight_id]

    def copy(self) -> SAState:
        """Create a deep copy of the state for exploratory neighborhood search."""
        new_assignments = dict(self.assignments)
        new_state = SAState(
            assignments=new_assignments,
            flights=self.flights,
            gates=self.gates,
        )
        return new_state

    def assign(self, flight_id: str, new_gate_id: str) -> None:
        """Update assignment for a single flight, updating lookup indexes."""
        old_gate_id = self.assignments.get(flight_id)
        if old_gate_id == new_gate_id:
            return

        flight = self.flight_map[flight_id]
        if old_gate_id is not None and old_gate_id in self.gate_to_flights:
            if flight in self.gate_to_flights[old_gate_id]:
                self.gate_to_flights[old_gate_id].remove(flight)

        self.assignments[flight_id] = new_gate_id
        if new_gate_id in self.gate_to_flights:
            self.gate_to_flights[new_gate_id].append(flight)

    def swap(self, flight_id_1: str, flight_id_2: str) -> None:
        """Swap gates assigned to two distinct flights."""
        g1 = self.assignments[flight_id_1]
        g2 = self.assignments[flight_id_2]
        if g1 == g2:
            return
        self.assign(flight_id_1, g2)
        self.assign(flight_id_2, g1)

    def to_gate_assignments(self) -> dict[str, GateAssignment]:
        """Convert state into standard GateAssignment dictionary."""
        result: dict[str, GateAssignment] = {}
        for f_id, g_id in self.assignments.items():
            fl = self.flight_map[f_id]
            g = self.gate_map[g_id]
            is_reassign = (
                fl.nominal_gate_id is not None and g_id != fl.nominal_gate_id
            )
            result[f_id] = GateAssignment(
                flight_id=fl.flight_id,
                gate_id=g.gate_id,
                flight_index=fl.flight_index,
                gate_index=g.gate_index,
                is_overflow=g.is_overflow,
                is_reassignment=is_reassign,
                occupancy_start_min=fl.time_window.start_min,
                occupancy_end_min=fl.time_window.end_min,
            )
        return result

    def is_feasible(self) -> bool:
        """Check if current state strictly satisfies all hard constraints."""
        gate_assignments = self.to_gate_assignments()
        diag = verify_hard_constraints_independently(
            flights=self.flights,
            gates=self.gates,
            assignments=gate_assignments,
        )
        return diag.is_valid


def create_initial_state(
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    initial_assignments: Mapping[str, GateAssignment] | None = None,
) -> SAState:
    """Instantiate and strictly validate an initial SA state.

    Args:
        flights: Sequence of Flight domain entities.
        gates: Sequence of Gate entities.
        initial_assignments: Optional pre-existing assignments.

    Returns:
        Validated, hard-feasible SAState.

    Raises:
        ValueError: If initial assignments are incomplete or violate any hard constraints.
    """
    if initial_assignments is None:
        raise ValueError("Initial assignments must be provided to instantiate SAState.")

    # Check completeness
    flight_ids = {f.flight_id for f in flights}
    assigned_ids = set(initial_assignments.keys())
    if assigned_ids != flight_ids:
        missing = flight_ids - assigned_ids
        extra = assigned_ids - flight_ids
        raise ValueError(
            f"Initial assignments mismatch flights. Missing: {missing}, Extra: {extra}"
        )

    # Independent hard-constraint verification
    diag = verify_hard_constraints_independently(
        flights=flights,
        gates=gates,
        assignments=initial_assignments,
    )
    if not diag.is_valid:
        raise ValueError(
            f"Initial assignment violates hard constraints: "
            f"conflicts={diag.conflict_count}, "
            f"compat={diag.gate_compatibility_satisfied}, "
            f"avail={diag.gate_availability_satisfied}, "
            f"all_assigned={diag.all_flights_assigned}"
        )

    assignments_dict = {f_id: assign.gate_id for f_id, assign in initial_assignments.items()}
    return SAState(
        assignments=assignments_dict,
        flights=flights,
        gates=gates,
    )
