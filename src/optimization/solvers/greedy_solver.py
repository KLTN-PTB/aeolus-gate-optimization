"""Deterministic Greedy Gate Assignment Solver Baseline.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Explicit, deterministic greedy allocation policy.
- Deterministic flight ordering: (window.start_min, window.end_min, flight_id).
- Fixed gate selection rule:
  1. Try nominal gate first if compatible, available, and conflict-free.
  2. Search contact gates ordered by lowest idle gap (best-fit) with deterministic gate_index tie-breaking.
  3. Fall back to remote stand / overflow apron if no contact gate is feasible.
- Uses the exact same flights, gates, constraints, and common evaluator as CP-SAT.
"""

from __future__ import annotations

import time
from typing import Sequence

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    OptimizationResult,
)
from src.optimization.evaluation import evaluate_gate_assignment


class DeterministicGreedyGateSolver:
    """Deterministic Greedy Gate Assignment Heuristic Baseline."""

    def __init__(self, config: GateOptimizationConfig | None = None) -> None:
        self.config = config or GateOptimizationConfig()

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        allow_overflow: bool = True,
    ) -> OptimizationResult:
        """Solve gate assignment deterministically via greedy interval scheduling.

        Args:
            flights: Sequence of Flight domain entities.
            gates: Sequence of Gate entities.
            allow_overflow: Whether unassigned flights can overflow to remote stands.

        Returns:
            OptimizationResult evaluated by the common evaluator.
        """
        t0 = time.perf_counter()

        n_flights = len(flights)
        if n_flights == 0:
            return evaluate_gate_assignment(
                assignments={},
                flights=flights,
                gates=gates,
                config=self.config,
                runtime_ms=0.0,
                solver_status="OPTIMAL",
                solver_name="DeterministicGreedy",
            )

        # Prepare gate entities
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            overflow_gate = Gate(
                gate_id="OVERFLOW_APRON",
                gate_index=len(gate_list),
                is_overflow=True,
            )
            gate_list.append(overflow_gate)

        contact_gates = sorted(
            [g for g in gate_list if not g.is_overflow],
            key=lambda g: (g.gate_index, g.gate_id),
        )
        overflow_gates = [g for g in gate_list if g.is_overflow]
        default_overflow = overflow_gates[0] if overflow_gates else None

        gate_map = {g.gate_id: g for g in gate_list}

        # Track occupied time windows per contact gate
        gate_occupancies: dict[str, list[FlightTimeWindow]] = {
            g.gate_id: [] for g in contact_gates
        }

        # 1. Deterministic flight ordering: arrival start -> arrival end -> flight_id
        sorted_flights = sorted(
            flights,
            key=lambda f: (f.time_window.start_min, f.time_window.end_min, f.flight_id),
        )

        assignments: dict[str, GateAssignment] = {}
        is_all_feasible = True

        for fl in sorted_flights:
            w_fl = fl.time_window
            chosen_gate: Gate | None = None

            # Policy Step 1: Nominal Gate Priority
            if fl.nominal_gate_id is not None and fl.nominal_gate_id in gate_occupancies:
                nom_g = gate_map[fl.nominal_gate_id]
                if (
                    nom_g.is_compatible_carrier(fl.carrier)
                    and nom_g.is_compatible_aircraft(fl.aircraft_type)
                    and nom_g.is_available_during(w_fl)
                ):
                    # Check overlap with existing occupancies
                    has_conflict = any(w_fl.overlaps(w_occ) for w_occ in gate_occupancies[nom_g.gate_id])
                    if not has_conflict:
                        chosen_gate = nom_g

            # Policy Step 2: Earliest Feasible Contact Gate (Best-Fit Idle Gap)
            if chosen_gate is None:
                candidates: list[tuple[int, int, Gate]] = []
                for g in contact_gates:
                    if not g.is_compatible_carrier(fl.carrier):
                        continue
                    if not g.is_compatible_aircraft(fl.aircraft_type):
                        continue
                    if not g.is_available_during(w_fl):
                        continue

                    # Overlap check
                    overlaps = any(w_fl.overlaps(w_occ) for w_occ in gate_occupancies[g.gate_id])
                    if overlaps:
                        continue

                    # Compute idle gap before flight arrival
                    prior_ends = [
                        w_occ.end_min
                        for w_occ in gate_occupancies[g.gate_id]
                        if w_occ.end_min <= w_fl.start_min
                    ]
                    last_end = max(prior_ends) if prior_ends else 0
                    idle_gap = w_fl.start_min - last_end
                    candidates.append((idle_gap, g.gate_index, g))

                if candidates:
                    # Sort by smallest idle gap (best-fit), break ties by gate_index
                    candidates.sort(key=lambda item: (item[0], item[1]))
                    chosen_gate = candidates[0][2]

            # Policy Step 3: Overflow Stand Fallback
            if chosen_gate is None:
                if default_overflow is not None:
                    chosen_gate = default_overflow
                else:
                    is_all_feasible = False
                    continue

            # Record assignment
            if not chosen_gate.is_overflow:
                gate_occupancies[chosen_gate.gate_id].append(w_fl)

            is_reassign = (
                fl.nominal_gate_id is not None
                and chosen_gate.gate_id != fl.nominal_gate_id
            )

            assignments[fl.flight_id] = GateAssignment(
                flight_id=fl.flight_id,
                gate_id=chosen_gate.gate_id,
                flight_index=fl.flight_index,
                gate_index=chosen_gate.gate_index,
                is_overflow=chosen_gate.is_overflow,
                is_reassignment=is_reassign,
                occupancy_start_min=w_fl.start_min,
                occupancy_end_min=w_fl.end_min,
            )

        runtime_ms = (time.perf_counter() - t0) * 1000.0

        solver_status = "FEASIBLE" if (is_all_feasible and len(assignments) == n_flights) else "INFEASIBLE"

        # Evaluate through common evaluator
        return evaluate_gate_assignment(
            assignments=assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=runtime_ms,
            solver_status=solver_status,
            solver_name="DeterministicGreedy",
        )
