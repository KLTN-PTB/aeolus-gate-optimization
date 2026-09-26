"""Unit tests for Greedy Baseline gate assignment."""

import pytest

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.greedy_baseline import greedy_assign


def test_greedy_assign_success() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 30)
    f2 = Flight("F2", "ARR", "A320", 110, 0.0, 0.0, 30)
    g1 = Gate("G1", compatible_types=["A320"])
    g2 = Gate("G2", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1, g2], CostParams())
    assign = greedy_assign(instance)

    assert len(assign) == 2
    assert assign["F1"] in ("G1", "G2")
    assert assign["F2"] in ("G1", "G2")
    assert assign["F1"] != assign["F2"]


def test_greedy_assign_failure_capacity_exceeded() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 60)
    f2 = Flight("F2", "ARR", "A320", 110, 0.0, 0.0, 60)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    with pytest.raises(RuntimeError, match="Greedy baseline failed"):
        greedy_assign(instance)
