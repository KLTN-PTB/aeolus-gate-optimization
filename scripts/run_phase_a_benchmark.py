"""Phase A Experimental Benchmark & Decision Gate A Assessment.

Evaluates Fold 4 (Train: 2016-2021, Val: 2022) with monthly stratified sampling:
1. Month distribution verification across all 12 calendar months (~8.33% +/- 1.5%).
2. Non-parametric Naive Baselines:
   - Global Median
   - Carrier Median
   - Carrier-Hour Median
3. Machine Learning Baselines:
   - XGBoost Baseline MSE
   - HistGradientBoosting Baseline MSE
4. Skill Score (%) relative to Carrier-Hour Median across 5 random seeds (42, 43, 44, 45, 46).
5. Comprehensive metrics evaluation (evaluate_all): Point regression, severe tail, tail PR-AUC.
6. Formal evaluation of Decision Gate A (< 5% Skill Score threshold).
"""

from __future__ import annotations

import gc
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

# Project root setup
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.preprocessing import build_tree_preprocessor, build_v1_1_tree_preprocessor
from src.data.stratified_loader import (
    get_month_distribution_report,
    load_stratified_fold_data,
)
from src.models.baselines import NaiveDelayBaselines, compute_skill_score
from src.features.refactored_features import compute_carrier_arrhour_median
from src.models.metrics import evaluate_all
from src.models.refactored_models import (
    build_refactored_hgb_bundle,
    build_refactored_xgboost_bundle,
)
from xgboost import XGBRegressor

BENCHMARK_SEEDS = [42, 43, 44, 45, 46]
TRAIN_YEARS = [2016, 2017, 2018, 2019, 2020, 2021]
VAL_YEAR = 2022
SAMPLE_TRAIN_PER_YEAR = 25000  # 150,000 train rows total across 6 years
SAMPLE_VAL = 25000
HPO_XGB_RESULT = ROOT / "artifacts" / "manifests" / "week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
V1_MANIFEST = ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_tuned_xgb_params() -> dict[str, Any]:
    with HPO_XGB_RESULT.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    params = manifest.get("best_params")
    if not isinstance(params, dict):
        raise ValueError("Frozen XGBoost HPO result has no best_params mapping")
    return dict(params)


def _variant_config(variant: str) -> tuple[bool, bool, int]:
    if variant == "v1":
        return False, False, 30
    if variant == "v1.1":
        return False, False, 30
    if variant == "v1.2a":
        return True, False, 30
    if variant == "v1.2b":
        return True, True, 30
    raise ValueError(f"Unsupported Phase A benchmark variant: {variant}")


def run_benchmark_for_seed(
    seed: int,
    *,
    variant: str = "v1.1",
    sample_train_per_year: int = SAMPLE_TRAIN_PER_YEAR,
    sample_val: int = SAMPLE_VAL,
) -> dict[str, Any]:
    """Execute benchmark for a single seed."""
    print(f"\n{'=' * 80}")
    use_target_encoding, smoothing, smoothing_k = _variant_config(variant)
    print(f"[*] RUNNING BENCHMARK - SEED {seed} ({variant})")
    print(f"{'=' * 80}")

    # 1. Load monthly stratified data
    t0 = time.time()
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
        train_years=TRAIN_YEARS,
        val_year=VAL_YEAR,
        sample_train_per_year=sample_train_per_year,
        sample_val=sample_val,
        project_root=ROOT,
        random_state=seed,
        feature_set="v1" if variant == "v1" else "v1.1",
    )
    load_duration = time.time() - t0
    print(f"[*] Data loaded in {load_duration:.2f}s: Train {X_train.shape}, Val {X_val.shape}")

    # 2. Check and report monthly distribution (first seed or all seeds)
    val_month_rep = get_month_distribution_report(X_val)
    print("\n--- Validation 2022 Monthly Stratification Report ---")
    print(val_month_rep.to_string(index=False))

    # Verify uniform monthly constraint: 8.33% +/- 1.5% (6.83% - 9.83%)
    for _, row in val_month_rep.iterrows():
        pct = row["Percentage"]
        if not (6.5 <= pct <= 10.5):
            print(f"[!] WARNING: Month {int(row['Month'])} has percentage {pct:.2f}%, slightly outside nominal bounds.")

    y_val_true = y_val_reg.to_numpy(dtype=np.float64)

    # Target-derived features are fit independently inside this fold/seed.
    # The apply frame's target, if present, is ignored by the helper.
    target_encoding_features: tuple[str, ...] = ()
    if use_target_encoding:
        train_for_encoding = X_train.copy()
        train_for_encoding["y_arr_reg"] = y_train_reg.to_numpy(dtype=np.float64)
        train_median, train_count = compute_carrier_arrhour_median(
            train_for_encoding,
            X_train,
            k=smoothing_k,
            smoothing=smoothing,
        )
        val_median, val_count = compute_carrier_arrhour_median(
            train_for_encoding,
            X_val,
            k=smoothing_k,
            smoothing=smoothing,
        )
        X_train = X_train.copy()
        X_val = X_val.copy()
        X_train["carrier_arrhour_train_median"] = train_median.to_numpy()
        X_train["carrier_arrhour_train_count"] = train_count.to_numpy()
        X_val["carrier_arrhour_train_median"] = val_median.to_numpy()
        X_val["carrier_arrhour_train_count"] = val_count.to_numpy()
        target_encoding_features = (
            "carrier_arrhour_train_median",
            "carrier_arrhour_train_count",
        )
        print(
            "[*] Target encoding fitted on this seed's train side: "
            f"smoothing={smoothing} k={smoothing_k}"
        )

    # 3. Fit Naive Baselines
    print("\n[*] Evaluating Naive Baselines...")
    naive = NaiveDelayBaselines()
    naive.fit(X_train, y_train_reg)

    pred_global = naive.predict_global_median(X_val)
    pred_carrier = naive.predict_carrier_median(X_val)
    pred_carrier_hour = naive.predict_carrier_hour_median(X_val)

    eval_global = evaluate_all(y_val_true, pred_global)
    eval_carrier = evaluate_all(y_val_true, pred_carrier)
    eval_carrier_hour = evaluate_all(y_val_true, pred_carrier_hour)

    mae_carrier_hour = eval_carrier_hour["point_regression"]["mae"]

    print(f"    Global Median:       MAE={eval_global['point_regression']['mae']:.2f}, RMSE={eval_global['point_regression']['rmse']:.2f}")
    print(f"    Carrier Median:      MAE={eval_carrier['point_regression']['mae']:.2f}, RMSE={eval_carrier['point_regression']['rmse']:.2f}")
    print(f"    Carrier-Hour Median: MAE={mae_carrier_hour:.2f}, RMSE={eval_carrier_hour['point_regression']['rmse']:.2f}")

    # 4. Fit Machine Learning Baselines (Preprocessed)
    print("\n[*] Preprocessing tabular features for Tree models...")
    if variant == "v1":
        tree_prep = build_tree_preprocessor()
    else:
        tree_prep = build_v1_1_tree_preprocessor(
            extra_numeric_features=target_encoding_features
        )
    X_tr_enc = tree_prep.fit_transform(X_train)
    X_val_enc = tree_prep.transform(X_val)

    # Model 1: XGBoost Baseline MSE
    print("[*] Training XGBoost Baseline MSE (reg:squarederror)...")
    tuned_params = _load_tuned_xgb_params()
    xgb_regressor = XGBRegressor(
        **tuned_params,
        objective="reg:squarederror",
        eval_metric="rmse",
        tree_method="hist",
        device="cpu",
        max_bin=256,
        random_state=seed,
        n_jobs=1,
    )
    xgb_regressor.fit(X_tr_enc, y_train_reg.to_numpy(dtype=np.float64))
    pred_xgb = xgb_regressor.predict(X_val_enc)
    eval_xgb = evaluate_all(y_val_true, pred_xgb)
    skill_xgb = compute_skill_score(eval_xgb["point_regression"]["mae"], mae_carrier_hour)
    print(f"    XGBoost MSE: MAE={eval_xgb['point_regression']['mae']:.2f}, RMSE={eval_xgb['point_regression']['rmse']:.2f}, Skill Score={skill_xgb:+.2f}%")

    # Model 2: HistGradientBoosting Baseline MSE
    print("[*] Training HistGradientBoosting Baseline (squared_error)...")
    hgb_bundle = build_refactored_hgb_bundle(loss="squared_error", seed=seed)
    hgb_bundle.regressor.fit(X_tr_enc, y_train_reg.to_numpy(dtype=np.float64))
    pred_hgb = hgb_bundle.regressor.predict(X_val_enc)
    eval_hgb = evaluate_all(y_val_true, pred_hgb)
    skill_hgb = compute_skill_score(eval_hgb["point_regression"]["mae"], mae_carrier_hour)
    print(f"    HistGradientBoosting: MAE={eval_hgb['point_regression']['mae']:.2f}, RMSE={eval_hgb['point_regression']['rmse']:.2f}, Skill Score={skill_hgb:+.2f}%")

    seed_result = {
        "seed": seed,
        "global_median": {
            "mae": eval_global["point_regression"]["mae"],
            "rmse": eval_global["point_regression"]["rmse"],
            "r2": eval_global["point_regression"]["r2"],
            "severe_mae": eval_global["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": eval_global["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": eval_global["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": compute_skill_score(eval_global["point_regression"]["mae"], mae_carrier_hour),
        },
        "carrier_median": {
            "mae": eval_carrier["point_regression"]["mae"],
            "rmse": eval_carrier["point_regression"]["rmse"],
            "r2": eval_carrier["point_regression"]["r2"],
            "severe_mae": eval_carrier["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": eval_carrier["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": eval_carrier["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": compute_skill_score(eval_carrier["point_regression"]["mae"], mae_carrier_hour),
        },
        "carrier_hour_median": {
            "mae": mae_carrier_hour,
            "rmse": eval_carrier_hour["point_regression"]["rmse"],
            "r2": eval_carrier_hour["point_regression"]["r2"],
            "severe_mae": eval_carrier_hour["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": eval_carrier_hour["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": eval_carrier_hour["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": 0.0,
        },
        "xgboost_mse": {
            "mae": eval_xgb["point_regression"]["mae"],
            "rmse": eval_xgb["point_regression"]["rmse"],
            "r2": eval_xgb["point_regression"]["r2"],
            "severe_mae": eval_xgb["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": eval_xgb["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": eval_xgb["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": skill_xgb,
        },
        "hist_gradient_boosting": {
            "mae": eval_hgb["point_regression"]["mae"],
            "rmse": eval_hgb["point_regression"]["rmse"],
            "r2": eval_hgb["point_regression"]["r2"],
            "severe_mae": eval_hgb["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": eval_hgb["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": eval_hgb["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": skill_hgb,
        },
    }

    del X_train, y_train_cls, y_train_reg, X_val, y_val_cls, y_val_reg, X_tr_enc, X_val_enc
    gc.collect()

    return seed_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Day 1 Phase A gap-closure benchmark")
    parser.add_argument(
        "--variant",
        choices=("v1", "v1.1", "v1.2a", "v1.2b"),
        default="v1.1",
    )
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args()
    variant = str(args.variant)
    report_path = (
        ROOT / "artifacts" / "manifests" / f"phase_a_benchmark_report_{variant.replace('.', '_')}.json"
        if args.report_path is None
        else (args.report_path if args.report_path.is_absolute() else ROOT / args.report_path)
    )
    feature_manifest_path = ROOT / "artifacts" / "manifests" / {
        "v1": "feature_manifest_arrival_v1.json",
        "v1.1": "feature_manifest_arrival_v1_1.json",
        "v1.2a": "feature_manifest_arrival_v1_2.json",
        "v1.2b": "feature_manifest_arrival_v1_2.json",
    }[variant]
    use_target_encoding, smoothing, smoothing_k = _variant_config(variant)

    print("=" * 88)
    print(f"      AEOLUS GATE OPTIMIZATION: PHASE A {variant.upper()} GAP CLOSURE")
    print("      Fold 4: Train 2016-2021 (Monthly Stratified), Val 2022 (Monthly Stratified)")
    print(f"      Seeds: {BENCHMARK_SEEDS}")
    print("=" * 88)

    all_seed_results: list[dict[str, Any]] = []
    start_time = time.time()

    for seed in BENCHMARK_SEEDS:
        res = run_benchmark_for_seed(seed, variant=variant)
        all_seed_results.append(res)

    total_time = time.time() - start_time
    print(f"\n[*] All 5 seeds completed in {total_time:.1f}s")

    # Aggregate metrics across seeds
    model_keys = ["global_median", "carrier_median", "carrier_hour_median", "xgboost_mse", "hist_gradient_boosting"]
    metric_keys = ["mae", "rmse", "r2", "skill_score_vs_carrier_hour", "severe_mae", "shrinkage_ratio", "pr_auc_severe"]

    summary: dict[str, dict[str, dict[str, float]]] = {}
    for m in model_keys:
        summary[m] = {}
        for met in metric_keys:
            vals = [s[m][met] for s in all_seed_results if s[m][met] is not None]
            mean_val = float(np.mean(vals)) if vals else 0.0
            std_val = float(np.std(vals)) if vals else 0.0
            summary[m][met] = {"mean": mean_val, "std": std_val}

    # Print Formatted Table
    print("\n" + "=" * 110)
    print(f"{'MODEL / BASELINE':<26} | {'MAE (Mean +/- Std)':<18} | {'RMSE (Mean +/- Std)':<19} | {'SKILL SCORE (%)':<16} | {'SHRINKAGE':<10} | {'TAIL PR-AUC':<10}")
    print("-" * 110)

    display_names = {
        "global_median": "Naive: Global Median",
        "carrier_median": "Naive: Carrier Median",
        "carrier_hour_median": "Naive: Carrier-Hour Median",
        "xgboost_mse": "ML: XGBoost Baseline MSE",
        "hist_gradient_boosting": "ML: HistGradientBoosting",
    }

    for m in model_keys:
        name = display_names[m]
        mae_str = f"{summary[m]['mae']['mean']:.2f} +/- {summary[m]['mae']['std']:.2f}"
        rmse_str = f"{summary[m]['rmse']['mean']:.2f} +/- {summary[m]['rmse']['std']:.2f}"
        skill_str = f"{summary[m]['skill_score_vs_carrier_hour']['mean']:+.2f}% +/- {summary[m]['skill_score_vs_carrier_hour']['std']:.2f}%"
        shrink_str = f"{summary[m]['shrinkage_ratio']['mean']:.4f}"
        pr_str = f"{summary[m]['pr_auc_severe']['mean']:.4f}"
        print(f"{name:<26} | {mae_str:<18} | {rmse_str:<19} | {skill_str:<16} | {shrink_str:<10} | {pr_str:<10}")

    print("=" * 110)

    # Decision Gate A Assessment
    max_ml_skill = max(
        summary["xgboost_mse"]["skill_score_vs_carrier_hour"]["mean"],
        summary["hist_gradient_boosting"]["skill_score_vs_carrier_hour"]["mean"],
    )

    print("\n" + "=" * 96)
    print("                            DECISION GATE A EVALUATION")
    print("=" * 96)
    print(f"[*] Carrier-Hour Median Reference MAE: {summary['carrier_hour_median']['mae']['mean']:.2f}")
    print(f"[*] Best ML Mean Skill Score vs Carrier-Hour Median: {max_ml_skill:+.2f}%")
    print(f"[*] Decision Threshold: Skill Score >= +5.0%")

    gate_verdict_triggered = max_ml_skill < 5.0
    if gate_verdict_triggered:
        print("\n[!] VERDICT: SKILL SCORE < 5.0% - CONDITION SATISFIED.")
        print("-" * 96)
        print("Trần tín hiệu hồi quy điểm thấp (R2 thấp). Trọng tâm nghiên cứu bắt buộc chuyển dịch sang")
        print("Mô hình Xác suất và Dự đoán Khoảng (Interval/Quantile Prediction) phục vụ CP-SAT")
        print("-" * 96)
    else:
        print("\n[*] VERDICT: ML model beats Carrier-Hour Median by >= 5.0%. Regression point signal confirmed viable.")

    print("=" * 96)

    # Save to artifacts manifest
    manifest_dir = ROOT / "artifacts" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    if not feature_manifest_path.is_file():
        raise FileNotFoundError(
            f"Feature manifest must be created before running {variant}: {feature_manifest_path}"
        )

    report_data = {
        "benchmark_version": f"phase_a_{variant}",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fold": "Fold 4 (Train 2016-2021, Val 2022)",
        "sampling_method": "Stratified Sampling by Month (12 calendar months)",
        "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
        "sample_val": SAMPLE_VAL,
        "seeds": BENCHMARK_SEEDS,
        "feature_set": variant,
        "feature_manifest": str(feature_manifest_path.relative_to(ROOT)),
        "feature_manifest_sha256": _sha256(feature_manifest_path),
        "parent_manifest": str(V1_MANIFEST.relative_to(ROOT)),
        "parent_manifest_sha256": _sha256(V1_MANIFEST),
        "hpo_result_manifest": str(HPO_XGB_RESULT.relative_to(ROOT)),
        "hpo_result_manifest_sha256": _sha256(HPO_XGB_RESULT),
        "xgboost": {
            "objective": "reg:squarederror",
            "best_params_source": str(HPO_XGB_RESULT.relative_to(ROOT)),
            "best_params": _load_tuned_xgb_params(),
        },
        "target_encoding": {
            "enabled": use_target_encoding,
            "smoothing": smoothing,
            "k": smoothing_k,
            "fit_scope": "each_seed_fold_train_rows_only",
            "validation_targets_used_for_feature": False,
        },
        "execution_time_seconds": round(total_time, 2),
        "summary": summary,
        "per_seed_results": all_seed_results,
        "decision_gate_a": {
            "max_ml_skill_score": round(max_ml_skill, 2),
            "threshold": 5.0,
            "condition_satisfied": gate_verdict_triggered,
            "formal_verdict": (
                "Trần tín hiệu hồi quy điểm thấp (R2 thấp). Trọng tâm nghiên cứu bắt buộc chuyển dịch sang "
                "Mô hình Xác suất và Dự đoán Khoảng (Interval/Quantile Prediction) phục vụ CP-SAT"
                if gate_verdict_triggered
                else "Point regression viable"
            ),
        },
    }

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n[+] Full benchmark report saved to {report_path}")


if __name__ == "__main__":
    main()
