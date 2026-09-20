"""Unit tests for Refactored Architecture V2 (Protocol V2).

Verifies:
1. Feature contract V2: calendar_year is eliminated, 10 approved predictors.
2. Safe chain feature contract representations.
3. Refactored preprocessors transform data into expected shapes.
4. TwoStageHurdleRegressor fits and predicts valid delay ranges.
5. All Huber / Pseudo-Huber loss estimators construct correctly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.refactored_features import (
    APPROVED_PREDICTOR_COLUMNS_V2,
    FEATURE_CONTRACT_VERSION_V2,
    NUMERIC_FEATURE_COLUMNS_V2,
    prepare_arrival_features_v2,
)
from src.data.refactored_preprocessing import (
    build_refactored_linear_preprocessor,
    build_refactored_tree_preprocessor,
)
from src.models.refactored_models import (
    TwoStageHurdleRegressor,
    build_refactored_hgb_bundle,
    build_refactored_linear_bundle,
    build_refactored_xgboost_bundle,
)


def test_refactored_feature_contract_eliminates_calendar_year() -> None:
    """Verifies calendar_year is dropped to eradicate Covariate Shift."""
    assert "calendar_year" not in NUMERIC_FEATURE_COLUMNS_V2
    assert "calendar_year" not in APPROVED_PREDICTOR_COLUMNS_V2
    assert len(APPROVED_PREDICTOR_COLUMNS_V2) == 10
    assert FEATURE_CONTRACT_VERSION_V2 == "arrival_feature_contract_v2"


def test_refactored_feature_preparation() -> None:
    """Tests feature preparation under Protocol V2."""
    raw_mock = pd.DataFrame({
        "FL_DATE": ["2022-05-10 00:00:00", "2022-05-11 00:00:00"],
        "CRS_DEP_TIME": ["2022-05-10 14:30:00", "2022-05-11 09:15:00"],
        "CRS_ELAPSED_TIME": [120.0, 95.0],
        "MONTH": [5, 5],
        "DAY_OF_MONTH": [10, 11],
        "DAY_OF_WEEK": [2, 3],
        "OP_CARRIER": ["DL", "WN"],
        "OP_CARRIER_FL_NUM": [1234.0, 5678.0],
        "ORIGIN": ["MCO", "LGA"],
        "DEST": ["ATL", "ATL"],
        "ARR_DELAY": [25.0, -10.0],
    })
    
    prep = prepare_arrival_features_v2(raw_mock)
    assert prep.feature_contract_version == "arrival_feature_contract_v2"
    assert "calendar_year" not in prep.X.columns
    assert list(prep.X.columns) == list(APPROVED_PREDICTOR_COLUMNS_V2)
    assert prep.y_arr_cls.tolist() == [1, 0]
    assert prep.y_arr_reg.tolist() == [25.0, -10.0]


def test_refactored_preprocessor_transformers() -> None:
    """Verifies that refactored linear and tree preprocessors work seamlessly."""
    mock_X = pd.DataFrame({
        "CRS_ELAPSED_TIME": [120.0, 95.0, 150.0],
        "calendar_month": [5, 6, 7],
        "calendar_day_of_month": [10, 15, 20],
        "calendar_day_of_week": [2, 3, 5],
        "is_weekend": [0, 0, 0],
        "scheduled_departure_hour": [14, 9, 18],
        "scheduled_departure_minute": [30, 15, 45],
        "OP_CARRIER": ["DL", "WN", "AA"],
        "ORIGIN": ["MCO", "LGA", "DFW"],
        "OP_CARRIER_FL_NUM": ["1234", "5678", "9999"],
    })
    
    tree_prep = build_refactored_tree_preprocessor()
    out_tree = tree_prep.fit_transform(mock_X)
    assert out_tree.shape[0] == 3
    assert out_tree.shape[1] >= len(APPROVED_PREDICTOR_COLUMNS_V2)
    
    lin_prep = build_refactored_linear_preprocessor()
    out_lin = lin_prep.fit_transform(mock_X)
    assert out_lin.shape[0] == 3


def test_two_stage_hurdle_regressor() -> None:
    """Verifies two-stage hurdle logic and threshold activation."""
    from sklearn.dummy import DummyClassifier, DummyRegressor
    
    X = np.array([[1.0], [2.0], [3.0], [4.0]])
    y_cls = np.array([0, 0, 1, 1])
    y_reg = np.array([-10.0, -5.0, 30.0, 60.0])
    
    clf = DummyClassifier(strategy="constant", constant=1)
    reg = DummyRegressor(strategy="constant", constant=45.0)
    
    hurdle = TwoStageHurdleRegressor(
        classifier=clf,
        conditional_regressor=reg,
        delay_threshold=15.0,
        gate_probability_threshold=0.5,
        default_on_time_value=-7.5,
    )
    hurdle.fit(X, y_cls, y_reg)
    pred = hurdle.predict(X)
    
    # Because classifier outputs p=1.0 for all, hurdle activates regressor (45.0)
    assert np.all(pred == 45.0)


def test_refactored_huber_estimator_construction() -> None:
    """Verifies that Huber and Pseudo-Huber loss estimators construct with valid parameters."""
    xgb_bundle = build_refactored_xgboost_bundle(huber_slope=15.0)
    assert xgb_bundle.regressor.get_params()["objective"] == "reg:pseudohubererror"
    assert xgb_bundle.regressor.get_params()["huber_slope"] == 15.0

    xgb_quantile = build_refactored_xgboost_bundle(objective="reg:quantileerror", quantile_alpha=0.75)
    assert xgb_quantile.regressor.get_params()["objective"] == "reg:quantileerror"
    assert xgb_quantile.regressor.get_params()["quantile_alpha"] == 0.75

    hgb_bundle = build_refactored_hgb_bundle(loss="absolute_error")
    assert hgb_bundle.regressor.get_params()["loss"] == "absolute_error"

    hgb_huber_alias = build_refactored_hgb_bundle(loss="huber")
    assert hgb_huber_alias.regressor.get_params()["loss"] == "absolute_error"

    lin_bundle = build_refactored_linear_bundle(epsilon=1.35)
    assert lin_bundle.regressor.get_params()["epsilon"] == 1.35


def test_stratified_regression_metrics_strata_and_bias() -> None:
    """Tests compute_stratified_regression_metrics across delay strata."""
    from src.models.metrics import compute_stratified_regression_metrics

    # Mock ground truth and predictions across 3 strata:
    # Early/On-time (<15m): -10, 0, 10
    # Moderate (15 <= y < 60): 20, 40
    # Severe (>=60m): 80, 120
    y_true = np.array([-10.0, 0.0, 10.0, 20.0, 40.0, 80.0, 120.0])
    # Predictions:
    # Early: -5, 5, 5 -> errors: 5, 5, -5 -> bias = 5/3 ~ 1.67, MAE = 5.0
    # Moderate: 25, 35 -> errors: 5, -5 -> bias = 0.0, MAE = 5.0
    # Severe: 70, 110 -> errors: -10, -10 -> bias = -10.0, MAE = 10.0
    y_pred = np.array([-5.0, 5.0, 5.0, 25.0, 35.0, 70.0, 110.0])

    metrics = compute_stratified_regression_metrics(y_true, y_pred)

    # Check overall
    assert metrics.overall.count == 7
    assert metrics.overall.mae is not None and metrics.overall.mae > 0

    # Check early on-time (< 15)
    assert metrics.early_on_time.count == 3
    assert pytest.approx(metrics.early_on_time.mae, rel=1e-3) == 5.0
    assert pytest.approx(metrics.early_on_time.mean_bias, rel=1e-3) == 5.0 / 3.0

    # Check moderate delay (15 <= y < 60)
    assert metrics.moderate_delay.count == 2
    assert pytest.approx(metrics.moderate_delay.mae, rel=1e-3) == 5.0
    assert pytest.approx(metrics.moderate_delay.mean_bias, rel=1e-3) == 0.0

    # Check severe delay (y >= 60)
    assert metrics.severe_delay.count == 2
    assert pytest.approx(metrics.severe_delay.mae, rel=1e-3) == 10.0
    assert pytest.approx(metrics.severe_delay.mean_bias, rel=1e-3) == -10.0
    assert pytest.approx(metrics.severe_delay.mean_true, rel=1e-3) == 100.0
    assert pytest.approx(metrics.severe_delay.mean_pred, rel=1e-3) == 90.0

    # Shrinkage ratio: 90.0 / 100.0 = 0.90 (no collapse)
    assert pytest.approx(metrics.shrinkage_ratio, rel=1e-3) == 0.90
    assert metrics.prediction_collapse_warning is False

    # Check dictionary access and serialization
    d = metrics.to_dict()
    assert d["severe_delay"]["count"] == 2
    assert d["shrinkage_ratio"] == metrics.shrinkage_ratio
    assert metrics["severe_delay"]["mae"] == metrics.severe_delay.mae


def test_prediction_collapse_warning_trigger() -> None:
    """Verifies that shrinkage_ratio < 0.30 triggers collapse warning on severe delay."""
    from src.models.metrics import compute_stratified_regression_metrics

    # Severe ground truth: delays = [100.0, 200.0] -> mean = 150.0
    # Collapsed predictions near 0: [5.0, 10.0] -> mean = 7.5
    # Shrinkage ratio = 7.5 / 150.0 = 0.05 (< 0.30)
    y_true = np.array([-5.0, 10.0, 30.0, 100.0, 200.0])
    y_pred = np.array([-4.0, 8.0, 12.0, 5.0, 10.0])

    with pytest.warns(UserWarning, match="Prediction collapse warning"):
        metrics = compute_stratified_regression_metrics(y_true, y_pred)

    assert metrics.shrinkage_ratio < 0.10
    assert metrics.prediction_collapse_warning is True
    assert metrics.warning_message is not None
    assert "Prediction collapse warning" in metrics.warning_message


def test_stratified_evaluation_contract_validation() -> None:
    """Verifies that contracts module validates stratified evaluation correctly."""
    from src.models.contracts import (
        Week4ContractViolation,
        validate_stratified_evaluation_contract,
    )
    from src.models.metrics import compute_stratified_regression_metrics

    y_true = np.array([5.0, 20.0, 75.0])
    y_pred = np.array([4.0, 18.0, 65.0])
    metrics = compute_stratified_regression_metrics(y_true, y_pred)

    # Valid metrics pass
    validate_stratified_evaluation_contract(metrics)

    # Non-instance raises violation
    with pytest.raises(Week4ContractViolation, match="instance of StratifiedRegressionMetrics"):
        validate_stratified_evaluation_contract({"fake": "metric"})  # type: ignore[arg-type]

