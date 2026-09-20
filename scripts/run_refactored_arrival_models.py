"""Refactored Arrival Models Execution & Benchmark Script (Protocol V2 + Phase 3).

Evaluates:
1. Baseline MSE XGBoost (L2 Loss)
2. Refactored Pseudo-Huber XGBoost (unweighted)
3. Refactored Pseudo-Huber XGBoost (with Temporal Sample Weighting)
4. Refactored HistGradientBoosting (Absolute Error, with Temporal Sample Weighting)
5. Refactored Quantile XGBoost (alpha=0.75, with Temporal Sample Weighting)
6. Hurdle Delay Predictor (Soft Gated, with Temporal Sample Weighting)
7. Hurdle Delay Predictor (Hard Gated threshold=0.30, with Temporal Sample Weighting)

Computes point predictions and 75th percentile safety buffers for gate assignment.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.access_guard import assert_data_access_allowed
from src.data.preprocessing import iter_arrival_development_batches
from src.data.refactored_preprocessing import (
    build_refactored_linear_preprocessor,
    build_refactored_tree_preprocessor,
)
from src.features.refactored_features import (
    APPROVED_PREDICTOR_COLUMNS_V2,
    prepare_arrival_features_v2,
)
from src.models.hurdle_inference import HurdleDelayPredictor
from src.models.metrics import compute_stratified_regression_metrics
from src.models.refactored_models import (
    TwoStageHurdleRegressor,
    build_refactored_hgb_bundle,
    build_refactored_linear_bundle,
    build_refactored_rf_bundle,
    build_refactored_xgboost_bundle,
)
from src.models.temporal_weighting import compute_temporal_sample_weights
from src.models.week5_xgboost import XGBClassifier, XGBRegressor


def slice_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    strat = compute_stratified_regression_metrics(y_true, y_pred)
    d = strat.to_dict()
    return {
        "Overall": {
            "MAE": round(d["overall"]["mae"], 2),
            "RMSE": round(d["overall"]["rmse"], 2),
            "Bias": round(d["overall"]["mean_bias"], 2),
        },
        "Early/On-time (<15m)": {
            "MAE": round(d["early_on_time"]["mae"], 2),
            "RMSE": round(d["early_on_time"]["rmse"], 2),
            "Bias": round(d["early_on_time"]["mean_bias"], 2),
        },
        "Moderate (15-59m)": {
            "MAE": round(d["moderate_delay"]["mae"], 2),
            "RMSE": round(d["moderate_delay"]["rmse"], 2),
            "Bias": round(d["moderate_delay"]["mean_bias"], 2),
        },
        "Severe (>=60m)": {
            "MAE": round(d["severe_delay"]["mae"], 2),
            "RMSE": round(d["severe_delay"]["rmse"], 2),
            "Bias": round(d["severe_delay"]["mean_bias"], 2),
            "Mean_True": round(d["severe_delay"]["mean_true"], 2),
            "Mean_Pred": round(d["severe_delay"]["mean_pred"], 2),
            "Shrinkage_Ratio": round(strat.shrinkage_ratio, 4),
            "Collapse_Warning": strat.prediction_collapse_warning,
        },
        "Shrinkage_Ratio": round(strat.shrinkage_ratio, 4),
        "Collapse_Warning": strat.prediction_collapse_warning,
    }


def load_fold_data(
    train_years: list[int],
    val_year: int,
    sample_train_per_year: int = 35000,
    sample_val: int = 40000,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, np.ndarray, pd.DataFrame, pd.Series, pd.Series]:
    train_x_list, train_cls_list, train_reg_list, train_year_list = [], [], [], []

    print(f"[*] Loading Train data for years {train_years} (sample {sample_train_per_year}/yr)...")
    for y in train_years:
        assert_data_access_allowed(y, "development")
        batches = []
        for batch in iter_arrival_development_batches(y, project_root=ROOT, batch_size=8192):
            batches.append(batch)
            if sum(len(b) for b in batches) >= sample_train_per_year * 2:
                break
        raw_df = pd.concat(batches, ignore_index=True)
        if len(raw_df) > sample_train_per_year:
            raw_df = raw_df.sample(n=sample_train_per_year, random_state=42)

        prep = prepare_arrival_features_v2(raw_df)
        train_x_list.append(prep.X)
        train_cls_list.append(prep.y_arr_cls)
        train_reg_list.append(prep.y_arr_reg)
        train_year_list.append(np.full(len(prep.X), y, dtype=np.int32))
        del raw_df, batches, prep
        gc.collect()

    X_train = pd.concat(train_x_list, ignore_index=True)
    y_train_cls = pd.concat(train_cls_list, ignore_index=True)
    y_train_reg = pd.concat(train_reg_list, ignore_index=True)
    train_years_vec = np.concatenate(train_year_list)

    print(f"[*] Loading Validation data for year {val_year} (sample {sample_val})...")
    assert_data_access_allowed(val_year, "development")
    val_batches = []
    for batch in iter_arrival_development_batches(val_year, project_root=ROOT, batch_size=8192):
        val_batches.append(batch)
        if sum(len(b) for b in val_batches) >= sample_val * 2:
            break
    val_raw = pd.concat(val_batches, ignore_index=True)
    if len(val_raw) > sample_val:
        val_raw = val_raw.sample(n=sample_val, random_state=42)

    val_prep = prepare_arrival_features_v2(val_raw)
    X_val = val_prep.X
    y_val_cls = val_prep.y_arr_cls
    y_val_reg = val_prep.y_arr_reg

    return X_train, y_train_cls, y_train_reg, train_years_vec, X_val, y_val_cls, y_val_reg


def main():
    print("=" * 96)
    print("AEOLUS GATE OPTIMIZATION: PHASE 3 REFACTORED MODEL BENCHMARK")
    print("=" * 96)

    out_dir = ROOT / "artifacts" / "predictions" / "refactored"
    out_dir.mkdir(parents=True, exist_ok=True)

    train_years = [2016, 2017, 2018, 2019, 2020, 2021]
    val_year = 2022
    X_train, y_train_cls, y_train_reg, train_years_vec, X_val, y_val_cls, y_val_reg = (
        load_fold_data(train_years, val_year, sample_train_per_year=35000, sample_val=40000)
    )
    print(f"[*] Train shape: {X_train.shape}, Val shape: {X_val.shape}")
    assert "calendar_year" not in X_train.columns, "calendar_year must not be present in V2 features!"

    print("[*] Computing Temporal Sample Weights...")
    train_weights = compute_temporal_sample_weights(train_years_vec, target_val_year=val_year)
    print(f"    Min weight: {train_weights.min():.2f} (COVID 2020: 0.50), Max weight: {train_weights.max():.2f} (2021: 1.00)")

    print("[*] Fitting Refactored Preprocessors...")
    tree_prep = build_refactored_tree_preprocessor()
    X_train_tree = tree_prep.fit_transform(X_train)
    X_val_tree = tree_prep.transform(X_val)

    y_t_cls = y_train_cls.values
    y_t_reg = y_train_reg.values
    y_v_reg = y_val_reg.values

    results = {}

    # Model 1: Baseline MSE (unweighted)
    print("\n--- [Model 1] Baseline XGBoost (MSE Loss, L2 penalty, Unweighted) ---")
    t0 = time.time()
    xgb_base = XGBRegressor(
        n_estimators=128, learning_rate=0.05, max_depth=6, subsample=0.8,
        colsample_bytree=0.8, objective="reg:squarederror", tree_method="hist",
        device="cpu", random_state=42, n_jobs=1
    )
    xgb_base.fit(X_train_tree, y_t_reg)
    p_xgb_base = xgb_base.predict(X_val_tree)
    results["XGBoost_Baseline_MSE"] = slice_metrics(y_v_reg, p_xgb_base)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['XGBoost_Baseline_MSE']['Overall']['MAE']} | Severe MAE: {results['XGBoost_Baseline_MSE']['Severe (>=60m)']['MAE']}")

    # Model 2: Refactored Pseudo-Huber (unweighted)
    print("\n--- [Model 2] Refactored XGBoost (Pseudo-Huber Loss, delta=15.0, Unweighted) ---")
    t0 = time.time()
    xgb_huber = XGBRegressor(
        n_estimators=128, learning_rate=0.05, max_depth=6, subsample=0.8,
        colsample_bytree=0.8, objective="reg:pseudohubererror", eval_metric="mphe",
        huber_slope=15.0, tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    xgb_huber.fit(X_train_tree, y_t_reg)
    p_xgb_huber = xgb_huber.predict(X_val_tree)
    results["XGBoost_Refactored_Huber"] = slice_metrics(y_v_reg, p_xgb_huber)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['XGBoost_Refactored_Huber']['Overall']['MAE']} | Severe MAE: {results['XGBoost_Refactored_Huber']['Severe (>=60m)']['MAE']}")

    # Model 3: Refactored Pseudo-Huber with Temporal Sample Weighting
    print("\n--- [Model 3] Refactored XGBoost (Pseudo-Huber + Temporal Weights) ---")
    t0 = time.time()
    xgb_huber_w = XGBRegressor(
        n_estimators=128, learning_rate=0.05, max_depth=6, subsample=0.8,
        colsample_bytree=0.8, objective="reg:pseudohubererror", eval_metric="mphe",
        huber_slope=15.0, tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    xgb_huber_w.fit(X_train_tree, y_t_reg, sample_weight=train_weights)
    p_xgb_huber_w = xgb_huber_w.predict(X_val_tree)
    results["XGBoost_Huber_Weighted"] = slice_metrics(y_v_reg, p_xgb_huber_w)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['XGBoost_Huber_Weighted']['Overall']['MAE']} | Severe MAE: {results['XGBoost_Huber_Weighted']['Severe (>=60m)']['MAE']}")

    # Model 4: HistGradientBoosting (Absolute Error + Temporal Weights)
    print("\n--- [Model 4] Refactored HistGradientBoosting (Absolute Error + Temporal Weights) ---")
    t0 = time.time()
    hgb_bundle = build_refactored_hgb_bundle(loss="absolute_error", seed=42)
    hgb_bundle.regressor.fit(X_train_tree, y_t_reg, sample_weight=train_weights)
    p_hgb_w = hgb_bundle.regressor.predict(X_val_tree)
    results["HistGradientBoosting_Absolute_Weighted"] = slice_metrics(y_v_reg, p_hgb_w)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['HistGradientBoosting_Absolute_Weighted']['Overall']['MAE']} | Severe MAE: {results['HistGradientBoosting_Absolute_Weighted']['Severe (>=60m)']['MAE']}")

    # Model 5: Refactored XGBoost (Quantile Loss alpha=0.75 + Temporal Weights)
    print("\n--- [Model 5] Refactored XGBoost (Quantile alpha=0.75 + Temporal Weights) ---")
    t0 = time.time()
    xgb_quantile = XGBRegressor(
        n_estimators=128, learning_rate=0.05, max_depth=6, subsample=0.8,
        colsample_bytree=0.8, objective="reg:quantileerror", eval_metric="mae",
        quantile_alpha=0.75, tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    xgb_quantile.fit(X_train_tree, y_t_reg, sample_weight=train_weights)
    p_xgb_quantile = xgb_quantile.predict(X_val_tree)
    results["XGBoost_Quantile_075_Weighted"] = slice_metrics(y_v_reg, p_xgb_quantile)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['XGBoost_Quantile_075_Weighted']['Overall']['MAE']} | Severe MAE: {results['XGBoost_Quantile_075_Weighted']['Severe (>=60m)']['MAE']}")

    # Model 6: Hurdle Model (Soft Gated + Temporal Weights)
    print("\n--- [Model 6] Hurdle Delay Predictor (Soft Gated + Temporal Weights) ---")
    t0 = time.time()
    clf_soft = XGBClassifier(
        n_estimators=100, learning_rate=0.08, max_depth=5, scale_pos_weight=5.0,
        tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    reg_soft = XGBRegressor(
        n_estimators=100, learning_rate=0.08, max_depth=5, objective="reg:pseudohubererror",
        huber_slope=15.0, tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    hurdle_soft = HurdleDelayPredictor(
        classifier_bundle=clf_soft,
        regressor_bundle=reg_soft,
        gating_mode="soft",
        threshold=0.30,
    )
    hurdle_soft.fit(X_train_tree, y_t_reg, sample_weight=train_weights)
    p_hurdle_soft = hurdle_soft.predict(X_val_tree)
    results["Hurdle_Soft_Gated_Weighted"] = slice_metrics(y_v_reg, p_hurdle_soft)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['Hurdle_Soft_Gated_Weighted']['Overall']['MAE']} | Severe MAE: {results['Hurdle_Soft_Gated_Weighted']['Severe (>=60m)']['MAE']}")

    # Model 7: Hurdle Model (Hard Gated threshold=0.30 + Temporal Weights)
    print("\n--- [Model 7] Hurdle Delay Predictor (Hard Gated threshold=0.30 + Temporal Weights) ---")
    t0 = time.time()
    clf_hard = XGBClassifier(
        n_estimators=100, learning_rate=0.08, max_depth=5, scale_pos_weight=5.0,
        tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    reg_hard = XGBRegressor(
        n_estimators=100, learning_rate=0.08, max_depth=5, objective="reg:pseudohubererror",
        huber_slope=15.0, tree_method="hist", device="cpu", random_state=42, n_jobs=1
    )
    hurdle_hard = HurdleDelayPredictor(
        classifier_bundle=clf_hard,
        regressor_bundle=reg_hard,
        gating_mode="hard",
        threshold=0.30,
    )
    hurdle_hard.fit(X_train_tree, y_t_reg, sample_weight=train_weights)
    p_hurdle_hard, p_quantile_buffer = hurdle_hard.predict_point_and_buffer(X_val_tree, alpha=0.75)
    results["Hurdle_Hard_Gated_Weighted"] = slice_metrics(y_v_reg, p_hurdle_hard)
    print(f"    Trained in {time.time()-t0:.1f}s | Overall MAE: {results['Hurdle_Hard_Gated_Weighted']['Overall']['MAE']} | Severe MAE: {results['Hurdle_Hard_Gated_Weighted']['Severe (>=60m)']['MAE']}")

    # Point estimate and safety buffer for downstream dispatch
    p_hurdle_point = p_hurdle_hard

    # Save OOF predictions
    oof_df = pd.DataFrame({
        "y_true": y_v_reg,
        "pred_xgb_baseline_mse": p_xgb_base,
        "pred_xgb_huber": p_xgb_huber,
        "pred_xgb_huber_weighted": p_xgb_huber_w,
        "pred_hgb_weighted": p_hgb_w,
        "pred_xgb_quantile": p_xgb_quantile,
        "pred_hurdle_soft": p_hurdle_soft,
        "pred_hurdle_hard": p_hurdle_hard,
        "pred_hurdle_point": p_hurdle_point,
        "pred_quantile_buffer": p_quantile_buffer,
    })
    table = pa.Table.from_pandas(oof_df)
    oof_file = out_dir / "refactored_comparison_fold_4.parquet"
    pq.write_table(table, oof_file)
    print(f"\n[*] Saved refactored predictions to: {oof_file}")

    # Save summary manifest
    manifest_file = ROOT / "artifacts" / "manifests" / "refactored_models_evaluation_v2.json"
    manifest_payload = {
        "evaluation_version": "refactored_models_evaluation_v2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "protocol_version": "arrival_feature_contract_v2",
        "phase": "phase_3_temporal_weighting_and_hurdle_completion",
        "fold_evaluated": "fold_4",
        "train_years": train_years,
        "validation_year": val_year,
        "results": results,
    }
    manifest_file.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    print(f"[*] Saved evaluation manifest to: {manifest_file}")

    print("\n" + "=" * 105)
    print("COMPARATIVE EVALUATION SUMMARY (FOLD 4, VALIDATION 2022 - WITH TEMPORAL SAMPLE WEIGHTS)")
    print("=" * 105)
    print(f"{'Model':<38} | {'Overall MAE':<11} | {'Overall RMSE':<12} | {'Severe MAE':<11} | {'Shrinkage':<10} | {'Collapse?':<9}")
    print("-" * 105)
    for model_name, m in results.items():
        o_mae = m["Overall"]["MAE"]
        o_rmse = m["Overall"]["RMSE"]
        s_mae = m["Severe (>=60m)"]["MAE"]
        shrinkage = m["Severe (>=60m)"]["Shrinkage_Ratio"]
        collapse = "YES" if m["Severe (>=60m)"]["Collapse_Warning"] else "NO"
        print(f"{model_name:<38} | {o_mae:<11.2f} | {o_rmse:<12.2f} | {s_mae:<11.2f} | {shrinkage:<10.4f} | {collapse:<9}")
    print("=" * 105)


if __name__ == "__main__":
    main()
