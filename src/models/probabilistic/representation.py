"""Fold-safe Neural Network feature representation for Probabilistic Core Arrival.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 3.3
Representation contract:
- time-of-day = minutes since midnight; sin(2πt/1440), cos(2πt/1440)
- month = cyclic sin/cos: sin(2π(m-1)/12), cos(2π(m-1)/12)
- day-of-week = cyclic sin/cos: sin(2π(d-1)/7), cos(2π(d-1)/7)
- CRS_ELAPSED_TIME, calendar_year, calendar_day_of_month, is_weekend:
  fold-train median imputation + StandardScaler
- OP_CARRIER, ORIGIN, OP_CARRIER_FL_NUM:
  fold-train vocabulary with dedicated UNKNOWN embedding index
- Strict preservation of the frozen 11 approved predictor columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler

from src.models.probabilistic.contracts import (
    CATEGORICAL_EMBEDDING_COLUMNS,
    CYCLIC_SOURCE_COLUMNS,
    NUMERIC_SCALED_COLUMNS,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    REPRESENTATION_VERSION,
    ProbabilisticContractViolation,
)

MINUTES_PER_DAY: Final = 1440.0
MONTHS_PER_YEAR: Final = 12.0
DAYS_PER_WEEK: Final = 7.0

CONTINUOUS_FEATURE_NAMES: Final = (
    "sin_time_of_day",
    "cos_time_of_day",
    "sin_calendar_month",
    "cos_calendar_month",
    "sin_calendar_day_of_week",
    "cos_calendar_day_of_week",
    "CRS_ELAPSED_TIME_scaled",
    "calendar_year_scaled",
    "calendar_day_of_month_scaled",
    "is_weekend_scaled",
)


@dataclass(frozen=True)
class ProcessedNNFeatures:
    """Aligned continuous and categorical embedding representation for neural nets."""

    continuous: np.ndarray  # shape (N, 10), float64
    categorical: np.ndarray  # shape (N, 3), int64
    continuous_feature_names: tuple[str, ...]
    categorical_feature_names: tuple[str, ...]
    vocabulary_sizes: Mapping[str, int]
    unknown_indices: Mapping[str, int]


class ProbabilisticNNPreprocessor(BaseEstimator, TransformerMixin):
    """Deterministic, fold-safe NN preprocessor preserving the 11-feature contract."""

    def __init__(self, *, representation_version: str = REPRESENTATION_VERSION) -> None:
        self.representation_version = representation_version
        self.is_fitted_ = False
        self.numeric_medians_: dict[str, float] = {}
        self.scaler_: StandardScaler | None = None
        self.vocabularies_: dict[str, dict[str, int]] = {}
        self.unknown_indices_: dict[str, int] = {}
        self.vocabulary_sizes_: dict[str, int] = {}

    def _validate_columns(self, X: pd.DataFrame) -> None:
        missing = set(PROBABILISTIC_PREDICTOR_COLUMNS).difference(X.columns)
        if missing:
            raise ProbabilisticContractViolation(
                f"Input DataFrame is missing approved predictor columns: {sorted(missing)}"
            )
        extra = set(X.columns).difference(PROBABILISTIC_PREDICTOR_COLUMNS)
        if extra:
            raise ProbabilisticContractViolation(
                f"Input DataFrame contains unauthorized extra columns: {sorted(extra)}"
            )

    def fit(self, X: pd.DataFrame, y: object = None) -> "ProbabilisticNNPreprocessor":
        """Fit preprocessing statistics strictly on training fold rows."""
        del y
        self._validate_columns(X)

        # 1. Fit medians for numeric scaled features
        self.numeric_medians_ = {}
        imputed_numerics = np.empty((len(X), len(NUMERIC_SCALED_COLUMNS)), dtype=np.float64)
        for i, col in enumerate(NUMERIC_SCALED_COLUMNS):
            values = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(values)
            median_val = float(np.median(values[valid])) if np.any(valid) else 0.0
            self.numeric_medians_[col] = median_val
            values_imputed = np.where(valid, values, median_val)
            imputed_numerics[:, i] = values_imputed

        # 2. Fit StandardScaler on imputed numerics
        self.scaler_ = StandardScaler()
        self.scaler_.fit(imputed_numerics)

        # 3. Fit categorical vocabularies
        self.vocabularies_ = {}
        self.unknown_indices_ = {}
        self.vocabulary_sizes_ = {}

        for col in CATEGORICAL_EMBEDDING_COLUMNS:
            raw_series = X[col].dropna().astype(str).str.strip()
            unique_cats = sorted(raw_series[raw_series != ""].unique())
            cat_to_idx = {cat: idx for idx, cat in enumerate(unique_cats)}
            unknown_idx = len(unique_cats)  # Index K is dedicated UNKNOWN
            vocab_size = len(unique_cats) + 1  # 0 to K inclusive

            self.vocabularies_[col] = cat_to_idx
            self.unknown_indices_[col] = unknown_idx
            self.vocabulary_sizes_[col] = vocab_size

        self.is_fitted_ = True
        return self

    def transform(self, X: pd.DataFrame) -> ProcessedNNFeatures:
        """Transform data using strictly the statistics fitted on the training fold."""
        if not self.is_fitted_ or self.scaler_ is None:
            raise ProbabilisticContractViolation("ProbabilisticNNPreprocessor is not fitted")
        self._validate_columns(X)

        n_rows = len(X)

        # 1. Cyclic time-of-day: t = 60 * hour + minute
        hour = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").to_numpy(dtype=np.float64)
        minute = pd.to_numeric(X["scheduled_departure_minute"], errors="coerce").to_numpy(dtype=np.float64)
        time_minutes = 60.0 * hour + minute
        sin_time = np.sin(2.0 * np.pi * time_minutes / MINUTES_PER_DAY)
        cos_time = np.cos(2.0 * np.pi * time_minutes / MINUTES_PER_DAY)

        # 2. Cyclic month: m in 1..12 -> (m - 1) / 12
        month = pd.to_numeric(X["calendar_month"], errors="coerce").to_numpy(dtype=np.float64)
        sin_month = np.sin(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)
        cos_month = np.cos(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)

        # 3. Cyclic day-of-week: d in 1..7 -> (d - 1) / 7
        dow = pd.to_numeric(X["calendar_day_of_week"], errors="coerce").to_numpy(dtype=np.float64)
        sin_dow = np.sin(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)
        cos_dow = np.cos(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)

        # 4. Impute and scale numeric features
        imputed_numerics = np.empty((n_rows, len(NUMERIC_SCALED_COLUMNS)), dtype=np.float64)
        for i, col in enumerate(NUMERIC_SCALED_COLUMNS):
            values = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(values)
            median_val = self.numeric_medians_[col]
            imputed_numerics[:, i] = np.where(valid, values, median_val)

        scaled_numerics = self.scaler_.transform(imputed_numerics)

        # Continuous matrix: (N, 10)
        continuous = np.column_stack(
            [
                sin_time,
                cos_time,
                sin_month,
                cos_month,
                sin_dow,
                cos_dow,
                scaled_numerics,
            ]
        )

        # 5. Categorical embedding indices: (N, 3)
        categorical = np.empty((n_rows, len(CATEGORICAL_EMBEDDING_COLUMNS)), dtype=np.int64)
        for i, col in enumerate(CATEGORICAL_EMBEDDING_COLUMNS):
            cat_map = self.vocabularies_[col]
            unknown_idx = self.unknown_indices_[col]
            raw_vals = X[col].astype(object).fillna("").astype(str).str.strip()
            indices = np.array([cat_map.get(val, unknown_idx) for val in raw_vals], dtype=np.int64)
            categorical[:, i] = indices

        return ProcessedNNFeatures(
            continuous=continuous,
            categorical=categorical,
            continuous_feature_names=CONTINUOUS_FEATURE_NAMES,
            categorical_feature_names=CATEGORICAL_EMBEDDING_COLUMNS,
            vocabulary_sizes=dict(self.vocabulary_sizes_),
            unknown_indices=dict(self.unknown_indices_),
        )
