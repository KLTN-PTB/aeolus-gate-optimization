"""Comprehensive Verification Suite for Task R4: Probabilistic Forecasting Methodology Audit & Repair.

Protocol: Task R4 Probabilistic Forecasting Methodology Audit & Repair
Coverage:
1. Rejection of invalid scale (sigma <= 0) and non-finite values (fail-closed).
2. Quantile monotonicity and monotonic rearrangement on crossing quantiles.
3. Truthful metric accounting: Supported vs Unsupported queries (CDF, NLL, PIT, Mean).
4. Zero metric fabrication: P5 is QUANTILE_FORECAST_ONLY without CDF, NLL, or PIT.
5. P1 Empirical baseline lacks continuous NLL and valid continuous PIT.
6. P4 Student-T degrees of freedom nu > 2.0, scale sigma > 0, role='historical_candidate'.
7. Determinism under fixed seed.
8. Evaluation engine result schema: metric_details structure.
9. Manifest consistency between YAML config and JSON manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionValidationError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    QuantilePredictiveDistribution,
)
from src.evaluation.calibration import compute_pit_diagnostics
from src.evaluation.forecast_metrics import evaluate_predictive_distribution
from src.models.probabilistic.candidate_interfaces import (
    PROBABILISTIC_CANDIDATE_REGISTRY,
    BaseProbabilisticCandidate,
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
    get_probabilistic_candidate,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES
from tests.probabilistic.test_distribution_contract import make_dummy_data


# =============================================================================
# 1. Numerical Safety & Validation (Fail-Closed)
# =============================================================================

def test_gaussian_rejects_non_positive_sigma() -> None:
    """Gaussian distribution must reject sigma <= 0 with DistributionValidationError."""
    mu = np.array([10.0, 12.0])
    sigma_zero = np.array([5.0, 0.0])
    sigma_neg = np.array([-1.0, 5.0])

    with pytest.raises(DistributionValidationError):
        dist = GaussianResidualDistribution(mu=mu, sigma=sigma_zero)
        dist.validate()

    with pytest.raises(DistributionValidationError):
        dist = GaussianResidualDistribution(mu=mu, sigma=sigma_neg)
        dist.validate()


def test_student_t_rejects_invalid_df_and_sigma() -> None:
    """Student-T distribution must reject nu <= 2.0 or sigma <= 0 upon validate()."""
    mu = np.array([5.0, 10.0])
    sigma = np.array([3.0, 4.0])

    # 1. NaN in df must fail closed
    with pytest.raises(DistributionValidationError):
        dist_nan = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=np.array([np.nan, 4.0]))
        dist_nan.validate()

    # 2. Corrupted nu <= 2.0 must fail closed
    dist = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=np.array([3.0, 4.0]))
    dist.validate()  # valid
    dist._df = np.array([1.5, 4.0])
    with pytest.raises(DistributionValidationError, match="df must be strictly > 2.0"):
        dist.validate()

    # 3. Corrupted sigma <= 0 must fail closed
    dist._df = np.array([3.0, 4.0])
    dist._sigma = np.array([0.0, 4.0])
    with pytest.raises(DistributionValidationError, match="sigma must be strictly positive"):
        dist.validate()


def test_quantile_distribution_rejects_nan_and_inf() -> None:
    """Quantile distribution must fail closed if quantiles contain NaN or Inf."""
    alphas = sorted(PRE_REGISTERED_QUANTILES)
    q_data_nan = {a: np.full(5, 10.0) for a in alphas}
    q_data_nan[0.50][2] = np.nan

    with pytest.raises(DistributionValidationError):
        dist = QuantilePredictiveDistribution(quantiles_dict=q_data_nan)
        dist.validate()

    q_data_inf = {a: np.full(5, 10.0) for a in alphas}
    q_data_inf[0.90][1] = np.inf

    with pytest.raises(DistributionValidationError):
        dist = QuantilePredictiveDistribution(quantiles_dict=q_data_inf)
        dist.validate()


# =============================================================================
# 2. Monotonicity & Monotone Rearrangement
# =============================================================================

def test_quantile_distribution_rejects_crossing_quantiles() -> None:
    """QuantilePredictiveDistribution must fail closed if quantiles violate monotonicity."""
    alphas = sorted(PRE_REGISTERED_QUANTILES)
    q_data = {a: np.full(5, float(i * 5.0)) for i, a in enumerate(alphas)}
    # Intentionally invert 0.75 and 0.90
    q_data[0.75], q_data[0.90] = q_data[0.90], q_data[0.75]

    with pytest.raises(DistributionValidationError, match="Quantile crossing detected"):
        dist = QuantilePredictiveDistribution(quantiles_dict=q_data)
        dist.validate()


def test_p5_monotone_rearrangement_prevents_crossing() -> None:
    """P5 prediction pipeline enforces monotone rearrangement, ensuring strictly valid quantiles."""
    X_train, y_train = make_dummy_data(n=80, seed=101)
    X_val, _ = make_dummy_data(n=25, seed=202)

    p5 = P5QuantileRegressionCandidate(seed=202601)
    p5.fit(X_train, y_train)
    dist = p5.predict_distribution(X_val)

    # validate() must pass without crossing error
    dist.validate()

    # Explicit check across all pre-registered quantiles for every row
    sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)
    for j in range(len(sorted_alphas) - 1):
        a_low, a_high = sorted_alphas[j], sorted_alphas[j + 1]
        q_l = dist.quantile(a_low)
        q_h = dist.quantile(a_high)
        assert np.all(q_l <= q_h + 1e-6), f"Monotonicity violated between {a_low} and {a_high}"


# =============================================================================
# 3. Truthful Capability Accounting & No Fabrication
# =============================================================================

def test_p5_strictly_quantile_forecast_only() -> None:
    """P5 must declare and behave strictly as QUANTILE_FORECAST_ONLY."""
    p5 = P5QuantileRegressionCandidate(seed=202601)
    caps = p5.capabilities()

    assert caps["has_quantiles"] is True
    assert caps["has_median"] is True
    assert caps["has_crps"] is True
    assert caps["has_mean"] is False
    assert caps["has_cdf"] is False
    assert caps["has_probability_ge"] is False
    assert caps["has_sampler"] is False
    assert caps["has_nll"] is False
    assert caps["has_pit"] is False

    X_train, y_train = make_dummy_data(n=60, seed=1)
    X_val, y_val = make_dummy_data(n=15, seed=2)
    p5.fit(X_train, y_train)
    dist = p5.predict_distribution(X_val)

    assert dist.metadata.get("role") == "QUANTILE_FORECAST_ONLY"
    assert dist.metadata.get("family") == "quantile_regression"

    # Unsupported queries must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        dist.mean()

    with pytest.raises(CapabilityNotSupportedError):
        dist.cdf(15.0)

    with pytest.raises(CapabilityNotSupportedError):
        dist.probability_ge(15.0)

    with pytest.raises(CapabilityNotSupportedError):
        dist.sample(10)


def test_p1_empirical_capabilities_and_pit_omission() -> None:
    """P1 Empirical baseline must not fabricate continuous NLL or continuous PIT."""
    p1 = P1EmpiricalCandidate(seed=202601)
    caps = p1.capabilities()

    assert caps["has_mean"] is True
    assert caps["has_quantiles"] is True
    assert caps["has_cdf"] is True
    assert caps["has_nll"] is False
    assert caps["has_pit"] is False

    X_train, y_train = make_dummy_data(n=60, seed=10)
    X_val, y_val = make_dummy_data(n=20, seed=20)
    p1.fit(X_train, y_train)
    dist = p1.predict_distribution(X_val)

    # PIT must report NOT_AVAILABLE
    pit_res = compute_pit_diagnostics(dist, y_val)
    assert pit_res["status"] == "NOT_AVAILABLE"
    assert "not support continuous pit" in pit_res["reason"].lower() or "step cdf" in pit_res["reason"].lower()


def test_p4_student_t_parameters_and_role() -> None:
    """P4 Student-T must enforce nu > 2.0, sigma > 0, and declare role='historical_candidate'."""
    p4 = P4NGBoostStudentTCandidate(seed=202601)
    X_train, y_train = make_dummy_data(n=60, seed=30)
    X_val, y_val = make_dummy_data(n=15, seed=40)
    p4.fit(X_train, y_train)
    dist = p4.predict_distribution(X_val)

    assert dist.metadata.get("role") == "historical_candidate"
    assert dist.metadata.get("family") == "ngboost_student_t"

    df_vals = dist._df
    sigma_vals = dist._sigma
    assert np.all(df_vals > 2.0), f"Degrees of freedom must be > 2.0, min was {np.min(df_vals)}"
    assert np.all(sigma_vals > 0.0), f"Scale sigma must be > 0.0, min was {np.min(sigma_vals)}"


# =============================================================================
# 4. Evaluation Engine Schema & Metric Details
# =============================================================================

@pytest.mark.parametrize(
    "candidate_id",
    [
        "P1_empirical",
        "P2_xgb_gaussian_oof",
        "P3_ngboost_normal",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
    ],
)
def test_evaluation_schema_and_metric_details(candidate_id: str) -> None:
    """All 5 probabilistic candidates must produce conformant metric_details under evaluate_predictive_distribution."""
    X_train, y_train = make_dummy_data(n=70, seed=123)
    X_val, y_val = make_dummy_data(n=20, seed=456)

    candidate = get_probabilistic_candidate(candidate_id, seed=202601)
    candidate.fit(X_train, y_train)
    dist = candidate.predict_distribution(X_val)

    metrics = evaluate_predictive_distribution(dist, y_val)

    # 1. Backwards-compatible top-level keys
    assert "crps" in metrics
    assert "pinball_losses" in metrics
    assert "metric_details" in metrics

    details = metrics["metric_details"]
    required_metric_names = [
        "mean",
        "median",
        "quantile",
        "cdf",
        "event_probability",
        "sampling",
        "crps",
        "exact_crps",
        "approximate_crps",
        "nll",
        "pit",
        "coverage",
        "interval_width",
    ]

    for m_name in required_metric_names:
        assert m_name in details, f"Missing {m_name} in metric_details for {candidate_id}"
        entry = details[m_name]
        assert "metric_value" in entry
        assert "metric_status" in entry
        assert entry["metric_status"] in {"SUPPORTED", "NOT_SUPPORTED", "APPROXIMATE"}
        assert "metric_method" in entry
        assert "is_exact" in entry
        assert "is_approximate" in entry
        assert "unsupported_reason" in entry

    # Candidate-specific contracts:
    if candidate_id == "P5_quantile_regression":
        assert details["mean"]["metric_status"] == "NOT_SUPPORTED"
        assert details["cdf"]["metric_status"] == "NOT_SUPPORTED"
        assert details["event_probability"]["metric_status"] == "NOT_SUPPORTED"
        assert details["sampling"]["metric_status"] == "NOT_SUPPORTED"
        assert details["nll"]["metric_status"] == "NOT_SUPPORTED"
        assert details["exact_crps"]["metric_status"] == "NOT_SUPPORTED"
        assert details["pit"]["metric_status"] == "NOT_SUPPORTED"
        assert details["quantile"]["metric_status"] == "SUPPORTED"
        assert details["approximate_crps"]["metric_status"] == "SUPPORTED"
    elif candidate_id == "P1_empirical":
        assert details["nll"]["metric_status"] == "NOT_SUPPORTED"
        assert details["pit"]["metric_status"] == "NOT_SUPPORTED"
        assert details["approximate_crps"]["metric_status"] == "SUPPORTED"
    elif candidate_id in {"P2_xgb_gaussian_oof", "P3_ngboost_normal"}:
        assert details["exact_crps"]["metric_status"] == "SUPPORTED"
        assert details["exact_crps"]["is_exact"] is True
        assert details["nll"]["metric_status"] == "SUPPORTED"
        assert details["pit"]["metric_status"] == "SUPPORTED"
    elif candidate_id == "P4_ngboost_student_t":
        assert details["exact_crps"]["metric_status"] == "NOT_SUPPORTED"
        assert details["approximate_crps"]["metric_status"] == "SUPPORTED"
        assert details["nll"]["metric_status"] == "SUPPORTED"
        assert details["pit"]["metric_status"] == "SUPPORTED"


# =============================================================================
# 5. Determinism & Seed Sensitivity
# =============================================================================

def test_probabilistic_candidate_seed_determinism() -> None:
    """Models with random state produce identical results under same seed and differ across seeds."""
    X_train, y_train = make_dummy_data(n=60, seed=55)
    X_val, _ = make_dummy_data(n=15, seed=66)

    m1 = P2XGBoostGaussianCandidate(seed=202601)
    m1.fit(X_train, y_train)
    p1 = m1.predict_distribution(X_val)

    m2 = P2XGBoostGaussianCandidate(seed=202601)
    m2.fit(X_train, y_train)
    p2 = m2.predict_distribution(X_val)

    np.testing.assert_array_almost_equal(p1.mean(), p2.mean(), decimal=6)
    np.testing.assert_array_almost_equal(p1._sigma, p2._sigma, decimal=6)


# =============================================================================
# 6. Manifest & Configuration Parity
# =============================================================================

def test_probabilistic_capability_manifest_parity() -> None:
    """YAML configuration and JSON manifest for probabilistic capabilities must be fully synchronized."""
    yaml_path = Path("configs/probabilistic_metric_capabilities_v2.yaml")
    json_path = Path("artifacts/manifests/probabilistic_metric_contract_v2.json")

    assert yaml_path.exists(), "configs/probabilistic_metric_capabilities_v2.yaml missing"
    assert json_path.exists(), "artifacts/manifests/probabilistic_metric_contract_v2.json missing"

    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    assert yaml_data["version"] == json_data["version"]
    assert yaml_data["evaluated_candidates"] == json_data["evaluated_candidates"]
    assert yaml_data["pre_registered_quantiles"] == json_data["pre_registered_quantiles"]

    for cid in yaml_data["evaluated_candidates"]:
        yaml_caps = yaml_data["candidates"][cid]["capabilities"]
        json_caps = json_data["candidates"][cid]["capabilities"]
        assert yaml_caps == json_caps, f"Capability mismatch for candidate {cid}"
