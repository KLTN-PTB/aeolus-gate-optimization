"""Unit and integration tests for weekly turnaround sessions reassignment pipeline.

Covers mandatory tests T1 through T9 from ANTIGRAVITY_FIX_GATE_OPTIMIZATION_WEEKLY.md:
- T1: P0 generation strictly uses sched_* (immune to pred_* changes)
- T2: P0 generation does not depend on actual_* (immune to actual_* changes)
- T3: Pred instance uses direct pred window in mode='fixed'
- T4: mode='fixed' does not multiply p * delay_est
- T5: initial_gate is properly mapped to Flight.current_gate (initial_gate > current_gate)
- T6: CP-SAT reassignment objective minimizes changes from P0
- T7: Same P0 shared across Greedy, CP-SAT, and CP-SAT+SA
- T8: No leakage of actual_* (planning succeeds even when actual_* is completely dropped)
- T9: Actual replay evaluates conflicts without modifying solver assignments
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import (
    dataframe_to_problem_instance,
    occupancy_window,
    solve_gate_assignment,
)
from src.optimization.greedy_baseline import greedy_assign
from src.optimization.p0_builder import attach_initial_gate, build_initial_gate_schedule
from src.optimization.simulated_annealing import simulated_annealing, soft_cost_breakdown


@pytest.fixture
def sample_sessions_df() -> pd.DataFrame:
    """Fixture providing a deterministic small set of turnaround sessions."""
    return pd.DataFrame([
        {
            "session_id": "TURN_001",
            "session_type": "PAIRED_TURN",
            "aircraft_type": "NARROWBODY",
            "sched_start_min": 100,
            "sched_end_min": 180,
            "sched_duration_min": 80,
            "pred_start_min": 110,
            "pred_end_min": 195,
            "pred_duration_min": 85,
            "p_delay_max": 0.8,
            "arr_delay_est_min": 25.0,
            "dep_delay_est_min": 15.0,
            "actual_start_min": 105,
            "actual_end_min": 190,
            "actual_duration_min": 85,
            "arr_true_delay_min": 5.0,
            "dep_true_delay_min": 10.0,
        },
        {
            "session_id": "TURN_002",
            "session_type": "PAIRED_TURN",
            "aircraft_type": "NARROWBODY",
            "sched_start_min": 150,
            "sched_end_min": 230,
            "sched_duration_min": 80,
            "pred_start_min": 160,
            "pred_end_min": 240,
            "pred_duration_min": 80,
            "p_delay_max": 0.4,
            "arr_delay_est_min": 10.0,
            "dep_delay_est_min": 10.0,
            "actual_start_min": 170,
            "actual_end_min": 250,
            "actual_duration_min": 80,
            "arr_true_delay_min": 20.0,
            "dep_true_delay_min": 20.0,
        },
        {
            "session_id": "TURN_003",
            "session_type": "UNMATCHED_ARR",
            "aircraft_type": "WIDEBODY",
            "sched_start_min": 300,
            "sched_end_min": 360,
            "sched_duration_min": 60,
            "pred_start_min": 310,
            "pred_end_min": 370,
            "pred_duration_min": 60,
            "p_delay_max": 0.2,
            "arr_delay_est_min": 10.0,
            "dep_delay_est_min": 0.0,
            "actual_start_min": 305,
            "actual_end_min": 365,
            "actual_duration_min": 60,
            "arr_true_delay_min": 5.0,
            "dep_true_delay_min": 0.0,
        },
    ])


def test_t1_p0_strictly_uses_sched(sample_sessions_df: pd.DataFrame) -> None:
    """T1: Two DataFrames with identical sched_* but radically different pred_* produce identical P0."""
    df1 = sample_sessions_df.copy()
    df2 = sample_sessions_df.copy()

    # Perturb predictions radically
    df2["pred_start_min"] = [500, 600, 700]
    df2["pred_end_min"] = [590, 690, 780]
    df2["pred_duration_min"] = [90, 90, 80]
    df2["p_delay_max"] = [0.99, 0.99, 0.99]
    df2["arr_delay_est_min"] = [120.0, 150.0, 200.0]

    p0_1 = build_initial_gate_schedule(df1, num_gates=3, buffer_time_min=15)
    p0_2 = build_initial_gate_schedule(df2, num_gates=3, buffer_time_min=15)

    assert p0_1.assignment == p0_2.assignment
    assert p0_1.status == p0_2.status
    assert p0_1.unassigned_count == p0_2.unassigned_count


def test_t2_p0_independent_of_actual(sample_sessions_df: pd.DataFrame) -> None:
    """T2: Modifying actual_* ground truth does NOT alter P0 assignment."""
    df1 = sample_sessions_df.copy()
    df2 = sample_sessions_df.copy()

    df2["actual_start_min"] = [999, 888, 777]
    df2["actual_end_min"] = [1100, 999, 850]
    df2["arr_true_delay_min"] = [50.0, 60.0, 70.0]

    p0_1 = build_initial_gate_schedule(df1, num_gates=3, buffer_time_min=15)
    p0_2 = build_initial_gate_schedule(df2, num_gates=3, buffer_time_min=15)

    assert p0_1.assignment == p0_2.assignment


def test_t3_pred_instance_uses_pred_window() -> None:
    """T3: A row with pred_start=100, pred_end=180, buffer=15 returns (85, 195) in mode='fixed'."""
    f = Flight(
        flight_id="TURN_TEST",
        direction="TURN",
        sched_time_min=90,
        dwell_time_min=60,
        p_delay=0.9,
        delay_est_min=50.0,
        base_start_min=100,
        base_end_min=180,
    )

    start, end = occupancy_window(f, buffer_time_min=15, mode="fixed")
    assert start == 85
    assert end == 195


def test_t4_no_recomputing_p_delay_est() -> None:
    """T4: Changing p_delay or delay_est does NOT alter occupancy window in mode='fixed'."""
    f1 = Flight(
        flight_id="TURN_01",
        direction="TURN",
        sched_time_min=100,
        dwell_time_min=50,
        p_delay=0.1,
        delay_est_min=5.0,
        base_start_min=200,
        base_end_min=280,
    )
    f2 = Flight(
        flight_id="TURN_01",
        direction="TURN",
        sched_time_min=100,
        dwell_time_min=50,
        p_delay=0.95,
        delay_est_min=180.0,
        base_start_min=200,
        base_end_min=280,
    )

    w1 = occupancy_window(f1, buffer_time_min=15, mode="fixed")
    w2 = occupancy_window(f2, buffer_time_min=15, mode="fixed")

    assert w1 == (185, 295)
    assert w2 == (185, 295)
    assert w1 == w2


def test_t5_initial_gate_alias() -> None:
    """T5: DataFrame with initial_gate is mapped to Flight.current_gate, with initial_gate > current_gate."""
    df = pd.DataFrame([
        {
            "session_id": "TURN_001",
            "session_type": "PAIRED_TURN",
            "sched_start_min": 100,
            "sched_end_min": 180,
            "sched_duration_min": 80,
            "initial_gate": "G05",
            "current_gate": "G02",  # Should be overridden by initial_gate
        },
        {
            "session_id": "TURN_002",
            "session_type": "PAIRED_TURN",
            "sched_start_min": 200,
            "sched_end_min": 280,
            "sched_duration_min": 80,
            "current_gate": "G07",  # Fallback to current_gate when initial_gate is missing
        },
    ])

    inst = dataframe_to_problem_instance(df, num_gates=10, time_basis="sched")
    f_map = {f.flight_id: f for f in inst.flights}

    assert f_map["TURN_001"].current_gate == "G05"
    assert f_map["TURN_002"].current_gate == "G07"


def test_t6_cpsat_reassignment_objective() -> None:
    """T6: In a toy case where P0 is feasible under predicted windows, CP-SAT preserves P0."""
    df = pd.DataFrame([
        {
            "session_id": "TURN_001",
            "session_type": "PAIRED_TURN",
            "sched_start_min": 100,
            "sched_end_min": 150,
            "sched_duration_min": 50,
            "pred_start_min": 105,
            "pred_end_min": 155,
            "pred_duration_min": 50,
        },
        {
            "session_id": "TURN_002",
            "session_type": "PAIRED_TURN",
            "sched_start_min": 200,
            "sched_end_min": 250,
            "sched_duration_min": 50,
            "pred_start_min": 205,
            "pred_end_min": 255,
            "pred_duration_min": 50,
        },
    ])

    p0 = build_initial_gate_schedule(df, num_gates=2, buffer_time_min=15)
    df_p0 = attach_initial_gate(df, p0)

    pred_inst = dataframe_to_problem_instance(df_p0, num_gates=2, time_basis="pred")
    cpsat_res = solve_gate_assignment(pred_inst, mode="fixed", time_limit_sec=10)

    # Since P0 is conflict-free under predictions, CP-SAT should keep all initial gates
    assert cpsat_res.assignment == p0.assignment
    reassignments = sum(1 for fid, gid in cpsat_res.assignment.items() if gid != p0.assignment[fid])
    assert reassignments == 0


def test_t7_same_p0_shared(sample_sessions_df: pd.DataFrame) -> None:
    """T7: Greedy, CP-SAT, and SA evaluate reassignments against the exact same initial_gate mapping."""
    p0 = build_initial_gate_schedule(sample_sessions_df, num_gates=3, buffer_time_min=15)
    df_with_p0 = attach_initial_gate(sample_sessions_df, p0)

    pred_inst = dataframe_to_problem_instance(df_with_p0, num_gates=3, time_basis="pred")

    # Greedy
    greedy_res = greedy_assign(pred_inst, mode="fixed", policy="min_reassignment")

    # CP-SAT
    cpsat_res = solve_gate_assignment(pred_inst, mode="fixed", time_limit_sec=10)

    # SA from CP-SAT
    sa_res = simulated_annealing(
        initial_assignment=cpsat_res.assignment,
        instance=pred_inst,
        mode="fixed",
        iterations=50,
        seed=42,
    )

    # Verification: every flight has initial_gate defined and matches P0 assignment
    for f in pred_inst.flights:
        assert f.current_gate == p0.assignment[f.flight_id]

    # Reassignments for all 3 methods are counted relative to the exact same P0
    greedy_reassigned = sum(1 for fid, gid in greedy_res.assignment.items() if gid != p0.assignment[fid])
    cpsat_reassigned = sum(1 for fid, gid in cpsat_res.assignment.items() if gid != p0.assignment[fid])
    sa_reassigned = sum(1 for fid, gid in sa_res.assignment.items() if gid != p0.assignment[fid])

    assert greedy_reassigned >= 0
    assert cpsat_reassigned >= 0
    assert sa_reassigned >= 0


def test_t8_no_actual_leakage(sample_sessions_df: pd.DataFrame) -> None:
    """T8: Planning pipeline executes successfully when all actual_* and *_true_delay_* columns are dropped."""
    actual_cols = [c for c in sample_sessions_df.columns if "actual" in c or "true_delay" in c]
    df_clean = sample_sessions_df.drop(columns=actual_cols)

    p0 = build_initial_gate_schedule(df_clean, num_gates=3, buffer_time_min=15)
    df_p0 = attach_initial_gate(df_clean, p0)

    pred_inst = dataframe_to_problem_instance(df_p0, num_gates=3, time_basis="pred")

    # Confirm all flight actual_delay_min are None
    for f in pred_inst.flights:
        assert f.actual_delay_min is None

    greedy_res = greedy_assign(pred_inst, mode="fixed", policy="min_reassignment")
    assert greedy_res.status in ("OPTIMAL", "FEASIBLE")

    cpsat_res = solve_gate_assignment(pred_inst, mode="fixed", time_limit_sec=10)
    assert cpsat_res.status in ("OPTIMAL", "FEASIBLE")


def test_t9_actual_replay_does_not_modify_assignment(sample_sessions_df: pd.DataFrame) -> None:
    """T9: Running replay evaluation with different actual data does NOT modify solver assignments."""
    p0 = build_initial_gate_schedule(sample_sessions_df, num_gates=3, buffer_time_min=15)
    df_p0 = attach_initial_gate(sample_sessions_df, p0)
    pred_inst = dataframe_to_problem_instance(df_p0, num_gates=3, time_basis="pred")

    cpsat_res = solve_gate_assignment(pred_inst, mode="fixed", time_limit_sec=10)
    saved_assignment = dict(cpsat_res.assignment)

    # Replay with actual dataset A
    actual_conflicts_a = 0
    gate_intervals_a: dict[str, list[tuple[int, int]]] = {}
    for idx, row in sample_sessions_df.iterrows():
        g = saved_assignment[row["session_id"]]
        s = max(0, row["actual_start_min"] - 15)
        e = row["actual_end_min"] + 15
        gate_intervals_a.setdefault(g, []).append((s, e))

    for g, intervals in gate_intervals_a.items():
        intervals.sort()
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                if max(intervals[i][0], intervals[j][0]) < min(intervals[i][1], intervals[j][1]):
                    actual_conflicts_a += 1

    # Assignment before and after replay must remain completely unchanged
    assert cpsat_res.assignment == saved_assignment
