from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

import src.data.preprocessing as preprocessing_module
from src.data.preprocessing import (
    Week3ATemporalBoundaryError,
    audit_training_categorical_cardinality,
    build_boosting_preprocessor,
    build_linear_preprocessor,
    build_tree_preprocessor,
    load_arrival_development_batch,
    iter_arrival_development_batches,
)
from src.features.tabular_features import ARRIVAL_PROJECTED_SOURCE_COLUMNS
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS


def _feature_frame(*, validation: bool = False) -> pd.DataFrame:
    if validation:
        return pd.DataFrame(
            {
                "CRS_ELAPSED_TIME": [10_000.0],
                "calendar_year": [2019],
                "calendar_month": [1],
                "calendar_day_of_month": [4],
                "calendar_day_of_week": [5],
                "is_weekend": [0],
                "scheduled_departure_hour": [13],
                "scheduled_departure_minute": [15],
                "OP_CARRIER": ["UNSEEN_CARRIER"],
                "ORIGIN": ["UNSEEN_ORIGIN"],
                "OP_CARRIER_FL_NUM": ["9999"],
            }
        )
    return pd.DataFrame(
        {
            "CRS_ELAPSED_TIME": [100.0, np.nan, 300.0],
            "calendar_year": [2016, 2017, 2018],
            "calendar_month": [1, 2, 3],
            "calendar_day_of_month": [1, 2, 3],
            "calendar_day_of_week": [5, 4, 3],
            "is_weekend": [0, 0, 0],
            "scheduled_departure_hour": [8, 9, 10],
            "scheduled_departure_minute": [0, 30, 45],
            "OP_CARRIER": ["AA", "AA", "DL"],
            "ORIGIN": ["BOS", "JFK", "BOS"],
            "OP_CARRIER_FL_NUM": ["100", "100", "200"],
        }
    )


@pytest.mark.parametrize(
    "builder",
    [build_linear_preprocessor, build_tree_preprocessor, build_boosting_preprocessor],
)
def test_preprocessors_share_raw_information_set_and_handle_unknown_categories(builder) -> None:
    train = _feature_frame()
    validation = _feature_frame(validation=True)
    transformer = builder()

    transformed_train = transformer.fit_transform(train)
    names_before = tuple(transformer.get_feature_names_out())
    transformed_validation = transformer.transform(validation)

    assert tuple(train.columns) == APPROVED_PREDICTOR_COLUMNS
    assert transformed_train.shape[1] == transformed_validation.shape[1]
    assert tuple(transformer.get_feature_names_out()) == names_before


def test_numeric_imputation_and_scaling_are_fit_on_training_rows_only() -> None:
    train = _feature_frame()
    validation = _feature_frame(validation=True)
    transformer = build_linear_preprocessor()
    transformer.fit(train)

    imputer = transformer.named_transformers_["numeric"].named_steps["imputer"]
    statistics_before = imputer.statistics_.copy()
    assert statistics_before[0] == 200.0

    transformer.transform(validation)

    np.testing.assert_array_equal(imputer.statistics_, statistics_before)
    assert imputer.statistics_[0] != 10_000.0


def test_category_vocabulary_does_not_expand_during_validation_transform() -> None:
    transformer = build_linear_preprocessor().fit(_feature_frame())
    encoder = transformer.named_transformers_["categorical"].named_steps["encoder"]
    categories_before = tuple(tuple(values) for values in encoder.categories_)

    transformer.transform(_feature_frame(validation=True))

    assert tuple(tuple(values) for values in encoder.categories_) == categories_before
    assert "UNSEEN_CARRIER" not in categories_before[0]
    assert "UNSEEN_ORIGIN" not in categories_before[1]


def test_high_cardinality_frequency_map_is_train_only_with_zero_unknown_fallback() -> None:
    transformer = build_tree_preprocessor().fit(_feature_frame())
    encoder = transformer.named_transformers_["high_cardinality"].named_steps[
        "encoder"
    ]
    mapping_before = dict(encoder.frequency_maps_["OP_CARRIER_FL_NUM"])

    transformed = transformer.transform(_feature_frame(validation=True))

    assert mapping_before == {"100": pytest.approx(2 / 3), "200": pytest.approx(1 / 3)}
    assert encoder.frequency_maps_["OP_CARRIER_FL_NUM"] == mapping_before
    high_card_index = list(transformer.get_feature_names_out()).index(
        "high_cardinality__OP_CARRIER_FL_NUM__frequency"
    )
    assert transformed[0, high_card_index] == 0.0


def test_preprocessing_schema_is_deterministic() -> None:
    train = _feature_frame()
    first = build_linear_preprocessor().fit(train)
    second = build_linear_preprocessor().fit(train.copy(deep=True))

    assert tuple(first.get_feature_names_out()) == tuple(second.get_feature_names_out())
    first_values = first.transform(train)
    second_values = second.transform(train)
    first_dense = first_values.toarray() if hasattr(first_values, "toarray") else np.asarray(first_values)
    second_dense = second_values.toarray() if hasattr(second_values, "toarray") else np.asarray(second_values)
    np.testing.assert_allclose(first_dense, second_dense)


def test_cardinality_audit_is_explicitly_training_scoped() -> None:
    result = audit_training_categorical_cardinality(_feature_frame())

    assert result == {"OP_CARRIER": 2, "ORIGIN": 2, "OP_CARRIER_FL_NUM": 2}


@pytest.mark.parametrize("year", [2023, 2024])
def test_week3a_bounded_loader_rejects_non_rolling_years_before_open(year: int) -> None:
    with pytest.raises(Week3ATemporalBoundaryError, match="2016-2022"):
        load_arrival_development_batch(year, max_rows=1)


class _FakeScanner:
    def __init__(self, batch: pa.RecordBatch) -> None:
        self._batch = batch

    def to_batches(self):
        return iter([self._batch])


class _FakeDataset:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._batch = pa.RecordBatch.from_pandas(frame, preserve_index=False)
        self.schema = self._batch.schema

    def scanner(self, **kwargs):
        del kwargs
        return _FakeScanner(self._batch)


@pytest.mark.parametrize(
    ("source_year", "flight_date", "message"),
    [
        (2017, "2016-01-01 00:00:00", "source_year"),
        (2016, "2017-01-01 00:00:00", "FL_DATE"),
    ],
)
def test_development_loader_validates_partition_content_before_yield(
    monkeypatch, source_year: int, flight_date: str, message: str
) -> None:
    frame = pd.DataFrame(
        {
            column: [None]
            for column in ARRIVAL_PROJECTED_SOURCE_COLUMNS
        }
    )
    frame.loc[0, "source_year"] = source_year
    frame.loc[0, "FL_DATE"] = flight_date
    frame.loc[0, "DEST"] = "ATL"
    monkeypatch.setattr(
        preprocessing_module.ds, "dataset", lambda *args, **kwargs: _FakeDataset(frame)
    )

    with pytest.raises(Week3ATemporalBoundaryError, match=message):
        list(iter_arrival_development_batches(2016, batch_size=1))


def test_development_loader_rejects_non_inbound_rows_inside_inbound_partition(
    monkeypatch,
) -> None:
    frame = pd.DataFrame(
        {
            column: [None]
            for column in ARRIVAL_PROJECTED_SOURCE_COLUMNS
        }
    )
    frame.loc[0, "source_year"] = 2016
    frame.loc[0, "FL_DATE"] = "2016-01-01 00:00:00"
    frame.loc[0, "DEST"] = "LAX"
    monkeypatch.setattr(
        preprocessing_module.ds, "dataset", lambda *args, **kwargs: _FakeDataset(frame)
    )

    with pytest.raises(Week3ATemporalBoundaryError, match="DEST=ATL"):
        list(iter_arrival_development_batches(2016, batch_size=1))
