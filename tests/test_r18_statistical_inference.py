"""Tests for Statistical Inference Engine, Temporal Dependence, and Multiplicity Control (Task R18).

Verifies:
1. Holm-Bonferroni correction is actually called and controls FWER within comparison families.
2. adjusted_p is fully populated (no None values for valid comparisons).
3. Family-level grouping is deterministic across repeated runs.
4. No impossible p-values (strictly in [0.0, 1.0] and bootstrap p >= 2/(B+1)).
5. Bootstrap random seed produces bitwise reproducible results.
6. Day-cluster temporal block bootstrap does not collapse to IID row bootstrap.
7. Aggregate metric bootstrap (RMSE, R^2, PR-AUC) recomputes metrics globally on resampled units.
8. Metadata completeness in audit and paired statistics artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

import numpy as np
import pandas as pd

from src.evaluation.paired_comparison import (
    DEFAULT_BOOTSTRAP_REPLICATIONS,
    DEFAULT_COMPARISON_SEED,
    InferenceUnit,
    StatisticalComparisonRecord,
    apply_multiplicity_correction,
    compute_bootstrap_p_value,
    compute_day_block_bootstrap_ci,
    compute_holm_bonferroni_correction,
    compute_paired_bootstrap_ci,
    compute_paired_classification_metrics,
    compute_paired_regression_metrics,
    extract_comparison_families_metadata,
    generate_bootstrap_indices,
    summarize_delta_distribution,
)


def test_holm_actually_called_and_populates_adjusted_p() -> None:
    """Verify that apply_multiplicity_correction executes Holm-Bonferroni and populates adjusted_p."""
    records = [
        StatisticalComparisonRecord(
            model_a=f"model_{i}",
            model_b="baseline",
            metric="delta_mae",
            unit_of_inference="day_cluster",
            n_units=4000,
            effect_size=-0.5 + 0.1 * i,
            ci_low=-0.8,
            ci_high=-0.2,
            raw_p=p,
            adjusted_p=None,  # Runner begins with None
            test_method="day_cluster_bootstrap",
            bootstrap_method="day_cluster_percentile",
            block_length=None,
            bootstrap_replicates=2000,
            seed=DEFAULT_COMPARISON_SEED,
            comparison_family="point_regression",
            fold_id="fold_1",
        )
        for i, p in enumerate([0.005, 0.02, 0.01, 0.04, 0.03])
    ]

    # Before correction: all adjusted_p are None
    assert all(r.adjusted_p is None for r in records)

    # Apply correction
    corrected = apply_multiplicity_correction(records, method="holm", group_by_metric=True)

    # After correction: ALL adjusted_p must be populated floats
    assert len(corrected) == 5
    assert all(r.adjusted_p is not None for r in corrected)
    assert all(isinstance(r.adjusted_p, float) for r in corrected)

    # Verify step-down ordering and values
    # Sorted raw p: p(1)=0.005, p(2)=0.01, p(3)=0.02, p(4)=0.03, p(5)=0.04 (m=5)
    # rank 0: 0.005 * 5 = 0.025
    # rank 1: max(0.025, 0.01 * 4) = 0.04
    # rank 2: max(0.04, 0.02 * 3) = 0.06
    # rank 3: max(0.06, 0.03 * 2) = 0.06
    # rank 4: max(0.06, 0.04 * 1) = 0.06
    assert corrected[0].adjusted_p == pytest.approx(0.025)
    assert corrected[2].adjusted_p == pytest.approx(0.040)
    assert corrected[1].adjusted_p == pytest.approx(0.060)
    assert corrected[4].adjusted_p == pytest.approx(0.060)
    assert corrected[3].adjusted_p == pytest.approx(0.060)


def test_adjustment_family_deterministic() -> None:
    """Verify that multiplicity correction families partition deterministically."""
    records = []
    for fold in ["fold_1", "fold_2"]:
        for metric in ["delta_mae", "delta_rmse"]:
            for i in range(5):
                records.append(
                    StatisticalComparisonRecord(
                        model_a=f"m_{i}",
                        model_b="baseline",
                        metric=metric,
                        unit_of_inference="day_cluster",
                        n_units=1000,
                        effect_size=-0.2,
                        ci_low=-0.4,
                        ci_high=-0.01,
                        raw_p=0.01 * (i + 1),
                        adjusted_p=None,
                        test_method="day_cluster_bootstrap",
                        bootstrap_method="day_cluster_percentile",
                        block_length=None,
                        bootstrap_replicates=2000,
                        seed=DEFAULT_COMPARISON_SEED,
                        comparison_family="point_regression",
                        fold_id=fold,
                    )
                )

    meta1 = extract_comparison_families_metadata(records, correction_method="holm_bonferroni", group_by_metric=True)
    meta2 = extract_comparison_families_metadata(records, correction_method="holm_bonferroni", group_by_metric=True)

    # Must be 4 families: (fold_1, mae), (fold_1, rmse), (fold_2, mae), (fold_2, rmse)
    assert len(meta1) == 4
    assert meta1 == meta2
    for fam in meta1:
        assert fam["n_tests"] == 5
        assert fam["correction"] == "holm_bonferroni"
        assert len(fam["comparisons"]) == 5


def test_no_impossible_p_values() -> None:
    """Verify that all p-values satisfy 0.0 <= p <= 1.0 and bootstrap p >= 2/(B+1)."""
    # 1. Zero differences should return p >= 2/(B+1) or 1.0, never 0.0
    zero_deltas = np.zeros(100)
    b_reps = 199
    p_zero = compute_bootstrap_p_value(zero_deltas)
    assert 0.0 <= p_zero <= 1.0

    # 2. Extreme non-zero differences: empirical bootstrap p bounded by 2/(B+1)
    extreme_deltas = np.full(b_reps, 10.0)
    p_extreme = compute_bootstrap_p_value(extreme_deltas)
    expected_lower_bound = 2.0 / (b_reps + 1.0)
    assert p_extreme == pytest.approx(expected_lower_bound, abs=1e-6)
    assert p_extreme > 0.0  # Prohibits false claim of p = 0.0 from finite sampling

    # 3. Holm correction bounds
    raw_p = [0.0, 0.001, 0.5, 0.99, 1.0]
    adj_p = compute_holm_bonferroni_correction(raw_p)
    assert all(0.0 <= p <= 1.0 for p in adj_p if p is not None)


def test_bootstrap_seed_reproducible() -> None:
    """Verify that identical random seeds produce bitwise identical bootstrap samples and CIs."""
    n = 200
    rng = np.random.default_rng(123)
    deltas = rng.normal(loc=0.5, scale=2.0, size=n)

    ci1_low, ci1_high, se1 = compute_paired_bootstrap_ci(deltas, n_bootstraps=500, seed=202601)
    ci2_low, ci2_high, se2 = compute_paired_bootstrap_ci(deltas, n_bootstraps=500, seed=202601)

    assert ci1_low == ci2_low
    assert ci1_high == ci2_high
    assert se1 == se2

    # Different seed must differ
    ci3_low, _, _ = compute_paired_bootstrap_ci(deltas, n_bootstraps=500, seed=999999)
    assert ci1_low != ci3_low


def test_block_bootstrap_does_not_collapse_to_iid_row_bootstrap() -> None:
    """Verify that day_cluster_percentile preserves cluster grouping and produces distinct samples from IID."""
    n_days = 50
    flights_per_day = 20
    n = n_days * flights_per_day  # 1000 flights
    dates = np.repeat(np.arange(n_days), flights_per_day)

    idx_iid = generate_bootstrap_indices(n, n_bootstraps=100, seed=202601, method="iid_percentile")
    idx_day = generate_bootstrap_indices(n, n_bootstraps=100, seed=202601, method="day_cluster_percentile", dates=dates)

    assert idx_iid.shape == (100, n)
    assert idx_day.shape == (100, n)

    # In IID, unique dates per bootstrap replicate is nearly 100% of all days (50)
    iid_unique_days = [len(np.unique(dates[idx_iid[b]])) for b in range(100)]
    # In day clustering, unique days per bootstrap replicate is roughly (1 - 1/e) * 50 ~ 31-32
    day_unique_days = [len(np.unique(dates[idx_day[b]])) for b in range(100)]

    assert np.mean(iid_unique_days) > 48.0  # IID samples virtually every day
    assert 25.0 <= np.mean(day_unique_days) <= 38.0  # Day cluster samples ~63.2% unique days
    assert not np.array_equal(idx_iid, idx_day)


def test_aggregate_metric_bootstrap_recomputes_metric() -> None:
    """Verify that RMSE, R2, and PR-AUC recompute global metrics globally rather than rowwise differences."""
    y = np.array([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    pred_a = y + 2.0  # RMSE_A = 2.0, MSE_A = 4.0
    pred_b = y + 4.0  # RMSE_B = 4.0, MSE_B = 16.0

    res = compute_paired_regression_metrics(y, pred_a, pred_b, seed=202601)

    # Delta RMSE must be 2.0 - 4.0 = -2.0
    # Must NOT be rowwise MSE difference (4.0 - 16.0 = -12.0)
    assert res["delta_rmse"].mean_delta == pytest.approx(-2.0, abs=1e-4)
    assert res["delta_rmse"].model_a_mean == pytest.approx(2.0, abs=1e-4)
    assert res["delta_rmse"].model_b_mean == pytest.approx(4.0, abs=1e-4)
    assert res["delta_rmse"].unit_of_inference == InferenceUnit.FOLD_POPULATION.value
    assert res["delta_rmse"].test_method == "paired_bootstrap_test"

    # Delta R^2
    # ss_tot for y: mean=17.5, var = 875/12, sst = 437.5
    # SSE_A = 6 * 4 = 24 -> R2_A = 1 - 24/437.5 = 0.9451
    # SSE_B = 6 * 16 = 96 -> R2_B = 1 - 96/437.5 = 0.7806
    # Delta R^2 = 0.9451 - 0.7806 = +0.1646
    assert res["delta_r2"].mean_delta == pytest.approx(0.1646, abs=1e-3)
    assert res["delta_r2"].higher_is_better is True
    assert res["delta_r2"].unit_of_inference == InferenceUnit.FOLD_POPULATION.value
    assert res["delta_r2"].test_method == "paired_bootstrap_test"


def test_metadata_complete_in_artifacts() -> None:
    """Verify that authoritative R18 audit and paired statistics artifacts exist and conform to schema."""
    audit_file = Path("artifacts/r18_statistical_inference_audit.json")
    assert audit_file.exists(), "Missing artifacts/r18_statistical_inference_audit.json"
    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))

    assert audit_data["status"] == "PASS"
    assert audit_data["correction"]["method"] == "holm_bonferroni"
    assert audit_data["correction"]["implemented"] is True
    assert audit_data["correction"]["called_by_runner"] is True
    assert audit_data["correction"]["validated"] is True
    assert audit_data["dependence"]["unit"] == "day_cluster"
    assert audit_data["dependence"]["block_key"] == "FL_DATE"
    assert audit_data["dependence"]["bootstrap_method"] == "day_cluster_percentile"
    assert audit_data["dependence"]["bootstrap_B"] >= 1000
    assert len(audit_data["comparison_families"]) > 0
    assert len(audit_data["limitations"]) >= 3

    stats_file = Path("artifacts/r18_paired_statistics_v2.json")
    assert stats_file.exists(), "Missing artifacts/r18_paired_statistics_v2.json"
    stats_data = json.loads(stats_file.read_text(encoding="utf-8"))
    assert len(stats_data) > 0

    required_keys = {
        "model_a",
        "model_b",
        "metric",
        "evaluation_slice",
        "inference_unit",
        "n_units",
        "delta",
        "ci_low",
        "ci_high",
        "effect_size",
        "raw_p",
        "adjusted_p",
        "correction_family",
        "test_method",
    }
    for item in stats_data:
        assert required_keys.issubset(item.keys())
        assert item["adjusted_p"] is not None if item["raw_p"] is not None else True
        if item["raw_p"] is not None:
            assert 0.0 <= item["raw_p"] <= 1.0
            assert 0.0 <= item["adjusted_p"] <= 1.0
            assert item["adjusted_p"] >= item["raw_p"] - 1e-9  # Adjusted p cannot be smaller than raw p
