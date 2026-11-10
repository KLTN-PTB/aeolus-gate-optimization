from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier, XGBRegressor

from src.data.load_aeolus import load_base_config
from src.features.tabular_features import prepare_arrival_features
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import FoldData, RollingFold, Week4ContractViolation, prepared_row_fingerprint
from src.models.week5_xgboost import (
    XGBOOST_BASELINE_VERSION,
    Week5XGBoostFoldContext,
    Week5XGBoostSpec,
    build_xgboost_estimators,
    load_xgboost_baseline_config,
    run_xgboost_fold_experiment,
)


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
            "flight_key": [f"xgb-{year}-a", f"xgb-{year}-b"],
            "source_year": [year, year],
            "source_row_number": [1, 2],
        }
    )


def _spec(*, fingerprints: dict[str, str] | None = None) -> Week5XGBoostSpec:
    base = load_base_config()
    return Week5XGBoostSpec(
        model_version=XGBOOST_BASELINE_VERSION,
        config_version=base["project"]["version"],
        seed=base["reproducibility"]["project_seed"],
        expected_validation_row_fingerprints=fingerprints,
    )


def _fold_data() -> tuple[RollingFold, FoldData]:
    fold = RollingFold("fold_1", (2016, 2017, 2018), 2019)
    train = prepare_arrival_features(
        pd.concat([_raw_year(year) for year in fold.train_years], ignore_index=True)
    )
    validation = prepare_arrival_features(_raw_year(fold.validation_year))
    return fold, FoldData(train=train, validation=validation)


def test_xgboost_factory_is_cpu_only_and_derives_scale_weight_from_train_balance() -> None:
    config = load_xgboost_baseline_config()
    fold, _ = _fold_data()
    bundle = build_xgboost_estimators(
        Week5XGBoostFoldContext(
            fold=fold,
            class_weights={0: 0.75, 1: 1.5},
            spec=_spec(),
        ),
        config=config,
    )

    assert isinstance(bundle.classifier, XGBClassifier)
    assert isinstance(bundle.regressor, XGBRegressor)
    classifier_params = bundle.classifier.get_params()
    regressor_params = bundle.regressor.get_params()
    assert classifier_params["device"] == "cpu"
    assert classifier_params["tree_method"] == "hist"
    assert classifier_params["n_jobs"] == 1
    assert classifier_params["objective"] == "binary:logistic"
    assert classifier_params["scale_pos_weight"] == pytest.approx(2.0)
    assert classifier_params["early_stopping_rounds"] is None
    assert regressor_params["device"] == "cpu"
    assert regressor_params["tree_method"] == "hist"
    assert regressor_params["n_jobs"] == 1
    assert regressor_params["objective"] == "reg:squarederror"
    assert regressor_params["early_stopping_rounds"] is None


def test_xgboost_fold_uses_probability_signed_target_and_exact_oof_contract() -> None:
    config = load_xgboost_baseline_config()
    fold, data = _fold_data()
    fingerprints = {fold.fold_id: prepared_row_fingerprint(data.validation)}
    spec = _spec(fingerprints=fingerprints)

    result_a, oof_a = run_xgboost_fold_experiment(
        spec,
        fold=fold,
        data=data,
        estimator_factory=lambda context: build_xgboost_estimators(context, config=config),
    )
    result_b, oof_b = run_xgboost_fold_experiment(
        spec,
        fold=fold,
        data=data,
        estimator_factory=lambda context: build_xgboost_estimators(context, config=config),
    )

    validate_oof_frame(oof_a)
    assert tuple(oof_a.columns) == OOF_COLUMNS
    assert np.isfinite(oof_a["p_arr_delay_15"]).all()
    assert oof_a["p_arr_delay_15"].between(0.0, 1.0).all()
    assert np.isfinite(oof_a["predicted_arr_delay_min"]).all()
    assert np.array_equal(
        oof_a["p_arr_delay_15"].to_numpy(), oof_b["p_arr_delay_15"].to_numpy()
    )
    assert np.array_equal(
        oof_a["predicted_arr_delay_min"].to_numpy(), oof_b["predicted_arr_delay_min"].to_numpy()
    )
    assert result_a.classification.threshold == 0.5
    assert result_a.preprocessor_state_unchanged_after_validation is True
    assert result_a.validation_row_fingerprint == fingerprints[fold.fold_id]
    assert result_b.regression.mae >= 0.0


def test_xgboost_fold_rejects_mismatched_week4_reference_rows_before_output() -> None:
    config = load_xgboost_baseline_config()
    fold, data = _fold_data()
    with pytest.raises(Week4ContractViolation, match="declared reference"):
        run_xgboost_fold_experiment(
            _spec(fingerprints={fold.fold_id: "not-the-week4-validation-fingerprint"}),
            fold=fold,
            data=data,
            estimator_factory=lambda context: build_xgboost_estimators(context, config=config),
        )


def test_xgboost_factory_rejects_unlocked_project_seed() -> None:
    config = load_xgboost_baseline_config()
    fold, _ = _fold_data()
    with pytest.raises(Week4ContractViolation, match="configured project seed"):
        build_xgboost_estimators(
            Week5XGBoostFoldContext(
                fold=fold,
                class_weights={0: 1.0, 1: 1.0},
                spec=replace(_spec(), seed=1),
            ),
            config=config,
        )
