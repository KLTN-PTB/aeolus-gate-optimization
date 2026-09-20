"""Unit tests for Phase 3: Temporal Sample Weighting and Hurdle Delay Predictor.

Verifies:
1. Temporal sample weights calculation (COVID-19 2020 penalty, 2021 anchor, linear decay).
2. HurdleDelayPredictor in soft and hard gating modes with point and safety buffer predictions.
3. Sample weight integration across XGBoost and HistGradientBoosting estimators.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier, DummyRegressor

from src.models.hurdle_inference import HurdleDelayPredictor
from src.models.metrics import compute_stratified_regression_metrics
from src.models.refactored_models import (
    build_refactored_hgb_bundle,
    build_refactored_xgboost_bundle,
    fit_bundle,
)
from src.models.temporal_weighting import compute_temporal_sample_weights


def test_temporal_weights_computation() -> None:
    """Tests temporal sample weight computation rules and boundaries."""
    years = np.array([2016, 2017, 2018, 2019, 2020, 2021, 2010])
    weights = compute_temporal_sample_weights(years, target_val_year=2022)

    assert weights.dtype == np.float32
    assert len(weights) == len(years)

    # 1. COVID-19 lockdown year 2020 penalty is 0.5
    assert pytest.approx(weights[4], rel=1e-4) == 0.50

    # 2. Year closest to validation (2021) has weight 1.0
    assert pytest.approx(weights[5], rel=1e-4) == 1.00

    # 3. Decaying weights for 2016-2019
    # 2019: 1.0 - 0.04 * 2 = 0.92
    assert pytest.approx(weights[3], rel=1e-4) == 0.92
    # 2018: 1.0 - 0.04 * 3 = 0.88
    assert pytest.approx(weights[2], rel=1e-4) == 0.88
    # 2017: 1.0 - 0.04 * 4 = 0.84
    assert pytest.approx(weights[1], rel=1e-4) == 0.84
    # 2016: 1.0 - 0.04 * 5 = 0.80
    assert pytest.approx(weights[0], rel=1e-4) == 0.80

    # 4. Floor clipping at 0.75 for distant past (2010)
    assert pytest.approx(weights[6], rel=1e-4) == 0.75

    # 5. Pandas Series input support
    series_years = pd.Series([2020, 2021])
    s_weights = compute_temporal_sample_weights(series_years, target_val_year=2022)
    assert pytest.approx(s_weights[0], rel=1e-4) == 0.50
    assert pytest.approx(s_weights[1], rel=1e-4) == 1.00

    # 6. Empty array edge case
    empty_weights = compute_temporal_sample_weights(np.array([]))
    assert len(empty_weights) == 0
    assert empty_weights.dtype == np.float32


def test_hurdle_predictor_soft_and_hard_modes() -> None:
    """Tests HurdleDelayPredictor fitting, point and safety buffer predictions."""
    np.random.seed(42)
    n_samples = 120
    n_features = 5

    X = np.random.randn(n_samples, n_features)
    # Synthetic heavy-tailed delays:
    # 80 on-time/early flights (< 15m), 20 moderate delays (15-59m), 20 severe delays (>= 60m)
    y_early = np.random.uniform(-15.0, 10.0, size=80)
    y_mod = np.random.uniform(15.0, 55.0, size=20)
    y_sev = np.random.uniform(60.0, 180.0, size=20)
    y = np.concatenate([y_early, y_mod, y_sev])

    # Sample weights
    sample_weights = np.random.uniform(0.5, 1.0, size=n_samples).astype(np.float32)

    # 1. Soft gating
    hgb_bundle = build_refactored_hgb_bundle(loss="absolute_error", seed=42)
    hurdle_soft = HurdleDelayPredictor(
        classifier_bundle=hgb_bundle.classifier,
        regressor_bundle=hgb_bundle.regressor,
        gating_mode="soft",
        threshold=0.30,
    )
    hurdle_soft.fit(X, y, sample_weight=sample_weights)

    pred_soft = hurdle_soft.predict(X)
    assert pred_soft.shape == (n_samples,)
    assert np.isfinite(pred_soft).all()
    assert hurdle_soft.early_median_ < 15.0

    # Stratified metrics on soft gating
    metrics_soft = compute_stratified_regression_metrics(y, pred_soft)
    assert metrics_soft.overall.count == n_samples
    assert metrics_soft.shrinkage_ratio > 0.0

    # 2. Hard gating
    xgb_bundle = build_refactored_xgboost_bundle(objective="reg:pseudohubererror", huber_slope=15.0)
    hurdle_hard = HurdleDelayPredictor(
        classifier_bundle=xgb_bundle.classifier,
        regressor_bundle=xgb_bundle.regressor,
        gating_mode="hard",
        threshold=0.30,
    )
    hurdle_hard.fit(X, y, sample_weight=sample_weights)

    pred_hard, pred_buffer = hurdle_hard.predict_point_and_buffer(X, alpha=0.75)
    assert pred_hard.shape == (n_samples,)
    assert pred_buffer.shape == (n_samples,)
    assert np.isfinite(pred_hard).all()
    assert np.isfinite(pred_buffer).all()

    # Safety buffer should provide non-negative padding for flight scheduling
    assert np.all(pred_buffer >= np.maximum(pred_hard, 0.0))

    # Stratified metrics on hard gating
    metrics_hard = compute_stratified_regression_metrics(y, pred_hard)
    assert metrics_hard.shrinkage_ratio > 0.0
    assert not np.isnan(metrics_hard.shrinkage_ratio)


def test_hurdle_predictor_invalid_gating_mode() -> None:
    """Verifies that invalid gating mode raises ValueError."""
    dummy_clf = DummyClassifier(strategy="constant", constant=1)
    dummy_reg = DummyRegressor(strategy="constant", constant=20.0)

    with pytest.raises(ValueError, match="gating_mode must be 'soft' or 'hard'"):
        HurdleDelayPredictor(dummy_clf, dummy_reg, gating_mode="unsupported_mode")


def test_sample_weight_integration() -> None:
    """Verifies sample_weight integration in XGBoost and HistGradientBoosting bundles."""
    np.random.seed(42)
    n = 60
    X = np.random.randn(n, 4)
    y_reg = np.random.uniform(-10.0, 80.0, size=n)
    y_cls = (y_reg >= 15.0).astype(int)
    weights = np.ones(n, dtype=np.float32)

    # Test XGBoost bundle with fit_bundle
    xgb_bundle = build_refactored_xgboost_bundle(objective="reg:pseudohubererror")
    fit_bundle(xgb_bundle, X, y_cls, y_reg, sample_weight=weights)
    p_xgb_cls = xgb_bundle.classifier.predict_proba(X)
    p_xgb_reg = xgb_bundle.regressor.predict(X)
    assert p_xgb_cls.shape == (n, 2)
    assert p_xgb_reg.shape == (n,)

    # Test HistGradientBoosting bundle with fit_bundle
    hgb_bundle = build_refactored_hgb_bundle(loss="absolute_error")
    fit_bundle(hgb_bundle, X, y_cls, y_reg, sample_weight=weights)
    p_hgb_cls = hgb_bundle.classifier.predict_proba(X)
    p_hgb_reg = hgb_bundle.regressor.predict(X)
    assert p_hgb_cls.shape == (n, 2)
    assert p_hgb_reg.shape == (n,)
