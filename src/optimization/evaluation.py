"""Common Gate Assignment Evaluator (V2 Repaired).

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. Unified evaluation for all gate optimization solvers (CP-SAT, Greedy, SA).
2. Independent hard-constraint verification outside the solver (overlaps, compatibility, availability).
3. Explicit separation between:
   - Decision-dependent costs (reassignment, remote overflow, soft conflict)
   - Exogenous reporting metrics (exogenous delay, turnaround slack)
4. Guarantees optimizer cannot self-certify feasibility (certified by Independent Verifier).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateAssignmentState,
    ObjectiveBreakdown,
    OptimizationResult,
    verify_hard_constraints_independently,
)


def evaluate_gate_assignment(
    assignments: Mapping[str, GateAssignment],
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig | None = None,
    *,
    realized_flights: Sequence[Flight] | None = None,
    runtime_ms: float = 0.0,
    solver_status: str | None = None,
    solver_name: str = "unknown",
) -> OptimizationResult:
    """Evaluate a complete gate assignment solution against standard constraints and objective.

    This common evaluator is used by CP-SAT, Greedy, and Simulated Annealing solvers to guarantee
    identical constraint verification and objective calculation.

    Args:
        assignments: Mapping of flight_id to GateAssignment.
        flights: Sequence of Flight domain entities.
        gates: Sequence of Gate entities.
        config: Optimization configuration with component weights.
        realized_flights: Optional sequence of flights with realized actual delays for post-hoc conflict audit.
        runtime_ms: Solver execution time in milliseconds.
        solver_status: Optional explicit solver status string.
        solver_name: Identifier for the solver that produced the solution.

    Returns:
        OptimizationResult with complete diagnostics and decomposed objective breakdown.
    """
    cfg = config or GateOptimizationConfig()
    flight_map = {f.flight_id: f for f in flights}
    gate_map = {g.gate_id: g for g in gates}

    # 1. Independent Hard Constraint Verification
    diagnostics = verify_hard_constraints_independently(
        flights=flights,
        gates=gates,
        assignments=assignments,
        realized_flights=realized_flights,
    )

    # 2. Soft Objective Decomposition
    total_reassignment_cost = 0.0
    total_overflow_cost = 0.0
    total_delay_cost = 0.0
    total_risk_cost = 0.0

    for f_id, fl in flight_map.items():
        assign = assignments.get(f_id)
        if assign is None:
            # Unassigned flight incurs massive overflow penalty
            total_overflow_cost += cfg.overflow_weight * 2.0
            continue

        gate = gate_map.get(assign.gate_id)
        is_overflow = gate.is_overflow if gate is not None else assign.is_overflow

        # A. Reassignment cost (deviation from nominal plan on contact gate)
        if not is_overflow:
            if fl.nominal_gate_id is not None and assign.gate_id != fl.nominal_gate_id:
                total_reassignment_cost += cfg.reassignment_weight

        # B. Overflow penalty (remote stand / apron)
        if is_overflow:
            total_overflow_cost += cfg.overflow_weight
            if fl.nominal_gate_id is not None:
                total_reassignment_cost += cfg.reassignment_weight

        # C. Delay cost (exogenous flight reporting context)
        if fl.arrival_delay_min > 0:
            total_delay_cost += (fl.arrival_delay_min / 60.0) * cfg.delay_weight

        # D. Buffer risk cost (if turnaround duration is close to minimum)
        stay_duration = fl.simulated_departure_min - fl.predicted_arrival_min
        slack = stay_duration - fl.min_turnaround_min
        if slack < 15:
            # Tight turn buffer penalty
            total_risk_cost += ((15 - slack) / 15.0) * cfg.risk_weight

    # E. Conflict penalty (if any planned contact gate conflicts exist outside solver)
    total_conflict_cost = diagnostics.conflict_count * cfg.conflict_weight

    total_objective = (
        total_reassignment_cost
        + total_overflow_cost
        + total_delay_cost
        + total_conflict_cost
        + total_risk_cost
    )

    breakdown = ObjectiveBreakdown(
        total_cost=total_objective,
        reassignment_cost=total_reassignment_cost,
        overflow_cost=total_overflow_cost,
        delay_cost=total_delay_cost,
        conflict_cost=total_conflict_cost,
        risk_cost=total_risk_cost,
        weights=cfg.to_dict(),
    )

    # Determine status
    if solver_status is not None:
        status_str = solver_status
    elif diagnostics.is_valid:
        status_str = "FEASIBLE"
    else:
        status_str = "INFEASIBLE"

    # Solver output CANNOT self-certify feasibility: certified by Independent Verifier
    is_feasible = bool(diagnostics.is_valid and diagnostics.unassigned_count == 0)

    return OptimizationResult(
        status=status_str,
        objective_value=total_objective,
        objective_breakdown=breakdown,
        feasible=is_feasible,
        runtime_ms=runtime_ms,
        optimality_gap=None,
        assignments=dict(assignments),
        constraint_diagnostics=diagnostics,
        solver_configuration={
            "solver_name": solver_name,
            **cfg.to_dict(),
        },
    )
