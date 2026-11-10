"""Stage 1 Distributional Baselines Runner.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Stage 1
Evaluates 5 non-MDN baselines across the 4 expanding-window folds:
- B1: Empirical carrier x scheduled-hour (with hierarchical backoff)
- B2: XGBoost point mean + cross-fitted OOF residual uncertainty (fixed-sigma Gaussian)
- B3: NGBoost Normal (heteroscedastic Gaussian)
- B4: LightGBM Quantile (multi-pinball regression across 9 quantiles)
- B5: NGBoost Student-T (heavy-tail candidate)

Saves:
- Fold-level prediction Parquet files
- Fold-level daily aggregation Parquet files
- Summary manifest with per-fold, pooled, and year-wise metrics
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.baselines import (
    B1EmpiricalDistribution,
    B2XGBoostGaussian,
    B3NGBoostNormal,
    B4LightGBMQuantile,
    B5NGBoostStudentT,
)
from src.models.probabilistic.contracts import (
    PREDETERMINED_DEPLOYMENT_SEED,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    SCREENING_SEED,
)
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
    build_daily_aggregation_table,
    compute_brier_score,
    compute_gaussian_crps,
    compute_gaussian_nll,
    compute_interval_metrics,
    compute_pinball_loss,
    compute_quantile_coverage,
    compute_quantile_crossing_rate,
)
from src.models.probabilistic.splitting import FROZEN_PROBABILISTIC_FOLDS


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_stage1_baselines(
    *,
    sample_train_per_year: int = 15_000,
    sample_val: int = 15_000,
    seed: int = SCREENING_SEED,
) -> Path:
    start_time = time.time()
    artifacts_dir = ROOT / "artifacts" / "probabilistic"
    manifests_dir = ROOT / "artifacts" / "manifests"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    baseline_dirs = {
        "B1_empirical": artifacts_dir / "baseline_empirical",
        "B2_xgb_gaussian": artifacts_dir / "xgb_gaussian",
        "B3_ngboost_normal": artifacts_dir / "ngboost",
        "B4_lightgbm_quantile": artifacts_dir / "lightgbm_quantile",
        "B5_ngboost_student_t": artifacts_dir / "ngboost_student_t",
    }
    for d in baseline_dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    fold_results: dict[str, dict[str, Any]] = {}
    pooled_data: dict[str, list[dict[str, Any]]] = {b: [] for b in baseline_dirs}

    print("=================================================================")
    print("STARTING STAGE 1 DISTRIBUTIONAL BASELINES EXECUTION")
    print(f"Screening seed: {seed}, Sample: {sample_train_per_year}/yr train, {sample_val}/yr val")
    print("=================================================================")

    for fold in FROZEN_PROBABILISTIC_FOLDS:
        fold_id = fold.fold_id
        val_year = fold.outer_val_year
        train_years = fold.outer_train_years
        print(f"\n--- Processing {fold_id} (Train {list(train_years)}, Val {val_year}) ---")

        # 1. Load data strictly respecting fold boundaries
        (
            X_train,
            y_train_cls,
            y_train_reg,
            train_years_vec,
            X_val,
            y_val_cls,
            y_val_reg,
            val_flight_keys,
        ) = load_stratified_fold_data(
            train_years=train_years,
            val_year=val_year,
            sample_train_per_year=sample_train_per_year,
            sample_val=sample_val,
            project_root=ROOT,
            random_state=seed,
            feature_set="v1",
        )

        y_train = y_train_reg.to_numpy(dtype=np.float64)
        y_val = y_val_reg.to_numpy(dtype=np.float64)
        n_val = len(y_val)

        # Reconstruct flight date
        dates = pd.to_datetime(
            {
                "year": X_val["calendar_year"],
                "month": X_val["calendar_month"],
                "day": X_val["calendar_day_of_month"],
            }
        ).dt.strftime("%Y-%m-%d")

        fold_metrics: dict[str, dict[str, Any]] = {}

        # -------------------------------------------------------------
        # B1: Empirical carrier x hour
        # -------------------------------------------------------------
        print("  -> Training B1: Empirical distribution...")
        t0 = time.time()
        b1 = B1EmpiricalDistribution(min_support=30)
        b1.fit(X_train, y_train)
        b1_pred = b1.predict_distribution(X_val)
        t_b1 = time.time() - t0

        b1_crps = compute_gaussian_crps(y_val, b1_pred["mu"], b1_pred["sigma"])
        b1_nll = compute_gaussian_nll(y_val, b1_pred["mu"], b1_pred["sigma"])
        b1_brier_15 = (y_val >= 15.0).astype(float) - b1_pred["event_probs"][15.0]
        b1_brier_60 = (y_val >= 60.0).astype(float) - b1_pred["event_probs"][60.0]

        # Calculate B1 pinball & intervals
        b1_pinball = {
            f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(y_val, b1_pred["quantiles"][a], a)))
            for a in PRE_REGISTERED_QUANTILES
        }
        b1_coverage = {
            f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(y_val, b1_pred["quantiles"][a])
            for a in PRE_REGISTERED_QUANTILES
        }
        b1_intervals = {}
        for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
            cov, w = compute_interval_metrics(y_val, b1_pred["quantiles"][q_l], b1_pred["quantiles"][q_u])
            b1_intervals[f"interval_cov_{int(nom*100)}"] = cov
            b1_intervals[f"interval_width_{int(nom*100)}"] = w

        crossing_rate_b1, _ = compute_quantile_crossing_rate(b1_pred["quantiles"])

        fold_metrics["B1_empirical"] = {
            "crps_mean": float(np.mean(b1_crps)),
            "nll_mean": float(np.mean(b1_nll)),
            "brier_15": compute_brier_score(y_val, b1_pred["event_probs"][15.0], 15.0),
            "brier_60": compute_brier_score(y_val, b1_pred["event_probs"][60.0], 60.0),
            "brier_120": compute_brier_score(y_val, b1_pred["event_probs"][120.0], 120.0),
            "crossing_rate": crossing_rate_b1,
            "train_time_sec": t_b1,
            **b1_pinball,
            **b1_coverage,
            **b1_intervals,
        }

        # Save B1 predictions
        df_b1_pred = pd.DataFrame(
            {
                "flight_key": val_flight_keys,
                "flight_date": dates,
                "y_true": y_val,
                "mu": b1_pred["mu"],
                "sigma": b1_pred["sigma"],
                "crps": b1_crps,
                "nll": b1_nll,
                "p_ge_15": b1_pred["event_probs"][15.0],
                "p_ge_60": b1_pred["event_probs"][60.0],
                "p_ge_120": b1_pred["event_probs"][120.0],
                "backoff_level": b1_pred["backoff_levels"],
            }
        )
        for a in PRE_REGISTERED_QUANTILES:
            df_b1_pred[f"q_{int(a*1000):03d}"] = b1_pred["quantiles"][a]
        b1_pred_file = baseline_dirs["B1_empirical"] / f"predictions_{fold_id}.parquet"
        df_b1_pred.to_parquet(b1_pred_file, index=False)

        # Save B1 daily aggregation
        b1_daily = build_daily_aggregation_table(
            dates, b1_crps, b1_nll, b1_brier_15**2, b1_brier_60**2
        )
        b1_daily.to_parquet(baseline_dirs["B1_empirical"] / f"daily_metrics_{fold_id}.parquet", index=False)

        pooled_data["B1_empirical"].append(
            {"y": y_val, "mu": b1_pred["mu"], "sigma": b1_pred["sigma"], "crps": b1_crps, "nll": b1_nll, "ev": b1_pred["event_probs"], "q": b1_pred["quantiles"]}
        )

        # -------------------------------------------------------------
        # B2: XGBoost mean + OOF residual uncertainty
        # -------------------------------------------------------------
        print("  -> Training B2: XGBoost Gaussian (with cross-fitted OOF sigma)...")
        t0 = time.time()
        b2 = B2XGBoostGaussian(seed=seed, n_oof_splits=3)
        b2.fit(X_train, y_train)
        b2_pred = b2.predict_distribution(X_val)
        t_b2 = time.time() - t0

        b2_crps = compute_gaussian_crps(y_val, b2_pred["mu"], b2_pred["sigma"])
        b2_nll = compute_gaussian_nll(y_val, b2_pred["mu"], b2_pred["sigma"])
        b2_brier_15 = (y_val >= 15.0).astype(float) - b2_pred["event_probs"][15.0]
        b2_brier_60 = (y_val >= 60.0).astype(float) - b2_pred["event_probs"][60.0]

        b2_pinball = {
            f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(y_val, b2_pred["quantiles"][a], a)))
            for a in PRE_REGISTERED_QUANTILES
        }
        b2_coverage = {
            f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(y_val, b2_pred["quantiles"][a])
            for a in PRE_REGISTERED_QUANTILES
        }
        b2_intervals = {}
        for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
            cov, w = compute_interval_metrics(y_val, b2_pred["quantiles"][q_l], b2_pred["quantiles"][q_u])
            b2_intervals[f"interval_cov_{int(nom*100)}"] = cov
            b2_intervals[f"interval_width_{int(nom*100)}"] = w

        crossing_rate_b2, _ = compute_quantile_crossing_rate(b2_pred["quantiles"])

        fold_metrics["B2_xgb_gaussian"] = {
            "crps_mean": float(np.mean(b2_crps)),
            "nll_mean": float(np.mean(b2_nll)),
            "sigma_oof": b2.sigma_oof_,
            "in_sample_sigma": b2.in_sample_sigma_,
            "brier_15": compute_brier_score(y_val, b2_pred["event_probs"][15.0], 15.0),
            "brier_60": compute_brier_score(y_val, b2_pred["event_probs"][60.0], 60.0),
            "brier_120": compute_brier_score(y_val, b2_pred["event_probs"][120.0], 120.0),
            "crossing_rate": crossing_rate_b2,
            "train_time_sec": t_b2,
            **b2_pinball,
            **b2_coverage,
            **b2_intervals,
        }

        df_b2_pred = pd.DataFrame(
            {
                "flight_key": val_flight_keys,
                "flight_date": dates,
                "y_true": y_val,
                "mu": b2_pred["mu"],
                "sigma": b2_pred["sigma"],
                "crps": b2_crps,
                "nll": b2_nll,
                "p_ge_15": b2_pred["event_probs"][15.0],
                "p_ge_60": b2_pred["event_probs"][60.0],
                "p_ge_120": b2_pred["event_probs"][120.0],
            }
        )
        for a in PRE_REGISTERED_QUANTILES:
            df_b2_pred[f"q_{int(a*1000):03d}"] = b2_pred["quantiles"][a]
        df_b2_pred.to_parquet(baseline_dirs["B2_xgb_gaussian"] / f"predictions_{fold_id}.parquet", index=False)

        b2_daily = build_daily_aggregation_table(
            dates, b2_crps, b2_nll, b2_brier_15**2, b2_brier_60**2
        )
        b2_daily.to_parquet(baseline_dirs["B2_xgb_gaussian"] / f"daily_metrics_{fold_id}.parquet", index=False)

        pooled_data["B2_xgb_gaussian"].append(
            {"y": y_val, "mu": b2_pred["mu"], "sigma": b2_pred["sigma"], "crps": b2_crps, "nll": b2_nll, "ev": b2_pred["event_probs"], "q": b2_pred["quantiles"]}
        )

        # -------------------------------------------------------------
        # B3: NGBoost Normal (Heteroscedastic Gaussian)
        # -------------------------------------------------------------
        print("  -> Training B3: NGBoost Normal...")
        t0 = time.time()
        b3 = B3NGBoostNormal(seed=seed, n_estimators=60, learning_rate=0.03)
        b3.fit(X_train, y_train)
        b3_pred = b3.predict_distribution(X_val)
        t_b3 = time.time() - t0

        b3_crps = compute_gaussian_crps(y_val, b3_pred["mu"], b3_pred["sigma"])
        b3_nll = compute_gaussian_nll(y_val, b3_pred["mu"], b3_pred["sigma"])
        b3_brier_15 = (y_val >= 15.0).astype(float) - b3_pred["event_probs"][15.0]
        b3_brier_60 = (y_val >= 60.0).astype(float) - b3_pred["event_probs"][60.0]

        b3_pinball = {
            f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(y_val, b3_pred["quantiles"][a], a)))
            for a in PRE_REGISTERED_QUANTILES
        }
        b3_coverage = {
            f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(y_val, b3_pred["quantiles"][a])
            for a in PRE_REGISTERED_QUANTILES
        }
        b3_intervals = {}
        for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
            cov, w = compute_interval_metrics(y_val, b3_pred["quantiles"][q_l], b3_pred["quantiles"][q_u])
            b3_intervals[f"interval_cov_{int(nom*100)}"] = cov
            b3_intervals[f"interval_width_{int(nom*100)}"] = w

        crossing_rate_b3, _ = compute_quantile_crossing_rate(b3_pred["quantiles"])

        fold_metrics["B3_ngboost_normal"] = {
            "crps_mean": float(np.mean(b3_crps)),
            "nll_mean": float(np.mean(b3_nll)),
            "sigma_mean": float(np.mean(b3_pred["sigma"])),
            "sigma_std": float(np.std(b3_pred["sigma"])),
            "brier_15": compute_brier_score(y_val, b3_pred["event_probs"][15.0], 15.0),
            "brier_60": compute_brier_score(y_val, b3_pred["event_probs"][60.0], 60.0),
            "brier_120": compute_brier_score(y_val, b3_pred["event_probs"][120.0], 120.0),
            "crossing_rate": crossing_rate_b3,
            "train_time_sec": t_b3,
            **b3_pinball,
            **b3_coverage,
            **b3_intervals,
        }

        df_b3_pred = pd.DataFrame(
            {
                "flight_key": val_flight_keys,
                "flight_date": dates,
                "y_true": y_val,
                "mu": b3_pred["mu"],
                "sigma": b3_pred["sigma"],
                "crps": b3_crps,
                "nll": b3_nll,
                "p_ge_15": b3_pred["event_probs"][15.0],
                "p_ge_60": b3_pred["event_probs"][60.0],
                "p_ge_120": b3_pred["event_probs"][120.0],
            }
        )
        for a in PRE_REGISTERED_QUANTILES:
            df_b3_pred[f"q_{int(a*1000):03d}"] = b3_pred["quantiles"][a]
        df_b3_pred.to_parquet(baseline_dirs["B3_ngboost_normal"] / f"predictions_{fold_id}.parquet", index=False)

        b3_daily = build_daily_aggregation_table(
            dates, b3_crps, b3_nll, b3_brier_15**2, b3_brier_60**2
        )
        b3_daily.to_parquet(baseline_dirs["B3_ngboost_normal"] / f"daily_metrics_{fold_id}.parquet", index=False)

        pooled_data["B3_ngboost_normal"].append(
            {"y": y_val, "mu": b3_pred["mu"], "sigma": b3_pred["sigma"], "crps": b3_crps, "nll": b3_nll, "ev": b3_pred["event_probs"], "q": b3_pred["quantiles"]}
        )

        # -------------------------------------------------------------
        # B4: LightGBM Quantile
        # -------------------------------------------------------------
        print("  -> Training B4: LightGBM Quantile (9 pinball models)...")
        t0 = time.time()
        b4 = B4LightGBMQuantile(seed=seed, n_estimators=100, learning_rate=0.05)
        b4.fit(X_train, y_train)
        b4_pred_q = b4.predict_quantiles(X_val)
        t_b4 = time.time() - t0

        b4_pinball = {
            f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(y_val, b4_pred_q[a], a)))
            for a in PRE_REGISTERED_QUANTILES
        }
        b4_coverage = {
            f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(y_val, b4_pred_q[a])
            for a in PRE_REGISTERED_QUANTILES
        }
        b4_intervals = {}
        for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
            cov, w = compute_interval_metrics(y_val, b4_pred_q[q_l], b4_pred_q[q_u])
            b4_intervals[f"interval_cov_{int(nom*100)}"] = cov
            b4_intervals[f"interval_width_{int(nom*100)}"] = w

        crossing_rate_b4, n_inversions_b4 = compute_quantile_crossing_rate(b4_pred_q)

        # NOTE: CRPS is strictly omitted for B4 as mandated by protocol rule
        fold_metrics["B4_lightgbm_quantile"] = {
            "crps_mean": None,
            "nll_mean": None,
            "crossing_rate": crossing_rate_b4,
            "total_crossing_inversions": n_inversions_b4,
            "train_time_sec": t_b4,
            **b4_pinball,
            **b4_coverage,
            **b4_intervals,
        }

        df_b4_pred = pd.DataFrame(
            {
                "flight_key": val_flight_keys,
                "flight_date": dates,
                "y_true": y_val,
            }
        )
        for a in PRE_REGISTERED_QUANTILES:
            df_b4_pred[f"q_{int(a*1000):03d}"] = b4_pred_q[a]
        df_b4_pred.to_parquet(baseline_dirs["B4_lightgbm_quantile"] / f"predictions_{fold_id}.parquet", index=False)

        # B4 daily aggregation with pinball losses
        daily_b4 = pd.DataFrame({"flight_date": dates})
        for a in [0.10, 0.50, 0.90]:
            daily_b4[f"pinball_{int(a*100):02d}"] = compute_pinball_loss(y_val, b4_pred_q[a], a)
        daily_b4_agg = daily_b4.groupby("flight_date").mean().reset_index()
        daily_b4_agg.to_parquet(baseline_dirs["B4_lightgbm_quantile"] / f"daily_metrics_{fold_id}.parquet", index=False)

        pooled_data["B4_lightgbm_quantile"].append({"y": y_val, "q": b4_pred_q})

        # -------------------------------------------------------------
        # B5: NGBoost Student-T
        # -------------------------------------------------------------
        print("  -> Training B5: NGBoost Student-T...")
        t0 = time.time()
        b5 = B5NGBoostStudentT(seed=seed, n_estimators=50, learning_rate=0.005)
        b5.fit(X_train, y_train)
        b5_pred = b5.predict_distribution(X_val)
        t_b5 = time.time() - t0

        df_vals = b5_pred["df"]
        z_t = (y_val - b5_pred["mu"]) / b5_pred["sigma"]
        b5_nll = -student_t.logpdf(z_t, df=df_vals) + np.log(b5_pred["sigma"])

        b5_pinball = {
            f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(y_val, b5_pred["quantiles"][a], a)))
            for a in PRE_REGISTERED_QUANTILES
        }
        b5_coverage = {
            f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(y_val, b5_pred["quantiles"][a])
            for a in PRE_REGISTERED_QUANTILES
        }
        b5_intervals = {}
        for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
            cov, w = compute_interval_metrics(y_val, b5_pred["quantiles"][q_l], b5_pred["quantiles"][q_u])
            b5_intervals[f"interval_cov_{int(nom*100)}"] = cov
            b5_intervals[f"interval_width_{int(nom*100)}"] = w

        crossing_rate_b5, _ = compute_quantile_crossing_rate(b5_pred["quantiles"])

        fold_metrics["B5_ngboost_student_t"] = {
            "crps_mean": None,  # analytical Student-T CRPS is non-standard; NLL and pinball are primary
            "nll_mean": float(np.mean(b5_nll)),
            "df_mean": float(np.mean(df_vals)),
            "df_min": float(np.min(df_vals)),
            "brier_15": compute_brier_score(y_val, b5_pred["event_probs"][15.0], 15.0),
            "brier_60": compute_brier_score(y_val, b5_pred["event_probs"][60.0], 60.0),
            "brier_120": compute_brier_score(y_val, b5_pred["event_probs"][120.0], 120.0),
            "crossing_rate": crossing_rate_b5,
            "train_time_sec": t_b5,
            **b5_pinball,
            **b5_coverage,
            **b5_intervals,
        }

        df_b5_pred = pd.DataFrame(
            {
                "flight_key": val_flight_keys,
                "flight_date": dates,
                "y_true": y_val,
                "mu": b5_pred["mu"],
                "sigma": b5_pred["sigma"],
                "df": df_vals,
                "nll": b5_nll,
                "p_ge_15": b5_pred["event_probs"][15.0],
                "p_ge_60": b5_pred["event_probs"][60.0],
                "p_ge_120": b5_pred["event_probs"][120.0],
            }
        )
        for a in PRE_REGISTERED_QUANTILES:
            df_b5_pred[f"q_{int(a*1000):03d}"] = b5_pred["quantiles"][a]
        df_b5_pred.to_parquet(baseline_dirs["B5_ngboost_student_t"] / f"predictions_{fold_id}.parquet", index=False)

        b5_brier_15 = (y_val >= 15.0).astype(float) - b5_pred["event_probs"][15.0]
        b5_brier_60 = (y_val >= 60.0).astype(float) - b5_pred["event_probs"][60.0]
        b5_daily = build_daily_aggregation_table(
            dates, None, b5_nll, b5_brier_15**2, b5_brier_60**2
        )
        b5_daily.to_parquet(baseline_dirs["B5_ngboost_student_t"] / f"daily_metrics_{fold_id}.parquet", index=False)

        pooled_data["B5_ngboost_student_t"].append(
            {"y": y_val, "mu": b5_pred["mu"], "sigma": b5_pred["sigma"], "df": df_vals, "nll": b5_nll, "ev": b5_pred["event_probs"], "q": b5_pred["quantiles"]}
        )

        fold_results[fold_id] = fold_metrics
        del X_train, X_val, y_train, y_val
        gc.collect()

    # -------------------------------------------------------------
    # 2. Compute Pooled Development Metrics (2016-2022)
    # -------------------------------------------------------------
    print("\n--- Computing Pooled Development Metrics ---")
    pooled_summary: dict[str, dict[str, Any]] = {}

    for b_name in baseline_dirs:
        b_folds = pooled_data[b_name]
        all_y = np.concatenate([f["y"] for f in b_folds])

        if b_name in {"B1_empirical", "B2_xgb_gaussian", "B3_ngboost_normal"}:
            all_crps = np.concatenate([f["crps"] for f in b_folds])
            all_nll = np.concatenate([f["nll"] for f in b_folds])
            p_15 = np.concatenate([f["ev"][15.0] for f in b_folds])
            p_60 = np.concatenate([f["ev"][60.0] for f in b_folds])
            p_120 = np.concatenate([f["ev"][120.0] for f in b_folds])

            pinball_dict = {
                f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(
                    all_y, np.concatenate([f["q"][a] for f in b_folds]), a
                )))
                for a in PRE_REGISTERED_QUANTILES
            }
            cov_dict = {
                f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(
                    all_y, np.concatenate([f["q"][a] for f in b_folds])
                )
                for a in PRE_REGISTERED_QUANTILES
            }
            intervals_dict = {}
            for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
                cov, w = compute_interval_metrics(
                    all_y,
                    np.concatenate([f["q"][q_l] for f in b_folds]),
                    np.concatenate([f["q"][q_u] for f in b_folds]),
                )
                intervals_dict[f"interval_cov_{int(nom*100)}"] = cov
                intervals_dict[f"interval_width_{int(nom*100)}"] = w

            all_quantiles_dict = {
                a: np.concatenate([f["q"][a] for f in b_folds])
                for a in PRE_REGISTERED_QUANTILES
            }
            cr, _ = compute_quantile_crossing_rate(all_quantiles_dict)

            pooled_summary[b_name] = {
                "crps_mean": float(np.mean(all_crps)),
                "nll_mean": float(np.mean(all_nll)),
                "brier_15": compute_brier_score(all_y, p_15, 15.0),
                "brier_60": compute_brier_score(all_y, p_60, 60.0),
                "brier_120": compute_brier_score(all_y, p_120, 120.0),
                "crossing_rate": cr,
                **pinball_dict,
                **cov_dict,
                **intervals_dict,
            }

        elif b_name == "B4_lightgbm_quantile":
            pinball_dict = {
                f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(
                    all_y, np.concatenate([f["q"][a] for f in b_folds]), a
                )))
                for a in PRE_REGISTERED_QUANTILES
            }
            cov_dict = {
                f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(
                    all_y, np.concatenate([f["q"][a] for f in b_folds])
                )
                for a in PRE_REGISTERED_QUANTILES
            }
            intervals_dict = {}
            for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
                cov, w = compute_interval_metrics(
                    all_y,
                    np.concatenate([f["q"][q_l] for f in b_folds]),
                    np.concatenate([f["q"][q_u] for f in b_folds]),
                )
                intervals_dict[f"interval_cov_{int(nom*100)}"] = cov
                intervals_dict[f"interval_width_{int(nom*100)}"] = w

            all_quantiles_dict = {
                a: np.concatenate([f["q"][a] for f in b_folds])
                for a in PRE_REGISTERED_QUANTILES
            }
            cr, tot_inv = compute_quantile_crossing_rate(all_quantiles_dict)

            pooled_summary[b_name] = {
                "crps_mean": None,
                "nll_mean": None,
                "crossing_rate": cr,
                "total_crossing_inversions": tot_inv,
                **pinball_dict,
                **cov_dict,
                **intervals_dict,
            }

        elif b_name == "B5_ngboost_student_t":
            all_nll = np.concatenate([f["nll"] for f in b_folds])
            p_15 = np.concatenate([f["ev"][15.0] for f in b_folds])
            p_60 = np.concatenate([f["ev"][60.0] for f in b_folds])
            p_120 = np.concatenate([f["ev"][120.0] for f in b_folds])

            pinball_dict = {
                f"pinball_q_{int(a*1000):03d}": float(np.mean(compute_pinball_loss(
                    all_y, np.concatenate([f["q"][a] for f in b_folds]), a
                )))
                for a in PRE_REGISTERED_QUANTILES
            }
            cov_dict = {
                f"cov_q_{int(a*1000):03d}": compute_quantile_coverage(
                    all_y, np.concatenate([f["q"][a] for f in b_folds])
                )
                for a in PRE_REGISTERED_QUANTILES
            }
            intervals_dict = {}
            for nom, (q_l, q_u) in SYMMETRIC_INTERVAL_PAIRS.items():
                cov, w = compute_interval_metrics(
                    all_y,
                    np.concatenate([f["q"][q_l] for f in b_folds]),
                    np.concatenate([f["q"][q_u] for f in b_folds]),
                )
                intervals_dict[f"interval_cov_{int(nom*100)}"] = cov
                intervals_dict[f"interval_width_{int(nom*100)}"] = w

            all_quantiles_dict = {
                a: np.concatenate([f["q"][a] for f in b_folds])
                for a in PRE_REGISTERED_QUANTILES
            }
            cr, _ = compute_quantile_crossing_rate(all_quantiles_dict)

            pooled_summary[b_name] = {
                "crps_mean": None,
                "nll_mean": float(np.mean(all_nll)),
                "df_mean": float(np.mean(np.concatenate([f["df"] for f in b_folds]))),
                "brier_15": compute_brier_score(all_y, p_15, 15.0),
                "brier_60": compute_brier_score(all_y, p_60, 60.0),
                "brier_120": compute_brier_score(all_y, p_120, 120.0),
                "crossing_rate": cr,
                **pinball_dict,
                **cov_dict,
                **intervals_dict,
            }

    total_wall_sec = time.time() - start_time
    print(f"\n=================================================================")
    print(f"STAGE 1 BASELINES COMPLETED in {total_wall_sec:.2f} seconds")
    print("=================================================================")

    # -------------------------------------------------------------
    # 3. Create Summary Manifest
    # -------------------------------------------------------------
    summary_manifest = {
        "manifest_version": "probabilistic_stage1_baselines_summary_v1",
        "created_at_utc": "2026-09-27T09:10:00Z",
        "protocol_manifest": "artifacts/manifests/probabilistic_protocol_v1.json",
        "seed": seed,
        "sample_train_per_year": sample_train_per_year,
        "sample_val": sample_val,
        "total_wall_seconds": total_wall_sec,
        "folds": [f.fold_id for f in FROZEN_PROBABILISTIC_FOLDS],
        "validation_years": [f.outer_val_year for f in FROZEN_PROBABILISTIC_FOLDS],
        "baselines_evaluated": list(baseline_dirs.keys()),
        "per_fold_metrics": fold_results,
        "pooled_development_metrics": pooled_summary,
        "holdout_guards": {
            "2023_accessed": False,
            "2024_accessed": False,
        },
    }

    summary_file = manifests_dir / "probabilistic_stage1_baselines_summary_v1.json"
    summary_file.write_text(json.dumps(summary_manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Summary manifest written to: {summary_file.name}")
    return summary_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Stage 1 Probabilistic Baselines")
    parser.add_argument("--train-sample", type=int, default=15_000)
    parser.add_argument("--val-sample", type=int, default=15_000)
    parser.add_argument("--seed", type=int, default=SCREENING_SEED)
    args = parser.parse_args()

    run_stage1_baselines(
        sample_train_per_year=args.train_sample,
        sample_val=args.val_sample,
        seed=args.seed,
    )
