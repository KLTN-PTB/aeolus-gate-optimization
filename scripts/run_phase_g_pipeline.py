"""Phase G — End-to-End Monte Carlo -> Gate Simulation -> Optimization Pipeline.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Pipeline flow:
flight features
→ marginal predictive distribution (B5 NGBoost Student-T)
→ dependence layer (D2 Gaussian Copula)
→ joint delay sample (MonteCarloScenarioRunner)
→ synthetic operational timeline (AircraftTurnModel)
→ gate occupancy & conflict detection (ConflictDetector)
→ assignment solvers (Greedy vs CP-SAT vs CP-SAT + SA)
→ artifact export (artifacts/end_to_end/)
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.baselines import B5NGBoostStudentT
from src.models.probabilistic.contracts import (
    PREDETERMINED_DEPLOYMENT_SEED,
    PROBABILISTIC_PREDICTOR_COLUMNS,
)
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    StudentTMarginalDistribution,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts
from src.simulation.scenario_runner import MonteCarloScenarioRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("phase_g_pipeline")


def run_phase_g_pipeline(
    *,
    convergence_sample_sizes: tuple[int, ...] = (100, 250, 500, 1000, 2500),
    n_optimization_scenarios: int = 20,
    n_contact_gates: int = 20,
    project_root: Path | None = None,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
) -> dict[str, Any]:
    """Execute end-to-end Monte Carlo simulation, optimization benchmark, and convergence audit."""
    root = project_root or PROJECT_ROOT
    artifacts_dir = root / "artifacts" / "end_to_end"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    start_wall_time = time.time()
    LOGGER.info("=" * 80)
    LOGGER.info("PHASE G: MONTE CARLO -> GATE SIMULATION -> OPTIMIZATION PIPELINE")
    LOGGER.info("Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md")
    LOGGER.info("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Load Development Data (2016-2022 train, 2023 development evaluation)
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- [Step 1] Loading Development Data & Fitting Marginal Model ---")
    (
        X_train,
        _,
        y_train_reg,
        _,
        X_val,
        _,
        y_val_reg,
        val_flight_keys,
    ) = load_stratified_fold_data(
        train_years=[2016, 2017, 2018, 2019, 2020, 2021, 2022],
        val_year=2023,
        sample_train_per_year=1000,
        sample_val=3000,
        project_root=root,
        random_state=seed,
        feature_set="v1",
    )

    val_df = X_val.copy()
    val_df["flight_key"] = val_flight_keys.values
    if "flight_date" not in val_df.columns:
        val_df["flight_date"] = (
            val_df["calendar_year"].astype(int).astype(str)
            + "-"
            + val_df["calendar_month"].astype(int).astype(str).str.zfill(2)
            + "-"
            + val_df["calendar_day_of_month"].astype(int).astype(str).str.zfill(2)
        )

    # Fit frozen winning marginal model: B5 NGBoost Student-T
    LOGGER.info("Fitting frozen B5 NGBoost Student-T marginal model on development train...")
    b5_model = B5NGBoostStudentT(seed=seed, n_estimators=50, learning_rate=0.005)
    b5_model.fit(X_train, y_train_reg.to_numpy(dtype=np.float64))

    # Select operational flight batch (a congested development day with substantial volume)
    day_counts = val_df["flight_date"].value_counts()
    eligible_days = day_counts[day_counts >= 15].index.tolist()
    if not eligible_days:
        eligible_days = day_counts.head(5).index.tolist()
    target_day = eligible_days[0]

    day_df = val_df[val_df["flight_date"] == target_day].copy().reset_index(drop=True)
    # Target 50-70 flights for clear operational congestion
    if len(day_df) > 60:
        day_df = day_df.iloc[:60].copy()
    elif len(day_df) < 30 and len(val_df) >= 50:
        day_df = val_df.iloc[:50].copy().reset_index(drop=True)

    n_flights = len(day_df)
    LOGGER.info(f"Selected operational day {target_day} with {n_flights} flights.")

    # Generate marginal distributions for the flight batch
    pred_dist = b5_model.predict_distribution(day_df[list(PROBABILISTIC_PREDICTOR_COLUMNS)])
    marginals = [
        StudentTMarginalDistribution(
            mu=float(pred_dist["mu"][i]),
            sigma=float(pred_dist["sigma"][i]),
            df=float(pred_dist["df"][i]),
            discrete=True,
        )
        for i in range(n_flights)
    ]

    # Frozen winning dependence model: D2 Gaussian Copula
    LOGGER.info("Instantiating frozen D2 Gaussian Copula dependence mechanism...")
    dependence_model = GaussianCopulaDependenceModel(
        temporal_length_scale_minutes=120.0,
        carrier_correlation=0.15,
    )

    # -------------------------------------------------------------------------
    # STEP 2 & 3: Monte Carlo Scenario Runner & Scenario Independence
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- [Step 2 & 3] Monte Carlo Scenario Runner Execution ---")
    scenario_runner = MonteCarloScenarioRunner(dependence_model=dependence_model)

    # Construct contact gates and overflow stand
    gates = [
        Gate(
            gate_id=f"G_{i+1:02d}",
            gate_index=i,
            is_overflow=False,
        )
        for i in range(n_contact_gates)
    ]
    overflow_gate = Gate(
        gate_id="OVERFLOW_APRON",
        gate_index=n_contact_gates,
        is_overflow=True,
    )
    all_gates = gates + [overflow_gate]

    # Pre-calculate nominal gate assignments on scheduled arrival
    turn_model = AircraftTurnModel(
        min_turnaround_min=45,
        default_dwell_min=60,
        separation_buffer_min=15,
    )
    scheduled_turns = turn_model.synthesize_batch(
        flight_df=day_df,
        sampled_delays=np.zeros(n_flights, dtype=float),
    )
    # Assign nominal gates round-robin across contact gates
    nominal_map = {
        turn.flight_id: gates[i % n_contact_gates].gate_id
        for i, turn in enumerate(scheduled_turns)
    }

    # -------------------------------------------------------------------------
    # STEP 8: Monte Carlo Convergence Evaluation (N = 100, 250, 500, 1000, 2500)
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- [Step 8] Evaluating Monte Carlo Convergence Across Sample Sizes ---")
    convergence_records: list[dict[str, Any]] = []

    # Generate max sample size once to evaluate progressive stabilization
    max_N = max(convergence_sample_sizes)
    rng_master = np.random.default_rng(seed)
    max_delay_scenarios = scenario_runner.run_scenarios(
        marginals=marginals,
        flight_features=day_df,
        n_scenarios=max_N,
        rng=rng_master,
    )

    for n_scen in convergence_sample_sizes:
        sub_scenarios = max_delay_scenarios[:n_scen, :]
        sub_hash = hashlib.sha256(sub_scenarios.tobytes()).hexdigest()
        n_unique_scenarios = int(len(np.unique(sub_scenarios, axis=0)))

        has_conflicts_list: list[bool] = []
        durations_list: list[float] = []
        utilizations_list: list[float] = []
        objectives_list: list[float] = []

        greedy_fast = DeterministicGreedyGateSolver(config=GateOptimizationConfig())

        # Evaluate all n_scen scenarios (uncapped) to ensure true Monte Carlo convergence audit
        for s in range(n_scen):
            s_delays = sub_scenarios[s, :]
            s_turns = turn_model.synthesize_batch(day_df, s_delays, nominal_map)
            # Evaluate nominal conflict
            c_res = detect_conflicts(nominal_map, s_turns, all_gates)
            has_conflicts_list.append(c_res.has_conflicts)
            durations_list.append(c_res.total_conflict_duration_min)
            utilizations_list.append(c_res.gate_utilization_rate)

            # Evaluate greedy objective
            s_flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(s_turns)]
            g_res = greedy_fast.solve(s_flights, all_gates)
            objectives_list.append(g_res.objective_value)

        p95_dur = float(np.percentile(durations_list, 95.0))
        mean_obj = float(np.mean(objectives_list))
        var_obj = float(np.var(objectives_list))
        var_dur = float(np.var(durations_list))
        conf_prob = float(np.mean(has_conflicts_list))
        mean_util = float(np.mean(utilizations_list))

        rec = {
            "sample_size_N": n_scen,
            "scenarios_evaluated": n_scen,
            "scenario_matrix_hash": sub_hash,
            "number_of_unique_scenarios": n_unique_scenarios,
            "conflict_probability": conf_prob,
            "p95_conflict_duration_min": p95_dur,
            "expected_objective": mean_obj,
            "objective_variance": var_obj,
            "conflict_duration_variance": var_dur,
            "mean_utilization": mean_util,
        }
        convergence_records.append(rec)
        LOGGER.info(
            f"  N={n_scen:4d} | Hash: {sub_hash[:12]} | Unique: {n_unique_scenarios:4d} | "
            f"Conflict Prob: {conf_prob:.3f} | P95 Conflict Dur: {p95_dur:.1f}m | "
            f"Expected Obj: {mean_obj:.1f} (var={var_obj:.1f}) | Util: {mean_util:.3f}"
        )

    # -------------------------------------------------------------------------
    # STEP 6, 7, 9: Optimization Comparison Across Identical Scenarios
    # -------------------------------------------------------------------------
    LOGGER.info(f"\n--- [Steps 6, 7, 9] Optimization Comparison on {n_optimization_scenarios} Identical Scenarios ---")
    opt_delays = max_delay_scenarios[:n_optimization_scenarios, :]

    config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        time_limit_seconds=10.0,
        num_search_workers=1,
        random_seed=seed,
    )
    sa_config = SAConfig(
        T0=50.0,
        Tmin=0.01,
        cooling_rate=0.95,
        iterations=300,
        seed=seed,
    )

    greedy_solver = DeterministicGreedyGateSolver(config=config)
    cpsat_solver = CPSatGateSolver(config=config)
    sa_solver = SimulatedAnnealingGateSolver(config=config, sa_config=sa_config)

    scenario_summaries: list[dict[str, Any]] = []
    greedy_results: list[dict[str, Any]] = []
    cpsat_results: list[dict[str, Any]] = []
    sa_results: list[dict[str, Any]] = []

    for s in range(n_optimization_scenarios):
        scenario_id = f"SCEN_{s+1:03d}"
        s_delays = opt_delays[s, :]

        # 1. Synthesize turns
        turns = turn_model.synthesize_batch(day_df, s_delays, nominal_map)
        flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(turns)]

        # Summary of arrival delays in this scenario
        scenario_summaries.append(
            {
                "scenario_id": scenario_id,
                "n_flights": n_flights,
                "mean_arrival_delay_min": float(np.mean(s_delays)),
                "p95_arrival_delay_min": float(np.percentile(s_delays, 95.0)),
                "max_arrival_delay_min": float(np.max(s_delays)),
            }
        )

        # 2. Solve with Method 1: Greedy
        res_g = greedy_solver.solve(flights, all_gates)
        conf_g = detect_conflicts(res_g.assignments, turns, all_gates)
        greedy_results.append(
            {
                "scenario_id": scenario_id,
                "solver": "Greedy",
                "objective": res_g.objective_value,
                "conflicts": conf_g.conflict_count,
                "total_conflict_duration_min": conf_g.total_conflict_duration_min,
                "max_concurrent_occupancy": conf_g.peak_single_gate_concurrency,
                "gate_utilization": conf_g.gate_utilization_rate,
                "reassignments": sum(1 for a in res_g.assignments.values() if a.is_reassignment),
                "overflows": sum(1 for a in res_g.assignments.values() if a.is_overflow),
                "runtime_ms": res_g.runtime_ms,
                "feasibility": res_g.feasible,
            }
        )

        # 3. Solve with Method 2: CP-SAT
        res_cp = cpsat_solver.solve(flights, all_gates)
        conf_cp = detect_conflicts(res_cp.assignments, turns, all_gates)
        cpsat_results.append(
            {
                "scenario_id": scenario_id,
                "solver": "CP-SAT",
                "objective": res_cp.objective_value,
                "conflicts": conf_cp.conflict_count,
                "total_conflict_duration_min": conf_cp.total_conflict_duration_min,
                "max_concurrent_occupancy": conf_cp.peak_single_gate_concurrency,
                "gate_utilization": conf_cp.gate_utilization_rate,
                "reassignments": sum(1 for a in res_cp.assignments.values() if a.is_reassignment),
                "overflows": sum(1 for a in res_cp.assignments.values() if a.is_overflow),
                "runtime_ms": res_cp.runtime_ms,
                "feasibility": res_cp.feasible,
            }
        )

        # 4. Solve with Method 3: CP-SAT + SA
        res_sa = sa_solver.solve(
            flights,
            all_gates,
            initial_assignments=res_cp.assignments,
        )
        conf_sa = detect_conflicts(res_sa.assignments, turns, all_gates)
        sa_results.append(
            {
                "scenario_id": scenario_id,
                "solver": "CP-SAT+SA",
                "objective": res_sa.objective_value,
                "conflicts": conf_sa.conflict_count,
                "total_conflict_duration_min": conf_sa.total_conflict_duration_min,
                "max_concurrent_occupancy": conf_sa.peak_single_gate_concurrency,
                "gate_utilization": conf_sa.gate_utilization_rate,
                "reassignments": sum(1 for a in res_sa.assignments.values() if a.is_reassignment),
                "overflows": sum(1 for a in res_sa.assignments.values() if a.is_overflow),
                "runtime_ms": res_cp.runtime_ms + res_sa.runtime_ms,
                "feasibility": res_sa.feasible,
            }
        )

        if (s + 1) % 5 == 0 or (s + 1) == n_optimization_scenarios:
            LOGGER.info(
                f"  Evaluated {s+1}/{n_optimization_scenarios} scenarios | "
                f"Greedy Obj={res_g.objective_value:.1f}, CP-SAT Obj={res_cp.objective_value:.1f}, "
                f"SA Obj={res_sa.objective_value:.1f}"
            )

    # -------------------------------------------------------------------------
    # STEP 10: Save Artifacts (Parquet & JSON)
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- [Step 10] Exporting Parquet and JSON Manifest Artifacts ---")
    df_scen = pd.DataFrame(scenario_summaries)
    df_greedy = pd.DataFrame(greedy_results)
    df_cpsat = pd.DataFrame(cpsat_results)
    df_sa = pd.DataFrame(sa_results)

    df_scen.to_parquet(artifacts_dir / "scenario_summary.parquet", index=False)
    df_greedy.to_parquet(artifacts_dir / "greedy_results.parquet", index=False)
    df_cpsat.to_parquet(artifacts_dir / "cp_sat_results.parquet", index=False)
    df_sa.to_parquet(artifacts_dir / "sa_results.parquet", index=False)

    aggregate_metrics = {
        "evaluation_scope": {
            "target_day": target_day,
            "n_flights": n_flights,
            "n_contact_gates": n_contact_gates,
            "n_scenarios_evaluated": n_optimization_scenarios,
        },
        "greedy_aggregate": {
            "mean_objective": float(df_greedy["objective"].mean()),
            "mean_reassignments": float(df_greedy["reassignments"].mean()),
            "mean_overflows": float(df_greedy["overflows"].mean()),
            "mean_runtime_ms": float(df_greedy["runtime_ms"].mean()),
            "total_conflicts": int(df_greedy["conflicts"].sum()),
            "all_feasible": bool(df_greedy["feasibility"].all()),
        },
        "cpsat_aggregate": {
            "mean_objective": float(df_cpsat["objective"].mean()),
            "mean_reassignments": float(df_cpsat["reassignments"].mean()),
            "mean_overflows": float(df_cpsat["overflows"].mean()),
            "mean_runtime_ms": float(df_cpsat["runtime_ms"].mean()),
            "total_conflicts": int(df_cpsat["conflicts"].sum()),
            "all_feasible": bool(df_cpsat["feasibility"].all()),
        },
        "cpsat_plus_sa_aggregate": {
            "mean_objective": float(df_sa["objective"].mean()),
            "mean_reassignments": float(df_sa["reassignments"].mean()),
            "mean_overflows": float(df_sa["overflows"].mean()),
            "mean_runtime_ms": float(df_sa["runtime_ms"].mean()),
            "total_conflicts": int(df_sa["conflicts"].sum()),
            "all_feasible": bool(df_sa["feasibility"].all()),
        },
        "relative_performance": {
            "cpsat_vs_greedy_improvement_pct": float(
                ((df_greedy["objective"].mean() - df_cpsat["objective"].mean()) / df_greedy["objective"].mean()) * 100.0
            ),
            "sa_vs_cpsat_improvement_pct": float(
                ((df_cpsat["objective"].mean() - df_sa["objective"].mean()) / df_cpsat["objective"].mean()) * 100.0
            ),
        },
        "mc_convergence_stability": convergence_records,
    }

    with open(artifacts_dir / "aggregate_metrics.json", "w", encoding="utf-8") as f:
        json.dump(aggregate_metrics, f, indent=2)

    total_wall_sec = time.time() - start_wall_time

    run_manifest = {
        "manifest_version": "phase_g_e2e_pipeline_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "PHASE_G",
        "status": "PASS",
        "protocol_reference": "docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md",
        "total_wall_seconds": total_wall_sec,
        "models": {
            "marginal": "B5_ngboost_student_t",
            "dependence": "DEP_D2_gaussian_copula",
            "turn_model": "AircraftTurnModel",
            "conflict_detector": "ConflictDetector",
            "solvers_compared": ["Greedy", "CP-SAT", "CP-SAT+SA"],
        },
        "artifacts_generated": [
            "run_manifest.json",
            "scenario_summary.parquet",
            "greedy_results.parquet",
            "cp_sat_results.parquet",
            "sa_results.parquet",
            "aggregate_metrics.json",
        ],
        "aggregate_summary": aggregate_metrics["relative_performance"],
        "all_hard_feasibility_satisfied": bool(
            df_greedy["feasibility"].all() and df_cpsat["feasibility"].all() and df_sa["feasibility"].all()
        ),
        "zero_contact_conflicts_across_all_solvers": bool(
            df_greedy["conflicts"].sum() == 0 and df_cpsat["conflicts"].sum() == 0 and df_sa["conflicts"].sum() == 0
        ),
    }

    with open(artifacts_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2)

    LOGGER.info(f"\n[PASS] Phase G Pipeline execution completed in {total_wall_sec:.2f} seconds.")
    LOGGER.info(f"Artifacts exported to: {artifacts_dir}")
    return run_manifest


if __name__ == "__main__":
    run_phase_g_pipeline()
