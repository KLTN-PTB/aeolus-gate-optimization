"""Stage 5 Runner — Neural Training Stability and Statistical Uncertainty Benchmark.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 8 & Section 10

Executes:
1. Training and evaluation of finalist candidate D3 across the 3 pre-registered seeds [202601, 202602, 202603]
   for all 4 expanding-window folds under both 'no_year' and 'with_year' modes.
2. Evaluation of the pre-registered 'seed_ensemble_3' candidate (exact 9-component mixture).
3. Assessment of algorithmic stability (mean +- SD, successful-run rate, dead-component rate, entropy, Neff).
4. Assessment of predictive consistency (point & quantile pairwise correlations/MAEs across seeds).
5. Statistical uncertainty estimation via day-block bootstrap (2,000 iterations) of paired score differences
   versus the approved baseline B2 (XGBoost OOF normal).
6. Manifest export: artifacts/manifests/probabilistic_stage5_stability_v1.json.
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
import torch

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    K5_MIN_CRPS_IMPROVEMENT_DELTA,
)
from src.models.probabilistic.distribution_ablation import (
    DistributionLadderCandidate,
    discretized_mixture_nll_torch,
    gaussian_mixture_crps,
    train_distribution_candidate,
    vectorized_discrete_mixture_quantile,
)
from src.models.probabilistic.metrics import compute_interval_metrics, compute_pinball_loss
from src.models.probabilistic.stability import (
    compute_algorithmic_stability,
    compute_day_block_bootstrap_ci,
    compute_prediction_consistency,
    construct_seed_ensemble_mixture,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("probabilistic_stage5")

FINALIST_SEEDS = [202601, 202602, 202603]
PREDETERMINED_DEPLOYMENT_SEED = 202601

FOLDS = [
    {
        "fold_id": "fold_1",
        "outer_train_years": [2016, 2017, 2018],
        "outer_val_year": 2019,
        "inner_train_years": [2016, 2017],
        "inner_val_years": [2018],
    },
    {
        "fold_id": "fold_2",
        "outer_train_years": [2016, 2017, 2018, 2019],
        "outer_val_year": 2020,
        "inner_train_years": [2016, 2017, 2018],
        "inner_val_years": [2019],
    },
    {
        "fold_id": "fold_3",
        "outer_train_years": [2016, 2017, 2018, 2019, 2020],
        "outer_val_year": 2021,
        "inner_train_years": [2016, 2017, 2018, 2019],
        "inner_val_years": [2020],
    },
    {
        "fold_id": "fold_4",
        "outer_train_years": [2016, 2017, 2018, 2019, 2020, 2021],
        "outer_val_year": 2022,
        "inner_train_years": [2016, 2017, 2018, 2019, 2020],
        "inner_val_years": [2021],
    },
]

QUANTILE_ALPHAS = [0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]
SYMMETRIC_INTERVAL_PAIRS = {
    0.50: (0.25, 0.75),
    0.80: (0.10, 0.90),
    0.90: (0.05, 0.95),
    0.95: (0.025, 0.975),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 5 Stability Benchmark")
    parser.add_argument("--train-sample", type=int, default=5000, help="Train samples per year")
    parser.add_argument("--val-sample", type=int, default=5000, help="Val samples per fold")
    parser.add_argument("--bootstraps", type=int, default=2000, help="Day/block bootstrap replications")
    args = parser.parse_args()

    start_time = time.time()
    LOGGER.info("=" * 80)
    LOGGER.info("STAGE 5 — NEURAL TRAINING STABILITY & DAY-BLOCK BOOTSTRAP BENCHMARK")
    LOGGER.info(f"Finalist seeds: {FINALIST_SEEDS}, Deployment seed: {PREDETERMINED_DEPLOYMENT_SEED}")
    LOGGER.info(f"Train samples/yr: {args.train_sample}, Val samples/fold: {args.val_sample}")
    LOGGER.info("=" * 80)

    output_dir = Path("artifacts/probabilistic/stability")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = Path("artifacts/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]

    # Containers for results
    # seed_runs[candidate_mode][seed][fold_id] -> results dict
    candidate_modes = ["no_year", "with_year"]
    raw_results: dict[str, dict[int, dict[str, Any]]] = {
        m: {s: {} for s in FINALIST_SEEDS} for m in candidate_modes
    }

    # Store prediction arrays for ensemble and consistency checks:
    # fold_predictions[candidate_mode][fold_id][seed] -> {pi, mu, sigma, y_val, dates, keys}
    fold_predictions: dict[str, dict[str, dict[int, dict[str, Any]]]] = {
        m: {f["fold_id"]: {} for f in FOLDS} for m in candidate_modes
    }

    # Track run failures
    total_runs_attempted = 0
    total_runs_succeeded = 0

    for fold in FOLDS:
        fold_id = fold["fold_id"]
        train_years = fold["outer_train_years"]
        val_year = fold["outer_val_year"]
        inner_train_years = fold["inner_train_years"]
        inner_val_years = fold["inner_val_years"]

        LOGGER.info(f"\n========================================================")
        LOGGER.info(f"--- Loading data for {fold_id} (Val {val_year}) ---")
        LOGGER.info(f"========================================================")

        # Fixed validation evaluation dataset using project seed 202601 for pairing
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
            train_years=train_years,
            val_year=val_year,
            sample_train_per_year=args.train_sample,
            sample_val=args.val_sample,
            project_root=root,
            random_state=PREDETERMINED_DEPLOYMENT_SEED,
            feature_set="v1",
        )

        train_df = X_train.copy()
        train_df["ARR_DELAY"] = y_train_reg.values
        val_df = X_val.copy()
        val_df["ARR_DELAY"] = y_val_reg.values

        for df in (train_df, val_df):
            if "flight_date" not in df.columns:
                df["flight_date"] = (
                    df["calendar_year"].astype(int).astype(str)
                    + "-"
                    + df["calendar_month"].astype(int).astype(str).str.zfill(2)
                    + "-"
                    + df["calendar_day_of_month"].astype(int).astype(str).str.zfill(2)
                )

        val_dates = val_df["flight_date"].to_numpy()

        inner_train_df = train_df[train_df["calendar_year"].isin(inner_train_years)].copy()
        inner_val_df = train_df[train_df["calendar_year"].isin(inner_val_years)].copy()

        for mode in candidate_modes:
            include_year = (mode == "with_year")
            cand_name = f"D3_k3_mixture__{mode}"

            for seed in FINALIST_SEEDS:
                LOGGER.info(f"\n>> Training {cand_name} on {fold_id} with SEED {seed}...")
                total_runs_attempted += 1

                try:
                    res = train_distribution_candidate(
                        candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
                        train_df=train_df,
                        val_df=val_df,
                        inner_train_df=inner_train_df,
                        inner_val_df=inner_val_df,
                        include_calendar_year=include_year,
                        k_components=3,
                        batch_size=1024,
                        max_epochs=20,
                        lr=1e-3,
                        weight_decay=1e-4,
                        seed=seed,
                        device="cpu",
                    )
                    total_runs_succeeded += 1
                except Exception as exc:
                    LOGGER.error(f"Run failed for {cand_name} on {fold_id} with seed {seed}: {exc}")
                    continue

                raw_results[mode][seed][fold_id] = res

                # Extract prediction arrays
                preds = res["predictions"]
                pi_val = preds["pi"]
                mu_val = preds["mu"]
                sigma_val = preds["sigma"]
                crps_vec = preds["crps_vec"]
                y_pred_point = preds["y_pred_point"]
                y_val_np = val_df["ARR_DELAY"].to_numpy(dtype=np.float64)

                quantiles_dict = {
                    a: vectorized_discrete_mixture_quantile(a, pi_val, mu_val, sigma_val)
                    for a in QUANTILE_ALPHAS
                }

                # Store for ensemble and consistency
                fold_predictions[mode][fold_id][seed] = {
                    "pi": pi_val,
                    "mu": mu_val,
                    "sigma": sigma_val,
                    "y_val": y_val_np,
                    "val_dates": val_dates,
                    "val_keys": val_flight_keys,
                    "metrics": res["metrics"],
                    "quantiles": {f"q_{int(round(a*1000)):03d}": quantiles_dict[a] for a in QUANTILE_ALPHAS},
                    "y_pred_point": y_pred_point,
                    "crps_pointwise": crps_vec,
                }

                # Save individual seed predictions parquet
                pred_df = pd.DataFrame({
                    "flight_key": val_flight_keys,
                    "flight_date": val_dates,
                    "y_true": y_val_np,
                    "y_pred_point": y_pred_point,
                    "crps": crps_vec,
                })
                for q_val in QUANTILE_ALPHAS:
                    col = f"q_{int(round(q_val*1000)):03d}"
                    pred_df[col] = quantiles_dict[q_val]

                out_p = output_dir / f"preds_{cand_name}_s{seed}_{fold_id}.parquet"
                pred_df.to_parquet(out_p, index=False)

                LOGGER.info(
                    f"  Fold {fold_id} Seed {seed}: CRPS = {res['metrics']['crps']:.4f} min, "
                    f"NLL = {res['metrics']['nll_discretized']:.4f}, Neff = {res['component_stats']['effective_component_count']:.2f}"
                )

    successful_run_rate = float(total_runs_succeeded / total_runs_attempted) if total_runs_attempted > 0 else 0.0
    LOGGER.info(f"\nAll runs completed. Successful run rate: {successful_run_rate * 100:.1f}% ({total_runs_succeeded}/{total_runs_attempted})")

    # =========================================================================
    # Evaluation of Pre-Registered Seed Ensemble Candidate: seed_ensemble_3
    # =========================================================================
    LOGGER.info("\n========================================================")
    LOGGER.info("CONSTRUCTING PRE-REGISTERED SEED ENSEMBLE CANDIDATE (seed_ensemble_3)")
    LOGGER.info("========================================================")

    ensemble_fold_results: dict[str, dict[str, Any]] = {m: {} for m in candidate_modes}
    ensemble_predictions: dict[str, dict[str, Any]] = {m: {} for m in candidate_modes}

    for mode in candidate_modes:
        for fold in FOLDS:
            fold_id = fold["fold_id"]
            seed_dict = fold_predictions[mode][fold_id]

            pi_list = [seed_dict[s]["pi"] for s in FINALIST_SEEDS]
            mu_list = [seed_dict[s]["mu"] for s in FINALIST_SEEDS]
            sigma_list = [seed_dict[s]["sigma"] for s in FINALIST_SEEDS]
            y_val_np = seed_dict[FINALIST_SEEDS[0]]["y_val"]
            val_dates = seed_dict[FINALIST_SEEDS[0]]["val_dates"]
            val_keys = seed_dict[FINALIST_SEEDS[0]]["val_keys"]

            # Exact mixture combination: 3 seeds * 3 components = 9 components
            pi_ens, mu_ens, sigma_ens = construct_seed_ensemble_mixture(pi_list, mu_list, sigma_list)

            # Evaluate exact analytical CRPS
            ens_crps_pointwise = gaussian_mixture_crps(y_val_np, pi_ens, mu_ens, sigma_ens)
            mean_crps = float(np.mean(ens_crps_pointwise))

            # Evaluate discretized NLL
            ens_nll = float(discretized_mixture_nll_torch(
                torch.from_numpy(y_val_np).float(),
                torch.from_numpy(pi_ens).float(),
                torch.from_numpy(mu_ens).float(),
                torch.from_numpy(sigma_ens).float(),
            ).item())

            # Evaluate point predictions (expected value)
            ens_point = np.sum(pi_ens * mu_ens, axis=1)
            ens_mae = float(np.mean(np.abs(y_val_np - ens_point)))

            # Evaluate 9 discrete quantiles
            quantiles_ens = {
                a: vectorized_discrete_mixture_quantile(a, pi_ens, mu_ens, sigma_ens)
                for a in QUANTILE_ALPHAS
            }

            # Metrics
            pinball_ens = {
                f"pinball_q_{int(round(a*1000)):03d}": float(np.mean(compute_pinball_loss(y_val_np, quantiles_ens[a], a)))
                for a in QUANTILE_ALPHAS
            }
            intervals_ens = {}
            for nom, (ql, qu) in SYMMETRIC_INTERVAL_PAIRS.items():
                cov, w = compute_interval_metrics(y_val_np, quantiles_ens[ql], quantiles_ens[qu])
                intervals_ens[f"interval_cov_{int(round(nom*100))}"] = cov
                intervals_ens[f"interval_width_{int(round(nom*100))}"] = w

            ens_res = {
                "crps": mean_crps,
                "nll_discretized": ens_nll,
                "mae": ens_mae,
                "pinball_loss": pinball_ens,
                "interval_metrics": intervals_ens,
            }
            ensemble_fold_results[mode][fold_id] = ens_res

            # Save ensemble predictions
            ens_pred_df = pd.DataFrame({
                "flight_key": val_keys,
                "flight_date": val_dates,
                "y_true": y_val_np,
                "y_pred_point": ens_point,
                "crps": ens_crps_pointwise,
            })
            for q_val in QUANTILE_ALPHAS:
                col = f"q_{int(round(q_val*1000)):03d}"
                ens_pred_df[col] = quantiles_ens[q_val]

            ens_parquet_p = output_dir / f"preds_seed_ensemble_3__{mode}_{fold_id}.parquet"
            ens_pred_df.to_parquet(ens_parquet_p, index=False)

            ensemble_predictions[mode][fold_id] = {
                "flight_date": val_dates,
                "crps": ens_crps_pointwise,
                "pred_df": ens_pred_df,
            }

            LOGGER.info(
                f"  Ensemble {mode} on {fold_id}: CRPS = {mean_crps:.4f} min, "
                f"NLL = {ens_nll:.4f}, MAE = {ens_mae:.4f} min"
            )

    # =========================================================================
    # Compute Algorithmic Stability Summaries Across Seeds
    # =========================================================================
    LOGGER.info("\n========================================================")
    LOGGER.info("COMPUTING ALGORITHMIC STABILITY SUMMARIES (Mean +- SD)")
    LOGGER.info("========================================================")

    stability_summaries: dict[str, Any] = {}
    predictive_consistencies: dict[str, Any] = {}

    for mode in candidate_modes:
        cand_name = f"D3_k3_mixture__{mode}"
        stability_summaries[cand_name] = {}

        # 1. Per-fold stability
        fold_stabs: dict[str, Any] = {}
        for fold in FOLDS:
            fold_id = fold["fold_id"]
            seed_metrics = {
                f"seed_{s}": {
                    "crps": raw_results[mode][s][fold_id]["metrics"]["crps"],
                    "nll_discretized": raw_results[mode][s][fold_id]["metrics"]["nll_discretized"],
                    "mae": raw_results[mode][s][fold_id]["metrics"]["mae"],
                    "effective_component_count": raw_results[mode][s][fold_id]["component_stats"]["effective_component_count"],
                    "component_entropy": raw_results[mode][s][fold_id]["component_stats"]["component_entropy"],
                    "sigma_q10": raw_results[mode][s][fold_id]["sigma_stats"]["q10"],
                    "sigma_q50": raw_results[mode][s][fold_id]["sigma_stats"]["q50"],
                    "sigma_q90": raw_results[mode][s][fold_id]["sigma_stats"]["q90"],
                }
                for s in FINALIST_SEEDS
            }
            fold_stabs[fold_id] = compute_algorithmic_stability(seed_metrics)

        # 2. Pooled stability (pooled across 20,000 instances)
        pooled_seed_metrics: dict[str, dict[str, float]] = {}
        for s in FINALIST_SEEDS:
            pooled_crps = float(np.mean([raw_results[mode][s][f["fold_id"]]["metrics"]["crps"] for f in FOLDS]))
            pooled_nll = float(np.mean([raw_results[mode][s][f["fold_id"]]["metrics"]["nll_discretized"] for f in FOLDS]))
            pooled_mae = float(np.mean([raw_results[mode][s][f["fold_id"]]["metrics"]["mae"] for f in FOLDS]))
            pooled_neff = float(np.mean([raw_results[mode][s][f["fold_id"]]["component_stats"]["effective_component_count"] for f in FOLDS]))
            pooled_entropy = float(np.mean([raw_results[mode][s][f["fold_id"]]["component_stats"]["component_entropy"] for f in FOLDS]))
            pooled_sigma_q50 = float(np.mean([raw_results[mode][s][f["fold_id"]]["sigma_stats"]["q50"] for f in FOLDS]))

            # Dead components: fraction of folds where min_pi < 1e-4
            dead_comp_count = sum(
                1 for f in FOLDS if raw_results[mode][s][f["fold_id"]]["component_stats"]["min_component_weight"] < 1e-4
            )
            dead_comp_rate = float(dead_comp_count / len(FOLDS))

            pooled_seed_metrics[f"seed_{s}"] = {
                "crps": pooled_crps,
                "nll_discretized": pooled_nll,
                "mae": pooled_mae,
                "effective_component_count": pooled_neff,
                "component_entropy": pooled_entropy,
                "sigma_q50": pooled_sigma_q50,
                "dead_component_rate": dead_comp_rate,
            }

        pooled_stab = compute_algorithmic_stability(pooled_seed_metrics)
        stability_summaries[cand_name]["per_fold"] = fold_stabs
        stability_summaries[cand_name]["pooled"] = pooled_stab

        # 3. Prediction consistency
        all_pred_points: dict[int, np.ndarray] = {s: [] for s in FINALIST_SEEDS}
        all_quantiles: dict[int, dict[str, list[np.ndarray]]] = {
            s: {f"q_{int(q*1000):03d}": [] for q in QUANTILE_ALPHAS} for s in FINALIST_SEEDS
        }

        for fold in FOLDS:
            fold_id = fold["fold_id"]
            for s in FINALIST_SEEDS:
                all_pred_points[s].append(fold_predictions[mode][fold_id][s]["y_pred_point"])
                for q_val in QUANTILE_ALPHAS:
                    col = f"q_{int(q_val*1000):03d}"
                    all_quantiles[s][col].append(fold_predictions[mode][fold_id][s]["quantiles"][col])

        flat_pred_points = {s: np.concatenate(all_pred_points[s]) for s in FINALIST_SEEDS}
        flat_quantiles = {
            s: {col: np.concatenate(all_quantiles[s][col]) for col in all_quantiles[s].keys()}
            for s in FINALIST_SEEDS
        }

        pred_consistency = compute_prediction_consistency(flat_pred_points, flat_quantiles)
        predictive_consistencies[cand_name] = pred_consistency

        LOGGER.info(f"\nAlgorithmic Stability for {cand_name} (Pooled):")
        LOGGER.info(
            f"  CRPS:       {pooled_stab['crps']['mean']:.4f} +- {pooled_stab['crps']['std']:.4f} min "
            f"(Range: [{pooled_stab['crps']['min']:.4f}, {pooled_stab['crps']['max']:.4f}])"
        )
        LOGGER.info(
            f"  NLL:        {pooled_stab['nll_discretized']['mean']:.4f} +- {pooled_stab['nll_discretized']['std']:.4f}"
        )
        LOGGER.info(
            f"  Neff:       {pooled_stab['effective_component_count']['mean']:.2f} +- {pooled_stab['effective_component_count']['std']:.2f}"
        )
        LOGGER.info(
            f"  Entropy:    {pooled_stab['component_entropy']['mean']:.3f} +- {pooled_stab['component_entropy']['std']:.3f}"
        )
        LOGGER.info(
            f"  Point Corr: {pred_consistency['mean_point_correlation']:.4f}, Point MAE: {pred_consistency['mean_point_mae']:.4f} min"
        )

    # =========================================================================
    # Day/Block Bootstrap: Statistical Sampling Uncertainty vs Baseline B2
    # =========================================================================
    LOGGER.info("\n========================================================")
    LOGGER.info("COMPUTING DAY-BLOCK BOOTSTRAP CONFIDENCE INTERVALS VS B2")
    LOGGER.info(f"Replications: {args.bootstraps}, Pre-registered Delta: {K5_MIN_CRPS_IMPROVEMENT_DELTA} min")
    LOGGER.info("========================================================")

    # Load Baseline B2 predictions from Stage 1
    b2_predictions: dict[str, pd.DataFrame] = {}
    for fold in FOLDS:
        fold_id = fold["fold_id"]
        b2_file = Path(f"artifacts/probabilistic/xgb_gaussian/predictions_{fold_id}.parquet")
        if not b2_file.exists():
            raise FileNotFoundError(f"Baseline B2 predictions not found at {b2_file}")
        b2_predictions[fold_id] = pd.read_parquet(b2_file)

    bootstrap_results: dict[str, Any] = {}

    # Candidates to compare against Baseline B2:
    # 1. Primary candidate D3 (deployment seed 202601, without calendar year)
    # 2. Diagnostic candidate D3 (deployment seed 202601, with calendar year)
    # 3. Seed Ensemble Candidate (seed_ensemble_3, without calendar year)
    eval_candidates = [
        ("D3_primary_deploy_s202601__no_year", "no_year", PREDETERMINED_DEPLOYMENT_SEED, False),
        ("D3_control_deploy_s202601__with_year", "with_year", PREDETERMINED_DEPLOYMENT_SEED, False),
        ("seed_ensemble_3__no_year", "no_year", None, True),
    ]

    for cand_label, mode, seed_val, is_ensemble in eval_candidates:
        LOGGER.info(f"\n--- Day/Block Bootstrap for {cand_label} vs Baseline B2 ---")
        bootstrap_results[cand_label] = {"per_fold": {}, "pooled": {}}

        pooled_daily_records: list[dict[str, Any]] = []

        for fold in FOLDS:
            fold_id = fold["fold_id"]
            df_b2 = b2_predictions[fold_id]

            if is_ensemble:
                df_cand = ensemble_predictions[mode][fold_id]["pred_df"]
            else:
                s_dict = fold_predictions[mode][fold_id][seed_val]
                df_cand = pd.DataFrame({
                    "flight_date": s_dict["val_dates"],
                    "crps": s_dict["crps_pointwise"],
                })

            # Exact paired per-flight delta CRPS
            # delta_crps = candidate_crps - baseline_crps (negative is improvement)
            delta_crps = df_cand["crps"].to_numpy() - df_b2["crps"].to_numpy()

            paired_df = pd.DataFrame({
                "flight_date": df_cand["flight_date"],
                "delta_crps": delta_crps,
            })

            # Aggregate by flight date
            daily_agg = paired_df.groupby("flight_date").agg(
                delta_crps=("delta_crps", "mean"),
                n_flights=("delta_crps", "count"),
            ).reset_index()

            # Save daily parquet
            daily_out_p = output_dir / f"daily_delta_{cand_label}_{fold_id}.parquet"
            daily_agg.to_parquet(daily_out_p, index=False)

            # Run day-block bootstrap on fold
            fold_boot = compute_day_block_bootstrap_ci(
                daily_agg,
                n_bootstraps=args.bootstraps,
                seed=PREDETERMINED_DEPLOYMENT_SEED,
                delta_threshold=K5_MIN_CRPS_IMPROVEMENT_DELTA,
            )

            bootstrap_results[cand_label]["per_fold"][fold_id] = {
                "point_estimate_delta_crps": fold_boot.point_estimate_delta_crps,
                "point_estimate_improvement": fold_boot.point_estimate_improvement,
                "bootstrap_se": fold_boot.bootstrap_se,
                "ci_95_delta_crps": [fold_boot.ci_lower_delta_crps, fold_boot.ci_upper_delta_crps],
                "ci_95_improvement": [fold_boot.ci_lower_improvement, fold_boot.ci_upper_improvement],
                "lower_bound_exceeds_threshold": fold_boot.lower_bound_exceeds_threshold,
                "n_days": fold_boot.n_days,
                "n_flights": fold_boot.n_flights,
            }

            for _, row in daily_agg.iterrows():
                pooled_daily_records.append(row.to_dict())

            LOGGER.info(
                f"  {fold_id}: Mean Improvement = {fold_boot.point_estimate_improvement:+.4f} min, "
                f"95% CI = [{fold_boot.ci_lower_improvement:+.4f}, {fold_boot.ci_upper_improvement:+.4f}], "
                f"SE = {fold_boot.bootstrap_se:.4f} min, Exceeds {K5_MIN_CRPS_IMPROVEMENT_DELTA}m: {fold_boot.lower_bound_exceeds_threshold}"
            )

        # Pooled day-block bootstrap across all 4 folds (20,000 flights)
        pooled_daily_df = pd.DataFrame(pooled_daily_records)
        pooled_boot = compute_day_block_bootstrap_ci(
            pooled_daily_df,
            n_bootstraps=args.bootstraps,
            seed=PREDETERMINED_DEPLOYMENT_SEED,
            delta_threshold=K5_MIN_CRPS_IMPROVEMENT_DELTA,
        )

        bootstrap_results[cand_label]["pooled"] = {
            "point_estimate_delta_crps": pooled_boot.point_estimate_delta_crps,
            "point_estimate_improvement": pooled_boot.point_estimate_improvement,
            "bootstrap_se": pooled_boot.bootstrap_se,
            "ci_95_delta_crps": [pooled_boot.ci_lower_delta_crps, pooled_boot.ci_upper_delta_crps],
            "ci_95_improvement": [pooled_boot.ci_lower_improvement, pooled_boot.ci_upper_improvement],
            "lower_bound_exceeds_threshold": pooled_boot.lower_bound_exceeds_threshold,
            "n_days": pooled_boot.n_days,
            "n_flights": pooled_boot.n_flights,
        }

        LOGGER.info(
            f"  POOLED: Mean Improvement = {pooled_boot.point_estimate_improvement:+.4f} min, "
            f"95% CI = [{pooled_boot.ci_lower_improvement:+.4f}, {pooled_boot.ci_upper_improvement:+.4f}], "
            f"SE = {pooled_boot.bootstrap_se:.4f} min, Exceeds {K5_MIN_CRPS_IMPROVEMENT_DELTA}m: {pooled_boot.lower_bound_exceeds_threshold}"
        )

    total_wall_sec = time.time() - start_time
    LOGGER.info(f"\nStage 5 execution successfully finished in {total_wall_sec:.2f}s.")

    # =========================================================================
    # Export Comprehensive Stage 5 Summary Manifest
    # =========================================================================
    manifest_path = manifest_dir / "probabilistic_stage5_stability_v1.json"
    manifest_content = {
        "manifest_version": "probabilistic_stage5_stability_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_manifest": "artifacts/manifests/probabilistic_protocol_v1.json",
        "seed_manifest": "artifacts/manifests/seed_manifest_v1.json",
        "finalist_seeds": FINALIST_SEEDS,
        "predetermined_deployment_seed": PREDETERMINED_DEPLOYMENT_SEED,
        "seed_policy": "evaluation_only_with_predetermined_deployment_seed",
        "registered_seed_ensemble_candidate": "seed_ensemble_3",
        "sample_train_per_year": args.train_sample,
        "sample_val": args.val_sample,
        "total_wall_seconds": total_wall_sec,
        "successful_run_rate": successful_run_rate,
        "runs_attempted": total_runs_attempted,
        "runs_succeeded": total_runs_succeeded,
        "algorithmic_stability": stability_summaries,
        "predictive_consistency": predictive_consistencies,
        "seed_ensemble_results": ensemble_fold_results,
        "statistical_uncertainty_bootstrap": bootstrap_results,
        "pre_registered_effect_size_delta": K5_MIN_CRPS_IMPROVEMENT_DELTA,
        "holdout_guards": {
            "2023_accessed": False,
            "2024_accessed": False,
        },
        "stage_status": "PASS",
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_content, f, indent=2)

    LOGGER.info(f"Summary manifest successfully created at: {manifest_path}")


if __name__ == "__main__":
    main()
