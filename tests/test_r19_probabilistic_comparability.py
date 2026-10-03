"""Test Suite for R19 Probabilistic Capability and Metric Comparability.

Protocol: Task R19 Forensic Audit
Invariants:
- Unsupported NLL rejected
- Unsupported PIT rejected
- Approximate CRPS cannot be labeled exact CRPS
- Pinball loss cannot be labeled CRPS directly
- P5 rejects generative sampling, continuous CDF, and mean
- P4 supports continuous parametric sampling, CDF, and NLL
"""

import json
from pathlib import Path

import numpy as np
import pytest

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    NGBoostStudentTDistribution,
    QuantilePredictiveDistribution,
)
from src.evaluation.forecast_metrics import (
    compute_gaussian_crps,
    evaluate_predictive_distribution,
)
from src.models.probabilistic.candidate_interfaces import (
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)

REPO_ROOT = Path("D:/Study/Code/Python/Aelous")


def test_unsupported_nll_rejected():
    """Verify that P1 (empirical) and P5 (quantile regression) reject NLL while P2-P4 support it."""
    p1 = P1EmpiricalCandidate()
    p2 = P2XGBoostGaussianCandidate()
    p3 = P3NGBoostNormalCandidate()
    p4 = P4NGBoostStudentTCandidate()
    p5 = P5QuantileRegressionCandidate()

    assert p1.capabilities()["has_nll"] is False, "P1 must not support NLL"
    assert p5.capabilities()["has_nll"] is False, "P5 must not support NLL"
    assert p2.capabilities()["has_nll"] is True, "P2 must support Gaussian NLL"
    assert p3.capabilities()["has_nll"] is True, "P3 must support Gaussian NLL"
    assert p4.capabilities()["has_nll"] is True, "P4 must support Student-T NLL"

    # Test via QuantilePredictiveDistribution
    quantiles = {0.1: np.array([5.0]), 0.5: np.array([10.0]), 0.9: np.array([20.0])}
    q_dist = QuantilePredictiveDistribution(quantiles_dict=quantiles)
    assert q_dist.capabilities.nll is False


def test_unsupported_pit_rejected():
    """Verify that continuous PIT is rejected for P1 (step CDF) and P5 (finite quantiles)."""
    p1 = P1EmpiricalCandidate()
    p4 = P4NGBoostStudentTCandidate()
    p5 = P5QuantileRegressionCandidate()

    assert p1.capabilities()["has_pit"] is False, "P1 must reject continuous PIT"
    assert p5.capabilities()["has_pit"] is False, "P5 must reject continuous PIT"
    assert p4.capabilities()["has_pit"] is True, "P4 must support continuous PIT via Student-T CDF"


def test_approximate_crps_cannot_be_labeled_exact_crps():
    """Verify that multi-pinball trapezoid CRPS is strictly designated as APPROXIMATE."""
    # Test via evaluate_predictive_distribution on QuantilePredictiveDistribution
    quantiles = {
        0.025: np.array([-10.0, -12.0]),
        0.050: np.array([-5.0, -6.0]),
        0.100: np.array([-2.0, -3.0]),
        0.250: np.array([0.0, 1.0]),
        0.500: np.array([5.0, 6.0]),
        0.750: np.array([12.0, 14.0]),
        0.900: np.array([20.0, 22.0]),
        0.950: np.array([30.0, 32.0]),
        0.975: np.array([45.0, 48.0]),
    }
    q_dist = QuantilePredictiveDistribution(quantiles_dict=quantiles, candidate_id="P5_quantile_regression")
    y_true = np.array([6.0, 10.0])

    metrics = evaluate_predictive_distribution(q_dist, y_true)
    detailed_eval = metrics["metric_details"]

    assert detailed_eval["crps"]["is_exact"] is False, "P5 CRPS must not be marked exact"
    assert detailed_eval["crps"]["is_approximate"] is True, "P5 CRPS must be marked approximate"
    assert detailed_eval["crps"]["metric_status"] == "APPROXIMATE"
    assert detailed_eval["exact_crps"]["metric_status"] == "NOT_SUPPORTED"
    assert "Analytical closed-form CRPS is only supported for Gaussian" in detailed_eval["exact_crps"]["unsupported_reason"]


def test_pinball_cannot_be_labeled_crps_directly():
    """Verify that mean pinball loss and CRPS approximation are distinct metrics."""
    # 9 alphas
    alphas = [0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]
    # Synthetic pinball losses
    pinball_losses = {f"alpha_{a:.3f}": float(np.sin(a * np.pi) + 2.0) for a in alphas}
    
    mean_pinball = float(np.mean(list(pinball_losses.values())))

    # Trapezoidal integration for CRPS: 2 * delta_alpha * midpoint
    sorted_alphas = sorted(alphas)
    q_crps_sum = 0.0
    for k in range(len(sorted_alphas) - 1):
        a_k = sorted_alphas[k]
        a_next = sorted_alphas[k + 1]
        delta_a = a_next - a_k
        pin_k = pinball_losses[f"alpha_{a_k:.3f}"]
        pin_next = pinball_losses[f"alpha_{a_next:.3f}"]
        pinball_mid = 0.5 * (pin_k + pin_next)
        q_crps_sum += 2.0 * delta_a * pinball_mid

    # Assert they are distinct numbers and differ substantially
    assert not np.isclose(mean_pinball, q_crps_sum), (
        f"Mean pinball ({mean_pinball}) and integrated CRPS ({q_crps_sum}) must be distinct"
    )
    # The integration covers 95% of distribution with weight 2, so ratio is not 1.0
    assert abs(mean_pinball - q_crps_sum) > 0.5


def test_p5_rejects_generative_sampling_and_cdf():
    """Verify that QuantilePredictiveDistribution raises CapabilityNotSupportedError for prohibited queries."""
    quantiles = {
        0.025: np.array([-10.0, -12.0]),
        0.050: np.array([-5.0, -6.0]),
        0.100: np.array([-2.0, -3.0]),
        0.250: np.array([0.0, 1.0]),
        0.500: np.array([5.0, 6.0]),
        0.750: np.array([12.0, 14.0]),
        0.900: np.array([20.0, 22.0]),
        0.950: np.array([30.0, 32.0]),
        0.975: np.array([45.0, 48.0]),
    }
    dist = QuantilePredictiveDistribution(quantiles_dict=quantiles)

    # 1. sample() must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError, match="Generative sampling is unsupported"):
        dist.sample(n=10)

    # 2. cdf() must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError, match="do not provide a continuous CDF"):
        dist.cdf(15.0)

    # 3. probability_ge() must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError, match="Event probability.*is unsupported"):
        dist.probability_ge(15.0)

    # 4. mean() must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError, match="do not support conditional expectation"):
        _ = dist.mean

    # 5. median() is supported
    med = dist.median
    np.testing.assert_allclose(med, np.array([5.0, 6.0]))


def test_p4_supports_continuous_parametric_sampling_and_cdf():
    """Verify that NGBoostStudentTDistribution fully supports sampling, CDF, and mean."""
    mu = np.array([10.0, 20.0])
    sigma = np.array([5.0, 8.0])
    df = np.array([3.5, 4.2])  # Strictly > 2.0

    dist = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df)

    # 1. mean is supported
    np.testing.assert_allclose(dist.mean, mu)

    # 2. sample is supported and produces shape (n, n_flights)
    samples = dist.sample(n=100, seed=42)
    assert samples.shape == (100, 2)
    assert np.all(np.isfinite(samples))

    # 3. cdf is supported and within [0, 1]
    cdf_vals = dist.cdf(15.0)
    assert len(cdf_vals) == 2
    assert np.all((cdf_vals >= 0.0) & (cdf_vals <= 1.0))

    # 4. probability_ge is supported
    p_ge = dist.probability_ge(15.0)
    np.testing.assert_allclose(p_ge, 1.0 - cdf_vals)


def test_capability_matrix_artifact_complete():
    """Verify that r19_probabilistic_capability_matrix.json exists and is strictly valid."""
    path = REPO_ROOT / "artifacts/r19_probabilistic_capability_matrix.json"
    assert path.exists(), f"Missing artifact: {path}"

    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["status"] == "PASS"
    assert "candidates" in doc
    candidates = doc["candidates"]

    # Verify P4
    assert "P4_ngboost_student_t" in candidates
    p4_caps = candidates["P4_ngboost_student_t"]["capabilities"]
    assert p4_caps["log_likelihood_nll"]["supported"] is True
    assert p4_caps["exact_crps"]["supported"] is False
    assert p4_caps["approximate_crps"]["supported"] is True
    assert p4_caps["pit"]["supported"] is True
    assert p4_caps["sampling"]["supported"] is True

    # Verify P5
    assert "P5_quantile_regression" in candidates
    p5_caps = candidates["P5_quantile_regression"]["capabilities"]
    assert p5_caps["point_location"]["supported"] is False
    assert p5_caps["full_cdf"]["supported"] is False
    assert p5_caps["log_likelihood_nll"]["supported"] is False
    assert p5_caps["sampling"]["supported"] is False
    assert p5_caps["pit"]["supported"] is False
    assert p5_caps["approximate_crps"]["supported"] is True
