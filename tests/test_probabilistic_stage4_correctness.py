"""Stage 4 — Dedicated MDN and Distributional Correctness Test Suite.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 7 (Stage 4)

Test Groups:
A. Parameter validity (non-negative weights, sum to 1, sigma >= floor, finite outputs).
B. Numerical correctness (finite log-prob, finite gradients, no NaN/Inf under extreme inputs, stable tails).
C. CDF / quantile correctness (monotonicity, boundaries, sampling validity).
D. Discrete likelihood (total probability convergence, event probability consistency with CDF, integer quantile definition).
E. Permutation invariance (invariance of PMF, CDF, CRPS, quantiles, and entropy under component relabeling).
F. Synthetic recovery (distributional recovery from known registered mixture).
G. Degeneracy & boundaries (near-zero sigma, sigma floor, dead component handling, initialization robustness).
H. Real ATL pipeline smoke test (tiny 50-row forward/backward check without real model training).
"""

from __future__ import annotations

import itertools
import numpy as np
import pytest
from scipy.stats import kstest
import torch

from src.models.probabilistic.contracts import DEFAULT_SIGMA_FLOOR
from src.models.probabilistic.correctness import (
    GaussianMixtureDistribution,
    compute_distributional_recovery_metrics,
    fit_synthetic_mixture,
    permute_mixture_parameters,
)
from src.models.probabilistic.distribution_ablation import (
    DistributionLadderCandidate,
    Stage3DistributionModel,
    Stage3DistributionPreprocessor,
    discretized_mixture_nll_torch,
    gaussian_mixture_crps,
    log_ndtr_diff_torch,
    vectorized_discrete_mixture_quantile,
)
from src.models.probabilistic.likelihood import (
    discrete_mixture_cdf,
    discrete_mixture_quantile,
    discretized_mixture_log_prob,
    log1mexp,
    log_ndtr_diff,
)


# =============================================================================
# A. Parameter Validity
# =============================================================================

def test_parameter_validity_mixture_weights_nonnegative():
    """Verify negative mixture weights are strictly rejected."""
    with pytest.raises(ValueError, match="Mixture weights must be non-negative"):
        GaussianMixtureDistribution(pi=[0.8, -0.1, 0.3], mu=[0, 10, 20], sigma=[5, 5, 5])


def test_parameter_validity_weights_sum_to_one():
    """Verify weights summing far from 1.0 are rejected, while valid weights sum to 1.0 within tolerance."""
    with pytest.raises(ValueError, match="must sum to 1.0"):
        GaussianMixtureDistribution(pi=[0.5, 0.2, 0.1], mu=[0, 10, 20], sigma=[5, 5, 5])

    dist = GaussianMixtureDistribution(pi=[0.6, 0.3, 0.1], mu=[-2, 15, 45], sigma=[4, 10, 20])
    assert np.isclose(np.sum(dist.pi), 1.0, atol=1e-6)
    assert np.all(dist.pi >= 0.0)


def test_parameter_validity_sigma_strictly_positive():
    """Verify sigma below floor is strictly rejected."""
    with pytest.raises(ValueError, match="strictly >= sigma_floor"):
        GaussianMixtureDistribution(pi=[0.5, 0.5], mu=[0, 10], sigma=[0.5, 2.0], sigma_floor=1.0)

    dist = GaussianMixtureDistribution(pi=[0.7, 0.3], mu=[0, 10], sigma=[1.0, 5.0], sigma_floor=1.0)
    assert np.all(dist.sigma >= 1.0)


def test_parameter_validity_finite_outputs():
    """Verify model forward produces strictly finite pi, mu, sigma across random inputs."""
    model = Stage3DistributionModel(
        candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
        num_continuous=10,
        num_carriers=5,
        num_origins=10,
        k_components=3,
        sigma_floor=DEFAULT_SIGMA_FLOOR,
    )
    x_cont = torch.randn(50, 10) * 10.0
    x_c = torch.randint(0, 5, (50,))
    x_o = torch.randint(0, 10, (50,))
    x_fl = torch.rand(50, 1)

    pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)

    assert torch.all(torch.isfinite(pi))
    assert torch.all(torch.isfinite(mu))
    assert torch.all(torch.isfinite(sigma))
    assert torch.all(pi >= 0.0)
    assert torch.allclose(pi.sum(dim=-1), torch.ones(50), atol=1e-5)
    assert torch.all(sigma >= DEFAULT_SIGMA_FLOOR)


# =============================================================================
# B. Numerical Correctness
# =============================================================================

def test_numerical_correctness_finite_log_probability_extremes():
    """Verify log-probability is finite across normal and extreme observations."""
    dist = GaussianMixtureDistribution(
        pi=[0.6, 0.3, 0.1],
        mu=[-2.0, 18.0, 55.0],
        sigma=[5.0, 12.0, 24.0],
        discrete=True,
    )
    y_test = np.array([-500.0, -100.0, -5.0, 0.0, 15.0, 60.0, 500.0, 2000.0])
    log_probs = dist.log_prob(y_test)

    assert np.all(np.isfinite(log_probs))
    # Extreme tails must have very negative log probabilities without NaN or Inf
    assert log_probs[0] < -100.0
    assert log_probs[-1] < -100.0


def test_numerical_correctness_finite_gradients():
    """Verify loss backward pass produces strictly finite gradients for extreme targets."""
    bs = 8
    pi_raw = torch.randn(bs, 3, requires_grad=True)
    mu = torch.randn(bs, 3, requires_grad=True)
    sigma_raw = torch.randn(bs, 3, requires_grad=True)

    pi = torch.softmax(pi_raw, dim=-1)
    sigma = torch.nn.functional.softplus(sigma_raw) + 1.0

    # Include extreme positive delay and negative delay
    y = torch.tensor([-45.0, 0.0, 10.0, 25.0, 120.0, 450.0, 800.0, 1500.0])
    loss = discretized_mixture_nll_torch(y, pi, mu, sigma)

    loss.backward()

    assert torch.isfinite(loss)
    assert torch.all(torch.isfinite(pi_raw.grad))
    assert torch.all(torch.isfinite(mu.grad))
    assert torch.all(torch.isfinite(sigma_raw.grad))


def test_numerical_correctness_extreme_inputs_no_nan_inf():
    """Verify model forward pass remains completely finite under 50-sigma input spikes."""
    model = Stage3DistributionModel(
        candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
        num_continuous=10,
        num_carriers=5,
        num_origins=10,
        k_components=3,
    )
    # Extreme input feature values (+-50.0)
    x_cont = torch.tensor([[50.0] * 10, [-50.0] * 10])
    x_c = torch.tensor([0, 4])
    x_o = torch.tensor([0, 9])
    x_fl = torch.tensor([[100.0], [-100.0]])

    pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)

    assert torch.all(torch.isfinite(pi))
    assert torch.all(torch.isfinite(mu))
    assert torch.all(torch.isfinite(sigma))


def test_numerical_correctness_stable_deep_tails():
    """Verify log_ndtr_diff and PyTorch counterpart across deep tails."""
    # Left tail (a, b << -10)
    a_left = torch.tensor([-30.0, -20.0, -10.0])
    b_left = a_left + 1.0
    res_left = log_ndtr_diff_torch(a_left, b_left)
    assert torch.all(torch.isfinite(res_left))
    assert torch.all(res_left < -30.0)

    # Right tail (a, b >> 10)
    a_right = torch.tensor([10.0, 20.0, 30.0])
    b_right = a_right + 1.0
    res_right = log_ndtr_diff_torch(a_right, b_right)
    assert torch.all(torch.isfinite(res_right))
    assert torch.all(res_right < -30.0)


# =============================================================================
# C. CDF / Quantile Correctness
# =============================================================================

def test_cdf_monotonicity():
    """Verify CDF is non-decreasing everywhere."""
    dist = GaussianMixtureDistribution(
        pi=[0.5, 0.3, 0.2],
        mu=[-5.0, 10.0, 40.0],
        sigma=[4.0, 8.0, 20.0],
        discrete=True,
    )
    y_grid = np.linspace(-40.0, 120.0, 500)
    cdf_vals = dist.cdf(y_grid)

    diffs = np.diff(cdf_vals)
    assert np.all(diffs >= -1e-12), "CDF exhibited non-monotonic decrease"


def test_cdf_limits_minus_plus_infinity():
    """Verify CDF limits at -inf is 0.0 and +inf is 1.0."""
    dist = GaussianMixtureDistribution(
        pi=[0.6, 0.3, 0.1],
        mu=[0.0, 20.0, 60.0],
        sigma=[5.0, 10.0, 25.0],
        discrete=True,
    )
    assert dist.cdf(-1000.0) < 1e-15
    assert dist.cdf(1000.0) > 1.0 - 1e-15


def test_quantile_monotonicity():
    """Verify quantiles are strictly monotonic with respect to probability level."""
    dist = GaussianMixtureDistribution(
        pi=[0.5, 0.35, 0.15],
        mu=[-3.0, 12.0, 50.0],
        sigma=[4.0, 9.0, 22.0],
        discrete=True,
    )
    p_levels = [0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99]
    quantiles = [dist.quantile(p) for p in p_levels]

    for i in range(len(quantiles) - 1):
        assert quantiles[i] <= quantiles[i + 1], f"Quantile inversion: Q({p_levels[i]}) > Q({p_levels[i+1]})"


def test_sampling_matches_mixture_distribution():
    """Verify empirical distribution of samples matches theoretical mixture via Kolmogorov-Smirnov test."""
    dist = GaussianMixtureDistribution(
        pi=[0.6, 0.3, 0.1],
        mu=[5.0, 25.0, 60.0],
        sigma=[5.0, 10.0, 20.0],
        discrete=False,  # continuous for KS test
    )
    rng = np.random.default_rng(202604)
    samples = dist.sample(10000, rng=rng)

    ks_res = kstest(samples, dist.cdf)
    # p-value > 0.01 confirms samples are generated from the true mixture distribution
    assert ks_res.pvalue > 0.01, f"KS test rejected sampling distribution: p={ks_res.pvalue:.4f}"


# =============================================================================
# D. Discrete Likelihood Properties
# =============================================================================

def test_discrete_likelihood_total_probability_converges():
    """Verify sum of discrete probabilities over large integer support converges to 1.0."""
    dist = GaussianMixtureDistribution(
        pi=[0.55, 0.35, 0.10],
        mu=[-2.0, 15.0, 50.0],
        sigma=[4.0, 10.0, 22.0],
        discrete=True,
    )
    y_support = np.arange(-150, 250)
    probs = dist.prob(y_support)

    total_prob = np.sum(probs)
    assert np.isclose(total_prob, 1.0, atol=1e-7), f"Total discrete mass was {total_prob}"


def test_discrete_likelihood_event_probabilities_consistent_with_cdf():
    """Verify P(Y >= T) computed by summing PMF matches 1 - F(T - 1)."""
    dist = GaussianMixtureDistribution(
        pi=[0.6, 0.3, 0.1],
        mu=[-1.0, 16.0, 45.0],
        sigma=[5.0, 11.0, 20.0],
        discrete=True,
    )
    thresholds = [15, 60, 120]
    for t in thresholds:
        # 1. Via CDF: P(Y >= T) = 1 - P(Y <= T - 1) = 1 - F(T - 1)
        prob_cdf = 1.0 - dist.cdf(t - 1)

        # 2. Via PMF summation: sum_{y=t}^{500} P(Y = y)
        support = np.arange(t, 600)
        prob_pmf = np.sum(dist.prob(support))

        assert np.isclose(prob_cdf, prob_pmf, atol=1e-6), (
            f"Event P(Y >= {t}) inconsistent: cdf={prob_cdf:.6f}, pmf={prob_pmf:.6f}"
        )


def test_discrete_likelihood_integer_quantile_definition():
    """Verify integer quantile satisfies: F(Q(p) - 1) < p <= F(Q(p))."""
    dist = GaussianMixtureDistribution(
        pi=[0.5, 0.35, 0.15],
        mu=[-4.0, 14.0, 48.0],
        sigma=[5.0, 10.0, 25.0],
        discrete=True,
    )
    for p in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]:
        q = dist.quantile(p)
        assert isinstance(q, (int, np.integer))

        cdf_at_q = dist.cdf(q)
        cdf_below_q = dist.cdf(q - 1)

        assert cdf_at_q >= p, f"For p={p}, cdf(Q(p))={cdf_at_q} was < p"
        assert cdf_below_q < p, f"For p={p}, cdf(Q(p)-1)={cdf_below_q} was >= p"


# =============================================================================
# E. Permutation Invariance
# =============================================================================

def test_permutation_invariance_density_and_mass():
    """Verify permuting component order leaves PMF and CDF strictly invariant."""
    pi = np.array([0.5, 0.3, 0.2])
    mu = np.array([-3.0, 15.0, 60.0])
    sigma = np.array([5.0, 12.0, 25.0])
    base_dist = GaussianMixtureDistribution(pi, mu, sigma, discrete=True)

    grid = np.linspace(-30.0, 100.0, 50)
    base_pmf = base_dist.prob(grid)
    base_cdf = base_dist.cdf(grid)

    for perm in itertools.permutations([0, 1, 2]):
        p_pi, p_mu, p_sigma = permute_mixture_parameters(pi, mu, sigma, perm)
        p_dist = GaussianMixtureDistribution(p_pi, p_mu, p_sigma, discrete=True)

        assert np.allclose(base_pmf, p_dist.prob(grid), atol=1e-12)
        assert np.allclose(base_cdf, p_dist.cdf(grid), atol=1e-12)


def test_permutation_invariance_cdf_and_crps():
    """Verify permuting component order leaves exact mixture CRPS strictly invariant."""
    pi = np.array([0.6, 0.25, 0.15])
    mu = np.array([-2.0, 20.0, 70.0])
    sigma = np.array([4.0, 10.0, 30.0])
    base_dist = GaussianMixtureDistribution(pi, mu, sigma, discrete=True)

    y_test = np.array([-10.0, 0.0, 15.0, 50.0, 120.0])
    base_crps = base_dist.crps(y_test)

    for perm in itertools.permutations([0, 1, 2]):
        p_pi, p_mu, p_sigma = permute_mixture_parameters(pi, mu, sigma, perm)
        p_dist = GaussianMixtureDistribution(p_pi, p_mu, p_sigma, discrete=True)

        assert np.allclose(base_crps, p_dist.crps(y_test), atol=1e-12)


def test_permutation_invariance_quantiles():
    """Verify quantiles are identical under all permutations."""
    pi = np.array([0.55, 0.30, 0.15])
    mu = np.array([-5.0, 12.0, 50.0])
    sigma = np.array([4.0, 11.0, 20.0])
    base_dist = GaussianMixtureDistribution(pi, mu, sigma, discrete=True)

    p_levels = [0.10, 0.50, 0.90]
    base_q = [base_dist.quantile(p) for p in p_levels]

    for perm in itertools.permutations([0, 1, 2]):
        p_pi, p_mu, p_sigma = permute_mixture_parameters(pi, mu, sigma, perm)
        p_dist = GaussianMixtureDistribution(p_pi, p_mu, p_sigma, discrete=True)

        p_q = [p_dist.quantile(p) for p in p_levels]
        assert base_q == p_q


def test_permutation_invariance_entropy_and_neff():
    """Verify entropy and effective component count are strictly permutation invariant."""
    pi = np.array([0.7, 0.2, 0.1])
    mu = np.array([0.0, 10.0, 20.0])
    sigma = np.array([5.0, 5.0, 5.0])
    base_dist = GaussianMixtureDistribution(pi, mu, sigma, discrete=True)

    base_entropy = base_dist.component_entropy
    base_neff = base_dist.effective_components

    for perm in itertools.permutations([0, 1, 2]):
        p_pi, p_mu, p_sigma = permute_mixture_parameters(pi, mu, sigma, perm)
        p_dist = GaussianMixtureDistribution(p_pi, p_mu, p_sigma, discrete=True)

        assert np.isclose(base_entropy, p_dist.component_entropy, atol=1e-14)
        assert np.isclose(base_neff, p_dist.effective_components, atol=1e-14)


# =============================================================================
# F. Synthetic Recovery
# =============================================================================

def test_synthetic_recovery_distributional_metrics():
    """Verify the implementation recovers a known synthetic mixture distribution."""
    true_pi = np.array([0.65, 0.35], dtype=np.float64)
    true_mu = np.array([-2.0, 25.0], dtype=np.float64)
    true_sigma = np.array([5.0, 15.0], dtype=np.float64)
    true_dist = GaussianMixtureDistribution(true_pi, true_mu, true_sigma, discrete=True)

    rng = np.random.default_rng(42)
    y_synth = true_dist.sample(8000, rng=rng)

    fit_dist, _ = fit_synthetic_mixture(
        y_train=y_synth,
        k_components=2,
        n_epochs=120,
        batch_size=512,
        lr=0.08,
        seed=42,
    )

    recovery = compute_distributional_recovery_metrics(
        true_dist,
        fit_dist,
        ks_threshold=0.04,
        w1_threshold=1.0,
    )

    assert recovery.kolmogorov_smirnov_stat <= 0.04, f"KS stat {recovery.kolmogorov_smirnov_stat} exceeded threshold"
    assert recovery.wasserstein_1_distance <= 1.0, f"Wasserstein-1 dist {recovery.wasserstein_1_distance} exceeded threshold"
    assert recovery.mean_absolute_quantile_error <= 1.5, f"Mean quantile error {recovery.mean_absolute_quantile_error} exceeded threshold"
    assert recovery.crps_absolute_error <= 0.25, f"CRPS error {recovery.crps_absolute_error} exceeded threshold"


# =============================================================================
# G. Degeneracy & Boundaries
# =============================================================================

def test_degeneracy_near_zero_sigma_and_floor():
    """Verify sigma floor prevents division by zero and near-zero sigma collapse."""
    model = Stage3DistributionModel(
        candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
        num_continuous=10,
        num_carriers=5,
        num_origins=10,
        k_components=3,
        sigma_floor=1.0,
    )
    # Deliberately drive raw_sigma layer bias to large negative values
    with torch.no_grad():
        model.sigma_head.bias.fill_(-50.0)

    x_cont = torch.zeros(10, 10)
    x_c = torch.zeros(10, dtype=torch.long)
    x_o = torch.zeros(10, dtype=torch.long)
    x_fl = torch.zeros(10, 1)

    pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)

    # Must be strictly >= sigma_floor (1.0)
    assert torch.all(sigma >= 1.0)
    assert torch.all(torch.isfinite(sigma))

    # Loss must remain finite
    loss = discretized_mixture_nll_torch(torch.zeros(10), pi, mu, sigma)
    assert torch.isfinite(loss)


def test_degeneracy_dead_components_stability():
    """Verify near-zero / dead component weights do not cause NaN or Inf in loss, gradients, or CRPS."""
    dead_dist = GaussianMixtureDistribution(
        pi=[0.999999999, 1e-9, 1e-15],
        mu=[-2.0, 15.0, 50.0],
        sigma=[5.0, 10.0, 20.0],
        discrete=True,
    )
    y_eval = np.array([-5.0, 0.0, 10.0, 50.0])
    log_probs = dead_dist.log_prob(y_eval)
    crps_vals = dead_dist.crps(y_eval)

    assert np.all(np.isfinite(log_probs))
    assert np.all(np.isfinite(crps_vals))
    assert np.isclose(dead_dist.effective_components, 1.0, atol=1e-5)
    assert np.isclose(dead_dist.component_entropy, 0.0, atol=1e-5)


def test_degeneracy_initialization_robustness():
    """Verify that multiple random seed initializations yield finite weights, sigmas >= 1, and finite losses."""
    for test_seed in [42, 101, 2026, 9999, 54321]:
        torch.manual_seed(test_seed)
        model = Stage3DistributionModel(
            candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
            num_continuous=10,
            num_carriers=5,
            num_origins=10,
            k_components=3,
        )
        x_cont = torch.randn(20, 10)
        x_c = torch.randint(0, 5, (20,))
        x_o = torch.randint(0, 10, (20,))
        x_fl = torch.rand(20, 1)

        pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)
        loss = discretized_mixture_nll_torch(torch.randn(20) * 10, pi, mu, sigma)
        loss.backward()

        assert torch.isfinite(loss)
        assert torch.all(sigma >= 1.0)
        for p in model.parameters():
            if p.grad is not None:
                assert torch.all(torch.isfinite(p.grad))
                assert torch.max(torch.abs(p.grad)) < 100.0


# =============================================================================
# H. Real ATL Pipeline Smoke Test (Tiny 50-row forward/backward, No Training)
# =============================================================================

def test_real_atl_pipeline_smoke():
    """Verify real ATL schema passes through preprocessing and model forward/backward on 50 sample rows.

    Per Stage 4 protocol: strictly a tiny smoke test without training the real ATL model.
    """
    sample_df = {
        "CRS_ELAPSED_TIME": np.random.uniform(60, 300, 50),
        "calendar_year": [2018] * 50,
        "calendar_month": np.random.randint(1, 13, 50),
        "calendar_day_of_month": np.random.randint(1, 29, 50),
        "calendar_day_of_week": np.random.randint(1, 8, 50),
        "is_weekend": np.random.randint(0, 2, 50),
        "scheduled_departure_hour": np.random.randint(6, 23, 50),
        "scheduled_departure_minute": np.random.randint(0, 60, 50),
        "OP_CARRIER": np.random.choice(["DL", "AA", "WN", "UA"], 50),
        "ORIGIN": np.random.choice(["ATL", "ORD", "DFW", "LAX"], 50),
        "OP_CARRIER_FL_NUM": [str(x) for x in np.random.randint(100, 999, 50)],
        "ARR_DELAY": np.random.normal(5, 20, 50).round(),
    }
    import pandas as pd
    df = pd.DataFrame(sample_df)

    preprocessor = Stage3DistributionPreprocessor(include_calendar_year=True)
    preprocessor.fit(df)
    batch = preprocessor.transform(df)

    model = Stage3DistributionModel(
        candidate=DistributionLadderCandidate.D3_K3_MIXTURE,
        num_continuous=batch["continuous"].shape[1],
        num_carriers=len(preprocessor.carrier_to_idx_),
        num_origins=len(preprocessor.origin_to_idx_),
        k_components=3,
    )

    x_cont = torch.from_numpy(batch["continuous"]).float()
    x_c = torch.from_numpy(batch["carrier"]).long()
    x_o = torch.from_numpy(batch["origin"]).long()
    x_fl = torch.from_numpy(batch["flight_freq"]).float()
    y_target = torch.from_numpy(df["ARR_DELAY"].values).float()

    pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)
    loss = discretized_mixture_nll_torch(y_target, pi, mu, sigma)
    loss.backward()

    assert torch.isfinite(loss)
    assert pi.shape == (50, 3)
    assert mu.shape == (50, 3)
    assert sigma.shape == (50, 3)
    assert torch.all(sigma >= 1.0)
    for p in model.parameters():
        if p.grad is not None:
            assert torch.all(torch.isfinite(p.grad))
