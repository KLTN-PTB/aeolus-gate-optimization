"""Unit tests for Phase B: Calibrated Hurdle Soft-Gating and Conformalized Quantile Regression."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss

from src.models.hurdle_inference import HurdleDelayPredictor
from src.models.metrics import compute_empirical_coverage, compute_pinball_loss
from src.models.quantile_prediction import (
    ConformalQuantileRegressor,
    rearrange_quantiles,
    verify_quantile_monotonicity,
)
from src.models.refactored_models import (
    build_refactored_hgb_bundle,
    build_refactored_xgboost_bundle,
)


def test_quantile_rearrangement_eliminates_crossing() -> None:
    """Verify that quantile rearrangement enforces q50 <= q75 <= q90 across 100% of samples."""
    # Artificially create severe quantile crossings:
    # Flight 0: q50=25.0, q75=15.0 (crossing!), q90=10.0 (crossing!)
    # Flight 1: q50=10.0, q75=30.0, q90=20.0 (crossing!)
    # Flight 2: q50=0.0, q75=5.0, q90=15.0 (valid)
    raw_quantiles = {
        0.50: np.array([25.0, 10.0, 0.0]),
        0.75: np.array([15.0, 30.0, 5.0]),
        0.90: np.array([10.0, 20.0, 15.0]),
    }

    # Raw quantiles must fail monotonicity
    assert not verify_quantile_monotonicity(raw_quantiles)

    # Apply rearrangement
    rearranged = rearrange_quantiles(raw_quantiles)

    # Rearranged quantiles must be strictly monotonic
    assert verify_quantile_monotonicity(rearranged)

    # Verify exact expected rearranged values:
    # Flight 0: q50*=25.0, q75*=max(15, 25)=25.0, q90*=max(10, 25)=25.0
    # Flight 1: q50*=10.0, q75*=max(30, 10)=30.0, q90*=max(20, 30)=30.0
    # Flight 2: q50*=0.0, q75*=max(5, 0)=5.0, q90*=max(15, 5)=15.0
    np.testing.assert_allclose(rearranged[0.50], [25.0, 10.0, 0.0])
    np.testing.assert_allclose(rearranged[0.75], [25.0, 30.0, 5.0])
    np.testing.assert_allclose(rearranged[0.90], [25.0, 30.0, 15.0])

    # Check 100% sample non-crossing guarantee
    assert np.all(rearranged[0.50] <= rearranged[0.75])
    assert np.all(rearranged[0.75] <= rearranged[0.90])


def test_calibrated_soft_gating_hurdle() -> None:
    """Verify Calibrated Soft-Gating Hurdle fits gate on P(y>=15) and regressor on y>=15."""
    np.random.seed(42)
    n = 200
    p = 5

    X = np.random.randn(n, p)
    # Synthetic delay distribution: 70% on-time (<15m), 30% delayed (>=15m)
    y = np.where(
        np.random.rand(n) < 0.30,
        np.random.uniform(15.0, 120.0, size=n),
        np.random.uniform(-20.0, 10.0, size=n),
    )

    hgb_bundle = build_refactored_hgb_bundle(loss="absolute_error", seed=42)
    hurdle = HurdleDelayPredictor(
        classifier_bundle=hgb_bundle.classifier,
        regressor_bundle=hgb_bundle.regressor,
        gating_mode="soft",
        delay_threshold=15.0,
        calibrate=True,
        calibration_fraction=0.25,
        random_state=42,
    )
    hurdle.fit(X, y)

    # 1. Check early median is < 15.0
    assert hurdle.early_median_ < 15.0

    # 2. Check predict_proba output is valid probabilities in [0, 1]
    probas = hurdle.predict_proba(X)
    assert probas.shape == (n, 2)
    assert np.all((probas >= 0.0) & (probas <= 1.0))
    np.testing.assert_allclose(probas.sum(axis=1), 1.0, rtol=1e-5)

    # 3. Check predicted values are within plausible range and soft-gated
    preds = hurdle.predict(X)
    assert len(preds) == n
    assert np.isfinite(preds).all()

    # Flights with very low delay probability should predict near early_median
    low_prob_mask = probas[:, 1] < 0.05
    if low_prob_mask.sum() > 0:
        np.testing.assert_allclose(
            preds[low_prob_mask],
            np.full(low_prob_mask.sum(), hurdle.early_median_),
            atol=5.0,
        )


def test_conformal_quantile_regression() -> None:
    """Verify ConformalQuantileRegressor monotonicity and empirical coverage guarantees."""
    np.random.seed(42)
    n_train = 400
    n_test = 200
    p = 4

    X_train = np.random.randn(n_train, p)
    y_train = 10.0 + 3.0 * X_train[:, 0] + np.random.exponential(scale=20.0, size=n_train)

    X_test = np.random.randn(n_test, p)
    y_test = 10.0 + 3.0 * X_test[:, 0] + np.random.exponential(scale=20.0, size=n_test)

    cqr = ConformalQuantileRegressor(
        alphas=(0.50, 0.75, 0.90),
        n_estimators=40,
        calibration_fraction=0.25,
        random_state=42,
    )
    cqr.fit(X_train, y_train)

    # 1. Monotonicity across raw, rearranged, and conformal
    rearranged = cqr.predict_rearranged_quantiles(X_test)
    assert verify_quantile_monotonicity(rearranged)
    assert np.all(rearranged[0.50] <= rearranged[0.75])
    assert np.all(rearranged[0.75] <= rearranged[0.90])

    conformal = cqr.predict_conformal_quantiles(X_test)
    assert verify_quantile_monotonicity(conformal)
    assert np.all(conformal[0.50] <= conformal[0.75])
    assert np.all(conformal[0.75] <= conformal[0.90])

    # 2. Conformal coverage evaluation on test set
    eval_res = cqr.evaluate_quantiles(X_test, y_test, use_conformal=True)
    assert eval_res["is_monotonic"] is True

    cov_50 = eval_res["metrics"]["alpha_0.50"]["empirical_coverage"]
    cov_75 = eval_res["metrics"]["alpha_0.75"]["empirical_coverage"]
    cov_90 = eval_res["metrics"]["alpha_0.90"]["empirical_coverage"]

    # Conformalized coverage should meet or exceed nominal targets (within minor finite-sample tolerance)
    assert cov_75 >= 72.0, f"q75 empirical coverage {cov_75:.2f}% below nominal target"
    assert cov_90 >= 87.0, f"q90 empirical coverage {cov_90:.2f}% below nominal target"
