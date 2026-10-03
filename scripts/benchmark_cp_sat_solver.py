"""Phase D — CP-SAT Gate Assignment Benchmark Suite.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Benchmark Matrix:
- Flights: 100, 200, 300 flights across typical daily operational window (06:00 - 23:00)
- Gates: 20, 30, 50 contact gates (+ 1 overflow stand)
Metrics Measured:
- Feasibility status (OPTIMAL, FEASIBLE)
- Objective value & decomposed cost breakdown
- Runtime in milliseconds
- Contact gate conflicts (independently verified, strictly 0)
- Reassignments and overflow count
- Optimality gap
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, verify_hard_constraints_independently
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


def generate_benchmark_scenario(
    n_flights: int,
    n_contact_gates: int,
    *,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
) -> tuple[list[Flight], list[Gate]]:
    """Synthesize realistic operational flight and gate instances for benchmarking."""
    rng = np.random.default_rng(seed)

    # 1. Contact gates + 1 overflow stand
    gates = [
        Gate(
            gate_id=f"GATE_{g:02d}",
            gate_index=g,
            is_overflow=False,
            allowed_carriers=frozenset({"DL", "AA", "UA", "WN"}) if g % 4 != 0 else frozenset({"DL"}),
        )
        for g in range(n_contact_gates)
    ]
    overflow_gate = Gate(
        gate_id="OVERFLOW_STAND",
        gate_index=n_contact_gates,
        is_overflow=True,
    )
    gates.append(overflow_gate)

    # 2. Daily flight traffic: operational arrivals between 06:00 (360m) and 22:30 (1350m)
    arrival_times = rng.uniform(360, 1350, size=n_flights)
    arrival_times.sort()

    carriers = ["DL", "DL", "DL", "AA", "UA", "WN"]  # DL dominant at KATL
    flights: list[Flight] = []

    for i in range(n_flights):
        arr_sched = int(round(arrival_times[i]))
        # Delay sampled from typical right-skewed arrival delay distribution (min: -15, mean: +12)
        delay = int(round(rng.exponential(scale=15.0) - 5.0))
        arr_pred = max(360, arr_sched + delay)

        c = carriers[i % len(carriers)]
        fl = Flight(
            flight_id=f"FL_{i:03d}",
            flight_index=i,
            carrier=c,
            flight_number=str(1000 + i),
            scheduled_arrival_min=arr_sched,
            scheduled_departure_min=arr_sched + 60,
            predicted_arrival_min=arr_pred,
            nominal_gate_id=f"GATE_{(i % n_contact_gates):02d}",
            min_turnaround_min=45,
            default_dwell_min=60,
            buffer_min=15,
            is_paired=False,
        )
        flights.append(fl)

    return flights, gates


def run_cp_sat_benchmark_suite() -> dict[str, Any]:
    """Execute complete 3x3 benchmark grid (100, 200, 300 flights x 20, 30, 50 gates)."""
    print("=" * 80)
    print("STARTING PHASE D: CP-SAT GATE ASSIGNMENT BENCHMARK SUITE")
    print("Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md")
    print("=" * 80)

    flight_levels = [100, 200, 300]
    gate_levels = [20, 30, 50]

    config = GateOptimizationConfig(
        time_limit_seconds=15.0,
        num_search_workers=1,
        random_seed=PREDETERMINED_DEPLOYMENT_SEED,
    )
    solver = CPSatGateSolver(config=config)

    benchmark_records: list[dict[str, Any]] = []

    for n_fl in flight_levels:
        for n_gt in gate_levels:
            scenario_name = f"F{n_fl}_G{n_gt}"
            print(f"\n--- Running Benchmark: {scenario_name} ({n_fl} flights, {n_gt} contact gates) ---")

            flights, gates = generate_benchmark_scenario(
                n_flights=n_fl,
                n_contact_gates=n_gt,
                seed=PREDETERMINED_DEPLOYMENT_SEED + n_fl + n_gt,
            )

            res = solver.solve(flights, gates)

            # Independent verification
            diag = res.constraint_diagnostics
            assert diag.is_valid is True, f"Hard constraint violation in {scenario_name}!"
            assert diag.no_contact_gate_conflicts is True, f"Conflict detected in {scenario_name}!"

            reassignments = sum(1 for a in res.assignments.values() if a.is_reassignment)
            overflows = sum(1 for a in res.assignments.values() if a.is_overflow)

            record = {
                "scenario_name": scenario_name,
                "n_flights": n_fl,
                "n_contact_gates": n_gt,
                "status": res.status,
                "feasible": res.feasible,
                "runtime_ms": res.runtime_ms,
                "objective_value": res.objective_value,
                "reassignments_count": reassignments,
                "overflow_count": overflows,
                "contact_gate_conflicts": diag.conflict_count,
                "optimality_gap": res.optimality_gap,
                "hard_constraints_satisfied": diag.is_valid,
                "objective_breakdown": res.objective_breakdown.to_dict(),
            }
            benchmark_records.append(record)

            print(f"  Status: {res.status} | Feasible: {res.feasible}")
            print(f"  Runtime: {res.runtime_ms:.1f} ms | Objective: {res.objective_value:.2f}")
            print(f"  Reassignments: {reassignments}/{n_fl} | Overflows: {overflows}/{n_fl}")
            print(f"  Contact Gate Conflicts: {diag.conflict_count} (Independent Check: PASS)")

    audit_dir = PROJECT_ROOT / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = audit_dir / "cp_sat_benchmark_manifest_v1.json"

    manifest_content = {
        "manifest_version": "cp_sat_benchmark_manifest_v1",
        "phase": "PHASE_D",
        "status": "PASS",
        "solver_backend": "Google OR-Tools CP-SAT",
        "solver_configuration": config.to_dict(),
        "total_scenarios_tested": len(benchmark_records),
        "all_hard_constraints_passed": all(r["hard_constraints_satisfied"] for r in benchmark_records),
        "zero_contact_conflicts_verified": all(r["contact_gate_conflicts"] == 0 for r in benchmark_records),
        "benchmarks": benchmark_records,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_content, f, indent=2)

    print(f"\n[Artifact Created] Benchmark manifest written to: {manifest_path}")
    print("\n" + "=" * 80)
    print("PHASE D CP-SAT GATE ASSIGNMENT: ALL BENCHMARKS PASS")
    print("=" * 80)

    return manifest_content


if __name__ == "__main__":
    run_cp_sat_benchmark_suite()
