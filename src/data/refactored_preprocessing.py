"""Refactored transformer builders for Protocol V2 (No calendar_year)."""

from __future__ import annotations

from typing import Final
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src.data.preprocessing import (
    FrequencyEncoder,
    MISSING_SENTINEL,
    _numeric_pipeline,
    _categorical_pipeline,
    _high_cardinality_pipeline,
)
from src.features.refactored_features import (
    APPROVED_PREDICTOR_COLUMNS_V2,
    NUMERIC_FEATURE_COLUMNS_V2,
    PREPROCESSING_VERSION_V2,
)
from src.features.tabular_features import (
    CATEGORICAL_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
)


def build_refactored_linear_preprocessor() -> ColumnTransformer:
    """Build Logistic/Huber linear preprocessing without calendar_year."""
    return ColumnTransformer(
        [
            ("numeric", _numeric_pipeline(scale=True), list(NUMERIC_FEATURE_COLUMNS_V2)),
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


def build_refactored_tree_preprocessor() -> ColumnTransformer:
    """Build dense preprocessing for RF/HGB/XGBoost without calendar_year."""
    return ColumnTransformer(
        [
            ("numeric", _numeric_pipeline(scale=False), list(NUMERIC_FEATURE_COLUMNS_V2)),
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


def build_refactored_boosting_preprocessor() -> ColumnTransformer:
    """Alias for boosting preprocessor."""
    return build_refactored_tree_preprocessor()
