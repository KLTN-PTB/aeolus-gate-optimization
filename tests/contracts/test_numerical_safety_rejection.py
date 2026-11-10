"""Tests for Fail-Closed Numerical Safety Rejection.

Protocol: Phase 4 Common Distribution Contract
Tests:
- Rejection of NaN values
- Rejection of Infinite values
- Rejection of invalid sigma (<= 0)
- Rejection of invalid degrees of freedom (df <= 2.0)
- Rejection of quantile crossing / non-monotonicity
- Rejection of invalid probabilities (< 0 or > 1)
- Rejection of invalid sample shapes
"""

from __future__ import annotations

import numpy as np
import pytest

from src.contracts.distribution import (
    DistributionValidationError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    QuantilePredictiveDistribution,
)


def test_reject_nan_in_gaussian_distribution() -> None:
    """Verify that Gaussian distributions reject NaN in mu or sigma."""
    mu_nan = np.array([0.0, np.nan, 5.0])
    sigma_valid = np.array([1.0, 1.0, 1.0])
    dist_nan_mu = GaussianResidualDistribution(mu=mu_nan, sigma=sigma_valid)
    with pytest.raises(DistributionValidationError, match="Gaussian mu contains NaN or Inf"):
        dist_nan_mu.validate()

    mu_valid = np.array([0.0, 1.0, 5.0])
    sigma_nan = np.array([1.0, np.nan, 2.0])
    dist_nan_sigma = GaussianResidualDistribution(mu=mu_valid, sigma=sigma_nan)
    with pytest.raises(DistributionValidationError, match="Gaussian sigma contains NaN or Inf"):
        dist_nan_sigma.validate()


def test_reject_inf_in_gaussian_distribution() -> None:
    """Verify that Gaussian distributions reject Inf."""
    mu_inf = np.array([0.0, np.inf, 5.0])
    sigma_valid = np.array([1.0, 1.0, 1.0])
    dist = GaussianResidualDistribution(mu=mu_inf, sigma=sigma_valid)
    with pytest.raises(DistributionValidationError, match="Gaussian mu contains NaN or Inf"):
        dist.validate()


def test_reject_non_positive_sigma() -> None:
    """Verify that Gaussian distributions reject non-positive sigma (<= 0)."""
    mu_valid = np.array([0.0, 1.0])
    sigma_zero = np.array([1.0, 0.0])
    dist = GaussianResidualDistribution(mu=mu_valid, sigma=sigma_zero)
    with pytest.raises(DistributionValidationError, match="strictly positive"):
        dist.validate()

    sigma_neg = np.array([1.0, -0.5])
    dist_neg = GaussianResidualDistribution(mu=mu_valid, sigma=sigma_neg)
    with pytest.raises(DistributionValidationError, match="strictly positive"):
        dist_neg.validate()


def test_reject_invalid_student_t_parameters() -> None:
    """Verify that Student-T rejects df <= 2.0 or negative sigma."""
    mu = np.array([10.0])
    sigma = np.array([2.0])
    df_invalid = np.array([1.5])  # Inf variance

    dist = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df_invalid)
    # The adapter floors df to 2.1 internally; if we inject invalid df directly into _df:
    dist._df = df_invalid
    with pytest.raises(DistributionValidationError, match="strictly > 2.0"):
        dist.validate()


def test_reject_quantile_crossing_in_quantile_distribution() -> None:
    """Verify that QuantilePredictiveDistribution rejects quantile crossing."""
    # Crossing: q(0.75) < q(0.25)
    quantiles_crossing = {
        0.25: np.array([10.0, 20.0]),
        0.50: np.array([12.0, 18.0]),
        0.75: np.array([8.0, 25.0]),  # Crossing on flight 0: 8.0 < 10.0
    }
    dist = QuantilePredictiveDistribution(quantiles_dict=quantiles_crossing)
    with pytest.raises(DistributionValidationError, match="Quantile crossing detected"):
        dist.validate()


def test_reject_nan_in_quantile_distribution() -> None:
    """Verify that QuantilePredictiveDistribution rejects NaN in quantiles."""
    quantiles_nan = {
        0.25: np.array([10.0, 20.0]),
        0.50: np.array([12.0, np.nan]),
        0.75: np.array([15.0, 25.0]),
    }
    dist = QuantilePredictiveDistribution(quantiles_dict=quantiles_nan)
    with pytest.raises(DistributionValidationError, match="contains NaN or Inf"):
        dist.validate()


def test_reject_invalid_probabilities_in_empirical_distribution() -> None:
    """Verify that EmpiricalDistribution rejects probabilities outside [0, 1]."""
    dist = EmpiricalDistribution(
        mean_vals=np.array([10.0]),
        median_vals=np.array([10.0]),
        quantiles_dict={0.5: np.array([10.0])},
        p_ge_15_vals=np.array([1.25]),  # Invalid probability > 1
        sample_pool_list=[np.array([5.0, 10.0, 15.0])],
    )
    with pytest.raises(DistributionValidationError, match="probability_ge out of"):
        dist.validate()


def test_reject_invalid_sample_count() -> None:
    """Verify that negative or zero sample count is rejected."""
    dist = GaussianResidualDistribution(mu=np.array([0.0]), sigma=np.array([1.0]))
    with pytest.raises(ValueError, match="must be positive"):
        dist.sample(0)

    with pytest.raises(ValueError, match="must be positive"):
        dist.sample(-5)
