from __future__ import annotations

import pandas as pd

from scripts.run_day3_carrier_ablation import (
    build_carrier_ablation_preprocessor,
    drop_model_features,
)


def test_drop_model_features_removes_only_carrier_from_model_matrix():
    X = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "DL"],
            "ORIGIN": ["ATL", "JFK"],
            "scheduled_arrival_hour": [8, 9],
        }
    )

    result = drop_model_features(X, ("OP_CARRIER",))

    assert "OP_CARRIER" not in result.columns
    assert list(result.columns) == ["ORIGIN", "scheduled_arrival_hour"]


def test_carrier_ablation_preprocessor_keeps_origin_and_excludes_carrier():
    preprocessor = build_carrier_ablation_preprocessor()

    configured_columns = [
        column
        for _, _, columns in preprocessor.transformers
        for column in columns
    ]

    assert "OP_CARRIER" not in configured_columns
    assert "ORIGIN" in configured_columns
    assert "OP_CARRIER_FL_NUM" in configured_columns

