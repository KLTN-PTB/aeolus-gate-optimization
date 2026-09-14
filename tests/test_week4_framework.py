from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.features.tabular_features import prepare_arrival_features
from src.models.artifacts import OOF_COLUMNS, ParquetOOFSink, write_json_artifact
from src.models.contracts import (
    OOF_SCHEMA_VERSION,
    ExperimentSpec,
    FoldData,
    Week4ContractViolation,
    load_week4_rolling_folds,
)
from src.models.rolling import EstimatorBundle, run_rolling_experiment


class _SyntheticClassifier:
    classes_ = np.asarray([0, 1])

    def fit(self, X: object, y: object) -> "_SyntheticClassifier":
        del X, y
        return self

    def predict_proba(self, X: object) -> np.ndarray:
        row_count = int(getattr(X, "shape")[0])
        positive = np.resize(np.asarray([0.2, 0.8], dtype=float), row_count)
        return np.column_stack([1.0 - positive, positive])


class _SyntheticRegressor:
    def fit(self, X: object, y: object) -> "_SyntheticRegressor":
        del X, y
        return self

    def predict(self, X: object) -> np.ndarray:
        row_count = int(getattr(X, "shape")[0])
        return np.resize(np.asarray([-9.0, 19.0], dtype=float), row_count)


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


def _provider(fold: object) -> FoldData:
    train_years = getattr(fold, "train_years")
    validation_year = getattr(fold, "validation_year")
    train = prepare_arrival_features(pd.concat([_raw_year(year) for year in train_years]))
    validation = prepare_arrival_features(_raw_year(validation_year))
    return FoldData(train=train, validation=validation)


def _factory(contexts: list[object]):
    def factory(context: object) -> EstimatorBundle:
        contexts.append(context)
        return EstimatorBundle(_SyntheticClassifier(), _SyntheticRegressor())

    return factory


def _spec() -> ExperimentSpec:
    return ExperimentSpec(
        method_id="linear",
        model_version="synthetic_linear_v1",
        config_version="0.1.0",
        seed=202601,
    )


def test_synthetic_rolling_runner_uses_all_locked_folds_and_oof_schema() -> None:
    contexts: list[object] = []
    result = run_rolling_experiment(
        _spec(),
        fold_data_provider=_provider,
        estimator_factory=_factory(contexts),
        retain_oof_batches=True,
    )

    assert [item.fold_id for item in result.fold_results] == [
        "fold_1",
        "fold_2",
        "fold_3",
        "fold_4",
    ]
    assert result.oof_rows_written == 8
    assert len(contexts) == 4
    assert all(getattr(context, "class_weights") == {0: 1.0, 1: 1.0} for context in contexts)
    assert all(item.classification.threshold == 0.5 for item in result.fold_results)
    assert all(item.classification.calibration["bin_count"] == 10 for item in result.fold_results)
    assert all(item.regression.r2 is not None for item in result.fold_results)
    assert all(item.peak_memory_bytes >= 0 for item in result.fold_results)
    assert all(
        item.fit_resources.memory_scope == "python_allocations_only_not_process_rss"
        for item in result.fold_results
    )
    for batch, fold in zip(result.retained_oof_batches, result.fold_results, strict=True):
        assert tuple(batch.columns) == OOF_COLUMNS
        assert set(batch["validation_year"]) == {fold.validation_year}
        assert set(batch["oof_schema_version"]) == {OOF_SCHEMA_VERSION}
        assert set(batch["y_arr_cls_pred_0_5"]) == {0, 1}
        assert set(batch["predicted_arr_delay_min"]) == {-9.0, 19.0}


def test_runner_requires_streaming_sink_or_explicit_small_test_retention() -> None:
    with pytest.raises(Week4ContractViolation, match="OOF sink"):
        run_rolling_experiment(
            _spec(),
            fold_data_provider=_provider,
            estimator_factory=_factory([]),
        )


def test_runner_enforces_declared_cross_method_validation_row_identity() -> None:
    reference = run_rolling_experiment(
        _spec(),
        fold_data_provider=_provider,
        estimator_factory=_factory([]),
        retain_oof_batches=True,
    )
    fingerprints = {
        result.fold_id: result.validation_row_fingerprint
        for result in reference.fold_results
    }
    matching = replace(
        _spec(),
        expected_validation_row_fingerprints=fingerprints,
    )
    run_rolling_experiment(
        matching,
        fold_data_provider=_provider,
        estimator_factory=_factory([]),
        retain_oof_batches=True,
    )
    fingerprints["fold_1"] = "incorrect-row-contract"
    with pytest.raises(Week4ContractViolation, match="differ from the declared reference"):
        run_rolling_experiment(
            replace(_spec(), expected_validation_row_fingerprints=fingerprints),
            fold_data_provider=_provider,
            estimator_factory=_factory([]),
            retain_oof_batches=True,
        )


def test_runner_rejects_forbidden_predictor_before_estimator_fit() -> None:
    def unsafe_provider(fold: object) -> FoldData:
        data = _provider(fold)
        if getattr(fold, "fold_id") == "fold_1":
            unsafe_validation = replace(data.validation, X=data.validation.X.assign(DEP_DELAY=1.0))
            return FoldData(train=data.train, validation=unsafe_validation)
        return data

    with pytest.raises(Week4ContractViolation, match="predictor columns"):
        run_rolling_experiment(
            _spec(),
            fold_data_provider=unsafe_provider,
            estimator_factory=_factory([]),
            retain_oof_batches=True,
        )


def test_runner_rejects_2023_provenance_before_estimator_fit() -> None:
    def invalid_year_provider(fold: object) -> FoldData:
        data = _provider(fold)
        if getattr(fold, "fold_id") == "fold_1":
            invalid_validation = prepare_arrival_features(_raw_year(2023))
            return FoldData(train=data.train, validation=invalid_validation)
        return data

    with pytest.raises(Week4ContractViolation, match="source years"):
        run_rolling_experiment(
            _spec(),
            fold_data_provider=invalid_year_provider,
            estimator_factory=_factory([]),
            retain_oof_batches=True,
        )


def test_parquet_sink_and_json_manifest_are_versioned_and_fold_streamed(tmp_path: Path) -> None:
    oof_path = tmp_path / "oof.parquet"
    contexts: list[object] = []
    with ParquetOOFSink(oof_path) as sink:
        result = run_rolling_experiment(
            _spec(),
            fold_data_provider=_provider,
            estimator_factory=_factory(contexts),
            oof_sink=sink.append,
        )

    written = pq.read_table(oof_path).to_pandas()
    assert len(written) == 8
    assert tuple(written.columns) == OOF_COLUMNS
    assert result.retained_oof_batches == ()
    manifest_path = tmp_path / "arrival_week4_manifest.json"
    write_json_artifact(manifest_path, result.manifest())
    assert '"diagnostics_only_no_posthoc_calibrator"' in manifest_path.read_text(encoding="utf-8")


def test_week4_fold_loader_reuses_manifest_backed_2016_to_2022_protocol() -> None:
    folds = load_week4_rolling_folds()
    assert [(fold.fold_id, fold.train_years, fold.validation_year) for fold in folds] == [
        ("fold_1", (2016, 2017, 2018), 2019),
        ("fold_2", (2016, 2017, 2018, 2019), 2020),
        ("fold_3", (2016, 2017, 2018, 2019, 2020), 2021),
        ("fold_4", (2016, 2017, 2018, 2019, 2020, 2021), 2022),
    ]


@pytest.mark.parametrize(
    ("method_id", "expected_family"),
    [
        ("linear", "linear"),
        ("random_forest", "tree"),
        ("hist_gradient_boosting", "boosting"),
    ],
)
def test_runner_supports_only_the_three_week4_model_families(
    method_id: str, expected_family: str
) -> None:
    spec = ExperimentSpec(
        method_id=method_id,  # type: ignore[arg-type]
        model_version=f"synthetic_{method_id}_v1",
        config_version="0.1.0",
        seed=202601,
    )
    result = run_rolling_experiment(
        spec,
        fold_data_provider=_provider,
        estimator_factory=_factory([]),
        retain_oof_batches=True,
    )
    assert result.manifest()["method"]["model_family"] == expected_family


def test_contract_refuses_out_of_scope_xgboost_before_any_fold_is_loaded() -> None:
    with pytest.raises(Week4ContractViolation, match="does not permit method"):
        ExperimentSpec(
            method_id="xgboost",  # type: ignore[arg-type]
            model_version="not_allowed",
            config_version="0.1.0",
            seed=202601,
        )
