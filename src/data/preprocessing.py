"""Fold-safe transformer builders and bounded Core Arrival development IO.

Only preprocessing transformers are fitted here.  No predictive estimator is
constructed or trained, and Week 3A reads are restricted to 2016-2022.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import resolve_project_root
from src.data.temporal_protocol import ROLLING_DEVELOPMENT_YEARS
from src.features.tabular_features import (
    APPROVED_PREDICTOR_COLUMNS,
    ARRIVAL_PROJECTED_SOURCE_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
)


PREPROCESSING_VERSION: Final = "arrival_preprocessing_v1"
MISSING_SENTINEL: Final = "__MISSING__"
UNKNOWN_FREQUENCY: Final = 0.0


class Week3ATemporalBoundaryError(ValueError):
    """Raised before IO when Week 3A is asked to open 2023 or 2024."""


class FrequencyEncoder(BaseEstimator, TransformerMixin):
    """Deterministic, training-fitted non-target frequency encoding.

    Validation-only categories map to zero.  The transformer never consumes a
    target and therefore cannot perform target encoding.
    """

    def __init__(
        self,
        *,
        feature_names: tuple[str, ...],
        unknown_value: float = UNKNOWN_FREQUENCY,
    ) -> None:
        self.feature_names = feature_names
        self.unknown_value = unknown_value

    def _array(self, X: object) -> np.ndarray:
        array = np.asarray(X, dtype=object)
        if array.ndim == 1:
            array = array.reshape(-1, 1)
        if array.ndim != 2 or array.shape[1] != len(self.feature_names):
            raise ValueError(
                "FrequencyEncoder input width does not match configured feature names"
            )
        return array

    def fit(self, X: object, y: object = None) -> "FrequencyEncoder":
        del y
        array = self._array(X)
        self.n_features_in_ = array.shape[1]
        self.feature_names_in_ = np.asarray(self.feature_names, dtype=object)
        self.frequency_maps_: dict[str, dict[str, float]] = {}
        denominator = len(array)
        if denominator == 0:
            raise ValueError("FrequencyEncoder cannot fit an empty training fold")
        for index, name in enumerate(self.feature_names):
            values = pd.Series(array[:, index], dtype="object").map(str)
            counts = values.value_counts(dropna=False, sort=False) / denominator
            self.frequency_maps_[name] = {
                str(category): float(frequency)
                for category, frequency in counts.items()
            }
        return self

    def transform(self, X: object) -> np.ndarray:
        check_is_fitted(self, "frequency_maps_")
        array = self._array(X)
        result = np.empty(array.shape, dtype="float64")
        for index, name in enumerate(self.feature_names):
            mapping = self.frequency_maps_[name]
            result[:, index] = pd.Series(array[:, index], dtype="object").map(
                lambda value: mapping.get(str(value), self.unknown_value)
            )
        return result

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        del input_features
        return np.asarray(
            [f"{name}__frequency" for name in self.feature_names], dtype=object
        )


def _numeric_pipeline(*, scale: bool) -> Pipeline:
    steps: list[tuple[str, object]] = [
        (
            "imputer",
            SimpleImputer(
                strategy="median", add_indicator=True, keep_empty_features=True
            ),
        )
    ]
    if scale:
        steps.append(("scaler", StandardScaler()))
    return Pipeline(steps)


def _categorical_pipeline(*, one_hot: bool) -> Pipeline:
    if one_hot:
        encoder: object = OneHotEncoder(
            handle_unknown="ignore", sparse_output=True, dtype=np.float64
        )
    else:
        encoder = OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
            encoded_missing_value=-2,
            dtype=np.float64,
        )
    return Pipeline(
        [
            (
                "imputer",
                SimpleImputer(
                    strategy="constant",
                    fill_value=MISSING_SENTINEL,
                    keep_empty_features=True,
                ),
            ),
            ("encoder", encoder),
        ]
    )


def _high_cardinality_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "imputer",
                SimpleImputer(
                    strategy="constant",
                    fill_value=MISSING_SENTINEL,
                    keep_empty_features=True,
                ),
            ),
            (
                "encoder",
                FrequencyEncoder(feature_names=HIGH_CARDINALITY_FEATURE_COLUMNS),
            ),
        ]
    )


def build_linear_preprocessor() -> ColumnTransformer:
    """Build Logistic/Ridge preprocessing; fit it on one fold's train rows."""
    return ColumnTransformer(
        [
            ("numeric", _numeric_pipeline(scale=True), list(NUMERIC_FEATURE_COLUMNS)),
            (
                "categorical",
                _categorical_pipeline(one_hot=True),
                list(CATEGORICAL_FEATURE_COLUMNS),
            ),
            (
                "high_cardinality",
                _high_cardinality_pipeline(),
                list(HIGH_CARDINALITY_FEATURE_COLUMNS),
            ),
        ],
        remainder="drop",
        sparse_threshold=0.3,
        verbose_feature_names_out=True,
    )


def build_tree_preprocessor() -> ColumnTransformer:
    """Build RF/HGB-style dense preprocessing; fit only on fold train rows."""
    return ColumnTransformer(
        [
            ("numeric", _numeric_pipeline(scale=False), list(NUMERIC_FEATURE_COLUMNS)),
            (
                "categorical",
                _categorical_pipeline(one_hot=False),
                list(CATEGORICAL_FEATURE_COLUMNS),
            ),
            (
                "high_cardinality",
                _high_cardinality_pipeline(),
                list(HIGH_CARDINALITY_FEATURE_COLUMNS),
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


def build_boosting_preprocessor() -> ColumnTransformer:
    """Build the future-tree preprocessing family without a model estimator."""
    return build_tree_preprocessor()


def audit_training_categorical_cardinality(
    training_features: pd.DataFrame,
) -> dict[str, int]:
    """Audit categorical cardinality from caller-supplied training rows only."""
    required = (*CATEGORICAL_FEATURE_COLUMNS, *HIGH_CARDINALITY_FEATURE_COLUMNS)
    missing = set(required).difference(training_features.columns)
    if missing:
        raise ValueError(f"Training feature frame is missing: {sorted(missing)}")
    return {
        column: int(training_features[column].nunique(dropna=False))
        for column in required
    }


def _assert_week3a_year(year: int) -> None:
    if year not in ROLLING_DEVELOPMENT_YEARS:
        raise Week3ATemporalBoundaryError(
            "Week 3A row-level preprocessing reads are restricted to 2016-2022"
        )


def _validate_arrival_partition_batch(frame: pd.DataFrame, *, expected_year: int) -> None:
    """Fail closed on partition-content provenance before yielding rows."""
    source_year = pd.to_numeric(frame["source_year"], errors="coerce")
    invalid_source_year = (
        source_year.isna()
        | ~np.isfinite(source_year)
        | (source_year != np.floor(source_year))
        | (source_year != expected_year)
    )
    if bool(invalid_source_year.any()):
        raise Week3ATemporalBoundaryError(
            f"source_year must equal requested partition year {expected_year}"
        )

    flight_date = pd.to_datetime(
        frame["FL_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    invalid_flight_date = flight_date.isna() | (flight_date.dt.year != expected_year)
    if bool(invalid_flight_date.any()):
        raise Week3ATemporalBoundaryError(
            f"FL_DATE must remain within requested partition year {expected_year}"
        )

    inbound = frame["DEST"].astype("string").str.strip().eq("ATL").fillna(False)
    if not bool(inbound.all()):
        raise Week3ATemporalBoundaryError(
            "inbound_atl partition contains a row outside DEST=ATL"
        )


def iter_arrival_development_batches(
    year: int,
    *,
    project_root: Path | None = None,
    batch_size: int = 4096,
) -> Iterator[pd.DataFrame]:
    """Yield projected inbound batches for one rolling-development year."""
    _assert_week3a_year(year)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    assert_data_access_allowed(year, "development")
    root = resolve_project_root(project_root)
    partition = root / "data" / "processed" / "inbound_atl" / f"year={year}"
    dataset = ds.dataset(partition, format="parquet")
    missing = set(ARRIVAL_PROJECTED_SOURCE_COLUMNS).difference(dataset.schema.names)
    if missing:
        raise ValueError(
            f"Inbound partition is missing projected columns: {sorted(missing)}"
        )
    scanner = dataset.scanner(
        columns=list(ARRIVAL_PROJECTED_SOURCE_COLUMNS),
        batch_size=batch_size,
        use_threads=False,
        batch_readahead=1,
        fragment_readahead=1,
    )
    for batch in scanner.to_batches():
        frame = batch.to_pandas()
        _validate_arrival_partition_batch(frame, expected_year=year)
        yield frame


def load_arrival_development_batch(
    year: int,
    *,
    project_root: Path | None = None,
    max_rows: int,
    batch_size: int = 4096,
) -> pd.DataFrame:
    """Load at most ``max_rows`` projected rows for bounded validation."""
    _assert_week3a_year(year)
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")
    frames: list[pd.DataFrame] = []
    remaining = max_rows
    for batch in iter_arrival_development_batches(
        year,
        project_root=project_root,
        batch_size=min(batch_size, max_rows),
    ):
        selected = batch.iloc[:remaining].copy(deep=True)
        frames.append(selected)
        remaining -= len(selected)
        if remaining == 0:
            break
    if not frames:
        return pd.DataFrame(columns=ARRIVAL_PROJECTED_SOURCE_COLUMNS)
    result = pd.concat(frames, ignore_index=True)
    return result.loc[:, list(ARRIVAL_PROJECTED_SOURCE_COLUMNS)]


assert tuple(
    (*NUMERIC_FEATURE_COLUMNS, *CATEGORICAL_FEATURE_COLUMNS, *HIGH_CARDINALITY_FEATURE_COLUMNS)
) == APPROVED_PREDICTOR_COLUMNS
