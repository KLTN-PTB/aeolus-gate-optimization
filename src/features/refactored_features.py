"""Refactored, leakage-safe Arrival feature preparation (Protocol V2).

Key improvements over V1:
1. Eliminates `calendar_year` from predictors to eliminate Covariate Shift (PSI 8.75 -> 0).
2. Introduces safe chain feature representations (has_prior_flight, missing indicator).
3. Preserves all temporal bounds, access guards, and fail-closed validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
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
    RAW_SAFE_SOURCE_COLUMNS_V1_1,
    SCHEDULED_ARRIVAL_FEATURE_COLUMNS,
    _categorical,
    _flight_number,
    _numeric_without_silent_coercion,
    _parse_scheduled_arrival_clock,
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
    *SCHEDULED_ARRIVAL_FEATURE_COLUMNS,
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

LOGGER = logging.getLogger(__name__)


def compute_carrier_arrhour_median(
    train_df: pd.DataFrame,
    apply_df: pd.DataFrame,
    k: int = 30,
    smoothing: bool = True,
) -> tuple[pd.Series, pd.Series]:
    """Compute train-side carrier/arrival-hour target encoding.

    The mapping is built exclusively from ``train_df`` and applied to
    ``apply_df``.  ``apply_df`` labels, when present, are deliberately ignored.
    Fallbacks are exact cell -> carrier -> global median.  Smoothing applies
    only to an observed cell and follows the locked weighted-median formula
    used by the Day 1 design note.
    """
    if not isinstance(train_df, pd.DataFrame) or not isinstance(apply_df, pd.DataFrame):
        raise TypeError("train_df and apply_df must be pandas DataFrames")
    if k < 0:
        raise ValueError("k must be non-negative")
    required = {"OP_CARRIER", "scheduled_arrival_hour"}
    missing_train = required.difference(train_df.columns)
    missing_apply = required.difference(apply_df.columns)
    if missing_train or missing_apply:
        raise KeyError(
            "target encoding requires safe keys; "
            f"missing_train={sorted(missing_train)} missing_apply={sorted(missing_apply)}"
        )

    target_column = next(
        (name for name in ("y_arr_reg", "ARR_DELAY") if name in train_df.columns),
        None,
    )
    if target_column is None:
        raise KeyError("train_df must contain y_arr_reg or ARR_DELAY")

    train_carrier = train_df["OP_CARRIER"].astype("string")
    train_hour = pd.to_numeric(train_df["scheduled_arrival_hour"], errors="coerce")
    train_target = pd.to_numeric(train_df[target_column], errors="coerce")
    valid_train = (
        train_carrier.notna()
        & train_hour.notna()
        & np.isfinite(train_hour)
        & (train_hour == np.floor(train_hour))
        & train_target.notna()
        & np.isfinite(train_target)
    )
    if not bool(valid_train.any()):
        raise ValueError("train_df has no finite rows for carrier/hour target encoding")

    train_keys = pd.DataFrame(
        {
            "carrier": train_carrier.loc[valid_train].astype(str),
            "hour": train_hour.loc[valid_train].astype(int),
            "target": train_target.loc[valid_train].astype(float),
        }
    )
    cell_group = train_keys.groupby(["carrier", "hour"])["target"]
    cell_medians = cell_group.median().to_dict()
    cell_counts = cell_group.size().to_dict()
    carrier_medians = train_keys.groupby("carrier")["target"].median().to_dict()
    global_median = float(train_keys["target"].median())

    apply_carrier = apply_df["OP_CARRIER"].astype("string")
    apply_hour = pd.to_numeric(apply_df["scheduled_arrival_hour"], errors="coerce")
    values = np.empty(len(apply_df), dtype=np.float64)
    counts = np.zeros(len(apply_df), dtype=np.int64)
    level_counts = {"cell": 0, "carrier": 0, "global": 0}

    for position, (carrier_value, hour_value) in enumerate(
        zip(apply_carrier.tolist(), apply_hour.tolist())
    ):
        if pd.notna(carrier_value) and pd.notna(hour_value) and np.isfinite(hour_value):
            carrier_key = str(carrier_value)
            hour_key = int(hour_value)
            cell_key = (carrier_key, hour_key)
        else:
            carrier_key = None
            cell_key = None

        if cell_key is not None and cell_key in cell_medians:
            cell_median = float(cell_medians[cell_key])
            cell_count = int(cell_counts[cell_key])
            counts[position] = cell_count
            level_counts["cell"] += 1
            if smoothing and carrier_key is not None and k > 0:
                carrier_median = float(carrier_medians[carrier_key])
                values[position] = (
                    cell_count * cell_median + k * carrier_median
                ) / (cell_count + k)
            else:
                values[position] = cell_median
        elif carrier_key is not None and carrier_key in carrier_medians:
            values[position] = float(carrier_medians[carrier_key])
            level_counts["carrier"] += 1
        else:
            values[position] = global_median
            level_counts["global"] += 1

    result_values = pd.Series(
        values, index=apply_df.index, name="carrier_arrhour_train_median"
    )
    result_counts = pd.Series(
        counts, index=apply_df.index, name="carrier_arrhour_train_count", dtype="int64"
    )
    if result_values.isna().any() or result_counts.isna().any():
        raise ValueError("target encoding produced NaN values after fallback")
    LOGGER.info(
        "carrier_arrhour_train_median fallback counts: cell=%d carrier=%d global=%d",
        level_counts["cell"],
        level_counts["carrier"],
        level_counts["global"],
    )
    return result_values, result_counts


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
    required = set(RAW_SAFE_SOURCE_COLUMNS_V1_1) | {"DEST", "ARR_DELAY"}
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
    arrival_hour, arrival_minute = _parse_scheduled_arrival_clock(eligible)
    X["scheduled_arrival_hour"] = arrival_hour
    X["scheduled_arrival_minute"] = arrival_minute
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
