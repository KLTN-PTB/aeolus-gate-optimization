"""Tests for Probability Calibration Inputs and Diagnostics in Phase 3."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.candidate_interfaces import P3NGBoostNormalCandidate
from src.models.probabilistic.evaluation_engine import evaluate_probabilistic_prediction
from src.models.probabilistic.metrics import compute_brier_score
from tests.probabilistic.test_distribution_contract import make_dummy_data


def test_brier_score_validity() -> None:
    """Verify Brier score computation for event Y >= 15."""
    y = np.array([20.0, 5.0, 15.0, -10.0])  # Actual indicators: [1, 0, 1, 0]
    p_perfect = np.array([1.0, 0.0, 1.0, 0.0])
    p_worst = np.array([0.0, 1.0, 0.0, 1.0])

    assert compute_brier_score(y, p_perfect, 15.0) == 0.0
    assert compute_brier_score(y, p_worst, 15.0) == 1.0


def test_calibration_diagnostics_structure() -> None:
    """Verify reliability table and ECE/MCE structure."""
    X_train, y_train = make_dummy_data(n=80, seed=12)
    X_val, y_val = make_dummy_data(n=30, seed=34)

    model = P3NGBoostNormalCandidate(seed=202601)
    model.fit(X_train, y_train)
    pred = model.predict_distribution(X_val)

    metrics = evaluate_probabilistic_prediction(pred, y_val)

    assert "calibration_diagnostics" in metrics
    cal = metrics["calibration_diagnostics"]
    assert "expected_calibration_error" in cal
    assert "maximum_calibration_error" in cal
    assert "reliability_table" in cal

    ece = cal["expected_calibration_error"]
    mce = cal["maximum_calibration_error"]
    assert 0.0 <= ece <= 1.0
    assert 0.0 <= mce <= 1.0
    assert ece <= mce + 1e-6

    # Verify PIT diagnostics
    assert "pit" in metrics
    assert "ks_statistic" in metrics["pit"]
    assert "ks_pvalue" in metrics["pit"]
    assert 0.0 <= metrics["pit"]["ks_statistic"] <= 1.0
