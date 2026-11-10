"""Phase C & Phase H — Dependence Contract Consistency Test Suite.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16
Step: STEP 5 — DEPENDENCE CONTRACT CONSISTENCY

Verifies:
1. Synchronization of spatial dimension contract between Phase C (stress test up to d=420)
   and Phase H (ProtocolComplianceGuard.check_dynamic_dependence_dimension).
2. Arbitrary positive daily flight counts d >= 1 without static whitelist restrictions.
3. Property-based verification:
   - Matrix shape (d, d)
   - Symmetry: max |C - C^T| < 1e-10
   - Diagonal convention: max |C_ii - 1.0| < 1e-10
   - Finite values: no NaN, no Inf
   - Positive Semi-Definiteness (PSD): min eigenvalue >= 1e-6
   - Copula sampling shape: (n_samples, d) with bounds in (0, 1)
   - Seed determinism: identical random seed reproduces identical copula samples.
4. Extended stress test for large hub dimensions (d >= 420, covering ATL peak daily arrivals).
5. Fail-closed rejection of non-positive dimensions (d <= 0) and empty inputs.
6. Documentation of hardware and computational resource limits:
   - Minimum dimension: d >= 1
   - Peak operational hub dimension: d = 420
   - Recommended resource limit: d <= 1500 (O(d^3) spectral compute limit for real-time simulation).
7. Strict preservation of dependence parameters (tau=120.0 min, rho=0.15, Gaussian Copula)
   and zero exposure to 2024 holdout data (POST_HOLDOUT).
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
import pytest

from src.audit.protocol_guards import (
    DEFAULT_CI_DEPENDENCE_DIMENSIONS,
    MIN_DEPENDENCE_DIMENSION,
    PEAK_OPERATIONAL_HUB_DIMENSION,
    RECOMMENDED_MAX_DIMENSION,
    ProtocolComplianceGuard,
    verify_dependence_dimension_properties,
)
from src.dependence.d2_gaussian_copula import GaussianCopulaJointSampler
from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.dependence import GaussianCopulaDependenceModel
from src.models.probabilistic.student_t_correctness import StudentTDistribution


def _make_flight_features(n_flights: int, seed: int = 202601) -> pd.DataFrame:
    """Generate realistic pre-cutoff flight features for n_flights."""
    rng = np.random.default_rng(seed)
    carriers = ["DL", "AA", "UA", "WN", "YX", "OO", "9E"]
    return pd.DataFrame(
        {
            "scheduled_departure_hour": rng.integers(6, 23, size=n_flights),
            "scheduled_departure_minute": rng.integers(0, 60, size=n_flights),
            "OP_CARRIER": [carriers[i % len(carriers)] for i in range(n_flights)],
        }
    )


# =============================================================================
# 1. PARAMETERIZED PROPERTY-BASED TESTS ACROSS REPRESENTATIVE DIMENSIONS
# =============================================================================

@pytest.mark.parametrize("d", [1, 5, 23, 77, 150, 420])
def test_parameterized_dimension_properties(d: int) -> None:
    """Verify all 7 mathematical invariants for arbitrary dimensions d in [1, 5, 23, 77, 150, 420]."""
    diag = verify_dependence_dimension_properties(d, n_samples=25, seed=202601)

    assert diag["is_valid"] is True, f"Failed verification for dimension d={d}"
    assert diag["shape_ok"] is True
    assert diag["is_symmetric"] is True
    assert diag["symmetry_max_error"] < 1e-10
    assert diag["diag_ok"] is True
    assert diag["diag_max_error"] < 1e-10
    assert diag["all_finite"] is True
    assert diag["is_psd"] is True
    assert diag["min_eigenvalue"] >= 1e-6 - 1e-10
    assert diag["sampling_shape_ok"] is True
    assert diag["sampling_range_ok"] is True
    assert diag["is_deterministic"] is True
    assert diag["is_non_trivial"] is True


# =============================================================================
# 2. EXTENDED STRESS TEST FOR LARGE HUB DIMENSIONS (d >= 420)
# =============================================================================

@pytest.mark.parametrize("d_stress", [420, 500])
def test_extended_stress_dimensions(d_stress: int) -> None:
    """Verify performance and numerical stability on peak hub daily arrival loads (ATL peak d=420+)."""
    model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0, carrier_correlation=0.15)
    df = _make_flight_features(d_stress, seed=999)

    t0 = time.perf_counter()
    corr = model.construct_correlation_matrix(df)
    t_construct = time.perf_counter() - t0

    assert corr.shape == (d_stress, d_stress)
    assert np.allclose(corr, corr.T, atol=1e-10)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-10)
    assert np.all(np.isfinite(corr))

    # Spectral floor verification
    eigvals = np.linalg.eigvalsh(corr)
    assert np.min(eigvals) >= 1e-6 - 1e-10

    # Cholesky and copula sampling verification
    rng = np.random.default_rng(202601)
    t0_sample = time.perf_counter()
    u = model.sample_copula(df, n_samples=50, rng=rng)
    t_sample = time.perf_counter() - t0_sample

    assert u.shape == (50, d_stress)
    assert np.all(np.isfinite(u))
    assert np.all((u >= 1e-6) & (u <= 1.0 - 1e-6))

    # Compute runtime must be well within operational limits (< 5.0 seconds)
    total_sec = t_construct + t_sample
    assert total_sec < 5.0, f"Stress test d={d_stress} too slow: {total_sec:.2f}s"


# =============================================================================
# 3. FAIL-CLOSED REJECTION OF INVALID DIMENSIONS
# =============================================================================

def test_fail_closed_invalid_dimensions() -> None:
    """Verify that non-positive dimensions (d <= 0) and empty inputs are strictly rejected."""
    # Test verify_dependence_dimension_properties with invalid d
    assert verify_dependence_dimension_properties(0)["is_valid"] is False
    assert verify_dependence_dimension_properties(-1)["is_valid"] is False
    assert verify_dependence_dimension_properties(-100)["is_valid"] is False

    # Test GaussianCopulaDependenceModel rejects empty features
    model = GaussianCopulaDependenceModel()
    empty_df = pd.DataFrame(columns=["scheduled_departure_hour", "scheduled_departure_minute", "OP_CARRIER"])
    with pytest.raises(ProbabilisticContractViolation, match="flight_features cannot be empty"):
        model.construct_correlation_matrix(empty_df)

    # Test GaussianCopulaJointSampler rejects empty features
    sampler = GaussianCopulaJointSampler()
    with pytest.raises(ProbabilisticContractViolation, match="flight_features cannot be empty"):
        sampler.construct_correlation_matrices(empty_df)


# =============================================================================
# 4. PROTOCOL COMPLIANCE GUARD INTEGRATION TEST
# =============================================================================

def test_protocol_guard_dynamic_dependence_dimension() -> None:
    """Verify that ProtocolComplianceGuard.check_dynamic_dependence_dimension passes with Phase C sync."""
    guard = ProtocolComplianceGuard()
    res = guard.check_dynamic_dependence_dimension()

    assert res["passed"] is True
    assert res["max_tested_dimension"] >= 420
    assert res["peak_operational_hub_covered"] is True
    assert res["property_based_checks_passed"] is True
    assert res["invalid_dimension_fail_closed"] is True

    # Resource limits must be properly documented
    res_limits = res["resource_limits"]
    assert res_limits["min_dimension"] == MIN_DEPENDENCE_DIMENSION == 1
    assert res_limits["peak_operational_dimension"] == PEAK_OPERATIONAL_HUB_DIMENSION == 420
    assert res_limits["recommended_max_dimension"] == RECOMMENDED_MAX_DIMENSION == 1500
    assert "O(d^3)" in res_limits["computational_complexity"]
    assert "O(d^2)" in res_limits["memory_scaling"]

    # All tested dimensions must match DEFAULT_CI_DEPENDENCE_DIMENSIONS
    assert tuple(res["tested_dimensions"]) == DEFAULT_CI_DEPENDENCE_DIMENSIONS


# =============================================================================
# 5. DETERMINISTIC SEED REPRODUCIBILITY (d=420 STRESS)
# =============================================================================

def test_deterministic_seed_reproducibility() -> None:
    """Verify identical random seeds produce bitwise identical draws at peak dimension d=420."""
    d = 420
    df = _make_flight_features(d, seed=123)
    model = GaussianCopulaDependenceModel()

    rng_a1 = np.random.default_rng(7777)
    u_a1 = model.sample_copula(df, n_samples=30, rng=rng_a1)

    rng_a2 = np.random.default_rng(7777)
    u_a2 = model.sample_copula(df, n_samples=30, rng=rng_a2)

    assert np.array_equal(u_a1, u_a2), "Identical seeds produced non-identical copula samples"

    rng_b = np.random.default_rng(8888)
    u_b = model.sample_copula(df, n_samples=30, rng=rng_b)
    assert not np.array_equal(u_a1, u_b), "Different seeds unexpectedly produced identical samples"


# =============================================================================
# 6. SYNCHRONIZED CONTRACT ACROSS SAMPLERS (D0, D1, D2)
# =============================================================================

def test_samplers_synchronized_contract() -> None:
    """Verify GaussianCopulaDependenceModel and GaussianCopulaJointSampler adhere to the synchronized contract."""
    d = 77
    df = _make_flight_features(d, seed=555)

    model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0, carrier_correlation=0.15)
    sampler = GaussianCopulaJointSampler(temporal_length_scale_minutes=120.0, carrier_correlation=0.15)

    corr_model = model.construct_correlation_matrix(df)
    _, corr_sampler, diag_sampler = sampler.construct_correlation_matrices(df)

    # Both models produce identical correlation matrices
    assert np.allclose(corr_model, corr_sampler, atol=1e-10)
    assert corr_model.shape == (d, d)
    assert corr_sampler.shape == (d, d)
    assert diag_sampler.matrix_dimension == d
    assert diag_sampler.corrected_min_eigenvalue >= 1e-6 - 1e-10

    # Hyper-parameters preserved
    assert model.length_scale == 120.0
    assert model.rho_carrier == 0.15
    assert sampler.length_scale == 120.0
    assert sampler.rho_carrier == 0.15
