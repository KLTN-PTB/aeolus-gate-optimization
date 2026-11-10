"""Exhaustive Combinatorial Oracle for Gate Assignment (Phase P06 Verification).

Enumerates all possible flight-to-gate assignments for small-scale problem instances:
1. Evaluates feasibility via independent hard constraint verification outside the solver.
2. Evaluates authoritative soft objective cost for all feasible assignments.
3. Finds the true mathematical global minimum objective and all optimal assignments.
4. Serves as ground-truth oracle to certify CP-SAT formulation mathematical parity (Section VII & CP01).
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Mapping, Sequence

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment


@dataclass(frozen=True)
class OracleResult:
    """Ground-truth certification output produced by exhaustive combinatorial search."""

    is_feasible: bool
    total_assignments_enumerated: int
    feasible_assignments_count: int
    optimal_objective: float | None
    optimal_assignments: list[dict[str, GateAssignment]]
    all_feasible_objectives: list[float]


def solve_exhaustive_oracle(
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig | None = None,
    *,
    allow_overflow: bool = True,
    max_combinations: int = 1_000_000,
) -> OracleResult:
    """Solve gate assignment problem via exhaustive brute-force search over all candidate gates.

    Args:
        flights: Sequence of Flight entities.
        gates: Sequence of Gate entities.
        config: Configuration containing objective weights.
        allow_overflow: Whether to permit overflow apron stand if not in gates.
        max_combinations: Safety guard against combinatorial explosion.

    Returns:
        OracleResult with certified minimum objective and feasibility proof.
    """
    cfg = config or GateOptimizationConfig()
    gate_list = list(gates)
    has_overflow = any(g.is_overflow for g in gate_list)
    if allow_overflow and not has_overflow:
        overflow_gate = Gate(
            gate_id="OVERFLOW_APRON",
            gate_index=len(gate_list),
            resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
            capacity=math.inf,
            is_overflow=True,
        )
        gate_list.append(overflow_gate)

    n_flights = len(flights)
    if n_flights == 0:
        return OracleResult(
            is_feasible=True,
            total_assignments_enumerated=1,
            feasible_assignments_count=1,
            optimal_objective=0.0,
            optimal_assignments=[{}],
            all_feasible_objectives=[0.0],
        )

    # 1. Determine eligible gates per flight
    candidate_gates_per_flight: list[list[Gate]] = []
    for fl in flights:
        cands = [
            g
            for g in gate_list
            if g.is_compatible_carrier(fl.carrier)
            and g.is_compatible_aircraft(fl.aircraft_type)
            and g.is_available_during(fl.time_window)
        ]
        if not cands:
            # Flight has 0 eligible gates; problem is mathematically infeasible
            return OracleResult(
                is_feasible=False,
                total_assignments_enumerated=0,
                feasible_assignments_count=0,
                optimal_objective=None,
                optimal_assignments=[],
                all_feasible_objectives=[],
            )
        candidate_gates_per_flight.append(cands)

    total_combinations = math.prod(len(cands) for cands in candidate_gates_per_flight)
    if total_combinations > max_combinations:
        raise ValueError(
            f"Exhaustive search space ({total_combinations:,} combinations) exceeds "
            f"max_combinations threshold ({max_combinations:,}). Use smaller instance for oracle."
        )

    # 2. Enumerate Cartesian product
    feasible_count = 0
    best_obj = float("inf")
    optimal_assignments: list[dict[str, GateAssignment]] = []
    all_feasible_objs: list[float] = []

    for gate_tuple in itertools.product(*candidate_gates_per_flight):
        assignment_map: dict[str, GateAssignment] = {}
        for f_idx, (fl, g) in enumerate(zip(flights, gate_tuple)):
            assignment_map[fl.flight_id] = GateAssignment(
                flight_id=fl.flight_id,
                gate_id=g.gate_id,
                flight_index=f_idx,
                gate_index=g.gate_index,
                is_overflow=g.is_overflow,
                is_reassignment=bool(fl.nominal_gate_id and g.gate_id != fl.nominal_gate_id),
                occupancy_start_min=fl.time_window.start_min,
                occupancy_end_min=fl.time_window.end_min,
            )

        # Verify hard constraints independently
        diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gate_list,
            assignments=assignment_map,
        )

        if diag.is_valid:
            feasible_count += 1
            eval_res = evaluate_gate_assignment(
                assignments=assignment_map,
                flights=flights,
                gates=gate_list,
                config=cfg,
            )
            cost = eval_res.objective_value
            all_feasible_objs.append(cost)

            if cost < best_obj - 1e-9:
                best_obj = cost
                optimal_assignments = [assignment_map]
            elif abs(cost - best_obj) < 1e-9:
                optimal_assignments.append(assignment_map)

    if feasible_count == 0:
        return OracleResult(
            is_feasible=False,
            total_assignments_enumerated=total_combinations,
            feasible_assignments_count=0,
            optimal_objective=None,
            optimal_assignments=[],
            all_feasible_objectives=[],
        )

    return OracleResult(
        is_feasible=True,
        total_assignments_enumerated=total_combinations,
        feasible_assignments_count=feasible_count,
        optimal_objective=round(best_obj, 4),
        optimal_assignments=optimal_assignments,
        all_feasible_objectives=sorted(all_feasible_objs),
    )
