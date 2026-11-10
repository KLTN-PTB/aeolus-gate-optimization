from __future__ import annotations

import pandas as pd
import pytest

from src.features.refactored_features import compute_carrier_arrhour_median


def _train_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "AA", "AA", "DL"],
            "scheduled_arrival_hour": [8, 8, 10, 8],
            "y_arr_reg": [10.0, 20.0, 40.0, 0.0],
            "source_year": [2016, 2017, 2018, 2018],
        }
    )


def test_target_encoding_uses_train_only_with_three_level_fallback() -> None:
    apply_df = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "AA", "UA"],
            "scheduled_arrival_hour": [8, 12, 8],
            "y_arr_reg": [999.0, -999.0, 123.0],
        },
        index=[11, 12, 13],
    )

    values, counts = compute_carrier_arrhour_median(
        _train_frame(), apply_df, smoothing=False
    )

    assert values.index.tolist() == [11, 12, 13]
    assert values.tolist() == [15.0, 20.0, 15.0]
    assert counts.tolist() == [2, 0, 0]
    assert values.notna().all()
    assert counts.notna().all()


def test_target_encoding_smoothing_uses_k30_and_ignores_validation_targets() -> None:
    apply_df = pd.DataFrame(
        {
            "OP_CARRIER": ["AA"],
            "scheduled_arrival_hour": [8],
            "y_arr_reg": [999999.0],
        },
        index=[7],
    )

    values, counts = compute_carrier_arrhour_median(
        _train_frame(), apply_df, k=30, smoothing=True
    )

    # cell median=15, carrier median=20, n_cell=2: (2*15 + 30*20)/(2+30)
    assert values.iloc[0] == pytest.approx((2 * 15.0 + 30 * 20.0) / 32.0)
    assert counts.iloc[0] == 2


def test_target_encoding_is_invariant_to_validation_row_permutation_and_values() -> None:
    train = _train_frame()
    validation = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "DL", "UA"],
            "scheduled_arrival_hour": [8, 8, 8],
            "y_arr_reg": [1.0, 2.0, 3.0],
        },
        index=[20, 21, 22],
    )
    baseline_values, baseline_counts = compute_carrier_arrhour_median(
        train, validation, smoothing=False
    )

    mutated = validation.sample(frac=1.0, random_state=99).copy()
    mutated["y_arr_reg"] = [-1000.0, 2000.0, 3000.0]
    mutated_values, mutated_counts = compute_carrier_arrhour_median(
        train, mutated, smoothing=False
    )

    pd.testing.assert_series_equal(
        baseline_values.sort_index(), mutated_values.sort_index()
    )
    pd.testing.assert_series_equal(
        baseline_counts.sort_index(), mutated_counts.sort_index()
    )
