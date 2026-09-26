"""CP-SAT Gate Assignment Solver using Google OR-Tools.

Formulates and solves the exact gate assignment problem with hard operational constraints:
- Gate availability windows
- Single gate assignment per flight
- No time overlap per gate (using NewOptionalIntervalVar and AddNoOverlap)
- Turn coupling via chain_group_id
(Đã bỏ qua ràng buộc kích thước thân máy bay - mọi tàu bay đều đỗ được ở mọi cổng)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

import pandas as pd
from ortools.sat.python import cp_model

from src.optimization.contracts import CostParams, CostParameters, Flight, Gate, ProblemInstance

logger = logging.getLogger(__name__)


def occupancy_window(
    flight: Flight,
    buffer_time_min: int,
    mode: str = "expected",
    realized_delay: Optional[float] = None,
) -> tuple[int, int]:
    """Calculate the occupancy interval (start, end) in minutes for a flight."""
    if mode == "expected":
        eff_delay = flight.p_delay * flight.delay_est_min
    elif mode == "worst_case":
        eff_delay = flight.delay_est_min
    elif mode == "realized":
        eff_delay = realized_delay if realized_delay is not None else 0.0
    else:
        raise ValueError(f"Unknown occupancy mode: {mode!r}")

    start = int(flight.sched_time_min + eff_delay - buffer_time_min)
    end = start + flight.dwell_time_min
    start_clamped = max(0, start)
    end_clamped = max(start_clamped + 1, end)
    return start_clamped, end_clamped


def solve_gate_assignment(
    instance: ProblemInstance,
    time_limit_sec: int = 60,
    mode: str = "expected",
    num_workers: int = 8,
) -> tuple[dict[str, str], str, float]:
    """Solve the gate assignment problem using CP-SAT."""
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.BoolVar] = {}
    y: dict[str, cp_model.BoolVar] = {}
    intervals_by_gate: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    # Nhóm các chuyến bay thuộc cùng chuỗi xoay vòng tàu bay
    chain_pairs: dict[str, list[Flight]] = defaultdict(list)
    for f in instance.flights:
        if f.chain_group_id:
            chain_pairs[f.chain_group_id].append(f)

    for f in instance.flights:
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min, mode)
        assigned_vars: list[cp_model.BoolVar] = []

        for g in instance.gates:
            var = model.NewBoolVar(f"x_{f.flight_id}_{g.gate_id}")
            x[f.flight_id, g.gate_id] = var
            assigned_vars.append(var)

            # RÀNG BUỘC THÂN MÁY BAY (Bỏ qua nếu aircraft_type="ALL" hoặc gate.compatible_types chứa "ALL")
            gate_types = [t.upper() for t in g.compatible_types] if g.compatible_types else ["ALL"]
            f_type = f.aircraft_type.upper() if f.aircraft_type else "ALL"
            if "ALL" not in gate_types and f_type != "ALL" and f_type not in gate_types:
                model.Add(var == 0)
                continue


            # Ràng buộc khung giờ hoạt động của cổng
            if start_i < g.available_from_min or end_i > g.available_to_min:
                model.Add(var == 0)
                continue

            # Biến khoảng thời gian chiếm dụng cổng tùy chọn
            duration = end_i - start_i
            interval = model.NewOptionalIntervalVar(
                start_i, duration, end_i, var, f"iv_{f.flight_id}_{g.gate_id}"
            )
            intervals_by_gate[g.gate_id].append(interval)

        # Ràng buộc cứng: Mỗi chuyến bay chỉ gán vào đúng 1 cổng
        model.Add(sum(assigned_vars) == 1)

        # Biến đánh dấu tái phân bổ cổng (phục vụ hàm mục tiêu)
        if f.current_gate is not None:
            yv = model.NewBoolVar(f"y_{f.flight_id}")
            y[f.flight_id] = yv
            key = (f.flight_id, f.current_gate)
            if key in x:
                model.Add(yv == 1 - x[key])
            else:
                model.Add(yv == 1)

    # Ràng buộc cứng: Không chồng chéo thời gian tại cùng một cổng
    for gate_id, intervals in intervals_by_gate.items():
        model.AddNoOverlap(intervals)

    # Ràng buộc chuỗi xoay vòng tàu bay (Flight Chain: cùng chain_group_id phải dùng chung cổng)
    for chain_id, flights in chain_pairs.items():
        if len(flights) == 2:
            f1, f2 = flights[0], flights[1]
            for g in instance.gates:
                if (f1.flight_id, g.gate_id) in x and (f2.flight_id, g.gate_id) in x:
                    model.Add(x[f1.flight_id, g.gate_id] == x[f2.flight_id, g.gate_id])

    # Hàm mục tiêu: Tối thiểu hóa số chuyến bay phải đổi cổng so với lịch cũ
    if y:
        model.Minimize(sum(y.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_sec)
    solver.parameters.num_search_workers = num_workers
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    wall_time = solver.WallTime()

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.error("CP-SAT solver failed: status=%s, wall_time=%.2fs", status_name, wall_time)
        raise RuntimeError(f"CP-SAT solution not feasible: status={status_name}")

    assignment: dict[str, str] = {}
    for f in instance.flights:
        assigned_gate = None
        for g in instance.gates:
            if solver.Value(x[f.flight_id, g.gate_id]) == 1:
                assigned_gate = g.gate_id
                break
        if assigned_gate is None:
            raise RuntimeError(f"Flight {f.flight_id} was not assigned any gate by CP-SAT")
        assignment[f.flight_id] = assigned_gate

    logger.info(
        "CP-SAT solved successfully: status=%s, assigned_flights=%d, wall_time=%.2fs",
        status_name,
        len(assignment),
        wall_time,
    )
    return assignment, status_name, wall_time


def dataframe_to_problem_instance(
    df: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    default_dwell_time_min: int = 45,
) -> ProblemInstance:
    """Chuyển đổi DataFrame kết quả mô hình (hoặc Parquet OOF) sang ProblemInstance.

    Hỗ trợ tự động ánh xạ các cột:
    - ID chuyến bay: flight_id hoặc flight_key
    - Xác suất trễ: p_delay, prob_delay, hoặc p_arr_delay_15 (từ OOF ML Classifier)
    - Số phút trễ ước tính: delay_est_min, pred_arr_delay, hoặc predicted_arr_delay_min (từ OOF ML Regressor)
    - Giờ lịch trình: sched_time_min, crs_arr_time, hoặc CRS_DEP_TIME
    - Chuỗi xoay vòng tàu bay: chain_group_id hoặc chain_id
    """
    flights: list[Flight] = []
    for idx, row in df.iterrows():
        f_id = str(row.get("flight_id", row.get("flight_key", f"FL_{idx:04d}")))
        sched_time = int(row.get("sched_time_min", row.get("crs_arr_time", row.get("CRS_DEP_TIME", 0))))
        dwell_time = int(row.get("dwell_time_min", row.get("CRS_ELAPSED_TIME", default_dwell_time_min)))
        delay_est = float(row.get("delay_est_min", row.get("predicted_arr_delay_min", row.get("pred_arr_delay", 0.0))))
        prob_delay = float(row.get("p_delay", row.get("p_arr_delay_15", row.get("prob_delay", 0.0))))

        cur_gate = row.get("current_gate")
        current_gate_str = str(cur_gate) if pd.notna(cur_gate) else None

        chain_id_val = row.get("chain_group_id", row.get("chain_id"))
        chain_group_id_str = str(chain_id_val) if pd.notna(chain_id_val) else None

        f = Flight(
            flight_id=f_id,
            direction=str(row.get("direction", "ARR")),
            sched_time_min=sched_time,
            dwell_time_min=dwell_time,
            delay_est_min=delay_est,
            p_delay=prob_delay,
            aircraft_type="ALL",  # Mặc định ALL - Không phân biệt kích thước máy bay
            current_gate=current_gate_str,
            chain_group_id=chain_group_id_str,
        )
        flights.append(f)

    gates: list[Gate] = []
    for j in range(1, num_gates + 1):
        g = Gate(
            gate_id=f"G{j:02d}",
            compatible_types=["ALL"],  # Mọi cổng chấp nhận mọi máy bay
            available_from_min=0,
            available_to_min=1440 * 2,
        )
        gates.append(g)

    cost_params = CostParams(buffer_time_min=buffer_time_min)
    return ProblemInstance(flights=flights, gates=gates, cost_params=cost_params)



def solve_from_dataframe(
    df: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    mode: str = "expected",
    time_limit_sec: int = 60,
) -> tuple[dict[str, str], str, float]:
    instance = dataframe_to_problem_instance(
        df=df,
        num_gates=num_gates,
        buffer_time_min=buffer_time_min,
    )
    return solve_gate_assignment(instance=instance, time_limit_sec=time_limit_sec, mode=mode)


# =====================================================================
# KHỐI THỬ NGHIỆM TRỰC TIẾP (DIRECT EXECUTION TEST BLOCK)
# =====================================================================
if __name__ == "__main__":
    # Sample DataFrame simulating Machine Learning model prediction outputs (Dual Prediction)
    sample_ml_predictions = pd.DataFrame({
        "flight_key": [
            "FL_ATL_01", "FL_ATL_02", "FL_ATL_03", "FL_ATL_04", "FL_ATL_05",
            "FL_ATL_06", "FL_ATL_07", "FL_ATL_08", "FL_ATL_09", "FL_ATL_10",
            "FL_ATL_11", "FL_ATL_12", "FL_ATL_13", "FL_ATL_14", "FL_ATL_15",
            "FL_ATL_16", "FL_ATL_17", "FL_ATL_18"
        ],
        "CRS_DEP_TIME": [
            360, 390, 420, 450, 480,
            510, 540, 570, 600, 630,
            660, 690, 720, 750, 780,
            810, 840, 870
        ],
        "CRS_ELAPSED_TIME": [
            45, 50, 40, 60, 45,
            35, 50, 40, 55, 40,
            45, 50, 40, 60, 45,
            35, 50, 40
        ],
        "p_arr_delay_15": [
            0.85, 0.20, 0.10, 0.95, 0.60,
            0.15, 0.75, 0.05, 0.80, 0.30,
            0.90, 0.10, 0.65, 0.25, 0.70,
            0.08, 0.85, 0.40
        ],
        "predicted_arr_delay_min": [
            25.0, 0.0, -5.0, 35.0, 15.0,
            0.0, 20.0, -8.0, 30.0, 5.0,
            40.0, 0.0, 18.0, 2.0, 22.0,
            -2.0, 32.0, 10.0
        ],
        "current_gate": [
            "G01", "G02", "G03", "G04", "G05",
            "G01", "G02", "G03", "G04", "G05",
            "G01", "G02", "G03", "G04", "G05",
            "G01", "G02", "G03"
        ],
        "chain_id": [
            "ROT_ALPHA", None, None, "ROT_BETA", "ROT_ALPHA",
            None, None, "ROT_GAMMA", None, None,
            None, "ROT_GAMMA", None, "ROT_BETA", None,
            "ROT_DELTA", None, "ROT_DELTA"
        ]
    })

    print("=========================================================================")
    print("      AEOLUS GATE OPTIMIZATION - DIRECT CP-SAT SOLVER TEST RUN          ")
    print("=========================================================================")
    print(f"Total flights in schedule: {len(sample_ml_predictions)}")
    print(f"Prediction model columns: p_arr_delay_15 (Classification), predicted_arr_delay_min (Regression)")
    print("-------------------------------------------------------------------------")

    # --- TEST SCENARIO 1: EXPECTED DELAY MODE (6 GATES) ---
    print("\n>>> TEST SCENARIO 1: Expected Delay Mode (6 Gates, Buffer=15m)")
    try:
        assign_s1, status_s1, time_s1 = solve_from_dataframe(
            df=sample_ml_predictions,
            num_gates=6,
            buffer_time_min=15,
            mode="expected",
            time_limit_sec=60
        )
        reassignments = sum(
            1 for row in sample_ml_predictions.itertuples()
            if row.current_gate and row.current_gate != assign_s1.get(row.flight_key)
        )
        print(f"Status: {status_s1} | Wall Time: {time_s1:.4f}s | Reassignments: {reassignments}")
        print(f"{'Flight Key':<12} | {'Sched (m)':<10} | {'Prob Delay':<10} | {'Est Delay':<10} | {'Old Gate':<9} | {'New Gate':<9} | {'Status'}")
        print("-" * 80)
        for row in sample_ml_predictions.itertuples():
            f_key = row.flight_key
            new_g = assign_s1[f_key]
            old_g = row.current_gate
            tag = "REASSIGNED" if old_g and old_g != new_g else "UNCHANGED"
            print(f"{f_key:<12} | {row.CRS_DEP_TIME:<10} | {row.p_arr_delay_15:<10.2f} | {row.predicted_arr_delay_min:<10.1f} | {old_g:<9} | {new_g:<9} | [{tag}]")
    except RuntimeError as err:
        print(f"Scenario 1 Failed: {err}")

    # --- TEST SCENARIO 2: WORST-CASE DELAY MODE (6 GATES) ---
    print("\n>>> TEST SCENARIO 2: Worst-Case Delay Mode (6 Gates, Buffer=15m)")
    try:
        assign_s2, status_s2, time_s2 = solve_from_dataframe(
            df=sample_ml_predictions,
            num_gates=6,
            buffer_time_min=15,
            mode="worst_case",
            time_limit_sec=60
        )
        print(f"Status: {status_s2} | Wall Time: {time_s2:.4f}s")
    except RuntimeError as err:
        print(f"Scenario 2 Status: {err}")

    # --- TEST SCENARIO 3: CAPACITY STRESS TEST (1 GATE -> EXPECT INFEASIBLE) ---
    print("\n>>> TEST SCENARIO 3: Stress Test (1 Gate -> Expect Infeasible)")
    try:
        assign_s3, status_s3, time_s3 = solve_from_dataframe(
            df=sample_ml_predictions,
            num_gates=1,
            buffer_time_min=15,
            mode="expected",
            time_limit_sec=10
        )
        print(f"Status: {status_s3} | Wall Time: {time_s3:.4f}s")
    except RuntimeError as err:
        print("Status: INFEASIBLE (Expected Exception Caught)")
        print("Summary: AddNoOverlap constraint successfully prevented time-overlapping gate assignments under insufficient gate capacity.")

    print("=========================================================================")