"""Tests for Mathematically Exact Student-T Implementation.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 3, 4, 7
Verifies:
1. Numerically stable log[T_nu(b) - T_nu(a)] across extreme tails.
2. Parameter guard enforcement (sigma >= 1.0, df >= 2.1).
3. Exact discrete integer quantile semantics vs integer bisection.
4. Analytical Student-t CRPS vs adaptive numerical integration.
5. Consistent discrete event probabilities P(Y >= k) = 1 - F(k - 1).
6. Discrete total probability mass normalization.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import t as student_t

from src.models.probabilistic.student_t_correctness import (
    StudentTDistribution,
    analytical_student_t_crps,
    log_student_t_diff,
)


def test_log_student_t_diff_extreme_tails() -> None:
    """Verify log_student_t_diff is finite, non-zero, and accurate in extreme tails."""
    df = 3.5

    # Center regime
    res_center = log_student_t_diff(-1.0, 1.0, df)
    expected_center = np.log(student_t.cdf(1.0, df=df) - student_t.cdf(-1.0, df=df))
    assert np.isclose(res_center, expected_center, atol=1e-12)

    # Right tail: [15, 20]
    res_rt = log_student_t_diff(15.0, 20.0, df)
    assert np.isfinite(res_rt)
    assert res_rt < -9.0  # tiny probability, but finite log

    # Compare against direct logsf ratio
    log_sf_15 = student_t.logsf(15.0, df=df)
    log_sf_20 = student_t.logsf(20.0, df=df)
    assert res_rt < log_sf_15
    assert res_rt > log_sf_20

    # Left tail: [-25, -20]
    res_lt = log_student_t_diff(-25.0, -20.0, df)
    assert np.isfinite(res_lt)
    assert res_lt < -9.0

    # Inverted interval must return -inf
    res_inv = log_student_t_diff(2.0, 1.0, df)
    assert np.isneginf(res_inv)


def test_student_t_parameter_guards() -> None:
    """Verify parameter floors: sigma >= 1.0, df >= 2.1."""
    # Valid parameters
    dist = StudentTDistribution(mu=5.0, sigma=2.0, df=3.0)
    assert dist.sigma == 2.0
    assert dist.df == 3.0

    # Under-floor sigma must raise ValueError
    with pytest.raises(ValueError, match="sigma must be strictly >= sigma_floor"):
        StudentTDistribution(mu=5.0, sigma=0.5, df=3.0, sigma_floor=1.0)

    # Under-floor df must raise ValueError
    with pytest.raises(ValueError, match="degrees of freedom df must be strictly >= df_floor"):
        StudentTDistribution(mu=5.0, sigma=2.0, df=1.5, df_floor=2.1)


def test_student_t_discrete_total_probability_mass() -> None:
    """Verify discrete integer PMF sums to 1.0 over support."""
    dist = StudentTDistribution(mu=10.0, sigma=5.0, df=4.0, discrete=True)
    y_grid = np.arange(-150, 170)
    probs = dist.prob(y_grid)

    assert np.all(probs >= 0.0)
    total_mass = np.sum(probs)
    assert np.isclose(total_mass, 1.0, atol=1e-4)


def test_student_t_exact_discrete_quantile_vs_bisection() -> None:
    """Verify exact integer quantile formula matches discrete bisection for all probabilities."""
    mu, sigma, df = 12.3, 7.8, 3.2
    dist = StudentTDistribution(mu=mu, sigma=sigma, df=df, discrete=True)

    test_ps = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]

    for p in test_ps:
        q_exact = dist.quantile(p)
        assert isinstance(q_exact, (int, np.integer))

        # Discrete bisection definition: min{ y in Z : F(y) >= p }
        low, high = int(mu - 20 * sigma), int(mu + 20 * sigma)
        bisection_q = high
        while low <= high:
            mid = (low + high) // 2
            if dist.cdf(mid) >= p:
                bisection_q = mid
                high = mid - 1
            else:
                low = mid + 1

        assert q_exact == bisection_q, f"Mismatch at p={p}: exact={q_exact}, bisection={bisection_q}"
        # Property of quantile: F(q) >= p and F(q - 1) < p
        assert dist.cdf(q_exact) >= p
        assert dist.cdf(q_exact - 1) < p


def test_student_t_analytical_crps_vs_numerical_quadrature() -> None:
    """Verify analytical Student-T CRPS matches numerical quadrature of (F(t) - 1(t>=y))^2 dt."""
    mu, sigma, df = 5.0, 4.0, 3.5
    test_ys = [-10.0, 0.0, 5.0, 15.0, 30.0]

    for y in test_ys:
        analytical_val = analytical_student_t_crps(y, mu, sigma, df)

        # Numerical integration of definition: int_-inf^inf [F(t) - 1(t >= y)]^2 dt
        def integrand(t: float) -> float:
            F_t = student_t.cdf((t - mu) / sigma, df=df)
            indicator = 1.0 if t >= y else 0.0
            return float((F_t - indicator) ** 2)

        numerical_val, _ = quad(integrand, -150.0, 150.0, epsabs=1e-7, epsrel=1e-7)
        assert np.isclose(analytical_val, numerical_val, rtol=1e-4, atol=1e-4)


def test_student_t_event_probability_consistency() -> None:
    """Verify discrete P(Y >= k) = 1 - F(k - 1) consistently."""
    dist = StudentTDistribution(mu=8.0, sigma=6.0, df=3.0, discrete=True)

    for k in (15, 60, 120):
        p_event = dist.event_prob(k)
        # By definition: P(Y >= k) = 1 - P(Y <= k - 1) = 1 - F(k - 1)
        expected_p = 1.0 - dist.cdf(k - 1)
        assert np.isclose(p_event, expected_p, atol=1e-12)


def test_student_t_sampling() -> None:
    """Verify discrete Student-T sampling produces integer arrays with consistent sample moments."""
    dist = StudentTDistribution(mu=20.0, sigma=8.0, df=5.0, discrete=True)
    rng = np.random.default_rng(202601)

    draws = dist.sample(10000, rng=rng)
    assert np.issubdtype(draws.dtype, np.integer)
    assert np.isclose(np.mean(draws), 20.0, atol=0.5)
