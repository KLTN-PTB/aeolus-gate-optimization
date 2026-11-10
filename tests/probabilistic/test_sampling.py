"""Tests for Distributional Sampling (Shape, Finite values, Determinism) in Phase 3."""

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
def test_sampling_validity_and_determinism(candidate_cls: type) -> None:
    """Verify that candidate samplers produce valid shapes, finite draws, and seed determinism."""
    X_train, y_train = make_dummy_data(n=100, seed=55)
    X_val, _ = make_dummy_data(n=20, seed=66)

    model = candidate_cls(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    n_samples = 50
    draws_seed_1 = pred.sampler(n_samples, seed=202601)

    # 1. Correct shape (n_samples, n_flights)
    assert draws_seed_1.shape == (n_samples, len(X_val))

    # 2. Strictly finite values
    assert np.all(np.isfinite(draws_seed_1)), f"Sampler produced NaN/Inf for {candidate_cls}"

    # 3. Determinism under fixed seed
    draws_seed_1_again = pred.sampler(n_samples, seed=202601)
    np.testing.assert_array_equal(
        draws_seed_1,
        draws_seed_1_again,
        err_msg=f"Non-deterministic sampling under identical seed in {candidate_cls}",
    )

    # 4. Sensitivity to different seed
    draws_seed_2 = pred.sampler(n_samples, seed=99999)
    assert not np.array_equal(draws_seed_1, draws_seed_2)


def test_quantile_candidate_rejects_sampling() -> None:
    """Verify that P5 quantile model raises CapabilityNotSupportedError when sampling is requested."""
    from src.contracts.distribution import CapabilityNotSupportedError

    X_train, y_train = make_dummy_data(n=100, seed=55)
    X_val, _ = make_dummy_data(n=20, seed=66)

    model = P5QuantileRegressionCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    assert not pred.metadata.get("capabilities", {}).get("has_sampler", False)
    with pytest.raises(CapabilityNotSupportedError, match="Generative sampling is unsupported"):
        pred.sample(10, seed=202601)
