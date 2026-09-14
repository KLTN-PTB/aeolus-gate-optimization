from __future__ import annotations

import warnings
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression, Ridge

from src.data.load_aeolus import load_base_config
from src.features.tabular_features import prepare_arrival_features
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import ExperimentSpec, FoldData, RollingFold, Week4ContractViolation
from src.models.linear_models import (
    LINEAR_BASELINE_VERSION,
    build_linear_estimators,
    load_linear_baseline_config,
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
            "flight_key": [f"linear-{year}-a", f"linear-{year}-b"],
            "source_year": [year, year],
            "source_row_number": [1, 2],
        }
    )


def _spec() -> ExperimentSpec:
    base = load_base_config()
    return ExperimentSpec(
        method_id="linear",
        model_version=LINEAR_BASELINE_VERSION,
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
    X.loc[X.index[0], "OP_CARRIER"] = "__UNKNOWN_FOR_LINEAR_TEST__"
    X.loc[X.index[1], "ORIGIN"] = np.nan
    validation = replace(validation, X=X)
    return fold, FoldData(train=train, validation=validation)


def test_locked_linear_config_and_factory_use_training_only_class_weights() -> None:
    config = load_linear_baseline_config()
    spec = _spec()
    fold, data = _fold_data()
    weights = derive_balanced_class_weights(data.train.y_arr_cls)
    bundle = build_linear_estimators(
        FoldContext(fold=fold, class_weights=weights, spec=spec), config=config
    )

    assert isinstance(bundle.classifier, LogisticRegression)
    assert bundle.classifier.get_params() == {
        **bundle.classifier.get_params(),
        "solver": "saga",
        "C": 1.0,
        "max_iter": 300,
        "tol": 0.001,
        "class_weight": weights,
        "random_state": spec.seed,
    }
    assert isinstance(bundle.regressor, Ridge)
    assert bundle.regressor.get_params()["alpha"] == 1.0
    assert bundle.regressor.get_params()["solver"] == "lsqr"
    assert bundle.regressor.get_params()["tol"] == 0.001


def test_linear_fold_smoke_supports_unknown_categories_missing_values_and_signed_targets() -> None:
    config = load_linear_baseline_config()
    spec = _spec()
    fold, data = _fold_data()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        result, oof = run_fold_experiment(
            spec,
            fold=fold,
            data=data,
            estimator_factory=lambda context: build_linear_estimators(context, config=config),
        )

    validate_oof_frame(oof)
    assert tuple(oof.columns) == OOF_COLUMNS
    assert np.isfinite(oof["p_arr_delay_15"]).all()
    assert oof["p_arr_delay_15"].between(0, 1).all()
    assert np.isfinite(oof["predicted_arr_delay_min"]).all()
    assert bool((data.train.y_arr_reg < 0).any())
    assert result.preprocessor_state_unchanged_after_validation is True
    assert result.classification.threshold == 0.5


def test_linear_factory_rejects_an_unlocked_seed() -> None:
    config = load_linear_baseline_config()
    fold, data = _fold_data()
    with pytest.raises(Week4ContractViolation, match="configured project seed"):
        build_linear_estimators(
            FoldContext(
                fold=fold,
                class_weights=derive_balanced_class_weights(data.train.y_arr_cls),
                spec=replace(_spec(), seed=1),
            ),
            config=config,
        )
