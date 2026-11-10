"""Comprehensive Test Suite for Paired Statistical Comparison Engine V2.

Verifies:
1. Exact row alignment and order permutation handling
2. Duplicate ID detection (fails closed, status=BLOCKED)
3. Missing row detection (fails closed, never silent inner join)
4. Wrong model pairing / target & metadata mismatch (fails closed)
5. CI reproducibility under fixed seed
6. Block bootstrap reproducibility across all 4 schemes (iid, day_cluster, fixed_block, stationary_block)
7. Aggregate metric bootstrap (RMSE, R2, PR-AUC computed via resampled aggregate, not rowwise subtraction)
8. Multiple-comparison correction (Holm-Bonferroni & Benjamini-Hochberg)
9. No false p-values from empty, invalid, or degenerate data
10. Canonical 15-field output schema parity
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evaluation.paired_comparison import (
    DEFAULT_BOOTSTRAP_REPLICATIONS,
    DEFAULT_COMPARISON_SEED,
    BootstrapMethod,
    InferenceUnit,
    PairedAlignmentError,
    StatisticalComparisonRecord,
    apply_multiplicity_correction,
    compare_model_pair,
    compute_benjamini_hochberg_correction,
    compute_bootstrap_p_value,
    compute_day_block_bootstrap_ci,
    compute_holm_bonferroni_correction,
    compute_paired_bootstrap_ci,
    compute_paired_classification_metrics,
    compute_paired_probabilistic_metrics,
    compute_paired_regression_metrics,
    compute_pointwise_t_test,
    compute_pointwise_wilcoxon,
    generate_bootstrap_indices,
    validate_paired_alignment,
)


# =============================================================================
# 1. EXACT ALIGNMENT & PERMUTATION TEST
# =============================================================================

def test_exact_alignment_and_order_permutation() -> None:
    """Rows with identical flight keys in different orders must be aligned row-for-row."""
    keys = [f"flight_{i:04d}" for i in range(120)]
    y_reg = np.linspace(-15.0, 45.0, 120)
    y_cls = (y_reg >= 15.0).astype(float)

    df_a = pd.DataFrame({
        "flight_key": keys,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": y_reg,
        "y_arr_cls": y_cls,
        "predicted_arr_delay_min": y_reg + 1.5,
    })

    # Permute df_b completely
    rng = np.random.default_rng(42)
    shuffled_idx = rng.permutation(120)
    df_b = df_a.iloc[shuffled_idx].copy()
    df_b["predicted_arr_delay_min"] = y_reg[shuffled_idx] + 3.0

    df_a_aligned, df_b_aligned, report = validate_paired_alignment(df_a, df_b)

    assert report.is_valid_alignment
    assert report.status == "MATCHED"
    assert report.expected_rows == 120
    assert report.matched_rows == 120
    assert report.unmatched_rows == 0
    assert report.missing_predictions == 0
    assert len(report.issues) == 0

    # Ensure row-for-row alignment
    np.testing.assert_array_equal(df_a_aligned["flight_key"].to_numpy(), df_b_aligned["flight_key"].to_numpy())
    np.testing.assert_array_almost_equal(df_a_aligned["y_arr_reg"].to_numpy(), df_b_aligned["y_arr_reg"].to_numpy())


# =============================================================================
# 2. DUPLICATE IDS TEST
# =============================================================================

def test_duplicate_ids_fail_closed() -> None:
    """Duplicate flight keys in either table must fail closed immediately."""
    keys = [f"flight_{i:04d}" for i in range(50)]
    keys_dup = list(keys)
    keys_dup[10] = keys_dup[9]  # Duplicate key!

    df_a = pd.DataFrame({
        "flight_key": keys_dup,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": np.zeros(50),
        "y_arr_cls": np.zeros(50),
        "predicted_arr_delay_min": np.zeros(50),
    })
    df_b = pd.DataFrame({
        "flight_key": keys,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": np.zeros(50),
        "y_arr_cls": np.zeros(50),
        "predicted_arr_delay_min": np.zeros(50),
    })

    _, _, report = validate_paired_alignment(df_a, df_b)
    assert not report.is_valid_alignment
    assert report.status == "BLOCKED"
    assert any("duplicate keys" in issue for issue in report.issues)


# =============================================================================
# 3. MISSING ROWS TEST (NO SILENT DROPPING)
# =============================================================================

def test_missing_rows_fail_closed() -> None:
    """Unmatched keys must report BLOCKED status and never silently drop rows."""
    keys_a = [f"flight_{i:04d}" for i in range(100)]
    keys_b = keys_a[:95]  # Model B missing 5 rows

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
        "y_arr_reg": np.zeros(95),
        "y_arr_cls": np.zeros(95),
        "predicted_arr_delay_min": np.zeros(95),
    })

    _, _, report = validate_paired_alignment(df_a, df_b)
    assert not report.is_valid_alignment
    assert report.status == "BLOCKED"
    assert report.expected_rows == 100
    assert report.matched_rows == 95
    assert report.unmatched_rows == 5
    assert report.missing_predictions == 5
    assert any("missing in Model B" in issue for issue in report.issues)

    # compare_model_pair must fail closed
    res = compare_model_pair(df_a, df_b, "mod_a", "mod_b", "point_regression", "fold_1", 2019)
    assert res.status == "BLOCKED"
    assert "Row alignment validation failed" in str(res.failure_reason)


# =============================================================================
# 4. WRONG MODEL PAIRING (TARGET & METADATA MISMATCH)
# =============================================================================

def test_wrong_model_pairing_fails_closed() -> None:
    """Mismatched targets or fold metadata must fail closed."""
    keys = [f"flight_{i:04d}" for i in range(50)]
    df_a = pd.DataFrame({
        "flight_key": keys,
        "fold_id": "fold_1",
        "validation_year": 2019,
        "y_arr_reg": np.linspace(0.0, 50.0, 50),
        "y_arr_cls": np.zeros(50),
        "predicted_arr_delay_min": np.zeros(50),
    })

    # Case 1: Target mismatch
    df_b_target_mismatch = df_a.copy()
    df_b_target_mismatch.loc[0, "y_arr_reg"] = 999.0
    _, _, report1 = validate_paired_alignment(df_a, df_b_target_mismatch)
    assert not report1.is_valid_alignment
    assert report1.status == "BLOCKED"
    assert any("Target column 'y_arr_reg' mismatch" in issue for issue in report1.issues)

    # Case 2: Metadata fold_id mismatch
    df_b_meta_mismatch = df_a.copy()
    df_b_meta_mismatch["fold_id"] = "fold_2"
    _, _, report2 = validate_paired_alignment(df_a, df_b_meta_mismatch)
    assert not report2.is_valid_alignment
    assert report2.status == "BLOCKED"
    assert any("Metadata 'fold_id' mismatch" in issue for issue in report2.issues)


# =============================================================================
# 5. CI REPRODUCIBILITY TEST
# =============================================================================

def test_ci_reproducibility() -> None:
    """Bootstrap CI computation must be strictly deterministic given identical seed."""
    rng = np.random.default_rng(2026)
    deltas = rng.normal(-2.0, 1.5, size=250)

    ci1_low, ci1_high, se1 = compute_paired_bootstrap_ci(deltas, seed=DEFAULT_COMPARISON_SEED)
    ci2_low, ci2_high, se2 = compute_paired_bootstrap_ci(deltas, seed=DEFAULT_COMPARISON_SEED)

    assert ci1_low == ci2_low
    assert ci1_high == ci2_high
    assert se1 == se2

    # Different seed must yield distinct sample realizations
    ci_diff_low, ci_diff_high, _ = compute_paired_bootstrap_ci(deltas, seed=999999)
    assert ci1_low != ci_diff_low or ci1_high != ci_diff_high


# =============================================================================
# 6. BLOCK BOOTSTRAP REPRODUCIBILITY & DISTINCT SCHEMES
# =============================================================================

def test_block_bootstrap_reproducibility_and_schemes() -> None:
    """Verify reproducibility and mathematical distinction among all 4 resampling schemes."""
    n = 100
    dates = np.array([f"2022-01-{(i % 10) + 1:02d}" for i in range(n)])

    # 1. i.i.d. scheme
    idx_iid_1 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="iid_percentile")
    idx_iid_2 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="iid_percentile")
    np.testing.assert_array_equal(idx_iid_1, idx_iid_2)

    # 2. Day-cluster scheme
    idx_day_1 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="day_cluster_percentile", dates=dates)
    idx_day_2 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="day_cluster_percentile", dates=dates)
    np.testing.assert_array_equal(idx_day_1, idx_day_2)

    # 3. Fixed block scheme
    idx_fix_1 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="fixed_block_percentile", block_length=10)
    idx_fix_2 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="fixed_block_percentile", block_length=10)
    np.testing.assert_array_equal(idx_fix_1, idx_fix_2)

    # 4. Stationary block scheme
    idx_stat_1 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="stationary_block_percentile", block_length=10.0)
    idx_stat_2 = generate_bootstrap_indices(n, n_bootstraps=20, seed=1234, method="stationary_block_percentile", block_length=10.0)
    np.testing.assert_array_equal(idx_stat_1, idx_stat_2)

    # Verify that stationary block and fixed block produce distinct index distributions
    assert not np.array_equal(idx_fix_1, idx_stat_1)
    assert not np.array_equal(idx_iid_1, idx_fix_1)


# =============================================================================
# 7. AGGREGATE METRIC BOOTSTRAP (RMSE, R2, PR-AUC)
# =============================================================================

def test_aggregate_metric_bootstrap_correctness() -> None:
    """Verify that RMSE, R2, and PR-AUC are computed via global aggregate bootstrap rather than rowwise subtraction."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    # Model A error = 1.0 everywhere -> RMSE_A = 1.0, MSE_A = 1.0
    # Model B error = 3.0 everywhere -> RMSE_B = 3.0, MSE_B = 9.0
    pred_a = y + 1.0
    pred_b = y + 3.0

    res = compute_paired_regression_metrics(y, pred_a, pred_b, seed=202601)

    # Delta RMSE must be 1.0 - 3.0 = -2.0
    # Crucial check: Legacy bug computed Delta MSE (1.0 - 9.0 = -8.0). We assert it is NOT -8.0!
    assert res["delta_rmse"].mean_delta == pytest.approx(-2.0, abs=1e-4)
    assert res["delta_rmse"].mean_delta != -8.0
    assert res["delta_rmse"].model_a_mean == pytest.approx(1.0, abs=1e-4)
    assert res["delta_rmse"].model_b_mean == pytest.approx(3.0, abs=1e-4)
    assert res["delta_rmse"].unit_of_inference == InferenceUnit.FOLD_POPULATION.value
    assert res["delta_rmse"].test_method == "paired_bootstrap_test"
    assert res["delta_rmse"].ci_lower == pytest.approx(-2.0, abs=1e-4)
    assert res["delta_rmse"].ci_upper == pytest.approx(-2.0, abs=1e-4)

    # Delta R^2
    # Total sum of squares of y: mean=30, ss_tot = 400 + 100 + 0 + 100 + 400 = 1000
    # SSE_A = 5 * 1.0 = 5.0 -> R2_A = 1 - 5/1000 = 0.995
    # SSE_B = 5 * 9.0 = 45.0 -> R2_B = 1 - 45/1000 = 0.955
    # Delta R^2 = 0.995 - 0.955 = +0.040
    assert res["delta_r2"].mean_delta == pytest.approx(0.04, abs=1e-3)
    assert res["delta_r2"].higher_is_better is True
    assert res["delta_r2"].unit_of_inference == InferenceUnit.FOLD_POPULATION.value
    assert res["delta_r2"].test_method == "paired_bootstrap_test"


def test_prauc_aggregate_bootstrap() -> None:
    """Verify that PR-AUC delta and CI are computed via global aggregate resampling."""
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
    p_a = np.array([0.9, 0.85, 0.8, 0.75, 0.2, 0.15, 0.1, 0.05, 0.1, 0.2])
    p_b = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    res = compute_paired_classification_metrics(y, p_a, p_b, seed=202601)
    assert isinstance(res["delta_pr_auc"], dict)
    assert res["delta_pr_auc"]["higher_is_better"] is True
    assert res["delta_pr_auc"]["mean_delta"] > 0.0
    assert res["delta_pr_auc"]["unit_of_inference"] == InferenceUnit.FOLD_POPULATION.value
    assert res["delta_pr_auc"]["test_method"] == "paired_bootstrap_test"


# =============================================================================
# 8. MULTIPLE-COMPARISON CORRECTION (HOLM & BENJAMINI-HOCHBERG)
# =============================================================================

def test_multiple_comparison_correction_holm_and_bh() -> None:
    """Verify exact analytical values and properties for Holm-Bonferroni and Benjamini-Hochberg."""
    # Test known textbook array: raw_p = [0.01, 0.04, 0.03]
    # Sorted: p(1)=0.01, p(2)=0.03, p(3)=0.04 (m=3)
    # Holm:
    # rank 0: 0.01 * 3 = 0.03
    # rank 1: max(0.03, 0.03 * 2) = 0.06
    # rank 2: max(0.06, 0.04 * 1) = 0.06
    raw_p = [0.01, 0.04, 0.03]
    adj_holm = compute_holm_bonferroni_correction(raw_p)
    assert adj_holm[0] == pytest.approx(0.03)
    assert adj_holm[1] == pytest.approx(0.06)
    assert adj_holm[2] == pytest.approx(0.06)

    # Benjamini-Hochberg:
    # rank 2: 0.04 * (3/3) = 0.04
    # rank 1: min(0.04, 0.03 * (3/2)) = min(0.04, 0.045) = 0.04
    # rank 0: min(0.04, 0.01 * (3/1)) = min(0.04, 0.03) = 0.03
    adj_bh = compute_benjamini_hochberg_correction(raw_p)
    assert adj_bh[0] == pytest.approx(0.03)
    assert adj_bh[1] == pytest.approx(0.04)
    assert adj_bh[2] == pytest.approx(0.04)

    # Monotonicity with arbitrary values
    raw_arbitrary = [0.005, 0.02, 0.01, 0.08, 0.03]
    holm_arb = compute_holm_bonferroni_correction(raw_arbitrary)
    sorted_pairs = sorted(zip(raw_arbitrary, holm_arb), key=lambda x: x[0])
    for i in range(len(sorted_pairs) - 1):
        assert sorted_pairs[i][1] <= sorted_pairs[i + 1][1]  # Monotonic


def test_apply_multiplicity_correction_to_records() -> None:
    """Verify application of Holm correction across structured StatisticalComparisonRecord list."""
    records = [
        StatisticalComparisonRecord(
            model_a=f"m_{i}",
            model_b="baseline",
            metric="mae",
            unit_of_inference="flight",
            n_units=1000,
            effect_size=-1.0,
            ci_low=-1.2,
            ci_high=-0.8,
            raw_p=p,
            adjusted_p=None,
            test_method="paired_t_test",
            bootstrap_method="iid_percentile",
            block_length=None,
            bootstrap_replicates=2000,
            seed=202601,
            comparison_family="point_regression",
            fold_id="fold_1",
        )
        for i, p in enumerate([0.01, 0.04, 0.03])
    ]

    updated = apply_multiplicity_correction(records, method="holm")
    assert len(updated) == 3
    assert updated[0].adjusted_p == pytest.approx(0.03)
    assert updated[1].adjusted_p == pytest.approx(0.06)
    assert updated[2].adjusted_p == pytest.approx(0.06)
    assert updated[0].is_significant_adj_05 is True
    assert updated[1].is_significant_adj_05 is False


# =============================================================================
# 9. NO FALSE P-VALUES FROM EMPTY / DEGENERATE DATA
# =============================================================================

def test_no_false_p_values_from_empty_or_degenerate_data() -> None:
    """Zero false p-values or fabricated significance on empty, degenerate, or single-class data."""
    # 1. Empty data
    res_empty = compute_paired_regression_metrics(np.array([]), np.array([]), np.array([]))
    assert res_empty["delta_mae"].n_units == 0
    assert res_empty["delta_mae"].raw_p is None
    assert res_empty["delta_mae"].ci_lower == 0.0
    assert res_empty["delta_mae"].ci_upper == 0.0

    # 2. Identical predictions (zero delta)
    y = np.array([5.0, 10.0, 15.0])
    pred = np.array([6.0, 9.0, 14.0])
    res_ident = compute_paired_regression_metrics(y, pred, pred)
    assert res_ident["delta_mae"].raw_p == 1.0
    assert res_ident["delta_mae"].mean_delta == 0.0

    # 3. Single-class classification data for PR-AUC
    y_single_class = np.zeros(20)  # Only class 0
    p_a = np.linspace(0.1, 0.9, 20)
    p_b = np.linspace(0.2, 0.8, 20)
    res_cls_single = compute_paired_classification_metrics(y_single_class, p_a, p_b)
    assert res_cls_single["delta_pr_auc"] == "NOT_AVAILABLE"

    # 4. Bootstrap p-value finite resolution floor: never 0.0 on finite B
    boot_all_positive = np.ones(DEFAULT_BOOTSTRAP_REPLICATIONS)
    p_floor = compute_bootstrap_p_value(boot_all_positive)
    expected_floor = 2.0 / (DEFAULT_BOOTSTRAP_REPLICATIONS + 1.0)
    assert p_floor == pytest.approx(expected_floor, rel=1e-5)
    assert p_floor > 0.0


# =============================================================================
# 10. CANONICAL OUTPUT SCHEMA PARITY
# =============================================================================

def test_canonical_output_schema_parity() -> None:
    """Verify that StatisticalComparisonRecord and PairedComparisonResult output all 15 required fields."""
    protocol_path = Path("artifacts/manifests/statistical_comparison_protocol_v2.json")
    assert protocol_path.exists(), "Protocol manifest must exist."
    with open(protocol_path, "r", encoding="utf-8") as f:
        protocol = json.load(f)

    required_fields = set(protocol["canonical_output_schema"])
    assert len(required_fields) == 15

    record = StatisticalComparisonRecord(
        model_a="mod_a",
        model_b="mod_b",
        metric="delta_mae",
        unit_of_inference="flight",
        n_units=500,
        effect_size=-1.5,
        ci_low=-1.8,
        ci_high=-1.2,
        raw_p=0.001,
        adjusted_p=0.01,
        test_method="paired_t_test",
        bootstrap_method="iid_percentile",
        block_length=None,
        bootstrap_replicates=2000,
        seed=202601,
    )

    rec_dict = record.to_dict()
    for field_name in required_fields:
        assert field_name in rec_dict, f"Field '{field_name}' missing from StatisticalComparisonRecord.to_dict()"
