"""Tests for Finite Values, NaN/Inf Detection, and Numerical Validity in Phase 3."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.candidate_interfaces import P2XGBoostGaussianCandidate
from src.models.probabilistic.correctness_validator import validate_candidate_correctness
from tests.probabilistic.test_distribution_contract import make_dummy_data


def test_finite_values_validation_passes_on_sound_model() -> None:
    """A valid model passes all numerical checks."""
    X_train, y_train = make_dummy_data(n=60, seed=77)
    X_val, _ = make_dummy_data(n=15, seed=88)

    model = P2XGBoostGaussianCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    report = validate_candidate_correctness(pred, test_seed=202601)
    assert report.is_valid
    assert len(report.issues) == 0


def test_nan_injection_causes_correctness_failure() -> None:
    """Injecting NaN or Inf into mean/median/quantiles triggers correctness failure."""
    X_train, y_train = make_dummy_data(n=60, seed=77)
    X_val, _ = make_dummy_data(n=15, seed=88)

    model = P2XGBoostGaussianCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    # Corrupt median with NaN
    corrupted_median = pred.median.copy()
    corrupted_median[0] = np.nan
    pred.median = corrupted_median

    report = validate_candidate_correctness(pred, test_seed=202601)
    assert not report.is_valid
    assert any("NaN" in issue or "Inf" in issue for issue in report.issues)


def test_probability_out_of_bounds_causes_failure() -> None:
    """Corrupting P(delay >= 15) to exceed [0, 1] triggers correctness failure."""
    X_train, y_train = make_dummy_data(n=60, seed=77)
    X_val, _ = make_dummy_data(n=15, seed=88)

    model = P2XGBoostGaussianCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    # Corrupt p_delay_ge_15
    corrupted_p = pred.p_delay_ge_15.copy()
    corrupted_p[0] = 1.25  # Exceeds 1.0
    pred.p_delay_ge_15 = corrupted_p

    report = validate_candidate_correctness(pred, test_seed=202601)
    assert not report.is_valid
    assert any("outside [0, 1]" in issue for issue in report.issues)
