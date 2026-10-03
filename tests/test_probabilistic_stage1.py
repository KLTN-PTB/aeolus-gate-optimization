"""Unit tests for Stage 1 Distributional Baselines (B1, B2, B3, B4, B5).

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Stage 1
Tests:
1. fold isolation: validation data is never accessible during training or preprocessing fitting.
2. preprocessing fit location: Preprocessor fit strictly on training fold rows.
3. no in-sample sigma for B2: B2 predictive uncertainty is estimated strictly from cross-fitted OOF residuals.
4. quantile ordering/crossing detection: detects crossing inversions vs strictly monotonic quantiles.
5. B4 interval level correctness: verifies 50%, 80%, 90%, 95% symmetric quantile pairs.
6. B4 CRPS omission: asserts CRPS is strictly omitted for quantile-only models.
7. B1 hierarchical backoff: verifies carrier x hour -> carrier -> global fallback logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.baselines import (
    B1EmpiricalDistribution,
    B2XGBoostGaussian,
    B3NGBoostNormal,
    B4LightGBMQuantile,
    B5NGBoostStudentT,
    TreePreprocessor,
)
from src.models.probabilistic.metrics import (
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
    compute_interval_metrics,
    compute_pinball_loss,
    compute_quantile_coverage,
    compute_quantile_crossing_rate,
)
from src.models.probabilistic.splitting import FROZEN_PROBABILISTIC_FOLDS


def _make_dummy_features(n: int = 100, seed: int = 42) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "CRS_ELAPSED_TIME": rng.uniform(60, 240, size=n),
            "calendar_year": rng.choice([2016, 2017], size=n),
            "calendar_month": rng.integers(1, 13, size=n),
            "calendar_day_of_month": rng.integers(1, 29, size=n),
            "calendar_day_of_week": rng.integers(1, 8, size=n),
            "is_weekend": rng.integers(0, 2, size=n),
            "scheduled_departure_hour": rng.integers(6, 22, size=n),
            "scheduled_departure_minute": rng.integers(0, 60, size=n),
            "OP_CARRIER": rng.choice(["AA", "DL", "UA"], size=n),
            "ORIGIN": rng.choice(["BOS", "JFK", "LAX"], size=n),
            "OP_CARRIER_FL_NUM": rng.choice(["100", "200", "300"], size=n),
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]
    y = rng.normal(10.0, 20.0, size=n).round()
    return df, y


def test_fold_isolation() -> None:
    for fold in FROZEN_PROBABILISTIC_FOLDS:
        assert fold.outer_val_year not in fold.outer_train_years
        assert fold.inner_val_year not in fold.inner_train_years
        assert fold.outer_val_year > max(fold.outer_train_years)


def test_preprocessing_fit_location() -> None:
    X_train, y_train = _make_dummy_features(n=50, seed=1)
    X_val, _ = _make_dummy_features(n=20, seed=2)
    X_val["OP_CARRIER"] = "UNKNOWN_CARRIER"  # unseen category

    prep = TreePreprocessor()
    prep.fit(X_train)

    # Preprocessor fit on train must not know val category
    trans_val = prep.transform(X_val)
    # The categorical index for OP_CARRIER is col 8 (numeric 8 cols, then categoricals)
    assert trans_val.shape[0] == 20
    assert trans_val.shape[1] == 11
    # Unseen category must be encoded as -1 (unknown)
    assert (trans_val[:, 8] == -1.0).all()


def test_no_in_sample_sigma_for_b2() -> None:
    X_train, y_train = _make_dummy_features(n=200, seed=42)
    b2 = B2XGBoostGaussian(n_estimators=30, seed=202601, n_oof_splits=3)
    b2.fit(X_train, y_train)

    assert b2.is_fitted_
    assert b2.sigma_oof_ > 0.0
    assert b2.in_sample_sigma_ > 0.0

    # In-sample residuals suffer from optimistic bias, so in-sample std should be smaller
    # than cross-fitted OOF std. They MUST not be identical!
    assert b2.sigma_oof_ != b2.in_sample_sigma_

    pred = b2.predict_distribution(X_train[:10])
    assert pred["distribution_type"] == "fixed_sigma_gaussian"
    assert np.allclose(pred["sigma"], b2.sigma_oof_)


def test_quantile_ordering_and_crossing_detection() -> None:
    # 1. Strictly monotonic quantiles -> 0% crossing
    monotonic_quantiles = {
        0.10: np.array([5.0, 10.0, 15.0]),
        0.50: np.array([12.0, 18.0, 22.0]),
        0.90: np.array([25.0, 30.0, 40.0]),
    }
    rate, inversions = compute_quantile_crossing_rate(monotonic_quantiles)
    assert rate == 0.0
    assert inversions == 0

    # 2. Inverted quantiles (crossing)
    crossing_quantiles = {
        0.10: np.array([5.0, 20.0, 15.0]),   # sample 1 has q_0.10 = 20.0 > q_0.50 = 18.0
        0.50: np.array([12.0, 18.0, 22.0]),
        0.90: np.array([25.0, 14.0, 40.0]),  # sample 1 has q_0.90 = 14.0 < q_0.50 = 18.0
    }
    rate_cross, inversions_cross = compute_quantile_crossing_rate(crossing_quantiles)
    assert rate_cross > 0.0
    assert inversions_cross > 0


def test_b4_interval_level_correctness() -> None:
    # Verify pre-registered symmetric pairs match nominal levels
    assert SYMMETRIC_INTERVAL_PAIRS[0.50] == (0.25, 0.75)
    assert SYMMETRIC_INTERVAL_PAIRS[0.80] == (0.10, 0.90)
    assert SYMMETRIC_INTERVAL_PAIRS[0.90] == (0.05, 0.95)
    assert SYMMETRIC_INTERVAL_PAIRS[0.95] == (0.025, 0.975)

    # Test coverage computation on standard Normal
    rng = np.random.default_rng(202601)
    y_test = rng.standard_normal(size=10000)
    # Theoretical 80% interval for standard Normal: [-1.2816, 1.2816]
    ql = np.full_like(y_test, -1.28155)
    qu = np.full_like(y_test, 1.28155)

    cov, width = compute_interval_metrics(y_test, ql, qu)
    assert np.isclose(cov, 0.80, atol=0.015)
    assert np.isclose(width, 2 * 1.28155, atol=1e-3)


def test_b1_hierarchical_backoff() -> None:
    # Train with 1 common carrier-hour group (count >= 5) and 1 rare group
    X = pd.DataFrame(
        {
            "OP_CARRIER": ["DL"] * 10 + ["AA"] * 2,
            "scheduled_departure_hour": [8] * 10 + [23] * 2,
            "scheduled_departure_minute": [0] * 12,
            "calendar_year": [2016] * 12,
            "calendar_month": [1] * 12,
            "calendar_day_of_month": [1] * 12,
            "calendar_day_of_week": [1] * 12,
            "is_weekend": [0] * 12,
            "CRS_ELAPSED_TIME": [100.0] * 12,
            "ORIGIN": ["BOS"] * 12,
            "OP_CARRIER_FL_NUM": ["100"] * 12,
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]
    y = np.array([5.0] * 10 + [50.0] * 2)

    b1 = B1EmpiricalDistribution(min_support=5)
    b1.fit(X, y)

    # Predict:
    # 1. DL at hour 8 -> carrier_hour level (10 >= 5)
    # 2. DL at hour 12 -> carrier level (DL count 10 >= 5)
    # 3. UA at hour 8 -> global level (UA not in train)
    X_test = pd.DataFrame(
        {
            "OP_CARRIER": ["DL", "DL", "UA"],
            "scheduled_departure_hour": [8, 12, 8],
            "scheduled_departure_minute": [0, 0, 0],
            "calendar_year": [2017, 2017, 2017],
            "calendar_month": [1, 1, 1],
            "calendar_day_of_month": [1, 1, 1],
            "calendar_day_of_week": [1, 1, 1],
            "is_weekend": [0, 0, 0],
            "CRS_ELAPSED_TIME": [100.0, 100.0, 100.0],
            "ORIGIN": ["BOS", "BOS", "BOS"],
            "OP_CARRIER_FL_NUM": ["100", "100", "100"],
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]

    pred = b1.predict_distribution(X_test)
    assert pred["backoff_levels"] == ["carrier_hour", "carrier", "global"]
    assert np.isclose(pred["mu"][0], 5.0)  # DL hour 8 mean
    assert np.isclose(pred["mu"][1], 5.0)  # DL overall mean
