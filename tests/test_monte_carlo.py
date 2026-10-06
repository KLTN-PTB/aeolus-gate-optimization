"""Unit tests for Monte Carlo robustness simulation."""

import random
from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.simulation.monte_carlo import count_conflicts, run_monte_carlo, sample_realized_delay


def test_sample_realized_delay_synthetic() -> None:
    f = Flight("F1", "ARR", "A320", 100, p_delay=1.0, delay_est_min=30.0, dwell_time_min=30)
    rng = random.Random(42)
    sample = sample_realized_delay(f, rng)
    assert sample >= 15.0


def test_count_conflicts_detection() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 60)
    f2 = Flight("F2", "ARR", "A320", 120, 0.0, 0.0, 60)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    assignment = {"F1": "G1", "F2": "G1"}
    realized_delays = {"F1": 0.0, "F2": 0.0}

    conflicts = count_conflicts(instance, assignment, realized_delays)
    assert conflicts == 1


def test_run_monte_carlo_reproducibility() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.5, 20.0, 30)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1], [g1], CostParams())
    res1 = run_monte_carlo(instance, {"F1": "G1"}, n_scenarios=20, seed=123)
    res2 = run_monte_carlo(instance, {"F1": "G1"}, n_scenarios=20, seed=123)

    assert len(res1) == 20
    assert [r["conflicts"] for r in res1] == [r["conflicts"] for r in res2]
