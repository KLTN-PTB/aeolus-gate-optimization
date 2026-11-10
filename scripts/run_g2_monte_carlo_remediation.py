"""Execution script for Remediated Monte Carlo (Gate G2 Remediation & MC500 Production Runner).

Protocol: Aeolus Predict-then-Optimize V4.1 - Phase G2 / MC500
Preserves: artifacts/remediation/monte_carlo_remediated/ (FROZEN - ZERO OVERWRITE)
Outputs to: artifacts/remediation/monte_carlo_mc500/<run_id>/

Executes:
- Mode A: Fixed Plan Robustness (0 re-optimizations, explicit feasibility decomposition).
- Mode B1: Retrospective Recourse (Full-information hindsight recourse; explicitly labeled RETROSPECTIVE).
- Mode B2: Rolling Online Recourse (Non-anticipative online event-driven recourse; strictly causal).
- Mode C1: Greedy Full-Foresight Benchmark (Heuristic baseline, NOT globally optimal lower bound).
- Mode C2: CP-SAT Optimal Foresight Oracle (Mathematically proven optimal lower bound).

Features:
- Integrated SimulationExecutionLedger with distinct Scenario Generation vs Evaluation accounting.
- Strict CRN pairing and 11-slot protocol verification.
- Isolated run-specific output directories.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.contracts.provenance import (
    DataOrigin,
    EvaluationRegime,
    EvidenceProvenance,
    InformationRegime,
    PairingSource,
    PredictionSource,
    ScenarioGeneration,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate, Flight, GateAssignment, GateResourceType
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.scalability_scenario import (
    generate_scalability_scenario,
    scenario_to_flights,
    scenario_to_gates,
)
from src.simulation.monte_carlo_engine_p09 import (
    CopulaDependenceModel,
    MonteCarloScenarioGenerator,
    RealizedScenario,
    apply_delays_to_flights,
)
from src.simulation.monte_carlo_engine_v2 import (
    CANONICAL_PROTOCOL_EVALUATIONS,
    FeasibilityBreakdown,
    RemediatedRealizationResult,
    RemediatedSimulationMode,
    SimulationExecutionLedger,
    compute_file_sha256,
    compute_remediated_paired_comparison,
    compute_remediated_statistics,
    evaluate_mode_a_fixed_plan_v2,
    evaluate_mode_b1_retrospective_recourse,
    evaluate_mode_b2_rolling_online_recourse,
    evaluate_mode_c_greedy_foresight,
    evaluate_mode_c_optimal_foresight,
)

DEFAULT_BASE_OUTPUT_DIR = Path("artifacts/remediation/monte_carlo_mc500")


def run_g2_remediation_pipeline(
    n_scenarios: int = 100,
    seed: int = 202601,
    output_dir: Path | str | None = None,
    dry_run: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute the full Remediated Monte Carlo pipeline with execution ledger tracking."""
    if dry_run:
        n_scenarios = 5

    if run_id is None:
        run_id = f"mc500_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}"

    if output_dir is not None:
        out_path = Path(output_dir)
    else:
        out_path = DEFAULT_BASE_OUTPUT_DIR / run_id

    out_path.mkdir(parents=True, exist_ok=True)

    t_pipeline_start = time.perf_counter()

    print("=" * 80)
    print("AEOLUS GATE G2: REMEDIATED MONTE CARLO PIPELINE (MC500 PRODUCTION RUNNER)")
    print("=" * 80)
    print(f"Run ID:                  {run_id}")
    print(f"Target Output Directory: {out_path.resolve()}")
    print(f"Number of Scenarios:     {n_scenarios}")
    print(f"Base Random Seed:        {seed}")
    print(f"Dry Run Mode:            {dry_run}")

    # 1. Configuration & Scenario Setup
    N_FLIGHTS = 120
    N_CONTACT_GATES = 25
    N_REMOTE_STANDS = 5

    print(f"\n[Step 1] Loading canonical scenario ({N_FLIGHTS} flights, {N_CONTACT_GATES} contact gates)...")
    scen = generate_scalability_scenario(
        n_flights=N_FLIGHTS,
        n_contact_gates=N_CONTACT_GATES,
        seed=seed,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    base_flights = scenario_to_flights(scen)
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=N_REMOTE_STANDS, remote_gate_id="REMOTE_STAND_01"
    )
    all_gates = contact_gates + [remote_gate]

    config = GateOptimizationConfig(
        finite_remote_capacity=N_REMOTE_STANDS,
        enforce_remote_capacity=True,
        allow_unbounded_overflow=False,
        time_limit_seconds=1.5,
        random_seed=seed,
    )

    # Export certified gate inventory artifact
    gate_inventory = {
        "n_contact_gates": len(contact_gates),
        "total_finite_remote_capacity": sum(
            g.capacity for g in all_gates if g.resource_type == GateResourceType.FINITE_REMOTE_STAND
        ),
        "n_unbounded_overflow_aprons": sum(
            1 for g in all_gates if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON
        ),
        "allow_unbounded_overflow": config.allow_unbounded_overflow,
        "gates": [
            {
                "gate_id": g.gate_id,
                "gate_index": g.gate_index,
                "resource_type": g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type),
                "capacity": float(g.capacity) if math.isfinite(g.capacity) else "unbounded",
                "is_overflow": g.is_overflow,
                "allowed_carriers": sorted(list(g.allowed_carriers)) if g.allowed_carriers is not None else None,
                "allowed_aircraft_types": sorted(list(g.allowed_aircraft_types)) if g.allowed_aircraft_types is not None else None,
                "available_windows": list(g.available_windows) if g.available_windows is not None else None,
            }
            for g in all_gates
        ],
    }
    with open(out_path / "gate_inventory.json", "w", encoding="utf-8") as f:
        json.dump(gate_inventory, f, indent=2)

    # Compute provenance hashes
    source_hash = compute_file_sha256("src/simulation/monte_carlo_engine_v2.py")
    config_dict = {
        "n_flights": N_FLIGHTS,
        "n_contact_gates": N_CONTACT_GATES,
        "n_remote_stands": N_REMOTE_STANDS,
        "finite_remote_capacity": config.finite_remote_capacity,
        "enforce_remote_capacity": config.enforce_remote_capacity,
        "allow_unbounded_overflow": config.allow_unbounded_overflow,
        "time_limit_seconds": config.time_limit_seconds,
        "random_seed": config.random_seed,
        "copula_rho": 0.45,
        "base_seed": seed,
    }
    config_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()

    # Initialize execution ledger
    ledger = SimulationExecutionLedger(
        run_id=run_id,
        requested_n=n_scenarios,
        config_hash=config_hash,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )

    try:
        # 2. Initial Planned Assignment (T-2h Prediction Cutoff)
        print("\n[Step 2] Generating initial plans at T-2h prediction cutoff...")
        solver_greedy = DeterministicGreedyGateSolver(config=config)
        res_greedy = solver_greedy.solve(base_flights, all_gates)
        print(f"  Greedy initial plan: obj={res_greedy.objective_value:.2f}, feas={res_greedy.feasible}")

        solver_cpsat = CPSatGateSolver(config=config)
        res_cpsat = solver_cpsat.solve(base_flights, all_gates)
        print(f"  CP-SAT initial plan: obj={res_cpsat.objective_value:.2f}, feas={res_cpsat.feasible}")

        solver_hybrid = HybridGateSolver(config=config)
        res_hybrid = solver_hybrid.solve(base_flights, all_gates)
        print(f"  Hybrid initial plan: obj={res_hybrid.objective_value:.2f}, feas={res_hybrid.feasible}")

        initial_solvers = [
            ("Greedy", res_greedy),
            ("CPSat", res_cpsat),
            ("Hybrid", res_hybrid),
        ]

        # 3. Monte Carlo Realizations Generation (Gaussian Copula rho=0.45, Student-t marginals)
        print(f"\n[Step 3] Generating {n_scenarios} realizations via Gaussian Copula (rho=0.45)...")
        generator = MonteCarloScenarioGenerator(
            n_scenarios=n_scenarios,
            seed=seed,
            rho=0.45,
            arr_mu=5.0,
            arr_sigma=18.0,
            arr_df=4.5,
            dep_mu=8.0,
            dep_sigma=22.0,
            dep_df=4.0,
        )
        scenarios = generator.generate_scenarios(base_flights, scenario_prefix="MC_REM")
        print(f"  Generated {len(scenarios)} realizations successfully.")

        # Register generated scenarios in ledger
        for s in scenarios:
            ledger.record_scenario_generated(
                scenario_id=s.scenario_id,
                scenario_index=s.scenario_index,
                seed=s.seed,
                realization_hash=s.realization_hash,
                generation_status="SUCCESS",
                source_hash=source_hash,
                config_hash=config_hash,
            )

        # Save scenario index CSV
        scen_records = [
            {
                "scenario_index": s.scenario_index,
                "scenario_id": s.scenario_id,
                "mean_arr_delay": round(float(np.mean(s.arrival_delays)), 2),
                "max_arr_delay": round(float(np.max(s.arrival_delays)), 2),
                "mean_dep_delay": round(float(np.mean(s.departure_delays)), 2),
                "max_dep_delay": round(float(np.max(s.departure_delays)), 2),
                "realization_hash": s.realization_hash,
                "seed": s.seed,
            }
            for s in scenarios
        ]
        pd.DataFrame(scen_records).to_csv(out_path / "scenario_index.csv", index=False)

        timing_breakdown: dict[str, float] = {}

        # 4. Mode A: Fixed Plan Robustness (Zero Re-optimizations)
        print("\n[Step 4] Evaluating MODE A: Fixed Plan Robustness...")
        t_mode_a_start = time.perf_counter()
        mode_a_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
        for s in scenarios:
            realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
            for solver_name, init_res in initial_solvers:
                t0 = time.perf_counter()
                try:
                    r_a = evaluate_mode_a_fixed_plan_v2(
                        frozen_assignments=init_res.assignments,
                        realized_flights=realized_flights,
                        gates=all_gates,
                        config=config,
                        realization=s,
                        solver_name=solver_name,
                    )
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    mode_a_results[solver_name].append(r_a)
                    ledger.record_evaluation_success(
                        scenario_id=s.scenario_id,
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_A",
                        solver_status=r_a.solver_status,
                        composite_feasible=r_a.feasibility.composite_feasible,
                        objective_value=r_a.objective_value if r_a.objective_value is not None else 0.0,
                        runtime_ms=dt_ms,
                    )
                except Exception as exc:
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    ledger.record_evaluation_failure(
                        scenario_id=s.scenario_id,
                        reason=str(exc),
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_A",
                        exception_type=type(exc).__name__,
                        runtime_ms=dt_ms,
                    )
                    raise

        timing_breakdown["mode_a_seconds"] = round(time.perf_counter() - t_mode_a_start, 4)
        df_mode_a = pd.DataFrame([r.to_flat_dict() for r_list in mode_a_results.values() for r in r_list])
        df_mode_a.to_csv(out_path / "fixed_plan_results.csv", index=False)
        print(f"  Exported fixed_plan_results.csv ({len(df_mode_a)} rows, {timing_breakdown['mode_a_seconds']:.2f}s)")

        # 5. Mode B1: Retrospective Recourse (Full Hindsight Benchmark)
        print("\n[Step 5] Evaluating MODE B1: Retrospective Recourse (Full Hindsight)...")
        t_mode_b1_start = time.perf_counter()
        mode_b1_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
        for s in scenarios:
            realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
            for solver_name, init_res in initial_solvers:
                t0 = time.perf_counter()
                try:
                    r_b1 = evaluate_mode_b1_retrospective_recourse(
                        initial_assignments=init_res.assignments,
                        realized_flights=realized_flights,
                        gates=all_gates,
                        config=config,
                        realization=s,
                        initial_solver_name=solver_name,
                        recourse_solver_name="DeterministicGreedy",
                    )
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    mode_b1_results[solver_name].append(r_b1)
                    ledger.record_evaluation_success(
                        scenario_id=s.scenario_id,
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_B1",
                        solver_status=r_b1.solver_status,
                        composite_feasible=r_b1.feasibility.composite_feasible,
                        objective_value=r_b1.objective_value if r_b1.objective_value is not None else 0.0,
                        runtime_ms=dt_ms,
                    )
                except Exception as exc:
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    ledger.record_evaluation_failure(
                        scenario_id=s.scenario_id,
                        reason=str(exc),
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_B1",
                        exception_type=type(exc).__name__,
                        runtime_ms=dt_ms,
                    )
                    raise

        timing_breakdown["mode_b1_seconds"] = round(time.perf_counter() - t_mode_b1_start, 4)
        df_mode_b1 = pd.DataFrame([r.to_flat_dict() for r_list in mode_b1_results.values() for r in r_list])
        df_mode_b1.to_csv(out_path / "recourse_b1_retrospective_results.csv", index=False)
        print(f"  Exported recourse_b1_retrospective_results.csv ({len(df_mode_b1)} rows, {timing_breakdown['mode_b1_seconds']:.2f}s)")

        # 6. Mode B2: Rolling-Horizon Online Recourse (Non-Anticipative)
        print("\n[Step 6] Evaluating MODE B2: Rolling Online Recourse (Non-Anticipative)...")
        t_mode_b2_start = time.perf_counter()
        mode_b2_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
        all_online_traces = []
        for s in scenarios:
            realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
            for solver_name, init_res in initial_solvers:
                t0 = time.perf_counter()
                try:
                    r_b2 = evaluate_mode_b2_rolling_online_recourse(
                        initial_assignments=init_res.assignments,
                        realized_flights=realized_flights,
                        base_scheduled_flights=base_flights,
                        gates=all_gates,
                        config=config,
                        realization=s,
                        initial_solver_name=solver_name,
                    )
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    mode_b2_results[solver_name].append(r_b2)
                    if r_b2.decision_trace:
                        for tr in r_b2.decision_trace:
                            all_online_traces.append({"scenario_index": s.scenario_index, "initial_solver": solver_name, **tr})

                    ledger.record_evaluation_success(
                        scenario_id=s.scenario_id,
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_B2",
                        solver_status=r_b2.solver_status,
                        composite_feasible=r_b2.feasibility.composite_feasible,
                        objective_value=r_b2.objective_value if r_b2.objective_value is not None else 0.0,
                        runtime_ms=dt_ms,
                    )
                except Exception as exc:
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    ledger.record_evaluation_failure(
                        scenario_id=s.scenario_id,
                        reason=str(exc),
                        realization_hash=s.realization_hash,
                        initial_plan_solver=solver_name,
                        recourse_mode="MODE_B2",
                        exception_type=type(exc).__name__,
                        runtime_ms=dt_ms,
                    )
                    raise

        timing_breakdown["mode_b2_seconds"] = round(time.perf_counter() - t_mode_b2_start, 4)
        df_mode_b2 = pd.DataFrame([r.to_flat_dict() for r_list in mode_b2_results.values() for r in r_list])
        df_mode_b2.to_csv(out_path / "recourse_b2_online_results.csv", index=False)
        print(f"  Exported recourse_b2_online_results.csv ({len(df_mode_b2)} rows, {timing_breakdown['mode_b2_seconds']:.2f}s)")

        # 7. Mode C1: Heuristic Greedy Foresight Benchmark
        print("\n[Step 7] Evaluating MODE C1: Heuristic Greedy Foresight Benchmark...")
        t_mode_c1_start = time.perf_counter()
        mode_c1_results = []
        for s in scenarios:
            realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
            t0 = time.perf_counter()
            try:
                r_c1 = evaluate_mode_c_greedy_foresight(
                    realized_flights=realized_flights,
                    gates=all_gates,
                    config=config,
                    realization=s,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                mode_c1_results.append(r_c1)
                ledger.record_evaluation_success(
                    scenario_id=s.scenario_id,
                    realization_hash=s.realization_hash,
                    initial_plan_solver="ForesightGreedy",
                    recourse_mode="MODE_C1",
                    solver_status=r_c1.solver_status,
                    composite_feasible=r_c1.feasibility.composite_feasible,
                    objective_value=r_c1.objective_value if r_c1.objective_value is not None else 0.0,
                    runtime_ms=dt_ms,
                )
            except Exception as exc:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                ledger.record_evaluation_failure(
                    scenario_id=s.scenario_id,
                    reason=str(exc),
                    realization_hash=s.realization_hash,
                    initial_plan_solver="ForesightGreedy",
                    recourse_mode="MODE_C1",
                    exception_type=type(exc).__name__,
                    runtime_ms=dt_ms,
                )
                raise

        timing_breakdown["mode_c1_seconds"] = round(time.perf_counter() - t_mode_c1_start, 4)
        df_mode_c1 = pd.DataFrame([r.to_flat_dict() for r in mode_c1_results])
        df_mode_c1.to_csv(out_path / "foresight_c1_greedy_results.csv", index=False)
        print(f"  Exported foresight_c1_greedy_results.csv ({len(df_mode_c1)} rows, {timing_breakdown['mode_c1_seconds']:.2f}s)")

        # 8. Mode C2: CP-SAT Optimal Foresight Oracle (Mathematical Proof)
        print("\n[Step 8] Evaluating MODE C2: CP-SAT Mathematical Optimal Oracle...")
        t_mode_c2_start = time.perf_counter()
        mode_c2_results = []
        for s in scenarios:
            realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
            t0 = time.perf_counter()
            try:
                r_c2 = evaluate_mode_c_optimal_foresight(
                    realized_flights=realized_flights,
                    gates=all_gates,
                    config=config,
                    realization=s,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                mode_c2_results.append(r_c2)
                ledger.record_evaluation_success(
                    scenario_id=s.scenario_id,
                    realization_hash=s.realization_hash,
                    initial_plan_solver="ForesightCPSat",
                    recourse_mode="MODE_C2",
                    solver_status=r_c2.solver_status,
                    composite_feasible=r_c2.feasibility.composite_feasible,
                    objective_value=r_c2.objective_value if r_c2.objective_value is not None else 0.0,
                    runtime_ms=dt_ms,
                )
            except Exception as exc:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                ledger.record_evaluation_failure(
                    scenario_id=s.scenario_id,
                    reason=str(exc),
                    realization_hash=s.realization_hash,
                    initial_plan_solver="ForesightCPSat",
                    recourse_mode="MODE_C2",
                    exception_type=type(exc).__name__,
                    runtime_ms=dt_ms,
                )
                raise

        timing_breakdown["mode_c2_seconds"] = round(time.perf_counter() - t_mode_c2_start, 4)
        df_mode_c2 = pd.DataFrame([r.to_flat_dict() for r in mode_c2_results])
        df_mode_c2.to_csv(out_path / "foresight_c2_optimal_results.csv", index=False)
        print(f"  Exported foresight_c2_optimal_results.csv ({len(df_mode_c2)} rows, {timing_breakdown['mode_c2_seconds']:.2f}s)")

        # 9. Paired CRN Comparisons
        print("\n[Step 9] Computing paired CRN statistical comparisons...")
        paired_comparisons = [
            compute_remediated_paired_comparison(
                mode_a_results["Greedy"],
                mode_b2_results["Greedy"],
                label_a="ModeA_FixedPlan",
                label_b="ModeB2_OnlineRecourse",
            ),
            compute_remediated_paired_comparison(
                mode_b1_results["Greedy"],
                mode_b2_results["Greedy"],
                label_a="ModeB1_RetrospectiveRecourse",
                label_b="ModeB2_OnlineRecourse",
            ),
            compute_remediated_paired_comparison(
                mode_c1_results,
                mode_c2_results,
                label_a="ModeC1_GreedyForesightBenchmark",
                label_b="ModeC2_CPSatOptimalOracle",
            ),
            compute_remediated_paired_comparison(
                mode_b2_results["Greedy"],
                mode_c2_results,
                label_a="ModeB2_OnlineRecourse",
                label_b="ModeC2_CPSatOptimalOracle",
            ),
        ]
        df_paired = pd.DataFrame(paired_comparisons)
        df_paired.to_csv(out_path / "paired_comparison.csv", index=False)
        print(f"  Exported paired_comparison.csv ({len(df_paired)} paired tests)")

        # 10. Rigorous Ledger Validation Gate
        print("\n[Step 10] Validating Execution Ledger invariants...")
        ledger.validate_ledger(required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS)
        ledger.validate_paired_crn(
            required_solvers=["Greedy", "CPSat", "Hybrid"],
            required_modes=["MODE_A", "MODE_B1", "MODE_B2"],
        )
        print("  [LEDGER PASS] All conservation equations, protocol slots, and CRN pairings verified.")

        # Export raw ledger records
        ledger_df = ledger.to_evaluation_dataframe()
        ledger_df.to_csv(out_path / "execution_ledger_entries.csv", index=False)
        gen_df = ledger.to_generation_dataframe()
        gen_df.to_csv(out_path / "execution_ledger_generation.csv", index=False)
        with open(out_path / "execution_ledger_summary.json", "w", encoding="utf-8") as f:
            json.dump(ledger.to_summary_dict(), f, indent=2)
        print(f"  Exported execution_ledger_entries.csv ({len(ledger_df)} rows)")
        print(f"  Exported execution_ledger_generation.csv ({len(gen_df)} rows)")
        print("  Exported execution_ledger_summary.json")

        t_pipeline_end = time.perf_counter()
        timing_breakdown["total_pipeline_seconds"] = round(t_pipeline_end - t_pipeline_start, 4)

        # 11. Statistical Summary Export
        print("\n[Step 11] Compiling statistical summaries...")
        ledger_summary = ledger.compute_summary()
        stats_summary = {
            "pipeline": "RemediatedMonteCarloEngineG2",
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "n_requested": n_scenarios,
            "n_generated": ledger_summary["accounting"]["n_generated_realizations"],
            "n_evaluated": ledger_summary["accounting"]["n_completed_evaluations"],
            "n_failed": ledger_summary["accounting"]["n_evaluation_failures"],
            "source_hash": source_hash,
            "config_hash": config_hash,
            "ledger_accounting": ledger_summary["accounting"],
            "ledger_rates": ledger.compute_rates(),
            "timing_breakdown": timing_breakdown,
            "scenarios_seed": seed,
            "canonical_scenario_id": "SCEN_P09_CANONICAL_120",
            "mode_a_fixed_plan": {
                solver: compute_remediated_statistics(r_list, requested_n=n_scenarios)
                for solver, r_list in mode_a_results.items()
            },
            "mode_b1_retrospective": {
                solver: compute_remediated_statistics(r_list, requested_n=n_scenarios)
                for solver, r_list in mode_b1_results.items()
            },
            "mode_b2_online_recourse": {
                solver: compute_remediated_statistics(r_list, requested_n=n_scenarios)
                for solver, r_list in mode_b2_results.items()
            },
            "mode_c1_greedy_foresight": compute_remediated_statistics(mode_c1_results, requested_n=n_scenarios),
            "mode_c2_optimal_oracle": compute_remediated_statistics(mode_c2_results, requested_n=n_scenarios),
        }
        with open(out_path / "statistical_summary.json", "w", encoding="utf-8") as f:
            json.dump(stats_summary, f, indent=2)
        print("  Exported statistical_summary.json")

        # 12. Failures Accounting
        acc = ledger_summary["accounting"]
        failures_record = {
            "pipeline": "RemediatedMonteCarloEngineG2",
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_requested_realizations": acc["n_requested_realizations"],
            "total_generated_realizations": acc["n_generated_realizations"],
            "total_expected_evaluations": acc["n_expected_evaluations"],
            "total_completed_evaluations": acc["n_completed_evaluations"],
            "total_evaluation_failures": acc["n_evaluation_failures"],
            "total_timeouts": acc["n_timeouts"],
            "failed_evaluations": [e.to_dict() for e in ledger.entries if e.evaluation_status != "SUCCESS"],
            "silent_drop_audit": {
                "silent_drops_detected": acc["n_missing_evaluations"] > 0,
                "missing_evaluations_count": acc["n_missing_evaluations"],
                "accounting_verified": (acc["n_missing_evaluations"] == 0 and acc["n_completed_evaluations"] == len(scenarios) * len(CANONICAL_PROTOCOL_EVALUATIONS)),
            },
        }
        with open(out_path / "failures.json", "w", encoding="utf-8") as f:
            json.dump(failures_record, f, indent=2)
        print("  Exported failures.json")

        # 13. Simulation Manifest Export (Marked COMPLETE)
        manifest = {
            "pipeline": "RemediatedMonteCarloEngineG2",
            "schema_version": "v2.1",
            "status": "COMPLETE",
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_scenarios": n_scenarios,
            "n_evaluations": len(ledger.entries),
            "seed": seed,
            "source_hash": source_hash,
            "config_hash": config_hash,
            "timing_breakdown": timing_breakdown,
            "copula": {
                "family": "Gaussian",
                "rho": 0.45,
                "is_positive_definite": True,
                "eigenvalues": [0.55, 1.45],
            },
            "marginal_distributions": {
                "arrival": {"family": "Student-t", "df": 4.5, "loc": 5.0, "scale": 18.0},
                "departure": {"family": "Student-t", "df": 4.0, "loc": 8.0, "scale": 22.0},
            },
            "modes": {
                "MODE_A_FIXED_PLAN": {
                    "information_regime": InformationRegime.PRE_OPERATIONAL.value,
                    "reoptimizations": 0,
                    "deployable": True,
                },
                "MODE_B1_RETROSPECTIVE_RECOURSE": {
                    "information_regime": InformationRegime.RETROSPECTIVE.value,
                    "recourse_policy": "FULL_INFORMATION_RETROSPECTIVE",
                    "deployable": False,
                    "scientific_status": "RETROSPECTIVE_BENCHMARK",
                },
                "MODE_B2_ONLINE_RECOURSE": {
                    "information_regime": InformationRegime.ONLINE_RECOURSE.value,
                    "recourse_policy": "ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN",
                    "deployable": True,
                    "scientific_status": "CAUSAL_ONLINE_RECOURSE",
                },
                "MODE_C_GREEDY_FORESIGHT": {
                    "information_regime": InformationRegime.FULL_FORESIGHT.value,
                    "recourse_policy": "HEURISTIC_FULL_FORESIGHT_BENCHMARK",
                    "deployable": False,
                    "scientific_status": "HEURISTIC_FORESIGHT_BASELINE",
                },
                "MODE_C_OPTIMAL_ORACLE": {
                    "information_regime": InformationRegime.FULL_FORESIGHT.value,
                    "recourse_policy": "PROVEN_MATHEMATICAL_OPTIMAL_FORESIGHT",
                    "deployable": False,
                    "scientific_status": "PROVEN_MATHEMATICAL_OPTIMAL_LOWER_BOUND",
                },
            },
            "artifacts_generated": [
                "gate_inventory.json",
                "scenario_index.csv",
                "fixed_plan_results.csv",
                "recourse_b1_retrospective_results.csv",
                "recourse_b2_online_results.csv",
                "foresight_c1_greedy_results.csv",
                "foresight_c2_optimal_results.csv",
                "paired_comparison.csv",
                "execution_ledger_entries.csv",
                "execution_ledger_generation.csv",
                "execution_ledger_summary.json",
                "statistical_summary.json",
                "failures.json",
            ],
        }
        with open(out_path / "simulation_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print("  Exported simulation_manifest.json (Status: COMPLETE)")

        print(f"\n[SUCCESS] MC500 Production Runner Completed Successfully in {timing_breakdown['total_pipeline_seconds']:.2f}s.")
        return stats_summary

    except Exception as pipeline_err:
        print(f"\n[PIPELINE EXCEPTION] Run interrupted: {pipeline_err}")
        # Save partial ledger and mark run as FAILED
        if "ledger" in locals():
            ledger.to_evaluation_dataframe().to_csv(out_path / "execution_ledger_entries_partial.csv", index=False)
            failed_manifest = {
                "pipeline": "RemediatedMonteCarloEngineG2",
                "status": "FAILED",
                "run_id": run_id,
                "error_message": str(pipeline_err),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            with open(out_path / "simulation_manifest_failed.json", "w", encoding="utf-8") as f:
                json.dump(failed_manifest, f, indent=2)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aeolus Remediated Monte Carlo Pipeline (G2/MC500 Production Runner)"
    )
    parser.add_argument(
        "--n-scenarios",
        "-n",
        type=int,
        default=100,
        help="Number of stochastic realizations to generate and evaluate (default: 100)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=202601,
        help="Base random seed for copula scenario generation (default: 202601)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Run output directory (default: artifacts/remediation/monte_carlo_mc500/<run_id>/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run flag (forces N=5 scenarios for quick verification)",
    )
    parser.add_argument(
        "positional_n",
        nargs="?",
        type=int,
        default=None,
        help="Positional argument for number of scenarios (backward compatibility)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    n = args.n_scenarios
    if args.positional_n is not None:
        n = args.positional_n
    if args.dry_run:
        n = 5

    run_g2_remediation_pipeline(
        n_scenarios=n,
        seed=args.seed,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
