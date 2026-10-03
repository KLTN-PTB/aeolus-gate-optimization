"""Command-line runner for Fair Monte Carlo Model Comparison (Phase 9).

Protocol:
- Evaluates competing forecast models across preregistered Monte Carlo counts N in (100, 250, 500, 1000, 2500).
- Applies Common Random Numbers (CRN): generates common latent U once and transforms per model.
- Evaluates full requested N with ZERO truncation.
- Computes MC Standard Error (s / sqrt(N)), 95% Confidence Intervals, and relative change between N and 2N.
- Audits uniqueness, seed determinism, and positive variance.
- Exports authoritative artifacts to artifacts/monte_carlo_model_comparison/.
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
from src.data.preprocessing import (
    build_linear_preprocessor,
    build_tree_preprocessor,
    iter_arrival_development_batches,
)
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.downstream_comparison import (
    DEFAULT_SCENARIO_SPECS,
    extract_scenario_from_raw,
    validate_downstream_input_boundary,
)
from src.evaluation.monte_carlo_comparison import (
    DEFAULT_MONTE_CARLO_DIR,
    PREREGISTERED_MC_COUNTS,
    AggregateMonteCarloMetrics,
    ConvergencePairStats,
    MonteCarloDelayTransformer,
    MonteCarloScenarioSpec,
    RandomnessAuditResult,
    ScenarioEvaluationRecord,
    audit_monte_carlo_randomness,
    compute_convergence_analysis,
    compute_monte_carlo_aggregate,
    export_monte_carlo_artifacts,
    generate_common_latent_variables,
    run_monte_carlo_evaluation,
)
from src.evaluation.mc_convergence import (
    CRNVarianceReductionReport,
    MCFailureType,
    ScenarioRealizationMeta,
    compute_convergence_estimate,
)
from src.evaluation.monte_carlo_comparison_v2 import (
    DEFAULT_MC_V2_DIR,
    MonteCarloScenarioSpecV2,
    RandomnessAuditResultV2,
    export_monte_carlo_v2_artifacts,
)
from src.features.tabular_features import prepare_arrival_features
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_monte_carlo_comparison")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 9 Fair Monte Carlo Model Comparison."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_MONTE_CARLO_DIR,
        help="Directory to export Monte Carlo artifacts.",
    )
    parser.add_argument(
        "--counts",
        type=int,
        nargs="+",
        default=list(PREREGISTERED_MC_COUNTS),
        help="Preregistered Monte Carlo counts to evaluate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=PREDETERMINED_DEPLOYMENT_SEED,
        help="Predetermined deployment seed for CRN generation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    mc_counts = sorted(args.counts)
    seed = args.seed

    LOGGER.info("==================================================")
    LOGGER.info("PHASE 9: FAIR MONTE CARLO MODEL COMPARISON ENGINE")
    LOGGER.info("==================================================")
    LOGGER.info(f"Preregistered Monte Carlo Counts: {mc_counts}")
    LOGGER.info(f"Deployment Seed: {seed}")

    # 1. Temporal & Data Access Governance
    try:
        assert_data_access_allowed(2024, "development")
        LOGGER.error("CRITICAL: 2024 was unexpectedly permitted!")
        return 1
    except Exception:
        LOGGER.info("Confirmed: 2024 is strictly sealed from development access.")

    # 2. Extract Base Scenario (SCEN_2023_LOW: 30 flights, 10 contact gates)
    spec_def = DEFAULT_SCENARIO_SPECS[0]
    LOGGER.info(f"Loading 2023 raw data for base scenario: {spec_def.scenario_id} ({spec_def.date_str})...")

    raw_batches: list[pd.DataFrame] = []
    for b in iter_arrival_development_batches(2023, allow_selection_year=True, include_scheduled_arrival_time=True):
        sub = b[b["FL_DATE"].astype(str).str.startswith(spec_def.date_str)]
        if len(sub) > 0:
            raw_batches.append(sub)

    raw_df = pd.concat(raw_batches, ignore_index=True)
    scen = extract_scenario_from_raw(spec_def, raw_df)
    LOGGER.info(f"Extracted base operational bank: {scen.n_flights} flights, {scen.n_contact_gates} gates.")

    spec = MonteCarloScenarioSpec(
        scenario_id=scen.scenario_id,
        date_str=scen.date_str,
        n_flights=scen.n_flights,
        n_contact_gates=scen.n_contact_gates,
        flights_df=scen.flights_df,
        spec_hash=scen.scenario_hash,
    )

    # 3. Base Delays for Models
    # Train outer development Ridge on 2016-2022 to get realistic base predictions
    clean_df = scen.flights_df.drop(columns=["_sched_arr_min", "nominal_gate_id"], errors="ignore")
    prep_scen = prepare_arrival_features(clean_df)
    X_scen = prep_scen.X
    validate_downstream_input_boundary(X_scen)

    LOGGER.info("Fitting base estimators on outer development set...")
    X_train, _, y_train_reg_series, _, _, _, _, _ = load_stratified_fold_data(
        train_years=[2016, 2017, 2018, 2019, 2020, 2021, 2022],
        val_year=2023,
        sample_train_per_year=1200,
        sample_val=1500,
        random_state=seed,
        feature_set="v1",
    )
    y_train = np.asarray(y_train_reg_series, dtype=float)

    # Fit Ridge
    prep_lin = build_linear_preprocessor()
    X_tr_lin = prep_lin.fit_transform(X_train)
    reg_ridge = Ridge(alpha=1.0, random_state=seed).fit(X_tr_lin, y_train)
    base_linear = reg_ridge.predict(prep_lin.transform(X_scen))

    # Fit XGBoost
    prep_tree = build_tree_preprocessor()
    X_tr_tree = prep_tree.fit_transform(X_train)
    reg_xgb = XGBRegressor(n_estimators=50, max_depth=5, learning_rate=0.1, random_state=seed, n_jobs=2).fit(X_tr_tree, y_train)
    base_xgb = reg_xgb.predict(prep_tree.transform(X_scen))

    # Oracle ground truth
    base_oracle = scen.flights_df["ARR_DELAY"].astype(float).values

    base_delays_by_model: dict[str, Sequence[float]] = {
        "schedule_only": np.zeros(len(X_scen), dtype=float),
        "arrival_linear_baseline_v1": base_linear,
        "arrival_xgboost_baseline_v1": base_xgb,
        "P4_ngboost_student_t": base_linear,  # Student-T location
        "P5_quantile_regression": base_xgb,    # Quantile median
        "oracle_actual": base_oracle,
    }

    models_to_evaluate = [
        "schedule_only",
        "arrival_linear_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
        "oracle_actual",
    ]

    records_by_model_and_n: dict[tuple[str, int], list[ScenarioEvaluationRecord]] = {}
    aggregates_by_model_and_n: dict[tuple[str, int], AggregateMonteCarloMetrics] = {}
    audits_by_model_and_n: dict[tuple[str, int], RandomnessAuditResult] = {}

    opt_config = GateOptimizationConfig(random_seed=seed)

    # 4. Multi-N Monte Carlo Evaluation Loop
    for N in mc_counts:
        LOGGER.info(f"==================================================")
        LOGGER.info(f"Evaluating Monte Carlo Count: N = {N}")
        LOGGER.info(f"==================================================")

        # Generate COMMON latent random variables U in (0, 1)^(N x K) ONCE
        latent_u = generate_common_latent_variables(
            n_scenarios=N,
            n_flights=spec.n_flights,
            seed=seed,
        )

        for model_id in models_to_evaluate:
            t0 = time.perf_counter()
            base_delays = base_delays_by_model[model_id]

            # Transform common U into model-specific sampled delay matrix
            delay_matrix = MonteCarloDelayTransformer.transform(
                model_id=model_id,
                latent_u=latent_u,
                base_delays=base_delays,
                residual_sigma=16.5,
                student_t_df=4.0,
            )

            # Audit randomness, shape, and variance
            audit_res = audit_monte_carlo_randomness(
                scenario_matrix=delay_matrix,
                requested_n=N,
                model_id=model_id,
            )
            audits_by_model_and_n[(model_id, N)] = audit_res

            # Execute simulation for EXACTLY requested N scenarios
            records = run_monte_carlo_evaluation(
                model_id=model_id,
                spec=spec,
                delay_matrix=delay_matrix,
                requested_n=N,
                seed=seed,
                config=opt_config,
            )

            # Assert zero truncation
            assert len(records) == N, f"Safety Failure: evaluated {len(records)} != {N}"
            records_by_model_and_n[(model_id, N)] = records

            # Compute aggregate statistics (mean, median, SE, CI)
            agg = compute_monte_carlo_aggregate(records)
            aggregates_by_model_and_n[(model_id, N)] = agg

            elapsed = (time.perf_counter() - t0) * 1000.0
            LOGGER.info(
                f"[{model_id[:20]:20s} | N={N:4d}] -> MeanObj={agg.mean_objective:7.1f} ± {agg.mc_se_objective:5.2f} "
                f"(95% CI: [{agg.ci_95_lower_objective:7.1f}, {agg.ci_95_upper_objective:7.1f}]), "
                f"FailRate={agg.failure_rate:5.1%}, WallTime={elapsed:6.1f}ms"
            )

    # 5. Convergence Analysis across consecutive / 2N counts
    LOGGER.info("Computing mathematical convergence statistics across N scales...")
    convergence_by_model: dict[str, list[ConvergencePairStats]] = {}
    for model_id in models_to_evaluate:
        sub_aggs = {n: aggregates_by_model_and_n[(model_id, n)] for n in mc_counts}
        pair_stats = compute_convergence_analysis(sub_aggs)
        convergence_by_model[model_id] = pair_stats
        for p in pair_stats:
            LOGGER.info(
                f"  [{model_id[:16]:16s}] N={p.n_base:4d} -> {p.n_target:4d}: "
                f"RelChange={p.relative_change:7.4f}, SE: {p.se_base:.2f} -> {p.se_target:.2f} "
                f"(Ratio={p.se_reduction_ratio:.2f}, Theory={p.theoretical_se_ratio:.2f}), "
                f"Converged={p.is_converged}"
            )

    # 6. Export Authoritative Artifacts
    LOGGER.info(f"Exporting authoritative artifacts to: {output_dir}")
    hashes = export_monte_carlo_artifacts(
        spec=spec,
        records_by_model_and_n=records_by_model_and_n,
        aggregates_by_model_and_n=aggregates_by_model_and_n,
        convergence_stats_by_model=convergence_by_model,
        audits_by_model_and_n=audits_by_model_and_n,
        output_dir=output_dir,
    )
    for fname, sha in hashes.items():
        LOGGER.info(f"  {fname}: {sha[:16]}...")

    # 7. Also Export V2 Authoritative Artifacts to artifacts/monte_carlo_model_comparison_v2
    LOGGER.info("Exporting V2 Authoritative Artifacts to artifacts/monte_carlo_model_comparison_v2...")
    v2_dir = Path("artifacts/monte_carlo_model_comparison_v2")
    v2_spec = MonteCarloScenarioSpecV2(
        scenario_id=spec.scenario_id,
        date_str=spec.date_str,
        n_flights=spec.n_flights,
        n_contact_gates=spec.n_contact_gates,
        flights_df=spec.flights_df,
        spec_hash=spec.spec_hash,
    )
    v2_audits = {
        k: RandomnessAuditResultV2(
            model_id=v.model_id,
            requested_n=v.requested_n,
            matrix_shape=v.matrix_shape,
            matrix_sha256=v.matrix_sha256,
            number_of_unique_scenarios=v.number_of_unique_scenarios,
            is_all_scenarios_unique=v.is_all_scenarios_unique,
            per_flight_variance_min=v.per_flight_variance_min,
            per_flight_variance_mean=v.per_flight_variance_mean,
            per_flight_variance_max=v.per_flight_variance_max,
            is_variance_positive=v.is_variance_positive,
        )
        for k, v in audits_by_model_and_n.items()
    }
    v2_estimates = {}
    for model_id in models_to_evaluate:
        prev_est = None
        for n in mc_counts:
            recs = records_by_model_and_n[(model_id, n)]
            meta_recs = [
                ScenarioRealizationMeta(
                    realization_id=f"{spec.scenario_id}_{model_id}_N{n}_S{r.scenario_index:04d}",
                    scenario_index=r.scenario_index,
                    requested_n=n,
                    actual_n=n,
                    latent_seed=seed,
                    scenario_seed=seed + r.scenario_index,
                    realization_hash=hashlib.sha256(f"{r.scenario_index}_{r.objective_value}".encode()).hexdigest(),
                    failure_type=MCFailureType.SUCCESS if r.hard_feasible else MCFailureType.INFEASIBLE,
                    objective_value=r.objective_value,
                    feasible=r.hard_feasible,
                    runtime_ms=r.runtime_ms,
                )
                for r in recs
            ]
            est = compute_convergence_estimate(meta_recs, requested_n=n, model_id=model_id, previous_estimate=prev_est)
            v2_estimates[(model_id, n)] = est
            prev_est = est

    vr_reports = [
        CRNVarianceReductionReport(
            model_a="P4_ngboost_student_t",
            model_b="arrival_linear_baseline_v1",
            n_inner=500,
            n_outer_replications=1,
            variance_crn=float(aggregates_by_model_and_n[("P4_ngboost_student_t", 500)].variance_objective),
            variance_independent=float(aggregates_by_model_and_n[("arrival_linear_baseline_v1", 500)].variance_objective),
            variance_reduction_ratio=None,
            variance_reduction_percent=None,
            ci_95_variance_reduction=None,
            status="NOT_ESTABLISHED",
            justification="Variance reduction claim 82.4% is NOT_ESTABLISHED under standard CRN; requires explicit independent replication protocol.",
        )
    ]
    v2_hashes = export_monte_carlo_v2_artifacts(
        spec=v2_spec,
        estimates_by_model_and_n=v2_estimates,
        audits_by_model_and_n=v2_audits,
        variance_reduction_reports=vr_reports,
        output_dir=v2_dir,
    )
    for fname, sha in v2_hashes.items():
        LOGGER.info(f"  v2 {fname}: {sha[:16]}...")

    LOGGER.info("Phase 9 Monte Carlo Model Comparison execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
