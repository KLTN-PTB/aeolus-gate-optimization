"""Execution script for Phase P05: Fair & Reproducible Solver Benchmark.

Generates:
1. artifacts/remediation/benchmarks/benchmark_manifest.json
2. artifacts/remediation/benchmarks/solver_runs.csv
3. artifacts/remediation/benchmarks/aggregate_metrics.json
4. artifacts/remediation/benchmarks/failures.json
5. artifacts/remediation/benchmarks/environment.json

Protocol: docs/remediation/05_benchmark_protocol.md
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimization.benchmark_harness import (
    BENCHMARK_SCHEMA_VERSION,
    AggregateBenchmarkMetrics,
    BenchmarkCaseSpec,
    BenchmarkManifest,
    BenchmarkRunResult,
    BenchmarkTier,
    SolverMode,
    compute_aggregate_metrics,
    compute_scenario_hash,
    execute_benchmark_run,
    generate_synthetic_benchmark_scenario,
    get_environment_info,
    save_benchmark_artifacts,
    validate_benchmark_invariants,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_p05_benchmark_suite")


def run_suite() -> None:
    LOGGER.info("Starting Phase P05 Benchmark Suite execution...")
    env_info = get_environment_info()

    # Define benchmark cases
    # Tier A (Micro Correctness) & Tier B (Thesis Core)
    scenarios_meta = [
        # Tier A
        {
            "tier": BenchmarkTier.TIER_A,
            "scenario_id": "SCEN_TIER_A_10F_3G",
            "scenario_type": "SYNTHETIC_MICRO",
            "n_flights": 10,
            "n_contact_gates": 3,
            "n_remote_stands": 1,
            "time_budget_ms": 2000.0,
            "repeats": 5,
        },
        {
            "tier": BenchmarkTier.TIER_A,
            "scenario_id": "SCEN_TIER_A_20F_6G",
            "scenario_type": "SYNTHETIC_MICRO",
            "n_flights": 20,
            "n_contact_gates": 6,
            "n_remote_stands": 2,
            "time_budget_ms": 2000.0,
            "repeats": 5,
        },
        # Tier B (Thesis Scale: 100, 200, 300 flights)
        {
            "tier": BenchmarkTier.TIER_B,
            "scenario_id": "SCEN_TIER_B_100F_20G",
            "scenario_type": "SYNTHETIC_THESIS",
            "n_flights": 100,
            "n_contact_gates": 20,
            "n_remote_stands": 3,
            "time_budget_ms": 2000.0,
            "repeats": 3,
        },
        {
            "tier": BenchmarkTier.TIER_B,
            "scenario_id": "SCEN_TIER_B_200F_30G",
            "scenario_type": "SYNTHETIC_THESIS",
            "n_flights": 200,
            "n_contact_gates": 30,
            "n_remote_stands": 5,
            "time_budget_ms": 2000.0,
            "repeats": 3,
        },
        {
            "tier": BenchmarkTier.TIER_B,
            "scenario_id": "SCEN_TIER_B_300F_50G",
            "scenario_type": "SYNTHETIC_THESIS",
            "n_flights": 300,
            "n_contact_gates": 50,
            "n_remote_stands": 5,
            "time_budget_ms": 2000.0,
            "repeats": 3,
        },
    ]

    all_specs: list[BenchmarkCaseSpec] = []
    all_results: list[BenchmarkRunResult] = []

    # Solver modes to evaluate for each scenario
    modes_to_test = [
        (SolverMode.GREEDY_STANDALONE, "DeterministicGreedy", {}),
        (SolverMode.CP_SAT_STANDALONE, "CPSat", {}),
        (SolverMode.SA_STANDALONE, "SimulatedAnnealing", {"sa_iterations": 500}),
        (SolverMode.HYBRID_STANDALONE, "HybridCPSatSA", {"cp_ratio": 0.5, "sa_iterations": 500}),
        (SolverMode.SA_FROM_PRECOMPUTED_INCUMBENT, "SimulatedAnnealing", {"sa_iterations": 500}),
    ]

    for scen_meta in scenarios_meta:
        scen_id = scen_meta["scenario_id"]
        n_flights = scen_meta["n_flights"]
        n_cg = scen_meta["n_contact_gates"]
        n_rs = scen_meta["n_remote_stands"]
        budget_ms = scen_meta["time_budget_ms"]
        repeats = scen_meta["repeats"]

        LOGGER.info(f"Generating scenario {scen_id} ({n_flights} flights x {n_cg} contact + {n_rs} remote gates)...")
        flights, gates = generate_synthetic_benchmark_scenario(
            tier=scen_meta["tier"],
            n_flights=n_flights,
            n_contact_gates=n_cg,
            n_remote_stands=n_rs,
            seed=202601,
        )
        scen_hash = compute_scenario_hash(flights, gates)

        # Precompute incumbent for diagnostic mode
        solver_greedy = DeterministicGreedyGateSolver()
        precomputed_res = solver_greedy.solve(flights, gates)
        precomputed_incumbent = precomputed_res.assignments if precomputed_res.feasible else None

        for mode_enum, solver_name, extra_cfg in modes_to_test:
            spec = BenchmarkCaseSpec(
                experiment_id=f"EXP_{scen_meta['tier'].value}",
                scenario_id=scen_id,
                scenario_hash=scen_hash,
                input_dataset_hash="hash_canonical_dev_inbound_2023",
                scenario_type=scen_meta["scenario_type"],
                n_flights=len(flights),
                n_aircraft_turns=len(flights),
                n_contact_gates=n_cg,
                n_finite_remote_stands=n_rs,
                capacity_policy="remote_stand_capacity_finite",
                objective_version="v1",
                objective_weights={
                    "reassignment_weight": 10.0,
                    "overflow_weight": 200.0,
                    "delay_weight": 1.0,
                    "conflict_weight": 1000.0,
                    "risk_weight": 2.0,
                },
                prediction_mode="point_prediction",
                solver_name=solver_name,
                solver_variant=mode_enum.value,
                seed=202601,
                worker_count=1,
                solver_config={
                    "scale_factor": 100,
                    "finite_remote_capacity": 1,
                    "allow_unbounded_overflow": True,
                    "enforce_remote_capacity": True,
                    **extra_cfg,
                },
                time_budget_ms=budget_ms,
                memory_budget_mb=1024.0,
                environment_info=env_info,
            )
            all_specs.append(spec)

            LOGGER.info(f"  Running mode {mode_enum.value} across {repeats} repetitions...")
            for rep in range(repeats):
                rep_spec = replace(spec, seed=202601 + rep)
                run_res = execute_benchmark_run(
                    spec=rep_spec,
                    flights=flights,
                    gates=gates,
                    run_id=f"rep_{rep+1}",
                    precomputed_incumbent=precomputed_incumbent if mode_enum == SolverMode.SA_FROM_PRECOMPUTED_INCUMBENT else None,
                )
                all_results.append(run_res)

                # Validate invariants B01-B20
                checks = validate_benchmark_invariants(rep_spec, run_res, flights, gates)
                failed_invariants = [k for k, v in checks.items() if not v]
                if failed_invariants:
                    LOGGER.warning(f"Run {scen_id} {mode_enum.value} rep_{rep+1} failed invariants: {failed_invariants}")

    # Compute aggregates
    LOGGER.info("Computing multi-run aggregate metrics...")
    aggregates = compute_aggregate_metrics(all_specs, all_results)

    # Build manifest
    feasible_count = sum(1 for r in all_results if r.feasible)
    failed_count = sum(1 for r in all_results if not r.feasible)

    summary_by_mode: dict[str, Any] = {}
    for agg in aggregates:
        summary_by_mode.setdefault(agg.solver_variant, []).append(
            {
                "scenario_id": agg.scenario_id,
                "n_runs": agg.n_runs,
                "feasible": agg.n_feasible,
                "wall_clock_median_ms": agg.wall_clock_median_ms,
                "objective_median": agg.objective_median,
            }
        )

    manifest = BenchmarkManifest(
        schema_version=BENCHMARK_SCHEMA_VERSION,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        environment=env_info,
        specs=[s.to_dict() for s in all_specs],
        run_count=len(all_results),
        feasible_count=feasible_count,
        failed_count=failed_count,
        summary_by_mode=summary_by_mode,
    )

    out_dir = ROOT / "artifacts" / "remediation" / "benchmarks"
    LOGGER.info(f"Persisting artifacts to {out_dir}...")
    paths = save_benchmark_artifacts(manifest, all_results, aggregates, output_dir=out_dir)

    for name, p in paths.items():
        LOGGER.info(f"  Exported {name}: {p} ({p.stat().st_size} bytes)")

    LOGGER.info("P05 Benchmark Suite execution finished successfully!")


if __name__ == "__main__":
    run_suite()
