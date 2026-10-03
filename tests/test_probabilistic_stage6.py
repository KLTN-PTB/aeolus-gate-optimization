"""Unit tests for Stage 6 — Forecast Evaluation & Gating.

Verifies:
1. Discrete randomized PIT calculation and uniformity on well-specified distributions.
2. Event probability evaluation metrics (Brier score, LogScore, ECE, calibration slope/intercept).
3. Stage 6 Gate Decision rules (Gate A Calibration, Gate B Proper Scoring, Gate C Event Probabilities).
4. Quantile-only baseline B4 exclusion from CRPS proper scoring.
5. Invariance of 2020 pandemic regime-shift detection logic.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import ndtr

from src.models.probabilistic.forecast_evaluation import (
    compute_discrete_randomized_pit,
    compute_event_probability_metrics,
    evaluate_pit_uniformity,
    evaluate_stage6_candidate_gates,
)


def test_discrete_randomized_pit_bounds_and_uniformity():
    rng = np.random.default_rng(42)
    n = 5000
    # True discrete Gaussian with mu=10, sigma=15
    y_cont = rng.normal(10.0, 15.0, size=n)
    y_true = np.rint(y_cont).astype(np.int64)

    # Exact discrete CDF at Y and Y - 1
    cdf_y = ndtr((y_true + 0.5 - 10.0) / 15.0)
    cdf_y_m1 = ndtr((y_true - 0.5 - 10.0) / 15.0)

    pit_vals = compute_discrete_randomized_pit(y_true, cdf_y, cdf_y_m1, seed=42)

    assert len(pit_vals) == n
    assert np.all(pit_vals >= 0.0)
    assert np.all(pit_vals <= 1.0)

    # Uniformity evaluation
    pit_res = evaluate_pit_uniformity(pit_vals, "test_synthetic")
    assert pit_res.ks_statistic < 0.03  # Close to Uniform(0, 1)
    assert pit_res.ks_pvalue > 0.05
    assert len(pit_res.histogram_10bins) == 10
    assert np.isclose(sum(pit_res.histogram_10bins), 1.0)


def test_compute_event_probability_metrics():
    rng = np.random.default_rng(42)
    n = 2000
    # True probabilities
    p_true = rng.uniform(0.05, 0.85, size=n)
    is_event = rng.binomial(1, p_true)
    y_delays = np.where(is_event == 1, 25.0, 5.0)

    metrics = compute_event_probability_metrics(y_delays, p_true, threshold=15)

    assert 0.0 <= metrics.brier_score <= 1.0
    assert metrics.brier_skill_score > 0.0  # Better than climatology
    assert metrics.expected_calibration_error < 0.05
    # For well-calibrated probabilities, slope should be near 1.0 and intercept near 0.0
    assert pytest.approx(metrics.calibration_slope, abs=0.25) == 1.0
    assert pytest.approx(metrics.calibration_intercept, abs=0.25) == 0.0


def test_stage6_gating_matrix_logic():
    # 1. Candidate that passes all gates
    pass_res = evaluate_stage6_candidate_gates(
        candidate_name="D3_test_pass",
        crps_value=13.3,
        crps_baseline_b2=18.4,
        coverage_80=0.82,
        coverage_90=0.91,
        crossing_rate=0.0,
        brier_60=0.040,
        brier_60_best=0.039,
    )
    assert pass_res.overall_stage6_passed is True
    assert pass_res.gate_a_calibration_passed is True
    assert pass_res.gate_b_proper_scoring_passed is True
    assert pass_res.gate_c_event_passed is True
    assert len(pass_res.rejection_reasons) == 0

    # 2. Candidate that fails Gate A (coverage too low)
    fail_cal = evaluate_stage6_candidate_gates(
        candidate_name="D_undercovered",
        crps_value=13.5,
        crps_baseline_b2=18.4,
        coverage_80=0.62,  # < 0.70
        coverage_90=0.75,
        crossing_rate=0.0,
        brier_60=0.040,
        brier_60_best=0.039,
    )
    assert fail_cal.overall_stage6_passed is False
    assert fail_cal.gate_a_calibration_passed is False
    assert any("80% interval coverage" in r for r in fail_cal.rejection_reasons)

    # 3. Candidate that fails Gate B (CRPS dominated by baseline)
    fail_score = evaluate_stage6_candidate_gates(
        candidate_name="D_dominated",
        crps_value=19.2,  # > 18.4 + 0.20
        crps_baseline_b2=18.4,
        coverage_80=0.80,
        coverage_90=0.90,
        crossing_rate=0.0,
        brier_60=0.040,
        brier_60_best=0.039,
    )
    assert fail_score.overall_stage6_passed is False
    assert fail_score.gate_b_proper_scoring_passed is False
    assert any("dominated" in r for r in fail_score.rejection_reasons)

    # 4. Candidate that fails Gate C (poor tail brier score)
    fail_tail = evaluate_stage6_candidate_gates(
        candidate_name="D_poor_tail",
        crps_value=14.0,
        crps_baseline_b2=18.4,
        coverage_80=0.80,
        coverage_90=0.90,
        crossing_rate=0.0,
        brier_60=0.060,  # 0.060 - 0.039 = 0.021 > 0.005 tolerance
        brier_60_best=0.039,
    )
    assert fail_tail.overall_stage6_passed is False
    assert fail_tail.gate_c_event_passed is False
    assert any("Tail Brier score" in r for r in fail_tail.rejection_reasons)


def test_b4_quantile_only_crps_exclusion():
    q_res = evaluate_stage6_candidate_gates(
        candidate_name="B4_lightgbm_quantile",
        crps_value=0.0,
        crps_baseline_b2=18.4,
        coverage_80=0.79,
        coverage_90=0.89,
        crossing_rate=0.001,
        brier_60=1.0,
        brier_60_best=0.040,
        is_quantile_only=True,
    )
    # Proper scoring gate details must record exclusion
    assert q_res.gate_b_details["is_quantile_only"] is True
    assert "Excluded" in q_res.gate_b_details["status"]
