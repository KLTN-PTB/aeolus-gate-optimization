"""Tests for Common Evaluation Engine Independence and Capability-Aware Scoring.

Protocol: Phase 4 Common Distribution Contract
Tests:
- Evaluator operates purely on PredictiveDistribution interface
- Evaluator does not modify the predictive distribution
- Rejects corrupted distributions (fail-closed)
- Capability-aware metric accounting (NOT_AVAILABLE for unsupported capabilities)
- No silent imputation or fabrication of metrics
"""

from __future__ import annotations

import copy
import numpy as np
import pytest

from src.contracts.distribution import (
    DistributionValidationError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    QuantilePredictiveDistribution,
)
from src.evaluation.forecast_metrics import evaluate_predictive_distribution
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


def test_evaluator_does_not_modify_distribution() -> None:
    """Verify that evaluate_predictive_distribution is side-effect free."""
    mu = np.array([5.0, 10.0, 15.0])
    sigma = np.array([3.0, 4.0, 5.0])
    dist = GaussianResidualDistribution(mu=mu, sigma=sigma)

    mu_before = np.copy(dist._mu)
    sigma_before = np.copy(dist._sigma)
    y_true = np.array([6.0, 8.0, 14.0])

    metrics = evaluate_predictive_distribution(dist, y_true)

    # Verification: parameters untouched
    np.testing.assert_array_equal(dist._mu, mu_before)
    np.testing.assert_array_equal(dist._sigma, sigma_before)
    assert isinstance(metrics, dict)
    assert "crps" in metrics
    assert "nll" in metrics


def test_evaluator_rejects_corrupted_distribution() -> None:
    """Verify that evaluator calls validate() and fails closed on corrupt distributions."""
    mu_corrupt = np.array([5.0, np.nan, 15.0])
    sigma_valid = np.array([3.0, 4.0, 5.0])
    dist_corrupt = GaussianResidualDistribution(mu=mu_corrupt, sigma=sigma_valid)
    y_true = np.array([5.0, 10.0, 15.0])

    with pytest.raises(DistributionValidationError):
        evaluate_predictive_distribution(dist_corrupt, y_true)


def test_evaluator_handles_quantile_model_without_cdf() -> None:
    """Verify that pure quantile models report NLL, Brier, and PIT as NOT_AVAILABLE without failing."""
    n_flights = 20
    rng = np.random.default_rng(202601)
    alphas = sorted(PRE_REGISTERED_QUANTILES)

    # Monotone quantiles per row
    q_data = {}
    base = rng.normal(8.0, 10.0, size=n_flights)
    for i, a in enumerate(alphas):
        q_data[a] = base + i * 2.5

    dist = QuantilePredictiveDistribution(quantiles_dict=q_data)
    y_true = base + 5.0

    metrics = evaluate_predictive_distribution(dist, y_true)

    # Quantile metrics must be computed properly
    assert isinstance(metrics["pinball_losses"], dict)
    assert len(metrics["pinball_losses"]) == len(alphas)
    assert isinstance(metrics["crps"], float)
    assert metrics["crps"] > 0.0

    # Unsupported metrics MUST be marked NOT_AVAILABLE without throwing or imputing
    assert metrics["nll"] == "NOT_AVAILABLE"
    assert metrics["brier_score_delay_ge_15"] == "NOT_AVAILABLE"
    assert metrics["pit"]["status"] == "NOT_AVAILABLE"
    assert "not support" in metrics["pit"]["reason"].lower()


def test_evaluator_handles_empirical_model_without_nll() -> None:
    """Verify that Empirical model evaluates CRPS and Brier, but reports NLL as NOT_AVAILABLE."""
    n_flights = 10
    pool = np.array([-5.0, 0.0, 5.0, 12.0, 20.0, 35.0, 60.0])
    pools = [pool for _ in range(n_flights)]
    mean_vals = np.full(n_flights, float(np.mean(pool)))
    median_vals = np.full(n_flights, float(np.median(pool)))
    quantiles_dict = {a: np.full(n_flights, float(np.quantile(pool, a))) for a in PRE_REGISTERED_QUANTILES}
    p_ge_15 = np.full(n_flights, float(np.mean(pool >= 15.0)))

    dist = EmpiricalDistribution(
        mean_vals=mean_vals,
        median_vals=median_vals,
        quantiles_dict=quantiles_dict,
        p_ge_15_vals=p_ge_15,
        sample_pool_list=pools,
    )
    y_true = np.full(n_flights, 10.0)

    metrics = evaluate_predictive_distribution(dist, y_true)

    assert isinstance(metrics["crps"], float)
    assert isinstance(metrics["brier_score_delay_ge_15"], float)
    assert metrics["nll"] == "NOT_AVAILABLE"
    assert metrics["pit"]["status"] in {"AVAILABLE", "NOT_AVAILABLE"}
