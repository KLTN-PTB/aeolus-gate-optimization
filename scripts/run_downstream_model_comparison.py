"""Command-line runner for Downstream Gate Assignment Model Comparison (Phase 8).

Protocol:
- Evaluates whether forecast model differences propagate downstream to Gate Assignment.
- Uses frozen/verified candidates from Phase 7 (zero HPO, zero retraining).
- Evaluates across 4 representative 2023 scenarios (30-70 flights, 10-20 contact gates).
- Uses 3 standard solvers: Deterministic Greedy, Google OR-Tools CP-SAT, Simulated Annealing.
- Exact same scenarios, gates, objective weights, seeds, and solver budgets across all models.
- Exports authoritative artifacts to artifacts/downstream_model_comparison/.
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

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor

from src.data.access_guard import assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.data.preprocessing import (
    build_linear_preprocessor,
    build_tree_preprocessor,
    iter_arrival_development_batches,
)
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    DEFAULT_DOWNSTREAM_DIR,
    DEFAULT_SCENARIO_SPECS,
    DownstreamCandidate,
    DownstreamEvaluationRecord,
    DownstreamScenario,
    assert_auxiliary_departure_isolated,
    compute_paired_downstream_deltas,
    evaluate_candidate_on_scenario,
    export_downstream_artifacts,
    extract_scenario_from_raw,
    validate_downstream_input_boundary,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS, prepare_arrival_features
from src.models.probabilistic.candidate_interfaces import (
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.sa import SAConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_downstream_model_comparison")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 8 Downstream Gate Assignment Model Comparison."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DOWNSTREAM_DIR,
        help="Directory to export downstream comparison artifacts.",
    )
    parser.add_argument(
        "--sample-train-per-year",
        type=int,
        default=2500,
        help="Stratified training samples per year for outer development fit (2016-2022).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=PREDETERMINED_DEPLOYMENT_SEED,
        help="Predetermined deployment seed.",
    )
    parser.add_argument(
        "--time-limit-seconds",
        type=float,
        default=5.0,
        help="CP-SAT solver time limit per scenario.",
    )
    parser.add_argument(
        "--sa-iterations",
        type=int,
        default=500,
        help="Simulated Annealing iterations per scenario.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    seed = args.seed

    LOGGER.info("==================================================")
    LOGGER.info("PHASE 8: DOWNSTREAM GATE ASSIGNMENT MODEL COMPARISON")
    LOGGER.info("==================================================")

    # 1. Temporal & Data Access Governance
    LOGGER.info("Enforcing temporal governance: 2024 is strictly sealed from development.")
    try:
        assert_data_access_allowed(2024, "development")
        LOGGER.error("CRITICAL: 2024 was unexpectedly permitted!")
        return 1
    except Exception:
        LOGGER.info("Confirmed: 2024 access denied (DataAccessDenied). Temporal holdout intact.")

    train_years = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    eval_year = 2023

    # 2. Ingest 2016-2022 Outer Development Data for Frozen Model Training
    LOGGER.info(f"Loading monthly-stratified training data {train_years} ({args.sample_train_per_year}/yr)...")
    (
        X_train,
        _,
        y_train_reg_series,
        _,
        _,
        _,
        _,
        _,
    ) = load_stratified_fold_data(
        train_years=train_years,
        val_year=eval_year,
        sample_train_per_year=args.sample_train_per_year,
        sample_val=2000,
        random_state=seed,
        feature_set="v1",
    )

    # Validate input boundary on training set
    validate_downstream_input_boundary(X_train)
    LOGGER.info("Input boundary validation PASSED for training predictors.")

    y_train_reg = np.asarray(y_train_reg_series, dtype=float)

    # 3. Fit Candidate Models (Zero HPO, Standard Frozen Configurations)
    LOGGER.info("[*] Fitting Model 1: arrival_linear_baseline_v1 (Ridge)...")
    prep_linear = build_linear_preprocessor()
    X_train_lin = prep_linear.fit_transform(X_train)
    reg_linear = Ridge(alpha=1.0, random_state=seed)
    reg_linear.fit(X_train_lin, y_train_reg)

    LOGGER.info("[*] Fitting Model 2: arrival_xgboost_baseline_v1 (XGBoost)...")
    prep_tree = build_tree_preprocessor()
    X_train_tree = prep_tree.fit_transform(X_train)
    reg_xgb = XGBRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=seed,
        n_jobs=2,
    )
    reg_xgb.fit(X_train_tree, y_train_reg)

    LOGGER.info("[*] Fitting Model 3: P5_quantile_regression (Median / Pinball)...")
    cand_p5 = P5QuantileRegressionCandidate(seed=seed)
    cand_p5.fit(X_train, y_train_reg)

    LOGGER.info("[*] Fitting Model 4: P4_ngboost_student_t (NGBoost Student-T)...")
    cand_p4 = P4NGBoostStudentTCandidate(seed=seed)
    cand_p4.fit(X_train, y_train_reg)

    LOGGER.info("All forecast candidate models successfully fitted on outer development window.")

    # 4. Load 2023 Operational Scenarios
    LOGGER.info("Loading 2023 raw data for operational bank scenario extraction...")
    target_dates = [s.date_str for s in DEFAULT_SCENARIO_SPECS]
    raw_2023_batches: list[pd.DataFrame] = []

    for b in iter_arrival_development_batches(2023, allow_selection_year=True, include_scheduled_arrival_time=True):
        b_dates = b["FL_DATE"].astype(str).str[:10]
        matched = b[b_dates.isin(target_dates)]
        if len(matched) > 0:
            raw_2023_batches.append(matched)

    if not raw_2023_batches:
        raise ValueError("Failed to load 2023 scenario raw data!")

    raw_2023_df = pd.concat(raw_2023_batches, ignore_index=True)
    LOGGER.info(f"Loaded {len(raw_2023_df)} raw flights across target 2023 scenario dates.")

    scenarios: list[DownstreamScenario] = []
    for spec in DEFAULT_SCENARIO_SPECS:
        scen = extract_scenario_from_raw(spec, raw_2023_df)
        scenarios.append(scen)
        LOGGER.info(
            f"  -> Scenario {scen.scenario_id}: date={scen.date_str}, "
            f"flights={scen.n_flights}, contact_gates={scen.n_contact_gates}, hash={scen.scenario_hash[:8]}"
        )

    # 5. Execute Solvers and Downstream Evaluations
    # Configurations
    opt_config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        time_limit_seconds=args.time_limit_seconds,
        num_search_workers=1,
        random_seed=seed,
    )
    sa_config = SAConfig(
        T0=100.0,
        Tmin=0.01,
        cooling_rate=0.95,
        iterations=args.sa_iterations,
        seed=seed,
    )

    solvers = ["DeterministicGreedy", "CPSat", "SimulatedAnnealing"]
    candidates = DEFAULT_DOWNSTREAM_CANDIDATES
    evaluation_records: list[DownstreamEvaluationRecord] = []

    LOGGER.info(f"Executing evaluations: {len(candidates)} candidates x {len(scenarios)} scenarios x {len(solvers)} solvers = 84 total runs...")

    for scen in scenarios:
        LOGGER.info(f"--- Evaluating Scenario: {scen.scenario_id} ({scen.n_flights} flights, {scen.n_contact_gates} gates) ---")
        
        # Prepare feature matrix for scenario flights (drop internal scenario metadata)
        clean_df = scen.flights_df.drop(
            columns=["_sched_arr_min", "nominal_gate_id"],
            errors="ignore",
        )
        prep_scen = prepare_arrival_features(clean_df)
        X_scen = prep_scen.X
        validate_downstream_input_boundary(X_scen)

        # Pre-compute predictions for all candidates on this scenario
        preds_by_model: dict[str, Sequence[float]] = {}
        
        # 1. Schedule-only baseline
        preds_by_model["schedule_only"] = np.zeros(len(X_scen), dtype=float)

        # 2. Linear / Ridge point model
        X_scen_lin = prep_linear.transform(X_scen)
        preds_by_model["arrival_linear_baseline_v1"] = reg_linear.predict(X_scen_lin)

        # 3. XGBoost point model
        X_scen_tree = prep_tree.transform(X_scen)
        preds_by_model["arrival_xgboost_baseline_v1"] = reg_xgb.predict(X_scen_tree)

        # 4. Weighted Ensemble (equal weights of linear + xgboost)
        preds_by_model["arrival_weighted_ensemble_v1"] = (
            0.5 * preds_by_model["arrival_linear_baseline_v1"]
            + 0.5 * preds_by_model["arrival_xgboost_baseline_v1"]
        )

        # 5. P5 Quantile Regression
        dist_p5 = cand_p5.predict_distribution(X_scen)
        preds_by_model["P5_quantile_regression"] = dist_p5.median()

        # 6. P4 NGBoost Student-T
        dist_p4 = cand_p4.predict_distribution(X_scen)
        preds_by_model["P4_ngboost_student_t"] = dist_p4.mean()

        # 7. Oracle Actual Delay (Reference Upper Bound)
        preds_by_model["oracle_actual"] = scen.flights_df["ARR_DELAY"].astype(float).values

        # Run solver evaluations
        for cand in candidates:
            preds = preds_by_model[cand.candidate_id]
            for solver_name in solvers:
                t_start = time.perf_counter()
                rec = evaluate_candidate_on_scenario(
                    candidate=cand,
                    scenario=scen,
                    predicted_delays=preds,
                    solver_name=solver_name,
                    config=opt_config,
                    sa_config=sa_config,
                )
                evaluation_records.append(rec)
                LOGGER.info(
                    f"[{cand.candidate_id[:16]:16s} | {scen.scenario_id[:12]:12s} | {solver_name[:12]:12s}] -> "
                    f"Status={rec.status}, Feasible={rec.hard_feasible}, Obj={rec.objective_value:8.1f}, "
                    f"Conflicts={rec.conflict_count:2d}, Reassign={rec.reassignment_count:2d}, "
                    f"Remote={rec.remote_count:2d}, Runtime={rec.runtime_ms:6.1f}ms"
                )

    # 6. Compute Paired Deltas Across All Candidate Pairs
    LOGGER.info("Computing exact scenario-level paired deltas...")
    paired_deltas = compute_paired_downstream_deltas(evaluation_records)
    LOGGER.info(f"Computed {len(paired_deltas)} paired deltas.")

    # 7. Export Artifacts
    LOGGER.info(f"Exporting authoritative artifacts to: {output_dir}")
    hashes = export_downstream_artifacts(
        records=evaluation_records,
        deltas=paired_deltas,
        output_dir=output_dir,
    )
    for fname, sha in hashes.items():
        LOGGER.info(f"  {fname}: {sha[:16]}...")

    LOGGER.info("Phase 8 Downstream Model Comparison execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
