"""Simulated Annealing Gate Optimization.

Takes an initial feasible assignment (from CP-SAT or Greedy) and optimizes multi-objective
soft costs (gate reassignment, delay risk, gate workload balance, remote stand penalties)
while guaranteeing zero hard constraint violations.

Supports:
- Aircraft type compatibility (including 'ALL' wildcards and case-insensitivity)
- Gate availability windows (available_from_min, available_to_min)
- Occupancy window calculation with turnaround and delay modes (expected, worst_case, realized)
- Turnaround chain coupling (paired legs stay at same gate)
- Both single-flight mutation and pairwise gate swap moves
- High-performance local feasibility validation
- Rich result encapsulation via SimulatedAnnealingResult (100% backward compatible with 2-tuple unpacking)
- Direct execution from DataFrame via simulated_annealing_from_dataframe
"""

from __future__ import annotations

import logging
import math
import random
import time
from collections import defaultdict
from typing import Any, Optional, Sequence

import pandas as pd

from src.optimization.contracts import Flight, Gate, ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window

logger = logging.getLogger(__name__)


def is_aircraft_compatible(aircraft_type: Optional[str], compatible_types: Optional[list[str]]) -> bool:
    """Kiểm tra tính tương thích giữa loại tàu bay và cổng đỗ.

    Hỗ trợ ký tự đại diện 'ALL' cho cả tàu bay và cổng đỗ, không phân biệt hoa thường.
    """
    gate_types = [t.upper() for t in compatible_types] if compatible_types else ["ALL"]
    f_type = aircraft_type.upper() if aircraft_type else "ALL"
    return "ALL" in gate_types or f_type == "ALL" or f_type in gate_types


class SimulatedAnnealingResult(tuple):
    """Kết quả phân bổ cổng từ thuật toán Simulated Annealing.

    Kế thừa tuple (assignment, best_cost) để tương thích 100% với cú pháp unpacking:
    `assign, cost = simulated_annealing(...)`.

    Đồng thời cung cấp các thuộc tính mở rộng phong phú:
    - result.assignment: dict[str, str]
    - result.best_cost: float
    - result.initial_cost: float
    - result.cost_improvement: float
    - result.solve_time_sec / result.wall_time: float
    - result.iterations: int
    - result.status: str ("OPTIMAL" | "FEASIBLE" | "INFEASIBLE")
    - result.cost_history: list[float]
    - result.schedule_df: pd.DataFrame
    """

    def __new__(
        cls,
        assignment: dict[str, str],
        best_cost: float,
        initial_cost: float = 0.0,
        solve_time_sec: float = 0.0,
        iterations: int = 0,
        status: str = "FEASIBLE",
        cost_history: Optional[list[float]] = None,
        schedule_df: Optional[pd.DataFrame] = None,
    ) -> SimulatedAnnealingResult:
        return super().__new__(cls, (assignment, best_cost))

    def __init__(
        self,
        assignment: dict[str, str],
        best_cost: float,
        initial_cost: float = 0.0,
        solve_time_sec: float = 0.0,
        iterations: int = 0,
        status: str = "FEASIBLE",
        cost_history: Optional[list[float]] = None,
        schedule_df: Optional[pd.DataFrame] = None,
    ) -> None:
        self.assignment = assignment
        self.best_cost = best_cost
        self.initial_cost = initial_cost
        self.cost_improvement = max(0.0, initial_cost - best_cost)
        self.solve_time_sec = solve_time_sec
        self.iterations = iterations
        self.status = status
        self.cost_history = cost_history or []
        self.schedule_df = schedule_df if schedule_df is not None else pd.DataFrame()

    @property
    def wall_time(self) -> float:
        return self.solve_time_sec


def soft_cost_breakdown(
    assignment: dict[str, str],
    instance: ProblemInstance,
    weights: Sequence[float] = (1.0, 1.0, 0.5, 1.0),
) -> dict[str, float]:
    """Calculate and breakdown multi-objective soft costs for a valid gate assignment.

    Returns
    -------
    dict[str, float]
        Dictionary containing:
        - reassignment_cost: gate reassignment penalty (w1)
        - delay_risk_cost: expected delay risk cost (w2)
        - load_balance_cost: gate workload balance variance penalty (w3)
        - remote_gate_cost: remote stand penalty (w4)
        - total: sum of all soft costs
    """
    w1, w2, w3, w4 = weights
    reassignment_cost = 0.0
    delay_risk_cost = 0.0
    remote_gate_cost = 0.0
    gate_load: dict[str, float] = defaultdict(float)
    gate_map = {g.gate_id: g for g in instance.gates}

    for f in instance.flights:
        g_id = assignment.get(f.flight_id)
        if not g_id or g_id not in gate_map:
            continue
        gate = gate_map[g_id]

        # Cost 1: Gate reassignment penalty
        if f.current_gate is not None and g_id != f.current_gate:
            reassignment_cost += w1 * instance.cost_params.reassignment_cost_default

        # Cost 2: Expected delay risk cost
        delay_risk_cost += w2 * f.p_delay * f.delay_est_min * instance.cost_params.delay_cost_weight

        # Cost 4: Remote gate penalty
        if not gate.is_contact_gate:
            remote_gate_cost += w4 * instance.cost_params.remote_gate_cost * f.priority_weight

        gate_load[g_id] += 1.0

    # Cost 3: Workload balance variance
    loads = list(gate_load.values()) or [0.0]
    mean_load = sum(loads) / len(loads)
    load_balance_cost = w3 * sum((l - mean_load) ** 2 for l in loads)

    total = reassignment_cost + delay_risk_cost + load_balance_cost + remote_gate_cost

    return {
        "reassignment_cost": float(reassignment_cost),
        "delay_risk_cost": float(delay_risk_cost),
        "load_balance_cost": float(load_balance_cost),
        "remote_gate_cost": float(remote_gate_cost),
        "total": float(total),
    }


def soft_cost(
    assignment: dict[str, str],
    instance: ProblemInstance,
    weights: Sequence[float],
) -> float:
    """Calculate multi-objective soft cost for a valid gate assignment.

    Parameters
    ----------
    assignment : dict[str, str]
        Mapping {flight_id: gate_id}.
    instance : ProblemInstance
        Problem instance data contract.
    weights : Sequence[float]
        Tuple/list of (w1, w2, w3, w4) objective weights.

    Returns
    -------
    float
        Total soft cost value.
    """
    return soft_cost_breakdown(assignment, instance, weights)["total"]


def _build_chain_pairs(instance: ProblemInstance) -> dict[str, Flight]:
    """Xây dựng liên kết ghép cặp xoay vòng 2 chiều cho các chuyến bay hợp lệ."""
    chain_groups: dict[str, list[Flight]] = defaultdict(list)
    for f in instance.flights:
        if f.chain_group_id:
            chain_groups[f.chain_group_id].append(f)

    flight_to_pair: dict[str, Flight] = {}
    for _, flights in chain_groups.items():
        if len(flights) == 2:
            f1, f2 = flights[0], flights[1]
            if f1.direction == "TURN" or f2.direction == "TURN":
                continue
            if {f1.direction, f2.direction} != {"ARR", "DEP"}:
                continue
            arr_f = f1 if f1.direction == "ARR" else f2
            dep_f = f2 if f1.direction == "ARR" else f1
            if arr_f.sched_time_min <= dep_f.sched_time_min and (dep_f.sched_time_min - arr_f.sched_time_min) <= 360:
                flight_to_pair[arr_f.flight_id] = dep_f
                flight_to_pair[dep_f.flight_id] = arr_f
    return flight_to_pair


def is_feasible(
    assignment: dict[str, str],
    instance: ProblemInstance,
    mode: str = "expected",
    use_turnaround: bool = False,
    default_turnaround_time_min: Optional[int] = None,
    precomputed_windows: Optional[dict[str, tuple[int, int]]] = None,
) -> bool:
    """Verify all hard constraints for a proposed candidate assignment.

    Hard Constraints:
    1. Aircraft compatibility (is_aircraft_compatible)
    2. Gate availability window [available_from_min, available_to_min]
    3. No time overlap between flights assigned to the same gate
    4. Flight chain turnaround gate coupling (paired ARR and DEP must share gate)

    Parameters
    ----------
    assignment : dict[str, str]
        Candidate mapping {flight_id: gate_id}.
    instance : ProblemInstance
        Problem instance data contract.
    mode : str
        Delay mode: 'expected', 'worst_case', 'realized'.
    use_turnaround : bool
        Whether to calculate turnaround occupancy.
    default_turnaround_time_min : Optional[int]
        Default turnaround time if not specified.
    precomputed_windows : Optional[dict[str, tuple[int, int]]]
        Cached flight occupancy intervals for high performance.

    Returns
    -------
    bool
        True if all hard constraints are satisfied, False otherwise.
    """
    gate_map = {g.gate_id: g for g in instance.gates}
    flight_map = {f.flight_id: f for f in instance.flights}
    occ_by_gate: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

    flight_to_pair = _build_chain_pairs(instance)
    def_turn = (
        default_turnaround_time_min
        if default_turnaround_time_min is not None
        else getattr(instance.cost_params, "default_turnaround_time_min", 45)
    )

    # 1. Ràng buộc từng chuyến bay
    for f in instance.flights:
        g_id = assignment.get(f.flight_id)
        if not g_id or g_id not in gate_map:
            return False

        gate = gate_map[g_id]

        # Ràng buộc 1: Tương thích loại tàu bay
        if not is_aircraft_compatible(f.aircraft_type, gate.compatible_types):
            return False

        # Xác định khoảng thời gian chiếm dụng cổng
        if precomputed_windows and f.flight_id in precomputed_windows:
            start_i, end_i = precomputed_windows[f.flight_id]
        else:
            turn_t = f.turnaround_time_min if f.turnaround_time_min is not None else (def_turn if use_turnaround else None)
            paired = flight_to_pair.get(f.flight_id)
            start_i, end_i = occupancy_window(
                flight=f,
                buffer_time_min=instance.cost_params.buffer_time_min,
                mode=mode,
                turnaround_time_min=turn_t,
                paired_flight=paired,
            )

        # Ràng buộc 2: Khung giờ hoạt động của cổng
        if start_i < gate.available_from_min or end_i > gate.available_to_min:
            return False

        # Ràng buộc 3: Không chồng lấn thời gian tại cùng một cổng
        for (s, e, other_fid) in occ_by_gate[g_id]:
            if max(start_i, s) < min(end_i, e):  # Xung đột thời gian
                return False

        occ_by_gate[g_id].append((start_i, end_i, f.flight_id))

    # Ràng buộc 4: Ghép cặp chuỗi quay đầu phải dùng chung cổng
    for arr_id, dep_f in flight_to_pair.items():
        if arr_id in assignment and dep_f.flight_id in assignment:
            if assignment[arr_id] != assignment[dep_f.flight_id]:
                return False

    return True


def neighbor(
    assignment: dict[str, str],
    instance: ProblemInstance,
    rng: random.Random,
    flight_to_pair: Optional[dict[str, Flight]] = None,
) -> dict[str, str]:
    """Generate a candidate neighbor solution by mutating one flight's gate assignment.

    Supports:
    - 50% probability: Single flight / turnaround pair mutation
    - 50% probability: Pairwise gate swap between two compatible flights
    """
    new_assignment = dict(assignment)
    if not instance.flights or not instance.gates:
        return new_assignment

    gate_map = {g.gate_id: g for g in instance.gates}
    f_pairs = flight_to_pair if flight_to_pair is not None else _build_chain_pairs(instance)

    # 1. Thử nghiệm đổi chéo cổng (Gate Swap) nếu có từ 2 chuyến bay trở lên
    if len(instance.flights) >= 2 and rng.random() < 0.5:
        f1, f2 = rng.sample(instance.flights, 2)
        g1_id, g2_id = assignment.get(f1.flight_id), assignment.get(f2.flight_id)
        if g1_id and g2_id and g1_id != g2_id:
            gate1, gate2 = gate_map.get(g1_id), gate_map.get(g2_id)
            if gate1 and gate2:
                # Kiểm tra tính tương thích chéo
                comp1 = is_aircraft_compatible(f1.aircraft_type, gate2.compatible_types)
                comp2 = is_aircraft_compatible(f2.aircraft_type, gate1.compatible_types)
                if comp1 and comp2:
                    new_assignment[f1.flight_id] = g2_id
                    new_assignment[f2.flight_id] = g1_id
                    # Đồng bộ chuyến đối ứng nếu có
                    p1 = f_pairs.get(f1.flight_id)
                    p2 = f_pairs.get(f2.flight_id)
                    if p1 and is_aircraft_compatible(p1.aircraft_type, gate2.compatible_types):
                        new_assignment[p1.flight_id] = g2_id
                    if p2 and is_aircraft_compatible(p2.aircraft_type, gate1.compatible_types):
                        new_assignment[p2.flight_id] = g1_id
                    return new_assignment

    # 2. Đột biến cổng đơn lẻ (Single Flight Mutation)
    f = rng.choice(instance.flights)
    paired = f_pairs.get(f.flight_id)
    compatible_gates = [
        g.gate_id
        for g in instance.gates
        if is_aircraft_compatible(f.aircraft_type, g.compatible_types)
        and (paired is None or is_aircraft_compatible(paired.aircraft_type, g.compatible_types))
    ]
    if compatible_gates:
        cur_g = assignment.get(f.flight_id)
        other_gates = [gid for gid in compatible_gates if gid != cur_g]
        chosen_g = rng.choice(other_gates if other_gates else compatible_gates)
        new_assignment[f.flight_id] = chosen_g
        if paired is not None:
            new_assignment[paired.flight_id] = chosen_g

    return new_assignment


def simulated_annealing(
    initial_assignment: dict[str, str],
    instance: ProblemInstance,
    weights: Sequence[float] = (1.0, 1.0, 0.5, 1.0),
    t0: float = 100.0,
    alpha: float = 0.95,
    iterations: int = 2000,
    seed: int = 42,
    mode: str = "expected",
    use_turnaround: bool = False,
    default_turnaround_time_min: Optional[int] = None,
    max_time_sec: Optional[float] = None,
) -> SimulatedAnnealingResult:
    """Perform Simulated Annealing metaheuristic starting from an initial feasible assignment.

    Parameters
    ----------
    initial_assignment : dict[str, str]
        Starting feasible gate assignment mapping.
    instance : ProblemInstance
        Problem instance data contract.
    weights : Sequence[float]
        Objective weights (w1, w2, w3, w4).
    t0 : float
        Initial temperature.
    alpha : float
        Cooling factor (0 < alpha < 1).
    iterations : int
        Number of SA iterations.
    seed : int
        RNG seed for reproducibility.
    mode : str
        Delay prediction mode ('expected', 'worst_case', 'realized').
    use_turnaround : bool
        Whether to calculate turnaround occupancy.
    default_turnaround_time_min : Optional[int]
        Default turnaround duration.
    max_time_sec : Optional[float]
        Optional wall-time cutoff in seconds.

    Returns
    -------
    SimulatedAnnealingResult
        Tuple subclass (assignment, best_cost) with extended metadata properties.
    """
    t_start = time.perf_counter()

    flight_to_pair = _build_chain_pairs(instance)
    def_turn = (
        default_turnaround_time_min
        if default_turnaround_time_min is not None
        else getattr(instance.cost_params, "default_turnaround_time_min", 45)
    )

    # 1. Tiền tính toán trước cửa sổ chiếm dụng cổng cho toàn bộ chuyến bay
    windows: dict[str, tuple[int, int]] = {}
    flight_map: dict[str, Flight] = {f.flight_id: f for f in instance.flights}
    gate_map: dict[str, Gate] = {g.gate_id: g for g in instance.gates}

    for f in instance.flights:
        turn_t = f.turnaround_time_min if f.turnaround_time_min is not None else (def_turn if use_turnaround else None)
        paired = flight_to_pair.get(f.flight_id)
        windows[f.flight_id] = occupancy_window(
            flight=f,
            buffer_time_min=instance.cost_params.buffer_time_min,
            mode=mode,
            turnaround_time_min=turn_t,
            paired_flight=paired,
        )

    # Kiểm tra tính khả thi của lời giải ban đầu
    if not is_feasible(
        initial_assignment,
        instance,
        mode=mode,
        use_turnaround=use_turnaround,
        default_turnaround_time_min=default_turnaround_time_min,
        precomputed_windows=windows,
    ):
        raise ValueError("Initial assignment passed to Simulated Annealing is not feasible")

    rng = random.Random(seed)
    current = dict(initial_assignment)
    current_cost = soft_cost(current, instance, weights)
    init_cost = current_cost
    best, best_cost = current, current_cost
    T = t0

    # Duy trì cấu trúc tra cứu nhanh danh sách chuyến tại từng cổng: {gate_id: set[flight_id]}
    gate_flights: dict[str, set[str]] = defaultdict(set)
    for fid, gid in current.items():
        gate_flights[gid].add(fid)

    def check_gate_feasibility(g_id: str, f_ids: set[str]) -> bool:
        """Kiểm tra nhanh tính khả thi cục bộ trên một cổng đơn lẻ."""
        gate = gate_map.get(g_id)
        if not gate:
            return False
        intervals: list[tuple[int, int]] = []
        for fid in f_ids:
            f = flight_map[fid]
            if not is_aircraft_compatible(f.aircraft_type, gate.compatible_types):
                return False
            s, e = windows[fid]
            if s < gate.available_from_min or e > gate.available_to_min:
                return False
            for (s_prev, e_prev) in intervals:
                if max(s, s_prev) < min(e, e_prev):
                    return False
            intervals.append((s, e))
        return True

    cost_history = [init_cost]
    actual_iterations = 0

    for it in range(iterations):
        actual_iterations = it + 1
        if max_time_sec and (time.perf_counter() - t_start) >= max_time_sec:
            break

        cand = neighbor(current, instance, rng, flight_to_pair=flight_to_pair)

        # Xác định các cổng bị thay đổi để kiểm tra nhanh cục bộ
        changed_gates: set[str] = set()
        for fid, new_gid in cand.items():
            old_gid = current.get(fid)
            if old_gid != new_gid:
                changed_gates.add(new_gid)

        # Kiểm tra tính khả thi của các cổng bị đột biến
        cand_feasible = True
        for g_id in changed_gates:
            target_fids = {fid for fid, gid in cand.items() if gid == g_id}
            if not check_gate_feasibility(g_id, target_fids):
                cand_feasible = False
                break

        if not cand_feasible:
            continue

        cand_cost = soft_cost(cand, instance, weights)
        delta = cand_cost - current_cost

        # Tiêu chuẩn Metropolis-Hastings
        if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-6)):
            current, current_cost = cand, cand_cost
            gate_flights.clear()
            for fid, gid in current.items():
                gate_flights[gid].add(fid)

            if current_cost < best_cost:
                best, best_cost = current, current_cost

        if it % 100 == 0:
            cost_history.append(best_cost)

        T *= alpha

    solve_time = time.perf_counter() - t_start

    # Đảm bảo lời giải tốt nhất thỏa mãn 100% ràng buộc cứng
    assert is_feasible(
        best,
        instance,
        mode=mode,
        use_turnaround=use_turnaround,
        default_turnaround_time_min=default_turnaround_time_min,
        precomputed_windows=windows,
    ), "Final SA solution violated hard constraints"

    logger.info(
        "Simulated Annealing completed in %.3fs: initial_cost=%.2f, best_cost=%.2f (improvement=%.2f, iterations=%d)",
        solve_time,
        init_cost,
        best_cost,
        init_cost - best_cost,
        actual_iterations,
    )

    return SimulatedAnnealingResult(
        assignment=best,
        best_cost=best_cost,
        initial_cost=init_cost,
        solve_time_sec=solve_time,
        iterations=actual_iterations,
        status="FEASIBLE" if best else "INFEASIBLE",
        cost_history=cost_history,
    )


def simulated_annealing_from_dataframe(
    df: pd.DataFrame,
    num_gates: int = 20,
    weights: Sequence[float] = (1.0, 1.0, 0.5, 1.0),
    iterations: int = 2000,
    t0: float = 100.0,
    alpha: float = 0.95,
    seed: int = 42,
    mode: str = "expected",
    initial_assignment: Optional[dict[str, str]] = None,
    return_schedule: bool = True,
    gates: Optional[list[Gate]] = None,
    airport: str = "ATL",
    planning_date: str = "2024-01-01",
) -> tuple[dict[str, str], float, float, pd.DataFrame] | SimulatedAnnealingResult:
    """Chạy tối ưu hóa Simulated Annealing trực tiếp từ DataFrame.

    Tự động khởi tạo nghiệm khả thi ban đầu bằng Greedy Baseline nếu initial_assignment=None.
    """
    from src.optimization.cp_sat_solver import dataframe_to_problem_instance
    from src.optimization.greedy_baseline import greedy_assign

    instance = dataframe_to_problem_instance(
        df=df,
        num_gates=num_gates,
        gates=gates,
        airport=airport,
        planning_date=planning_date,
    )

    if initial_assignment is None:
        init_res = greedy_assign(instance, mode=mode, allow_unassigned=True)
        if len(init_res) < len(instance.flights):
            logger.warning(
                "Greedy could not assign all %d flights (assigned %d), adjusting gates or parameters may be required",
                len(instance.flights),
                len(init_res),
            )
        initial_assignment = init_res.assignment

    result = simulated_annealing(
        initial_assignment=initial_assignment,
        instance=instance,
        weights=weights,
        t0=t0,
        alpha=alpha,
        iterations=iterations,
        seed=seed,
        mode=mode,
    )

    if return_schedule:
        records = []
        for f in instance.flights:
            g_id = result.assignment.get(f.flight_id)
            w = occupancy_window(f, instance.cost_params.buffer_time_min, mode=mode)
            records.append({
                "flight_id": f.flight_id,
                "direction": f.direction,
                "aircraft_type": f.aircraft_type,
                "current_gate": f.current_gate,
                "assigned_gate": g_id,
                "is_reassigned": (f.current_gate is not None) and (g_id != f.current_gate),
                "occupancy_start_min": w[0],
                "occupancy_end_min": w[1],
                "occupancy_duration_min": w[1] - w[0],
            })
        schedule_df = pd.DataFrame(records)
        return result.assignment, result.best_cost, result.solve_time_sec, schedule_df

    return result
