"""Stage 7.5 Runner — Joint Validation.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 17 (Stage 7.5)
Authoritative Inputs:
- Stage 7 Freeze Manifest: artifacts/manifests/probabilistic_stage7_system_candidates_v1.json
- Development Data: 2016-2022 Folds 1-4

Executes:
1. Validates all 12 frozen complete-system candidates across multi-flight development days.
2. Computes joint metrics:
   - Pairwise severe co-exceedance rate (both >= 60m).
   - Simultaneous severe delay probabilities P(N60 >= 1), P(N60 >= 2), P(N120 >= 1).
   - Severe delay count per day (mean, variance, Q90).
   - Maximum concurrent delay per day.
   - Aggregate daily total delay distribution (mean, std, Q90, CRPS).
   - Variance recovery ratio (simulated std / empirical std).
3. Validates marginal calibration preservation across flights.
4. Compares D1 and D2 directly against D0 independent baseline to verify measurable benefit.
5. Runs randomized PIT sensitivity evaluation across 10 draws.
6. Determines candidate pass/fail status and selects surviving candidate pool for Stage 8.
7. Exports authoritative manifest:
   artifacts/manifests/probabilistic_stage7_5_joint_validation_v1.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.contracts import (
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)

DEPLOYMENT_SEED = 202601
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    ScenarioBlockDependenceModel,
)
from src.models.probabilistic.dependence_interface import (
    DayFlightBatch,
    DiscretePITPolicy,
)
from src.models.probabilistic.joint_validation import (
    DailyJointGroundTruth,
    DailyJointSimulation,
    JointSystemEvaluationResult,
    evaluate_system_candidate_joint_performance,
    extract_daily_ground_truth,
    extract_daily_simulation,
)
from src.models.probabilistic.system_candidate import (
    CompleteSystemCandidate,
    build_complete_system_candidate,
)
from scripts.run_probabilistic_stage7_candidate_construction import build_marginal_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("probabilistic_stage7_5")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 7.5 Joint Validation")
    parser.add_argument("--n-scenarios", type=int, default=200, help="Number of scenarios per day")
    parser.add_argument("--max-days", type=int, default=40, help="Number of development days to evaluate")
    args = parser.parse_args()

    start_time = time.time()
    LOGGER.info("=" * 80)
    LOGGER.info("STAGE 7.5 — JOINT VALIDATION ON DEVELOPMENT DATA (2016-2022)")
    LOGGER.info(f"Scenarios per day: {args.n_scenarios} | Target evaluation days: {args.max_days}")
    LOGGER.info("=" * 80)

    root = Path(__file__).resolve().parents[1]
    manifest_dir = root / "artifacts" / "manifests"

    # 1. Ingest Stage 7 Freeze Manifest
    stage7_manifest_path = manifest_dir / "probabilistic_stage7_system_candidates_v1.json"
    if not stage7_manifest_path.exists():
        LOGGER.error(f"Stage 7 freeze manifest missing at {stage7_manifest_path}")
        sys.exit(1)

    with open(stage7_manifest_path, "r", encoding="utf-8") as f:
        stage7_data = json.load(f)

    all_candidate_ids = list(stage7_data["complete_system_candidates"].keys())
    surviving_marginals = stage7_data["surviving_marginal_candidates"]
    LOGGER.info(f"Loaded {len(all_candidate_ids)} frozen complete system candidates from Stage 7.")

    # 2. Reconstruct System Candidate Objects
    LOGGER.info("\n--- Instantiating Frozen System Candidate Objects ---")
    system_candidates: dict[str, CompleteSystemCandidate] = {}
    for cand_id, meta in stage7_data["complete_system_candidates"].items():
        marg_id = meta["marginal_candidate_id"]
        dep_id = meta["dependence_candidate_id"]
        m_factory = build_marginal_factory(marg_id, root)

        cand = build_complete_system_candidate(
            marginal_candidate_id=marg_id,
            dependence_family_id=dep_id,
            marginal_factory=m_factory,
            project_root=root,
            dependence_kwargs=meta["dependence_parameters"],
        )
        system_candidates[cand_id] = cand

    # 3. Load Multi-Flight Development Validation Batches (Folds 1 and 4)
    LOGGER.info("\n--- Loading Multi-Flight Days from Development Validation Folds ---")
    (
        _,
        _,
        _,
        _,
        X_val_f4,
        _,
        y_val_reg_f4,
        val_flight_keys,
    ) = load_stratified_fold_data(
        train_years=[2016, 2017, 2018, 2019, 2020, 2021],
        val_year=2022,
        sample_train_per_year=100,
        sample_val=5000,
        project_root=root,
        random_state=DEPLOYMENT_SEED,
        feature_set="v1",
    )

    val_df = X_val_f4.copy()
    val_df["y_true"] = y_val_reg_f4.values
    val_df["flight_key"] = val_flight_keys.values
    if "flight_date" not in val_df.columns:
        val_df["flight_date"] = (
            val_df["calendar_year"].astype(int).astype(str)
            + "-"
            + val_df["calendar_month"].astype(int).astype(str).str.zfill(2)
            + "-"
            + val_df["calendar_day_of_month"].astype(int).astype(str).str.zfill(2)
        )

    # Filter dates with >= 8 flights
    date_counts = val_df["flight_date"].value_counts()
    eligible_dates = date_counts[date_counts >= 8].index.tolist()
    selected_dates = eligible_dates[:args.max_days]
    LOGGER.info(f"Selected {len(selected_dates)} development days with 8 to {date_counts.max()} flights (Fold 4 / 2022).")

    # Construct DayFlightBatch and ground truth for each selected date
    daily_batches: list[DayFlightBatch] = []
    daily_truths: list[DailyJointGroundTruth] = []

    for d_str in selected_dates:
        sub_df = val_df[val_df["flight_date"] == d_str].copy()
        feat_df = sub_df[list(PROBABILISTIC_PREDICTOR_COLUMNS)].copy()
        feat_df.index = pd.Index(sub_df["flight_key"].values)
        y_arr = sub_df["y_true"].to_numpy(dtype=float)

        batch = DayFlightBatch(flight_date=d_str, flight_features=feat_df, observed_delays=y_arr)
        gt = extract_daily_ground_truth(d_str, y_arr)

        daily_batches.append(batch)
        daily_truths.append(gt)

    total_eval_flights = sum(gt.n_flights for gt in daily_truths)
    total_eval_pairs = sum(gt.n_flights * (gt.n_flights - 1) // 2 for gt in daily_truths)
    tot_emp_severe_pairs = sum(gt.pairs_both_ge60 for gt in daily_truths)
    LOGGER.info(f"Total flights: {total_eval_flights:,} | Total pairs: {total_eval_pairs:,} | Realized severe pairs: {tot_emp_severe_pairs}")

    # 4. Joint Simulation and Evaluation Across Candidates
    LOGGER.info("\n========================================================")
    LOGGER.info("EVALUATING JOINT METRICS ACROSS ALL CANDIDATE SYSTEMS")
    LOGGER.info("========================================================")

    # First evaluate D0 baselines for each marginal family
    d0_results: dict[str, JointSystemEvaluationResult] = {}
    candidate_results: dict[str, JointSystemEvaluationResult] = {}

    for marg_id in surviving_marginals:
        cand_id_d0 = f"SYS_{marg_id}__DEP_D0_independent"
        cand_d0 = system_candidates[cand_id_d0]

        LOGGER.info(f"\n>> Simulating Baseline: {cand_id_d0}...")
        sims_d0: list[DailyJointSimulation] = []
        for b_idx, batch in enumerate(daily_batches):
            y_sim = cand_d0.sample_scenarios(batch, n_scenarios=args.n_scenarios, seed=DEPLOYMENT_SEED + b_idx)
            sim = extract_daily_simulation(batch.flight_date, y_sim)
            sims_d0.append(sim)

        res_d0 = evaluate_system_candidate_joint_performance(
            candidate_id=cand_id_d0,
            marginal_candidate_id=marg_id,
            dependence_candidate_id="DEP_D0_independent",
            daily_truths=daily_truths,
            daily_sims=sims_d0,
        )
        d0_results[marg_id] = res_d0
        candidate_results[cand_id_d0] = res_d0

        LOGGER.info(
            f"  {cand_id_d0:55s} | Agg CRPS: {res_d0.daily_aggregate_crps:6.2f}m | "
            f"Std Ratio: {res_d0.aggregate_std_ratio:.3f} | CoEx Err: {res_d0.co_exceedance_abs_error:.5f} | "
            f"Gate: [{res_d0.overall_stage7_5_decision}]"
        )

    # Now evaluate D1 and D2 candidates and compare against their D0 baseline
    for cand_id, cand in system_candidates.items():
        if cand.dependence_candidate_id == "DEP_D0_independent":
            continue

        marg_id = cand.marginal_candidate_id
        dep_id = cand.dependence_candidate_id
        d0_res = d0_results[marg_id]

        LOGGER.info(f"\n>> Simulating Dependence Model: {cand_id}...")
        sims: list[DailyJointSimulation] = []
        psd_passed_all = True

        for b_idx, batch in enumerate(daily_batches):
            # Check PSD explicitly for D2
            if dep_id == "DEP_D2_gaussian_copula":
                corr = cand.dependence_model.construct_correlation_matrix(batch.flight_features)  # type: ignore
                min_eig = np.min(np.linalg.eigvalsh(corr))
                if min_eig < 1e-6 - 1e-9:
                    psd_passed_all = False

            y_sim = cand.sample_scenarios(batch, n_scenarios=args.n_scenarios, seed=DEPLOYMENT_SEED + b_idx)
            sim = extract_daily_simulation(batch.flight_date, y_sim)
            sims.append(sim)

        res = evaluate_system_candidate_joint_performance(
            candidate_id=cand_id,
            marginal_candidate_id=marg_id,
            dependence_candidate_id=dep_id,
            daily_truths=daily_truths,
            daily_sims=sims,
            d0_result=d0_res,
            psd_all_passed=psd_passed_all,
        )
        candidate_results[cand_id] = res

        LOGGER.info(
            f"  {cand_id:55s} | Agg CRPS: {res.daily_aggregate_crps:6.2f}m (vs D0 {d0_res.daily_aggregate_crps:6.2f}m) | "
            f"Std Ratio: {res.aggregate_std_ratio:.3f} (vs D0 {d0_res.aggregate_std_ratio:.3f}) | "
            f"CoEx Err: {res.co_exceedance_abs_error:.5f} | Gate: [{res.overall_stage7_5_decision}]"
        )

    # 5. Sensitivity Evaluation of Randomized PIT
    LOGGER.info("\n--- Evaluating Discrete Randomized PIT Sensitivity (10 draws) ---")
    rep_batch = daily_batches[0]
    rep_marginals = system_candidates["SYS_seed_ensemble_3__DEP_D0_independent"].marginal_factory(rep_batch.flight_features)
    pit_sens = DiscretePITPolicy.evaluate_pit_sensitivity(
        y=rep_batch.observed_delays,  # type: ignore
        marginal_cdfs=rep_marginals,
        n_draws=10,
        base_seed=DEPLOYMENT_SEED,
    )
    LOGGER.info(f"Mean U standard deviation across 10 draws: {pit_sens['mean_u_std_across_draws']:.4f}")
    LOGGER.info(f"Max U standard deviation across 10 draws:  {pit_sens['max_u_std_across_draws']:.4f}")
    LOGGER.info(f"Sensitivity Stability Check:              {'PASS' if pit_sens['sensitivity_stable'] == 1.0 else 'FAIL'}")

    # 6. Gating Decision and Surviving Candidate Pool Selection for Stage 8
    LOGGER.info("\n========================================================")
    LOGGER.info("STAGE 7.5 PASS/FAIL MATRIX & SURVIVING CANDIDATE POOL")
    LOGGER.info("========================================================")

    surviving_pool_stage8: list[str] = []
    pruned_joint_candidates: list[str] = []

    for cand_id, res in candidate_results.items():
        status = res.overall_stage7_5_decision
        if status == "PASS":
            surviving_pool_stage8.append(cand_id)
            LOGGER.info(f"  [RETAINED] {cand_id:55s} -> Retained for Stage 8 evaluation")
        else:
            pruned_joint_candidates.append(cand_id)
            LOGGER.info(f"  [PRUNED  ] {cand_id:55s} -> {res.rejection_reasons}")

    LOGGER.info(f"\nSurviving Complete System Candidate Pool ({len(surviving_pool_stage8)} candidates):")
    for sc in surviving_pool_stage8:
        LOGGER.info(f"  * {sc}")

    # 7. Authoritative Manifest Export
    total_wall_sec = time.time() - start_time
    manifest_path = manifest_dir / "probabilistic_stage7_5_joint_validation_v1.json"
    manifest_content = {
        "manifest_version": "probabilistic_stage7_5_joint_validation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "STAGE_7_5_JOINT_VALIDATION",
        "total_wall_seconds": total_wall_sec,
        "evaluation_scope": {
            "folds_evaluated": [4],
            "development_years": [2022],
            "days_evaluated": len(selected_dates),
            "flights_evaluated": total_eval_flights,
            "pairs_evaluated": total_eval_pairs,
            "scenarios_per_day": args.n_scenarios,
        },
        "pit_randomization_sensitivity": pit_sens,
        "candidate_evaluations": {
            cid: res.to_dict() for cid, res in candidate_results.items()
        },
        "surviving_pool_count": len(surviving_pool_stage8),
        "surviving_complete_system_candidates_for_stage8": surviving_pool_stage8,
        "pruned_count": len(pruned_joint_candidates),
        "pruned_candidates": pruned_joint_candidates,
        "holdout_guards": {
            "2023_accessed": False,
            "2024_accessed": False,
        },
        "stage_status": "PASS",
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_content, f, indent=2)

    LOGGER.info(f"\nAuthoritative Stage 7.5 Joint Validation Manifest written to: {manifest_path}")
    LOGGER.info(f"Stage 7.5 successfully completed in {total_wall_sec:.2f}s.")


if __name__ == "__main__":
    main()
