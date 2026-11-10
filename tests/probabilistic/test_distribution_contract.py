"""Tests for Distributional Contract and Common Representation in Phase 3."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.candidate_interfaces import (
    BaseProbabilisticCandidate,
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
    ProbabilisticPrediction,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


def make_dummy_data(n: int = 120, seed: int = 202601) -> tuple[pd.DataFrame, np.ndarray]:
    """Create synthetic training data adhering strictly to APPROVED_PREDICTOR_COLUMNS."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "CRS_ELAPSED_TIME": rng.uniform(60, 240, size=n),
            "calendar_year": rng.choice([2016, 2017, 2018], size=n),
            "calendar_month": rng.integers(1, 13, size=n),
            "calendar_day_of_month": rng.integers(1, 29, size=n),
            "calendar_day_of_week": rng.integers(1, 8, size=n),
            "is_weekend": rng.integers(0, 2, size=n),
            "scheduled_departure_hour": rng.integers(6, 23, size=n),
            "scheduled_departure_minute": rng.integers(0, 60, size=n),
            "OP_CARRIER": rng.choice(["AA", "DL", "UA", "WN"], size=n),
            "ORIGIN": rng.choice(["BOS", "LGA", "MCO", "ORD"], size=n),
            "OP_CARRIER_FL_NUM": rng.choice(["101", "202", "303"], size=n),
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]
    y = rng.normal(8.0, 18.0, size=n).round(1)
    return df, y


@pytest.mark.parametrize(
    "candidate_cls,expected_id",
    [
        (P1EmpiricalCandidate, "P1_empirical"),
        (P2XGBoostGaussianCandidate, "P2_xgb_gaussian_oof"),
        (P3NGBoostNormalCandidate, "P3_ngboost_normal"),
        (P4NGBoostStudentTCandidate, "P4_ngboost_student_t"),
        (P5QuantileRegressionCandidate, "P5_quantile_regression"),
    ],
)
def test_candidate_contract_and_common_representation(
    candidate_cls: type[BaseProbabilisticCandidate], expected_id: str
) -> None:
    """Verify that all 5 candidates inherit BaseProbabilisticCandidate and emit valid common outputs."""
    X_train, y_train = make_dummy_data(n=80, seed=1)
    X_val, _ = make_dummy_data(n=25, seed=2)

    candidate = candidate_cls(seed=202601)
    assert isinstance(candidate, BaseProbabilisticCandidate)
    assert candidate.candidate_id == expected_id

    # Capabilities must return non-empty dict
    caps = candidate.capabilities()
    assert isinstance(caps, dict)
    assert "has_median" in caps
    assert "has_quantiles" in caps
    assert "has_cdf" in caps
    assert "has_p_delay_ge_15" in caps

    # Fit and predict distribution
    candidate.fit(X_train, y_train)
    assert candidate.is_fitted_

    pred = candidate.predict_distribution(X_val)
    assert isinstance(pred, ProbabilisticPrediction)

    # Check common output components
    assert len(pred.median) == len(X_val)
    if caps.get("has_p_delay_ge_15", False):
        assert len(pred.p_delay_ge_15) == len(X_val)
    assert set(pred.quantiles.keys()) == set(PRE_REGISTERED_QUANTILES)
    if caps.get("has_cdf", False):
        assert callable(pred.cdf)
    if caps.get("has_sampler", False):
        assert callable(pred.sampler)
    assert pred.metadata["candidate_id"] == expected_id
