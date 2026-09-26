"""Unit tests for CP-SAT gate assignment solver."""

import pytest

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window, solve_gate_assignment


def test_occupancy_window_calculation() -> None:
    flight = Flight(
        flight_id="F1",
        direction="ARR",
        aircraft_type="A320",
        sched_time_min=600,
        p_delay=0.5,
        delay_est_min=30.0,
        dwell_time_min=45,
    )
    # expected eff_delay = 0.5 * 30.0 = 15.0
    # start = 600 + 15 - 15 = 600
    # end = 600 + 45 = 645
    start, end = occupancy_window(flight, buffer_time_min=15, mode="expected")
    assert start == 600
    assert end == 645


def test_cp_sat_non_overlapping_case() -> None:
    # 1 gate, 2 non-overlapping flights
    f1 = Flight("F1", "ARR", "A320", sched_time_min=100, p_delay=0.0, delay_est_min=0.0, dwell_time_min=30)
    f2 = Flight("F2", "ARR", "A320", sched_time_min=200, p_delay=0.0, delay_est_min=0.0, dwell_time_min=30)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    assignment, status, wall_time = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    assert assignment["F1"] == "G1"
    assert assignment["F2"] == "G1"


def test_cp_sat_overlapping_infeasible_case() -> None:
    # 1 gate, 2 overlapping flights -> must raise RuntimeError infeasible
    f1 = Flight("F1", "ARR", "A320", sched_time_min=100, p_delay=0.0, delay_est_min=0.0, dwell_time_min=60)
    f2 = Flight("F2", "ARR", "A320", sched_time_min=120, p_delay=0.0, delay_est_min=0.0, dwell_time_min=60)
    g1 = Gate("G1", compatible_types=["A320"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams())
    with pytest.raises(RuntimeError, match="CP-SAT solution not feasible"):
        solve_gate_assignment(instance)


def test_cp_sat_aircraft_compatibility() -> None:
    # 2 gates: G1 (A320 only), G2 (WIDEBODY only); F1 is WIDEBODY -> must get G2
    f1 = Flight("F1", "ARR", "WIDEBODY", sched_time_min=100, p_delay=0.0, delay_est_min=0.0, dwell_time_min=30)
    g1 = Gate("G1", compatible_types=["A320"])
    g2 = Gate("G2", compatible_types=["WIDEBODY"])

    instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1], [g1, g2], CostParams())
    assignment, status, _ = solve_gate_assignment(instance)

    assert status in ("OPTIMAL", "FEASIBLE")
    assert assignment["F1"] == "G2"
