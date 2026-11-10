from __future__ import annotations

import pandas as pd
from scripts.run_phase_a_benchmark_lightgbm import (
    LIGHTGBM_CATEGORICAL_FEATURES,
    build_lightgbm_regressor,
    prepare_native_categorical_frames,
)


def test_lightgbm_builder_uses_locked_default_l1_params():
    model = build_lightgbm_regressor(seed=42)
    params = model.get_params()

    assert params["objective"] == "regression_l1"
    assert params["metric"] == "mae"
    assert params["num_leaves"] == 31
    assert params["learning_rate"] == 0.05
    assert params["n_estimators"] == 500
    assert params["min_data_in_leaf"] == 20
    assert params["random_state"] == 42
    assert params["n_jobs"] == 1


def test_native_categorical_frames_share_train_categories_and_preserve_numeric_features():
    X_train = pd.DataFrame(
        {
            "OP_CARRIER": ["AA", "DL"],
            "ORIGIN": ["ATL", "JFK"],
            "OP_CARRIER_FL_NUM": [1, 2],
            "scheduled_departure_hour": [8, 9],
        }
    )
    X_val = pd.DataFrame(
        {
            "OP_CARRIER": ["DL", "UA"],
            "ORIGIN": ["JFK", "ATL"],
            "OP_CARRIER_FL_NUM": [2, 3],
            "scheduled_departure_hour": [10, 11],
        }
    )

    train_out, val_out = prepare_native_categorical_frames(X_train, X_val)

    for column in LIGHTGBM_CATEGORICAL_FEATURES:
        assert isinstance(train_out[column].dtype, pd.CategoricalDtype)
        assert isinstance(val_out[column].dtype, pd.CategoricalDtype)
        assert list(train_out[column].cat.categories) == list(val_out[column].cat.categories)
    assert train_out["scheduled_departure_hour"].dtype == X_train["scheduled_departure_hour"].dtype
    assert pd.isna(val_out.loc[1, "OP_CARRIER"])
