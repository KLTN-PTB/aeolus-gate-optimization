"""Leakage-safe, deterministic feature preparation for Core Departure V1.

Protocol: Aeolus Dual Core Architecture
Task: ModelTask.CORE_DEPARTURE (ORIGIN=ATL, target signed DEP_DELAY at CRS_DEP_TIME - 2h)

This module provides two distinct entry points:
1. `prepare_departure_training`: constructs X, continuous/classification labels,
   identifiers, and cutoffs. Requires valid DEP_DELAY ground truth.
2. `prepare_departure_inference`: constructs X, identifiers, and cutoffs from
   schedule-only inputs. Strictly does NOT require or consume actual delay outcomes.

Enforces:
- Population boundary: ORIGIN == "ATL" (outbound ATL only).
- Exactly 10 approved V1 features (no calendar_year, weather, chain, or actual ops).
- Signed DEP_DELAY target preserved without clipping or imputation.
- Prediction cutoff at CRS_DEP_TIME - 2 hours in America/New_York local time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

import numpy as np
import pandas as pd

from src.data.leakage_rules import (
    CORE_DEPARTURE_APPROVED_FEATURES,
    CORE_DEPARTURE_TASK,
    TASK_COLUMN_STATUS,
    assert_candidate_predictors_allowed,
)


FEATURE_CONTRACT_VERSION: Final = "departure_feature_contract_v1"
MISSING_POLICY_VERSION: Final = "departure_missing_policy_v1"
CATEGORICAL_POLICY_VERSION: Final = "departure_categorical_policy_v1"
TIMEZONE_ATL: Final = "America/New_York"

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
    "DEST",
    "CRS_DEP_TIME",
    "CRS_ELAPSED_TIME",
    "MONTH",
    "DAY_OF_MONTH",
    "DAY_OF_WEEK",
)

# Exactly the 10 approved Core Departure V1 predictor columns
APPROVED_DEPARTURE_PREDICTOR_COLUMNS: Final = (
    "CRS_ELAPSED_TIME",
    "calendar_month",
    "calendar_day_of_month",
    "calendar_day_of_week",
    "is_weekend",
    "scheduled_departure_hour",
    "scheduled_departure_minute",
    "OP_CARRIER",
    "DEST",
    "OP_CARRIER_FL_NUM",
)

NUMERIC_FEATURE_COLUMNS: Final = (
    "CRS_ELAPSED_TIME",
    "calendar_month",
    "calendar_day_of_month",
    "calendar_day_of_week",
    "is_weekend",
    "scheduled_departure_hour",
    "scheduled_departure_minute",
)
CATEGORICAL_FEATURE_COLUMNS: Final = ("OP_CARRIER", "DEST")
HIGH_CARDINALITY_FEATURE_COLUMNS: Final = ("OP_CARRIER_FL_NUM",)


class DepartureTargetError(ValueError):
    """Raised when the Core Departure target cannot be constructed safely."""


class DepartureFeatureContractViolation(ValueError):
    """Raised when raw columns or schedule representations violate the Core Departure contract."""


@dataclass(frozen=True)
class TargetEligibilityReport:
    """Auditable counts for target construction before feature preparation."""

    input_rows: int
    eligible_rows: int
    dropped_missing_target_rows: int
    target_imputation_used: bool = False


@dataclass(frozen=True)
class DepartureEligibilityReport:
    """Auditable flow and target eligibility counts for one outbound batch."""

    input_rows: int
    outbound_rows: int
    eligible_rows: int
    dropped_non_outbound_rows: int
    dropped_missing_target_rows: int
    target_imputation_used: bool = False


@dataclass(frozen=True)
class PreparedDepartureFeatures:
    """Aligned Core Departure training matrix, labels, trace IDs, and cutoffs."""

    X: pd.DataFrame
    y_dep_reg: pd.Series
    y_dep_cls: pd.Series
    identifiers: pd.DataFrame
    prediction_cutoff: pd.Series
    eligibility: DepartureEligibilityReport


@dataclass(frozen=True)
class PreparedDepartureInferenceFeatures:
    """Aligned Core Departure predictor matrix, trace IDs, and cutoffs for inference."""

    X: pd.DataFrame
    identifiers: pd.DataFrame
    prediction_cutoff: pd.Series
    eligibility: DepartureEligibilityReport


def _numeric_without_silent_coercion(
    values: pd.Series, *, field: str, error_type: type[ValueError]
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & (numeric.isna() | ~np.isfinite(numeric))
    if bool(invalid.any()):
        examples = values.loc[invalid].head(3).tolist()
        raise error_type(f"invalid non-missing {field}: {examples}")
    return numeric.astype("float64")


def build_departure_labels(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, TargetEligibilityReport]:
    """Build exact Departure labels and explicitly drop missing targets.

    Signed DEP_DELAY (including negative values for early departures) is strictly
    preserved. Missing targets are dropped, never imputed or floored.
    """
    if "DEP_DELAY" not in frame:
        raise DepartureTargetError("DEP_DELAY is required to construct Departure labels")
    target = _numeric_without_silent_coercion(
        frame["DEP_DELAY"], field="DEP_DELAY", error_type=DepartureTargetError
    )
    valid = target.notna()
    valid_target = target.loc[valid]
    labels = pd.DataFrame(index=valid_target.index)
    labels["y_dep_reg"] = valid_target.astype("float64")
    labels["y_dep_cls"] = (valid_target >= 15.0).astype("int8")
    report = TargetEligibilityReport(
        input_rows=len(frame),
        eligible_rows=int(valid.sum()),
        dropped_missing_target_rows=int((~valid).sum()),
    )
    return labels, report


def status_for_departure_feature(column: str) -> str:
    """Return the Core Departure disposition for a column.

    Unknown columns return UNKNOWN_BLOCKED for fail-closed safety.
    """
    if column in {"flight_key", "chain_id", "source_year", "source_row_number"}:
        return DROP_IDENTIFIER
    status = TASK_COLUMN_STATUS[CORE_DEPARTURE_TASK].get(column)
    if status is None:
        return UNKNOWN_BLOCKED
    if status == "SAFE":
        return KEEP_SAFE
    if status == "TARGET":
        return TARGET_ONLY
    if status in {"LEAKAGE", "SIMULATION_LEAKAGE"}:
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


def _parse_schedule_sources(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Parse and validate canonical timestamp representations for FL_DATE and CRS_DEP_TIME.

    Operates in America/New_York (ATL local scheduled time).
    Enforces that flight date and scheduled departure date are aligned and
    detects invalid or out-of-range times.
    """
    flight_date = pd.to_datetime(
        frame["FL_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    if flight_date.isna().any():
        flight_date = pd.to_datetime(frame["FL_DATE"], errors="coerce")

    raw_dep = frame["CRS_DEP_TIME"]
    # Check if raw_dep is already datetime-like or string timestamp
    departure = pd.to_datetime(
        raw_dep, format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    if departure.isna().any():
        # Check numeric HHMM format (e.g. 1430, 830)
        numeric = pd.to_numeric(raw_dep, errors="coerce")
        numeric_valid = (
            numeric.notna()
            & np.isfinite(numeric)
            & (numeric >= 0)
            & (numeric <= 2400)
            & (numeric == np.floor(numeric))
            & ((numeric % 100) <= 59)
        )
        # Any non-missing that is neither valid timestamp nor valid HHMM is rejected
        invalid_numeric = raw_dep.notna() & departure.isna() & ~numeric_valid
        if bool(invalid_numeric.any()):
            examples = raw_dep.loc[invalid_numeric].head(3).tolist()
            raise DepartureFeatureContractViolation(
                f"invalid non-missing CRS_DEP_TIME value (out-of-range or malformed): {examples}"
            )

        if bool(numeric_valid.any()):
            hour_part = (numeric.loc[numeric_valid] // 100).astype(int)
            minute_part = (numeric.loc[numeric_valid] % 100).astype(int)
            # Handle 2400 (midnight roll to next day)
            rolled_mask = hour_part == 24
            hour_part.loc[rolled_mask] = 0
            base_date = flight_date.loc[numeric_valid].copy()
            if bool(rolled_mask.any()):
                base_date.loc[rolled_mask] = base_date.loc[rolled_mask] + pd.Timedelta(days=1)

            constructed = (
                base_date
                + pd.to_timedelta(hour_part, unit="h")
                + pd.to_timedelta(minute_part, unit="m")
            )
            departure = departure.fillna(constructed)
        else:
            departure = pd.to_datetime(raw_dep, errors="coerce")

    invalid_date = frame["FL_DATE"].notna() & flight_date.isna()
    invalid_departure = frame["CRS_DEP_TIME"].notna() & departure.isna()
    if bool(invalid_date.any()) or bool(invalid_departure.any()):
        raise DepartureFeatureContractViolation(
            "FL_DATE/CRS_DEP_TIME must use audited canonical timestamp representation"
        )
    if bool(flight_date.isna().any()) or bool(departure.isna().any()):
        raise DepartureFeatureContractViolation(
            "FL_DATE and CRS_DEP_TIME cannot be missing for Departure feature construction"
        )

    # Date relation validation: departure date must match flight service date
    date_mismatch = (flight_date.dt.normalize() != departure.dt.normalize()) & ~(
        (departure.dt.hour == 0) & (departure.dt.minute == 0) & (departure - flight_date == pd.Timedelta(days=1))
    )
    if bool(date_mismatch.any()):
        raise DepartureFeatureContractViolation(
            "CRS_DEP_TIME date must match the canonical service date FL_DATE"
        )

    return flight_date, departure


def _validate_calendar_source(
    frame: pd.DataFrame, field: str, expected: pd.Series
) -> None:
    if field not in frame:
        raise DepartureFeatureContractViolation(
            f"Required calendar source column is missing: {field}"
        )
    observed = _numeric_without_silent_coercion(
        frame[field], field=field, error_type=DepartureFeatureContractViolation
    )
    mismatch = observed.notna() & (observed != expected.astype("float64"))
    if bool(mismatch.any()):
        raise DepartureFeatureContractViolation(
            f"{field} conflicts with calendar values derived from FL_DATE"
        )


def _categorical(values: pd.Series, *, field: str) -> pd.Series:
    def normalize(value: object) -> object:
        if pd.isna(value):
            return np.nan
        if not isinstance(value, str):
            raise DepartureFeatureContractViolation(
                f"{field} must contain strings or missing values"
            )
        stripped = value.strip()
        return stripped if stripped else np.nan

    return values.map(normalize)


def _flight_number(values: pd.Series) -> pd.Series:
    numeric = _numeric_without_silent_coercion(
        values,
        field="OP_CARRIER_FL_NUM",
        error_type=DepartureFeatureContractViolation,
    )
    non_integral = numeric.notna() & (numeric != np.floor(numeric))
    if bool(non_integral.any()):
        raise DepartureFeatureContractViolation(
            "OP_CARRIER_FL_NUM must be integral before categorical encoding"
        )
    return numeric.map(lambda value: np.nan if pd.isna(value) else str(int(value)))


def _build_feature_matrix(
    eligible: pd.DataFrame, flight_date: pd.Series, departure: pd.Series
) -> pd.DataFrame:
    """Build the exactly 10 approved V1 features."""
    calendar_day_of_week = (flight_date.dt.dayofweek + 1).astype("int16")
    _validate_calendar_source(eligible, "MONTH", flight_date.dt.month)
    _validate_calendar_source(eligible, "DAY_OF_MONTH", flight_date.dt.day)
    _validate_calendar_source(eligible, "DAY_OF_WEEK", calendar_day_of_week)

    X = pd.DataFrame(index=eligible.index)
    X["CRS_ELAPSED_TIME"] = _numeric_without_silent_coercion(
        eligible["CRS_ELAPSED_TIME"],
        field="CRS_ELAPSED_TIME",
        error_type=DepartureFeatureContractViolation,
    )
    X["calendar_month"] = flight_date.dt.month.astype("int16")
    X["calendar_day_of_month"] = flight_date.dt.day.astype("int16")
    X["calendar_day_of_week"] = calendar_day_of_week
    X["is_weekend"] = calendar_day_of_week.isin([6, 7]).astype("int8")
    X["scheduled_departure_hour"] = departure.dt.hour.astype("int16")
    X["scheduled_departure_minute"] = departure.dt.minute.astype("int16")
    X["OP_CARRIER"] = _categorical(eligible["OP_CARRIER"], field="OP_CARRIER")
    X["DEST"] = _categorical(eligible["DEST"], field="DEST")
    X["OP_CARRIER_FL_NUM"] = _flight_number(eligible["OP_CARRIER_FL_NUM"])

    # Reorder exactly to approved 10 columns
    X = X.loc[:, list(APPROVED_DEPARTURE_PREDICTOR_COLUMNS)]

    # Strictly assert candidate predictors are allowed under Core Departure leakage rules
    assert_candidate_predictors_allowed(X.columns, task=CORE_DEPARTURE_TASK)
    return X


def prepare_departure_training(
    frame: pd.DataFrame,
) -> PreparedDepartureFeatures:
    """Prepare one bounded Core Departure training batch with targets and trace metadata.

    Enforces:
    1. Population boundary: ORIGIN == "ATL" (non-outbound rows filtered).
    2. Signed DEP_DELAY target: preserved without clipping or imputation.
    3. Exactly 10 approved V1 features: CRS_ELAPSED_TIME, calendar_month,
       calendar_day_of_month, calendar_day_of_week, is_weekend,
       scheduled_departure_hour, scheduled_departure_minute, OP_CARRIER,
       DEST, OP_CARRIER_FL_NUM.
    4. Prediction cutoff: CRS_DEP_TIME - 2 hours.
    5. Strict leakage verification: fails closed on unknown or forbidden columns.
    """
    if "ORIGIN" not in frame:
        raise DepartureFeatureContractViolation("ORIGIN is required for population validation")
    if "DEP_DELAY" not in frame:
        raise DepartureTargetError("DEP_DELAY is required to construct Core Departure targets")

    required_sources = set(RAW_SAFE_SOURCE_COLUMNS)
    missing = required_sources - set(frame.columns)
    if missing:
        raise DepartureFeatureContractViolation(
            f"Core Departure input is missing required source columns: {sorted(missing)}"
        )

    outbound_mask = frame["ORIGIN"].astype("string").str.strip().eq("ATL").fillna(False)
    dropped_non_outbound = int((~outbound_mask).sum())
    outbound = frame.loc[outbound_mask].copy(deep=True).reset_index(drop=True)

    labels, target_report = build_departure_labels(outbound)
    eligible = outbound.loc[labels.index].copy(deep=True).reset_index(drop=True)
    labels = labels.reset_index(drop=True)

    flight_date, departure = _parse_schedule_sources(eligible)
    X = _build_feature_matrix(eligible, flight_date, departure)

    prediction_cutoff = departure - pd.Timedelta(hours=2)

    identifiers = pd.DataFrame(index=eligible.index)
    for col in IDENTIFIER_COLUMNS:
        if col in eligible.columns:
            identifiers[col] = eligible[col].values

    eligibility = DepartureEligibilityReport(
        input_rows=len(frame),
        outbound_rows=len(outbound),
        eligible_rows=len(eligible),
        dropped_non_outbound_rows=dropped_non_outbound,
        dropped_missing_target_rows=target_report.dropped_missing_target_rows,
    )

    return PreparedDepartureFeatures(
        X=X,
        y_dep_reg=labels["y_dep_reg"],
        y_dep_cls=labels["y_dep_cls"],
        identifiers=identifiers,
        prediction_cutoff=prediction_cutoff,
        eligibility=eligibility,
    )


def prepare_departure_inference(
    frame: pd.DataFrame,
) -> PreparedDepartureInferenceFeatures:
    """Prepare schedule-only Core Departure predictor matrix for inference.

    Strictly does NOT require or consume actual delay outcomes (DEP_DELAY, ARR_DELAY,
    actual timestamps). Any outcome columns present in frame are ignored.
    """
    if "ORIGIN" not in frame:
        raise DepartureFeatureContractViolation("ORIGIN is required for population validation")

    required_sources = set(RAW_SAFE_SOURCE_COLUMNS)
    missing = required_sources - set(frame.columns)
    if missing:
        raise DepartureFeatureContractViolation(
            f"Core Departure input is missing required source columns: {sorted(missing)}"
        )

    outbound_mask = frame["ORIGIN"].astype("string").str.strip().eq("ATL").fillna(False)
    dropped_non_outbound = int((~outbound_mask).sum())
    eligible = frame.loc[outbound_mask].copy(deep=True).reset_index(drop=True)

    flight_date, departure = _parse_schedule_sources(eligible)
    X = _build_feature_matrix(eligible, flight_date, departure)

    prediction_cutoff = departure - pd.Timedelta(hours=2)

    identifiers = pd.DataFrame(index=eligible.index)
    for col in IDENTIFIER_COLUMNS:
        if col in eligible.columns:
            identifiers[col] = eligible[col].values

    eligibility = DepartureEligibilityReport(
        input_rows=len(frame),
        outbound_rows=len(eligible),
        eligible_rows=len(eligible),
        dropped_non_outbound_rows=dropped_non_outbound,
        dropped_missing_target_rows=0,
    )

    return PreparedDepartureInferenceFeatures(
        X=X,
        identifiers=identifiers,
        prediction_cutoff=prediction_cutoff,
        eligibility=eligibility,
    )


def prepare_core_departure_features(
    frame: pd.DataFrame,
) -> PreparedDepartureFeatures:
    """Backward-compatible alias for prepare_departure_training."""
    return prepare_departure_training(frame)
