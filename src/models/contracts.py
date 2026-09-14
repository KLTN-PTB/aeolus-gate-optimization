"""Locked Week-4 contracts for Core Arrival rolling experiments.

This module contains no estimator implementation and never opens a data
partition.  It validates the already locked temporal/feature contracts before
the rolling runner receives fold data from a later, bounded IO adapter.
"""

from __future__ import annotations

import json
from hashlib import blake2b
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Mapping

import numpy as np
import pandas as pd

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import load_base_config, resolve_project_root
from src.data.preprocessing import PREPROCESSING_VERSION
from src.data.temporal_protocol import (
    FINAL_HOLDOUT_YEAR,
    MODEL_SELECTION_YEAR,
    ROLLING_DEVELOPMENT_YEARS,
)
from src.features.tabular_features import (
    APPROVED_PREDICTOR_COLUMNS,
    PreparedArrivalFeatures,
)


WEEK4_FRAMEWORK_VERSION: Final = "week4_training_evaluation_v1"
WEEK4_EXPERIMENT_CONTRACT_VERSION: Final = "arrival_week4_experiment_v1"
OOF_SCHEMA_VERSION: Final = "arrival_oof_prediction_v1"
FEATURE_MANIFEST_VERSION: Final = "feature_manifest_arrival_v1"
CLASSIFICATION_THRESHOLD: Final = 0.5

Week4Method = Literal["linear", "random_forest", "hist_gradient_boosting"]
ModelFamily = Literal["linear", "tree", "boosting"]

METHOD_MODEL_FAMILY: Final[dict[Week4Method, ModelFamily]] = {
    "linear": "linear",
    "random_forest": "tree",
    "hist_gradient_boosting": "boosting",
}


class Week4ContractViolation(ValueError):
    """Raised when a Week-4 experiment would violate a locked contract."""


@dataclass(frozen=True)
class RollingFold:
    """One manifest-backed expanding-window train/validation partition."""

    fold_id: str
    train_years: tuple[int, ...]
    validation_year: int


@dataclass(frozen=True)
class ExperimentSpec:
    """Versioned, estimator-agnostic metadata for one Week-4 method run."""

    method_id: Week4Method
    model_version: str
    config_version: str
    seed: int
    feature_manifest_version: str = FEATURE_MANIFEST_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION
    experiment_contract_version: str = WEEK4_EXPERIMENT_CONTRACT_VERSION
    classification_threshold: float = CLASSIFICATION_THRESHOLD
    expected_validation_row_fingerprints: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.method_id not in METHOD_MODEL_FAMILY:
            raise Week4ContractViolation(f"Week 4 does not permit method {self.method_id!r}")
        if not self.model_version:
            raise Week4ContractViolation("model_version must be non-empty")
        if not self.config_version:
            raise Week4ContractViolation("config_version must be non-empty")
        if self.feature_manifest_version != FEATURE_MANIFEST_VERSION:
            raise Week4ContractViolation("unexpected Arrival feature manifest version")
        if self.preprocessing_version != PREPROCESSING_VERSION:
            raise Week4ContractViolation("unexpected Arrival preprocessing version")
        if self.experiment_contract_version != WEEK4_EXPERIMENT_CONTRACT_VERSION:
            raise Week4ContractViolation("unexpected Week-4 experiment contract version")
        if self.classification_threshold != CLASSIFICATION_THRESHOLD:
            raise Week4ContractViolation(
                "Week 4 Recall/F1 threshold is locked at 0.5 and may not be optimized"
            )
        if self.expected_validation_row_fingerprints is not None and any(
            not fold_id or not fingerprint
            for fold_id, fingerprint in self.expected_validation_row_fingerprints.items()
        ):
            raise Week4ContractViolation("expected validation row fingerprints must be non-empty")

    @property
    def model_family(self) -> ModelFamily:
        return METHOD_MODEL_FAMILY[self.method_id]


@dataclass(frozen=True)
class FoldData:
    """Prepared train/validation data supplied by a bounded external loader.

    The framework deliberately has no multi-year loading API: an implementation
    must supply one fold at a time and must not silently sample or concatenate
    all development years in this layer.
    """

    train: PreparedArrivalFeatures
    validation: PreparedArrivalFeatures


def load_week4_rolling_folds(
    *, project_root: Path | None = None
) -> tuple[RollingFold, ...]:
    """Load and cross-check the existing config and temporal-fold manifest."""

    root = resolve_project_root(project_root)
    config = load_base_config(project_root=root)
    configured = config.get("temporal", {}).get("rolling_folds", {}).get("folds")
    if not isinstance(configured, list):
        raise Week4ContractViolation("base config lacks rolling fold definitions")

    manifest_path = root / "artifacts" / "manifests" / "temporal_folds_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week4ContractViolation("temporal folds manifest is unreadable") from error
    if manifest.get("random_split_allowed") is not False:
        raise Week4ContractViolation("temporal manifest must prohibit random split")
    observed = manifest.get("rolling_folds")
    if not isinstance(observed, list):
        raise Week4ContractViolation("temporal manifest lacks rolling folds")

    expected_shape = [
        {
            "id": item.get("id"),
            "train_years": item.get("train_years"),
            "validation_year": item.get("validation_year"),
        }
        for item in configured
        if isinstance(item, dict)
    ]
    observed_shape = [
        {
            "id": item.get("id"),
            "train_years": item.get("train_years"),
            "validation_year": item.get("validation_year"),
        }
        for item in observed
        if isinstance(item, dict)
    ]
    if expected_shape != observed_shape or len(expected_shape) != len(configured):
        raise Week4ContractViolation("base config and temporal-fold manifest disagree")

    folds: list[RollingFold] = []
    for item in expected_shape:
        fold_id = item["id"]
        years = item["train_years"]
        validation_year = item["validation_year"]
        if (
            not isinstance(fold_id, str)
            or not isinstance(years, list)
            or not all(isinstance(year, int) for year in years)
            or not isinstance(validation_year, int)
        ):
            raise Week4ContractViolation("malformed rolling fold definition")
        if (
            not years
            or validation_year in years
            or validation_year <= max(years)
            or set([*years, validation_year]).difference(ROLLING_DEVELOPMENT_YEARS)
        ):
            raise Week4ContractViolation(f"fold {fold_id} is outside the 2016-2022 protocol")
        # The guard is checked before a later loader can open any partition.
        for year in [*years, validation_year]:
            assert_data_access_allowed(year, "development")
        folds.append(RollingFold(fold_id, tuple(years), validation_year))

    if not folds:
        raise Week4ContractViolation("at least one rolling fold is required")
    return tuple(folds)


def validate_fold_data(fold: RollingFold, data: FoldData) -> None:
    """Fail closed on temporal, label, feature and trace-identity boundaries."""

    _validate_prepared_partition(
        data.train,
        expected_years=set(fold.train_years),
        partition_name=f"{fold.fold_id} train",
    )
    _validate_prepared_partition(
        data.validation,
        expected_years={fold.validation_year},
        partition_name=f"{fold.fold_id} validation",
    )
    train_keys = set(data.train.identifiers["flight_key"].astype(str))
    validation_keys = set(data.validation.identifiers["flight_key"].astype(str))
    if train_keys.intersection(validation_keys):
        raise Week4ContractViolation(f"{fold.fold_id} has overlapping train/validation flight keys")


def prepared_row_fingerprint(prepared: PreparedArrivalFeatures) -> str:
    """Hash trace identity plus both labels, independent of input row ordering.

    The fingerprint intentionally excludes predictions and learned state.  It is
    persisted per fold so later Week-4 methods can prove they used identical
    target rows without loading a prior method's OOF Parquet into memory.
    """

    trace = pd.DataFrame(
        {
            "flight_key": prepared.identifiers["flight_key"].astype(str),
            "source_year": prepared.identifiers["source_year"].astype("int64"),
            "y_arr_cls": prepared.y_arr_cls.astype("int8"),
            "y_arr_reg": prepared.y_arr_reg.astype("float64"),
        }
    ).sort_values(["source_year", "flight_key"], kind="mergesort")
    row_hashes = pd.util.hash_pandas_object(trace, index=False, categorize=True)
    digest = blake2b(digest_size=16)
    digest.update(np.asarray(row_hashes, dtype="uint64").tobytes())
    return digest.hexdigest()


def _validate_prepared_partition(
    prepared: PreparedArrivalFeatures,
    *,
    expected_years: set[int],
    partition_name: str,
) -> None:
    if tuple(prepared.X.columns) != APPROVED_PREDICTOR_COLUMNS:
        raise Week4ContractViolation(
            f"{partition_name} predictor columns differ from the approved Arrival contract"
        )
    forbidden_names = {
        "DEP_DELAY",
        "y_dep_cls",
        "p_dep_delay",
        "chain_id",
        "flight_key",
        "source_year",
        "source_row_number",
        "DEP_TIME",
        "TAXI_OUT",
        "WHEELS_OFF",
        "WHEELS_ON",
        "TAXI_IN",
        "ARR_TIME",
        "ACTUAL_ELAPSED_TIME",
        "AIR_TIME",
        "O_TEMP",
        "O_PRCP",
        "O_WSPD",
        "D_TEMP",
        "D_PRCP",
        "D_WSPD",
    }
    if set(prepared.X.columns).intersection(forbidden_names):
        raise Week4ContractViolation(f"{partition_name} includes a forbidden predictor")
    if set(prepared.identifiers.columns) < {"flight_key", "source_year"}:
        raise Week4ContractViolation(f"{partition_name} lacks required trace identifiers")
    if not (
        prepared.X.index.equals(prepared.y_arr_cls.index)
        and prepared.X.index.equals(prepared.y_arr_reg.index)
        and prepared.X.index.equals(prepared.identifiers.index)
        and prepared.X.index.equals(prepared.prediction_cutoff.index)
    ):
        raise Week4ContractViolation(f"{partition_name} has misaligned features, targets, or trace IDs")
    if not prepared.identifiers["flight_key"].is_unique:
        raise Week4ContractViolation(f"{partition_name} flight_key must be unique")
    source_year = np.asarray(prepared.identifiers["source_year"], dtype=float)
    if not np.isfinite(source_year).all() or not np.equal(source_year, np.floor(source_year)).all():
        raise Week4ContractViolation(f"{partition_name} has invalid source_year provenance")
    observed_years = set(source_year.astype(int).tolist())
    if observed_years != expected_years:
        raise Week4ContractViolation(
            f"{partition_name} source years {sorted(observed_years)} != {sorted(expected_years)}"
        )
    if observed_years.intersection({MODEL_SELECTION_YEAR, FINAL_HOLDOUT_YEAR}):
        raise Week4ContractViolation(f"{partition_name} attempts to use 2023 or 2024")
    y_cls = np.asarray(prepared.y_arr_cls, dtype=int)
    y_reg = np.asarray(prepared.y_arr_reg, dtype=float)
    if not np.isfinite(y_reg).all() or not set(y_cls).issubset({0, 1}):
        raise Week4ContractViolation(f"{partition_name} targets are malformed")
    if not np.array_equal(y_cls, (y_reg >= 15.0).astype(int)):
        raise Week4ContractViolation(f"{partition_name} Arrival target definitions disagree")
