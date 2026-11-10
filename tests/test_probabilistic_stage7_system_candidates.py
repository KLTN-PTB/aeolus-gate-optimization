"""Unit tests for Stage 7 — Complete System Candidate Construction.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 12, 13, 14, 15, 16, 17
Verifies:
1. Complete system candidate schema and required components.
2. Arbitrary daily flight count n_d support (n=1, 5, 25, 100, 200).
3. Pre-cutoff safety guard: rejection of forbidden realized columns.
4. PSD guarantee for covariance/correlation matrices.
5. Discrete randomized PIT determinism under locked seed.
6. End-to-end Monte Carlo, Simulation, and Optimization interfaces.
7. Pre-registered diagnostic evidence gate for D3 tail copula.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.contracts import (
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.correctness import GaussianMixtureDistribution
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    ScenarioBlockDependenceModel,
    StudentTMarginalDistribution,
    TailDependentCopulaModel,
    evaluate_tail_copula_evidence_gate,
)
from src.models.probabilistic.dependence_interface import (
    DayFlightBatch,
    DiscretePITPolicy,
    PSDPolicy,
)
from src.models.probabilistic.system_candidate import (
    CompleteSystemCandidate,
    build_complete_system_candidate,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_pre_cutoff_features() -> pd.DataFrame:
    """Generate synthetic pre-cutoff features for 20 flights."""
    rng = np.random.default_rng(202601)
    n = 20
    df = pd.DataFrame({
        "CRS_ELAPSED_TIME": rng.integers(60, 360, size=n).astype(float),
        "calendar_year": np.full(n, 2022, dtype=int),
        "calendar_month": rng.integers(1, 13, size=n),
        "calendar_day_of_month": rng.integers(1, 29, size=n),
        "calendar_day_of_week": rng.integers(1, 8, size=n),
        "is_weekend": rng.integers(0, 2, size=n),
        "scheduled_departure_hour": rng.integers(6, 23, size=n),
        "scheduled_departure_minute": rng.integers(0, 60, size=n),
        "OP_CARRIER": rng.choice(["AA", "DL", "UA", "WN", "OO", "EV"], size=n),
        "ORIGIN": rng.choice(["ORD", "ATL", "DFW", "LAX", "DEN"], size=n),
        "OP_CARRIER_FL_NUM": [f"FL_{i}" for i in range(n)],
    })
    return df


@pytest.fixture
def mock_marginal_factory():
    """Returns factory producing mock discrete Gaussian mixture marginals."""
    def _factory(features: pd.DataFrame):
        n = len(features)
        marginals = []
        for i in range(n):
            # Realistic arrival delay parameters (minutes)
            pi = [0.60, 0.30, 0.10]
            mu = [-5.0 + (i % 5), 15.0 + (i % 10), 65.0]
            sigma = [8.0, 15.0, 35.0]
            marginals.append(GaussianMixtureDistribution(pi, mu, sigma, discrete=True))
        return marginals
    return _factory


# =============================================================================
# Tests
# =============================================================================

def test_pre_cutoff_safety_guard_rejects_forbidden_columns(sample_pre_cutoff_features):
    """DayFlightBatch must strictly reject any realized post-cutoff column."""
    # 1. Valid pre-cutoff batch should succeed
    batch = DayFlightBatch(flight_date="2022-06-15", flight_features=sample_pre_cutoff_features)
    assert batch.n_flights == 20

    # 2. Injecting realized departure delay must raise contract violation
    bad_features = sample_pre_cutoff_features.copy()
    bad_features["DEP_DELAY"] = 15.0
    with pytest.raises(ProbabilisticContractViolation, match="contains realized post-cutoff columns"):
        DayFlightBatch(flight_date="2022-06-15", flight_features=bad_features)

    # 3. Injecting realized taxi-out must raise contract violation
    bad_features2 = sample_pre_cutoff_features.copy()
    bad_features2["TAXI_OUT"] = 18.0
    with pytest.raises(ProbabilisticContractViolation, match="contains realized post-cutoff columns"):
        DayFlightBatch(flight_date="2022-06-15", flight_features=bad_features2)


def test_arbitrary_daily_flight_counts_supported(mock_marginal_factory):
    """Dependence models must seamlessly handle arbitrary daily n (n=1, 5, 25, 100, 200)."""
    rng = np.random.default_rng(202601)
    dep_models = [
        IndependentDependenceModel(),
        ScenarioBlockDependenceModel(),
        GaussianCopulaDependenceModel(),
        TailDependentCopulaModel(),
    ]

    for n in [1, 5, 25, 100, 200]:
        df = pd.DataFrame({
            "CRS_ELAPSED_TIME": rng.integers(60, 360, size=n).astype(float),
            "calendar_year": np.full(n, 2022, dtype=int),
            "calendar_month": rng.integers(1, 13, size=n),
            "calendar_day_of_month": rng.integers(1, 29, size=n),
            "calendar_day_of_week": rng.integers(1, 8, size=n),
            "is_weekend": rng.integers(0, 2, size=n),
            "scheduled_departure_hour": rng.integers(6, 23, size=n),
            "scheduled_departure_minute": rng.integers(0, 60, size=n),
            "OP_CARRIER": rng.choice(["AA", "DL", "UA", "WN"], size=n),
            "ORIGIN": rng.choice(["ORD", "ATL", "DFW"], size=n),
            "OP_CARRIER_FL_NUM": [f"FL_{i}" for i in range(n)],
        })
        marginals = mock_marginal_factory(df)

        for model in dep_models:
            u = model.sample_copula(df, n_samples=10, rng=rng)
            assert u.shape == (10, n), f"{model.name} failed shape for n={n}"
            assert np.all(u > 0.0) and np.all(u < 1.0), f"{model.name} out of bounds for n={n}"

            y = model.sample_joint(marginals, df, n_samples=10, rng=rng)
            assert y.shape == (10, n)
            assert np.all(np.isfinite(y))


def test_psd_enforcement_guarantee(sample_pre_cutoff_features):
    """Correlation matrix must always be strictly PSD with unit diagonal and min eigval >= 1e-6."""
    d2 = GaussianCopulaDependenceModel(temporal_length_scale_minutes=60.0, carrier_correlation=0.30)
    corr = d2.construct_correlation_matrix(sample_pre_cutoff_features)

    # Unit diagonal
    np.testing.assert_allclose(np.diag(corr), 1.0, atol=1e-8)

    # Positive semi-definite: all eigenvalues >= MIN_PSD_EIGENVALUE
    eigvals = np.linalg.eigvalsh(corr)
    assert np.min(eigvals) >= 1e-6 - 1e-9

    # Test with duplicate identical flights (extreme rank-deficient case)
    dup_features = pd.concat([sample_pre_cutoff_features.iloc[:5]] * 4, ignore_index=True)
    corr_dup = d2.construct_correlation_matrix(dup_features)
    eigvals_dup = np.linalg.eigvalsh(corr_dup)
    assert np.min(eigvals_dup) >= 1e-6 - 1e-9


def test_discrete_randomized_pit_seed_determinism(sample_pre_cutoff_features, mock_marginal_factory):
    """Discrete randomized PIT must be perfectly reproducible when seed is fixed."""
    marginals = mock_marginal_factory(sample_pre_cutoff_features)
    y_obs = np.array([float(m.quantile(0.70)) for m in marginals])

    rng1 = np.random.default_rng(202601)
    u1 = DiscretePITPolicy.compute_randomized_pit(y_obs, marginals, rng1)

    rng2 = np.random.default_rng(202601)
    u2 = DiscretePITPolicy.compute_randomized_pit(y_obs, marginals, rng2)

    np.testing.assert_array_equal(u1, u2)

    # Sensitivity across draws
    sens = DiscretePITPolicy.evaluate_pit_sensitivity(y_obs, marginals, n_draws=10, base_seed=202601)
    assert sens["n_draws"] == 10.0
    assert sens["mean_u_std_across_draws"] < 0.25
    assert sens["sensitivity_stable"] == 1.0


def test_complete_system_candidate_interfaces(sample_pre_cutoff_features, mock_marginal_factory):
    """Verify Monte Carlo, Simulation, Optimization, and Manifest serialization interfaces."""
    batch = DayFlightBatch(flight_date="2022-06-15", flight_features=sample_pre_cutoff_features)

    cand = build_complete_system_candidate(
        marginal_candidate_id="seed_ensemble_3",
        dependence_family_id="DEP_D2_gaussian_copula",
        marginal_factory=mock_marginal_factory,
    )

    # 1. Monte Carlo Interface
    y_mc = cand.sample_scenarios(batch, n_scenarios=50, seed=202601)
    assert y_mc.shape == (50, 20)
    assert np.all(np.isfinite(y_mc))

    # Reproducibility check with same seed
    y_mc_rep = cand.sample_scenarios(batch, n_scenarios=50, seed=202601)
    np.testing.assert_array_equal(y_mc, y_mc_rep)

    # 2. Simulation Interface
    sim_res = cand.simulate_daily_operations(batch, n_scenarios=50, seed=202601)
    assert sim_res["flight_date"] == "2022-06-15"
    assert sim_res["n_flights"] == 20
    assert sim_res["n_scenarios"] == 50
    assert "mean_daily_total_delay" in sim_res
    assert "p_any_severe_ge60" in sim_res
    assert 0.0 <= sim_res["p_any_severe_ge60"] <= 1.0

    # 3. Optimization Interface
    opt_mat = cand.get_scenario_matrix(batch, n_scenarios=50, seed=202601)
    assert opt_mat.shape == (50, 20)

    # 4. Manifest Dictionary
    m_dict = cand.to_manifest_dict()
    assert m_dict["candidate_id"] == "SYS_seed_ensemble_3__DEP_D2_gaussian_copula"
    assert "feature_manifest" in m_dict
    assert "representation_manifest" in m_dict
    assert "architecture" in m_dict
    assert "training_policy" in m_dict
    assert "frozen_weights_config" in m_dict
    assert "calibration_method" in m_dict
    assert "dependence_parameters" in m_dict
    assert "sampling_procedure" in m_dict
    assert "seed_policy" in m_dict
    assert len(m_dict["sampling_procedure"]) == 5


def test_student_t_marginal_distribution():
    """Verify StudentTMarginalDistribution implements MarginalDistributionProtocol."""
    dist = StudentTMarginalDistribution(mu=10.0, sigma=15.0, df=4.0, discrete=True)

    # CDF monotonically increases
    assert dist.cdf(0.0) < dist.cdf(10.0) < dist.cdf(30.0)
    assert 0.0 < dist.cdf(10.0) < 1.0

    # Quantile monotonically increases
    assert dist.quantile(0.10) < dist.quantile(0.50) < dist.quantile(0.90)

    # Samples are finite
    rng = np.random.default_rng(202601)
    samples = dist.sample(100, rng)
    assert len(samples) == 100
    assert np.all(np.isfinite(samples))


def test_tail_copula_evidence_gate():
    """Pre-registered evidence gate correctly determines whether D3 tail copula is opened."""
    # Case 1: Deficit exceeds threshold -> OPENED
    res_open = evaluate_tail_copula_evidence_gate(
        historical_pairs_both_ge60=200,
        total_eligible_pairs=10000,
        d2_expected_pairs_ge60=100.0,
        deficit_threshold=0.005,
    )
    assert res_open.d3_tail_copula_opened is True
    assert "D3 Tail Copula is OPENED" in res_open.diagnostic_rationale

    # Case 2: Deficit within threshold -> CLOSED
    res_closed = evaluate_tail_copula_evidence_gate(
        historical_pairs_both_ge60=120,
        total_eligible_pairs=10000,
        d2_expected_pairs_ge60=100.0,
        deficit_threshold=0.005,
    )
    assert res_closed.d3_tail_copula_opened is False
    assert "D3 Tail Copula remains CLOSED" in res_closed.diagnostic_rationale
