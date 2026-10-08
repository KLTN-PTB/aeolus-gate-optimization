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

import math
import time
from typing import Sequence

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
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
            if getattr(self.config, "allow_unbounded_overflow", True):
                overflow_gate = Gate(
                    gate_id="OVERFLOW_APRON",
                    gate_index=len(gate_list),
                    resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
                    is_overflow=True,
                )
                gate_list.append(overflow_gate)

        contact_gates = sorted(
            [g for g in gate_list if not g.is_remote_stand],
            key=lambda g: (g.gate_index, g.gate_id),
        )
        finite_remote_stands = sorted(
            [g for g in gate_list if g.resource_type == GateResourceType.FINITE_REMOTE_STAND],
            key=lambda g: (g.gate_index, g.gate_id),
        )
        unbounded_aprons = [
            g for g in gate_list if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON
        ]

        gate_map = {g.gate_id: g for g in gate_list}

        # Track occupied time windows per capacity-constrained resource
        gate_occupancies: dict[str, list[FlightTimeWindow]] = {
            g.gate_id: [] for g in gate_list if g.resource_type != GateResourceType.UNBOUNDED_OVERFLOW_APRON
        }

        # 1. Deterministic flight ordering: arrival start -> arrival end -> flight_id
        sorted_flights = sorted(
            flights,
            key=lambda f: (f.time_window.start_min, f.time_window.end_min, f.flight_id),
        )

        assignments: dict[str, GateAssignment] = {}
        is_all_feasible = True

        def _can_accommodate_window(target_g: Gate, window: FlightTimeWindow) -> bool:
            if target_g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON:
                return True
            cur_occ = gate_occupancies.get(target_g.gate_id, [])
            cap = int(target_g.capacity) if (target_g.capacity is not None and math.isfinite(target_g.capacity)) else 1
            if cap == 1:
                return not any(window.overlaps(occ) for occ in cur_occ)
            # Pooled capacity K > 1
            events: list[tuple[int, int]] = [(window.start_min, 1), (window.end_min, -1)]
            for occ in cur_occ:
                events.append((occ.start_min, 1))
                events.append((occ.end_min, -1))
            events.sort(key=lambda ev: (ev[0], ev[1]))
            running = 0
            for _, delta in events:
                running += delta
                if running > cap:
                    return False
            return True

        for fl in sorted_flights:
            w_fl = fl.time_window
            chosen_gate: Gate | None = None

            # Policy Step 1: Nominal Gate Priority
            if fl.nominal_gate_id is not None and fl.nominal_gate_id in gate_map:
                nom_g = gate_map[fl.nominal_gate_id]
                if (
                    nom_g.is_compatible_carrier(fl.carrier)
                    and nom_g.is_compatible_aircraft(fl.aircraft_type)
                    and nom_g.is_available_during(w_fl)
                ):
                    if _can_accommodate_window(nom_g, w_fl):
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
                    if not _can_accommodate_window(g, w_fl):
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
                    candidates.sort(key=lambda item: (item[0], item[1]))
                    chosen_gate = candidates[0][2]

            # Policy Step 3: Feasible Finite Remote Stand (Best-Fit Gap)
            if chosen_gate is None and finite_remote_stands:
                remote_candidates: list[tuple[int, int, Gate]] = []
                for g in finite_remote_stands:
                    if not g.is_compatible_carrier(fl.carrier):
                        continue
                    if not g.is_compatible_aircraft(fl.aircraft_type):
                        continue
                    if not g.is_available_during(w_fl):
                        continue
                    if not _can_accommodate_window(g, w_fl):
                        continue

                    prior_ends = [
                        w_occ.end_min
                        for w_occ in gate_occupancies[g.gate_id]
                        if w_occ.end_min <= w_fl.start_min
                    ]
                    last_end = max(prior_ends) if prior_ends else 0
                    idle_gap = w_fl.start_min - last_end
                    remote_candidates.append((idle_gap, g.gate_index, g))

                if remote_candidates:
                    remote_candidates.sort(key=lambda item: (item[0], item[1]))
                    chosen_gate = remote_candidates[0][2]

            # Policy Step 4: Unbounded Apron Fallback (Only if explicitly present)
            if chosen_gate is None:
                if unbounded_aprons:
                    chosen_gate = unbounded_aprons[0]
                else:
                    # Infeasible: capacity exhausted and no unbounded apron available
                    is_all_feasible = False
                    continue

            # Record assignment
            if chosen_gate.gate_id in gate_occupancies:
                gate_occupancies[chosen_gate.gate_id].append(w_fl)

            is_reassign = (
                fl.nominal_gate_id is not None
                and chosen_gate.gate_id != fl.nominal_gate_id
            )

            state_str = (
                GateAssignmentState.REMOTE_STAND.value
                if chosen_gate.is_remote_stand
                else GateAssignmentState.CONTACT_GATE.value
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
                assignment_state=state_str,
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
