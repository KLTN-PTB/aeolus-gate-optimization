"""Tests for Candidate Capability Declarations and Omission of Unsupported Metrics."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.candidate_interfaces import (
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)
from src.models.probabilistic.evaluation_engine import evaluate_probabilistic_prediction
from tests.probabilistic.test_distribution_contract import make_dummy_data


def test_candidate_capability_declarations() -> None:
    """Verify that capabilities accurately reflect model properties without fabrication."""
    p1 = P1EmpiricalCandidate()
    p2 = P2XGBoostGaussianCandidate()
    p3 = P3NGBoostNormalCandidate()
    p4 = P4NGBoostStudentTCandidate()
    p5 = P5QuantileRegressionCandidate()

    # P1 (Empirical) does not support continuous NLL
    assert not p1.capabilities()["has_nll"]
    assert p1.capabilities()["has_crps"]

    # P2 (XGBoost + Gaussian) supports parametric NLL and CRPS
    assert p2.capabilities()["has_nll"]
    assert p2.capabilities()["has_crps"]

    # P3 (NGBoost Normal) supports parametric NLL and CRPS
    assert p3.capabilities()["has_nll"]
    assert p3.capabilities()["has_crps"]

    # P4 (NGBoost Student-T) supports parametric NLL and CRPS, designated as historical
    assert p4.capabilities()["has_nll"]
    assert p4.capabilities()["has_crps"]

    # P5 (Quantile Regression) does not support mean or continuous NLL
    assert not p5.capabilities()["has_mean"]
    assert not p5.capabilities()["has_nll"]
    assert p5.capabilities()["has_median"]
    assert p5.capabilities()["has_quantiles"]


def test_unsupported_metrics_marked_not_available() -> None:
    """When a model lacks capability, corresponding metrics evaluate to NOT_AVAILABLE."""
    X_train, y_train = make_dummy_data(n=60, seed=1)
    X_val, y_val = make_dummy_data(n=20, seed=2)

    # Evaluate P5
    p5 = P5QuantileRegressionCandidate(seed=202601)
    p5.fit(X_train, y_train)
    pred_p5 = p5.predict_distribution(X_val)

    # Mean must raise CapabilityNotSupportedError
    from src.contracts.distribution import CapabilityNotSupportedError

    with pytest.raises(CapabilityNotSupportedError):
        _ = pred_p5.mean()

    # CDF must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = pred_p5.cdf(15.0)

    # Sampling must raise CapabilityNotSupportedError
    with pytest.raises(CapabilityNotSupportedError):
        _ = pred_p5.sample(10)

    metrics_p5 = evaluate_probabilistic_prediction(pred_p5, y_val)
    # NLL, Brier score, and PIT must evaluate strictly to NOT_AVAILABLE
    assert metrics_p5["nll"] == "NOT_AVAILABLE"
    assert metrics_p5["brier_score_delay_ge_15"] == "NOT_AVAILABLE"
    assert metrics_p5["pit"]["status"] == "NOT_AVAILABLE"

    # Evaluate P1
    p1 = P1EmpiricalCandidate(seed=202601)
    p1.fit(X_train, y_train)
    pred_p1 = p1.predict_distribution(X_val)
    metrics_p1 = evaluate_probabilistic_prediction(pred_p1, y_val)
    assert metrics_p1["nll"] == "NOT_AVAILABLE"


def test_ngboost_student_t_designated_as_historical_candidate() -> None:
    """NGBoost Student-T must have role='historical_candidate' and not assumed champion."""
    p4 = P4NGBoostStudentTCandidate(seed=202601)
    X_train, y_train = make_dummy_data(n=40, seed=1)
    X_val, _ = make_dummy_data(n=10, seed=2)

    p4.fit(X_train, y_train)
    pred = p4.predict_distribution(X_val)

    assert pred.metadata.get("role") == "historical_candidate"
    assert pred.metadata.get("family") == "ngboost_student_t"
