"""Tests for Quantile Monotonicity, Non-Crossing, and Pinball Loss."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.candidate_interfaces import (
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES, compute_pinball_loss
from tests.probabilistic.test_distribution_contract import make_dummy_data


@pytest.mark.parametrize(
    "candidate_cls",
    [
        P1EmpiricalCandidate,
        P2XGBoostGaussianCandidate,
        P3NGBoostNormalCandidate,
        P4NGBoostStudentTCandidate,
        P5QuantileRegressionCandidate,
    ],
)
def test_quantile_monotonicity_across_alphas(candidate_cls: type) -> None:
    """Verify that quantiles are non-decreasing: q_alpha1 <= q_alpha2 for alpha1 < alpha2."""
    X_train, y_train = make_dummy_data(n=80, seed=33)
    X_val, _ = make_dummy_data(n=25, seed=44)

    model = candidate_cls(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)
    for i in range(len(sorted_alphas) - 1):
        a1 = sorted_alphas[i]
        a2 = sorted_alphas[i + 1]
        q1 = pred.quantiles[a1]
        q2 = pred.quantiles[a2]
        # Allow tiny numerical tolerance of 1e-4
        inversions = q1 > (q2 + 1e-4)
        assert not np.any(inversions), f"Quantile crossing between {a1} and {a2} for {candidate_cls}"

    # Median check
    np.testing.assert_allclose(pred.median, pred.quantiles[0.50], atol=1e-5)


def test_pinball_loss_non_negative() -> None:
    """Verify pinball loss is strictly non-negative and zero on exact hits."""
    y = np.array([10.0, 20.0, -5.0])
    q_exact = np.array([10.0, 20.0, -5.0])
    q_higher = np.array([15.0, 25.0, 0.0])
    q_lower = np.array([5.0, 15.0, -10.0])

    loss_exact = compute_pinball_loss(y, q_exact, 0.5)
    np.testing.assert_allclose(loss_exact, [0.0, 0.0, 0.0])

    loss_higher = compute_pinball_loss(y, q_higher, 0.5)
    loss_lower = compute_pinball_loss(y, q_lower, 0.5)
    assert np.all(loss_higher > 0.0)
    assert np.all(loss_lower > 0.0)
