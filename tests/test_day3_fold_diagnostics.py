from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.run_day3_fold_diagnostics import (
    classify_temporal_case,
    population_stability_index,
    summarize_carrier_hour_stability,
)


def test_population_stability_index_is_zero_for_identical_categorical_mix():
    reference = pd.Series(["AA", "AA", "DL", "UA"])
    current = pd.Series(["AA", "AA", "DL", "UA"])

    assert population_stability_index(reference, current) == 0.0


def test_carrier_hour_stability_counts_sparse_cells_and_scores_their_validation_rows():
    train = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "AA", "DL", "DL", "UA"],
            "scheduled_arrival_hour": [8, 8, 9, 9, 10],
        }
    )
    y_train = pd.Series([1.0, 3.0, 2.0, 4.0, 10.0])
    validation = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "DL", "UA", "WN"],
            "scheduled_arrival_hour": [8, 9, 10, 11],
        }
    )
    y_validation = pd.Series([2.0, 3.0, 12.0, 20.0])

    result = summarize_carrier_hour_stability(train, y_train, validation, y_validation)

    assert result["train_cell_count"] == 3
    assert result["sparse_train_cell_count"] == 3
    assert result["validation_unseen_row_count"] == 1
    assert result["validation_sparse_row_count"] == 3
    assert np.isclose(result["validation_sparse_mae"], 2.0 / 3.0)
    assert np.isclose(result["validation_unseen_mae"], 17.0)


def test_temporal_case_is_case_b_when_point_gate_passes_but_trend_warns():
    result = classify_temporal_case(
        macro_skill=0.4091,
        fold4_skill=-0.2519,
        skill_2021=0.1698,
        skill_2022=-0.2519,
        max_psi=0.10,
    )

    assert result["case"] == "B"
    assert result["macro_positive"] is True
    assert result["fold4_above_minus_1pp"] is True
    assert result["trend_warning"] is True
