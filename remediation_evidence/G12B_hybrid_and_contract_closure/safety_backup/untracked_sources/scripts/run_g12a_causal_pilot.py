"""AEOLUS-G12A: Causal Online Recourse Pilot Experiment Runner.

Executes:
- Canonical scenario (120 flights, 25 contact gates, 5 remote stands).
- Modes: Mode A, Mode B1, Mode B2 (Causal), Mode C1, Mode C2.
- Preserves all frozen artifacts (zero overwrite).
- Outputs strictly to: artifacts/remediation/monte_carlo_g12a/
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

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
    RealizedScenario,
    apply_delays_to_flights,
)
from src.simulation.monte_carlo_engine_v2 import (
    compute_remediated_paired_comparison,
    compute_remediated_statistics,
    evaluate_mode_a_fixed_plan_v2,
    evaluate_mode_b1_retrospective_recourse,
    evaluate_mode_b2_rolling_online_recourse,
    evaluate_mode_c_greedy_foresight,
    evaluate_mode_c_optimal_foresight,
)

OUTPUT_DIR = ROOT_DIR / "artifacts" / "remediation" / "monte_carlo_g12a"


def run_g12a_pilot(n_scenarios: int = 20, seed: int = 202601) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print(f"AEOLUS-G12A: CAUSAL ONLINE RECOURSE PILOT (N={n_scenarios}, SEED={seed})")
    print("=" * 80)
    print(f"Output Directory: {OUTPUT_DIR.resolve()}")

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
    contact_gates, overflow_gate = scenario_to_gates(scen)
    all_gates = contact_gates + [overflow_gate]

    config = GateOptimizationConfig(
        finite_remote_capacity=N_REMOTE_STANDS,
        enforce_remote_capacity=True,
        allow_unbounded_overflow=False,
        time_limit_seconds=1.5,
        random_seed=seed,
    )

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
    scenarios = generator.generate_scenarios(base_flights, scenario_prefix=f"MC_G12A_{n_scenarios}")
    print(f"  Generated {len(scenarios)} realizations successfully.")

    # 4. Mode A
    print("\n[Step 4] Evaluating MODE A: Fixed Plan Robustness...")
    mode_a_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_a_results["Greedy"].append(evaluate_mode_a_fixed_plan_v2(res_greedy.assignments, realized_flights, all_gates, config, s, "Greedy"))
        mode_a_results["CPSat"].append(evaluate_mode_a_fixed_plan_v2(res_cpsat.assignments, realized_flights, all_gates, config, s, "CPSat"))
        mode_a_results["Hybrid"].append(evaluate_mode_a_fixed_plan_v2(res_hybrid.assignments, realized_flights, all_gates, config, s, "Hybrid"))

    # 5. Mode B1
    print("\n[Step 5] Evaluating MODE B1: Retrospective Recourse...")
    mode_b1_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_b1_results["Greedy"].append(evaluate_mode_b1_retrospective_recourse(res_greedy.assignments, realized_flights, all_gates, config, s, "Greedy", "DeterministicGreedy"))
        mode_b1_results["CPSat"].append(evaluate_mode_b1_retrospective_recourse(res_cpsat.assignments, realized_flights, all_gates, config, s, "CPSat", "DeterministicGreedy"))
        mode_b1_results["Hybrid"].append(evaluate_mode_b1_retrospective_recourse(res_hybrid.assignments, realized_flights, all_gates, config, s, "Hybrid", "DeterministicGreedy"))

    # 6. Mode B2 (Causal Online Recourse)
    print("\n[Step 6] Evaluating MODE B2: Causal Online Recourse (Non-Anticipative)...")
    mode_b2_results = {"Greedy": [], "CPSat": [], "Hybrid": []}
    b2_traces = []
    t_b2_start = time.perf_counter()
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        for init_name, init_res in [("Greedy", res_greedy), ("CPSat", res_cpsat), ("Hybrid", res_hybrid)]:
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
            mode_b2_results[init_name].append(r_b2)
            for tr in r_b2.decision_trace:
                b2_traces.append({"scenario_index": s.scenario_index, "initial_solver": init_name, **tr})
    t_b2_total = time.perf_counter() - t_b2_start
    print(f"  Mode B2 completed in {t_b2_total:.2f}s ({len(b2_traces)} total reassignments across all runs)")

    # 7. Mode C1 & C2
    print("\n[Step 7] Evaluating MODE C1 & C2 Foresight Baselines...")
    mode_c1_results = []
    mode_c2_results = []
    for s in scenarios:
        realized_flights = apply_delays_to_flights(base_flights, s.arrival_delays, s.departure_delays)
        mode_c1_results.append(evaluate_mode_c_greedy_foresight(realized_flights, all_gates, config, s))
        mode_c2_results.append(evaluate_mode_c_optimal_foresight(realized_flights, all_gates, config, s))

    # Compile statistics
    print("\n[Step 8] Compiling statistical summaries...")
    stats_dict: dict[str, Any] = {}
    for solver_key in ["Greedy", "CPSat", "Hybrid"]:
        stats_dict[f"ModeA_{solver_key}"] = compute_remediated_statistics(mode_a_results[solver_key], requested_n=n_scenarios)
        stats_dict[f"ModeB1_{solver_key}"] = compute_remediated_statistics(mode_b1_results[solver_key], requested_n=n_scenarios)
        stats_dict[f"ModeB2_{solver_key}"] = compute_remediated_statistics(mode_b2_results[solver_key], requested_n=n_scenarios)

    stats_dict["ModeC1_Greedy"] = compute_remediated_statistics(mode_c1_results, requested_n=n_scenarios)
    stats_dict["ModeC2_CPSat"] = compute_remediated_statistics(mode_c2_results, requested_n=n_scenarios)

    # Paired comparisons
    paired_dict: dict[str, Any] = {}
    for solver_key in ["Greedy", "CPSat", "Hybrid"]:
        paired_dict[f"B2_vs_A_{solver_key}"] = compute_remediated_paired_comparison(
            mode_b2_results[solver_key], mode_a_results[solver_key], f"ModeB2_{solver_key}", f"ModeA_{solver_key}"
        )
        paired_dict[f"B1_vs_A_{solver_key}"] = compute_remediated_paired_comparison(
            mode_b1_results[solver_key], mode_a_results[solver_key], f"ModeB1_{solver_key}", f"ModeA_{solver_key}"
        )

    # Export CSVs
    df_b2 = pd.DataFrame([r.to_flat_dict() for r_list in mode_b2_results.values() for r in r_list])
    df_b2.to_csv(OUTPUT_DIR / f"mode_b2_results_n{n_scenarios}.csv", index=False)

    summary_payload = {
        "n_scenarios": n_scenarios,
        "seed": seed,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "statistics": stats_dict,
        "paired_comparisons": paired_dict,
    }
    with open(OUTPUT_DIR / f"statistical_summary_n{n_scenarios}.json", "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)

    print(f"\nSuccessfully generated and exported results for N={n_scenarios} scenarios!")
    return summary_payload


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_g12a_pilot(n_scenarios=n, seed=202601)
