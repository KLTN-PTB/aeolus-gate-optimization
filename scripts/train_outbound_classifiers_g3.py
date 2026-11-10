"""Authoritative Outbound Classification & Probability Evaluation Pipeline (Gate G3 Remediation).

Protocol: Aeolus Predict-then-Optimize V4.1 - Phase G3
Task: Outbound Classification (Target: P(DEP_DELAY >= 15 min) at T-2h Cutoff)
Features: Exactly the 10 approved Core Departure V1 features (ORIGIN=ATL, schedule-only).
Temporal Isolation:
- Training Partition: 2021 Outbound ATL (309,488 rows)
- Calibration Partition: 2022 Outbound ATL (311,746 rows)
- Evaluation / Selection Partition: 2023 Outbound ATL (332,734 rows)
- Holdout 2024: STRICTLY UNTOUCHED

Models:
1. Constant Prevalence Baseline (Prior probability)
2. Logistic Regression Classifier (Linear, uncalibrated & calibrated)
3. XGBoost Classifier (Tree, uncalibrated & calibrated)

Outputs:
- artifacts/remediation/outbound_classification/models/
- artifacts/remediation/outbound_classification/predictions/
- artifacts/remediation/outbound_classification/metrics/
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
import xgboost as xgb

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    prepare_departure_training,
)

OUTPUT_DIR = ROOT / "artifacts" / "remediation" / "outbound_classification"
MODELS_DIR = OUTPUT_DIR / "models"
PRED_DIR = OUTPUT_DIR / "predictions"
METRICS_DIR = OUTPUT_DIR / "metrics"

for d in [OUTPUT_DIR, MODELS_DIR, PRED_DIR, METRICS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


from src.models.thesis_models import CalibratedPredictor


def compute_expected_calibration_error(y_true: np.ndarray, probas: np.ndarray, n_bins: int = 10) -> tuple[float, list[dict]]:
    """Compute Expected Calibration Error (ECE) and bin-level reliability statistics."""
    bin_limits = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n_total = len(y_true)
    bin_records = []

    for i in range(n_bins):
        lower = bin_limits[i]
        upper = bin_limits[i + 1]
        mask = (probas >= lower) & (probas < upper) if i < n_bins - 1 else (probas >= lower) & (probas <= upper)
        bin_count = int(np.sum(mask))

        if bin_count > 0:
            bin_acc = float(np.mean(y_true[mask]))
            bin_conf = float(np.mean(probas[mask]))
            weight = bin_count / n_total
            ece += weight * abs(bin_acc - bin_conf)
            bin_records.append({
                "bin_index": i + 1,
                "bin_range": [round(lower, 2), round(upper, 2)],
                "count": bin_count,
                "mean_predicted_prob": round(bin_conf, 5),
                "observed_positive_rate": round(bin_acc, 5),
                "calibration_gap": round(abs(bin_acc - bin_conf), 5),
            })
        else:
            bin_records.append({
                "bin_index": i + 1,
                "bin_range": [round(lower, 2), round(upper, 2)],
                "count": 0,
                "mean_predicted_prob": None,
                "observed_positive_rate": None,
                "calibration_gap": 0.0,
            })

    return round(float(ece), 5), bin_records


def run_outbound_classification_pipeline() -> dict[str, any]:
    print("=" * 80)
    print("AEOLUS GATE G3: OUTBOUND CLASSIFIER & PROBABILITY CALIBRATION")
    print("=" * 80)

    # 1. Load Data Partitions
    print("\n[Step 1] Loading temporal data partitions...")
    t0 = time.perf_counter()

    data_dir = ROOT / "data" / "processed" / "outbound_atl"
    df_train_raw = pq.read_table(data_dir / "year=2021").to_pandas()
    df_calib_raw = pq.read_table(data_dir / "year=2022").to_pandas()
    df_eval_raw = pq.read_table(data_dir / "year=2023").to_pandas()

    print(f"  Loaded raw partitions: Train(2021)={len(df_train_raw)}, Calib(2022)={len(df_calib_raw)}, Eval(2023)={len(df_eval_raw)} in {time.perf_counter()-t0:.2f}s")

    # 2. Prepare Features & Targets (T-2h cutoff contract)
    print("\n[Step 2] Preparing features at T-2h prediction cutoff...")
    t0 = time.perf_counter()
    batch_train = prepare_departure_training(df_train_raw)
    batch_calib = prepare_departure_training(df_calib_raw)
    batch_eval = prepare_departure_training(df_eval_raw)

    y_train = batch_train.y_dep_cls
    y_calib = batch_calib.y_dep_cls
    y_eval = batch_eval.y_dep_cls

    prev_train = float(np.mean(y_train))
    prev_calib = float(np.mean(y_calib))
    prev_eval = float(np.mean(y_eval))

    print(f"  Prevalence P(dep_delay >= 15 min): Train={prev_train:.4f}, Calib={prev_calib:.4f}, Eval={prev_eval:.4f}")
    print(f"  Feature preparation completed in {time.perf_counter()-t0:.2f}s")

    # 3. Transform Features using Preprocessors
    print("\n[Step 3] Transforming features via frozen preprocessors...")
    linear_prep = joblib.load(ROOT / "artifacts" / "dual_core" / "models" / "departure_linear_preprocessor_v1.joblib")
    tree_prep = joblib.load(ROOT / "artifacts" / "dual_core" / "models" / "departure_tree_preprocessor_v1.joblib")

    X_train_lin = linear_prep.transform(batch_train.X)
    X_calib_lin = linear_prep.transform(batch_calib.X)
    X_eval_lin = linear_prep.transform(batch_eval.X)

    X_train_tree = tree_prep.transform(batch_train.X)
    X_calib_tree = tree_prep.transform(batch_calib.X)
    X_eval_tree = tree_prep.transform(batch_eval.X)

    # 4. Train Models
    print("\n[Step 4] Training Outbound Classifiers...")
    # Model A: Logistic Regression
    t0 = time.perf_counter()
    lr = LogisticRegression(
        C=1.0,
        max_iter=100,
        solver="lbfgs",
        random_state=202601,
    )
    lr.fit(X_train_lin, y_train)
    t_train_lr = time.perf_counter() - t0
    print(f"  Trained Logistic Regression in {t_train_lr:.2f}s")

    # Model B: XGBoost Classifier
    t0 = time.perf_counter()
    xgb_clf = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.05,
        tree_method="hist",
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=202601,
        eval_metric="logloss",
    )
    xgb_clf.fit(X_train_tree, y_train)
    t_train_xgb = time.perf_counter() - t0
    print(f"  Trained XGBoost Classifier in {t_train_xgb:.2f}s")

    # 5. Calibration using 2022 Calibration Set (Pre-fit, Zero Evaluation Leakage)
    print("\n[Step 5] Fitting Probability Calibrators on 2022 development calibration split...")
    # Isotonic calibration for Logistic Regression
    cal_lr = CalibratedPredictor(base_estimator=lr, method="isotonic")
    cal_lr.fit_calibration(X_calib_lin, y_calib)

    # Sigmoid (Platt) calibration for XGBoost
    cal_xgb = CalibratedPredictor(base_estimator=xgb_clf, method="sigmoid")
    cal_xgb.fit_calibration(X_calib_tree, y_calib)
    print("  Probability calibration fit successfully.")

    # Save Models
    joblib.dump(lr, MODELS_DIR / "outbound_logistic_classifier_v1.joblib")
    joblib.dump(cal_lr, MODELS_DIR / "outbound_logistic_calibrated_v1.joblib")
    joblib.dump(xgb_clf, MODELS_DIR / "outbound_xgboost_classifier_v1.joblib")
    joblib.dump(cal_xgb, MODELS_DIR / "outbound_xgboost_calibrated_v1.joblib")
    print(f"  Saved trained classifiers to {MODELS_DIR}")

    # 6. Evaluation on 2023 Selection Dataset (N=332,734)
    print("\n[Step 6] Evaluating classifiers on 2023 Selection split (N=332,734)...")
    prob_constant = np.full(len(y_eval), prev_train)
    prob_lr_raw = lr.predict_proba(X_eval_lin)[:, 1]
    prob_lr_cal = cal_lr.predict_proba(X_eval_lin)[:, 1]
    prob_xgb_raw = xgb_clf.predict_proba(X_eval_tree)[:, 1]
    prob_xgb_cal = cal_xgb.predict_proba(X_eval_tree)[:, 1]

    models_to_eval = [
        ("constant_prevalence_baseline", prob_constant, "constant_baseline"),
        ("outbound_logistic_raw_v1", prob_lr_raw, "linear_logistic"),
        ("outbound_logistic_calibrated_v1", prob_lr_cal, "linear_logistic_isotonic"),
        ("outbound_xgboost_raw_v1", prob_xgb_raw, "xgboost_tree"),
        ("outbound_xgboost_calibrated_v1", prob_xgb_cal, "xgboost_tree_sigmoid"),
    ]

    metrics_records = []
    reliability_data = {}

    for m_id, probas, family in models_to_eval:
        roc_auc = float(roc_auc_score(y_eval, probas)) if len(np.unique(probas)) > 1 else 0.5
        pr_auc = float(average_precision_score(y_eval, probas))
        brier = float(brier_score_loss(y_eval, probas))
        eps = 1e-15
        p_clipped = np.clip(probas, eps, 1.0 - eps)
        ll = float(log_loss(y_eval, p_clipped))

        ece, bins_data = compute_expected_calibration_error(y_eval, probas, n_bins=10)
        reliability_data[m_id] = bins_data

        pred_bin = (probas >= 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_eval, pred_bin, labels=[0, 1]).ravel()
        prec = float(precision_score(y_eval, pred_bin, zero_division=0))
        rec = float(recall_score(y_eval, pred_bin, zero_division=0))
        f1 = float(f1_score(y_eval, pred_bin, zero_division=0))

        metrics_records.append({
            "task": "core_departure_classification",
            "model_id": m_id,
            "family": family,
            "evaluation_split": "development_selection_2023",
            "sample_size": len(y_eval),
            "class_prevalence": round(prev_eval, 5),
            "roc_auc": round(roc_auc, 5),
            "pr_auc": round(pr_auc, 5),
            "brier_score": round(brier, 5),
            "log_loss": round(ll, 5),
            "ece": round(ece, 5),
            "threshold": 0.5,
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
            "precision": round(prec, 5),
            "recall": round(rec, 5),
            "f1": round(f1, 5),
            "is_calibrated": bool("calibrated" in m_id),
            "beats_constant_brier": bool(brier < brier_score_loss(y_eval, prob_constant)),
            "meets_ece_target_0_05": bool(ece <= 0.05),
        })

    df_metrics = pd.DataFrame(metrics_records)
    df_metrics.to_csv(METRICS_DIR / "outbound_classification_metrics_2023.csv", index=False)
    print(f"  Exported outbound_classification_metrics_2023.csv")

    with open(METRICS_DIR / "reliability_diagrams_2023.json", "w", encoding="utf-8") as f:
        json.dump(reliability_data, f, indent=2)
    print(f"  Exported reliability_diagrams_2023.json")

    # Export Predictions Parquet (N=332,734)
    df_pred_out = pd.DataFrame({
        "flight_key": batch_eval.identifiers["flight_key"],
        "y_true": y_eval,
        "prob_constant": np.round(prob_constant, 5),
        "prob_logistic_raw": np.round(prob_lr_raw, 5),
        "prob_logistic_calibrated": np.round(prob_lr_cal, 5),
        "prob_xgboost_raw": np.round(prob_xgb_raw, 5),
        "prob_xgboost_calibrated": np.round(prob_xgb_cal, 5),
    })
    df_pred_out.to_parquet(PRED_DIR / "outbound_classification_selection_2023.parquet", index=False)
    print(f"  Exported outbound_classification_selection_2023.parquet ({len(df_pred_out)} rows)")

    # Print Summary Table
    print("\n" + "=" * 80)
    print("OUTBOUND CLASSIFICATION BENCHMARK SUMMARY (2023 SELECTION SPLIT, N=332,734)")
    print("=" * 80)
    print(df_metrics[["model_id", "roc_auc", "pr_auc", "brier_score", "ece", "precision", "recall", "f1", "meets_ece_target_0_05"]].to_string(index=False))
    print("=" * 80)

    return {"status": "SUCCESS", "metrics": metrics_records}


if __name__ == "__main__":
    run_outbound_classification_pipeline()
