"""Conflict Detector for Operational Gate Occupancy Intervals.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Given assignments and occupancy intervals:
  1. Detect pairwise overlaps on contact gates.
  2. Count total conflicts.
  3. Calculate total and per-conflict overlap duration.
  4. Calculate concurrent occupancy over time (peak demand).
  5. Compute gate utilization rate.
- Explicit disclaimer: Evaluates synthetic robustness; does not infer real-world airport conflicts
  in the absence of physical airfield logs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from src.optimization.domain import Gate, GateAssignment
from src.simulation.aircraft_turn import AircraftTurn


@dataclass(frozen=True)
class SimulatedConflict:
    """Record of a simulated gate conflict between two flights on the same contact gate."""

    gate_id: str
    flight_1: str
    flight_2: str
    overlap_duration_min: float
    window_1: tuple[int, int]
    window_2: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConflictDetectionResult:
    """Comprehensive conflict, concurrent occupancy, and utilization outcome."""

    conflict_count: int
    total_conflict_duration_min: float
    conflicts: list[SimulatedConflict]
    peak_single_gate_concurrency: int
    peak_airport_concurrency: int
    gate_utilization_rate: float
    has_conflicts: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_count": self.conflict_count,
            "total_conflict_duration_min": float(self.total_conflict_duration_min),
            "peak_single_gate_concurrency": self.peak_single_gate_concurrency,
            "peak_airport_concurrency": self.peak_airport_concurrency,
            "gate_utilization_rate": float(self.gate_utilization_rate),
            "has_conflicts": self.has_conflicts,
            "conflict_details": [c.to_dict() for c in self.conflicts],
        }


def detect_conflicts(
    assignments: Mapping[str, GateAssignment | str],
    turns: Sequence[AircraftTurn],
    gates: Sequence[Gate],
    *,
    day_duration_min: int = 1440,
) -> ConflictDetectionResult:
    """Analyze assignments and occupancy intervals for simulated conflicts and concurrent occupancy.

    Notice: Simulated conflict metrics evaluate operational robustness under synthetic stochastic arrival
    scenarios. They do not infer real-world airport conflicts in the absence of observed physical gate logs.

    Args:
        assignments: Dict mapping flight_id to assigned gate_id or GateAssignment.
        turns: Sequence of AircraftTurn entities with occupancy intervals [sim_arr, gate_release).
        gates: Sequence of Gate entities (contact gates and overflow stands).
        day_duration_min: Total operational minutes in day for utilization calculation (default: 1440).

    Returns:
        ConflictDetectionResult with exact metrics.
    """
    gate_map = {g.gate_id: g for g in gates}
    turn_map = {t.flight_id: t for t in turns}

    # Group flights by gate
    gate_to_turns: dict[str, list[AircraftTurn]] = {g.gate_id: [] for g in gates}
    for f_id, assign in assignments.items():
        g_id = assign.gate_id if isinstance(assign, GateAssignment) else str(assign)
        if g_id in gate_to_turns and f_id in turn_map:
            gate_to_turns[g_id].append(turn_map[f_id])

    conflicts: list[SimulatedConflict] = []
    total_conflict_duration = 0.0
    max_single_gate_concurrency = 0
    total_contact_occupied_min = 0.0

    contact_gates = [g for g in gates if not g.is_overflow]
    n_contact = len(contact_gates)

    # 1. Evaluate pairwise conflicts on contact gates
    for g in gates:
        assigned = gate_to_turns[g.gate_id]
        if not assigned:
            continue

        # Compute peak occupancy at this gate via timeline event sweep
        events: list[tuple[int, int]] = []  # (time, +1 arrival / -1 departure)
        for t in assigned:
            events.append((t.simulated_arrival_min, 1))
            events.append((t.gate_release_min, -1))
            if not g.is_overflow:
                total_contact_occupied_min += t.occupancy_duration_min

        # Sort events: departures before arrivals at exact same minute
        events.sort(key=lambda ev: (ev[0], ev[1]))
        curr_occupancy = 0
        peak_here = 0
        for _, delta in events:
            curr_occupancy += delta
            if curr_occupancy > peak_here:
                peak_here = curr_occupancy
        if peak_here > max_single_gate_concurrency:
            max_single_gate_concurrency = peak_here

        # Check contact conflicts
        if g.is_overflow:
            continue  # Remote apron has no single-aircraft exclusion constraint

        n_here = len(assigned)
        if n_here <= 1:
            continue

        sorted_turns = sorted(assigned, key=lambda t: t.simulated_arrival_min)
        for i in range(n_here - 1):
            t1 = sorted_turns[i]
            w1 = (t1.simulated_arrival_min, t1.gate_release_min)
            for j in range(i + 1, n_here):
                t2 = sorted_turns[j]
                w2 = (t2.simulated_arrival_min, t2.gate_release_min)
                # Overlap test: max(s1, s2) < min(e1, e2)
                if max(w1[0], w2[0]) < min(w1[1], w2[1]):
                    overlap = min(w1[1], w2[1]) - max(w1[0], w2[0])
                    total_conflict_duration += overlap
                    conflicts.append(
                        SimulatedConflict(
                            gate_id=g.gate_id,
                            flight_1=t1.flight_id,
                            flight_2=t2.flight_id,
                            overlap_duration_min=float(overlap),
                            window_1=w1,
                            window_2=w2,
                        )
                    )

    # 2. Airport-wide concurrent contact occupancy
    airport_events: list[tuple[int, int]] = []
    for g in contact_gates:
        for t in gate_to_turns[g.gate_id]:
            airport_events.append((t.simulated_arrival_min, 1))
            airport_events.append((t.gate_release_min, -1))
    airport_events.sort(key=lambda ev: (ev[0], ev[1]))

    curr_airport = 0
    max_airport_concurrency = 0
    for _, delta in airport_events:
        curr_airport += delta
        if curr_airport > max_airport_concurrency:
            max_airport_concurrency = curr_airport

    # 3. Gate utilization rate
    total_capacity_min = max(1.0, float(n_contact * day_duration_min))
    utilization_rate = total_contact_occupied_min / total_capacity_min

    return ConflictDetectionResult(
        conflict_count=len(conflicts),
        total_conflict_duration_min=total_conflict_duration,
        conflicts=conflicts,
        peak_single_gate_concurrency=max_single_gate_concurrency,
        peak_airport_concurrency=max_airport_concurrency,
        gate_utilization_rate=utilization_rate,
        has_conflicts=len(conflicts) > 0,
    )
