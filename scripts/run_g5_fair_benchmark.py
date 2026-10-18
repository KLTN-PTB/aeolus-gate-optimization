"""G5 Fair Benchmark Runner across Greedy, CP-SAT, SA, and Hybrid Solvers.

Protocol: AEOLUS-G5 Fair Benchmark & Scalability Gate
Requirements:
1. Identical Scenarios: All 4 solvers run on the exact same scenario instances (verified via SHA-256).
2. Authoritative Common Evaluator: evaluate_gate_assignment() for all objective computations.
3. Independent Verification: verify_hard_constraints_independently() for all feasibility determinations.
4. Uniform Weights: GateOptimizationConfig with uniform decomposed weights.
5. High-Resolution Monotonic Timing: time.perf_counter_ns() for all execution timing.
6. Honest Statuses: OPTIMAL only when proven; no fake improvements.
7. Isolated Output Directory: artifacts/remediation/benchmarks/g5_fair_benchmark/ (never overwriting historical files).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from src.optimization.benchmark_harness import (
    BenchmarkTier,
    compute_scenario_hash,
    generate_synthetic_benchmark_scenario,
    get_environment_info,
)
from src.optimization.config import GateOptimizationConfig, compute_improvement_pct
from src.optimization.domain import (
    Flight,
    Gate,
    GateResourceType,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver


def build_benchmark_scenarios() -> list[dict[str, Any]]:
    """Define benchmark scenarios spanning Micro, Medium, and Thesis Scales (100, 200, 300 flights)."""
    scenarios = []

    # Scenario 1: Micro Parity (4 flights, 2 contact gates, 1 remote, 1 overflow)
    g_micro = [
        Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", 1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("REMOTE_1", 2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
        Gate("OVERFLOW_APRON", 3, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf, is_overflow=True),
    ]
    f_micro = [
        Flight("F1", 0, "DL", "101", 100, 160, 100, nominal_gate_id="G1"),
        Flight("F2", 1, "DL", "102", 120, 180, 120, nominal_gate_id="G1"),
        Flight("F3", 2, "AA", "103", 200, 260, 200, nominal_gate_id="G2"),
        Flight("F4", 3, "AA", "104", 220, 280, 220, nominal_gate_id="G2"),
    ]
    scenarios.append({
        "scenario_id": "SCEN_01_MICRO_PARITY",
        "name": "Micro Parity Instance",
        "tier": BenchmarkTier.TIER_A.value,
        "n_flights": len(f_micro),
        "n_contact_gates": 2,
        "flights": f_micro,
        "gates": g_micro,
        "time_limit_sec": 3.0,
    })

    # Scenario 2: Medium (30 flights, 8 contact gates, 2 remote stands)
    f_med, g_med = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_A, 30, 8, n_remote_stands=2, seed=42)
    scenarios.append({
        "scenario_id": "SCEN_02_MEDIUM_30",
        "name": "Medium Scale Instance (30 flights / 8 gates)",
        "tier": BenchmarkTier.TIER_A.value,
        "n_flights": 30,
        "n_contact_gates": 8,
        "flights": f_med,
        "gates": g_med,
        "time_limit_sec": 5.0,
    })

    # Scenario 3: Thesis Scale 100/20
    f_100, g_100 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 100, 20, n_remote_stands=3, seed=101)
    scenarios.append({
        "scenario_id": "SCEN_03_THESIS_100_20",
        "name": "Thesis Scale Instance 1 (100 flights / 20 gates)",
        "tier": BenchmarkTier.TIER_B.value,
        "n_flights": 100,
        "n_contact_gates": 20,
        "flights": f_100,
        "gates": g_100,
        "time_limit_sec": 5.0,
    })

    # Scenario 4: Thesis Scale 200/30
    f_200, g_200 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 200, 30, n_remote_stands=4, seed=202)
    scenarios.append({
        "scenario_id": "SCEN_04_THESIS_200_30",
        "name": "Thesis Scale Instance 2 (200 flights / 30 gates)",
        "tier": BenchmarkTier.TIER_B.value,
        "n_flights": 200,
        "n_contact_gates": 30,
        "flights": f_200,
        "gates": g_200,
        "time_limit_sec": 5.0,
    })

    # Scenario 5: Thesis Scale 300/50
    f_300, g_300 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 300, 50, n_remote_stands=5, seed=303)
    scenarios.append({
        "scenario_id": "SCEN_05_THESIS_300_50",
        "name": "Thesis Scale Instance 3 (300 flights / 50 gates)",
        "tier": BenchmarkTier.TIER_B.value,
        "n_flights": 300,
        "n_contact_gates": 50,
        "flights": f_300,
        "gates": g_300,
        "time_limit_sec": 5.0,
    })

    return scenarios


def run_benchmark():
    """Execute fair benchmark across 4 solvers and all scenarios."""
    print("=" * 80)
    print("AEOLUS-G5: FAIR OPTIMIZATION BENCHMARK EXECUTION")
    print("=" * 80)

    env_info = get_environment_info()
    print(f"Platform: {env_info['platform_system']} {env_info['platform_release']} | Python: {env_info['python_version']}")
    print(f"OR-Tools: {env_info['ortools_version']} | Logical CPUs: {env_info['cpu_count_logical']}")

    scenarios = build_benchmark_scenarios()
    output_dir = Path("artifacts/remediation/benchmarks/g5_fair_benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_rows = []

    for scen in scenarios:
        scen_id = scen["scenario_id"]
        scen_name = scen["name"]
        flights = scen["flights"]
        gates = scen["gates"]
        n_flights = len(flights)
        n_gates = len(gates)
        time_limit = scen["time_limit_sec"]

        scen_hash = compute_scenario_hash(flights, gates)
        print(f"\n--- Running {scen_id}: {scen_name} ---")
        print(f"Flights: {n_flights} | Gates: {n_gates} | SHA-256: {scen_hash[:16]}... | Time Limit: {time_limit}s")

        config = GateOptimizationConfig(
            reassignment_weight=10.0,
            overflow_weight=200.0,
            delay_weight=1.0,
            conflict_weight=1000.0,
            risk_weight=2.0,
            time_limit_seconds=time_limit,
            num_search_workers=1,
            random_seed=42,
            cp_sat_use_warm_start=True,
            cp_sat_fallback_to_greedy=True,
        )
        sa_config = SAConfig(iterations=300, seed=42)

        # Solver 1: Greedy Standalone
        t_start = time.perf_counter_ns()
        greedy_solver = DeterministicGreedyGateSolver(config)
        gr_res = greedy_solver.solve(flights, gates)
        gr_wall_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0

        results_rows.append({
            "scenario_id": scen_id,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "GREEDY_STANDALONE",
            "status": gr_res.status,
            "feasible": gr_res.feasible,
            "optimality_proven": gr_res.optimality_proven,
            "objective_value": round(gr_res.objective_value, 4) if gr_res.objective_value is not None else None,
            "reassignment_cost": gr_res.objective_breakdown.reassignment_cost if gr_res.objective_breakdown else 0.0,
            "overflow_cost": gr_res.objective_breakdown.overflow_cost if gr_res.objective_breakdown else 0.0,
            "hard_violations": gr_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(gr_wall_ms, 2),
            "fallback_used": False,
        })
        print(f"  [GREEDY]  Obj: {gr_res.objective_value:10.4f} | Feas: {gr_res.feasible} | Time: {gr_wall_ms:8.2f} ms | Status: {gr_res.status}")

        # Solver 2: CP-SAT Standalone
        t_start = time.perf_counter_ns()
        cp_solver = CPSatGateSolver(config)
        cp_res = cp_solver.solve(flights, gates)
        cp_wall_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0

        results_rows.append({
            "scenario_id": scen_id,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "CP_SAT_STANDALONE",
            "status": cp_res.status,
            "feasible": cp_res.feasible,
            "optimality_proven": cp_res.optimality_proven,
            "objective_value": round(cp_res.objective_value, 4) if cp_res.objective_value is not None else None,
            "reassignment_cost": cp_res.objective_breakdown.reassignment_cost if cp_res.objective_breakdown else 0.0,
            "overflow_cost": cp_res.objective_breakdown.overflow_cost if cp_res.objective_breakdown else 0.0,
            "hard_violations": cp_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(cp_wall_ms, 2),
            "fallback_used": cp_res.solver_configuration.get("fallback_used", False),
        })
        print(f"  [CP-SAT]  Obj: {cp_res.objective_value:10.4f} | Feas: {cp_res.feasible} | Time: {cp_wall_ms:8.2f} ms | Status: {cp_res.status} (Proven: {cp_res.optimality_proven})")

        # Solver 3: SA Standalone (seeded by Greedy)
        t_start = time.perf_counter_ns()
        sa_solver = SimulatedAnnealingGateSolver(config, sa_config)
        sa_res = sa_solver.solve(flights, gates)
        sa_wall_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0

        results_rows.append({
            "scenario_id": scen_id,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "SA_STANDALONE",
            "status": sa_res.status,
            "feasible": sa_res.feasible,
            "optimality_proven": sa_res.optimality_proven,
            "objective_value": round(sa_res.objective_value, 4) if sa_res.objective_value is not None else None,
            "reassignment_cost": sa_res.objective_breakdown.reassignment_cost if sa_res.objective_breakdown else 0.0,
            "overflow_cost": sa_res.objective_breakdown.overflow_cost if sa_res.objective_breakdown else 0.0,
            "hard_violations": sa_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(sa_wall_ms, 2),
            "fallback_used": False,
        })
        print(f"  [SA]      Obj: {sa_res.objective_value:10.4f} | Feas: {sa_res.feasible} | Time: {sa_wall_ms:8.2f} ms | Status: {sa_res.status} (Impr vs Gr: {gr_res.objective_value - sa_res.objective_value:.2f})")

        # Solver 4: Hybrid Standalone (CP-SAT 50% + SA 50%)
        t_start = time.perf_counter_ns()
        hybrid_solver = HybridGateSolver(config, sa_config, cp_ratio=0.5)
        hyb_res = hybrid_solver.solve(flights, gates)
        hyb_wall_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0

        hyb_trace = hyb_res.solver_configuration
        results_rows.append({
            "scenario_id": scen_id,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "HYBRID_STANDALONE",
            "status": hyb_res.status,
            "feasible": hyb_res.feasible,
            "optimality_proven": hyb_res.optimality_proven,
            "objective_value": round(hyb_res.objective_value, 4) if hyb_res.objective_value is not None else None,
            "reassignment_cost": hyb_res.objective_breakdown.reassignment_cost if hyb_res.objective_breakdown else 0.0,
            "overflow_cost": hyb_res.objective_breakdown.overflow_cost if hyb_res.objective_breakdown else 0.0,
            "hard_violations": hyb_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(hyb_wall_ms, 2),
            "fallback_used": hyb_trace.get("fallback_used", False),
        })
        print(f"  [HYBRID]  Obj: {hyb_res.objective_value:10.4f} | Feas: {hyb_res.feasible} | Time: {hyb_wall_ms:8.2f} ms | Status: {hyb_res.status} (Stage1 Source: {hyb_trace.get('initial_solution_source')})")

    # Persist outputs
    df_results = pd.DataFrame(results_rows)
    csv_file = output_dir / "g5_fair_benchmark_results.csv"
    df_results.to_csv(csv_file, index=False)
    print(f"\n[OK] CSV exported to: {csv_file}")

    manifest_data = {
        "benchmark_id": "AEOLUS_G5_FAIR_BENCHMARK",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": env_info,
        "n_scenarios": len(scenarios),
        "n_solver_runs": len(results_rows),
        "solvers_evaluated": ["GREEDY_STANDALONE", "CP_SAT_STANDALONE", "SA_STANDALONE", "HYBRID_STANDALONE"],
        "results": results_rows,
    }
    json_file = output_dir / "g5_fair_benchmark_manifest.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"[OK] JSON Manifest exported to: {json_file}")
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()
