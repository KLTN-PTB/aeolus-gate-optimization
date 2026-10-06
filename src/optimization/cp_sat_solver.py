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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path when executed directly as a script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from ortools.sat.python import cp_model

from src.optimization.contracts import CostParams, CostParameters, Flight, Gate, ProblemInstance

logger = logging.getLogger(__name__)


class GateAssignmentResult:
    """Kết quả phân bổ cổng từ CP-SAT, kèm thông tin tính toán thời gian cất cánh.

    Hỗ trợ cả 2 cách sử dụng:
    1. Unpacking chuẩn 3-tuple (tương thích 100% với code/test hiện hữu):
       assignment, status, wall_time = solve_gate_assignment(instance)
    2. Truy cập thuộc tính phong phú:
       result.departure_times        # dict {flight_id: pred_dep_min}
       result.schedule_df            # pd.DataFrame chi tiết giờ hạ cánh, quay đầu, cất cánh
       result.assignment             # dict {flight_id: gate_id}
       result.status                 # "OPTIMAL" | "FEASIBLE"
       result.wall_time              # float (seconds)
    """

    def __init__(
        self,
        assignment: dict[str, str],
        status: str,
        wall_time: float,
        departure_times: Optional[dict[str, int]] = None,
        schedule_df: Optional[pd.DataFrame] = None,
    ) -> None:
        self.assignment = assignment
        self.status = status
        self.wall_time = wall_time
        self.departure_times = departure_times or {}
        self.schedule_df = schedule_df if schedule_df is not None else pd.DataFrame()

    def __iter__(self):
        yield self.assignment
        yield self.status
        yield self.wall_time

    def __getitem__(self, index: int) -> Any:
        return (self.assignment, self.status, self.wall_time)[index]

    def __len__(self) -> int:
        return 3

    def __repr__(self) -> str:
        return (
            f"GateAssignmentResult(status={self.status!r}, "
            f"assigned_flights={len(self.assignment)}, "
            f"wall_time={self.wall_time:.4f}s)"
        )


def calculate_departure_time(
    flight: Flight,
    paired_flight: Optional[Flight] = None,
    turnaround_time_min: Optional[int] = None,
    mode: str = "expected",
    realized_delay: Optional[float] = None,
    default_turnaround_time_min: int = 45,
) -> dict[str, Any]:
    """Tính toán thời gian cất cánh dự kiến của tàu bay có tính đến thời gian quay đầu.

    Công thức chuẩn hóa (theo Roadmap V3/V4 Section 4):
    1. Giờ hạ cánh dự kiến (Predicted Arrival):
       - Mode 'expected': eff_delay = p_delay * delay_est_min
       - Mode 'worst_case': eff_delay = delay_est_min
       - Mode 'realized': eff_delay = realized_delay if realized_delay is not None else 0.0
       A_pred = A_sched + eff_delay
    2. Thời gian quay đầu (Turnaround Time):
       T_turn = turnaround_time_min or flight.turnaround_time_min or default_turnaround_time_min
    3. Giờ cất cánh sớm nhất có thể sau khi quay đầu (Earliest Feasible Departure):
       D_min = A_pred + T_turn
    4. Giờ cất cánh dự kiến / mô phỏng (Simulated/Predicted Departure):
       - Đối với chuyến bay đến ghép cặp với chuyến đi (paired outbound flight):
         D_pred = max(D_sched, D_min)
       - Đối với chuyến bay đến độc lập (unpaired arrival):
         D_pred = D_min (hoặc max(D_min, A_pred + dwell_time_min))
       - Đối với chuyến bay đi độc lập (unpaired departure):
         D_pred = D_sched + eff_delay
    5. Độ trễ cất cánh phát sinh (Reactionary / Turnaround Departure Delay):
       dep_delay = max(0.0, D_pred - D_sched) (nếu có D_sched)

    Parameters
    ----------
    flight : Flight
        Chuyến bay cần tính toán thời gian cất cánh.
    paired_flight : Optional[Flight]
        Chuyến bay ghép cặp trong cùng chuỗi xoay vòng tàu bay (chain_group_id).
    turnaround_time_min : Optional[int]
        Thời gian quay đầu ghi đè (phút). Nếu None, lấy từ flight hoặc default.
    mode : str
        Chế độ trễ: 'expected', 'worst_case', 'realized'.
    realized_delay : Optional[float]
        Mức trễ thực tế nếu mode == 'realized'.
    default_turnaround_time_min : int
        Thời gian quay đầu mặc định (mặc định 45 phút).

    Returns
    -------
    dict[str, Any]
        Dictionary chứa các thông tin tính toán chi tiết:
        - flight_id: str
        - direction: str ("ARR" | "DEP")
        - sched_arrival_min: Optional[int]
        - pred_arrival_min: Optional[int]
        - turnaround_time_min: int
        - earliest_departure_min: int (D_min)
        - sched_departure_min: Optional[int] (D_sched)
        - calculated_departure_min: int (D_pred, thời gian máy bay cất cánh)
        - departure_delay_min: float
    """
    if mode == "expected":
        eff_delay = flight.p_delay * flight.delay_est_min
    elif mode == "worst_case":
        eff_delay = flight.delay_est_min
    elif mode == "realized":
        eff_delay = realized_delay if realized_delay is not None else 0.0
    else:
        raise ValueError(f"Unknown occupancy mode: {mode!r}")

    t_turn = (
        turnaround_time_min
        if turnaround_time_min is not None
        else (flight.turnaround_time_min if flight.turnaround_time_min is not None else default_turnaround_time_min)
    )

    if flight.direction == "ARR":
        sched_arr = flight.sched_time_min
        pred_arr = int(sched_arr + eff_delay)
        earliest_dep = pred_arr + t_turn

        if paired_flight is not None:
            sched_dep = paired_flight.sched_time_min
            calc_dep = max(sched_dep, earliest_dep)
            dep_delay = max(0.0, float(calc_dep - sched_dep))
        else:
            sched_dep = sched_arr + t_turn
            calc_dep = earliest_dep
            dep_delay = max(0.0, float(calc_dep - sched_dep))

        return {
            "flight_id": flight.flight_id,
            "direction": flight.direction,
            "sched_arrival_min": sched_arr,
            "pred_arrival_min": pred_arr,
            "turnaround_time_min": t_turn,
            "earliest_departure_min": earliest_dep,
            "sched_departure_min": sched_dep,
            "calculated_departure_min": calc_dep,
            "departure_delay_min": dep_delay,
        }

    elif flight.direction == "TURN":
        sched_arr = flight.sched_time_min
        pred_arr = int(sched_arr + eff_delay)
        duration = max(1, flight.dwell_time_min)
        sched_dep = sched_arr + duration
        calc_dep = pred_arr + duration
        dep_delay = max(0.0, float(calc_dep - sched_dep))
        return {
            "flight_id": flight.flight_id,
            "direction": flight.direction,
            "sched_arrival_min": sched_arr,
            "pred_arrival_min": pred_arr,
            "turnaround_time_min": t_turn,
            "earliest_departure_min": pred_arr + (t_turn or duration),
            "sched_departure_min": sched_dep,
            "calculated_departure_min": calc_dep,
            "departure_delay_min": dep_delay,
        }

    else:  # direction == "DEP"
        sched_dep = flight.sched_time_min

        if paired_flight is not None and paired_flight.direction == "ARR":
            if mode == "expected":
                arr_delay = paired_flight.p_delay * paired_flight.delay_est_min
            elif mode == "worst_case":
                arr_delay = paired_flight.delay_est_min
            elif mode == "realized":
                arr_delay = realized_delay if realized_delay is not None else 0.0
            else:
                arr_delay = 0.0

            sched_arr = paired_flight.sched_time_min
            pred_arr = int(sched_arr + arr_delay)
            pair_t_turn = (
                turnaround_time_min
                if turnaround_time_min is not None
                else (
                    flight.turnaround_time_min
                    if flight.turnaround_time_min is not None
                    else (
                        paired_flight.turnaround_time_min
                        if paired_flight.turnaround_time_min is not None
                        else default_turnaround_time_min
                    )
                )
            )
            earliest_dep = pred_arr + pair_t_turn
            calc_dep = max(sched_dep, earliest_dep)
            dep_delay = max(0.0, float(calc_dep - sched_dep))

            return {
                "flight_id": flight.flight_id,
                "direction": flight.direction,
                "sched_arrival_min": sched_arr,
                "pred_arrival_min": pred_arr,
                "turnaround_time_min": pair_t_turn,
                "earliest_departure_min": earliest_dep,
                "sched_departure_min": sched_dep,
                "calculated_departure_min": calc_dep,
                "departure_delay_min": dep_delay,
            }
        else:
            calc_dep = int(sched_dep + eff_delay)
            dep_delay = max(0.0, float(calc_dep - sched_dep))
            return {
                "flight_id": flight.flight_id,
                "direction": flight.direction,
                "sched_arrival_min": None,
                "pred_arrival_min": None,
                "turnaround_time_min": t_turn,
                "earliest_departure_min": calc_dep,
                "sched_departure_min": sched_dep,
                "calculated_departure_min": calc_dep,
                "departure_delay_min": dep_delay,
            }


def occupancy_window(
    flight: Flight,
    buffer_time_min: int,
    mode: str = "expected",
    realized_delay: Optional[float] = None,
    turnaround_time_min: Optional[int] = None,
    paired_flight: Optional[Flight] = None,
) -> tuple[int, int]:
    """Calculate the occupancy interval (start, end) in minutes for a flight or turn session.

    Hỗ trợ cả 3 dạng hướng di chuyển:
    - ARR: chuyến đến độc lập hoặc chặng đầu của cặp xoay vòng.
    - DEP: chuyến đi độc lập hoặc chặng sau của cặp xoay vòng.
    - TURN: phiên quay đầu kỹ thuật trọn gói (turnaround session).
    """
    if mode == "expected":
        eff_delay = flight.p_delay * flight.delay_est_min
    elif mode == "worst_case":
        eff_delay = flight.delay_est_min
    elif mode == "realized":
        eff_delay = realized_delay if realized_delay is not None else 0.0
    else:
        raise ValueError(f"Unknown occupancy mode: {mode!r}")

    t_turn = turnaround_time_min if turnaround_time_min is not None else flight.turnaround_time_min

    if flight.direction == "TURN":
        arr_time = int(flight.sched_time_min + eff_delay)
        duration = max(1, flight.dwell_time_min)
        dep_time = arr_time + duration
        start = int(arr_time - buffer_time_min)
        end = int(dep_time + buffer_time_min)
    elif t_turn is not None or paired_flight is not None:
        t_effective = t_turn if t_turn is not None else flight.dwell_time_min
        dep_info = calculate_departure_time(
            flight=flight,
            paired_flight=paired_flight,
            turnaround_time_min=t_effective,
            mode=mode,
            realized_delay=realized_delay,
        )
        if paired_flight is not None:
            # Paired turn: flight and paired_flight represent inbound and outbound legs of same aircraft turn.
            arr_flight = flight if flight.direction == "ARR" else paired_flight
            arr_time = dep_info["pred_arrival_min"] if dep_info["pred_arrival_min"] is not None else arr_flight.sched_time_min
            calc_dep = dep_info["calculated_departure_min"]
            t_split = max(arr_time, min(calc_dep, (arr_time + calc_dep) // 2))

            if flight.direction == "ARR":
                start = int(arr_time - buffer_time_min)
                end = int(t_split)
            else:
                start = int(t_split)
                end = int(calc_dep + buffer_time_min)
        elif flight.direction == "ARR":
            arr_time = dep_info["pred_arrival_min"] if dep_info["pred_arrival_min"] is not None else flight.sched_time_min
            start = int(arr_time - buffer_time_min)
            dep_time = dep_info["calculated_departure_min"]
            end = int(dep_time + buffer_time_min)
        else:
            dep_time = dep_info["calculated_departure_min"]
            end = int(dep_time + buffer_time_min)
            start = int(dep_time - flight.dwell_time_min - buffer_time_min)
    else:
        if flight.direction == "DEP":
            dep_time = int(flight.sched_time_min + eff_delay)
            end = int(dep_time + buffer_time_min)
            start = int(dep_time - flight.dwell_time_min - buffer_time_min)
        else:
            start = int(flight.sched_time_min + eff_delay - buffer_time_min)
            end = start + flight.dwell_time_min

    start_clamped = max(0, start)
    end_clamped = max(start_clamped + 1, end)
    return start_clamped, end_clamped


def compute_flight_schedule(
    instance: ProblemInstance,
    assignment: Optional[dict[str, str]] = None,
    mode: str = "expected",
    default_turnaround_time_min: int = 45,
) -> pd.DataFrame:
    """Tính toán thời gian cất cánh và lịch biểu chi tiết cho toàn bộ chuyến bay trong ProblemInstance.

    Parameters
    ----------
    instance : ProblemInstance
        Bài toán lập lịch cổng đỗ với danh sách chuyến bay và cổng.
    assignment : Optional[dict[str, str]]
        Kết quả gán cổng {flight_id: gate_id} nếu đã giải.
    mode : str
        Chế độ dự báo trễ: 'expected', 'worst_case', 'realized'.
    default_turnaround_time_min : int
        Thời gian quay đầu mặc định (phút).

    Returns
    -------
    pd.DataFrame
        Bảng chi tiết bao gồm giờ đến, thời gian quay đầu, giờ cất cánh và khoảng chiếm dụng cổng.
    """
    chain_pairs: dict[str, list[Flight]] = defaultdict(list)
    for f in instance.flights:
        if f.chain_group_id:
            chain_pairs[f.chain_group_id].append(f)

    flight_to_pair: dict[str, Flight] = {}
    for chain_id, flights in chain_pairs.items():
        if len(flights) == 2:
            f1, f2 = flights[0], flights[1]
            flight_to_pair[f1.flight_id] = f2
            flight_to_pair[f2.flight_id] = f1

    records = []
    for f in instance.flights:
        paired = flight_to_pair.get(f.flight_id)
        dep_info = calculate_departure_time(
            flight=f,
            paired_flight=paired,
            turnaround_time_min=f.turnaround_time_min,
            mode=mode,
            default_turnaround_time_min=default_turnaround_time_min,
        )
        assigned_gate = assignment.get(f.flight_id) if assignment else None
        start_i, end_i = occupancy_window(
            flight=f,
            buffer_time_min=instance.cost_params.buffer_time_min,
            mode=mode,
            turnaround_time_min=f.turnaround_time_min,
            paired_flight=paired,
        )

        if mode == "expected":
            eff_delay = f.p_delay * f.delay_est_min
        elif mode == "worst_case":
            eff_delay = f.delay_est_min
        elif mode == "realized":
            eff_delay = f.actual_delay_min if f.actual_delay_min is not None else 0.0
        else:
            eff_delay = 0.0

        pred_target_min = int(f.sched_time_min + eff_delay)
        actual_delay = getattr(f, "actual_delay_min", None)
        actual_target_min = int(f.sched_time_min + actual_delay) if actual_delay is not None else None

        records.append({
            "flight_id": f.flight_id,
            "direction": f.direction,
            "aircraft_type": f.aircraft_type,
            "chain_group_id": f.chain_group_id,
            "current_gate": f.current_gate,
            "assigned_gate": assigned_gate,
            "is_reassigned": (f.current_gate != assigned_gate) if (f.current_gate is not None and assigned_gate is not None) else False,
            "p_delay": f.p_delay,
            "delay_est_min": f.delay_est_min,
            "effective_delay_min": round(eff_delay, 2),
            "actual_delay_min": actual_delay,
            "sched_target_min": f.sched_time_min,
            "pred_target_min": pred_target_min,
            "actual_target_min": actual_target_min,
            "sched_arrival_min": dep_info["sched_arrival_min"],
            "pred_arrival_min": dep_info["pred_arrival_min"],
            "turnaround_time_min": dep_info["turnaround_time_min"],
            "earliest_departure_min": dep_info["earliest_departure_min"],
            "sched_departure_min": dep_info["sched_departure_min"],
            "calculated_departure_min": dep_info["calculated_departure_min"],
            "departure_delay_min": dep_info["departure_delay_min"],
            "dwell_time_min": f.dwell_time_min,
            "occupancy_duration_min": end_i - start_i,
            "occupancy_start_min": start_i,
            "occupancy_end_min": end_i,
        })

    return pd.DataFrame(records)


def solve_gate_assignment(
    instance: ProblemInstance,
    time_limit_sec: int = 60,
    mode: str = "expected",
    num_workers: int = 8,
    use_turnaround: bool = False,
    default_turnaround_time_min: Optional[int] = None,
    return_schedule: bool = False,
) -> tuple[dict[str, str], str, float] | GateAssignmentResult:
    """Solve the gate assignment problem using CP-SAT, supporting turnaround time to calculate departure time.

    Parameters
    ----------
    instance : ProblemInstance
        Dữ liệu bài toán lập lịch cổng.
    time_limit_sec : int
        Giới hạn thời gian giải CP-SAT (giây).
    mode : str
        Chế độ dự báo trễ ('expected', 'worst_case', 'realized').
    num_workers : int
        Số luồng tìm kiếm song song của CP-SAT.
    use_turnaround : bool
        Nếu True, kích hoạt tính toán khoảng chiếm dụng cổng dựa trên thời gian quay đầu.
    default_turnaround_time_min : Optional[int]
        Thời gian quay đầu mặc định nếu flight.turnaround_time_min là None.
    return_schedule : bool
        Nếu True, trả về tuple 4 phần tử (assignment, status, wall_time, schedule_df).
        Nếu False, trả về GateAssignmentResult (hỗ trợ cả unpack 3-tuple và truy cập thuộc tính).

    Returns
    -------
    GateAssignmentResult hoặc tuple
        (assignment, status_name, wall_time) hoặc (assignment, status_name, wall_time, schedule_df).
    """
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.BoolVar] = {}
    y: dict[str, cp_model.BoolVar] = {}
    intervals_by_gate: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    # Nhóm các chuyến bay thuộc cùng chuỗi xoay vòng tàu bay
    chain_pairs: dict[str, list[Flight]] = defaultdict(list)
    for f in instance.flights:
        if f.chain_group_id:
            chain_pairs[f.chain_group_id].append(f)

    flight_to_pair: dict[str, Flight] = {}
    for chain_id, flights in chain_pairs.items():
        if len(flights) == 2:
            f1, f2 = flights[0], flights[1]
            flight_to_pair[f1.flight_id] = f2
            flight_to_pair[f2.flight_id] = f1

    def_turn = (
        default_turnaround_time_min
        if default_turnaround_time_min is not None
        else getattr(instance.cost_params, "default_turnaround_time_min", 45)
    )

    for f in instance.flights:
        turn_t = f.turnaround_time_min if f.turnaround_time_min is not None else (def_turn if use_turnaround else None)
        paired = flight_to_pair.get(f.flight_id)
        start_i, end_i = occupancy_window(
            flight=f,
            buffer_time_min=instance.cost_params.buffer_time_min,
            mode=mode,
            turnaround_time_min=turn_t,
            paired_flight=paired,
        )
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
    # Chỉ ghép cặp cho 2 chặng đơn lẻ (1 ARR và 1 DEP) thuộc cùng một chuỗi quay đầu tại sân bay,
    # trong đó chuyến ARR phải đến trước chuyến DEP và khoảng cách quay đầu hợp lý (<= 6 giờ).
    for chain_id, flights in chain_pairs.items():
        if len(flights) == 2:
            f1, f2 = flights[0], flights[1]
            if f1.direction == "TURN" or f2.direction == "TURN":
                continue
            if {f1.direction, f2.direction} != {"ARR", "DEP"}:
                continue
            arr_f = f1 if f1.direction == "ARR" else f2
            dep_f = f2 if f1.direction == "ARR" else f1
            # Chuyến đến phải trước chuyến đi trong cùng 1 chu kỳ quay đầu tại sân bay
            if arr_f.sched_time_min > dep_f.sched_time_min:
                continue
            # Khoảng cách quay đầu không quá 6 tiếng (360 phút)
            if (dep_f.sched_time_min - arr_f.sched_time_min) > 360:
                continue
            w1 = occupancy_window(arr_f, instance.cost_params.buffer_time_min, mode=mode, turnaround_time_min=turn_t, paired_flight=dep_f)
            w2 = occupancy_window(dep_f, instance.cost_params.buffer_time_min, mode=mode, turnaround_time_min=turn_t, paired_flight=arr_f)
            if w1[0] < w2[1] and w2[0] < w1[1]:
                continue
            for g in instance.gates:
                if (arr_f.flight_id, g.gate_id) in x and (dep_f.flight_id, g.gate_id) in x:
                    model.Add(x[arr_f.flight_id, g.gate_id] == x[dep_f.flight_id, g.gate_id])

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

    # Tính toán toàn bộ lịch cất cánh dựa trên thời gian quay đầu
    schedule_df = compute_flight_schedule(
        instance=instance,
        assignment=assignment,
        mode=mode,
        default_turnaround_time_min=def_turn,
    )
    departure_times = dict(zip(schedule_df["flight_id"], schedule_df["calculated_departure_min"]))

    if return_schedule:
        return assignment, status_name, wall_time, schedule_df

    return GateAssignmentResult(
        assignment=assignment,
        status=status_name,
        wall_time=wall_time,
        departure_times=departure_times,
        schedule_df=schedule_df,
    )


def dataframe_to_problem_instance(
    df: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    default_dwell_time_min: int = 45,
    default_turnaround_time_min: int = 45,
    gates: Optional[list[Gate]] = None,
    airport: str = "ATL",
    planning_date: str = "2024-01-01",
) -> ProblemInstance:
    """Chuyển đổi DataFrame kết quả mô hình (hoặc Parquet OOF, Parquet Turnaround Sessions) sang ProblemInstance.

    Hỗ trợ tự động nhận diện:
    - Bảng phiên quay đầu (Turnaround Sessions): session_id, session_type, sched_start_min, pred_start_min,...
    - Bảng chuyến bay truyền thống: flight_id, flight_key, CRS_DEP_TIME, crs_arr_time,...
    """
    is_session_df = "session_id" in df.columns or "session_type" in df.columns

    flights: list[Flight] = []

    if is_session_df:
        for idx, row in df.iterrows():
            f_id = str(row.get("session_id", row.get("flight_id", row.get("flight_key", f"TURN_{idx:04d}"))))
            stype = str(row.get("session_type", "PAIRED_TURN"))
            if stype == "PAIRED_TURN":
                direction = "TURN"
            elif stype == "UNMATCHED_ARR":
                direction = "ARR"
            elif stype == "UNMATCHED_DEP":
                direction = "DEP"
            else:
                direction = str(row.get("direction", "TURN"))

            # Giờ lịch trình (phút từ 00:00)
            if direction == "DEP" and "sched_end_min" in row and pd.notna(row["sched_end_min"]):
                sched_time = int(row["sched_end_min"])
            elif "sched_start_min" in row and pd.notna(row["sched_start_min"]):
                sched_time = int(row["sched_start_min"])
            elif "sched_time_min" in row and pd.notna(row["sched_time_min"]):
                sched_time = int(row["sched_time_min"])
            else:
                sched_time = 0

            # Thời gian đỗ tại cổng
            if "sched_duration_min" in row and pd.notna(row["sched_duration_min"]):
                dwell_time = max(1, int(row["sched_duration_min"]))
            elif "pred_duration_min" in row and pd.notna(row["pred_duration_min"]):
                dwell_time = max(1, int(row["pred_duration_min"]))
            elif "dwell_time_min" in row and pd.notna(row["dwell_time_min"]):
                dwell_time = max(1, int(row["dwell_time_min"]))
            else:
                dwell_time = default_dwell_time_min

            # Thời gian quay đầu
            turnaround_val = row.get("turnaround_time_min")
            turnaround_time = (
                int(turnaround_val)
                if pd.notna(turnaround_val) and float(turnaround_val) > 0
                else default_turnaround_time_min
            )

            # Xác suất trễ
            p_val = row.get("p_delay_max", row.get("p_delay", row.get("prob_delay", 0.5)))
            prob_delay = max(0.0, min(1.0, float(p_val))) if pd.notna(p_val) else 0.5

            # Mức trễ dự báo
            if direction == "DEP":
                d_val = row.get("dep_delay_est_min", row.get("predicted_dep_delay_min", row.get("delay_est_min", 0.0)))
            else:
                d_val = row.get("arr_delay_est_min", row.get("predicted_arr_delay_min", row.get("delay_est_min", 0.0)))
            delay_est = max(0.0, float(d_val)) if pd.notna(d_val) else 0.0

            # Loại tàu bay
            aircraft_type = str(row.get("aircraft_type", "ALL")) if pd.notna(row.get("aircraft_type")) else "ALL"

            # Chuỗi xoay vòng & Cổng hiện tại (Trong bảng phiên, mỗi phiên đã đại diện trọn vẹn một đợt đỗ cổng)
            chain_group_id_str = None
            cur_gate = row.get("current_gate")
            current_gate_str = str(cur_gate) if pd.notna(cur_gate) else None

            # Nhãn trễ thực tế
            if direction == "DEP":
                act_val = row.get("dep_true_delay_min", row.get("actual_delay_min"))
            else:
                act_val = row.get("arr_true_delay_min", row.get("actual_delay_min"))
            actual_delay = float(act_val) if pd.notna(act_val) else None

            f = Flight(
                flight_id=f_id,
                direction=direction,
                sched_time_min=sched_time,
                dwell_time_min=dwell_time,
                delay_est_min=delay_est,
                p_delay=prob_delay,
                aircraft_type=aircraft_type,
                current_gate=current_gate_str,
                chain_group_id=chain_group_id_str,
                turnaround_time_min=turnaround_time,
                actual_delay_min=actual_delay,
            )
            flights.append(f)
    else:
        # Standard legacy / raw flight DataFrame
        has_dir = "direction" in df.columns
        chain_col = "chain_group_id" if "chain_group_id" in df.columns else ("chain_id" if "chain_id" in df.columns else None)
        chain_flight_dir: dict[Any, str] = {}
        if not has_dir and chain_col and chain_col in df.columns:
            chain_groups = df[df[chain_col].notna()].groupby(chain_col)
            for _, group in chain_groups:
                if len(group) == 2:
                    sched_col = next(
                        (c for c in ["sched_time_min", "crs_arr_time", "CRS_ARR_TIME", "CRS_DEP_TIME", "crs_dep_time"] if c in df.columns),
                        None,
                    )
                    if sched_col:
                        sorted_indices = group.sort_values(sched_col).index.tolist()
                        chain_flight_dir[sorted_indices[0]] = "ARR"
                        chain_flight_dir[sorted_indices[1]] = "DEP"

        for idx, row in df.iterrows():
            f_id = str(row.get("flight_id", row.get("flight_key", f"FL_{idx:04d}")))
            sched_col = next(
                (c for c in ["sched_time_min", "crs_arr_time", "CRS_ARR_TIME", "CRS_DEP_TIME", "crs_dep_time", "ARR_HOUR", "DEP_HOUR"] if c in row and pd.notna(row[c])),
                None,
            )
            sched_time = int(float(row[sched_col])) if sched_col else 0

            dwell_col = next(
                (c for c in ["dwell_time_min", "sched_duration_min", "CRS_ELAPSED_TIME"] if c in row and pd.notna(row[c])),
                None,
            )
            dwell_time = max(1, int(float(row[dwell_col]))) if dwell_col else default_dwell_time_min

            delay_col = next(
                (c for c in ["delay_est_min", "predicted_arr_delay_min", "predicted_dep_delay_min", "pred_arr_delay", "arr_delay_est_min"] if c in row and pd.notna(row[c])),
                None,
            )
            delay_est = max(0.0, float(row[delay_col])) if delay_col else 0.0

            prob_col = next(
                (c for c in ["p_delay", "p_delay_max", "p_arr_delay_15", "p_dep_delay_15", "prob_delay"] if c in row and pd.notna(row[c])),
                None,
            )
            prob_delay = max(0.0, min(1.0, float(row[prob_col]))) if prob_col else 0.0

            cur_gate = row.get("current_gate")
            current_gate_str = str(cur_gate) if pd.notna(cur_gate) else None

            chain_id_val = row.get("chain_group_id", row.get("chain_id"))
            chain_group_id_str = str(chain_id_val) if pd.notna(chain_id_val) else None

            if has_dir:
                direction = str(row.get("direction", "ARR"))
            elif idx in chain_flight_dir:
                direction = chain_flight_dir[idx]
            else:
                direction = "ARR"

            turnaround_val = row.get("turnaround_time_min", row.get("turnaround_time", row.get("T_turnaround")))
            turnaround_time = int(turnaround_val) if pd.notna(turnaround_val) and float(turnaround_val) > 0 else None

            ac_type = str(row.get("aircraft_type", "ALL")) if pd.notna(row.get("aircraft_type")) else "ALL"

            actual_val = row.get("actual_delay_min", row.get("y_true_arr_delay_min", row.get("y_true_dep_delay_min", row.get("ARR_DELAY", row.get("DEP_DELAY")))))
            actual_delay = float(actual_val) if pd.notna(actual_val) else None

            f = Flight(
                flight_id=f_id,
                direction=direction,
                sched_time_min=sched_time,
                dwell_time_min=dwell_time,
                delay_est_min=delay_est,
                p_delay=prob_delay,
                aircraft_type=ac_type,
                current_gate=current_gate_str,
                chain_group_id=chain_group_id_str,
                turnaround_time_min=turnaround_time,
                actual_delay_min=actual_delay,
            )
            flights.append(f)

    if gates is None:
        gates = []
        for j in range(1, num_gates + 1):
            g = Gate(
                gate_id=f"G{j:02d}",
                compatible_types=["ALL"],
                available_from_min=0,
                available_to_min=1440 * 2,
            )
            gates.append(g)

    cost_params = CostParams(
        buffer_time_min=buffer_time_min,
        default_turnaround_time_min=default_turnaround_time_min,
    )
    return ProblemInstance(
        airport=airport,
        planning_date=planning_date,
        flights=flights,
        gates=gates,
        cost_params=cost_params,
    )


def solve_from_dataframe(
    df: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    mode: str = "expected",
    time_limit_sec: int = 60,
    use_turnaround: bool = False,
    default_turnaround_time_min: int = 45,
    return_schedule: bool = False,
    gates: Optional[list[Gate]] = None,
) -> tuple[dict[str, str], str, float] | GateAssignmentResult:
    instance = dataframe_to_problem_instance(
        df=df,
        num_gates=num_gates,
        buffer_time_min=buffer_time_min,
        default_turnaround_time_min=default_turnaround_time_min,
        gates=gates,
    )
    return solve_gate_assignment(
        instance=instance,
        time_limit_sec=time_limit_sec,
        mode=mode,
        use_turnaround=use_turnaround,
        default_turnaround_time_min=default_turnaround_time_min,
        return_schedule=return_schedule,
    )


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

    # --- TEST SCENARIO 1: EXPECTED DELAY MODE WITH TURNAROUND (6 GATES) ---
    print("\n>>> TEST SCENARIO 1: Expected Delay Mode with Turnaround (6 Gates, Buffer=15m, Turnaround=45m)")
    try:
        res_s1 = solve_from_dataframe(
            df=sample_ml_predictions,
            num_gates=6,
            buffer_time_min=15,
            mode="expected",
            time_limit_sec=60,
            use_turnaround=True,
            default_turnaround_time_min=45,
        )
        assign_s1, status_s1, time_s1 = res_s1
        reassignments = sum(
            1 for row in sample_ml_predictions.itertuples()
            if row.current_gate and row.current_gate != assign_s1.get(row.flight_key)
        )
        print(f"Status: {status_s1} | Wall Time: {time_s1:.4f}s | Reassignments: {reassignments}")
        print(f"{'Flight Key':<11} | {'Arr Pred':<9} | {'Turn(m)':<8} | {'D_min':<7} | {'D_pred':<7} | {'DepDelay':<9} | {'Gate':<6} | {'Status'}")
        print("-" * 88)
        for rec in res_s1.schedule_df.itertuples():
            f_key = rec.flight_id
            new_g = rec.assigned_gate
            old_g_series = sample_ml_predictions.loc[sample_ml_predictions["flight_key"] == f_key, "current_gate"]
            old_g = old_g_series.values[0] if len(old_g_series) > 0 else None
            tag = "REASSIGNED" if old_g and old_g != new_g else "UNCHANGED"
            print(
                f"{f_key:<11} | {rec.pred_arrival_min:<9} | {rec.turnaround_time_min:<8} | "
                f"{rec.earliest_departure_min:<7} | {rec.calculated_departure_min:<7} | "
                f"{rec.departure_delay_min:<9.1f} | {new_g:<6} | [{tag}]"
            )
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