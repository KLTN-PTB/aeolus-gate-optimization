"""Unit tests for Greedy Baseline gate assignment."""

import pytest

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.greedy_baseline import GreedyAssignmentResult, greedy_assign


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
    assert isinstance(assign, GreedyAssignmentResult)
    assert assign.status == "OPTIMAL"
    assert assign.solve_time_sec >= 0.0


def test_greedy_assign_failure_capacity_exceeded() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 60)
    f2 = Flight("F2", "ARR", "A320", 110, 0.0, 0.0, 60)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    with pytest.raises(RuntimeError, match="Greedy baseline failed"):
        greedy_assign(instance)


def test_greedy_allow_unassigned_overflow() -> None:
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 60)
    f2 = Flight("F2", "ARR", "A320", 110, 0.0, 0.0, 60)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    result = greedy_assign(instance, allow_unassigned=True)

    assert len(result) == 1
    assert "F1" in result
    assert result.unassigned_flights == ["F2"]
    assert result.status == "FEASIBLE"


def test_greedy_aircraft_compatibility() -> None:
    # G1: WIDEBODY only, G2: ALL
    f_narrow = Flight("F1", "ARR", "NARROWBODY", 100, 0.0, 0.0, 30)
    f_wide = Flight("F2", "ARR", "WIDEBODY", 100, 0.0, 0.0, 30)
    g1 = Gate("G1", compatible_types=["WIDEBODY"])
    g2 = Gate("G2", compatible_types=["ALL"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f_narrow, f_wide], [g1, g2], CostParams())
    result = greedy_assign(instance)

    assert result["F1"] == "G2"  # Narrowbody cannot use G1, must use G2
    assert result["F2"] == "G1"  # Widebody uses G1


def test_greedy_gate_availability_window() -> None:
    # G1 available 0-300, G2 available 300-1440
    f1 = Flight("F1", "ARR", "A320", 100, 0.0, 0.0, 30)  # window ~85-130
    f2 = Flight("F2", "ARR", "A320", 400, 0.0, 0.0, 30)  # window ~385-430
    g1 = Gate("G1", compatible_types=["ALL"], available_from_min=0, available_to_min=300)
    g2 = Gate("G2", compatible_types=["ALL"], available_from_min=300, available_to_min=1440)

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1, g2], CostParams())
    result = greedy_assign(instance)

    assert result["F1"] == "G1"
    assert result["F2"] == "G2"


def test_greedy_min_reassignment_policy() -> None:
    # F1 initially at G1, F2 initially at G2
    # At time 100, F1 arrives, but F2 is delayed and also arrives at 100 -> conflict!
    f1 = Flight("F1", "ARR", "ALL", 100, 0.0, 0.0, 30, current_gate="G1")
    f2 = Flight("F2", "ARR", "ALL", 100, 0.0, 0.0, 30, current_gate="G1")
    g1 = Gate("G1", compatible_types=["ALL"])
    g2 = Gate("G2", compatible_types=["ALL"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1, g2], CostParams())
    result = greedy_assign(instance, policy="min_reassignment")

    assert result["F1"] == "G1"  # F1 kept G1
    assert result["F2"] == "G2"  # F2 reassigned to G2
    assert result.reassigned_count == 1


def test_greedy_contact_first_policy() -> None:
    f1 = Flight("F1", "ARR", "ALL", 100, 0.0, 0.0, 30)
    g_remote = Gate("G_REMOTE", compatible_types=["ALL"], is_contact_gate=False)
    g_contact = Gate("G_CONTACT", compatible_types=["ALL"], is_contact_gate=True)

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1], [g_remote, g_contact], CostParams())
    result = greedy_assign(instance, policy="contact_first")

    assert result["F1"] == "G_CONTACT"
