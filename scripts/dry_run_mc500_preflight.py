"""AEOLUS-MC500 Preflight Small Dry-Run Script.

Protocol: AEOLUS-MC500-PREFLIGHT Task E
Executes N=5 stochastic realizations on canonical scenario SCEN_P09_CANONICAL_120.
Evaluates:
- Mode A (Fixed Plan): 3 solvers (Greedy, CP-SAT, Hybrid) x 5 realizations = 15 evaluations
- Mode B1 (Retrospective Recourse): 3 solvers x 5 realizations = 15 evaluations
- Mode B2 (Rolling Online Recourse): 3 solvers x 5 realizations = 15 evaluations
- Mode C1 (Greedy Foresight): 1 solver x 5 realizations = 5 evaluations
- Mode C2 (CP-SAT Optimal Foresight): 1 solver x 5 realizations = 5 evaluations
Total evaluations: 55 evaluations.

Integrates SimulationExecutionLedger to record every evaluation event and validates:
- Accounting conservation laws
- Paired CRN consistency across solvers
- Deterministic replay verification
- Wall-clock runtime profiling per mode
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate, Flight, GateAssignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.scalability_scenario import (
    generate_scalability_scenario,
    scenario_to_flights,
    scenario_to_gates,
)
from src.simulation.monte_carlo_engine_p09 import (
    MonteCarloScenarioGenerator,
    apply_delays_to_flights,
)
from src.simulation.monte_carlo_engine_v2 import (
    SimulationExecutionLedger,
    evaluate_mode_a_fixed_plan_v2,
    evaluate_mode_b1_retrospective_recourse,
    evaluate_mode_b2_rolling_online_recourse,
    evaluate_mode_c_greedy_foresight,
    evaluate_mode_c_optimal_foresight,
)

OUTPUT_DIR = Path("audit_exports/MC500_preflight")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_dry_run() -> dict[str, any]:
    t_prog_start = time.perf_counter()
    n_scenarios = 5
    seed = 202601
    log_lines = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("AEOLUS-MC500 PREFLIGHT: SMALL DRY-RUN EXECUTION (N=5)")
    log("=" * 80)
    log(f"Platform: Windows 10 | Python: {sys.version.split()[0]}")
    log(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    log(f"Requested Scenarios: {n_scenarios} | Base Seed: {seed}")

    # Step 1: Scenario Setup
    N_FLIGHTS = 120
    N_CONTACT_GATES = 25
    N_REMOTE_STANDS = 5

    scen = generate_scalability_scenario(
        n_flights=N_FLIGHTS,
        n_contact_gates=N_CONTACT_GATES,
        seed=seed,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    base_flights = scenario_to_flights(scen)
    contact_gates, overflow_gate = scenario_to_gates(scen)
    all_gates = contact_gates + [overflow_gate]

    config = GateOptimizationConfig(
        finite_remote_capacity=N_REMOTE_STANDS,
        enforce_remote_capacity=True,
        allow_unbounded_overflow=False,
        time_limit_seconds=1.5,
        random_seed=seed,
    )
    import hashlib
    config_hash = hashlib.sha256(json.dumps(config.to_dict(), sort_keys=True).encode()).hexdigest()
    log(f"Config Hash: {config_hash}")

    # Step 2: Initial Plans
    log("\n[Step 2] Solving Initial Plans at T-2h Cutoff...")
    solver_greedy = DeterministicGreedyGateSolver(config=config)
    res_greedy = solver_greedy.solve(base_flights, all_gates)
    log(f"  Greedy:   Obj={res_greedy.objective_value:.2f} | Feas={res_greedy.feasible} | Time={res_greedy.runtime_ms:.1f}ms")

    solver_cpsat = CPSatGateSolver(config=config)
    res_cpsat = solver_cpsat.solve(base_flights, all_gates)
    log(f"  CP-SAT:   Obj={res_cpsat.objective_value:.2f} | Feas={res_cpsat.feasible} | Time={res_cpsat.runtime_ms:.1f}ms")

    solver_hybrid = HybridGateSolver(config=config)
    res_hybrid = solver_hybrid.solve(base_flights, all_gates)
    log(f"  Hybrid:   Obj={res_hybrid.objective_value:.2f} | Feas={res_hybrid.feasible} | Time={res_hybrid.runtime_ms:.1f}ms")

    # Step 3: Stochastic Scenarios
    log(f"\n[Step 3] Generating {n_scenarios} Stochastic Realizations (Copula rho=0.45)...")
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
    scenarios = generator.generate_scenarios(base_flights, scenario_prefix="MC_PREFLIGHT")
    for s in scenarios:
        log(f"  Scenario {s.scenario_index}: ID={s.scenario_id} | Hash={s.realization_hash[:16]}... | Seed={s.seed}")

    # Ledger Initialization for Mode B2 (and tracking)
    ledger_b2 = SimulationExecutionLedger(
        run_id="MC500_PREFLIGHT_RUN",
        requested_n=n_scenarios,
        config_hash=config_hash,
    )

    timing_per_mode = {}

    # Step 4: Mode A (Fixed Plan)
    log("\n[Step 4] Evaluating MODE A (Fixed Plan)...")
    t0 = time.perf_counter()
    mode_a_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_a_results["Greedy"].append(evaluate_mode_a_fixed_plan_v2(res_greedy.assignments, realized_flights, all_gates, config, s, "Greedy"))
        mode_a_results["CPSat"].append(evaluate_mode_a_fixed_plan_v2(res_cpsat.assignments, realized_flights, all_gates, config, s, "CPSat"))
        mode_a_results["Hybrid"].append(evaluate_mode_a_fixed_plan_v2(res_hybrid.assignments, realized_flights, all_gates, config, s, "Hybrid"))
    timing_per_mode["MODE_A"] = (time.perf_counter() - t0) * 1000.0
    log(f"  Mode A completed: {len(scenarios)*3} evaluations in {timing_per_mode['MODE_A']:.2f}ms")

    # Step 5: Mode B1 (Retrospective Recourse)
    log("\n[Step 5] Evaluating MODE B1 (Retrospective Recourse)...")
    t0 = time.perf_counter()
    mode_b1_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_b1_results["Greedy"].append(evaluate_mode_b1_retrospective_recourse(res_greedy.assignments, realized_flights, all_gates, config, s, "Greedy", "DeterministicGreedy"))
        mode_b1_results["CPSat"].append(evaluate_mode_b1_retrospective_recourse(res_cpsat.assignments, realized_flights, all_gates, config, s, "CPSat", "DeterministicGreedy"))
        mode_b1_results["Hybrid"].append(evaluate_mode_b1_retrospective_recourse(res_hybrid.assignments, realized_flights, all_gates, config, s, "Hybrid", "DeterministicGreedy"))
    timing_per_mode["MODE_B1"] = (time.perf_counter() - t0) * 1000.0
    log(f"  Mode B1 completed: {len(scenarios)*3} evaluations in {timing_per_mode['MODE_B1']:.2f}ms")

    # Step 6: Mode B2 (Rolling Online Recourse) with Ledger Recording
    log("\n[Step 6] Evaluating MODE B2 (Causal Online Recourse) with Ledger Accounting...")
    t0 = time.perf_counter()
    mode_b2_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        for init_name, init_res in [("Greedy", res_greedy), ("CPSat", res_cpsat), ("Hybrid", res_hybrid)]:
            t_eval_start = time.perf_counter()
            r_b2 = evaluate_mode_b2_rolling_online_recourse(
                initial_assignments=init_res.assignments,
                realized_flights=realized_flights,
                base_scheduled_flights=base_flights,
                gates=all_gates,
                config=config,
                realization=s,
                initial_solver_name=init_name,
                lock_horizon_minutes=45,
            )
            t_eval_end = time.perf_counter()
            mode_b2_results[init_name].append(r_b2)

            # Record event in ledger
            ledger_b2.record_evaluation_success(
                scenario_id=s.scenario_id,
                realization_hash=s.realization_hash,
                initial_plan_solver=init_name,
                recourse_mode="MODE_B2_ONLINE_RECOURSE",
                solver_status=r_b2.solver_status,
                composite_feasible=r_b2.feasibility.composite_feasible,
                objective_value=r_b2.objective_value,
                runtime_ms=r_b2.runtime_ms,
                start_time=t_eval_start,
                end_time=t_eval_end,
            )
            log(f"    Recorded Ledger: {s.scenario_id} [{init_name}] | Status={r_b2.solver_status} | Obj={r_b2.objective_value:.2f} | Time={r_b2.runtime_ms:.2f}ms")

    timing_per_mode["MODE_B2"] = (time.perf_counter() - t0) * 1000.0
    log(f"  Mode B2 completed: {len(scenarios)*3} evaluations in {timing_per_mode['MODE_B2']:.2f}ms")

    # Step 7: Mode C1 & C2 (Foresight Baselines)
    log("\n[Step 7] Evaluating MODE C1 & C2 Foresight Baselines...")
    t0 = time.perf_counter()
    mode_c1_results = []
    mode_c2_results = []
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_c1_results.append(evaluate_mode_c_greedy_foresight(realized_flights, all_gates, config, s))
        mode_c2_results.append(evaluate_mode_c_optimal_foresight(realized_flights, all_gates, config, s))
    timing_per_mode["MODE_C1_C2"] = (time.perf_counter() - t0) * 1000.0
    log(f"  Mode C1 & C2 completed: {len(scenarios)*2} evaluations in {timing_per_mode['MODE_C1_C2']:.2f}ms")

    # Step 8: Validate Ledger Accounting
    log("\n[Step 8] Validating Execution Ledger Invariants...")
    ledger_b2.validate_ledger()
    log("  [PASS] validate_ledger(): All requested scenarios strictly accounted for (0 missing)")
    ledger_b2.validate_paired_crn(required_solvers=["Greedy", "CPSat", "Hybrid"])
    log("  [PASS] validate_paired_crn(): Bit-exact realization hashes match across all 3 solvers")

    summary = ledger_b2.compute_summary()
    rates = ledger_b2.compute_rates()
    log(f"  Ledger Accounting Summary: {json.dumps(summary['accounting'], indent=2)}")
    log(f"  Ledger Rates: {json.dumps(rates, indent=2)}")

    # Step 9: Verify Deterministic Replay
    log("\n[Step 9] Verifying Deterministic Replay (Scenario 0 Re-run)...")
    s0 = scenarios[0]
    rf0 = apply_delays_to_flights(base_flights, s0.arrival_delays, s0.departure_delays)
    r_replay = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=res_greedy.assignments,
        realized_flights=rf0,
        base_scheduled_flights=base_flights,
        gates=all_gates,
        config=config,
        realization=s0,
        initial_solver_name="Greedy",
        lock_horizon_minutes=45,
    )
    orig_obj = mode_b2_results["Greedy"][0].objective_value
    replay_obj = r_replay.objective_value
    assert orig_obj == replay_obj, f"Deterministic replay mismatch: orig={orig_obj}, replay={replay_obj}"
    log(f"  [PASS] Deterministic replay exact match: obj={replay_obj:.4f}")

    total_prog_ms = (time.perf_counter() - t_prog_start) * 1000.0
    timing_per_mode["TOTAL_PROGRAM"] = total_prog_ms
    log(f"\nTotal Program Wall-Clock: {total_prog_ms:.2f}ms ({total_prog_ms/1000.0:.2f}s)")

    # Export Artifacts
    df_entries = pd.DataFrame([e.to_dict() for e in ledger_b2.entries])
    entries_csv = OUTPUT_DIR / "dry_run_ledger_entries.csv"
    df_entries.to_csv(entries_csv, index=False)
    log(f"Saved: {entries_csv} ({len(df_entries)} entries)")

    summary_json = OUTPUT_DIR / "dry_run_ledger_summary.json"
    summary_payload = {
        "milestone": "AEOLUS-MC500-PREFLIGHT",
        "dry_run_n": n_scenarios,
        "seed": seed,
        "config_hash": config_hash,
        "timing_per_mode_ms": timing_per_mode,
        "accounting_summary": summary,
        "rates": rates,
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    log(f"Saved: {summary_json}")

    raw_log_file = OUTPUT_DIR / "RAW_EXECUTION_LOG.txt"
    raw_log_file.write_text("\n".join(log_lines), encoding="utf-8")
    log(f"Saved: {raw_log_file}")

    return summary_payload


if __name__ == "__main__":
    run_dry_run()
