"""Refactored, leakage-safe Arrival feature preparation (Protocol V2).

Key improvements over V1:
1. Eliminates `calendar_year` from predictors to eliminate Covariate Shift (PSI 8.75 -> 0).
2. Introduces safe chain feature representations (has_prior_flight, missing indicator).
3. Preserves all temporal bounds, access guards, and fail-closed validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

import numpy as np
import pandas as pd

from src.data.leakage_rules import ARRIVAL_TASK, assert_candidate_predictors_allowed
from src.features.tabular_features import (
    ArrivalEligibilityReport,
    ArrivalFeatureContractViolation,
    CATEGORICAL_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    RAW_SAFE_SOURCE_COLUMNS,
    _categorical,
    _flight_number,
    _numeric_without_silent_coercion,
    _parse_schedule_sources,
    _validate_calendar_source,
    build_arrival_labels,
)

FEATURE_CONTRACT_VERSION_V2: Final = "arrival_feature_contract_v2"
PREPROCESSING_VERSION_V2: Final = "arrival_preprocessing_v2"

# V2 NUMERIC: Eliminates calendar_year to eradicate severe temporal covariate shift
NUMERIC_FEATURE_COLUMNS_V2: Final = (
    "CRS_ELAPSED_TIME",
    "calendar_month",
    "calendar_day_of_month",
    "calendar_day_of_week",
    "is_weekend",
    "scheduled_departure_hour",
    "scheduled_departure_minute",
)

APPROVED_PREDICTOR_COLUMNS_V2: Final = (
    *NUMERIC_FEATURE_COLUMNS_V2,
    *CATEGORICAL_FEATURE_COLUMNS,
    *HIGH_CARDINALITY_FEATURE_COLUMNS,
)

SAFE_CHAIN_FEATURE_COLUMNS: Final = (
    "has_prior_flight",
    "is_prior_delay_missing",
    "imputed_prior_arrival_delay",
    "turnaround_tight",
)


@dataclass(frozen=True)
class PreparedArrivalFeaturesV2:
    """Aligned Core Arrival information V2, labels, trace IDs, and cutoffs."""

    X: pd.DataFrame
    y_arr_cls: pd.Series
    y_arr_reg: pd.Series
    identifiers: pd.DataFrame
    prediction_cutoff: pd.Series
    eligibility: ArrivalEligibilityReport
    feature_contract_version: str = FEATURE_CONTRACT_VERSION_V2


def prepare_arrival_features_v2(
    frame: pd.DataFrame,
    *,
    chain_map: pd.DataFrame | None = None,
) -> PreparedArrivalFeaturesV2:
    """Prepare one bounded Core Arrival batch under Protocol V2.

    Drops `calendar_year` from predictors to prevent split-on-year overfitting.
    Optionally joins safe, auditable chain status without imputing 0 blindly.
    """
    required = set(RAW_SAFE_SOURCE_COLUMNS) | {"DEST", "ARR_DELAY"}
    missing = required.difference(frame.columns)
    if missing:
        raise ArrivalFeatureContractViolation(
            f"Core Arrival V2 input is missing required columns: {sorted(missing)}"
        )

    inbound_mask = frame["DEST"].astype("string").str.strip().eq("ATL").fillna(False)
    inbound = frame.loc[inbound_mask].copy(deep=True).reset_index(drop=True)
    labels, target_report = build_arrival_labels(inbound)
    eligible = inbound.loc[labels.index].copy(deep=True).reset_index(drop=True)
    labels = labels.reset_index(drop=True)

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
    ).astype("float32")
    
    # Note: calendar_year is excluded from X
    X["calendar_month"] = flight_date.dt.month.astype("int8")
    X["calendar_day_of_month"] = flight_date.dt.day.astype("int8")
    X["calendar_day_of_week"] = calendar_day_of_week.astype("int8")
    X["is_weekend"] = calendar_day_of_week.isin([6, 7]).astype("int8")
    X["scheduled_departure_hour"] = departure.dt.hour.astype("int8")
    X["scheduled_departure_minute"] = departure.dt.minute.astype("int8")
    X["OP_CARRIER"] = _categorical(eligible["OP_CARRIER"], field="OP_CARRIER")
    X["ORIGIN"] = _categorical(eligible["ORIGIN"], field="ORIGIN")
    X["OP_CARRIER_FL_NUM"] = _flight_number(eligible["OP_CARRIER_FL_NUM"])

    # Optional Safe Chain Integration
    if chain_map is not None and "flight_key" in eligible:
        merged = pd.merge(
            eligible[["flight_key"]],
            chain_map,
            left_on="flight_key",
            right_on="target_flight_key",
            how="left",
        )
        has_prior = (merged["chain_position"] > 0).astype("int8")
        X["has_prior_flight"] = has_prior.values
        X["is_prior_delay_missing"] = (merged["chain_position"] == 0).astype("int8").values
    else:
        # Default V2 base columns
        X = X.loc[:, list(APPROVED_PREDICTOR_COLUMNS_V2)]

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
    
    return PreparedArrivalFeaturesV2(
        X=X,
        y_arr_cls=labels["y_arr_cls"].copy(),
        y_arr_reg=labels["y_arr_reg"].copy(),
        identifiers=identifiers,
        prediction_cutoff=cutoff,
        eligibility=eligibility,
        feature_contract_version=FEATURE_CONTRACT_VERSION_V2,
    )
