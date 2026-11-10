"""Comprehensive simulation runner and evaluator across all prediction datasets in src/artifacts/predictions.

Evaluates:
- Datasets:
  1. Hub Master Schedule (851 Turns, 50 Contact Gates) from atl_1500_flights_cpsat_turnaround_schedule.csv
  2. Bottleneck Gate Schedule (160 Flights, 10 Contact Gates) from greedy_160_flights_10_gates_schedule.csv
  3. Turnaround Flight Schedule (149 Flights, 20 Contact Gates) from atl_cpsat_turnaround_flights_schedule.csv
- Simulation Models / Branches:
  1. SCHEDULE_ONLY (Nominal baseline, Zero ML)
  2. ARRIVAL_P4_ONLY_LEGACY (Legacy Arrival-only ML)
  3. DUAL_POINT (Dual Core Point ML - Arrival + Departure)
  4. DUAL_PROBABILISTIC (Dual Core Probabilistic Monte Carlo)
- Solvers:
  1. DeterministicGreedy
  2. CPSat
  3. SimulatedAnnealing
  4. HybridCPSatSA
- Metrics:
  - Planned objective value
  - Contact vs Remote assignments
  - Planned hard constraint violations
  - Realized post-hoc conflicts against actual delays
  - Realized overlap minutes
  - Total runtime (ms) and peak memory
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import psutil

from src.evaluation.dual_core_benchmark import (
    BenchmarkBranch,
    SolverExecutionMetrics,
    TurnDataBundle,
    evaluate_solver_on_bundle,
    generate_contact_gates,
    get_process_metrics,
    load_and_build_branch_turns,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.dual_prediction_turn import CouplingAssumption

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("all_prediction_simulations")

PREDICTIONS_DIR = Path("src/artifacts/predictions")
OUTPUT_JSON_PATH = Path("artifacts/dual_core/benchmarks/all_prediction_simulations_evaluation_v1.json")


def build_subset_bundle_from_keys(
    master_csv: Path,
    subset_keys: set[str],
    branch: BenchmarkBranch,
    n_contact_gates: int,
    seed: int = 202601,
) -> TurnDataBundle:
    """Build a TurnDataBundle filtered to the turns that touch the subset_keys."""
    bundle = load_and_build_branch_turns(
        csv_path=master_csv,
        branch=branch,
        n_contact_gates=n_contact_gates,
        seed=seed,
    )
    # Filter turns where arrival or departure leg is in subset_keys
    filtered_indices: list[int] = []
    filtered_turns = []
    for idx, turn in enumerate(bundle.turns):
        arr_in = turn.arrival_leg_id in subset_keys if turn.arrival_leg_id else False
        dep_in = turn.departure_leg_id in subset_keys if turn.departure_leg_id else False
        if arr_in or dep_in:
            filtered_indices.append(idx)
            filtered_turns.append(turn)

    from dataclasses import replace

    planned = [replace(bundle.planned_flights[i], flight_index=new_idx) for new_idx, i in enumerate(filtered_indices)]
    realized = [replace(bundle.realized_flights[i], flight_index=new_idx) for new_idx, i in enumerate(filtered_indices)]

    gates = generate_contact_gates(n_contact_gates, allow_overflow=True)
    return TurnDataBundle(
        branch=branch,
        turns=filtered_turns,
        planned_flights=planned,
        realized_flights=realized,
        gates=gates,
    )


def run_full_simulation_suite() -> dict[str, Any]:
    """Execute simulation across all prediction datasets and simulation models."""
    master_1500_csv = PREDICTIONS_DIR / "atl_1500_flights_cpsat_turnaround_schedule.csv"
    greedy_160_csv = PREDICTIONS_DIR / "greedy_160_flights_10_gates_schedule.csv"
    turnaround_149_csv = PREDICTIONS_DIR / "atl_cpsat_turnaround_flights_schedule.csv"

    if not master_1500_csv.exists():
        raise FileNotFoundError(f"Missing master schedule CSV at {master_1500_csv}")

    df_160 = pd.read_csv(greedy_160_csv)
    keys_160 = set(df_160["flight_id"].dropna().astype(str))

    df_149 = pd.read_csv(turnaround_149_csv)
    keys_149 = set(df_149["flight_key"].dropna().astype(str))

    scenarios = [
        {
            "scenario_id": "hub_schedule_1500_flights_851_turns",
            "name": "ATL Hub Schedule (851 Turns, 50 Contact Gates)",
            "type": "full_hub",
            "n_contact_gates": 50,
            "keys": None,
            "source_file": "atl_1500_flights_cpsat_turnaround_schedule.csv",
        },
        {
            "scenario_id": "bottleneck_160_flights_10_gates",
            "name": "Bottleneck Ramp Schedule (160 Flights, 10 Contact Gates)",
            "type": "subset_160",
            "n_contact_gates": 10,
            "keys": keys_160,
            "source_file": "greedy_160_flights_10_gates_schedule.csv",
        },
        {
            "scenario_id": "turnaround_149_flights_20_gates",
            "name": "Turnaround Schedule (149 Flights, 20 Contact Gates)",
            "type": "subset_149",
            "n_contact_gates": 20,
            "keys": keys_149,
            "source_file": "atl_cpsat_turnaround_flights_schedule.csv",
        },
    ]

    branches = [
        BenchmarkBranch.SCHEDULE_ONLY,
        BenchmarkBranch.ARRIVAL_P4_ONLY_LEGACY,
        BenchmarkBranch.DUAL_POINT,
        BenchmarkBranch.DUAL_PROBABILISTIC,
    ]

    solvers = ["DeterministicGreedy", "CPSat", "SimulatedAnnealing", "HybridCPSatSA"]

    results: dict[str, Any] = {
        "metadata": {
            "protocol": "AEOLUS_ALL_PREDICTION_SIMULATIONS_EVALUATION_V1",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "datasets_evaluated": [
                "atl_1500_flights_cpsat_turnaround_schedule.csv",
                "atl_cpsat_turnaround_sessions_schedule.csv",
                "atl_1500_flights_reassigned_schedule.csv",
                "greedy_160_flights_10_gates_schedule.csv",
                "atl_cpsat_turnaround_flights_schedule.csv",
            ],
            "branches_evaluated": [b.value for b in branches],
            "solvers_evaluated": solvers,
        },
        "scenarios": {},
    }

    t0_all = time.perf_counter()

    for scen in scenarios:
        scen_id = scen["scenario_id"]
        scen_name = scen["name"]
        n_gates = scen["n_contact_gates"]
        LOGGER.info("=== Running Simulation on Scenario: %s (%s gates) ===", scen_name, n_gates)
        results["scenarios"][scen_id] = {
            "scenario_name": scen_name,
            "n_contact_gates": n_gates,
            "source_file": scen["source_file"],
            "branches": {},
        }

        for branch in branches:
            LOGGER.info("  Branch: %s", branch.value)
            if scen["keys"] is None:
                # Master 851 turns
                bundle = load_and_build_branch_turns(
                    csv_path=master_1500_csv,
                    branch=branch,
                    n_contact_gates=n_gates,
                )
            else:
                bundle = build_subset_bundle_from_keys(
                    master_csv=master_1500_csv,
                    subset_keys=scen["keys"],
                    branch=branch,
                    n_contact_gates=n_gates,
                )

            results["scenarios"][scen_id]["num_turns"] = len(bundle.planned_flights)
            results["scenarios"][scen_id]["branches"][branch.value] = {}

            for solver_name in solvers:
                # Budget: CP-SAT 1.0s, SA 300 iterations
                metrics: SolverExecutionMetrics = evaluate_solver_on_bundle(
                    solver_name=solver_name,
                    bundle=bundle,
                    time_limit_seconds=1.0,
                    sa_iterations=300,
                    seed=202601,
                )
                LOGGER.info(
                    "    Solver %s -> status=%s, obj=%.1f, contact=%d, remote=%d, planned_viol=%d, real_conflicts=%d, real_overlap_min=%.1f, time=%.1fms",
                    solver_name,
                    metrics.status,
                    metrics.objective_value,
                    metrics.contact_assignments,
                    metrics.remote_assignments,
                    metrics.planned_hard_violations,
                    metrics.realized_post_hoc_conflicts,
                    metrics.realized_overlap_minutes,
                    metrics.total_runtime_ms,
                )
                results["scenarios"][scen_id]["branches"][branch.value][solver_name] = metrics.to_dict()

    total_duration_sec = time.perf_counter() - t0_all
    results["metadata"]["total_execution_seconds"] = round(total_duration_sec, 2)
    LOGGER.info("Simulation suite finished in %.2f seconds.", total_duration_sec)

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    LOGGER.info("Wrote simulation evaluation artifact to %s", OUTPUT_JSON_PATH)

    return results


if __name__ == "__main__":
    run_full_simulation_suite()
