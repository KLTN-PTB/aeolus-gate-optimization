"""AEOLUS-G12B Fair Wall-Clock Benchmark Runner.

Protocol: AEOLUS-G12B Part E Fair Benchmark & Incumbent Verification Gate.
Covers 5 tiers x 4 solvers under identical conditions:
Tiers:
1. Micro Oracle (4 flights, 2 contact gates, 1 remote, 1 overflow)
2. Medium (30 flights, 8 contact gates, 2 remote stands)
3. Thesis Scale 1 (100 flights, 20 contact gates, 3 remote stands)
4. Thesis Scale 2 (200 flights, 30 contact gates, 4 remote stands)
5. Thesis Scale 3 (300 flights, 50 contact gates, 5 remote stands)

Solvers:
1. Deterministic Greedy
2. CP-SAT Standalone
3. Greedy + SA (Two-stage heuristic)
4. CP-SAT + SA (Guarded Hybrid with Incumbent Protection & Global Budget)

Outputs saved to: artifacts/remediation/benchmarks/g12b_fair_benchmark/
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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    """Define benchmark scenarios across Micro, Medium, and Thesis scales."""
    scenarios = []

    # Tier 1: Micro Oracle (4 flights, 2 contact gates, 1 remote, 1 overflow)
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
        "scenario_id": "SCEN_01_MICRO_ORACLE",
        "name": "Micro Oracle Parity (4 flights / 2 contact gates)",
        "tier": "Micro",
        "n_flights": 4,
        "n_contact_gates": 2,
        "flights": f_micro,
        "gates": g_micro,
        "time_limit_sec": 2.0,
    })

    # Tier 2: Medium (30 flights, 8 contact gates, 2 remote stands)
    f_med, g_med = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_A, 30, 8, n_remote_stands=2, seed=42)
    scenarios.append({
        "scenario_id": "SCEN_02_MEDIUM_30",
        "name": "Medium Scale (30 flights / 8 contact gates)",
        "tier": "Medium",
        "n_flights": 30,
        "n_contact_gates": 8,
        "flights": f_med,
        "gates": g_med,
        "time_limit_sec": 3.0,
    })

    # Tier 3: Thesis Scale 1 (100 flights / 20 contact gates)
    f_100, g_100 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 100, 20, n_remote_stands=3, seed=101)
    scenarios.append({
        "scenario_id": "SCEN_03_THESIS_100",
        "name": "Thesis Scale 1 (100 flights / 20 contact gates)",
        "tier": "Thesis-100",
        "n_flights": 100,
        "n_contact_gates": 20,
        "flights": f_100,
        "gates": g_100,
        "time_limit_sec": 5.0,
    })

    # Tier 4: Thesis Scale 2 (200 flights / 30 contact gates)
    f_200, g_200 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 200, 30, n_remote_stands=4, seed=202)
    scenarios.append({
        "scenario_id": "SCEN_04_THESIS_200",
        "name": "Thesis Scale 2 (200 flights / 30 contact gates)",
        "tier": "Thesis-200",
        "n_flights": 200,
        "n_contact_gates": 30,
        "flights": f_200,
        "gates": g_200,
        "time_limit_sec": 5.0,
    })

    # Tier 5: Thesis Scale 3 (300 flights / 50 contact gates)
    f_300, g_300 = generate_synthetic_benchmark_scenario(BenchmarkTier.TIER_B, 300, 50, n_remote_stands=5, seed=303)
    scenarios.append({
        "scenario_id": "SCEN_05_THESIS_300",
        "name": "Thesis Scale 3 (300 flights / 50 contact gates)",
        "tier": "Thesis-300",
        "n_flights": 300,
        "n_contact_gates": 50,
        "flights": f_300,
        "gates": g_300,
        "time_limit_sec": 5.0,
    })

    return scenarios


def run_fair_benchmark() -> dict[str, Any]:
    """Execute the tiered benchmark across all 4 solvers."""
    print("=" * 80)
    print("AEOLUS-G12B: FAIR WALL-CLOCK BENCHMARK EXECUTION")
    print("=" * 80)

    env_info = get_environment_info()
    print(f"Platform: {env_info['platform_system']} {env_info['platform_release']} | Python: {env_info['python_version']}")
    print(f"OR-Tools: {env_info['ortools_version']} | Logical CPUs: {env_info['cpu_count_logical']}")

    scenarios = build_benchmark_scenarios()
    output_dir = Path("artifacts/remediation/benchmarks/g12b_fair_benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []

    for scen in scenarios:
        scen_id = scen["scenario_id"]
        scen_name = scen["name"]
        tier = scen["tier"]
        flights = scen["flights"]
        gates = scen["gates"]
        n_flights = len(flights)
        n_gates = len(gates)
        time_limit = scen["time_limit_sec"]
        scen_hash = compute_scenario_hash(flights, gates)

        print(f"\n>>> Running {scen_id} [{tier}] ({n_flights} flights, {n_gates} gates, budget={time_limit}s, SHA={scen_hash[:12]}...)")

        cfg = GateOptimizationConfig(
            reassignment_weight=10.0,
            overflow_weight=200.0,
            delay_weight=1.0,
            conflict_weight=1000.0,
            risk_weight=2.0,
            time_limit_seconds=time_limit,
            total_wall_clock_budget_seconds=time_limit,
            num_search_workers=1,
            random_seed=42,
            cp_sat_use_warm_start=True,
            cp_sat_fallback_to_greedy=True,
        )
        sa_cfg = SAConfig(iterations=300, seed=42)

        # -------------------------------------------------------------
        # Solver 1: Greedy Standalone
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        greedy_solver = DeterministicGreedyGateSolver(cfg)
        gr_res = greedy_solver.solve(flights, gates)
        gr_runtime_ms = (time.perf_counter() - t0) * 1000.0

        rows.append({
            "scenario_id": scen_id,
            "tier": tier,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "Greedy",
            "status": gr_res.status,
            "feasible": gr_res.feasible,
            "optimality_proven": gr_res.optimality_proven,
            "termination_reason": str(gr_res.termination_reason),
            "objective_value": round(gr_res.objective_value, 4),
            "reassignment_cost": gr_res.objective_breakdown.reassignment_cost if gr_res.objective_breakdown else 0.0,
            "overflow_cost": gr_res.objective_breakdown.overflow_cost if gr_res.objective_breakdown else 0.0,
            "hard_violations": gr_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(gr_runtime_ms, 2),
            "stage1_ms": round(gr_runtime_ms, 2),
            "stage2_ms": 0.0,
            "incumbent_cost": round(gr_res.objective_value, 4),
            "sa_accepted": False,
            "sa_improved": False,
            "sa_rejection_reason": "N/A_STANDALONE",
        })
        print(f"  [Greedy]     Obj: {gr_res.objective_value:10.4f} | Feas: {gr_res.feasible} | Time: {gr_runtime_ms:8.2f} ms | Status: {gr_res.status}")

        # -------------------------------------------------------------
        # Solver 2: CP-SAT Standalone
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        cpsat_solver = CPSatGateSolver(cfg)
        cp_res = cpsat_solver.solve(flights, gates)
        cp_runtime_ms = (time.perf_counter() - t0) * 1000.0

        rows.append({
            "scenario_id": scen_id,
            "tier": tier,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "CP-SAT",
            "status": cp_res.status,
            "feasible": cp_res.feasible,
            "optimality_proven": cp_res.optimality_proven,
            "termination_reason": str(cp_res.termination_reason),
            "objective_value": round(cp_res.objective_value, 4) if cp_res.feasible else float("inf"),
            "reassignment_cost": cp_res.objective_breakdown.reassignment_cost if cp_res.objective_breakdown else 0.0,
            "overflow_cost": cp_res.objective_breakdown.overflow_cost if cp_res.objective_breakdown else 0.0,
            "hard_violations": cp_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(cp_runtime_ms, 2),
            "stage1_ms": round(cp_runtime_ms, 2),
            "stage2_ms": 0.0,
            "incumbent_cost": round(cp_res.objective_value, 4) if cp_res.feasible else float("inf"),
            "sa_accepted": False,
            "sa_improved": False,
            "sa_rejection_reason": "N/A_STANDALONE",
        })
        print(f"  [CP-SAT]     Obj: {cp_res.objective_value:10.4f} | Feas: {cp_res.feasible} | Time: {cp_runtime_ms:8.2f} ms | Status: {cp_res.status}")

        # -------------------------------------------------------------
        # Solver 3: Greedy + SA
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        sa_solver = SimulatedAnnealingGateSolver(cfg, sa_config=sa_cfg)
        gr_sa_res = sa_solver.solve(
            flights=flights,
            gates=gates,
            initial_assignments=gr_res.assignments,
            deadline_perf_counter=t0 + time_limit,
        )
        gr_sa_runtime_ms = (time.perf_counter() - t0) * 1000.0
        gr_sa_improved = gr_sa_res.objective_value < gr_res.objective_value - 1e-6

        rows.append({
            "scenario_id": scen_id,
            "tier": tier,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "Greedy+SA",
            "status": gr_sa_res.status,
            "feasible": gr_sa_res.feasible,
            "optimality_proven": gr_sa_res.optimality_proven,
            "termination_reason": str(gr_sa_res.termination_reason),
            "objective_value": round(gr_sa_res.objective_value, 4),
            "reassignment_cost": gr_sa_res.objective_breakdown.reassignment_cost if gr_sa_res.objective_breakdown else 0.0,
            "overflow_cost": gr_sa_res.objective_breakdown.overflow_cost if gr_sa_res.objective_breakdown else 0.0,
            "hard_violations": gr_sa_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(gr_sa_runtime_ms, 2),
            "stage1_ms": round(gr_runtime_ms, 2),
            "stage2_ms": round(gr_sa_runtime_ms - gr_runtime_ms, 2),
            "incumbent_cost": round(gr_res.objective_value, 4),
            "sa_accepted": True,
            "sa_improved": gr_sa_improved,
            "sa_rejection_reason": "NONE",
        })
        print(f"  [Greedy+SA]  Obj: {gr_sa_res.objective_value:10.4f} | Feas: {gr_sa_res.feasible} | Time: {gr_sa_runtime_ms:8.2f} ms | Status: {gr_sa_res.status}")

        # -------------------------------------------------------------
        # Solver 4: CP-SAT + SA (Guarded Hybrid)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        hybrid_solver = HybridGateSolver(cfg, sa_config=sa_cfg, cp_ratio=0.5)
        hyb_res = hybrid_solver.solve(flights, gates)
        hyb_runtime_ms = (time.perf_counter() - t0) * 1000.0

        trace = hyb_res.solver_configuration
        rows.append({
            "scenario_id": scen_id,
            "tier": tier,
            "scenario_hash": scen_hash,
            "n_flights": n_flights,
            "n_gates": n_gates,
            "solver": "CP-SAT+SA",
            "status": hyb_res.status,
            "feasible": hyb_res.feasible,
            "optimality_proven": hyb_res.optimality_proven,
            "termination_reason": str(hyb_res.termination_reason),
            "objective_value": round(hyb_res.objective_value, 4),
            "reassignment_cost": hyb_res.objective_breakdown.reassignment_cost if hyb_res.objective_breakdown else 0.0,
            "overflow_cost": hyb_res.objective_breakdown.overflow_cost if hyb_res.objective_breakdown else 0.0,
            "hard_violations": hyb_res.constraint_diagnostics.hard_constraint_violations_count,
            "runtime_ms": round(hyb_runtime_ms, 2),
            "stage1_ms": round(trace.get("stage1_wall_clock_ms", 0.0), 2),
            "stage2_ms": round(trace.get("stage2_wall_clock_ms", 0.0), 2),
            "incumbent_cost": round(trace.get("initial_cost", hyb_res.objective_value), 4),
            "sa_accepted": bool(trace.get("sa_accepted", False)),
            "sa_improved": bool(trace.get("sa_improved", False)),
            "sa_rejection_reason": str(trace.get("sa_rejection_reason", "NONE")),
        })
        print(f"  [CP-SAT+SA]  Obj: {hyb_res.objective_value:10.4f} | Feas: {hyb_res.feasible} | Time: {hyb_runtime_ms:8.2f} ms | Status: {hyb_res.status} | Incumbent Protected: {hyb_res.objective_value <= trace.get('initial_cost', float('inf')) + 1e-6}")

    # Export results
    df = pd.DataFrame(rows)
    csv_path = output_dir / "fair_benchmark_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[OK] Saved results CSV: {csv_path}")

    # Build summary
    summary = {
        "benchmark_metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "platform": f"{env_info['platform_system']} {env_info['platform_release']}",
            "python_version": env_info["python_version"],
            "ortools_version": env_info["ortools_version"],
            "num_tiers": len(scenarios),
            "num_solvers": 4,
            "total_runs": len(rows),
        },
        "incumbent_protection_verification": {
            "all_runs_feasible": bool(df["feasible"].all()),
            "zero_hard_violations": bool((df["hard_violations"] == 0).all()),
            "hybrid_monotonicity_satisfied": bool(
                (df[df["solver"] == "CP-SAT+SA"]["objective_value"] <= df[df["solver"] == "CP-SAT+SA"]["incumbent_cost"] + 1e-6).all()
            ),
        },
        "records": rows,
    }

    json_path = output_dir / "fair_benchmark_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Saved summary JSON: {json_path}")

    # Markdown Table Report
    md_lines = [
        "# AEOLUS-G12B Fair Wall-Clock Benchmark Results",
        "",
        f"- Generated at: {summary['benchmark_metadata']['timestamp']}",
        f"- Platform: {summary['benchmark_metadata']['platform']}",
        f"- OR-Tools: {summary['benchmark_metadata']['ortools_version']}",
        "",
        "## Tiered Performance Matrix",
        "",
        "| Scenario | Flights | Gates | Solver | Status | Feasible | Optimality | Obj Value | Incumbent | Runtime (ms) | SA Accepted | Rejection Reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['scenario_id']} | {r['n_flights']} | {r['n_gates']} | {r['solver']} | {r['status']} | {r['feasible']} | {r['optimality_proven']} | {r['objective_value']} | {r['incumbent_cost']} | {r['runtime_ms']} | {r['sa_accepted']} | {r['sa_rejection_reason']} |"
        )

    md_path = output_dir / "fair_benchmark_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"[OK] Saved report MD: {md_path}")

    return summary


if __name__ == "__main__":
    run_fair_benchmark()
