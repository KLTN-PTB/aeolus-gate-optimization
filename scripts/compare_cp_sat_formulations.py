"""Formulation Comparison Benchmarking Script for CP-SAT (Phase P06).

Compares 4 formulations on identical scenarios:
- F0: Baseline Dense Pairwise
- F1: Sparse Variables + Sparse Pairwise
- F2: Sparse Variables + AddNoOverlap / AddCumulative
- F3: Sparse Variables + AddNoOverlap + Greedy Warm Start
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psutil
from ortools.sat.python import cp_model

from src.optimization.benchmark_harness import (
    BenchmarkTier,
    generate_synthetic_benchmark_scenario,
    get_environment_info,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def solve_formulation(
    flights: list[Flight],
    gates: list[Gate],
    formulation_type: str,
    time_limit_seconds: float = 2.0,
    seed: int = 202601,
) -> dict:
    proc = psutil.Process(os.getpid())
    tracemalloc.start()
    t0 = time.perf_counter()
    t0_ns = time.perf_counter_ns()

    n_flights = len(flights)
    gate_list = list(gates)
    has_overflow = any(g.is_overflow for g in gate_list)
    if not has_overflow:
        overflow_gate = Gate(
            gate_id="OVERFLOW_APRON",
            gate_index=len(gate_list),
            resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
            capacity=math.inf,
            is_overflow=True,
        )
        gate_list.append(overflow_gate)

    n_gates = len(gate_list)
    model = cp_model.CpModel()
    sf = 100
    config = GateOptimizationConfig(time_limit_seconds=time_limit_seconds, random_seed=seed)

    t_build_start_ns = time.perf_counter_ns()

    # 1. Variables
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    eligible_map: dict[int, list[int]] = {}

    if formulation_type == "F0_BASELINE_DENSE":
        for f_idx in range(n_flights):
            eligible_map[f_idx] = list(range(n_gates))
            for g_idx in range(n_gates):
                x[f_idx, g_idx] = model.NewBoolVar(f"x_{f_idx}_{g_idx}")
    else:
        # Sparse variables
        for f_idx, fl in enumerate(flights):
            candidates = []
            for g_idx, gate in enumerate(gate_list):
                if (
                    gate.is_compatible_carrier(fl.carrier)
                    and gate.is_compatible_aircraft(fl.aircraft_type)
                    and gate.is_available_during(fl.time_window)
                ):
                    candidates.append(g_idx)
                    x[f_idx, g_idx] = model.NewBoolVar(f"x_{f_idx}_{g_idx}")
            eligible_map[f_idx] = candidates

    # 2. Assignment constraints: sum_g x[f, g] == 1
    for f_idx in range(n_flights):
        cand = eligible_map[f_idx]
        if not cand:
            # Infeasible problem
            model.Add(0 == 1)
        else:
            model.Add(sum(x[f_idx, g_idx] for g_idx in cand) == 1)

    # 3. Compatibility & availability constraints (only needed for F0)
    if formulation_type == "F0_BASELINE_DENSE":
        for f_idx, fl in enumerate(flights):
            for g_idx, gate in enumerate(gate_list):
                if not gate.is_available_during(fl.time_window):
                    model.Add(x[f_idx, g_idx] == 0)
                elif not gate.is_compatible_carrier(fl.carrier) or not gate.is_compatible_aircraft(fl.aircraft_type):
                    model.Add(x[f_idx, g_idx] == 0)

    # 4. Overlap constraints
    if formulation_type in ("F0_BASELINE_DENSE", "F1_SPARSE_PAIRWISE"):
        # Pairwise constraints
        sorted_indices = sorted(range(n_flights), key=lambda idx: flights[idx].time_window.start_min)
        overlapping_pairs = []
        for a, i in enumerate(sorted_indices):
            w_i = flights[i].time_window
            for b in range(a + 1, n_flights):
                j = sorted_indices[b]
                if flights[j].time_window.start_min >= w_i.end_min:
                    break
                if w_i.overlaps(flights[j].time_window):
                    overlapping_pairs.append((i, j))

        for g_idx, gate in enumerate(gate_list):
            if gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or gate.is_unbounded:
                continue
            if gate.capacity == 1:
                for i, j in overlapping_pairs:
                    if (i, g_idx) in x and (j, g_idx) in x:
                        model.Add(x[i, g_idx] + x[j, g_idx] <= 1)
            elif math.isfinite(gate.capacity) and gate.capacity > 1:
                cap = int(gate.capacity)
                seen_subsets = set()
                for i in range(n_flights):
                    t = flights[i].time_window.start_min
                    active_tuple = tuple(
                        k for k in range(n_flights)
                        if flights[k].time_window.start_min <= t < flights[k].time_window.end_min and (k, g_idx) in x
                    )
                    if len(active_tuple) > cap and active_tuple not in seen_subsets:
                        seen_subsets.add(active_tuple)
                        model.Add(sum(x[k, g_idx] for k in active_tuple) <= cap)

    elif formulation_type in ("F2_SPARSE_INTERVAL", "F3_SPARSE_INTERVAL_WARMSTART"):
        # Native interval constraints via AddNoOverlap & AddCumulative
        for g_idx, gate in enumerate(gate_list):
            if gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or gate.is_unbounded:
                continue

            gate_intervals = []
            for f_idx in range(n_flights):
                if (f_idx, g_idx) in x:
                    fl = flights[f_idx]
                    start = fl.time_window.start_min
                    end = fl.time_window.end_min
                    size = max(1, end - start)
                    interval = model.NewOptionalIntervalVar(
                        start, size, end, x[f_idx, g_idx], f"iv_{f_idx}_{g_idx}"
                    )
                    gate_intervals.append(interval)

            if gate_intervals:
                if gate.capacity == 1:
                    model.AddNoOverlap(gate_intervals)
                elif math.isfinite(gate.capacity) and gate.capacity > 1:
                    demands = [1] * len(gate_intervals)
                    model.AddCumulative(gate_intervals, demands, int(gate.capacity))

    # 5. Objective
    objective_terms = []
    for f_idx, fl in enumerate(flights):
        nom_gate_id = fl.nominal_gate_id
        for g_idx in eligible_map[f_idx]:
            gate = gate_list[g_idx]
            var = x[f_idx, g_idx]
            cost = 0.0
            if not gate.is_overflow:
                if nom_gate_id is not None and gate.gate_id != nom_gate_id:
                    cost += config.reassignment_weight
            else:
                cost += config.overflow_weight
                if nom_gate_id is not None:
                    cost += config.reassignment_weight

            int_coeff = int(round(cost * sf))
            if int_coeff != 0:
                objective_terms.append(int_coeff * var)

    if objective_terms:
        model.Minimize(sum(objective_terms))

    # 6. Optional Warm Start (F3)
    warm_start_time_ms = 0.0
    if formulation_type == "F3_SPARSE_INTERVAL_WARMSTART":
        t_ws0 = time.perf_counter()
        greedy_solver = DeterministicGreedyGateSolver(config=config)
        greedy_res = greedy_solver.solve(flights, gate_list, allow_overflow=True)
        warm_start_time_ms = (time.perf_counter() - t_ws0) * 1000.0

        if greedy_res.feasible:
            gate_to_idx = {g.gate_id: idx for idx, g in enumerate(gate_list)}
            for fl in flights:
                asgn = greedy_res.assignments.get(fl.flight_id)
                if asgn is not None and asgn.gate_id in gate_to_idx:
                    g_idx = gate_to_idx[asgn.gate_id]
                    if (fl.flight_index, g_idx) in x:
                        model.AddHint(x[fl.flight_index, g_idx], 1)

    t_build_end_ns = time.perf_counter_ns()
    model_construction_ms = (t_build_end_ns - t_build_start_ns) / 1_000_000.0 + warm_start_time_ms

    # 7. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = False

    t_search_start_ns = time.perf_counter_ns()
    raw_status = solver.Solve(model)
    t_search_end_ns = time.perf_counter_ns()
    search_time_ms = (t_search_end_ns - t_search_start_ns) / 1_000_000.0

    _, peak_traced = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    try:
        peak_wset_mb = proc.memory_info().peak_wset / (1024.0 * 1024.0)
    except Exception:
        peak_wset_mb = peak_traced / (1024.0 * 1024.0)

    # 8. Extract assignments and verify
    is_feasible = raw_status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assignments: dict[str, GateAssignment] = {}
    if is_feasible:
        for f_idx, fl in enumerate(flights):
            for g_idx in eligible_map[f_idx]:
                if solver.BooleanValue(x[f_idx, g_idx]):
                    gate = gate_list[g_idx]
                    assignments[fl.flight_id] = GateAssignment(
                        flight_id=fl.flight_id,
                        gate_id=gate.gate_id,
                        flight_index=f_idx,
                        gate_index=g_idx,
                        is_overflow=gate.is_overflow,
                        is_reassignment=bool(fl.nominal_gate_id and gate.gate_id != fl.nominal_gate_id),
                        occupancy_start_min=fl.time_window.start_min,
                        occupancy_end_min=fl.time_window.end_min,
                    )
                    break

    diag = verify_hard_constraints_independently(flights=flights, gates=gate_list, assignments=assignments) if is_feasible else None
    verified_feasible = bool(is_feasible and diag and diag.is_valid and len(assignments) == n_flights)

    eval_res = evaluate_gate_assignment(
        assignments=assignments,
        flights=flights,
        gates=gate_list,
        config=config,
    ) if verified_feasible else None

    total_wall_clock_ms = (time.perf_counter_ns() - t0_ns) / 1_000_000.0

    status_str = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(raw_status, "UNKNOWN")

    return {
        "formulation": formulation_type,
        "n_flights": n_flights,
        "n_gates": n_gates,
        "n_variables": len(x),
        "model_construction_ms": round(model_construction_ms, 2),
        "search_time_ms": round(search_time_ms, 2),
        "total_wall_clock_ms": round(total_wall_clock_ms, 2),
        "peak_memory_mb": round(peak_wset_mb, 2),
        "status": status_str,
        "feasible": verified_feasible,
        "objective_value": round(eval_res.objective_value, 4) if eval_res else None,
        "best_bound": round(solver.BestObjectiveBound() / sf, 4) if is_feasible and objective_terms else None,
    }


def main() -> None:
    print("=" * 80)
    print("CP-SAT FORMULATION BENCHMARK: F0 vs F1 vs F2 vs F3")
    print("=" * 80)

    test_scales = [
        (20, 6, 2),
        (100, 20, 3),
        (200, 30, 5),
        (300, 50, 5),
    ]

    formulations = [
        "F0_BASELINE_DENSE",
        "F1_SPARSE_PAIRWISE",
        "F2_SPARSE_INTERVAL",
        "F3_SPARSE_INTERVAL_WARMSTART",
    ]

    all_results = []

    for n_fl, n_cg, n_rs in test_scales:
        print(f"\nEvaluating Scale: {n_fl} flights x {n_cg} contact + {n_rs} remote gates:")
        flights, gates = generate_synthetic_benchmark_scenario(
            tier=BenchmarkTier.TIER_B,
            n_flights=n_fl,
            n_contact_gates=n_cg,
            n_remote_stands=n_rs,
            seed=202601,
        )

        for f_type in formulations:
            print(f"  Running {f_type}...", end="", flush=True)
            res = solve_formulation(flights, gates, f_type, time_limit_seconds=2.0)
            all_results.append(res)
            print(f" -> Status: {res['status']} | Feasible: {res['feasible']} | Build: {res['model_construction_ms']:.1f}ms | Search: {res['search_time_ms']:.1f}ms | Obj: {res['objective_value']}")

    out_file = ROOT / "artifacts" / "remediation" / "cp_sat" / "formulation_comparison.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFormulation comparison saved to: {out_file}")


if __name__ == "__main__":
    main()
