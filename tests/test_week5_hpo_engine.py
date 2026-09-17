from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.features.tabular_features import prepare_arrival_features
from src.models.contracts import ExperimentSpec, FoldData, RollingFold, Week4ContractViolation
from src.models.hpo import HPOFoldContext, run_hpo_trial
from src.models.week5_contracts import (
    Week5StudySpec,
    assert_week5_result_artifact_writable,
    load_week5_rolling_folds,
    load_week5_study_specs,
    validate_week5_rolling_folds,
)
from src.models.week5_hpo_protocol import Week5ProtocolViolation, load_week5_hpo_protocol


class _DeterministicTrial:
    def __init__(self, number: int = 7) -> None:
        self.number = number
        self.params: dict[str, Any] = {}
        self.user_attrs: dict[str, Any] = {}

    def suggest_int(
        self,
        name: str,
        low: int,
        high: int,
        *,
        step: int = 1,
        log: bool = False,
    ) -> int:
        del high, step, log
        self.params[name] = low
        return low

    def suggest_float(
        self,
        name: str,
        low: float,
        high: float,
        *,
        step: float | None = None,
        log: bool = False,
    ) -> float:
        del high, step, log
        self.params[name] = low
        return low

    def suggest_categorical(self, name: str, choices: list[Any]) -> Any:
        self.params[name] = choices[0]
        return choices[0]

    def set_user_attr(self, name: str, value: Any) -> None:
        self.user_attrs[name] = value


class _ProbabilityOnlyClassifier:
    classes_ = np.asarray([0, 1])

    def fit(self, X: object, y: object) -> "_ProbabilityOnlyClassifier":
        del X, y
        return self

    def predict(self, X: object) -> np.ndarray:
        del X
        raise AssertionError("classification HPO must not consume hard labels")

    def predict_proba(self, X: object) -> np.ndarray:
        rows = int(getattr(X, "shape")[0])
        positive = np.resize(np.asarray([0.1, 0.9]), rows)
        return np.column_stack([1.0 - positive, positive])


class _SignedTargetRegressor:
    seen_targets: list[np.ndarray] = []

    def fit(self, X: object, y: object) -> "_SignedTargetRegressor":
        del X
        self.seen_targets.append(np.asarray(y, dtype=float).copy())
        return self

    def predict(self, X: object) -> np.ndarray:
        rows = int(getattr(X, "shape")[0])
        return np.resize(np.asarray([-10.0, 20.0]), rows)


class _OffsetRegressor:
    def __init__(self, offset: float) -> None:
        self.offset = offset

    def fit(self, X: object, y: object) -> "_OffsetRegressor":
        del X, y
        return self

    def predict(self, X: object) -> np.ndarray:
        rows = int(getattr(X, "shape")[0])
        return np.resize(np.asarray([-10.0, 20.0]), rows) + self.offset


class _TrackingPreprocessor:
    fitted_year_sets: list[set[int]] = []
    transformed_year_sets: list[set[int]] = []

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        self.fitted_year_sets.append(set(X["calendar_year"].astype(int)))
        return np.asarray(X[["calendar_year"]], dtype=float)

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        self.transformed_year_sets.append(set(X["calendar_year"].astype(int)))
        return np.asarray(X[["calendar_year"]], dtype=float)


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
            "flight_key": [f"synthetic-{year}-a", f"synthetic-{year}-b"],
            "source_year": [year, year],
            "source_row_number": [1, 2],
        }
    )


def _provider(fold: RollingFold) -> FoldData:
    train = prepare_arrival_features(
        pd.concat([_raw_year(year) for year in fold.train_years], ignore_index=True)
    )
    validation = prepare_arrival_features(_raw_year(fold.validation_year))
    return FoldData(train=train, validation=validation)


def _spec(study_id: str) -> Week5StudySpec:
    protocol = load_week5_hpo_protocol()
    return load_week5_study_specs(protocol)[study_id]


def test_week5_contract_extends_methods_without_rewriting_week4_history() -> None:
    with pytest.raises(Week4ContractViolation, match="Week 4 does not permit"):
        ExperimentSpec(
            method_id="xgboost",  # type: ignore[arg-type]
            model_version="historically_invalid_week4_method",
            config_version="0.1.0",
            seed=202601,
        )

    studies = load_week5_study_specs(load_week5_hpo_protocol())
    assert len(studies) == 6
    assert studies["xgboost_classification"].method_id == "xgboost"
    assert studies["xgboost_classification"].task == "classification"


def test_week5_contract_uses_exactly_the_four_locked_folds() -> None:
    folds = load_week5_rolling_folds(load_week5_hpo_protocol())
    assert [(fold.fold_id, fold.train_years, fold.validation_year) for fold in folds] == [
        ("fold_1", (2016, 2017, 2018), 2019),
        ("fold_2", (2016, 2017, 2018, 2019), 2020),
        ("fold_3", (2016, 2017, 2018, 2019, 2020), 2021),
        ("fold_4", (2016, 2017, 2018, 2019, 2020, 2021), 2022),
    ]


@pytest.mark.parametrize("blocked_year", [2023, 2024])
def test_week5_fold_validation_rejects_hpo_in_blocked_years(blocked_year: int) -> None:
    folds = list(load_week5_rolling_folds(load_week5_hpo_protocol()))
    folds[-1] = RollingFold("fold_4", folds[-1].train_years, blocked_year)
    with pytest.raises((Week5ProtocolViolation, PermissionError), match="HPO is blocked"):
        validate_week5_rolling_folds(tuple(folds))


def test_classification_objective_consumes_probability_and_records_trial_evidence() -> None:
    trial = _DeterministicTrial()

    def factory(context: HPOFoldContext) -> _ProbabilityOnlyClassifier:
        assert context.task == "classification"
        assert context.class_weights == {0: 1.0, 1: 1.0}
        return _ProbabilityOnlyClassifier()

    value = run_hpo_trial(
        _spec("random_forest_classification"),
        trial=trial,
        fold_data_provider=_provider,
        estimator_factory=factory,
    )

    assert value == pytest.approx(1.0)
    assert trial.user_attrs["trial_number"] == 7
    assert trial.user_attrs["fold_ids"] == ["fold_1", "fold_2", "fold_3", "fold_4"]
    assert trial.user_attrs["per_fold_objective"] == [1.0, 1.0, 1.0, 1.0]
    assert trial.user_attrs["aggregate_objective"] == pytest.approx(1.0)
    assert trial.user_attrs["seed"] == 202601
    assert trial.user_attrs["model_family"] == "tree"
    assert trial.user_attrs["feature_manifest_version"] == "feature_manifest_arrival_v1"
    assert trial.user_attrs["preprocessing_version"] == "arrival_preprocessing_v1"
    assert len(trial.user_attrs["protocol_hash"]) == 64
    assert trial.user_attrs["runtime_seconds"] >= 0.0
    assert all(
        "pr_auc" in metrics and "roc_auc" in metrics and "brier_score" in metrics
        for metrics in trial.user_attrs["per_fold_metrics"]
    )


def test_regression_engine_fits_unmodified_signed_arrival_target() -> None:
    _SignedTargetRegressor.seen_targets = []

    value = run_hpo_trial(
        _spec("hist_gradient_boosting_regression"),
        trial=_DeterministicTrial(),
        fold_data_provider=_provider,
        estimator_factory=lambda context: _SignedTargetRegressor(),
    )

    assert value == pytest.approx(0.0)
    assert len(_SignedTargetRegressor.seen_targets) == 4
    assert all(float(target.min()) == -10.0 for target in _SignedTargetRegressor.seen_targets)
    assert all(float(target.max()) == 20.0 for target in _SignedTargetRegressor.seen_targets)


def test_preprocessing_is_refit_on_train_side_of_each_fold_only() -> None:
    _TrackingPreprocessor.fitted_year_sets = []
    _TrackingPreprocessor.transformed_year_sets = []

    run_hpo_trial(
        _spec("random_forest_regression"),
        trial=_DeterministicTrial(),
        fold_data_provider=_provider,
        estimator_factory=lambda context: _SignedTargetRegressor(),
        preprocessor_factory=_TrackingPreprocessor,
    )

    assert _TrackingPreprocessor.fitted_year_sets == [
        {2016, 2017, 2018},
        {2016, 2017, 2018, 2019},
        {2016, 2017, 2018, 2019, 2020},
        {2016, 2017, 2018, 2019, 2020, 2021},
    ]
    assert _TrackingPreprocessor.transformed_year_sets == [{2019}, {2020}, {2021}, {2022}]
    assert all(
        validation_year not in train_years
        for train_years, validation_year in zip(
            _TrackingPreprocessor.fitted_year_sets,
            [2019, 2020, 2021, 2022],
            strict=True,
        )
    )


def test_regression_objective_uses_equal_fold_macro_not_row_weighting() -> None:
    offsets = {"fold_1": 1.0, "fold_2": 2.0, "fold_3": 3.0, "fold_4": 4.0}

    value = run_hpo_trial(
        _spec("xgboost_regression"),
        trial=_DeterministicTrial(),
        fold_data_provider=_provider,
        estimator_factory=lambda context: _OffsetRegressor(offsets[context.fold.fold_id]),
    )

    assert value == pytest.approx(2.5)


def test_engine_rejects_in_memory_study_mutation_even_when_hash_string_is_unchanged() -> None:
    registered = _spec("random_forest_regression")
    altered_space = dict(registered.search_space)
    altered_space["n_estimators"] = {"type": "int", "low": 1, "high": 2}
    altered = replace(registered, search_space=altered_space)

    with pytest.raises(Week5ProtocolViolation, match="frozen study declaration"):
        run_hpo_trial(
            altered,
            trial=_DeterministicTrial(),
            fold_data_provider=_provider,
            estimator_factory=lambda context: _SignedTargetRegressor(),
        )


def test_result_artifact_guard_blocks_hash_mismatch_and_completed_overwrite(
    tmp_path: Path,
) -> None:
    protocol = load_week5_hpo_protocol()
    artifact = tmp_path / "study_result.json"

    assert_week5_result_artifact_writable(artifact, protocol_hash=protocol.protocol_hash)
    artifact.write_text(
        json.dumps({"status": "INTERRUPTED", "protocol_hash": "wrong-hash"}),
        encoding="utf-8",
    )
    with pytest.raises(Week5ProtocolViolation, match="protocol hash mismatch"):
        assert_week5_result_artifact_writable(artifact, protocol_hash=protocol.protocol_hash)

    artifact.write_text(
        json.dumps({"status": "COMPLETED", "protocol_hash": protocol.protocol_hash}),
        encoding="utf-8",
    )
    with pytest.raises(Week5ProtocolViolation, match="completed artifact"):
        assert_week5_result_artifact_writable(artifact, protocol_hash=protocol.protocol_hash)
