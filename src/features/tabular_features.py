"""Leakage-safe, deterministic feature preparation for Core Arrival Week 3A.

The module constructs labels and the common raw information set only.  It does
not fit preprocessing state, read Parquet, derive reconstructed Chain features,
or train a predictive estimator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

import numpy as np
import pandas as pd

from src.data.leakage_rules import (
    ARRIVAL_TASK,
    TASK_COLUMN_STATUS,
    WEATHER_COLUMNS,
    assert_candidate_predictors_allowed,
)
from src.features.chain_feature_policy import assert_chain_features_ml_admissible


FEATURE_CONTRACT_VERSION: Final = "arrival_feature_contract_v1"
MISSING_POLICY_VERSION: Final = "arrival_missing_policy_v1"
CATEGORICAL_POLICY_VERSION: Final = "arrival_categorical_policy_v1"

KEEP_SAFE: Final = "KEEP_SAFE"
DROP_CONSTANT: Final = "DROP_CONSTANT"
DROP_LEAKAGE: Final = "DROP_LEAKAGE"
DROP_WEATHER: Final = "DROP_WEATHER"
DROP_IDENTIFIER: Final = "DROP_IDENTIFIER"
REVIEW_REQUIRED: Final = "REVIEW_REQUIRED"
UNKNOWN_BLOCKED: Final = "UNKNOWN_BLOCKED"
TARGET_ONLY: Final = "TARGET_ONLY"

IDENTIFIER_COLUMNS: Final = (
    "flight_key",
    "chain_id",
    "source_year",
    "source_row_number",
)

RAW_SAFE_SOURCE_COLUMNS: Final = (
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "ORIGIN",
    "CRS_DEP_TIME",
    "CRS_ELAPSED_TIME",
    "MONTH",
    "DAY_OF_MONTH",
    "DAY_OF_WEEK",
)

NUMERIC_FEATURE_COLUMNS: Final = (
    "CRS_ELAPSED_TIME",
    "calendar_year",
    "calendar_month",
    "calendar_day_of_month",
    "calendar_day_of_week",
    "is_weekend",
    "scheduled_departure_hour",
    "scheduled_departure_minute",
)
CATEGORICAL_FEATURE_COLUMNS: Final = ("OP_CARRIER", "ORIGIN")
HIGH_CARDINALITY_FEATURE_COLUMNS: Final = ("OP_CARRIER_FL_NUM",)
DERIVED_FEATURE_COLUMNS: Final = (
    "calendar_year",
    "calendar_month",
    "calendar_day_of_month",
    "calendar_day_of_week",
    "is_weekend",
    "scheduled_departure_hour",
    "scheduled_departure_minute",
)
APPROVED_PREDICTOR_COLUMNS: Final = (
    *NUMERIC_FEATURE_COLUMNS,
    *CATEGORICAL_FEATURE_COLUMNS,
    *HIGH_CARDINALITY_FEATURE_COLUMNS,
)

# Column projection for bounded development reads.  The projection omits every
# Weather, actual-operation, Chain, and auxiliary-Departure field.
ARRIVAL_PROJECTED_SOURCE_COLUMNS: Final = (
    *RAW_SAFE_SOURCE_COLUMNS,
    "DEST",
    "ARR_DELAY",
    "flight_key",
    "source_year",
    "source_row_number",
)


class ArrivalTargetError(ValueError):
    """Raised when the Core Arrival target cannot be constructed safely."""


class ArrivalFeatureContractViolation(ValueError):
    """Raised when raw columns or schedule representations fail closed."""


@dataclass(frozen=True)
class TargetEligibilityReport:
    """Auditable counts for target construction before feature preparation."""

    input_rows: int
    eligible_rows: int
    dropped_missing_target_rows: int
    target_imputation_used: bool = False


@dataclass(frozen=True)
class ArrivalEligibilityReport:
    """Auditable flow and target eligibility counts for one bounded batch."""

    input_rows: int
    inbound_rows: int
    eligible_rows: int
    dropped_non_inbound_rows: int
    dropped_missing_target_rows: int
    target_imputation_used: bool = False


@dataclass(frozen=True)
class PreparedArrivalFeatures:
    """Aligned Core Arrival information, labels, trace IDs, and cutoffs."""

    X: pd.DataFrame
    y_arr_cls: pd.Series
    y_arr_reg: pd.Series
    identifiers: pd.DataFrame
    prediction_cutoff: pd.Series
    eligibility: ArrivalEligibilityReport


def _numeric_without_silent_coercion(
    values: pd.Series, *, field: str, error_type: type[ValueError]
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & (numeric.isna() | ~np.isfinite(numeric))
    if bool(invalid.any()):
        examples = values.loc[invalid].head(3).tolist()
        raise error_type(f"invalid non-missing {field}: {examples}")
    return numeric.astype("float64")


def build_arrival_labels(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, TargetEligibilityReport]:
    """Build exact Arrival labels and explicitly drop missing targets.

    The returned label frame contains only rows with a finite ``ARR_DELAY``.
    Missing targets are never imputed or converted to the on-time class.
    """
    if "ARR_DELAY" not in frame:
        raise ArrivalTargetError("ARR_DELAY is required to construct Arrival labels")
    target = _numeric_without_silent_coercion(
        frame["ARR_DELAY"], field="ARR_DELAY", error_type=ArrivalTargetError
    )
    valid = target.notna()
    valid_target = target.loc[valid]
    labels = pd.DataFrame(index=valid_target.index)
    labels["y_arr_cls"] = (valid_target >= 15.0).astype("int8")
    labels["y_arr_reg"] = valid_target.astype("float64")
    report = TargetEligibilityReport(
        input_rows=len(frame),
        eligible_rows=int(valid.sum()),
        dropped_missing_target_rows=int((~valid).sum()),
    )
    return labels, report


def status_for_arrival_feature(column: str) -> str:
    """Return the Week 3A disposition for a raw column.

    Unknown columns return ``UNKNOWN_BLOCKED`` so callers can record the
    disposition, while preparation itself rejects them.
    """
    if column == "chain_id":
        return DROP_IDENTIFIER
    status = TASK_COLUMN_STATUS[ARRIVAL_TASK].get(column)
    if status is None:
        return UNKNOWN_BLOCKED
    if column == "CRS_ARR_TIME":
        # Scheduled arrival is known, but its stored date does not prove
        # rollover; Week 3A does not derive duration or overnight indicators.
        return REVIEW_REQUIRED
    if status == "SAFE":
        return KEEP_SAFE
    if status == "TARGET":
        return TARGET_ONLY
    if status == "LEAKAGE":
        return DROP_LEAKAGE
    if status == "INSUFFICIENT_EVIDENCE":
        return DROP_WEATHER
    if status == "IDENTIFIER_ONLY":
        return DROP_IDENTIFIER
    if status == "DROP_CONSTANT":
        return DROP_CONSTANT
    if status in {"UNCERTAIN", "CONDITIONAL"}:
        return REVIEW_REQUIRED
    return UNKNOWN_BLOCKED


def _validate_input_columns(
    columns: Iterable[str], *, declared_extra_features: set[str]
) -> None:
    unknown = {
        column
        for column in columns
        if status_for_arrival_feature(column) == UNKNOWN_BLOCKED
        and column not in declared_extra_features
    }
    if unknown:
        raise ArrivalFeatureContractViolation(
            f"Core Arrival input contains unknown/unclassified fields: {sorted(unknown)}"
        )


def _parse_schedule_sources(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    flight_date = pd.to_datetime(
        frame["FL_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    departure = pd.to_datetime(
        frame["CRS_DEP_TIME"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    invalid_date = frame["FL_DATE"].notna() & flight_date.isna()
    invalid_departure = frame["CRS_DEP_TIME"].notna() & departure.isna()
    if bool(invalid_date.any()) or bool(invalid_departure.any()):
        raise ArrivalFeatureContractViolation(
            "FL_DATE/CRS_DEP_TIME must use the audited canonical timestamp representation"
        )
    if bool(flight_date.isna().any()) or bool(departure.isna().any()):
        raise ArrivalFeatureContractViolation(
            "FL_DATE and CRS_DEP_TIME cannot be missing for Arrival feature construction"
        )
    if bool((flight_date.dt.normalize() != departure.dt.normalize()).any()):
        raise ArrivalFeatureContractViolation(
            "CRS_DEP_TIME date must match the canonical service date"
        )
    ambiguous_midnight = (
        (departure.dt.hour == 0)
        & (departure.dt.minute == 0)
        & (departure.dt.second == 0)
    )
    if bool(ambiguous_midnight.any()):
        raise ArrivalFeatureContractViolation(
            "exact-midnight CRS_DEP_TIME is blocked because original 0000/2400 semantics are not proven"
        )
    return flight_date, departure


def _validate_calendar_source(
    frame: pd.DataFrame, field: str, expected: pd.Series
) -> None:
    if field not in frame:
        raise ArrivalFeatureContractViolation(
            f"Required calendar source column is missing: {field}"
        )
    observed = _numeric_without_silent_coercion(
        frame[field], field=field, error_type=ArrivalFeatureContractViolation
    )
    mismatch = observed.notna() & (observed != expected.astype("float64"))
    if bool(mismatch.any()):
        raise ArrivalFeatureContractViolation(
            f"{field} conflicts with calendar values derived from FL_DATE"
        )


def _categorical(values: pd.Series, *, field: str) -> pd.Series:
    def normalize(value: object) -> object:
        if pd.isna(value):
            return np.nan
        if not isinstance(value, str):
            raise ArrivalFeatureContractViolation(
                f"{field} must contain strings or missing values"
            )
        stripped = value.strip()
        return stripped if stripped else np.nan

    return values.map(normalize)


def _flight_number(values: pd.Series) -> pd.Series:
    numeric = _numeric_without_silent_coercion(
        values,
        field="OP_CARRIER_FL_NUM",
        error_type=ArrivalFeatureContractViolation,
    )
    non_integral = numeric.notna() & (numeric != np.floor(numeric))
    if bool(non_integral.any()):
        raise ArrivalFeatureContractViolation(
            "OP_CARRIER_FL_NUM must be integral before categorical encoding"
        )
    return numeric.map(lambda value: np.nan if pd.isna(value) else str(int(value)))


def prepare_arrival_features(
    frame: pd.DataFrame,
    *,
    extra_approved_features: Iterable[str] | None = None,
) -> PreparedArrivalFeatures:
    """Prepare one bounded Core Arrival batch without fitting learned state.

    Extra Chain-derived fields default to none.  When explicitly supplied they
    must first pass the independent D026 availability gate; no join or Chain
    feature derivation is implemented here.
    """
    extras = tuple(extra_approved_features or ())
    extra_set = set(extras)
    _validate_input_columns(frame.columns, declared_extra_features=extra_set)
    if extras:
        assert_chain_features_ml_admissible(extras)
        # Necessary second gate.  It currently fails closed until a future
        # registry-first Arrival leakage classification is added.
        assert_candidate_predictors_allowed(extras, task=ARRIVAL_TASK)

    required = set(RAW_SAFE_SOURCE_COLUMNS) | {"DEST", "ARR_DELAY"}
    missing = required.difference(frame.columns)
    if missing:
        raise ArrivalFeatureContractViolation(
            f"Core Arrival input is missing required columns: {sorted(missing)}"
        )

    inbound_mask = frame["DEST"].astype("string").str.strip().eq("ATL").fillna(False)
    # Reset labels before any target selection.  Label-based selection on an
    # arbitrary caller index can multiply rows when index labels are duplicated.
    # Trace identity remains in the explicit identifier columns.
    inbound = frame.loc[inbound_mask].copy(deep=True).reset_index(drop=True)
    labels, target_report = build_arrival_labels(inbound)
    eligible = inbound.loc[labels.index].copy(deep=True).reset_index(drop=True)
    labels = labels.reset_index(drop=True)

    # Confirm that every raw information source entering feature derivation is
    # independently allowed by the normal Arrival leakage contract.
    assert_candidate_predictors_allowed(RAW_SAFE_SOURCE_COLUMNS, task=ARRIVAL_TASK)

    flight_date, departure = _parse_schedule_sources(eligible)
    calendar_day_of_week = flight_date.dt.dayofweek + 1
    _validate_calendar_source(eligible, "MONTH", flight_date.dt.month)
    _validate_calendar_source(eligible, "DAY_OF_MONTH", flight_date.dt.day)
    _validate_calendar_source(eligible, "DAY_OF_WEEK", calendar_day_of_week)

    X = pd.DataFrame(index=eligible.index)
    X["CRS_ELAPSED_TIME"] = _numeric_without_silent_coercion(
        eligible["CRS_ELAPSED_TIME"],
        field="CRS_ELAPSED_TIME",
        error_type=ArrivalFeatureContractViolation,
    )
    X["calendar_year"] = flight_date.dt.year.astype("int64")
    X["calendar_month"] = flight_date.dt.month.astype("int64")
    X["calendar_day_of_month"] = flight_date.dt.day.astype("int64")
    X["calendar_day_of_week"] = calendar_day_of_week.astype("int64")
    X["is_weekend"] = calendar_day_of_week.isin([6, 7]).astype("int8")
    X["scheduled_departure_hour"] = departure.dt.hour.astype("int64")
    X["scheduled_departure_minute"] = departure.dt.minute.astype("int64")
    X["OP_CARRIER"] = _categorical(eligible["OP_CARRIER"], field="OP_CARRIER")
    X["ORIGIN"] = _categorical(eligible["ORIGIN"], field="ORIGIN")
    X["OP_CARRIER_FL_NUM"] = _flight_number(eligible["OP_CARRIER_FL_NUM"])
    X = X.loc[:, list(APPROVED_PREDICTOR_COLUMNS)]

    identifier_names = [name for name in IDENTIFIER_COLUMNS if name in eligible]
    identifiers = eligible.loc[:, identifier_names].copy(deep=True)
    cutoff = (departure - pd.Timedelta(hours=2)).rename("prediction_cutoff")
    eligibility = ArrivalEligibilityReport(
        input_rows=len(frame),
        inbound_rows=len(inbound),
        eligible_rows=len(eligible),
        dropped_non_inbound_rows=len(frame) - len(inbound),
        dropped_missing_target_rows=target_report.dropped_missing_target_rows,
    )
    return PreparedArrivalFeatures(
        X=X,
        y_arr_cls=labels["y_arr_cls"].copy(),
        y_arr_reg=labels["y_arr_reg"].copy(),
        identifiers=identifiers,
        prediction_cutoff=cutoff,
        eligibility=eligibility,
    )


assert not set(APPROVED_PREDICTOR_COLUMNS).intersection(WEATHER_COLUMNS)
