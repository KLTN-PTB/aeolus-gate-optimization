"""Tests for Paired Statistical Comparison Engine.

Protocol: Phase 5 Paired Statistical Comparison
Required Tests:
- Exact pairing on flight_key and metadata
- Sign correctness for error (lower is better) and score (higher is better) metrics
- Missing row detection (fail-closed, no silent inner join)
- Deterministic bootstrap sampling under seed
- Identical predictions produce delta = 0 and fraction_unchanged = 1.0
- Known synthetic case matching analytical values
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.paired_comparison import (
    PairedAlignmentError,
    compare_model_pair,
    compute_paired_bootstrap_ci,
    compute_paired_classification_metrics,
    compute_paired_regression_metrics,
    validate_paired_alignment,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


def test_exact_pairing_success() -> None:
    """Verify exact alignment when flight_keys match but row order differs."""
    keys = [f"flight_key_{i:04d}" for i in range(100)]
    y_reg = np.linspace(-10.0, 50.0, 100)
    y_cls = (y_reg >= 15.0).astype(float)

    df_a = pd.DataFrame({
        "flight_key": keys,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": y_reg,
        "y_arr_cls": y_cls,
        "predicted_arr_delay_min": y_reg + 1.0,
    })

    # Shuffle df_b
    rng = np.random.default_rng(42)
    shuffled_idx = rng.permutation(100)
    df_b = df_a.iloc[shuffled_idx].copy()
    df_b["predicted_arr_delay_min"] = y_reg[shuffled_idx] + 2.0

    df_a_aligned, df_b_aligned, report = validate_paired_alignment(df_a, df_b)

    assert report.is_valid_alignment
    assert report.status == "MATCHED"
    assert report.expected_rows == 100
    assert report.matched_rows == 100
    assert report.unmatched_rows == 0
    assert report.missing_predictions == 0

    # Row keys must now be perfectly aligned row-for-row
    np.testing.assert_array_equal(df_a_aligned["flight_key"], df_b_aligned["flight_key"])


def test_missing_row_detection_fails_closed() -> None:
    """Verify that missing observations fail closed and are NOT silently dropped."""
    keys_a = [f"flight_key_{i:04d}" for i in range(100)]
    keys_b = keys_a[:97]  # Model B is missing 3 rows

    df_a = pd.DataFrame({
        "flight_key": keys_a,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": np.zeros(100),
        "y_arr_cls": np.zeros(100),
        "predicted_arr_delay_min": np.zeros(100),
    })

    df_b = pd.DataFrame({
        "flight_key": keys_b,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": np.zeros(97),
        "y_arr_cls": np.zeros(97),
        "predicted_arr_delay_min": np.zeros(97),
    })

    # validate_paired_alignment must return BLOCKED status with unmatched rows recorded
    df_a_res, df_b_res, report = validate_paired_alignment(df_a, df_b)
    assert not report.is_valid_alignment
    assert report.status == "BLOCKED"
    assert report.expected_rows == 100
    assert report.matched_rows == 97
    assert report.unmatched_rows == 3
    assert report.missing_predictions == 3
    assert any("missing in Model B" in issue for issue in report.issues)

    # compare_model_pair must return status BLOCKED
    res = compare_model_pair(
        df_a, df_b, "model_a", "model_b", "point_regression", "fold_1", 2019
    )
    assert res.status == "BLOCKED"
    assert "Row alignment validation failed" in str(res.failure_reason)


def test_sign_correctness_for_error_and_score_metrics() -> None:
    """Verify sign semantics: Delta < 0 means improvement for error metrics; Delta > 0 for score metrics."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    # Model A error = 1.0 everywhere; Model B error = 3.0 everywhere
    pred_a = y + 1.0
    pred_b = y + 3.0

    reg_deltas = compute_paired_regression_metrics(y, pred_a, pred_b)

    # Delta MAE = 1.0 - 3.0 = -2.0 (Model A is better -> negative delta)
    assert reg_deltas["delta_mae"].mean_delta == pytest.approx(-2.0)
    assert reg_deltas["delta_mae"].fraction_improved == 1.0
    assert reg_deltas["delta_mae"].fraction_worse == 0.0

    # Delta R^2: Model A has lower error -> higher R^2 -> positive delta
    assert reg_deltas["delta_r2"].mean_delta > 0.0
    assert reg_deltas["delta_r2"].fraction_improved == 1.0
    assert reg_deltas["delta_r2"].fraction_worse == 0.0

    # Classification: Brier score
    y_cls = np.array([1.0, 1.0, 0.0, 0.0])
    p_a = np.array([0.9, 0.9, 0.1, 0.1])  # Better probabilities
    p_b = np.array([0.6, 0.6, 0.4, 0.4])  # Worse probabilities

    cls_deltas = compute_paired_classification_metrics(y_cls, p_a, p_b)
    # Delta Brier < 0 indicates Model A improvement
    assert cls_deltas["delta_brier"].mean_delta < 0.0
    assert cls_deltas["delta_brier"].fraction_improved == 1.0
    assert cls_deltas["delta_brier"].fraction_worse == 0.0


def test_deterministic_bootstrap() -> None:
    """Verify that bootstrap confidence intervals are strictly deterministic given a fixed seed."""
    rng = np.random.default_rng(1234)
    deltas = rng.normal(-1.5, 0.8, size=200)

    ci_low_1, ci_high_1, se_1 = compute_paired_bootstrap_ci(deltas, seed=202601)
    ci_low_2, ci_high_2, se_2 = compute_paired_bootstrap_ci(deltas, seed=202601)

    assert ci_low_1 == ci_low_2
    assert ci_high_1 == ci_high_2
    assert se_1 == se_2

    # Variation with different seed
    ci_low_diff, ci_high_diff, _ = compute_paired_bootstrap_ci(deltas, seed=99999)
    assert ci_low_1 != ci_low_diff or ci_high_1 != ci_high_diff


def test_identical_predictions_delta_zero() -> None:
    """Verify that identical model predictions yield delta = 0 and fraction_unchanged = 1.0."""
    y = np.array([5.0, 10.0, 15.0, 20.0, 25.0])
    pred = np.array([6.0, 9.0, 14.0, 22.0, 24.0])

    deltas = compute_paired_regression_metrics(y, pred, pred)

    assert deltas["delta_mae"].mean_delta == 0.0
    assert deltas["delta_mae"].median_delta == 0.0
    assert deltas["delta_mae"].std_delta == 0.0
    assert deltas["delta_mae"].ci_lower == 0.0
    assert deltas["delta_mae"].ci_upper == 0.0
    assert deltas["delta_mae"].fraction_improved == 0.0
    assert deltas["delta_mae"].fraction_worse == 0.0
    assert deltas["delta_mae"].fraction_unchanged == 1.0


def test_known_synthetic_case() -> None:
    """Verify exact analytical values on known synthetic paired inputs."""
    y = np.array([10.0, 20.0, 30.0, 40.0])
    pred_a = np.array([11.0, 19.0, 31.0, 39.0])  # absolute errors all 1.0
    pred_b = np.array([13.0, 17.0, 33.0, 37.0])  # absolute errors all 3.0

    res = compute_paired_regression_metrics(y, pred_a, pred_b)

    # MAE_A = 1.0, MAE_B = 3.0 -> Delta MAE = -2.0
    assert res["delta_mae"].model_a_mean == 1.0
    assert res["delta_mae"].model_b_mean == 3.0
    assert res["delta_mae"].mean_delta == -2.0
    assert res["delta_mae"].median_delta == -2.0
    assert res["delta_mae"].std_delta == 0.0
    assert res["delta_mae"].ci_lower == -2.0
    assert res["delta_mae"].ci_upper == -2.0
    assert res["delta_mae"].fraction_improved == 1.0
    assert res["delta_mae"].fraction_worse == 0.0
    assert res["delta_mae"].fraction_unchanged == 0.0
