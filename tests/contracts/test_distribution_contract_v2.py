"""Comprehensive Verification Suite for Task R5: Predictive Distribution Contract V2.

Protocol: Task R5 Predictive Distribution Contract
Coverage:
1. Base API completeness: mean, median, quantile, cdf, probability_ge, sample, validate, metadata, capabilities.
2. Capability Object: explicit 10-field capability accounting without guessing.
3. Fail-Closed behavior: unsupported operations raise explicit CapabilityNotSupportedError.
4. P5 Isolation: cdf=unsupported, mean=unsupported, sample=unsupported, crps_approx=True, crps_exact=False.
5. Batch Vectorization: scalar, 1D pointwise, 2D grid/quantiles, and strict output shapes.
6. Numerical Safety: NaN/Inf, non-positive scale, df <= 2.0, non-monotonic quantiles, q outside (0, 1).
7. Seed Reproducibility: deterministic draws given identical seeds, sensitivity under different seeds.
8. Manifest Validation: artifacts/manifests/distribution_contract_v2.json integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionCapabilities,
    DistributionValidationError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    QuantilePredictiveDistribution,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


# =============================================================================
# Fixtures and Helpers
# =============================================================================

@pytest.fixture
def sample_data() -> dict[str, Any]:
    n = 10
    mu = np.linspace(5.0, 25.0, n)
    sigma = np.linspace(2.0, 6.0, n)
    df = np.full(n, 4.0)

    # Monotone quantiles
    alphas = sorted(PRE_REGISTERED_QUANTILES)
    q_dict = {a: mu + sigma * (i - 4) * 0.8 for i, a in enumerate(alphas)}

    # Empirical pools
    pools = [np.linspace(m - 3 * s, m + 3 * s, 40) for m, s in zip(mu, sigma)]
    p_15 = np.clip((mu - 10.0) / 20.0, 0.0, 1.0)

    return {
        "n": n,
        "mu": mu,
        "sigma": sigma,
        "df": df,
        "q_dict": q_dict,
        "pools": pools,
        "p_15": p_15,
        "alphas": alphas,
    }


# =============================================================================
# 1. Capability Object Structure & Verification
# =============================================================================

def test_distribution_capabilities_object_semantics() -> None:
    """DistributionCapabilities must implement 10 canonical keys, aliases, and .supports()."""
    caps = DistributionCapabilities(
        mean=True,
        median=True,
        quantile=True,
        cdf=True,
        probability_ge=True,
        sample=True,
        nll=True,
        crps_exact=True,
        crps_approx=True,
        pit=True,
    )

    # 1. Canonical keys
    for req in DistributionCapabilities.REQUIRED_CAPABILITIES:
        assert req in caps
        assert caps[req] is True
        assert caps.supports(req) is True

    # 2. Backwards-compatibility aliases
    assert caps["has_mean"] is True
    assert caps["has_quantiles"] is True
    assert caps["has_sampler"] is True
    assert caps["has_crps"] is True
    assert caps.has_mean is True

    # 3. CallableDict semantics
    assert caps() is caps


def test_p5_declared_capabilities_strictly_quantile_only(sample_data: dict[str, Any]) -> None:
    """P5 Quantile regression must explicitly declare supported vs unsupported operations."""
    dist = QuantilePredictiveDistribution(quantiles_dict=sample_data["q_dict"])
    caps = dist.capabilities

    assert isinstance(caps, DistributionCapabilities)
    assert caps.supports("mean") is False
    assert caps.supports("cdf") is False
    assert caps.supports("probability_ge") is False
    assert caps.supports("sample") is False
    assert caps.supports("nll") is False
    assert caps.supports("crps_exact") is False
    assert caps.supports("quantile") is True
    assert caps.supports("median") is True
    assert caps.supports("crps_approx") is True
    assert caps.supports("pit") is False

    assert dist.metadata.get("role") == "QUANTILE_FORECAST_ONLY"


def test_p1_empirical_declared_capabilities(sample_data: dict[str, Any]) -> None:
    """P1 Empirical baseline must declare cdf/quantiles while omitting continuous NLL/PIT."""
    dist = EmpiricalDistribution(
        mean_vals=sample_data["mu"],
        median_vals=sample_data["mu"],
        quantiles_dict=sample_data["q_dict"],
        p_ge_15_vals=sample_data["p_15"],
        sample_pool_list=sample_data["pools"],
    )
    caps = dist.capabilities

    assert isinstance(caps, DistributionCapabilities)
    assert caps.supports("mean") is True
    assert caps.supports("median") is True
    assert caps.supports("quantile") is True
    assert caps.supports("cdf") is True
    assert caps.supports("probability_ge") is True
    assert caps.supports("sample") is True
    assert caps.supports("nll") is False
    assert caps.supports("crps_exact") is False
    assert caps.supports("crps_approx") is True
    assert caps.supports("pit") is False


# =============================================================================
# 2. Fail-Closed Unsupported Operations
# =============================================================================

def test_p5_unsupported_operations_raise_capability_error(sample_data: dict[str, Any]) -> None:
    """Calling unsupported operations on P5 must raise CapabilityNotSupportedError."""
    dist = QuantilePredictiveDistribution(quantiles_dict=sample_data["q_dict"])

    with pytest.raises(CapabilityNotSupportedError, match="conditional expectation"):
        _ = dist.mean()

    with pytest.raises(CapabilityNotSupportedError, match="continuous CDF"):
        _ = dist.cdf(15.0)

    with pytest.raises(CapabilityNotSupportedError, match="Event probability"):
        _ = dist.probability_ge(15.0)

    with pytest.raises(CapabilityNotSupportedError, match="Generative sampling"):
        _ = dist.sample(10)

    # Pre-registered bounds check: extrapolation prohibited
    with pytest.raises(CapabilityNotSupportedError, match="outside pre-registered quantile grid"):
        _ = dist.quantile(0.001)

    with pytest.raises(CapabilityNotSupportedError, match="outside pre-registered quantile grid"):
        _ = dist.quantile(0.999)


# =============================================================================
# 3. Batch Vectorization & Output Shapes
# =============================================================================

def test_quantile_scalar_and_batch_shapes(sample_data: dict[str, Any]) -> None:
    """Quantile query must support scalar alpha -> (N,) and sequence alphas -> (K, N)."""
    n = sample_data["n"]
    dist = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])

    # Scalar float
    q_scalar = dist.quantile(0.50)
    assert q_scalar.shape == (n,)
    np.testing.assert_array_almost_equal(q_scalar, sample_data["mu"], decimal=5)

    # Batch sequence (K=3)
    k_alphas = [0.10, 0.50, 0.90]
    q_batch = dist.quantile(k_alphas)
    assert q_batch.shape == (len(k_alphas), n)

    # Vectorized consistency
    for idx, a in enumerate(k_alphas):
        np.testing.assert_array_almost_equal(q_batch[idx], dist.quantile(a), decimal=5)


def test_cdf_scalar_pointwise_and_grid_shapes(sample_data: dict[str, Any]) -> None:
    """CDF query must support scalar x -> (N,), pointwise array (N,) -> (N,), and grid (M,) -> (M, N)."""
    n = sample_data["n"]
    dist = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])

    # 1. Scalar
    res_scalar = dist.cdf(15.0)
    assert res_scalar.shape == (n,)
    assert np.all((res_scalar >= 0.0) & (res_scalar <= 1.0))

    # 2. Pointwise (N,)
    x_pointwise = np.copy(sample_data["mu"])
    res_pointwise = dist.cdf(x_pointwise)
    assert res_pointwise.shape == (n,)
    # At x = mu, standard Gaussian CDF = 0.50
    np.testing.assert_array_almost_equal(res_pointwise, np.full(n, 0.50), decimal=5)

    # 3. Grid (M=4, where M != N)
    x_grid = np.array([-10.0, 0.0, 15.0, 50.0])
    res_grid = dist.cdf(x_grid)
    assert res_grid.shape == (len(x_grid), n)
    assert np.all((res_grid >= 0.0) & (res_grid <= 1.0))

    # Grid monotonicity across M rows
    for m in range(len(x_grid) - 1):
        assert np.all(res_grid[m] <= res_grid[m + 1] + 1e-7)


def test_probability_ge_shapes_and_bounds(sample_data: dict[str, Any]) -> None:
    """Event probability P(Y >= threshold) must return (N,) bounded in [0, 1]."""
    n = sample_data["n"]
    dist = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])

    # Scalar
    p_scalar = dist.probability_ge(15.0)
    assert p_scalar.shape == (n,)
    assert np.all((p_scalar >= 0.0) & (p_scalar <= 1.0))

    # Vector of shape (N,)
    thr_vec = np.full(n, 15.0)
    p_vec = dist.probability_ge(thr_vec)
    assert p_vec.shape == (n,)
    np.testing.assert_array_almost_equal(p_scalar, p_vec)

    # Monotonicity with respect to threshold: higher threshold -> lower probability
    p_high = dist.probability_ge(60.0)
    assert np.all(p_high <= p_scalar + 1e-7)


# =============================================================================
# 4. Numerical Safety & Validation (Fail-Closed)
# =============================================================================

@pytest.mark.parametrize(
    "invalid_q",
    [-0.5, 0.0, 1.0, 1.2],
)
def test_quantile_rejects_out_of_bounds_alpha(sample_data: dict[str, Any], invalid_q: float) -> None:
    """Quantile must raise ValueError if alpha is not strictly in (0, 1)."""
    dist_gaussian = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])
    with pytest.raises(ValueError, match="alpha must be in"):
        dist_gaussian.quantile(invalid_q)

    dist_student = NGBoostStudentTDistribution(
        mu=sample_data["mu"], sigma=sample_data["sigma"], df=sample_data["df"]
    )
    with pytest.raises(ValueError, match="alpha must be in"):
        dist_student.quantile(invalid_q)

    dist_emp = EmpiricalDistribution(
        mean_vals=sample_data["mu"],
        median_vals=sample_data["mu"],
        quantiles_dict=sample_data["q_dict"],
        p_ge_15_vals=sample_data["p_15"],
        sample_pool_list=sample_data["pools"],
    )
    with pytest.raises(ValueError, match="alpha must be in"):
        dist_emp.quantile(invalid_q)


def test_reject_nan_and_inf_in_parameters(sample_data: dict[str, Any]) -> None:
    """validate() must reject NaN or Inf across all distributions."""
    mu_nan = np.copy(sample_data["mu"])
    mu_nan[3] = np.nan
    with pytest.raises(DistributionValidationError, match="NaN or Inf"):
        dist = GaussianResidualDistribution(mu=mu_nan, sigma=sample_data["sigma"])
        dist.validate()

    sigma_inf = np.copy(sample_data["sigma"])
    sigma_inf[2] = np.inf
    with pytest.raises(DistributionValidationError, match="NaN or Inf"):
        dist = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sigma_inf)
        dist.validate()


def test_reject_non_positive_scale(sample_data: dict[str, Any]) -> None:
    """validate() must reject non-positive scale sigma <= 0."""
    dist_zero = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])
    dist_zero._sigma[0] = 0.0
    with pytest.raises(DistributionValidationError, match="sigma must be strictly positive"):
        dist_zero.validate()

    dist_neg = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])
    dist_neg._sigma[1] = -2.0
    with pytest.raises(DistributionValidationError, match="sigma must be strictly positive"):
        dist_neg.validate()


def test_student_t_rejects_df_le_2(sample_data: dict[str, Any]) -> None:
    """validate() must fail closed if degrees of freedom df <= 2.0."""
    dist = NGBoostStudentTDistribution(
        mu=sample_data["mu"], sigma=sample_data["sigma"], df=sample_data["df"]
    )
    dist.validate()  # Passes initially

    dist._df[0] = 2.0
    with pytest.raises(DistributionValidationError, match="df must be strictly > 2.0"):
        dist.validate()

    dist._df[0] = 1.2
    with pytest.raises(DistributionValidationError, match="df must be strictly > 2.0"):
        dist.validate()


def test_quantile_distribution_rejects_crossing(sample_data: dict[str, Any]) -> None:
    """QuantilePredictiveDistribution must fail closed if quantiles violate monotonicity."""
    corrupted_dict = {k: np.copy(v) for k, v in sample_data["q_dict"].items()}
    # Cross 0.25 and 0.50
    corrupted_dict[0.25][0] = corrupted_dict[0.50][0] + 5.0

    dist = QuantilePredictiveDistribution(quantiles_dict=corrupted_dict)
    with pytest.raises(DistributionValidationError, match="Quantile crossing detected"):
        dist.validate()


# =============================================================================
# 5. Generative Sampling & Seed Reproducibility
# =============================================================================

def test_sampling_shapes_and_seed_reproducibility(sample_data: dict[str, Any]) -> None:
    """Sampling must produce (n, N), require n > 0, and be strictly deterministic under fixed seed."""
    n_samples = 50
    n_flights = sample_data["n"]
    dist = GaussianResidualDistribution(mu=sample_data["mu"], sigma=sample_data["sigma"])

    # 1. Invalid n
    with pytest.raises(ValueError, match="must be positive"):
        dist.sample(0)

    with pytest.raises(ValueError, match="must be positive"):
        dist.sample(-5)

    # 2. Shape
    draws_1 = dist.sample(n_samples, seed=202601)
    assert draws_1.shape == (n_samples, n_flights)
    assert np.all(np.isfinite(draws_1))

    # 3. Determinism
    draws_2 = dist.sample(n_samples, seed=202601)
    np.testing.assert_array_equal(draws_1, draws_2)

    # 4. Sensitivity to different seed
    draws_3 = dist.sample(n_samples, seed=99999)
    assert not np.array_equal(draws_1, draws_3)


# =============================================================================
# 6. Manifest Parity & Metadata Schema
# =============================================================================

def test_distribution_contract_manifest_integrity() -> None:
    """Verify distribution_contract_v2.json exists, is valid, and matches declared classes."""
    manifest_path = Path("artifacts/manifests/distribution_contract_v2.json")
    assert manifest_path.exists(), f"Missing manifest at {manifest_path}"

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == "v2.0"
    assert payload["contract_name"] == "AEOLUS_V4_PREDICTIVE_DISTRIBUTION_CONTRACT_V2"

    dists = payload["distributions"]
    expected_adapters = [
        "EmpiricalDistribution",
        "GaussianResidualDistribution",
        "NGBoostNormalDistribution",
        "NGBoostStudentTDistribution",
        "QuantilePredictiveDistribution",
    ]

    for adapter_name in expected_adapters:
        assert adapter_name in dists
        item = dists[adapter_name]
        assert "capabilities" in item
        caps = item["capabilities"]
        for req in DistributionCapabilities.REQUIRED_CAPABILITIES:
            assert req in caps
            assert isinstance(caps[req], bool)
