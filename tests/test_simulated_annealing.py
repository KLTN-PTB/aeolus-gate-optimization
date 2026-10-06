"""Unit tests for Simulated Annealing gate optimizer."""

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import solve_gate_assignment
from src.optimization.simulated_annealing import is_feasible, simulated_annealing, soft_cost


def test_simulated_annealing_cost_non_increasing() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.2, 10.0, 30, current_gate="G02")
    f2 = Flight("F2", "ARR", "A320", 200, 0.5, 30.0, 30, current_gate="G01")
    g1 = Gate("G01", compatible_types=["A320"], is_contact_gate=True)
    g2 = Gate("G02", compatible_types=["A320"], is_contact_gate=False)

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1, g2], CostParams())
    cpsat_assign, _, _ = solve_gate_assignment(instance)

    assert is_feasible(cpsat_assign, instance)
    weights = (1.0, 1.0, 0.5, 1.0)
    init_cost = soft_cost(cpsat_assign, instance, weights)

    sa_assign, sa_cost = simulated_annealing(
        cpsat_assign,
        instance,
        weights=weights,
        iterations=500,
        seed=42,
    )

    assert is_feasible(sa_assign, instance)
    assert sa_cost <= init_cost + 1e-6
