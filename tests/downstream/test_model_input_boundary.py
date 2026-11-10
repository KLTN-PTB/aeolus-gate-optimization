"""Tests for downstream candidate input boundary and leakage prevention (Phase 8)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.evaluation.downstream_comparison import (
    FORBIDDEN_DEPARTURE_TERMS,
    validate_downstream_input_boundary,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS


def test_approved_predictors_pass_validation() -> None:
    """Approved predictor columns must pass downstream input boundary check cleanly."""
    valid_cols = list(APPROVED_PREDICTOR_COLUMNS)
    validate_downstream_input_boundary(valid_cols)

    df_valid = pd.DataFrame(columns=valid_cols)
    validate_downstream_input_boundary(df_valid)


def test_weather_columns_strictly_rejected() -> None:
    """Weather columns must fail closed when passed to downstream comparison."""
    for col in WEATHER_COLUMNS:
        with pytest.raises(ValueError, match="Weather features forbidden"):
            validate_downstream_input_boundary([col])

    # In combination with approved columns
    mixed = list(APPROVED_PREDICTOR_COLUMNS) + ["HourlyPrecipitation"]
    with pytest.raises(ValueError, match="Weather features forbidden"):
        validate_downstream_input_boundary(mixed)


def test_arrival_leakage_columns_strictly_rejected() -> None:
    """Arrival leakage columns must fail closed when passed to downstream comparison."""
    for col in ARRIVAL_LEAKAGE_COLUMNS:
        with pytest.raises(
            ValueError,
            match=r"(Arrival leakage features forbidden|Departure delay / auxiliary field forbidden)",
        ):
            validate_downstream_input_boundary([col])

    # Operational actual outcomes
    for bad_col in ["ARR_TIME", "DEP_TIME", "ACTUAL_ELAPSED_TIME", "TAXI_IN", "TAXI_OUT"]:
        with pytest.raises(ValueError, match="Arrival leakage features forbidden"):
            validate_downstream_input_boundary([bad_col])


def test_departure_delay_and_targets_strictly_rejected() -> None:
    """Departure delay and auxiliary prediction targets must fail closed."""
    for term in FORBIDDEN_DEPARTURE_TERMS:
        with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
            validate_downstream_input_boundary([term])

    with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
        validate_downstream_input_boundary(["p_dep_delay"])

    with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
        validate_downstream_input_boundary(["DEP_DELAY"])

    with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
        validate_downstream_input_boundary(["y_dep_cls"])
