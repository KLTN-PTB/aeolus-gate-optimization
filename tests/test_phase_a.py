"""Unit tests for Phase A: Stratified Sampling, Naive Baselines, and Comprehensive Metrics."""

import numpy as np
import pandas as pd
import pytest

from src.data.stratified_loader import (
    get_month_distribution_report,
    load_stratified_year_data,
)
from src.models.baselines import NaiveDelayBaselines, compute_skill_score
from src.models.contracts import MetricContractViolation
from src.models.metrics import (
    compute_empirical_coverage,
    compute_pinball_loss,
    evaluate_all,
)


def test_stratified_loader_monthly_distribution() -> None:
    """Verify load_stratified_year_data produces uniform distribution across all 12 months."""
    # Test loading 1200 rows from year 2022
    target_samples = 1200
    df = load_stratified_year_data(2022, target_samples=target_samples, random_state=42)

    assert len(df) == target_samples
    report = get_month_distribution_report(df)

    assert len(report) == 12, "Should contain all 12 calendar months"
    # Each month should have target_samples // 12 = 100 rows
    for count in report["Count"]:
        assert count == 100

    # Percentage should be ~8.33% (+/- 0.1%)
    for pct in report["Percentage"]:
        assert pytest.approx(8.33, abs=0.1) == pct


def test_get_month_distribution_report_formats() -> None:
    """Test get_month_distribution_report with different month column naming schemes."""
    # MONTH column
    df_month = pd.DataFrame({"MONTH": [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]})
    rep1 = get_month_distribution_report(df_month)
    assert len(rep1) == 12

    # FL_DATE column
    df_date = pd.DataFrame({"FL_DATE": pd.date_range("2022-01-01", periods=12, freq="MS")})
    rep2 = get_month_distribution_report(df_date)
    assert len(rep2) == 12

    # calendar_month column
    df_cal = pd.DataFrame({"calendar_month": list(range(1, 13))})
    rep3 = get_month_distribution_report(df_cal)
    assert len(rep3) == 12

    # Missing column raises ValueError
    with pytest.raises(ValueError, match="Cannot locate month column"):
        get_month_distribution_report(pd.DataFrame({"other": [1, 2, 3]}))


def test_naive_delay_baselines_fit_predict() -> None:
    """Verify NaiveDelayBaselines computes medians and performs hierarchical fallback correctly."""
    # Training data
    # Carrier AA:
    #   Hour 8: delays [10.0, 20.0, 30.0] -> median 20.0
    #   Hour 10: delays [5.0, 15.0] -> median 10.0
    #   Overall AA delays: [10, 20, 30, 5, 15] -> median 15.0
    # Carrier DL:
    #   Hour 8: delays [0.0, 0.0] -> median 0.0
    #   Overall DL delays: [0, 0] -> median 0.0
    # Global delays: [10, 20, 30, 5, 15, 0, 0] -> median 10.0
    X_train = pd.DataFrame({
        "OP_CARRIER": ["AA", "AA", "AA", "AA", "AA", "DL", "DL"],
        "CRS_ARR_HOUR": [8, 8, 8, 10, 10, 8, 8],
    })
    y_train = np.array([10.0, 20.0, 30.0, 5.0, 15.0, 0.0, 0.0])

    baseline = NaiveDelayBaselines()
    baseline.fit(X_train, y_train)

    assert baseline.global_median_ == 10.0
    assert baseline.carrier_medians_["AA"] == 15.0
    assert baseline.carrier_medians_["DL"] == 0.0
    assert baseline.carrier_hour_medians_[("AA", 8)] == 20.0
    assert baseline.carrier_hour_medians_[("AA", 10)] == 10.0
    assert baseline.carrier_hour_medians_[("DL", 8)] == 0.0

    # Test cases for prediction
    X_test = pd.DataFrame({
        "OP_CARRIER": [
            "AA",   # Known carrier, known hour (AA, 8) -> 20.0
            "AA",   # Known carrier, unknown hour (AA, 14) -> carrier median 15.0
            "DL",   # Known carrier, known hour (DL, 8) -> 0.0
            "UA",   # Unknown carrier, unknown hour (UA, 12) -> global median 10.0
        ],
        "CRS_ARR_HOUR": [8, 14, 8, 12],
    })

    # Global median prediction
    p_global = baseline.predict_global_median(X_test)
    np.testing.assert_array_equal(p_global, np.array([10.0, 10.0, 10.0, 10.0]))

    # Carrier median prediction
    p_carrier = baseline.predict_carrier_median(X_test)
    np.testing.assert_array_equal(p_carrier, np.array([15.0, 15.0, 0.0, 10.0]))

    # Carrier-hour median prediction with hierarchical fallback
    p_carrier_hour = baseline.predict_carrier_hour_median(X_test)
    np.testing.assert_array_equal(p_carrier_hour, np.array([20.0, 15.0, 0.0, 10.0]))

    # Default predict() should equal carrier-hour median
    np.testing.assert_array_equal(baseline.predict(X_test), p_carrier_hour)


def test_naive_delay_baselines_alternative_columns() -> None:
    """Test NaiveDelayBaselines extracts columns under alternative names."""
    X = pd.DataFrame({
        "OP_UNIQUE_CARRIER": ["WN", "WN"],
        "scheduled_arrival_hour": [9, 15],
    })
    y = np.array([4.0, 8.0])
    baseline = NaiveDelayBaselines().fit(X, y)

    preds = baseline.predict(X)
    assert len(preds) == 2
    assert preds[0] == 4.0
    assert preds[1] == 8.0


def test_skill_score_calculation() -> None:
    """Test skill score percentage calculation relative to baseline."""
    # 20% improvement
    assert compute_skill_score(mae_model=20.0, mae_baseline=25.0) == pytest.approx(20.0)

    # 20% worse
    assert compute_skill_score(mae_model=30.0, mae_baseline=25.0) == pytest.approx(-20.0)

    # Perfect model (MAE = 0)
    assert compute_skill_score(mae_model=0.0, mae_baseline=25.0) == pytest.approx(100.0)

    # Identical model
    assert compute_skill_score(mae_model=25.0, mae_baseline=25.0) == pytest.approx(0.0)

    # Near zero baseline
    assert compute_skill_score(mae_model=10.0, mae_baseline=0.0) == 0.0


def test_pinball_loss_and_empirical_coverage() -> None:
    """Test pinball loss and empirical coverage functions."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    q = np.array([15.0, 25.0, 25.0, 45.0, 55.0])

    # Empirical coverage: y <= q
    # 10 <= 15 (True), 20 <= 25 (True), 30 <= 25 (False), 40 <= 45 (True), 50 <= 55 (True)
    # 4 / 5 = 80.0%
    cov = compute_empirical_coverage(y, q)
    assert cov == pytest.approx(80.0)

    # Pinball loss for alpha = 0.5 (Median / MAE * 0.5)
    loss_05 = compute_pinball_loss(y, q, alpha=0.5)
    mae_diff = np.mean(np.abs(y - q)) * 0.5
    assert loss_05 == pytest.approx(mae_diff)

    # Length mismatch raises MetricContractViolation
    with pytest.raises(MetricContractViolation):
        compute_pinball_loss(y, q[:3], alpha=0.5)

    with pytest.raises(MetricContractViolation):
        compute_empirical_coverage(y, q[:3])


def test_evaluate_all_metrics() -> None:
    """Test evaluate_all computes point, severe, tail ranking, classification, and quantile metrics."""
    np.random.seed(42)
    n = 100
    y_true = np.random.normal(loc=10.0, scale=30.0, size=n)
    # Force some severe delays >= 60
    y_true[:15] = np.random.uniform(65.0, 150.0, size=15)

    # Simulated predictions
    y_pred_point = y_true + np.random.normal(0, 10, size=n)
    y_prob_delay = np.clip((y_pred_point + 10) / 50.0, 0.0, 1.0)
    q_preds = {
        0.50: y_pred_point,
        0.75: y_pred_point + 15.0,
        0.90: y_pred_point + 30.0,
    }

    results = evaluate_all(
        y_true=y_true,
        y_pred_point=y_pred_point,
        y_prob_delay=y_prob_delay,
        q_preds=q_preds,
    )

    # Verify structure
    assert "point_regression" in results
    assert "severe_conditioned" in results
    assert "tail_risk_ranking" in results
    assert "classification_gate" in results
    assert "quantile_coverage" in results

    # Check point regression
    assert results["point_regression"]["mae"] > 0
    assert results["point_regression"]["rmse"] > 0
    assert results["point_regression"]["r2"] is not None

    # Check severe conditioned
    assert results["severe_conditioned"]["count"] >= 15
    assert results["severe_conditioned"]["severe_mae"] > 0
    assert results["severe_conditioned"]["shrinkage_ratio"] > 0

    # Check tail risk ranking
    assert 0.0 <= results["tail_risk_ranking"]["pr_auc_severe"] <= 1.0
    assert 0.0 <= results["tail_risk_ranking"]["roc_auc_severe"] <= 1.0

    # Check classification gate
    assert 0.0 <= results["classification_gate"]["roc_auc"] <= 1.0
    assert 0.0 <= results["classification_gate"]["pr_auc"] <= 1.0
    assert 0.0 <= results["classification_gate"]["brier_score"] <= 1.0

    # Check quantile coverage
    assert "pinball_loss_0.50" in results["quantile_coverage"]
    assert "pinball_loss_0.75" in results["quantile_coverage"]
    assert "pinball_loss_0.90" in results["quantile_coverage"]
    assert "coverage_0.50" in results["quantile_coverage"]
    assert "coverage_0.75" in results["quantile_coverage"]
    assert "coverage_0.90" in results["quantile_coverage"]
