"""Fold-safe, reproducible preprocessing for Core Departure V1.

Protocol: Aeolus Dual Core Architecture Protocol V2
Task: ModelTask.CORE_DEPARTURE (ORIGIN=ATL, target signed DEP_DELAY)

This module provides training-fold-only transformers and preprocessing pipelines
for Core Departure models (linear and tree-based).
Invariants:
- Numeric imputation and scaling fit exclusively on the training fold.
- Categorical vocabularies fit exclusively on the training fold; unseen categories
  during validation/inference are safely zeroed out without data leakage.
- Flight number uses train-only frequency encoding.
- Strictly isolated from Core Arrival fitted state and transformers.
- Input columns must strictly match the 10 approved Core Departure features.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final, Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted

from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
)


DEPARTURE_PREPROCESSING_VERSION: Final = "departure_preprocessing_v1"
MISSING_SENTINEL: Final = "__MISSING__"
UNKNOWN_FREQUENCY: Final = 0.0

DEPARTURE_NUMERIC_FEATURES: Final = tuple(NUMERIC_FEATURE_COLUMNS)
DEPARTURE_CATEGORICAL_FEATURES: Final = tuple(CATEGORICAL_FEATURE_COLUMNS)
DEPARTURE_HIGH_CARDINALITY_FEATURES: Final = tuple(HIGH_CARDINALITY_FEATURE_COLUMNS)
DEPARTURE_APPROVED_PREDICTORS: Final = tuple(APPROVED_DEPARTURE_PREDICTOR_COLUMNS)


class DeparturePreprocessingError(ValueError):
    """Raised when data preprocessing violates the Core Departure contract."""


class DepartureFrequencyEncoder(BaseEstimator, TransformerMixin):
    """Deterministic, training-fitted frequency encoder for high-cardinality features.

    Validation-only categories map to zero. The transformer never consumes the
    target variable, eliminating target leakage.
    """

    def __init__(
        self,
        *,
        feature_names: Sequence[str] = DEPARTURE_HIGH_CARDINALITY_FEATURES,
        unknown_value: float = UNKNOWN_FREQUENCY,
    ) -> None:
        self.feature_names = tuple(feature_names)
        self.unknown_value = unknown_value

    def _array(self, X: object) -> np.ndarray:
        array = np.asarray(X, dtype=object)
        if array.ndim == 1:
            array = array.reshape(-1, 1)
        if array.ndim != 2 or array.shape[1] != len(self.feature_names):
            raise ValueError(
                f"DepartureFrequencyEncoder input width ({array.shape[1] if array.ndim == 2 else 0}) "
                f"does not match configured feature names ({len(self.feature_names)})"
            )
        return array

    def fit(self, X: object, y: object = None) -> "DepartureFrequencyEncoder":
        del y
        array = self._array(X)
        self.n_features_in_ = array.shape[1]
        self.feature_names_in_ = np.asarray(self.feature_names, dtype=object)
        self.frequency_maps_: dict[str, dict[str, float]] = {}
        denominator = len(array)
        if denominator == 0:
            raise DeparturePreprocessingError(
                "DepartureFrequencyEncoder cannot fit on an empty training fold"
            )
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
            handle_unknown="ignore", sparse_output=False, dtype=np.float64
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
                DepartureFrequencyEncoder(
                    feature_names=DEPARTURE_HIGH_CARDINALITY_FEATURES
                ),
            ),
        ]
    )


def build_departure_linear_preprocessor() -> ColumnTransformer:
    """Build Logistic/Ridge preprocessing; fit it exclusively on training fold rows."""
    return ColumnTransformer(
        [
            (
                "numeric",
                _numeric_pipeline(scale=True),
                list(DEPARTURE_NUMERIC_FEATURES),
            ),
            (
                "categorical",
                _categorical_pipeline(one_hot=True),
                list(DEPARTURE_CATEGORICAL_FEATURES),
            ),
            (
                "high_cardinality",
                _high_cardinality_pipeline(),
                list(DEPARTURE_HIGH_CARDINALITY_FEATURES),
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


def build_departure_tree_preprocessor() -> ColumnTransformer:
    """Build RF/HGB-style dense preprocessing; fit exclusively on training fold rows."""
    return ColumnTransformer(
        [
            (
                "numeric",
                _numeric_pipeline(scale=False),
                list(DEPARTURE_NUMERIC_FEATURES),
            ),
            (
                "categorical",
                _categorical_pipeline(one_hot=False),
                list(DEPARTURE_CATEGORICAL_FEATURES),
            ),
            (
                "high_cardinality",
                _high_cardinality_pipeline(),
                list(DEPARTURE_HIGH_CARDINALITY_FEATURES),
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


class DeparturePreprocessingPipeline:
    """Managed fold-safe preprocessor wrapping scikit-learn transformers with provenance tracking."""

    def __init__(self, *, preprocessor_type: str = "linear") -> None:
        if preprocessor_type not in {"linear", "tree"}:
            raise DeparturePreprocessingError(
                f"Unknown preprocessor_type '{preprocessor_type}'. Must be 'linear' or 'tree'."
            )
        self.preprocessor_type = preprocessor_type
        self.transformation_version = DEPARTURE_PREPROCESSING_VERSION
        self.transformer: ColumnTransformer = (
            build_departure_linear_preprocessor()
            if preprocessor_type == "linear"
            else build_departure_tree_preprocessor()
        )
        self.is_fitted: bool = False
        self.n_features_in_: int = len(DEPARTURE_APPROVED_PREDICTORS)
        self.feature_names_in_: tuple[str, ...] = DEPARTURE_APPROVED_PREDICTORS
        self.training_sample_count_: int = 0
        self.manifest_: dict[str, Any] = {}

    def _validate_input_schema(self, X: pd.DataFrame) -> None:
        if not isinstance(X, pd.DataFrame):
            raise DeparturePreprocessingError(f"Input X must be a pandas DataFrame, got {type(X)}")
        expected_cols = list(DEPARTURE_APPROVED_PREDICTORS)
        if list(X.columns) != expected_cols:
            missing = set(expected_cols) - set(X.columns)
            extra = set(X.columns) - set(expected_cols)
            msg = []
            if missing:
                msg.append(f"missing={sorted(missing)}")
            if extra:
                msg.append(f"extra_unapproved={sorted(extra)}")
            if not missing and not extra:
                msg.append(f"order mismatch: {list(X.columns)} != {expected_cols}")
            raise DeparturePreprocessingError(
                f"Input X violates Core Departure schema: {'; '.join(msg)}"
            )

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "DeparturePreprocessingPipeline":
        del y
        self._validate_input_schema(X)
        if len(X) == 0:
            raise DeparturePreprocessingError("Cannot fit DeparturePreprocessingPipeline on empty DataFrame")
        self.transformer.fit(X)
        self.is_fitted = True
        self.training_sample_count_ = len(X)
        self.manifest_ = self._generate_manifest(X)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise DeparturePreprocessingError("DeparturePreprocessingPipeline is not fitted")
        self._validate_input_schema(X)
        result = self.transformer.transform(X)
        return result.toarray() if hasattr(result, "toarray") else np.asarray(result, dtype=np.float64)

    def fit_transform(self, X: pd.DataFrame, y: pd.Series | None = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def get_feature_names_out(self) -> list[str]:
        if not self.is_fitted:
            raise DeparturePreprocessingError("DeparturePreprocessingPipeline is not fitted")
        return [str(name) for name in self.transformer.get_feature_names_out()]

    def _generate_manifest(self, X_train: pd.DataFrame) -> dict[str, Any]:
        """Extract fitted statistics and cryptographic hashes for auditable persistence."""
        num_imputer = self.transformer.named_transformers_["numeric"].named_steps["imputer"]
        cat_encoder = self.transformer.named_transformers_["categorical"].named_steps["encoder"]
        high_encoder = self.transformer.named_transformers_["high_cardinality"].named_steps["encoder"]

        # Numeric statistics
        medians = {
            col: float(num_imputer.statistics_[idx])
            for idx, col in enumerate(DEPARTURE_NUMERIC_FEATURES)
        }
        scales = {}
        means = {}
        if self.preprocessor_type == "linear":
            scaler = self.transformer.named_transformers_["numeric"].named_steps["scaler"]
            means = {
                col: float(scaler.mean_[idx])
                for idx, col in enumerate(DEPARTURE_NUMERIC_FEATURES)
            }
            scales = {
                col: float(scaler.scale_[idx])
                for idx, col in enumerate(DEPARTURE_NUMERIC_FEATURES)
            }

        # Categorical vocabularies
        cat_vocab = {}
        if hasattr(cat_encoder, "categories_"):
            for idx, col in enumerate(DEPARTURE_CATEGORICAL_FEATURES):
                cat_vocab[col] = [str(val) for val in cat_encoder.categories_[idx]]

        # Frequency mapping
        freq_maps = {
            col: dict(high_encoder.frequency_maps_[col])
            for col in DEPARTURE_HIGH_CARDINALITY_FEATURES
        }

        output_features = self.get_feature_names_out()

        content_for_hash = json.dumps(
            {
                "version": self.transformation_version,
                "type": self.preprocessor_type,
                "input_features": list(DEPARTURE_APPROVED_PREDICTORS),
                "output_features": output_features,
                "medians": medians,
                "means": means,
                "scales": scales,
                "vocab": cat_vocab,
                "frequency_maps": freq_maps,
            },
            sort_keys=True,
        )
        sha256_fingerprint = hashlib.sha256(content_for_hash.encode("utf-8")).hexdigest()

        return {
            "transformation_version": self.transformation_version,
            "preprocessor_type": self.preprocessor_type,
            "task": "core_departure",
            "hub": "ATL",
            "training_samples": self.training_sample_count_,
            "input_features": list(DEPARTURE_APPROVED_PREDICTORS),
            "output_features_count": len(output_features),
            "output_features": output_features,
            "numeric_imputation_strategy": "median_with_indicator",
            "numeric_medians": medians,
            "numeric_means": means,
            "numeric_scales": scales,
            "categorical_vocabularies": cat_vocab,
            "frequency_mappings": freq_maps,
            "sha256_fingerprint": sha256_fingerprint,
        }

    def export_manifest(self) -> dict[str, Any]:
        if not self.is_fitted:
            raise DeparturePreprocessingError("DeparturePreprocessingPipeline is not fitted")
        return dict(self.manifest_)

    def save_manifest(self, path: str | Path) -> None:
        manifest = self.export_manifest()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
