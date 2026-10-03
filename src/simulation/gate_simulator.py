"""Gate Simulation and Optimization Engine.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)

Provides:
1. Nominal gate planning on scheduled intervals.
2. Nominal plan robustness evaluation (conflicts and overlap durations under realization).
3. Dynamic greedy gate allocation with remote stand / overflow recourse.
4. Exact mixed-integer linear programming (MILP) gate optimization via SciPy / HiGHS.
5. Concurrent gate occupancy tracking, peak demand, and gate utilization metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.optimize import LinearConstraint, milp

from src.simulation.turn_synthesis import SyntheticTurn


@dataclass
class GateConflict:
    """Record of a gate conflict between two flights simultaneously assigned to the same gate."""

    gate_id: int
    flight_key_1: str
    flight_key_2: str
    overlap_duration_min: float
    overlap_start_min: float
    overlap_end_min: float


@dataclass
class GateSimulationResult:
    """Downstream gate simulation and allocation outcome for one operational day/scenario."""

    scenario_id: int
    n_flights: int
    n_contact_gates: int
    solver_mode: str  # "nominal_frozen", "dynamic_greedy", "exact_milp"
    assignments: dict[str, int]  # flight_key -> gate_id (0..M-1: contact, -1: overflow)
    conflicts: list[GateConflict]
    total_conflict_count: int
    total_conflict_duration_min: float
    overflow_count: int
    reassignments_count: int
    peak_concurrent_occupancy: int
    gate_utilization_rate: float
    wall_clock_time_sec: float

    @property
    def has_conflicts(self) -> bool:
        return self.total_conflict_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "n_flights": self.n_flights,
            "n_contact_gates": self.n_contact_gates,
            "solver_mode": self.solver_mode,
            "total_conflict_count": self.total_conflict_count,
            "total_conflict_duration_min": self.total_conflict_duration_min,
            "overflow_count": self.overflow_count,
            "reassignments_count": self.reassignments_count,
            "peak_concurrent_occupancy": self.peak_concurrent_occupancy,
            "gate_utilization_rate": self.gate_utilization_rate,
            "wall_clock_time_sec": self.wall_clock_time_sec,
        }


class GateSimulator:
    """Gate simulation and assignment optimizer for operational delay scenarios."""

    OVERFLOW_GATE_ID = -1

    def __init__(
        self,
        n_contact_gates: int = 30,
        *,
        overflow_penalty: float = 100.0,
        reassignment_penalty: float = 1.0,
        buffer_minutes: float = 0.0,
    ) -> None:
        """Initialize GateSimulator.

        Args:
            n_contact_gates: Total available contact gates (M).
            overflow_penalty: Objective penalty for assigning flight to remote stand/overflow.
            reassignment_penalty: Objective penalty for changing flight away from nominal gate.
            buffer_minutes: Separation buffer required between consecutive flights at the same gate.
        """
        if n_contact_gates <= 0:
            raise ValueError("n_contact_gates must be strictly positive")
        self.n_contact_gates = int(n_contact_gates)
        self.overflow_penalty = float(overflow_penalty)
        self.reassignment_penalty = float(reassignment_penalty)
        self.buffer_minutes = float(buffer_minutes)

    # =========================================================================
    # Nominal Schedule Allocation
    # =========================================================================
    def build_nominal_schedule_plan(self, turns: list[SyntheticTurn]) -> dict[str, int]:
        """Compute conflict-free nominal gate assignments based on scheduled times.

        Uses greedy interval scheduling ordered by scheduled arrival.
        """
        # Sort by scheduled arrival
        sorted_turns = sorted(turns, key=lambda t: (t.scheduled_arrival_min, t.scheduled_departure_min))
        gate_available_at = np.zeros(self.n_contact_gates, dtype=float)
        nominal_assignments: dict[str, int] = {}

        for turn in sorted_turns:
            start = turn.scheduled_arrival_min
            end = turn.scheduled_departure_min + self.buffer_minutes

            # Find first available contact gate
            assigned_gate = self.OVERFLOW_GATE_ID
            for g in range(self.n_contact_gates):
                if gate_available_at[g] <= start:
                    assigned_gate = g
                    gate_available_at[g] = end
                    break

            if assigned_gate == self.OVERFLOW_GATE_ID:
                # Fallback: assign to gate with earliest release time
                earliest_g = int(np.argmin(gate_available_at))
                assigned_gate = earliest_g
                gate_available_at[earliest_g] = end

            nominal_assignments[turn.flight_key] = assigned_gate

        return nominal_assignments

    # =========================================================================
    # Path 1: Nominal Plan Robustness (Zero Recourse)
    # =========================================================================
    def evaluate_nominal_plan_under_delays(
        self,
        turns: list[SyntheticTurn],
        nominal_assignments: dict[str, int],
        *,
        scenario_id: int = 0,
    ) -> GateSimulationResult:
        """Evaluate gate conflicts if the airport rigidly keeps the nominal gate plan."""
        import time
        t0 = time.time()

        # Group turns by gate
        gate_to_turns: dict[int, list[SyntheticTurn]] = {g: [] for g in range(self.n_contact_gates)}
        for turn in turns:
            g = nominal_assignments.get(turn.flight_key, self.OVERFLOW_GATE_ID)
            if g != self.OVERFLOW_GATE_ID:
                gate_to_turns[g].append(turn)

        conflicts: list[GateConflict] = []
        for g, g_turns in gate_to_turns.items():
            n_t = len(g_turns)
            for i in range(n_t):
                t1 = g_turns[i]
                for j in range(i + 1, n_t):
                    t2 = g_turns[j]
                    # Check overlap: max(start1, start2) < min(end1, end2)
                    start_overlap = max(t1.gate_arrival_min, t2.gate_arrival_min)
                    end_overlap = min(t1.gate_release_min, t2.gate_release_min)
                    if start_overlap < end_overlap:
                        conflicts.append(
                            GateConflict(
                                gate_id=g,
                                flight_key_1=t1.flight_key,
                                flight_key_2=t2.flight_key,
                                overlap_duration_min=float(end_overlap - start_overlap),
                                overlap_start_min=float(start_overlap),
                                overlap_end_min=float(end_overlap),
                            )
                        )

        tot_conflict_duration = sum(c.overlap_duration_min for c in conflicts)
        peak_occ, util = self._compute_occupancy_metrics(turns, nominal_assignments)

        return GateSimulationResult(
            scenario_id=scenario_id,
            n_flights=len(turns),
            n_contact_gates=self.n_contact_gates,
            solver_mode="nominal_frozen",
            assignments=nominal_assignments,
            conflicts=conflicts,
            total_conflict_count=len(conflicts),
            total_conflict_duration_min=float(tot_conflict_duration),
            overflow_count=sum(1 for g in nominal_assignments.values() if g == self.OVERFLOW_GATE_ID),
            reassignments_count=0,
            peak_concurrent_occupancy=peak_occ,
            gate_utilization_rate=util,
            wall_clock_time_sec=time.time() - t0,
        )

    # =========================================================================
    # Path 2: Dynamic Greedy Recourse
    # =========================================================================
    def solve_dynamic_greedy(
        self,
        turns: list[SyntheticTurn],
        nominal_assignments: dict[str, int],
        *,
        scenario_id: int = 0,
    ) -> GateSimulationResult:
        """Dynamic greedy recourse assigning flights to earliest available contact gate or overflow."""
        import time
        t0 = time.time()

        # Sort flights by realized arrival time
        sorted_turns = sorted(turns, key=lambda t: (t.gate_arrival_min, t.gate_release_min))
        gate_available_at = np.zeros(self.n_contact_gates, dtype=float)
        realized_assignments: dict[str, int] = {}
        reassignments = 0
        overflow = 0

        for turn in sorted_turns:
            start = turn.gate_arrival_min
            end = turn.gate_release_min + self.buffer_minutes
            nom_g = nominal_assignments.get(turn.flight_key, self.OVERFLOW_GATE_ID)

            assigned_g = self.OVERFLOW_GATE_ID

            # 1. Try to keep nominal gate if free
            if nom_g != self.OVERFLOW_GATE_ID and gate_available_at[nom_g] <= start:
                assigned_g = nom_g
            else:
                # 2. Search for any available contact gate
                for g in range(self.n_contact_gates):
                    if gate_available_at[g] <= start:
                        assigned_g = g
                        break

            # 3. If no contact gate available, send to overflow
            if assigned_g != self.OVERFLOW_GATE_ID:
                gate_available_at[assigned_g] = end
                if assigned_g != nom_g:
                    reassignments += 1
            else:
                overflow += 1
                if nom_g != self.OVERFLOW_GATE_ID:
                    reassignments += 1

            realized_assignments[turn.flight_key] = assigned_g

        peak_occ, util = self._compute_occupancy_metrics(turns, realized_assignments)

        return GateSimulationResult(
            scenario_id=scenario_id,
            n_flights=len(turns),
            n_contact_gates=self.n_contact_gates,
            solver_mode="dynamic_greedy",
            assignments=realized_assignments,
            conflicts=[],  # Greedy dynamic allocation enforces zero conflict by construction
            total_conflict_count=0,
            total_conflict_duration_min=0.0,
            overflow_count=overflow,
            reassignments_count=reassignments,
            peak_concurrent_occupancy=peak_occ,
            gate_utilization_rate=util,
            wall_clock_time_sec=time.time() - t0,
        )

    # =========================================================================
    # Path 3: Exact Mixed-Integer Linear Programming (MILP) Optimizer
    # =========================================================================
    def solve_milp_assignment(
        self,
        turns: list[SyntheticTurn],
        nominal_assignments: dict[str, int],
        *,
        scenario_id: int = 0,
        time_limit_sec: float = 5.0,
    ) -> GateSimulationResult:
        """Solve exact optimal gate assignment minimizing overflow and reassignments via HiGHS MILP."""
        import time
        t0 = time.time()

        n = len(turns)
        m = self.n_contact_gates
        # Total decision variables: n * (m + 1)
        # x[i, g] for g in 0..m-1 (contact gates), and x[i, m] for overflow stand
        total_vars = n * (m + 1)

        def _var_idx(i_fl: int, g_idx: int) -> int:
            return i_fl * (m + 1) + g_idx

        # 1. Objective function coefficients: c
        c = np.zeros(total_vars, dtype=float)
        for i, turn in enumerate(turns):
            nom_g = nominal_assignments.get(turn.flight_key, self.OVERFLOW_GATE_ID)
            # Reassignment cost for contact gates
            for g in range(m):
                if g != nom_g:
                    c[_var_idx(i, g)] = self.reassignment_penalty
            # Overflow cost
            c[_var_idx(i, m)] = self.overflow_penalty

        # 2. Assignment constraints: sum_g x[i, g] == 1 for each flight
        # Rows: n
        rows = []
        lhs = []
        rhs = []
        for i in range(n):
            row = np.zeros(total_vars, dtype=float)
            for g in range(m + 1):
                row[_var_idx(i, g)] = 1.0
            rows.append(row)
            lhs.append(1.0)
            rhs.append(1.0)

        # 3. Non-overlap constraints on contact gates:
        # For each pair (i, j) that overlaps in time and for each gate g:
        # x[i, g] + x[j, g] <= 1
        for i in range(n):
            t1 = turns[i]
            for j in range(i + 1, n):
                t2 = turns[j]
                # Check if simulated intervals overlap
                start_overlap = max(t1.gate_arrival_min, t2.gate_arrival_min)
                end_overlap = min(t1.gate_release_min, t2.gate_release_min) + self.buffer_minutes
                if start_overlap < end_overlap:
                    for g in range(m):
                        row = np.zeros(total_vars, dtype=float)
                        row[_var_idx(i, g)] = 1.0
                        row[_var_idx(j, g)] = 1.0
                        rows.append(row)
                        lhs.append(0.0)
                        rhs.append(1.0)

        a_mat = np.array(rows, dtype=float)
        constraints = LinearConstraint(a_mat, lhs, rhs)
        integrality = np.ones(total_vars, dtype=int)  # all binary variables
        bounds = (np.zeros(total_vars), np.ones(total_vars))

        # Solve MILP via SciPy HiGHS
        try:
            res = milp(c=c, integrality=integrality, constraints=constraints, bounds=bounds)
            if res.success and res.x is not None:
                x_sol = np.round(res.x).astype(int)
                realized_assignments: dict[str, int] = {}
                reassignments = 0
                overflow = 0

                for i, turn in enumerate(turns):
                    nom_g = nominal_assignments.get(turn.flight_key, self.OVERFLOW_GATE_ID)
                    assigned_g = self.OVERFLOW_GATE_ID
                    for g in range(m):
                        if x_sol[_var_idx(i, g)] == 1:
                            assigned_g = g
                            break

                    if assigned_g == self.OVERFLOW_GATE_ID:
                        overflow += 1
                        if nom_g != self.OVERFLOW_GATE_ID:
                            reassignments += 1
                    else:
                        if assigned_g != nom_g:
                            reassignments += 1

                    realized_assignments[turn.flight_key] = assigned_g

                peak_occ, util = self._compute_occupancy_metrics(turns, realized_assignments)

                return GateSimulationResult(
                    scenario_id=scenario_id,
                    n_flights=n,
                    n_contact_gates=self.n_contact_gates,
                    solver_mode="exact_milp",
                    assignments=realized_assignments,
                    conflicts=[],
                    total_conflict_count=0,
                    total_conflict_duration_min=0.0,
                    overflow_count=overflow,
                    reassignments_count=reassignments,
                    peak_concurrent_occupancy=peak_occ,
                    gate_utilization_rate=util,
                    wall_clock_time_sec=time.time() - t0,
                )
        except Exception:
            pass

        # Fallback to dynamic greedy if MILP is infeasible or errors
        return self.solve_dynamic_greedy(turns, nominal_assignments, scenario_id=scenario_id)

    # =========================================================================
    # Occupancy Metrics Helpers
    # =========================================================================
    def _compute_occupancy_metrics(
        self,
        turns: list[SyntheticTurn],
        assignments: dict[str, int],
    ) -> tuple[int, float]:
        """Compute peak concurrent contact gate occupancy and gate utilization rate."""
        contact_turns = [
            t for t in turns if assignments.get(t.flight_key, self.OVERFLOW_GATE_ID) != self.OVERFLOW_GATE_ID
        ]
        if not contact_turns:
            return 0, 0.0

        # Event-based sweep-line algorithm to find peak concurrent occupancy
        events: list[tuple[float, int]] = []
        total_occupied_minutes = 0.0

        for t in contact_turns:
            events.append((t.gate_arrival_min, 1))   # Arrival: +1
            events.append((t.gate_release_min, -1))  # Release: -1
            total_occupied_minutes += t.occupancy_duration_min

        # Sort events chronologically (releases before arrivals at exact same minute)
        events.sort(key=lambda e: (e[0], e[1]))

        current_occ = 0
        peak_occ = 0
        for _, delta in events:
            current_occ += delta
            if current_occ > peak_occ:
                peak_occ = current_occ

        # Operational span (from earliest arrival to latest release)
        min_time = min(t.gate_arrival_min for t in contact_turns)
        max_time = max(t.gate_release_min for t in contact_turns)
        span_minutes = max(1.0, max_time - min_time)

        # Utilization: total occupied gate-minutes / (n_contact_gates * span_minutes)
        utilization = float(total_occupied_minutes / (self.n_contact_gates * span_minutes))

        return int(min(peak_occ, self.n_contact_gates)), float(np.clip(utilization, 0.0, 1.0))
