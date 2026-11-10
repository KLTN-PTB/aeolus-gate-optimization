"""Tests for Distribution Contract Properties, Known Distributions, and Invariants.

Protocol: Phase 4 Common Distribution Contract
Tests:
- Known analytical distributions match mathematical expectations
- Batch form handling across scalar, vector, and grid inputs
- CDF non-decreasing property
- Quantile monotonicity across alpha grid
- Sample shape and seed determinism
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm, t as student_t

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    QuantilePredictiveDistribution,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


def test_gaussian_residual_distribution_known_properties() -> None:
    """Verify GaussianResidualDistribution on known standard Normal N(0, 1)."""
    mu = np.array([0.0, 10.0])
    sigma = np.array([1.0, 2.0])
    dist = GaussianResidualDistribution(mu=mu, sigma=sigma)

    # 1. Mean and Median
    np.testing.assert_allclose(dist.mean(), mu)
    np.testing.assert_allclose(dist.median(), mu)

    # 2. Scalar Quantile
    q_50 = dist.quantile(0.50)
    np.testing.assert_allclose(q_50, mu)
    q_975 = dist.quantile(0.975)
    np.testing.assert_allclose(q_975, mu + sigma * 1.959964, atol=1e-4)

    # 3. Batch Quantiles: shape (K, N)
    alphas = [0.10, 0.50, 0.90]
    q_batch = dist.quantile(alphas)
    assert q_batch.shape == (3, 2)
    np.testing.assert_allclose(q_batch[1], mu)

    # 4. CDF scalar and vector
    cdf_mu = dist.cdf(mu)  # pointwise vector: F_0(0.0), F_1(10.0)
    np.testing.assert_allclose(cdf_mu, np.array([0.5, 0.5]))

    # 5. Probability >= threshold
    p_ge_0 = dist.probability_ge(0.0)
    assert p_ge_0[0] == pytest.approx(0.5)

    # 6. Sampling shape and determinism
    samples_1 = dist.sample(100, seed=42)
    assert samples_1.shape == (100, 2)
    samples_1_again = dist.sample(100, seed=42)
    np.testing.assert_array_equal(samples_1, samples_1_again)

    # Statistical check of sample mean
    sample_means = np.mean(samples_1, axis=0)
    np.testing.assert_allclose(sample_means, mu, atol=0.3)


def test_student_t_distribution_known_properties() -> None:
    """Verify NGBoostStudentTDistribution on known Student-T with df=5."""
    mu = np.array([5.0])
    sigma = np.array([3.0])
    df = np.array([5.0])
    dist = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df)

    # Mean and Median equal mu
    assert float(dist.mean()[0]) == 5.0
    assert float(dist.median()[0]) == 5.0

    # CDF at mu is 0.5
    assert float(dist.cdf(5.0)[0]) == pytest.approx(0.5)

    # Quantile at 0.5 is mu
    assert float(dist.quantile(0.5)[0]) == pytest.approx(5.0)

    # Quantile at 0.975 matches scipy student_t.ppf
    expected_q975 = 5.0 + 3.0 * student_t.ppf(0.975, df=5.0)
    assert float(dist.quantile(0.975)[0]) == pytest.approx(expected_q975, abs=1e-5)

    # Sampling determinism
    s1 = dist.sample(50, seed=123)
    s2 = dist.sample(50, seed=123)
    np.testing.assert_array_equal(s1, s2)


def test_empirical_distribution_known_properties() -> None:
    """Verify EmpiricalDistribution on known discrete historical samples."""
    # Flight 0 has sample pool [10, 20, 30, 40, 50] -> mean=30, median=30
    # Flight 1 has sample pool [0, 0, 10, 10, 30] -> mean=10, median=10
    pool0 = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    pool1 = np.array([0.0, 0.0, 10.0, 10.0, 30.0])
    pools = [pool0, pool1]

    mean_vals = np.array([30.0, 10.0])
    median_vals = np.array([30.0, 10.0])
    quantiles_dict = {
        0.50: np.array([30.0, 10.0]),
        0.10: np.array([14.0, 0.0]),
        0.90: np.array([46.0, 22.0]),
    }
    p_ge_15 = np.array([4.0 / 5.0, 1.0 / 5.0])  # 4/5 >= 15 for flight 0; 1/5 >= 15 for flight 1

    dist = EmpiricalDistribution(
        mean_vals=mean_vals,
        median_vals=median_vals,
        quantiles_dict=quantiles_dict,
        p_ge_15_vals=p_ge_15,
        sample_pool_list=pools,
    )

    np.testing.assert_allclose(dist.mean(), mean_vals)
    np.testing.assert_allclose(dist.median(), median_vals)
    np.testing.assert_allclose(dist.probability_ge(15.0), p_ge_15)

    # CDF checks
    # Flight 0: 3 out of 5 values <= 30.0 -> F(30) = 0.60
    # Flight 1: 4 out of 5 values <= 10.0 -> F(10) = 0.80
    assert float(dist.cdf(30.0)[0]) == pytest.approx(0.60)
    assert float(dist.cdf(10.0)[1]) == pytest.approx(0.80)

    # Sampling from empirical pool
    draws = dist.sample(100, seed=777)
    assert draws.shape == (100, 2)
    # Every draw for flight 0 must be in pool0
    assert set(draws[:, 0]).issubset(set(pool0))


def test_quantile_predictive_distribution_contract() -> None:
    """Verify QuantilePredictiveDistribution adheres strictly to Phase 4 rules."""
    alphas = [0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975]
    n_flights = 5
    quantiles_dict = {
        a: np.full(n_flights, float(a * 100.0)) for a in alphas
    }
    dist = QuantilePredictiveDistribution(quantiles_dict=quantiles_dict)

    # 1. Quantile and median supported
    np.testing.assert_allclose(dist.median(), np.full(n_flights, 50.0))
    np.testing.assert_allclose(dist.quantile(0.5), np.full(n_flights, 50.0))
    np.testing.assert_allclose(dist.quantile(0.1), np.full(n_flights, 10.0))

    # 2. Linear interpolation between registered alphas
    # Alpha 0.30 is between 0.25 (25.0) and 0.50 (50.0) -> 30.0
    np.testing.assert_allclose(dist.quantile(0.30), np.full(n_flights, 30.0))

    # 3. Mean unsupported -> raises CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = dist.mean()

    # 4. Continuous CDF unsupported -> raises CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = dist.cdf(25.0)

    # 5. Event probability unsupported -> raises CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = dist.probability_ge(15.0)

    # 6. Generative sampling unsupported -> raises CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = dist.sample(10)


def test_cdf_monotonicity_across_distributions() -> None:
    """Verify that CDF is non-decreasing across delay domain for all CDF-supporting distributions."""
    mu = np.array([5.0, 15.0, -10.0])
    sigma = np.array([8.0, 12.0, 5.0])
    df = np.array([4.0, 6.0, 10.0])

    dists: list[PredictiveDistribution] = [
        GaussianResidualDistribution(mu=mu, sigma=sigma),
        NGBoostNormalDistribution(mu=mu, sigma=sigma),
        NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df),
    ]

    grid = np.linspace(-60.0, 120.0, 50)
    for dist in dists:
        for i in range(len(grid) - 1):
            f_low = dist.cdf(grid[i])
            f_high = dist.cdf(grid[i + 1])
            # F(grid[i]) <= F(grid[i+1])
            assert np.all(f_low <= f_high + 1e-7), f"CDF decreased between {grid[i]} and {grid[i+1]}"


def test_quantile_monotonicity_across_distributions() -> None:
    """Verify that quantiles are non-decreasing across alpha grid."""
    mu = np.array([5.0, 15.0, -10.0])
    sigma = np.array([8.0, 12.0, 5.0])
    df = np.array([4.0, 6.0, 10.0])

    alphas = sorted(PRE_REGISTERED_QUANTILES)
    dists: list[PredictiveDistribution] = [
        GaussianResidualDistribution(mu=mu, sigma=sigma),
        NGBoostNormalDistribution(mu=mu, sigma=sigma),
        NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df),
    ]

    for dist in dists:
        for j in range(len(alphas) - 1):
            q_low = dist.quantile(alphas[j])
            q_high = dist.quantile(alphas[j + 1])
            assert np.all(q_low <= q_high + 1e-6), f"Quantile inversion between alpha {alphas[j]} and {alphas[j+1]}"
