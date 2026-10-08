"""Integration test for strategy comparison script."""

from src.evaluation.compare_gate_strategies import evaluate_strategies
from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance


def test_evaluate_strategies_pipeline() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.2, 10.0, 30, current_gate="G1")
    f2 = Flight("F2", "ARR", "A320", 200, 0.4, 20.0, 30, current_gate="G2")
    g1 = Gate("G1", compatible_types=["A320"], is_contact_gate=True)
    g2 = Gate("G2", compatible_types=["A320"], is_contact_gate=True)

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1, g2], CostParams())
    results = evaluate_strategies(instance, n_scenarios=20, seed=42)

    assert "Greedy" in results
    assert "CP-SAT" in results
    assert "CP-SAT+SA" in results

    assert results["CP-SAT"]["feasible"] is True
    assert results["CP-SAT+SA"]["feasible"] is True
    assert results["CP-SAT+SA"]["soft_cost"] <= results["CP-SAT"]["soft_cost"] + 1e-6
