"""Scalability benchmark across problem scales comparing CP-SAT formulations (P06).

Measures:
- Model construction time (ms)
- Search time (ms)
- Total wall-clock time (ms)
- Peak memory (MB)
- Variables and constraints counts
- Feasibility, solver status, optimality proven, objective values

Outputs:
artifacts/remediation/cp_sat/scalability_results.csv
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil

from src.optimization.benchmark_harness import (
    BenchmarkTier,
    generate_synthetic_benchmark_scenario,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


def run_benchmark():
    out_dir = Path("artifacts/remediation/cp_sat")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_file = out_dir / "scalability_results.csv"

    scales = [
        # (scale_label, n_flights, n_contact_gates, n_remote_stands, run_dense)
        ("100x20", 100, 18, 2, True),
        ("200x30", 200, 28, 2, True),
        ("300x50", 300, 48, 2, True),
        ("500x50", 500, 48, 2, True),
        ("750x50", 750, 48, 2, False),  # dense pairwise omitted to prevent 2M+ constraint OOM
        ("1000x50", 1000, 48, 2, False),
        ("1500x50", 1500, 48, 2, False),
    ]

    time_limit = 10.0  # 10s search budget per run to ensure fast, responsive benchmark
    proc = psutil.Process(os.getpid())

    rows = []

    print(f"{'Scale':<10} | {'Formulation':<20} | {'Vars':<7} | {'Constrs':<9} | {'Build(ms)':<10} | {'Search(ms)':<10} | {'Total(ms)':<10} | {'RAM(MB)':<8} | {'Status':<10} | {'Opt Proven':<10}")
    print("-" * 125)

    for scale_label, n_fl, n_cg, n_rs, run_dense in scales:
        flights, gates = generate_synthetic_benchmark_scenario(
            tier=BenchmarkTier.TIER_B,
            n_flights=n_fl,
            n_contact_gates=n_cg,
            n_remote_stands=n_rs,
            seed=202601,
        )
        n_gates_total = len(gates)

        formulations_to_test = []
        if run_dense:
            formulations_to_test.append(("dense_pairwise", False))
        formulations_to_test.append(("sparse_interval", False))
        formulations_to_test.append(("sparse_interval", True))  # with greedy warm-start

        for form, use_ws in formulations_to_test:
            cfg = GateOptimizationConfig(
                scale_factor=100,
                num_search_workers=2,
                time_limit_seconds=time_limit,
                cp_sat_formulation=form,
                cp_sat_use_warm_start=use_ws,
                cp_sat_fallback_to_greedy=False,
            )

            tracemalloc.start()
            ram_start = proc.memory_info().rss / (1024 * 1024)
            t0 = time.perf_counter()

            solver = CPSatGateSolver(config=cfg)
            res = solver.solve(flights, gates, allow_overflow=True)

            t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_ram_mb = round(peak_bytes / (1024 * 1024), 2)

            solver_cfg = res.solver_configuration
            n_vars = solver_cfg.get("n_variables", 0)
            n_constrs = solver_cfg.get("n_constraints", 0)
            build_ms = solver_cfg.get("model_construction_ms", 0.0)
            search_ms = solver_cfg.get("search_time_ms", 0.0)
            total_wall_ms = solver_cfg.get("total_wall_clock_ms", t_elapsed_ms)
            status = res.status
            opt_proven = res.optimality_proven
            obj = res.objective_value

            label = f"{form}+WS" if use_ws else form

            print(
                f"{scale_label:<10} | {label:<20} | {n_vars:<7} | {n_constrs:<9} | {build_ms:<10.1f} | {search_ms:<10.1f} | {total_wall_ms:<10.1f} | {peak_ram_mb:<8.1f} | {status:<10} | {str(opt_proven):<10}"
            )

            rows.append({
                "scale": scale_label,
                "n_flights": n_fl,
                "n_gates": n_gates_total,
                "formulation": form,
                "warm_start": use_ws,
                "n_variables": n_vars,
                "n_constraints": n_constrs,
                "build_time_ms": build_ms,
                "search_time_ms": search_ms,
                "total_wall_clock_ms": total_wall_ms,
                "peak_memory_mb": peak_ram_mb,
                "status": status,
                "feasible": res.feasible,
                "optimality_proven": opt_proven,
                "objective_value": round(obj, 2) if obj is not None else "",
                "time_limit_sec": time_limit,
            })

    # Save to CSV
    fieldnames = [
        "scale",
        "n_flights",
        "n_gates",
        "formulation",
        "warm_start",
        "n_variables",
        "n_constraints",
        "build_time_ms",
        "search_time_ms",
        "total_wall_clock_ms",
        "peak_memory_mb",
        "status",
        "feasible",
        "optimality_proven",
        "objective_value",
        "time_limit_sec",
    ]

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("-" * 125)
    print(f"Benchmark results successfully written to {csv_file}")


if __name__ == "__main__":
    run_benchmark()
