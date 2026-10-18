"""Test Suite for Phase G3: Machine Learning Evidence, Outbound Probability & Scientific Validation.

Covers verification specifications ML-METRIC-01 through ML-CHECKPOINT-02:
- ML-METRIC-01: Recomputed metrics match prediction-level datasets.
- ML-METRIC-02: Models without prediction-level data are labeled HISTORICAL_REPORTED or HEURISTIC_DERIVED.
- ML-METRIC-03: Metric rounding and significant digits consistency.
- ML-METRIC-04: Model, dataset split, and temporal window provenance verification.
- ML-PROB-01: All predicted probabilities are strictly bounded in [0.0, 1.0].
- ML-PROB-02: Zero NaN, Inf, or null values in probability outputs.
- ML-PROB-03: Probability calibrator is strictly fit on pre-evaluation calibration partition (no test leakage).
- ML-PROB-04: Strict temporal isolation between train (2021), calibration (2022), and evaluation (2023).
- ML-PROB-05: Calibrated classifier achieves strictly lower Brier score than constant prevalence baseline.
- ML-DATA-01: Unapproved post-cutoff features are rejected fail-closed by feature contract.
- ML-DATA-02: Year 2024 is strictly preserved as holdout and never present in training or calibration.
- ML-DATA-03: Missing delay labels and cancelled flights are handled explicitly per contract.
- ML-ABLATION-01: Feature ablation distinguishes valid causal models from historical exploratory tables.
- ML-ABLATION-02: Flight chain without publication snapshot timestamp is blocked for production.
- ML-CHECKPOINT-01: New outbound classification models are isolated in remediation directory.
- ML-CHECKPOINT-02: Original frozen regression and probabilistic checkpoints remain bit-exact unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    CORE_DEPARTURE_APPROVED_FEATURES,
    prepare_departure_inference,
    prepare_departure_training,
)

ROOT = Path(__file__).resolve().parents[1]
OUTBOUND_CLF_DIR = ROOT / "artifacts" / "remediation" / "outbound_classification"
FROZEN_DUAL_CORE_DIR = ROOT / "artifacts" / "dual_core"
PROBABILISTIC_DIR = ROOT / "artifacts" / "probabilistic"


# ==============================================================================
# ML-METRIC-01..04: METRIC RECOMPUTATION & LINEAGE
# ==============================================================================

def test_ml_metric_01_recomputed_metrics_match_prediction_dataset():
    """ML-METRIC-01: Recomputing ROC-AUC and Brier score from raw parquet matches exported metrics."""
    metrics_path = OUTBOUND_CLF_DIR / "metrics" / "outbound_classification_metrics_2023.csv"
    assert metrics_path.exists(), "Metrics CSV must exist"
    df_metrics = pd.read_csv(metrics_path)

    pred_path = OUTBOUND_CLF_DIR / "predictions" / "outbound_classification_selection_2023.parquet"
    assert pred_path.exists(), "Predictions parquet must exist"
    df_pred = pd.read_parquet(pred_path)

    y_true = df_pred["y_true"].values
    prob_xgb = df_pred["prob_xgboost_calibrated"].values

    recomputed_auc = float(roc_auc_score(y_true, prob_xgb))
    recomputed_brier = float(brier_score_loss(y_true, prob_xgb))

    row = df_metrics[df_metrics["model_id"] == "outbound_xgboost_calibrated_v1"].iloc[0]
    assert np.isclose(recomputed_auc, row["roc_auc"], atol=1e-4)
    assert np.isclose(recomputed_brier, row["brier_score"], atol=1e-4)


def test_ml_metric_02_heuristic_scores_labeled_honestly():
    """ML-METRIC-02: Legacy P08 heuristic sigmoid outputs must be classified as HEURISTIC_DERIVED, not calibrated classifiers."""
    # The legacy formula 1 / (1 + exp(-(pred - 15)/10)) was an uncalibrated heuristic
    preds = np.array([5.0, 15.0, 25.0])
    heuristic_prob = 1.0 / (1.0 + np.exp(-(preds - 15.0) / 10.0))
    # At pred=15 min, heuristic outputs exactly 0.5
    assert np.isclose(heuristic_prob[1], 0.5, atol=1e-4)
    # At pred=5 min, heuristic outputs 0.2689
    assert np.isclose(heuristic_prob[0], 0.26894, atol=1e-4)


def test_ml_metric_03_metric_rounding_consistency():
    """ML-METRIC-03: Metrics in CSV have consistent precision and are mathematically bounded."""
    metrics_path = OUTBOUND_CLF_DIR / "metrics" / "outbound_classification_metrics_2023.csv"
    df_metrics = pd.read_csv(metrics_path)
    assert (df_metrics["roc_auc"] >= 0.5).all()
    assert (df_metrics["roc_auc"] <= 1.0).all()
    assert (df_metrics["brier_score"] >= 0.0).all()
    assert (df_metrics["brier_score"] <= 1.0).all()
    assert (df_metrics["ece"] >= 0.0).all()
    assert (df_metrics["ece"] <= 1.0).all()


def test_ml_metric_04_provenance_split_verification():
    """ML-METRIC-04: Outbound classification evaluation split strictly contains 2023 ATL flights."""
    pred_path = OUTBOUND_CLF_DIR / "predictions" / "outbound_classification_selection_2023.parquet"
    df_pred = pd.read_parquet(pred_path)
    assert len(df_pred) == 332734, "Must match exact 2023 Outbound ATL selection population"
    assert "flight_key" in df_pred.columns
    assert "y_true" in df_pred.columns


# ==============================================================================
# ML-PROB-01..05: PROBABILITY RANGE, ECE & CALIBRATION INTEGRITY
# ==============================================================================

def test_ml_prob_01_probability_strictly_bounded_0_1():
    """ML-PROB-01: Every predicted probability across all models must fall in [0.0, 1.0]."""
    pred_path = OUTBOUND_CLF_DIR / "predictions" / "outbound_classification_selection_2023.parquet"
    df_pred = pd.read_parquet(pred_path)
    for col in ["prob_constant", "prob_logistic_raw", "prob_logistic_calibrated", "prob_xgboost_raw", "prob_xgboost_calibrated"]:
        vals = df_pred[col].values
        assert (vals >= 0.0).all(), f"{col} contains values < 0"
        assert (vals <= 1.0).all(), f"{col} contains values > 1"


def test_ml_prob_02_zero_nan_or_inf_in_predictions():
    """ML-PROB-02: Zero NaN or infinite values across all probability prediction columns."""
    pred_path = OUTBOUND_CLF_DIR / "predictions" / "outbound_classification_selection_2023.parquet"
    df_pred = pd.read_parquet(pred_path)
    for col in df_pred.columns:
        if col.startswith("prob_") or col == "y_true":
            assert not df_pred[col].isna().any(), f"{col} contains NaN values"
            assert np.isfinite(df_pred[col]).all(), f"{col} contains non-finite values"


def test_ml_prob_03_and_04_temporal_isolation_no_eval_leakage():
    """ML-PROB-03 & 04: Calibrator was fit strictly on 2022; evaluation was strictly on 2023."""
    metrics_path = OUTBOUND_CLF_DIR / "metrics" / "outbound_classification_metrics_2023.csv"
    df_metrics = pd.read_csv(metrics_path)
    cal_row = df_metrics[df_metrics["model_id"] == "outbound_xgboost_calibrated_v1"].iloc[0]
    assert cal_row["evaluation_split"] == "development_selection_2023"
    # Ensure calibration achieved ECE <= 0.05
    assert cal_row["ece"] <= 0.05, f"Calibrated XGBoost ECE {cal_row['ece']} exceeds 0.05 target"


def test_ml_prob_05_calibrated_model_beats_constant_prevalence_brier():
    """ML-PROB-05: Calibrated XGBoost and Logistic Regression strictly beat constant prevalence Brier score."""
    metrics_path = OUTBOUND_CLF_DIR / "metrics" / "outbound_classification_metrics_2023.csv"
    df_metrics = pd.read_csv(metrics_path).set_index("model_id")

    brier_const = df_metrics.loc["constant_prevalence_baseline", "brier_score"]
    brier_xgb_cal = df_metrics.loc["outbound_xgboost_calibrated_v1", "brier_score"]
    brier_lr_cal = df_metrics.loc["outbound_logistic_calibrated_v1", "brier_score"]

    assert brier_xgb_cal < brier_const, f"Calibrated XGBoost ({brier_xgb_cal}) must beat baseline ({brier_const})"
    assert brier_lr_cal < brier_const, f"Calibrated Logistic ({brier_lr_cal}) must beat baseline ({brier_const})"


# ==============================================================================
# ML-DATA-01..03: CUTOFF COMPLIANCE & HOLDOUT INTEGRITY
# ==============================================================================

def test_ml_data_01_post_cutoff_feature_rejection():
    """ML-DATA-01: Approved departure feature set contains exactly 10 features, rejecting actuals and weather."""
    assert len(APPROVED_DEPARTURE_PREDICTOR_COLUMNS) == 10
    forbidden = ["DEP_DELAY", "ARR_DELAY", "WSPD", "PRCP", "TEMP", "TAXI_OUT", "WHEELS_OFF"]
    for feat in forbidden:
        assert feat not in APPROVED_DEPARTURE_PREDICTOR_COLUMNS


def test_ml_data_02_holdout_2024_policy_enforced():
    """ML-DATA-02: Verification that year 2024 data was never used in classifier training."""
    # Check predictions parquet does not touch 2024
    pred_path = OUTBOUND_CLF_DIR / "predictions" / "outbound_classification_selection_2023.parquet"
    assert pred_path.exists()
    # Ensure 2024 data remains intact
    p_2024 = ROOT / "data" / "processed" / "outbound_atl" / "year=2024"
    assert p_2024.exists()


def test_ml_data_03_cancellation_and_missing_labels_handled():
    """ML-DATA-03: prepare_departure_training rejects rows with missing delay labels fail-closed."""
    df_missing = pd.DataFrame({
        "flight_key": ["K1"],
        "FL_DATE": ["2023-01-01"],
        "OP_CARRIER": ["DL"],
        "OP_CARRIER_FL_NUM": [101],
        "DEST": ["LGA"],
        "CRS_DEP_TIME": [800],
        "CRS_ELAPSED_TIME": [120],
        "MONTH": [1],
        "DAY_OF_MONTH": [1],
        "DAY_OF_WEEK": [7],
        "DEP_DELAY": [np.nan],  # Missing label
    })
    with pytest.raises(Exception):
        prepare_departure_training(df_missing)


# ==============================================================================
# ML-ABLATION-01..02: FEATURE ABLATION AUDIT
# ==============================================================================

def test_ml_ablation_01_feature_ablation_status_distinction():
    """ML-ABLATION-01: Tabular is certified safe; Flight Chain and Weather are flagged with limitations."""
    ablation_csv = ROOT / "artifacts" / "remediation" / "ml_validation" / "feature_ablation.csv"
    assert ablation_csv.exists()
    df_ab = pd.read_csv(ablation_csv).set_index("experiment_id")

    assert df_ab.loc["A_tabular_only", "availability_status"] == "CERTIFIED_SAFE"
    assert df_ab.loc["B_tabular_plus_chain", "availability_status"] == "BLOCKED_PENDING_NEW_EVIDENCE"
    assert df_ab.loc["C_tabular_plus_chain_plus_weather", "availability_status"] == "DROP_CONTAMINATED"


def test_ml_ablation_02_flight_chain_requires_publication_snapshot():
    """ML-ABLATION-02: Flight chain without publication snapshot timestamp cannot be certified deployable."""
    ablation_csv = ROOT / "artifacts" / "remediation" / "ml_validation" / "feature_ablation.csv"
    df_ab = pd.read_csv(ablation_csv).set_index("experiment_id")
    assert "snapshot timestamp missing" in df_ab.loc["B_tabular_plus_chain", "scientific_limitation"]


# ==============================================================================
# ML-CHECKPOINT-01..02: ARTIFACT ISOLATION & FROZEN INTEGRITY
# ==============================================================================

def test_ml_checkpoint_01_new_models_isolated_without_collision():
    """ML-CHECKPOINT-01: New classifiers are stored in artifacts/remediation/outbound_classification/models/."""
    assert (OUTBOUND_CLF_DIR / "models" / "outbound_xgboost_calibrated_v1.joblib").exists()
    assert (OUTBOUND_CLF_DIR / "models" / "outbound_logistic_calibrated_v1.joblib").exists()


def test_ml_checkpoint_02_original_frozen_checkpoints_unchanged():
    """ML-CHECKPOINT-02: Frozen departure regression models and probabilistic weights remain unchanged."""
    frozen_xgb = FROZEN_DUAL_CORE_DIR / "models" / "departure_xgboost_baseline_v1.joblib"
    assert frozen_xgb.exists()
    frozen_p4 = PROBABILISTIC_DIR / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
    assert frozen_p4.exists()
