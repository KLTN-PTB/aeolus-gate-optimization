"""Objective Evaluation for Simulated Annealing States.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Exact parity with the common evaluator evaluate_gate_assignment().
- Decomposed cost evaluation for fast state assessment.
- Fail-closed verification: penalties for conflicts and illegal assignments.
"""

from __future__ import annotations

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import OptimizationResult
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.state import SAState


def compute_state_objective(
    state: SAState,
    config: GateOptimizationConfig,
) -> float:
    """Compute exact soft objective value for an SA state.

    Matches evaluate_gate_assignment() soft cost decomposition:
    Obj = reassignment_cost + overflow_cost + delay_cost + risk_cost + conflict_cost

    Args:
        state: SAState with flight -> gate mapping.
        config: GateOptimizationConfig with soft objective weights.

    Returns:
        Total floating point objective cost.
    """
    total_reassignment_cost = 0.0
    total_overflow_cost = 0.0
    total_delay_cost = 0.0
    total_risk_cost = 0.0

    flight_map = state.flight_map
    gate_map = state.gate_map

    for f_id, fl in flight_map.items():
        g_id = state.assignments.get(f_id)
        if g_id is None:
            total_overflow_cost += config.overflow_weight * 2.0
            continue

        gate = gate_map.get(g_id)
        is_overflow = gate.is_overflow if gate is not None else False

        # Reassignment cost on contact gate
        if not is_overflow:
            if fl.nominal_gate_id is not None and g_id != fl.nominal_gate_id:
                total_reassignment_cost += config.reassignment_weight

        # Overflow penalty (remote apron)
        if is_overflow:
            total_overflow_cost += config.overflow_weight
            if fl.nominal_gate_id is not None:
                total_reassignment_cost += config.reassignment_weight

        # Delay cost (constant per flight)
        if fl.arrival_delay_min > 0:
            total_delay_cost += (fl.arrival_delay_min / 60.0) * config.delay_weight

        # Turnaround slack risk cost (constant per flight)
        stay_duration = fl.simulated_departure_min - fl.predicted_arrival_min
        slack = stay_duration - fl.min_turnaround_min
        if slack < 15:
            total_risk_cost += ((15 - slack) / 15.0) * config.risk_weight

    # Fast conflict detection across contact gates
    total_conflict_cost = 0.0
    for g_id, assigned_flights in state.gate_to_flights.items():
        gate = gate_map.get(g_id)
        if gate is not None and gate.is_overflow:
            continue
        n = len(assigned_flights)
        if n <= 1:
            continue
        sorted_fl = sorted(assigned_flights, key=lambda f: f.time_window.start_min)
        for i in range(n - 1):
            w1 = sorted_fl[i].time_window
            for j in range(i + 1, n):
                w2 = sorted_fl[j].time_window
                if w1.overlaps(w2):
                    total_conflict_cost += config.conflict_weight

    return (
        total_reassignment_cost
        + total_overflow_cost
        + total_delay_cost
        + total_risk_cost
        + total_conflict_cost
    )


def evaluate_state(
    state: SAState,
    config: GateOptimizationConfig,
    *,
    runtime_ms: float = 0.0,
    solver_status: str | None = None,
    solver_name: str = "SimulatedAnnealing",
) -> OptimizationResult:
    """Evaluate an SA state using the authoritative common evaluator.

    Args:
        state: SAState to evaluate.
        config: GateOptimizationConfig.
        runtime_ms: Execution time in milliseconds.
        solver_status: Status string.
        solver_name: Solver identifier.

    Returns:
        OptimizationResult with complete independent diagnostics and breakdown.
    """
    assignments = state.to_gate_assignments()
    return evaluate_gate_assignment(
        assignments=assignments,
        flights=state.flights,
        gates=state.gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status=solver_status,
        solver_name=solver_name,
    )
