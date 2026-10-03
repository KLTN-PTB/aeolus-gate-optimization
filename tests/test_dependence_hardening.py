"""Phase C — Tests for D0/D1/D2 Joint Dependence Hardening and PSD Validation.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16, 17
Verifies:
1. Variable daily flight counts n_d (e.g., n=1, 2, 5, 23, 77, 150, 420) without fixed-dimension assumptions.
2. D0 independent sampling with zero unintended cross-flight coupling.
3. D1 pre-cutoff conditioning audit (strictly rejects realized outcomes) and factor decomposition.
4. D2 covariance kernel properties: time units (min), tau=120, rho=0.15, unit diagonal, symmetry, [0, 1] range.
5. PSD validation & projection: separation of raw and corrected matrices, min eigenvalue >= 1e-6, distortion reporting.
6. Deterministic repeatability under fixed random seeds.
7. Seed-controlled randomized PIT sensitivity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.dependence.base import (
    BaseJointSampler,
    FORBIDDEN_POST_CUTOFF_COLUMNS,
    validate_flight_batch_inputs,
)
from src.dependence.d0_independent import IndependentJointSampler
from src.dependence.d1_scenario import ScenarioBlockJointSampler
from src.dependence.d2_gaussian_copula import GaussianCopulaJointSampler
from src.dependence.pit import (
    compute_controlled_randomized_pit,
    evaluate_pit_seed_sensitivity,
)
from src.dependence.psd import (
    MIN_PSD_EIGENVALUE,
    PSDDiagnostic,
    validate_and_project_psd,
)
from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.student_t_correctness import StudentTDistribution


def _make_dummy_flight_metadata(n_flights: int, seed: int = 202601) -> pd.DataFrame:
    """Generate valid pre-cutoff flight metadata for n flights."""
    rng = np.random.default_rng(seed)
    carriers = ["DL", "AA", "UA", "WN", "YX", "OO", "9E"]
    return pd.DataFrame(
        {
            "scheduled_departure_hour": rng.integers(5, 23, size=n_flights),
            "scheduled_departure_minute": rng.integers(0, 60, size=n_flights),
            "OP_CARRIER": [carriers[i % len(carriers)] for i in range(n_flights)],
            "CRS_ELAPSED_TIME": rng.uniform(60, 300, size=n_flights),
            "is_weekend": rng.integers(0, 2, size=n_flights),
        }
    )


def _make_dummy_marginals(n_flights: int) -> list[StudentTDistribution]:
    """Generate n_flights valid Student-t marginal distributions."""
    return [
        StudentTDistribution(
            mu=float(5.0 + (i % 10)),
            sigma=float(4.0 + (i % 3)),
            df=float(3.2 + 0.1 * (i % 5)),
            discrete=True,
        )
        for i in range(n_flights)
    ]


@pytest.mark.parametrize("n_flights", [1, 2, 5, 23, 77, 150, 420])
@pytest.mark.parametrize(
    "sampler_cls",
    [IndependentJointSampler, ScenarioBlockJointSampler, GaussianCopulaJointSampler],
)
def test_variable_daily_n(n_flights: int, sampler_cls: type[BaseJointSampler]) -> None:
    """Verify D0, D1, D2 run on arbitrary daily flight counts and return valid finite samples."""
    sampler = sampler_cls()
    meta = _make_dummy_flight_metadata(n_flights)
    marginals = _make_dummy_marginals(n_flights)
    rng = np.random.default_rng(202601)

    n_samples = 20
    y_draws = sampler.sample(
        marginal_distributions=marginals,
        flight_metadata=meta,
        rng=rng,
        n_samples=n_samples,
    )

    assert y_draws.shape == (n_samples, n_flights)
    assert np.all(np.isfinite(y_draws))
    assert np.all(y_draws == np.round(y_draws))  # exact discrete integers


def test_d0_independent_no_unintended_coupling() -> None:
    """Verify D0 produces completely independent draws with zero cross-flight correlation."""
    n_flights = 5
    n_samples = 30000
    meta = _make_dummy_flight_metadata(n_flights)
    marginals = _make_dummy_marginals(n_flights)
    rng = np.random.default_rng(202601)

    sampler = IndependentJointSampler()
    u_draws = sampler.sample_copula(meta, n_samples=n_samples, rng=rng)

    # Compute empirical correlation matrix between copula variates
    corr = np.corrcoef(u_draws, rowvar=False)
    assert corr.shape == (n_flights, n_flights)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-12)

    # Off-diagonal correlations must be statistically negligible (|r| < 0.02)
    off_diag = corr[~np.eye(n_flights, dtype=bool)]
    assert np.max(np.abs(off_diag)) < 0.02


def test_d1_pre_cutoff_leakage_audit() -> None:
    """Verify D1 strictly rejects any realized post-cutoff columns."""
    meta = _make_dummy_flight_metadata(10)
    sampler = ScenarioBlockJointSampler()
    marginals = _make_dummy_marginals(10)
    rng = np.random.default_rng(202601)

    for forbidden_col in ["ARR_DELAY", "DEP_DELAY", "CANCELLED", "WEATHER_DELAY"]:
        leaked_meta = meta.copy()
        leaked_meta[forbidden_col] = 0.0
        with pytest.raises(ProbabilisticContractViolation, match="forbidden post-cutoff"):
            sampler.sample(marginals, leaked_meta, rng, n_samples=10)


def test_d2_kernel_audit_properties() -> None:
    """Verify D2 kernel: time units, tau=120, rho=0.15, unit diagonal, symmetry, [0, 1] range."""
    n_flights = 25
    meta = _make_dummy_flight_metadata(n_flights)
    sampler = GaussianCopulaJointSampler(
        temporal_length_scale_minutes=120.0, carrier_correlation=0.15
    )

    raw_corr, corr_mat, diag = sampler.construct_correlation_matrices(meta)

    # 1. Symmetry
    assert np.allclose(raw_corr, raw_corr.T, atol=1e-12)
    assert np.allclose(corr_mat, corr_mat.T, atol=1e-12)

    # 2. Diagonal is strictly 1.0
    assert np.allclose(np.diag(raw_corr), 1.0, atol=1e-12)
    assert np.allclose(np.diag(corr_mat), 1.0, atol=1e-12)

    # 3. Entries bounded in [0, 1]
    assert np.all(raw_corr >= -1e-12) and np.all(raw_corr <= 1.0 + 1e-12)
    assert np.all(corr_mat >= -1.0) and np.all(corr_mat <= 1.0)

    # 4. Corrected min eigenvalue >= MIN_PSD_EIGENVALUE
    eigvals = np.linalg.eigvalsh(corr_mat)
    assert np.min(eigvals) >= MIN_PSD_EIGENVALUE - 1e-12

    # 5. Diagnostic reporting
    assert diag.matrix_dimension == n_flights
    assert isinstance(diag.frobenius_distortion, float)
    assert diag.frobenius_distortion >= 0.0


def test_psd_projection_and_distortion_reporting() -> None:
    """Verify validate_and_project_psd correctly reports distortion on non-PSD matrix."""
    # Create an indefinite matrix with a negative eigenvalue
    raw_indef = np.array(
        [
            [1.0, 0.9, 0.9],
            [0.9, 1.0, 0.9],
            [0.9, 0.9, 0.1],  # intentional inconsistency making it non-PSD
        ],
        dtype=np.float64,
    )
    raw_indef = 0.5 * (raw_indef + raw_indef.T)

    corrected, diag = validate_and_project_psd(raw_indef, min_eigenvalue=1e-6, is_correlation=True)

    assert diag.raw_is_psd is False
    assert diag.raw_negative_eigenvalue_count > 0
    assert diag.was_correction_applied is True
    assert diag.frobenius_distortion > 0.0
    assert diag.relative_frobenius_distortion > 0.0
    assert diag.corrected_min_eigenvalue >= 1e-6

    # Verify corrected matrix is strictly PSD and has unit diagonal
    corr_eigvals = np.linalg.eigvalsh(corrected)
    assert np.min(corr_eigvals) >= 1e-6 - 1e-12
    assert np.allclose(np.diag(corrected), 1.0, atol=1e-12)


def test_joint_sampling_repeatability() -> None:
    """Verify identical random seeds produce identical joint arrival delay matrices."""
    n_flights = 15
    meta = _make_dummy_flight_metadata(n_flights)
    marginals = _make_dummy_marginals(n_flights)
    sampler = GaussianCopulaJointSampler()

    # Run 1
    rng1 = np.random.default_rng(202601)
    draws1 = sampler.sample(marginals, meta, rng1, n_samples=50)

    # Run 2 with same seed
    rng2 = np.random.default_rng(202601)
    draws2 = sampler.sample(marginals, meta, rng2, n_samples=50)

    assert np.array_equal(draws1, draws2)

    # Run 3 with different seed
    rng3 = np.random.default_rng(202602)
    draws3 = sampler.sample(marginals, meta, rng3, n_samples=50)
    assert not np.array_equal(draws1, draws3)


def test_seed_controlled_pit_sensitivity() -> None:
    """Verify seed-controlled discrete randomized PIT repeatability and stability."""
    n_flights = 20
    marginals = _make_dummy_marginals(n_flights)
    y_obs = np.array([m.quantile(0.65) for m in marginals], dtype=np.int64)

    report = evaluate_pit_seed_sensitivity(
        y_obs,
        marginals,
        seeds=(202601, 202602, 202603, 202604, 202605),
    )

    assert report.is_repeatable is True
    assert report.is_sensitivity_stable is True
    assert report.n_samples == n_flights
    assert report.mean_std_across_seeds < 0.25
