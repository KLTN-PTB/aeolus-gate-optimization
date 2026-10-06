"""Dedicated unit test suite for verifying CP-SAT hard operational constraints.

Tests the following hard constraints enforced by OR-Tools CP-SAT:
1. Single Gate Assignment per Flight (sum(x_{f,g}) == 1)
2. No Overlap of Occupancy Windows at any Gate (AddNoOverlap + buffer time)
3. Gate Availability Timeframe Limits ([available_from_min, available_to_min])
4. Flight Chain Rotation Coupling (flights sharing chain_group_id assigned to same gate)
5. Specific Aircraft-Gate Compatibility Filtering
6. Infeasibility Detection & Exception Handling
"""

from __future__ import annotations

import pytest

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window, solve_gate_assignment


def test_hard_constraint_exactly_one_gate_per_flight() -> None:
    """Verify every flight receives exactly one valid gate assignment."""
    flights = [
        Flight(f"F{i}", "ARR", "A320", 100 + i * 40, 0.1, 5.0, 30)
        for i in range(10)
    ]
    gates = [Gate("G1", ["A320"]), Gate("G2", ["A320"]), Gate("G3", ["A320"])]
    instance = ProblemInstance("ATL", "2026-09-20", 1440, flights, gates, CostParams())

    assignment, status, _ = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    assert len(assignment) == 10
    for f in flights:
        assert f.flight_id in assignment
        assert assignment[f.flight_id] in ["G1", "G2", "G3"]


def test_hard_constraint_no_time_overlap_per_gate() -> None:
    """Verify no two flights assigned to the same gate overlap in time (with buffer time)."""
    # 15 flights distributed over time so 5 gates are feasible
    flights = [
        Flight(f"FL_{i}", "ARR", "ALL", 300 + i * 30, 0.4, 15.0, 35)
        for i in range(15)
    ]
    gates = [Gate(f"G{j}", ["ALL"]) for j in range(1, 6)]
    instance = ProblemInstance("ATL", "2026-09-20", 1440, flights, gates, CostParams(buffer_time_min=15))

    assignment, status, _ = solve_gate_assignment(instance)
    assert status in ("OPTIMAL", "FEASIBLE")


    # Group occupancy intervals by assigned gate
    gate_intervals: dict[str, list[tuple[int, int, str]]] = {g.gate_id: [] for g in gates}
    for f in flights:
        g_id = assignment[f.flight_id]
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min, mode="expected")
        gate_intervals[g_id].append((start_i, end_i, f.flight_id))

    # Assert pairwise non-overlap for every gate
    for g_id, intervals in gate_intervals.items():
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        for idx in range(len(sorted_intervals) - 1):
            s1, e1, f1_id = sorted_intervals[idx]
            s2, e2, f2_id = sorted_intervals[idx + 1]
            assert e1 <= s2, (
                f"Hard constraint violation on gate {g_id}: flight {f1_id} [{s1}, {e1}] "
                f"overlaps with flight {f2_id} [{s2}, {e2}]"
            )


def test_hard_constraint_gate_availability_window() -> None:
    """Verify flights are never assigned to gates outside the gate availability window."""
    # Flight operates from 500 to 560
    f1 = Flight("F_WINDOW", "ARR", "ALL", 500, 0.0, 0.0, 60)

    # G1 available [0, 400] (Too early)
    g1 = Gate("G1_EARLY", ["ALL"], available_from_min=0, available_to_min=400)
    # G2 available [450, 700] (Covers [500, 560])
    g2 = Gate("G2_VALID", ["ALL"], available_from_min=450, available_to_min=700)
    # G3 available [600, 1000] (Too late)
    g3 = Gate("G3_LATE", ["ALL"], available_from_min=600, available_to_min=1000)

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1], [g1, g2, g3], CostParams(buffer_time_min=0))
    assignment, status, _ = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    assert assignment["F_WINDOW"] == "G2_VALID"


def test_hard_constraint_flight_chain_coupling() -> None:
    """Verify paired flights sharing chain_group_id are strictly assigned to the SAME gate."""
    # Pair 1 (ROT_01)
    f1 = Flight("ARR_01", "ARR", "ALL", 100, 0.0, 0.0, 40, chain_group_id="ROT_01")
    f2 = Flight("DEP_01", "DEP", "ALL", 160, 0.0, 0.0, 40, chain_group_id="ROT_01")

    # Pair 2 (ROT_02)
    f3 = Flight("ARR_02", "ARR", "ALL", 200, 0.0, 0.0, 40, chain_group_id="ROT_02")
    f4 = Flight("DEP_02", "DEP", "ALL", 260, 0.0, 0.0, 40, chain_group_id="ROT_02")

    gates = [Gate("G1", ["ALL"]), Gate("G2", ["ALL"])]
    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2, f3, f4], gates, CostParams(buffer_time_min=10))

    assignment, status, _ = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    # Both flights in ROT_01 must be on the same gate
    assert assignment["ARR_01"] == assignment["DEP_01"]
    # Both flights in ROT_02 must be on the same gate
    assert assignment["ARR_02"] == assignment["DEP_02"]


def test_hard_constraint_specific_aircraft_compatibility() -> None:
    """Verify aircraft compatibility restriction when explicit non-ALL types are given."""
    f_wide = Flight("F_WIDE", "ARR", "B777", 100, 0.0, 0.0, 30)
    f_narrow = Flight("F_NARROW", "ARR", "A320", 100, 0.0, 0.0, 30)

    g_narrow_only = Gate("G_NARROW", ["A320", "B738"])
    g_wide_only = Gate("G_WIDE", ["B777", "A350"])

    instance = ProblemInstance(
        "ATL", "2026-09-20", 1440, [f_wide, f_narrow], [g_narrow_only, g_wide_only], CostParams()
    )

    assignment, status, _ = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    assert assignment["F_WIDE"] == "G_WIDE"
    assert assignment["F_NARROW"] == "G_NARROW"


def test_hard_constraint_infeasibility_detection_time_overlap() -> None:
    """Verify CP-SAT correctly fails closed (raises RuntimeError) when time overlaps are unresolvable."""
    # 3 flights overlapping at the same time: [100..160], [110..170], [120..180]
    f1 = Flight("F1", "ARR", "ALL", 100, 0.0, 0.0, 60)
    f2 = Flight("F2", "ARR", "ALL", 110, 0.0, 0.0, 60)
    f3 = Flight("F3", "ARR", "ALL", 120, 0.0, 0.0, 60)

    # Only 2 gates available -> 3 overlapping flights CANNOT fit
    gates = [Gate("G1", ["ALL"]), Gate("G2", ["ALL"])]
    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2, f3], gates, CostParams(buffer_time_min=0))

    with pytest.raises(RuntimeError, match="CP-SAT solution not feasible"):
        solve_gate_assignment(instance)
