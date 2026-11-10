"""Stage 3 Runner — Distribution Ablation: Separating Conditional Variance from Mixture Structure.

Executes expanding-window folds 1-4 for D1 (K=1 fixed sigma), D2 (K=1 heteroscedastic sigma),
and D3 (K=3 mixture) with and without calendar_year.
Conditionally opens D4 (K=5) if and only if pre-registered Stage 0 opening criteria are met.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    K5_MIN_COMPONENT_WEIGHT,
    K5_MIN_CRPS_IMPROVEMENT_DELTA,
    K5_MIN_EFFECTIVE_COMPONENTS,
)
from src.models.probabilistic.distribution_ablation import (
    DistributionLadderCandidate,
    train_distribution_candidate,
    vectorized_discrete_mixture_quantile,
)
from src.models.probabilistic.likelihood import discrete_mixture_cdf
from src.models.probabilistic.metrics import (
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
    build_daily_aggregation_table,
    compute_interval_metrics,
    compute_pinball_loss,
    compute_quantile_coverage,
    compute_quantile_crossing_rate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger(__name__)

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

CORE_CANDIDATES = [
    (DistributionLadderCandidate.D1_K1_FIXED_SIGMA, 1),
    (DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC, 1),
    (DistributionLadderCandidate.D3_K3_MIXTURE, 3),
]


def run_stage3_distribution_ablation(
    *,
    train_sample_per_year: int = 5000,
    val_sample: int = 5000,
    seed: int = 202601,
    max_epochs: int = 20,
    batch_size: int = 256,
    output_dir: str | Path = "artifacts/probabilistic/distribution_ablation",
    manifest_path: str | Path = "artifacts/manifests/probabilistic_stage3_distribution_ablation_v1.json",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    LOGGER.info("=================================================================")
    LOGGER.info("STARTING STAGE 3 DISTRIBUTION ABLATION EXECUTION")
    LOGGER.info(
        f"Screening seed: {seed}, Sample: {train_sample_per_year}/yr train, {val_sample} val"
    )
    LOGGER.info("=================================================================")

    per_fold_results: dict[str, dict[str, Any]] = {}
    pooled_data: dict[str, dict[str, list[Any]]] = {}

    for fold in FOLDS:
        fold_id = fold["fold_id"]
        train_years = fold["outer_train_years"]
        val_year = fold["outer_val_year"]
        inner_train_years = fold["inner_train_years"]
        inner_val_years = fold["inner_val_years"]

        LOGGER.info(f"\n--- Processing {fold_id} (Train {train_years}, Val {val_year}) ---")

        root = Path(__file__).resolve().parents[1]
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
            sample_train_per_year=train_sample_per_year,
            sample_val=val_sample,
            project_root=root,
            random_state=seed,
            feature_set="v1",
        )

        train_df = X_train.copy()
        train_df["ARR_DELAY"] = y_train_reg.to_numpy(dtype=np.float64)

        val_df = X_val.copy()
        val_df["ARR_DELAY"] = y_val_reg.to_numpy(dtype=np.float64)

        # Dates & flight keys
        for df in (train_df, val_df):
            if "flight_date" not in df.columns:
                df["flight_date"] = (
                    df["calendar_year"].astype(int).astype(str)
                    + "-"
                    + df["calendar_month"].astype(int).astype(str).str.zfill(2)
                    + "-"
                    + df["calendar_day_of_month"].astype(int).astype(str).str.zfill(2)
                )
            if "flight_key" not in df.columns:
                df["flight_key"] = [
                    f"{d}_{c}_{fl}_{i}"
                    for i, (d, c, fl) in enumerate(
                        zip(df["flight_date"], df["OP_CARRIER"], df["OP_CARRIER_FL_NUM"])
                    )
                ]

        inner_train_df = train_df[train_df["calendar_year"].isin(inner_train_years)].copy()
        inner_val_df = train_df[train_df["calendar_year"].isin(inner_val_years)].copy()

        y_val_true = val_df["ARR_DELAY"].to_numpy(dtype=np.float64)
        val_dates = val_df["flight_date"].to_numpy()

        per_fold_results[fold_id] = {}

        # Run core candidates across both calendar_year modes
        for cand, k in CORE_CANDIDATES:
            for with_year in (True, False):
                config_key = f"{cand.value}__{'with_year' if with_year else 'no_year'}"
                LOGGER.info(f"  -> Training candidate: {config_key} (K={k})...")

                t0 = time.time()
                res = train_distribution_candidate(
                    candidate=cand,
                    train_df=train_df,
                    val_df=val_df,
                    inner_train_df=inner_train_df,
                    inner_val_df=inner_val_df,
                    include_calendar_year=with_year,
                    k_components=k,
                    seed=seed,
                    max_epochs=max_epochs,
                    batch_size=batch_size,
                )
                elapsed = time.time() - t0

                preds = res["predictions"]
                pi_val = preds["pi"]
                mu_val = preds["mu"]
                sigma_val = preds["sigma"]
                crps_vec = preds["crps_vec"]
                y_point = preds["y_pred_point"]

                # Quantile calculation via vectorized discrete mixture CDF threshold search
                quantiles_dict: dict[float, np.ndarray] = {
                    alpha: vectorized_discrete_mixture_quantile(alpha, pi_val, mu_val, sigma_val)
                    for alpha in PRE_REGISTERED_QUANTILES
                }

                pinball_scores = {
                    f"pinball_q_{int(round(a * 1000)):03d}": float(
                        np.mean(compute_pinball_loss(y_val_true, quantiles_dict[a], a))
                    )
                    for a in PRE_REGISTERED_QUANTILES
                }
                coverage_scores = {
                    f"cov_q_{int(round(a * 1000)):03d}": compute_quantile_coverage(y_val_true, quantiles_dict[a])
                    for a in PRE_REGISTERED_QUANTILES
                }
                interval_scores = {}
                for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
                    cov, w = compute_interval_metrics(y_val_true, quantiles_dict[q_l], quantiles_dict[q_u])
                    interval_scores[f"interval_cov_{int(round(nom * 100))}"] = cov
                    interval_scores[f"interval_width_{int(round(nom * 100))}"] = w

                crossing_rate, total_inversions = compute_quantile_crossing_rate(quantiles_dict)
                crossing_metrics = {
                    "crossing_rate": crossing_rate,
                    "total_crossing_inversions": total_inversions,
                }
                interval_metrics = {**coverage_scores, **interval_scores}

                # Event probabilities and Brier scores for daily aggregation
                p_ge_15 = 1.0 - discrete_mixture_cdf(14.0, pi_val, mu_val, sigma_val)
                p_ge_60 = 1.0 - discrete_mixture_cdf(59.0, pi_val, mu_val, sigma_val)
                brier_15 = (p_ge_15 - (y_val_true >= 15.0).astype(float)) ** 2
                brier_60 = (p_ge_60 - (y_val_true >= 60.0).astype(float)) ** 2

                # Daily metrics table for day-block bootstrap
                daily_df = build_daily_aggregation_table(
                    flight_dates=val_dates,
                    per_flight_crps=crps_vec,
                    per_flight_nll=None,
                    per_flight_brier_15=brier_15,
                    per_flight_brier_60=brier_60,
                )
                daily_parquet = output_path / f"daily_{config_key}_{fold_id}.parquet"
                daily_df.to_parquet(daily_parquet, index=False)

                # Predictions parquet
                pred_dict: dict[str, Any] = {
                    "flight_key": val_df["flight_key"].to_numpy(),
                    "flight_date": val_dates,
                    "y_true": y_val_true,
                    "y_pred_point": y_point,
                    "crps": crps_vec,
                }
                for alpha in PRE_REGISTERED_QUANTILES:
                    q_str = f"q_{int(round(alpha * 1000)):03d}"
                    pred_dict[q_str] = quantiles_dict[alpha]
                pred_df = pd.DataFrame(pred_dict)
                pred_parquet = output_path / f"preds_{config_key}_{fold_id}.parquet"
                pred_df.to_parquet(pred_parquet, index=False)

                # Pool metrics
                if config_key not in pooled_data:
                    pooled_data[config_key] = {
                        "y_true": [],
                        "crps_vec": [],
                        "nll_discretized": [],
                        "nll_continuous": [],
                        "weights": [],
                        "entropy": [],
                        "n_eff": [],
                    }
                pooled_data[config_key]["y_true"].append(y_val_true)
                pooled_data[config_key]["crps_vec"].append(crps_vec)
                pooled_data[config_key]["nll_discretized"].append(res["metrics"]["nll_discretized"])
                pooled_data[config_key]["nll_continuous"].append(res["metrics"]["nll_continuous"])
                pooled_data[config_key]["weights"].append(res["component_stats"]["component_weights"])
                pooled_data[config_key]["entropy"].append(res["component_stats"]["component_entropy"])
                pooled_data[config_key]["n_eff"].append(res["component_stats"]["effective_component_count"])

                per_fold_results[fold_id][config_key] = {
                    "candidate": cand.value,
                    "k_components": k,
                    "include_calendar_year": with_year,
                    "best_epoch": res["best_epoch"],
                    "best_inner_nll": res["best_inner_nll"],
                    "metrics": res["metrics"],
                    "component_stats": res["component_stats"],
                    "sigma_stats": res["sigma_stats"],
                    "pinball_loss": pinball_scores,
                    "crossing_metrics": crossing_metrics,
                    "interval_metrics": interval_metrics,
                    "train_time_sec": elapsed,
                    "predictions_parquet": str(pred_parquet.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/"),
                    "daily_parquet": str(daily_parquet.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/"),
                }

    # -------------------------------------------------------------------------
    # Pooled Development Metrics
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- Computing Pooled Development Metrics ---")
    pooled_metrics: dict[str, dict[str, Any]] = {}
    for config_key, pdict in pooled_data.items():
        all_crps = np.concatenate(pdict["crps_vec"])
        pooled_metrics[config_key] = {
            "pooled_crps_mean": float(np.mean(all_crps)),
            "pooled_crps_std": float(np.std(all_crps)),
            "mean_nll_discretized": float(np.mean(pdict["nll_discretized"])),
            "mean_nll_continuous": float(np.mean(pdict["nll_continuous"])),
            "mean_effective_components": float(np.mean(pdict["n_eff"])),
            "mean_entropy": float(np.mean(pdict["entropy"])),
            "mean_component_weights": [float(w) for w in np.mean(pdict["weights"], axis=0)],
        }

    # -------------------------------------------------------------------------
    # Check K=5 Opening Criteria on Primary Specification (D3 with_year)
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- Evaluating Stage 0 K=5 Opening Criteria on D3 ---")
    d3_key = f"{DistributionLadderCandidate.D3_K3_MIXTURE.value}__with_year"
    d2_key = f"{DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC.value}__with_year"

    # 1. Effective components > 2.50 across all 4 development folds
    n_eff_per_fold = [
        per_fold_results[f["fold_id"]][d3_key]["component_stats"]["effective_component_count"]
        for f in FOLDS
    ]
    cond1_passed = all(ne > K5_MIN_EFFECTIVE_COMPONENTS for ne in n_eff_per_fold)

    # 2. Min component weight >= 0.05 across all 4 folds
    min_weight_per_fold = [
        per_fold_results[f["fold_id"]][d3_key]["component_stats"]["min_component_weight"]
        for f in FOLDS
    ]
    cond2_passed = all(mw >= K5_MIN_COMPONENT_WEIGHT for mw in min_weight_per_fold)

    # 3. Delta CRPS = CRPS(D2) - CRPS(D3) > 0.05 min
    d2_crps = pooled_metrics[d2_key]["pooled_crps_mean"]
    d3_crps = pooled_metrics[d3_key]["pooled_crps_mean"]
    crps_diff = d2_crps - d3_crps
    cond3_passed = crps_diff > K5_MIN_CRPS_IMPROVEMENT_DELTA

    k5_evaluation = {
        "condition_1_effective_components": {
            "required_threshold": K5_MIN_EFFECTIVE_COMPONENTS,
            "fold_values": n_eff_per_fold,
            "passed": cond1_passed,
        },
        "condition_2_min_component_weight": {
            "required_threshold": K5_MIN_COMPONENT_WEIGHT,
            "fold_values": min_weight_per_fold,
            "passed": cond2_passed,
        },
        "condition_3_crps_improvement": {
            "required_delta_minutes": K5_MIN_CRPS_IMPROVEMENT_DELTA,
            "observed_delta_minutes": float(crps_diff),
            "passed": cond3_passed,
        },
        "all_criteria_met": bool(cond1_passed and cond2_passed and cond3_passed),
        "k5_opened": bool(cond1_passed and cond2_passed and cond3_passed),
        "decision_rationale": (
            "All 3 pre-registered criteria passed; K=5 candidate opened."
            if (cond1_passed and cond2_passed and cond3_passed)
            else "At least one pre-registered opening criterion failed; K=5 remains sealed."
        ),
    }

    LOGGER.info(f"K=5 Opening Criteria Met: {k5_evaluation['all_criteria_met']}")
    LOGGER.info(f"Rationale: {k5_evaluation['decision_rationale']}")

    # -------------------------------------------------------------------------
    # Ladder Attribution & Calendar-Year Diagnosis
    # -------------------------------------------------------------------------
    d1_key = f"{DistributionLadderCandidate.D1_K1_FIXED_SIGMA.value}__with_year"
    ladder_attribution = {
        "d1_crps": pooled_metrics[d1_key]["pooled_crps_mean"],
        "d2_crps": pooled_metrics[d2_key]["pooled_crps_mean"],
        "d3_crps": pooled_metrics[d3_key]["pooled_crps_mean"],
        "heteroscedasticity_value_crps_delta (D1 - D2)": float(
            pooled_metrics[d1_key]["pooled_crps_mean"] - pooled_metrics[d2_key]["pooled_crps_mean"]
        ),
        "mixture_value_crps_delta (D2 - D3)": float(
            pooled_metrics[d2_key]["pooled_crps_mean"] - pooled_metrics[d3_key]["pooled_crps_mean"]
        ),
        "total_ladder_improvement (D1 - D3)": float(
            pooled_metrics[d1_key]["pooled_crps_mean"] - pooled_metrics[d3_key]["pooled_crps_mean"]
        ),
    }

    calendar_year_diagnosis = {
        "d1_with_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D1_K1_FIXED_SIGMA.value}__with_year"]["pooled_crps_mean"],
        "d1_no_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D1_K1_FIXED_SIGMA.value}__no_year"]["pooled_crps_mean"],
        "d2_with_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC.value}__with_year"]["pooled_crps_mean"],
        "d2_no_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC.value}__no_year"]["pooled_crps_mean"],
        "d3_with_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D3_K3_MIXTURE.value}__with_year"]["pooled_crps_mean"],
        "d3_no_year_crps": pooled_metrics[f"{DistributionLadderCandidate.D3_K3_MIXTURE.value}__no_year"]["pooled_crps_mean"],
        "d3_year_delta": float(
            pooled_metrics[f"{DistributionLadderCandidate.D3_K3_MIXTURE.value}__no_year"]["pooled_crps_mean"]
            - pooled_metrics[f"{DistributionLadderCandidate.D3_K3_MIXTURE.value}__with_year"]["pooled_crps_mean"]
        ),
    }

    wall_clock = time.time() - start_time
    LOGGER.info(f"\n=================================================================")
    LOGGER.info(f"STAGE 3 DISTRIBUTION ABLATION COMPLETED in {wall_clock:.2f} seconds")
    LOGGER.info(f"D1 (Fixed Sigma) CRPS: {ladder_attribution['d1_crps']:.4f}")
    LOGGER.info(f"D2 (Heteroscedastic) CRPS: {ladder_attribution['d2_crps']:.4f}")
    LOGGER.info(f"D3 (K=3 Mixture) CRPS: {ladder_attribution['d3_crps']:.4f}")
    LOGGER.info(f"Heteroscedasticity Contribution: {ladder_attribution['heteroscedasticity_value_crps_delta (D1 - D2)']:.4f} min")
    LOGGER.info(f"Mixture Structure Contribution: {ladder_attribution['mixture_value_crps_delta (D2 - D3)']:.4f} min")
    LOGGER.info("=================================================================")

    summary_manifest = {
        "manifest_version": "probabilistic_stage3_distribution_ablation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_manifest": "artifacts/manifests/probabilistic_protocol_v1.json",
        "seed": seed,
        "sample_train_per_year": train_sample_per_year,
        "sample_val": val_sample,
        "total_wall_seconds": wall_clock,
        "folds": [f["fold_id"] for f in FOLDS],
        "validation_years": [f["outer_val_year"] for f in FOLDS],
        "core_ladder_evaluated": [c[0].value for c in CORE_CANDIDATES],
        "calendar_year_ablation_modes": ["with_year", "no_year"],
        "per_fold_results": per_fold_results,
        "pooled_development_metrics": pooled_metrics,
        "ladder_attribution": ladder_attribution,
        "calendar_year_diagnosis": calendar_year_diagnosis,
        "k5_opening_evaluation": k5_evaluation,
        "sigma_policy": {
            "parameterization": "sigma(x) = softplus(raw_sigma(x)) + sigma_floor",
            "sigma_floor": DEFAULT_SIGMA_FLOOR,
            "gradient_clip_norm": 1.0,
        },
        "holdout_guards": {
            "2023_accessed": False,
            "2024_accessed": False,
        },
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(summary_manifest, f, indent=2)

    LOGGER.info(f"Summary manifest written to: {manifest_file}")
    return summary_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 3 Distribution Ablation")
    parser.add_argument("--train-sample", type=int, default=5000, help="Train samples per year")
    parser.add_argument("--val-sample", type=int, default=5000, help="Validation samples per year")
    parser.add_argument("--seed", type=int, default=202601, help="Screening seed")
    parser.add_argument("--epochs", type=int, default=20, help="Max inner epochs")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    args = parser.parse_args()

    run_stage3_distribution_ablation(
        train_sample_per_year=args.train_sample,
        val_sample=args.val_sample,
        seed=args.seed,
        max_epochs=args.epochs,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
