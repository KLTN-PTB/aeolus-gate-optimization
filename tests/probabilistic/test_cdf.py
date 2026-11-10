"""Tests for CDF properties (monotonicity, boundaries, consistency) in Phase 3."""

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
from tests.probabilistic.test_distribution_contract import make_dummy_data


@pytest.mark.parametrize(
    "candidate_cls",
    [
        P1EmpiricalCandidate,
        P2XGBoostGaussianCandidate,
        P3NGBoostNormalCandidate,
        P4NGBoostStudentTCandidate,
    ],
)
def test_cdf_monotonicity_and_bounds(candidate_cls: type) -> None:
    """Verify that CDF callable is non-decreasing and bounded in [0, 1]."""
    X_train, y_train = make_dummy_data(n=70, seed=10)
    X_val, _ = make_dummy_data(n=20, seed=20)

    model = candidate_cls(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    # Evaluate across fine delay grid
    grid = np.linspace(-60.0, 180.0, 30)
    evals = [pred.cdf(y) for y in grid]

    for j in range(len(grid) - 1):
        f_curr = evals[j]
        f_next = evals[j + 1]

        # Bounded in [0, 1]
        assert np.all(f_curr >= -1e-6), f"CDF < 0 at y={grid[j]}"
        assert np.all(f_curr <= 1.0 + 1e-6), f"CDF > 1 at y={grid[j]}"

        # Monotonically non-decreasing
        assert np.all(f_curr <= f_next + 1e-5), f"CDF decrease between {grid[j]} and {grid[j+1]}"

    # Extreme bounds check
    f_far_left = pred.cdf(-500.0)
    f_far_right = pred.cdf(500.0)
    assert np.all(f_far_left <= 0.05)
    assert np.all(f_far_right >= 0.95)


@pytest.mark.parametrize(
    "candidate_cls",
    [
        P2XGBoostGaussianCandidate,
        P3NGBoostNormalCandidate,
        P4NGBoostStudentTCandidate,
    ],
)
def test_cdf_event_probability_consistency(candidate_cls: type) -> None:
    """Verify that P(delay >= 15) is closely consistent with 1 - CDF(15.0)."""
    X_train, y_train = make_dummy_data(n=70, seed=15)
    X_val, _ = make_dummy_data(n=20, seed=25)

    model = candidate_cls(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    cdf_at_15 = pred.cdf(15.0)
    expected_p15 = 1.0 - cdf_at_15

    # Should match p_delay_ge_15 within tight tolerance
    np.testing.assert_allclose(pred.p_delay_ge_15, expected_p15, atol=1e-3)


def test_quantile_candidate_rejects_heuristic_cdf() -> None:
    """Verify that P5 quantile model does not synthesize an unsupported CDF."""
    from src.contracts.distribution import CapabilityNotSupportedError

    X_train, y_train = make_dummy_data(n=70, seed=15)
    X_val, _ = make_dummy_data(n=20, seed=25)

    model = P5QuantileRegressionCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    assert not pred.metadata.get("capabilities", {}).get("has_cdf", False)
    with pytest.raises(CapabilityNotSupportedError, match="continuous CDF"):
        pred.cdf(15.0)
