"""Greedy Baseline Gate Assignment Strategy.

Sorts flights chronologically by occupancy start time and assigns compatible gates
according to configurable greedy heuristics:
- earliest_free (default): picks gate that freed earliest (longest idle time / largest buffer)
- first_available: picks first compatible free gate in gate list order
- min_reassignment: prioritizes keeping flight's current_gate if conflict-free
- contact_first: prioritizes contact gates over remote stands

Supports:
- Aircraft type compatibility (including 'ALL' wildcards)
- Gate availability windows (available_from_min, available_to_min)
- Occupancy window calculation with turnaround and delay modes (expected, worst_case, realized)
- Turnaround chain coupling
- Result encapsulation via GreedyAssignmentResult (subclass of dict for 100% backward compatibility)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Optional

import pandas as pd

from src.optimization.contracts import Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import calculate_departure_time, occupancy_window

logger = logging.getLogger(__name__)


def is_aircraft_compatible(aircraft_type: Optional[str], compatible_types: Optional[list[str]]) -> bool:
    """Kiểm tra tính tương thích giữa loại tàu bay và cổng đỗ."""
    gate_types = [t.upper() for t in compatible_types] if compatible_types else ["ALL"]
    f_type = aircraft_type.upper() if aircraft_type else "ALL"
    return "ALL" in gate_types or f_type == "ALL" or f_type in gate_types


class GreedyAssignmentResult(dict[str, str]):
    """Kết quả phân bổ cổng từ thuật toán Greedy.

    Kế thừa dict[str, str] để tương thích 100% với code/test hiện hữu:
    - assign["F1"] -> "G1"
    - len(assign) -> số chuyến được gán

    Đồng thời cung cấp các thuộc tính mở rộng phong phú:
    - result.status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE"
    - result.solve_time_sec: float
    - result.unassigned_flights: list[str]
    - result.reassigned_count: int
    - result.gate_workload: dict[str, int]
    - result.schedule_df: pd.DataFrame
    """

    def __init__(
        self,
        assignment: dict[str, str],
        status: str,
        solve_time_sec: float,
        unassigned_flights: Optional[list[str]] = None,
        reassigned_count: int = 0,
        gate_workload: Optional[dict[str, int]] = None,
        schedule_df: Optional[pd.DataFrame] = None,
    ) -> None:
        super().__init__(assignment)
        self.status = status
        self.solve_time_sec = solve_time_sec
        self.unassigned_flights = unassigned_flights or []
        self.reassigned_count = reassigned_count
        self.gate_workload = gate_workload or {}
        self.schedule_df = schedule_df if schedule_df is not None else pd.DataFrame()

    @property
    def assignment(self) -> dict[str, str]:
        return dict(self)

    @property
    def wall_time(self) -> float:
        return self.solve_time_sec


def greedy_assign(
    instance: ProblemInstance,
    mode: str = "expected",
    policy: str = "earliest_free",
    use_turnaround: bool = False,
    default_turnaround_time_min: Optional[int] = None,
    allow_unassigned: bool = False,
    return_schedule: bool = False,
) -> GreedyAssignmentResult:
    """Assign gates greedily based on chronological occupancy intervals.

    Parameters
    ----------
    instance : ProblemInstance
        Container dữ liệu bài toán (flights, gates, cost_params).
    mode : str
        Chế độ dự báo trễ: 'expected', 'worst_case', 'realized'.
    policy : str
        Chiến lược chọn cổng:
        - 'earliest_free': Cổng đã rảnh lâu nhất (tối đa hóa đệm an toàn).
        - 'first_available': Cổng đầu tiên khả dụng theo thứ tự danh sách cổng.
        - 'min_reassignment': Ưu tiên giữ nguyên current_gate nếu không bị xung đột.
        - 'contact_first': Ưu tiên cổng ống lồng (is_contact_gate=True) trước bãi xa.
    use_turnaround : bool
        Nếu True, kích hoạt tính toán chiếm dụng theo thời gian quay đầu.
    default_turnaround_time_min : Optional[int]
        Thời gian quay đầu mặc định nếu chuyến bay không quy định.
    allow_unassigned : bool
        Nếu False, raise RuntimeError khi một chuyến bay không tìm được cổng (chuẩn test).
        Nếu True, ghi nhận chuyến bay vào unassigned_flights và tiếp tục gán các chuyến khác.
    return_schedule : bool
        Nếu True, xây dựng bảng schedule_df chi tiết giờ đến, giờ quay đầu, giờ cất cánh.

    Returns
    -------
    GreedyAssignmentResult
        Đối tượng kết quả (tương thích dict) chứa {flight_id: gate_id} và các chỉ số đo lường.
    """
    t0 = time.perf_counter()
    assignment: dict[str, str] = {}
    unassigned: list[str] = []
    reassigned_count: int = 0

    # 1. Ghép cặp chuỗi xoay vòng tàu bay nếu có
    chain_pairs: dict[str, list[Flight]] = defaultdict(list)
    for f in instance.flights:
        if f.chain_group_id:
            chain_pairs[f.chain_group_id].append(f)

    flight_to_pair: dict[str, Flight] = {}
    for chain_id, flights in chain_pairs.items():
        if len(flights) == 2:
            arr_f = next((f for f in flights if f.direction == "ARR"), None)
            dep_f = next((f for f in flights if f.direction == "DEP"), None)
            if arr_f and dep_f and arr_f.sched_time_min < dep_f.sched_time_min and (dep_f.sched_time_min - arr_f.sched_time_min) <= 360:
                flight_to_pair[arr_f.flight_id] = dep_f
                flight_to_pair[dep_f.flight_id] = arr_f

    def_turn = (
        default_turnaround_time_min
        if default_turnaround_time_min is not None
        else getattr(instance.cost_params, "default_turnaround_time_min", 45)
    )

    # 2. Tính toán khoảng chiếm dụng cổng cho từng chuyến bay
    flight_windows: list[dict[str, Any]] = []
    for f in instance.flights:
        paired = flight_to_pair.get(f.flight_id)
        if paired is not None:
            turn_t = max(
                f.turnaround_time_min or (def_turn if use_turnaround else 45),
                paired.turnaround_time_min or (def_turn if use_turnaround else 45),
            )
        else:
            turn_t = f.turnaround_time_min if f.turnaround_time_min is not None else (def_turn if use_turnaround else None)

        start_i, end_i = occupancy_window(
            flight=f,
            buffer_time_min=instance.cost_params.buffer_time_min,
            mode=mode,
            turnaround_time_min=turn_t,
            paired_flight=paired,
        )

        dep_info = calculate_departure_time(
            flight=f,
            paired_flight=paired,
            turnaround_time_min=turn_t,
            mode=mode,
            default_turnaround_time_min=def_turn,
        )

        flight_windows.append({
            "flight": f,
            "start": start_i,
            "end": end_i,
            "paired": paired,
            "dep_info": dep_info,
        })

    # Sắp xếp theo thứ tự thời gian bắt đầu chiếm dụng (Interval Earliest-Start-First)
    flight_windows.sort(key=lambda item: (item["start"], item["end"], item["flight"].sched_time_min))

    # 3. Theo dõi lịch trình chiếm dụng trên từng cổng: {gate_id: [(start, end, flight_id), ...]}
    gate_intervals: dict[str, list[tuple[int, int, str]]] = {g.gate_id: [] for g in instance.gates}
    gate_map = {g.gate_id: g for g in instance.gates}

    # 4. Gán cổng tham lam (Greedy Allocation)
    for item in flight_windows:
        f: Flight = item["flight"]
        start_i: int = item["start"]
        end_i: int = item["end"]

        # Lọc các cổng ứng viên hợp lệ: tương thích loại tàu bay + nằm trong giờ hoạt động + không chồng chéo
        candidates: list[Gate] = []
        for g in instance.gates:
            if not is_aircraft_compatible(f.aircraft_type, g.compatible_types):
                continue
            if start_i < g.available_from_min or end_i > g.available_to_min:
                continue
            overlaps = any(max(start_i, occ_s) < min(end_i, occ_e) for occ_s, occ_e, _ in gate_intervals[g.gate_id])
            if not overlaps:
                candidates.append(g)

        if not candidates:
            if not allow_unassigned:
                logger.error("Greedy baseline failed for flight %s: no free compatible gate", f.flight_id)
                raise RuntimeError(
                    f"Greedy baseline failed at flight {f.flight_id}: no free compatible gate available at minute {start_i}"
                )
            unassigned.append(f.flight_id)
            continue

        # Lựa chọn cổng theo chính sách (Policy Selection)
        chosen: Optional[Gate] = None

        # Ràng buộc chuỗi xoay vòng: Nếu chuyến đối ứng (paired) đã được xếp cổng,
        # ưu tiên tuyệt đối cổng đó để đảm bảo tàu bay không phải chuyển cổng khi quay đầu
        if item.get("paired") is not None:
            paired_f = item["paired"]
            paired_gate_id = assignment.get(paired_f.flight_id)
            if paired_gate_id:
                matching_paired = next((g for g in candidates if g.gate_id == paired_gate_id), None)
                if matching_paired is not None:
                    chosen = matching_paired

        if chosen is None and policy == "min_reassignment" and f.current_gate:
            # Ưu tiên giữ nguyên cổng cũ nếu cổng cũ nằm trong danh sách ứng viên hợp lệ
            matching_cur = next((g for g in candidates if g.gate_id == f.current_gate), None)
            if matching_cur is not None:
                chosen = matching_cur

        if chosen is None and policy == "contact_first":
            # Ưu tiên cổng ống lồng (is_contact_gate=True)
            contact_cands = [g for g in candidates if g.is_contact_gate]
            if contact_cands:
                candidates = contact_cands

        if chosen is None:
            if policy == "first_available":
                chosen = candidates[0]
            else:  # 'earliest_free' (mặc định)
                def idle_score(g: Gate) -> int:
                    prior_ends = [occ_e for occ_s, occ_e, _ in gate_intervals[g.gate_id] if occ_e <= start_i]
                    return max(prior_ends) if prior_ends else 0

                chosen = min(candidates, key=idle_score)

        assignment[f.flight_id] = chosen.gate_id
        gate_intervals[chosen.gate_id].append((start_i, end_i, f.flight_id))

        if f.current_gate is not None and chosen.gate_id != f.current_gate:
            reassigned_count += 1

    solve_time = time.perf_counter() - t0
    status = "OPTIMAL" if not unassigned else ("INFEASIBLE" if not assignment else "FEASIBLE")

    # 5. Thống kê phụ tải cổng
    workload = {g_id: len(intervals) for g_id, intervals in gate_intervals.items()}

    # 6. Xây dựng bảng lịch trình nếu có yêu cầu
    schedule_df = pd.DataFrame()
    if return_schedule or len(assignment) > 0:
        records = []
        for item in flight_windows:
            f = item["flight"]
            dep_info = item["dep_info"]
            assigned_g = assignment.get(f.flight_id)
            is_reassigned = (f.current_gate is not None) and (assigned_g != f.current_gate)

            records.append({
                "flight_id": f.flight_id,
                "direction": f.direction,
                "aircraft_type": f.aircraft_type,
                "current_gate": f.current_gate,
                "assigned_gate": assigned_g,
                "is_reassigned": is_reassigned,
                "p_delay": f.p_delay,
                "delay_est_min": f.delay_est_min,
                "sched_target_min": f.sched_time_min,
                "calculated_departure_min": dep_info.get("calculated_departure_min"),
                "occupancy_start_min": item["start"],
                "occupancy_end_min": item["end"],
                "occupancy_duration_min": item["end"] - item["start"],
            })
        schedule_df = pd.DataFrame(records)

    logger.info(
        "Greedy assignment completed: %d flights assigned, %d unassigned, %d reassigned in %.3fs",
        len(assignment), len(unassigned), reassigned_count, solve_time
    )

    return GreedyAssignmentResult(
        assignment=assignment,
        status=status,
        solve_time_sec=solve_time,
        unassigned_flights=unassigned,
        reassigned_count=reassigned_count,
        gate_workload=workload,
        schedule_df=schedule_df,
    )


def greedy_assign_from_dataframe(
    df: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    default_dwell_time_min: int = 45,
    default_turnaround_time_min: int = 45,
    mode: str = "expected",
    policy: str = "earliest_free",
    use_turnaround: bool = False,
    allow_unassigned: bool = False,
    return_schedule: bool = True,
    gates: Optional[list[Gate]] = None,
    airport: str = "ATL",
    planning_date: str = "2024-01-01",
) -> tuple[dict[str, str], str, float, pd.DataFrame] | GreedyAssignmentResult:
    """Chuyển đổi DataFrame kết quả mô hình (hoặc Parquet) sang ProblemInstance và giải bằng Greedy Baseline.

    Parameters
    ----------
    df : pd.DataFrame
        Bảng chuyến bay hoặc phiên quay đầu (Turnaround Sessions).
    num_gates : int
        Số cổng đỗ mô phỏng.
    buffer_time_min : int
        Đệm an toàn giữa 2 chuyến tại cùng 1 cổng (phút).
    mode : str
        Chế độ tính trễ: 'expected', 'worst_case', 'realized'.
    policy : str
        Chính sách gán cổng ('earliest_free', 'first_available', 'min_reassignment', 'contact_first').
    allow_unassigned : bool
        Nếu True, cho phép bỏ qua chuyến bay không tìm được cổng thay vì raise Exception.
    return_schedule : bool
        Nếu True, trả về tuple (assignment, status, wall_time, schedule_df).

    Returns
    -------
    tuple hoặc GreedyAssignmentResult
    """
    from src.optimization.cp_sat_solver import dataframe_to_problem_instance

    instance = dataframe_to_problem_instance(
        df=df,
        num_gates=num_gates,
        buffer_time_min=buffer_time_min,
        default_dwell_time_min=default_dwell_time_min,
        default_turnaround_time_min=default_turnaround_time_min,
        gates=gates,
        airport=airport,
        planning_date=planning_date,
    )
    result = greedy_assign(
        instance=instance,
        mode=mode,
        policy=policy,
        use_turnaround=use_turnaround,
        default_turnaround_time_min=default_turnaround_time_min,
        allow_unassigned=allow_unassigned,
        return_schedule=return_schedule,
    )
    if return_schedule:
        return result.assignment, result.status, result.solve_time_sec, result.schedule_df
    return result

