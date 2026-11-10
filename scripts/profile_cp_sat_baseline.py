"""Baseline Root Cause Profiler for CP-SAT Solver (Phase P06 Step 1).

Measures:
- n_flights, n_gates
- n_eligible_pairs, n_overlap_pairs
- n_binary_vars, n_constraints
- time_create_vars_ms, time_add_constraints_ms
- model_construction_ms, search_time_ms, total_wall_clock_ms
- peak_memory_mb, solver_status, objective_value, best_bound
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

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import psutil

from src.optimization.benchmark_harness import (
    BenchmarkTier,
    generate_synthetic_benchmark_scenario,
    get_environment_info,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import GateResourceType
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


def profile_baseline_scale(n_flights: int, n_contact_gates: int, n_remote_stands: int = 2) -> dict:
    proc = psutil.Process(os.getpid())
    tracemalloc.start()

    flights, gates = generate_synthetic_benchmark_scenario(
        tier=BenchmarkTier.TIER_B,
        n_flights=n_flights,
        n_contact_gates=n_contact_gates,
        n_remote_stands=n_remote_stands,
        seed=202601,
    )
    n_gates = len(gates)

    # 1. Count eligible pairs
    eligible_pairs = 0
    for fl in flights:
        for g in gates:
            if g.is_compatible_carrier(fl.carrier) and g.is_compatible_aircraft(fl.aircraft_type) and g.is_available_during(fl.time_window):
                eligible_pairs += 1

    # 2. Count overlapping pairs
    sorted_fl = sorted(flights, key=lambda f: f.time_window.start_min)
    n_fl = len(sorted_fl)
    overlap_pairs = 0
    for a in range(n_fl):
        w_i = sorted_fl[a].time_window
        for b in range(a + 1, n_fl):
            if sorted_fl[b].time_window.start_min >= w_i.end_min:
                break
            if w_i.overlaps(sorted_fl[b].time_window):
                overlap_pairs += 1

    # 3. Time creation of variables vs constraints in current baseline
    cfg = GateOptimizationConfig(
        time_limit_seconds=2.0,
        random_seed=202601,
        enforce_remote_capacity=True,
    )
    solver = CPSatGateSolver(config=cfg)

    # Solve and record
    res = solver.solve(flights, gates, allow_overflow=True)

    _, peak_traced = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    try:
        peak_wset_mb = proc.memory_info().peak_wset / (1024.0 * 1024.0)
    except Exception:
        peak_wset_mb = peak_traced / (1024.0 * 1024.0)

    cfg_stats = res.solver_configuration or {}
    model_construction_ms = cfg_stats.get("model_construction_ms", 0.0)
    search_time_ms = cfg_stats.get("search_time_ms", 0.0)
    total_wall_clock_ms = res.runtime_ms

    # Theoretical constraint counts in baseline:
    # - 1 assignment per flight = n_flights
    # - overlap mutexes per discrete gate = overlap_pairs * n_discrete_gates
    # - availability = n_flights * n_gates
    # - compatibility = n_flights * n_gates
    # - overflow cost/objective
    n_discrete_gates = sum(1 for g in gates if g.capacity == 1 and not g.is_unbounded)
    est_constraints = n_flights + (overlap_pairs * n_discrete_gates)

    return {
        "n_flights": n_flights,
        "n_gates": n_gates,
        "n_discrete_gates": n_discrete_gates,
        "n_eligible_pairs": eligible_pairs,
        "n_cartesian_pairs": n_flights * n_gates,
        "sparsity_ratio": round(eligible_pairs / (n_flights * n_gates), 4),
        "n_overlap_pairs": overlap_pairs,
        "n_binary_vars": n_flights * n_gates,
        "n_constraints_estimated": est_constraints,
        "model_construction_ms": round(model_construction_ms, 2),
        "search_time_ms": round(search_time_ms, 2),
        "total_wall_clock_ms": round(total_wall_clock_ms, 2),
        "peak_memory_mb": round(peak_wset_mb, 2),
        "status": res.status,
        "feasible": res.feasible,
        "objective_value": res.objective_value if res.feasible else None,
        "best_bound": res.best_bound,
    }


def main() -> None:
    scales = [
        (20, 6, 2),
        (100, 20, 3),
        (200, 30, 5),
        (300, 50, 5),
        (500, 50, 5),
    ]

    results = []
    print("=" * 80)
    print("STARTING CP-SAT BASELINE ROOT CAUSE PROFILING")
    print("=" * 80)

    for n_fl, n_cg, n_rs in scales:
        print(f"Profiling scale {n_fl} flights x {n_cg} contact gates + {n_rs} remote stands...")
        stats = profile_baseline_scale(n_fl, n_cg, n_rs)
        results.append(stats)
        print(f"  -> Vars: {stats['n_binary_vars']} | Overlaps: {stats['n_overlap_pairs']} | Est Constraints: {stats['n_constraints_estimated']}")
        print(f"  -> Build: {stats['model_construction_ms']:.2f}ms | Search: {stats['search_time_ms']:.2f}ms | Total: {stats['total_wall_clock_ms']:.2f}ms")
        print(f"  -> Status: {stats['status']} | Feasible: {stats['feasible']} | Objective: {stats['objective_value']}")
        print("-" * 60)

    out_dir = ROOT / "artifacts" / "remediation" / "cp_sat"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "resource_profile.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "environment": get_environment_info(),
                "baseline_profiles": results,
            },
            f,
            indent=2,
        )
    print(f"Baseline profiling saved to: {out_file}")


if __name__ == "__main__":
    main()
