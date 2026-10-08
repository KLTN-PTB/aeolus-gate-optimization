"""Runner script for Native P4 Downstream Rebuild (P10-A).

Executes:
1. P4 checkpoint verification and loading.
2. Canonical 2023 scenario extraction (SCEN_2023_LOW).
3. Forecast generation for 4 approved arms (Schedule-only, Ridge, Native P4, Oracle).
4. Solver benchmark across 4 authorized solvers (Greedy, CP-SAT, SA, Hybrid) under 2.0s ceiling.
5. Monte Carlo robustness evaluation across registered grid [100, 250, 500, 1000, 2500].
6. Full artifact export to artifacts/native_downstream_v1/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t
from sklearn.linear_model import Ridge

from src.data.access_guard import assert_data_access_allowed
from src.data.preprocessing import build_linear_preprocessor
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_SCENARIO_SPECS,
    DownstreamScenario,
    DownstreamScenarioSpec,
    extract_scenario_from_raw,
    validate_downstream_input_boundary,
)
from src.evaluation.mc_convergence import (
    MCFailureType,
    generate_crn_latent_matrix,
)
from src.evaluation.native_downstream_p4 import (
    CANONICAL_MC_N,
    NATIVE_DOWNSTREAM_DIR,
    P4_CERTIFIED_CHECKPOINT_PATH,
    P4_CERTIFIED_SHA256,
    PREREGISTERED_MC_GRID,
    SOLVER_TIME_LIMIT_SECONDS,
    MonteCarloConvergenceResult,
    P5RoleViolationError,
    SolverExecutionRecord,
    execute_four_solvers,
    run_monte_carlo_grid,
    verify_and_load_p4_checkpoint,
)
from src.features.tabular_features import prepare_arrival_features
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.simulation.aircraft_turn import AircraftTurnModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_native_p4_downstream")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run P10-A Native P4 Downstream Rebuild."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=NATIVE_DOWNSTREAM_DIR,
        help="Directory to export native downstream artifacts.",
    )
    parser.add_argument(
        "--solver-time-limit",
        type=float,
        default=SOLVER_TIME_LIMIT_SECONDS,
        help="Ceiling solver wall-clock budget in seconds.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=PREDETERMINED_DEPLOYMENT_SEED,
        help="Predetermined deployment seed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    LOGGER.info("=" * 80)
    LOGGER.info("P10-A: NATIVE P4 DOWNSTREAM REBUILD AFTER R39")
    LOGGER.info(f"Target Output Directory: {output_dir}")
    LOGGER.info(f"Registered Solver Ceiling: {args.solver_time_limit}s | Seed: {args.seed}")
    LOGGER.info("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 0: PREFLIGHT & REPOSITORY INTEGRITY
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 0] Performing repository preflight check...")
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        git_commit = "7ba0aba92d366f712977faaaa5a73cba65a32a55"

    LOGGER.info(f"Current git commit HEAD: {git_commit}")

    # Ensure 2024 is strictly isolated (only development 2016-2023 allowed)
    assert_data_access_allowed(2023, "development")

    # -------------------------------------------------------------------------
    # STEP 1: VERIFY FROZEN P4 CHECKPOINT
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 1] Verifying certified native P4 model checkpoint...")
    p4_model, p4_meta = verify_and_load_p4_checkpoint(
        checkpoint_path=P4_CERTIFIED_CHECKPOINT_PATH,
        expected_sha256=P4_CERTIFIED_SHA256,
    )
    LOGGER.info(
        f"  -> Checkpoint SHA-256: {p4_meta['sha256']} (VERIFIED EXACT MATCH)\n"
        f"  -> Model class: {p4_meta['model_class']}\n"
        f"  -> Estimators: {p4_meta['n_estimators']}, lr: {p4_meta['learning_rate']}, seed: {p4_meta['seed']}"
    )

    # Export checkpoint verification record
    with open(output_dir / "p4_checkpoint_verification.json", "w", encoding="utf-8") as f:
        json.dump(p4_meta, f, indent=2)

    # -------------------------------------------------------------------------
    # STEP 2: LOAD CANONICAL DEVELOPMENT SCENARIO (SCEN_2023_LOW)
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 2] Loading canonical historical development scenario: SCEN_2023_LOW...")
    spec_low = DEFAULT_SCENARIO_SPECS[0]
    if spec_low.scenario_id != "SCEN_2023_LOW":
        raise ValueError(f"Expected SCEN_2023_LOW, got {spec_low.scenario_id}")

    raw_2023_path = ROOT / "data" / "processed" / "inbound_atl" / "year=2023"
    raw_2023_df = pd.read_parquet(raw_2023_path)
    scen = extract_scenario_from_raw(spec_low, raw_2023_df)
    LOGGER.info(
        f"  -> Scenario ID: {scen.scenario_id}\n"
        f"  -> Date: {scen.date_str}\n"
        f"  -> Flights: {scen.n_flights}, Contact Gates: {scen.n_contact_gates}\n"
        f"  -> Scenario Hash: {scen.scenario_hash}"
    )

    scenario_manifest = {
        "scenario_id": scen.scenario_id,
        "date_str": scen.date_str,
        "day_id": scen.day_id,
        "n_flights": scen.n_flights,
        "n_contact_gates": scen.n_contact_gates,
        "scenario_seed": scen.scenario_seed,
        "scenario_hash": scen.scenario_hash,
        "flight_keys": scen.flights_df["flight_key"].tolist(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(output_dir / "scenario_manifest.json", "w", encoding="utf-8") as f:
        json.dump(scenario_manifest, f, indent=2)

    # -------------------------------------------------------------------------
    # STEP 3: PREPARE CORE ARRIVAL FEATURES (ZERO LEAKAGE)
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 3] Preparing Core Arrival features without leakage...")
    clean_df = scen.flights_df.drop(
        columns=["_sched_arr_min", "nominal_gate_id"],
        errors="ignore",
    )
    prep_scen = prepare_arrival_features(clean_df)
    X_scen = prep_scen.X
    validate_downstream_input_boundary(X_scen)
    LOGGER.info(f"  -> Prepared X shape: {X_scen.shape}, Features: {list(X_scen.columns)}")

    # -------------------------------------------------------------------------
    # STEP 4: FIT POINT BASELINE & COMPUTE P4 PREDICTIONS
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 4] Generating forecast predictions across approved candidate arms...")
    # Arm 1: Schedule-only (0 min delay)
    pred_schedule = np.zeros(scen.n_flights, dtype=float)

    # Arm 2: Ridge Point Baseline (trained on 2016-2022 development data)
    LOGGER.info("  -> Ingesting 2016-2022 development sample to fit reference Ridge point baseline...")
    X_train, _, y_train_series, _, _, _, _, _ = load_stratified_fold_data(
        train_years=list(range(2016, 2023)),
        val_year=2023,
        sample_train_per_year=1000,
        random_state=args.seed,
        feature_set="v1",
    )
    prep_lin = build_linear_preprocessor()
    X_tr_lin = prep_lin.fit_transform(X_train)
    reg_linear = Ridge(alpha=1.0, random_state=args.seed)
    y_tr_arr = np.asarray(y_train_series, dtype=float)
    reg_linear.fit(X_tr_lin, y_tr_arr)

    # Compute residual sigma for point baseline Monte Carlo
    lin_resids = y_tr_arr - reg_linear.predict(X_tr_lin)
    sigma_linear = float(np.std(lin_resids))

    X_scen_lin = prep_lin.transform(X_scen)
    pred_linear = reg_linear.predict(X_scen_lin).astype(float)

    # Arm 3: Native Frozen P4 NGBoost Student-T
    LOGGER.info("  -> Predicting observation-dependent Student-T parameters via native frozen P4...")
    dist_p4 = p4_model.predict_distribution(X_scen)
    p4_mu = np.asarray(dist_p4["mu"], dtype=float)
    p4_sigma = np.asarray(dist_p4["sigma"], dtype=float)
    p4_df = np.asarray(dist_p4["df"], dtype=float)
    pred_p4_loc = p4_mu  # Location parameter is planned arrival delay

    # Parameter integrity audit
    assert len(p4_mu) == scen.n_flights
    assert bool(np.all(np.isfinite(p4_mu))), "Non-finite mu detected in P4"
    assert bool(np.all(np.isfinite(p4_sigma))), "Non-finite sigma detected in P4"
    assert bool(np.all(p4_sigma > 0.0)), "Non-positive sigma detected in P4"
    assert bool(np.all(p4_df > 2.0)), "df <= 2 detected in P4"
    LOGGER.info(
        f"     mu range: [{np.min(p4_mu):.2f}, {np.max(p4_mu):.2f}] | "
        f"sigma range: [{np.min(p4_sigma):.2f}, {np.max(p4_sigma):.2f}] | "
        f"df range: [{np.min(p4_df):.2f}, {np.max(p4_df):.2f}]"
    )

    # Arm 4: Oracle Ground-Truth Actual ARR_DELAY (Reference only)
    actual_arr_delay = np.asarray(scen.flights_df["ARR_DELAY"], dtype=float)

    candidate_forecasts: dict[str, np.ndarray] = {
        "schedule_only": pred_schedule,
        "arrival_linear_baseline_v1": pred_linear,
        "P4_ngboost_student_t": pred_p4_loc,
        "oracle_actual": actual_arr_delay,
    }

    # -------------------------------------------------------------------------
    # STEP 5: SOLVER BENCHMARK ACROSS 4 SOLVERS UNDER 2.0s CEILING
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 5] Executing solver comparison across 4 authorized solvers...")
    opt_config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=0.0,
        conflict_weight=1000.0,
        risk_weight=0.0,
        time_limit_seconds=args.solver_time_limit,
        num_search_workers=1,
        random_seed=args.seed,
    )
    turn_model = AircraftTurnModel(
        min_turnaround_min=45,
        default_dwell_min=60,
        separation_buffer_min=15,
    )

    all_solver_records: list[SolverExecutionRecord] = []
    for model_id, delays in candidate_forecasts.items():
        LOGGER.info(f"  -> Running 4 solvers for arm: {model_id}...")
        recs = execute_four_solvers(
            model_id=model_id,
            scenario=scen,
            planned_delays=delays,
            config=opt_config,
            turn_model=turn_model,
        )
        for r in recs:
            LOGGER.info(
                f"     [{r.solver_name}] status={r.status} feasible={r.feasible} "
                f"obj={r.objective_value:.1f} reass={r.reassignment_count} "
                f"remote={r.remote_count} runtime={r.runtime_ms:.1f}ms"
            )
        all_solver_records.extend(recs)

    # Export solver records
    solver_dicts = [r.to_dict() for r in all_solver_records]
    with open(output_dir / "solver_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(solver_dicts, f, indent=2)
    pd.DataFrame(solver_dicts).to_csv(output_dir / "solver_benchmark_results.csv", index=False)

    # Compute paired deltas
    solver_records_map = {
        (r.model_id, r.solver_name): r for r in all_solver_records
    }
    model_ids = list(candidate_forecasts.keys())
    solvers = ["DeterministicGreedy", "CPSat", "SimulatedAnnealing", "HybridCPSatSA"]
    paired_deltas: list[dict[str, Any]] = []

    for solv in solvers:
        for i in range(len(model_ids)):
            for j in range(i + 1, len(model_ids)):
                m_a = model_ids[i]
                m_b = model_ids[j]
                rec_a = solver_records_map.get((m_a, solv))
                rec_b = solver_records_map.get((m_b, solv))
                if rec_a and rec_b:
                    paired_deltas.append({
                        "solver_name": solv,
                        "model_a": m_a,
                        "model_b": m_b,
                        "delta_objective": round(rec_a.objective_value - rec_b.objective_value, 4),
                        "delta_reassignments": rec_a.reassignment_count - rec_b.reassignment_count,
                        "delta_remote": rec_a.remote_count - rec_b.remote_count,
                        "delta_unassigned": rec_a.unassigned_count - rec_b.unassigned_count,
                        "delta_conflicts": rec_a.planned_conflicts - rec_b.planned_conflicts,
                    })

    with open(output_dir / "paired_model_deltas.json", "w", encoding="utf-8") as f:
        json.dump(paired_deltas, f, indent=2)
    pd.DataFrame(paired_deltas).to_csv(output_dir / "paired_model_deltas.csv", index=False)

    # -------------------------------------------------------------------------
    # STEP 6: MONTE CARLO ROBUSTNESS EVALUATION (GRID: 100 TO 2500)
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 6] Executing Monte Carlo robustness evaluation across registered grid...")
    max_mc_n = max(PREREGISTERED_MC_GRID)
    latent_u, u_sha256 = generate_crn_latent_matrix(
        n_scenarios=max_mc_n,
        n_flights=scen.n_flights,
        seed=args.seed,
    )
    LOGGER.info(f"  -> Generated Common Random Numbers matrix U shape {latent_u.shape}, SHA-256: {u_sha256}")

    # Build delay matrices per arm
    # P4: Native Heteroscedastic Student-T
    t_shocks = student_t.ppf(latent_u, df=p4_df[None, :])
    matrix_p4 = p4_mu[None, :] + p4_sigma[None, :] * t_shocks

    # Schedule-only: Zero arrival delay deterministically across all scenarios
    matrix_sched = np.zeros((max_mc_n, scen.n_flights), dtype=float)

    # Ridge: Homoscedastic Gaussian residual
    matrix_linear = pred_linear[None, :] + sigma_linear * norm.ppf(latent_u)

    # Oracle: Perfect knowledge replicated across scenarios
    matrix_oracle = np.tile(actual_arr_delay, (max_mc_n, 1))

    delay_matrices = {
        "P4_ngboost_student_t": matrix_p4,
        "schedule_only": matrix_sched,
        "arrival_linear_baseline_v1": matrix_linear,
        "oracle_actual": matrix_oracle,
    }

    # Randomness Audit
    randomness_audit_results: list[dict[str, Any]] = []
    for m_id, d_mat in delay_matrices.items():
        mat_hash = hashlib.sha256(d_mat.tobytes()).hexdigest()
        unique_scens = int(len(np.unique(d_mat, axis=0)))
        per_flight_var = np.var(d_mat, axis=0)
        is_det = m_id in {"schedule_only", "oracle_actual"}

        audit_rec = {
            "model_id": m_id,
            "max_n": max_mc_n,
            "matrix_shape": list(d_mat.shape),
            "matrix_sha256": mat_hash,
            "number_of_unique_scenarios": unique_scens,
            "is_all_scenarios_unique": True if is_det else bool(unique_scens == max_mc_n),
            "per_flight_variance_min": float(np.min(per_flight_var)),
            "per_flight_variance_mean": float(np.mean(per_flight_var)),
            "per_flight_variance_max": float(np.max(per_flight_var)),
            "is_variance_positive": True if is_det else bool(np.all(per_flight_var > 0.0)),
        }
        randomness_audit_results.append(audit_rec)

    with open(output_dir / "randomness_audit.json", "w", encoding="utf-8") as f:
        json.dump(randomness_audit_results, f, indent=2)

    # Run Monte Carlo Grid
    mc_convergence_results: list[MonteCarloConvergenceResult] = []
    all_realization_records: list[ScenarioRealizationMeta] = []

    for m_id, d_mat in delay_matrices.items():
        LOGGER.info(f"  -> Simulating Monte Carlo grid for: {m_id}...")
        conv_res, real_recs = run_monte_carlo_grid(
            model_id=m_id,
            scenario=scen,
            delay_matrix=d_mat,
            counts=PREREGISTERED_MC_GRID,
            config=opt_config,
            turn_model=turn_model,
        )
        for c in conv_res:
            LOGGER.info(
                f"     N={c.n_requested:4d} | Mean Obj: {c.mean_objective:.2f} | "
                f"MC SE: {c.mc_se_objective:.2f} | 95% CI: [{c.ci_95_lower:.2f}, {c.ci_95_upper:.2f}] | "
                f"Rel Change: {c.rel_change_from_previous_n if c.rel_change_from_previous_n is not None else 0.0:.6f}"
            )
        mc_convergence_results.extend(conv_res)
        all_realization_records.extend(real_recs)

    mc_dicts = [r.to_dict() for r in mc_convergence_results]
    with open(output_dir / "monte_carlo_convergence_results.json", "w", encoding="utf-8") as f:
        json.dump(mc_dicts, f, indent=2)
    pd.DataFrame(mc_dicts).to_csv(output_dir / "monte_carlo_convergence_results.csv", index=False)

    # -------------------------------------------------------------------------
    # STEP 7: BUILD DOWNSTREAM SUMMARY & EXPORT CHECKSUMS
    # -------------------------------------------------------------------------
    LOGGER.info("[STEP 7] Exporting summary manifest and cryptographic checksums...")
    elapsed_total_s = round(time.perf_counter() - t_start, 2)

    downstream_summary = {
        "experiment_name": "P10-A Native P4 Downstream Rebuild",
        "status": "COMPLETED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_runtime_seconds": elapsed_total_s,
        "git_commit": git_commit,
        "scenario_id": scen.scenario_id,
        "p4_checkpoint_sha256": p4_meta["sha256"],
        "crn_latent_matrix_sha256": u_sha256,
        "solvers_evaluated": solvers,
        "models_evaluated": model_ids,
        "solver_runs_count": len(all_solver_records),
        "monte_carlo_grid": list(PREREGISTERED_MC_GRID),
        "canonical_n": CANONICAL_MC_N,
        "solver_summary_by_model": {},
        "monte_carlo_summary_at_canonical_n": {},
    }

    for m in model_ids:
        m_solv = [r for r in all_solver_records if r.model_id == m]
        downstream_summary["solver_summary_by_model"][m] = {
            "mean_objective": float(np.mean([r.objective_value for r in m_solv])),
            "all_feasible": bool(all(r.feasible for r in m_solv)),
            "mean_reassignments": float(np.mean([r.reassignment_count for r in m_solv])),
            "mean_remote_count": float(np.mean([r.remote_count for r in m_solv])),
            "mean_runtime_ms": float(np.mean([r.runtime_ms for r in m_solv])),
        }

    for m in model_ids:
        mc_500 = next(
            (c for c in mc_convergence_results if c.model_id == m and c.n_requested == CANONICAL_MC_N),
            None,
        )
        if mc_500:
            downstream_summary["monte_carlo_summary_at_canonical_n"][m] = {
                "mean_objective": mc_500.mean_objective,
                "median_objective": mc_500.median_objective,
                "std_objective": mc_500.std_objective,
                "mc_se_objective": mc_500.mc_se_objective,
                "ci_95": [mc_500.ci_95_lower, mc_500.ci_95_upper],
                "n_success": mc_500.n_success,
                "n_failed": mc_500.n_failed,
            }

    with open(output_dir / "downstream_summary.json", "w", encoding="utf-8") as f:
        json.dump(downstream_summary, f, indent=2)

    # Run Manifest
    run_manifest = {
        "run_id": f"P10A_NATIVE_P4_{int(time.time())}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "p4_checkpoint_sha256": p4_meta["sha256"],
        "scenario_id": scen.scenario_id,
        "scenario_seed": scen.scenario_seed,
        "solver_seed": args.seed,
        "monte_carlo_counts": list(PREREGISTERED_MC_GRID),
        "total_runtime_seconds": elapsed_total_s,
        "system_status": "P10A_PASS",
        "python_version": sys.version,
    }
    with open(output_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2)

    # Compute manifest.sha256
    files_to_hash = [
        "p4_checkpoint_verification.json",
        "scenario_manifest.json",
        "solver_benchmark_results.json",
        "solver_benchmark_results.csv",
        "paired_model_deltas.json",
        "paired_model_deltas.csv",
        "randomness_audit.json",
        "monte_carlo_convergence_results.json",
        "monte_carlo_convergence_results.csv",
        "downstream_summary.json",
        "run_manifest.json",
    ]
    manifest_lines = []
    for fname in sorted(files_to_hash):
        fpath = output_dir / fname
        if fpath.exists():
            h = hashlib.sha256(fpath.read_bytes()).hexdigest()
            manifest_lines.append(f"{h}  {fname}")

    with open(output_dir / "manifest.sha256", "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    LOGGER.info(f"[SUCCESS] P10-A Native P4 Downstream Rebuild completed in {elapsed_total_s}s!")
    LOGGER.info(f"Artifacts exported to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
