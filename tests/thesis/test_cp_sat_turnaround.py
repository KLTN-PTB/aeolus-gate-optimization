"""Unit tests for CP-SAT solver aircraft turnaround time and departure time calculation.

Verifies:
1. Earliest feasible departure calculation: D_min = A_pred + T_turnaround
2. Simulated/predicted departure calculation: D_pred = max(D_sched, D_min)
3. Turnaround delay propagation: dep_delay = max(0, D_pred - D_sched)
4. Turnaround-aware gate occupancy windows and CP-SAT gate allocation
5. GateAssignmentResult 3-tuple unpacking & rich attribute access
6. OOF adapter turnaround column recognition
"""

import pandas as pd
import pytest

from src.optimization.contracts import (
    CostParams,
    Flight,
    Gate,
    GateOptimizationContractViolation,
    ProblemInstance,
)
from src.optimization.cp_sat_solver import (
    GateAssignmentResult,
    calculate_departure_time,
    compute_flight_schedule,
    occupancy_window,
    solve_gate_assignment,
)
from src.optimization.oof_adapter import oof_to_problem_instance


class TestDepartureTimeCalculation:
    """Kiểm tra công thức tính toán thời gian cất cánh dự kiến."""

    def test_standalone_arrival_departure_time(self) -> None:
        """Chuyến bay đến độc lập: cất cánh sau khi hạ cánh và hoàn thành thời gian quay đầu."""
        f_arr = Flight(
            flight_id="FL_ARR_01",
            direction="ARR",
            sched_time_min=480,  # 08:00
            p_delay=1.0,
            delay_est_min=20.0,
            turnaround_time_min=45,
            dwell_time_min=30,
        )
        # A_pred = 480 + 1.0 * 20.0 = 500 (08:20)
        # D_min = 500 + 45 = 545 (09:05)
        # D_pred = D_min = 545
        info = calculate_departure_time(f_arr, turnaround_time_min=45)

        assert info["flight_id"] == "FL_ARR_01"
        assert info["pred_arrival_min"] == 500
        assert info["turnaround_time_min"] == 45
        assert info["earliest_departure_min"] == 545
        assert info["calculated_departure_min"] == 545

    def test_paired_turn_on_time_departure(self) -> None:
        """Cặp chuyến chuỗi xoay vòng hạ cánh đúng giờ -> cất cánh đúng giờ theo lịch."""
        f_in = Flight(
            flight_id="IN_01",
            direction="ARR",
            sched_time_min=360,  # 06:00
            p_delay=0.0,
            delay_est_min=0.0,
            turnaround_time_min=45,
            chain_group_id="CHAIN_1",
        )
        f_out = Flight(
            flight_id="OUT_01",
            direction="DEP",
            sched_time_min=480,  # 08:00
            turnaround_time_min=45,
            chain_group_id="CHAIN_1",
        )
        # A_pred = 360
        # D_min = 360 + 45 = 405
        # D_sched = 480
        # D_pred = max(480, 405) = 480
        info_out = calculate_departure_time(f_out, paired_flight=f_in, turnaround_time_min=45)

        assert info_out["pred_arrival_min"] == 360
        assert info_out["earliest_departure_min"] == 405
        assert info_out["sched_departure_min"] == 480
        assert info_out["calculated_departure_min"] == 480
        assert info_out["departure_delay_min"] == 0.0

    def test_paired_turn_reactionary_delay_propagation(self) -> None:
        """Chuyến đến trễ nặng -> trễ dây chuyền quay đầu khiến chuyến đi cất cánh muộn."""
        f_in = Flight(
            flight_id="IN_LATE",
            direction="ARR",
            sched_time_min=360,  # 06:00
            p_delay=1.0,
            delay_est_min=90.0,  # Hạ cánh lúc 360 + 90 = 450 (07:30)
            turnaround_time_min=45,
            chain_group_id="CHAIN_DELAY",
        )
        f_out = Flight(
            flight_id="OUT_DELAYED",
            direction="DEP",
            sched_time_min=480,  # 08:00
            turnaround_time_min=45,
            chain_group_id="CHAIN_DELAY",
        )
        # A_pred = 450
        # D_min = 450 + 45 = 495 (08:15)
        # D_sched = 480 (08:00)
        # D_pred = max(480, 495) = 495!
        # dep_delay = 495 - 480 = 15 phút
        info_out = calculate_departure_time(f_out, paired_flight=f_in, turnaround_time_min=45)

        assert info_out["pred_arrival_min"] == 450
        assert info_out["earliest_departure_min"] == 495
        assert info_out["sched_departure_min"] == 480
        assert info_out["calculated_departure_min"] == 495
        assert info_out["departure_delay_min"] == 15.0


class TestOccupancyWindowTurnaround:
    """Kiểm tra khoảng thời gian chiếm dụng cổng khi tích hợp thời gian quay đầu."""

    def test_legacy_occupancy_when_turnaround_is_none(self) -> None:
        """Khi không khai báo turnaround time, giữ nguyên kết quả cũ 100%."""
        f = Flight("F1", "ARR", "A320", sched_time_min=500, p_delay=0.5, delay_est_min=20.0, dwell_time_min=40)
        start, end = occupancy_window(f, buffer_time_min=10, mode="expected", turnaround_time_min=None)
        # eff_delay = 0.5 * 20 = 10
        # start = 500 + 10 - 10 = 500
        # end = 500 + 40 = 540
        assert start == 500
        assert end == 540

    def test_turnaround_occupancy_standalone_arrival(self) -> None:
        """Chiếm dụng cổng từ giờ hạ cánh đến giờ cất cánh sau khi quay đầu."""
        f = Flight(
            "F_ARR", "ARR", "A320", sched_time_min=500, p_delay=1.0, delay_est_min=10.0,
            turnaround_time_min=50, dwell_time_min=30,
        )
        # A_pred = 510, D_pred = 510 + 50 = 560
        # buffer = 15
        # start = 510 - 15 = 495
        # end = 560 + 15 = 575
        start, end = occupancy_window(f, buffer_time_min=15, turnaround_time_min=50)
        assert start == 495
        assert end == 575


class TestCpSatWithTurnaround:
    """Kiểm tra bộ giải CP-SAT khi bật tính toán thời gian quay đầu."""

    def test_solve_gate_assignment_with_turnaround(self) -> None:
        f1 = Flight("F1_ARR", "ARR", "ALL", sched_time_min=100, p_delay=0.0, delay_est_min=0.0, turnaround_time_min=40, chain_group_id="ROT_1")
        f2 = Flight("F1_DEP", "DEP", "ALL", sched_time_min=180, p_delay=0.0, delay_est_min=0.0, turnaround_time_min=40, chain_group_id="ROT_1")
        g1 = Gate("G1", ["ALL"])

        instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g1], CostParams(buffer_time_min=10))
        result = solve_gate_assignment(instance, use_turnaround=True)

        # 1. Unpacking 3-tuple tương thích
        assign, status, wall_time = result
        assert status in ("OPTIMAL", "FEASIBLE")
        assert assign["F1_ARR"] == "G1"
        assert assign["F1_DEP"] == "G1"

        # 2. Truy cập thuộc tính phong phú
        assert isinstance(result, GateAssignmentResult)
        assert "F1_ARR" in result.departure_times
        assert "F1_DEP" in result.departure_times
        assert result.departure_times["F1_DEP"] == 180  # Sched 180 >= 100 + 40 = 140

        # 3. Schedule DataFrame
        df_sched = result.schedule_df
        assert len(df_sched) == 2
        f_dep_row = df_sched[df_sched["flight_id"] == "F1_DEP"].iloc[0]
        assert f_dep_row["calculated_departure_min"] == 180
        assert f_dep_row["earliest_departure_min"] == 140

    def test_return_schedule_flag(self) -> None:
        f1 = Flight("F1", "ARR", "ALL", sched_time_min=100, p_delay=0.0, delay_est_min=0.0, turnaround_time_min=30)
        g1 = Gate("G1", ["ALL"])
        instance = ProblemInstance("ATL", "2026-09-20", 1440, [f1], [g1], CostParams(buffer_time_min=5))

        res = solve_gate_assignment(instance, use_turnaround=True, return_schedule=True)
        assert len(res) == 4
        assign, status, wall_time, schedule_df = res
        assert status in ("OPTIMAL", "FEASIBLE")
        assert isinstance(schedule_df, pd.DataFrame)
        assert schedule_df.iloc[0]["calculated_departure_min"] == 130


class TestContractValidation:
    """Kiểm tra ràng buộc hợp lệ đối với turnaround_time_min."""

    def test_invalid_negative_turnaround_raises(self) -> None:
        with pytest.raises(GateOptimizationContractViolation, match="turnaround_time_min must be positive"):
            Flight("F_BAD", "ARR", "ALL", 100, 0.0, 0.0, 30, turnaround_time_min=-10)

    def test_invalid_zero_turnaround_raises(self) -> None:
        with pytest.raises(GateOptimizationContractViolation, match="turnaround_time_min must be positive"):
            Flight("F_ZERO", "ARR", "ALL", 100, 0.0, 0.0, 30, turnaround_time_min=0)

    def test_invalid_cost_params_default_turnaround(self) -> None:
        with pytest.raises(GateOptimizationContractViolation, match="default_turnaround_time_min must be positive"):
            CostParams(default_turnaround_time_min=0)


class TestOofAdapterTurnaroundMapping:
    """Kiểm tra OOF adapter nhận diện đúng các alias của turnaround_time."""

    def test_turnaround_column_extracted(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["FL_001"],
            "p_arr_delay_15": [0.3],
            "predicted_arr_delay_min": [10.0],
            "CRS_DEP_TIME": ["0800"],
            "turnaround_time_min": [55],
        })
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)
        assert instance.flights[0].turnaround_time_min == 55

    def test_turnaround_alias_T_turnaround(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["FL_002"],
            "p_arr_delay_15": [0.4],
            "predicted_arr_delay_min": [15.0],
            "CRS_DEP_TIME": ["0900"],
            "T_turnaround": [50],
        })
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)
        assert instance.flights[0].turnaround_time_min == 50


class TestTurnaroundSessions:
    """Kiểm tra xử lý và giải bài toán với định dạng Turnaround Sessions."""

    def test_dataframe_to_problem_instance_sessions(self) -> None:
        from src.optimization.cp_sat_solver import dataframe_to_problem_instance

        df = pd.DataFrame({
            "session_id": ["TURN_001", "TURN_002"],
            "session_type": ["PAIRED_TURN", "UNMATCHED_ARR"],
            "aircraft_type": ["WIDEBODY", "NARROWBODY"],
            "sched_start_min": [100, 200],
            "sched_end_min": [180, 245],
            "sched_duration_min": [80, 45],
            "turnaround_time_min": [75, 40],
            "p_delay_max": [0.35, 0.20],
            "arr_delay_est_min": [5.0, 2.0],
            "dep_delay_est_min": [4.0, 0.0],
            "chain_group_id": ["CHAIN_01", "CHAIN_02"],
        })

        instance = dataframe_to_problem_instance(df, num_gates=5)
        assert len(instance.flights) == 2
        f1, f2 = instance.flights[0], instance.flights[1]

        assert f1.flight_id == "TURN_001"
        assert f1.direction == "TURN"
        assert f1.aircraft_type == "WIDEBODY"
        assert f1.dwell_time_min == 80
        assert f1.turnaround_time_min == 75

        assert f2.flight_id == "TURN_002"
        assert f2.direction == "ARR"
        assert f2.aircraft_type == "NARROWBODY"

    def test_solve_turnaround_sessions_cpsat(self) -> None:
        from src.optimization.cp_sat_solver import dataframe_to_problem_instance, solve_gate_assignment

        df = pd.DataFrame({
            "session_id": ["TURN_001", "TURN_002"],
            "session_type": ["PAIRED_TURN", "PAIRED_TURN"],
            "aircraft_type": ["NARROWBODY", "NARROWBODY"],
            "sched_start_min": [100, 100],
            "sched_end_min": [180, 180],
            "sched_duration_min": [80, 80],
            "p_delay_max": [0.1, 0.1],
            "arr_delay_est_min": [0.0, 0.0],
        })

        # 2 sessions cùng giờ cần 2 cổng
        instance = dataframe_to_problem_instance(df, num_gates=2)
        assignment, status, _ = solve_gate_assignment(instance)
        assert status == "OPTIMAL"
        assert len(assignment) == 2
        assert assignment["TURN_001"] != assignment["TURN_002"]
