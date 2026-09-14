from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from src.data.load_aeolus import load_base_config
from src.features.tabular_features import prepare_arrival_features
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import ExperimentSpec, FoldData, RollingFold, Week4ContractViolation
from src.models.random_forest_models import (
    RANDOM_FOREST_BASELINE_VERSION,
    build_random_forest_estimators,
    load_random_forest_baseline_config,
)
from src.models.rolling import FoldContext, derive_balanced_class_weights, run_fold_experiment


def _raw_year(year: int) -> pd.DataFrame:
    dates = pd.to_datetime([f"{year}-01-02", f"{year}-01-03"])
    return pd.DataFrame(
        {
            "FL_DATE": [f"{year}-01-02 00:00:00", f"{year}-01-03 00:00:00"],
            "OP_CARRIER": ["AA", "DL"],
            "OP_CARRIER_FL_NUM": [101.0, 202.0],
            "ORIGIN": ["BOS", "JFK"],
            "DEST": ["ATL", "ATL"],
            "CRS_DEP_TIME": [f"{year}-01-02 09:00:00", f"{year}-01-03 23:30:00"],
            "CRS_ELAPSED_TIME": [120.0, 130.0],
            "MONTH": dates.month.tolist(),
            "DAY_OF_MONTH": dates.day.tolist(),
            "DAY_OF_WEEK": (dates.dayofweek + 1).tolist(),
            "ARR_DELAY": [-10.0, 20.0],
            "flight_key": [f"rf-{year}-a", f"rf-{year}-b"],
            "source_year": [year, year],
            "source_row_number": [1, 2],
        }
    )


def _spec() -> ExperimentSpec:
    base = load_base_config()
    return ExperimentSpec(
        method_id="random_forest",
        model_version=RANDOM_FOREST_BASELINE_VERSION,
        config_version=base["project"]["version"],
        seed=base["reproducibility"]["project_seed"],
    )


def _fold_data() -> tuple[RollingFold, FoldData]:
    fold = RollingFold("fold_1", (2016, 2017, 2018), 2019)
    train = prepare_arrival_features(
        pd.concat([_raw_year(year) for year in fold.train_years], ignore_index=True)
    )
    validation = prepare_arrival_features(_raw_year(fold.validation_year))
    X = validation.X.copy(deep=True)
    X.loc[X.index[0], "OP_CARRIER"] = "__UNKNOWN_FOR_RF_TEST__"
    X.loc[X.index[1], "ORIGIN"] = np.nan
    validation = replace(validation, X=X)
    return fold, FoldData(train=train, validation=validation)


def _run_once() -> tuple[object, pd.DataFrame]:
    config = load_random_forest_baseline_config()
    fold, data = _fold_data()
    return run_fold_experiment(
        _spec(),
        fold=fold,
        data=data,
        estimator_factory=lambda context: build_random_forest_estimators(context, config=config),
    )


def test_locked_random_forest_config_uses_full_bootstrap_draws_and_training_weights() -> None:
    config = load_random_forest_baseline_config()
    spec = _spec()
    fold, data = _fold_data()
    weights = derive_balanced_class_weights(data.train.y_arr_cls)
    bundle = build_random_forest_estimators(
        FoldContext(fold=fold, class_weights=weights, spec=spec), config=config
    )

    assert isinstance(bundle.classifier, RandomForestClassifier)
    assert isinstance(bundle.regressor, RandomForestRegressor)
    for estimator in (bundle.classifier, bundle.regressor):
        params = estimator.get_params()
        assert params["n_estimators"] == 96
        assert params["max_depth"] == 14
        assert params["min_samples_split"] == 40
        assert params["min_samples_leaf"] == 20
        assert params["max_features"] == "sqrt"
        assert params["bootstrap"] is True
        assert params["max_samples"] is None
        assert params["n_jobs"] == 1
        assert params["random_state"] == spec.seed
    assert bundle.classifier.get_params()["class_weight"] == weights


def test_random_forest_fold_smoke_handles_tree_encoding_and_is_repeatable() -> None:
    result_a, oof_a = _run_once()
    result_b, oof_b = _run_once()

    validate_oof_frame(oof_a)
    assert tuple(oof_a.columns) == OOF_COLUMNS
    assert np.isfinite(oof_a["p_arr_delay_15"]).all()
    assert oof_a["p_arr_delay_15"].between(0, 1).all()
    assert np.isfinite(oof_a["predicted_arr_delay_min"]).all()
    assert np.array_equal(
        oof_a["p_arr_delay_15"].to_numpy(), oof_b["p_arr_delay_15"].to_numpy()
    )
    assert np.array_equal(
        oof_a["predicted_arr_delay_min"].to_numpy(), oof_b["predicted_arr_delay_min"].to_numpy()
    )
    assert getattr(result_a, "preprocessor_state_unchanged_after_validation") is True
    assert getattr(result_b, "classification").threshold == 0.5


def test_random_forest_factory_rejects_unlocked_seed() -> None:
    config = load_random_forest_baseline_config()
    fold, data = _fold_data()
    with pytest.raises(Week4ContractViolation, match="configured project seed"):
        build_random_forest_estimators(
            FoldContext(
                fold=fold,
                class_weights=derive_balanced_class_weights(data.train.y_arr_cls),
                spec=replace(_spec(), seed=1),
            ),
            config=config,
        )
