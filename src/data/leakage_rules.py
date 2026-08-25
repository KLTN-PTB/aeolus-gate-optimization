"""Explicit Week-2 prediction-time leakage rules for the T-2h contract.

This module classifies columns and rejects unsafe candidate predictors.  It
does not fit, transform, encode, impute, or otherwise preprocess data.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final


PREDICTION_CUTOFF_HOURS: Final = 2
REGRESSION_TARGET: Final = "ARR_DELAY"
CLASSIFICATION_TARGET: Final = "y_cls"
CLASSIFICATION_THRESHOLD_MINUTES: Final = 15

SAFE_COLUMNS: Final = frozenset(
    {
        "FL_DATE",
        "OP_CARRIER",
        "OP_CARRIER_FL_NUM",
        "ORIGIN",
        "CRS_DEP_TIME",
        "CRS_ARR_TIME",
        "CRS_ELAPSED_TIME",
        "MONTH",
        "DAY_OF_MONTH",
        "DAY_OF_WEEK",
    }
)

TARGET_COLUMNS: Final = frozenset({REGRESSION_TARGET, CLASSIFICATION_TARGET})

LEAKAGE_COLUMNS: Final = frozenset(
    {
        "DEP_TIME",
        "DEP_DELAY",
        "TAXI_OUT",
        "WHEELS_OFF",
        "WHEELS_ON",
        "TAXI_IN",
        "ARR_TIME",
        "ACTUAL_ELAPSED_TIME",
        "AIR_TIME",
    }
)

WEATHER_COLUMNS: Final = frozenset(
    {"O_TEMP", "O_PRCP", "O_WSPD", "D_TEMP", "D_PRCP", "D_WSPD"}
)
WEATHER_AUDIT_STATUS: Final = "INSUFFICIENT_EVIDENCE"
CORE_WEATHER_POLICY: Final = "DROP"
CORE_DROPPED_WEATHER_COLUMNS: Final = WEATHER_COLUMNS
UNCERTAIN_COLUMNS: Final = frozenset({"FLIGHTS"})

IDENTIFIER_ONLY_COLUMNS: Final = frozenset(
    {"flight_key", "source_row_number", "source_year"}
)

DROP_CONSTANT_INBOUND_ATL_COLUMNS: Final = frozenset(
    {"DEST", "DEST_INDEX", "D_LATITUDE", "D_LONGITUDE"}
)

CONDITIONAL_COLUMNS: Final = frozenset(
    {"ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}
)

FORBIDDEN_PREDICTOR_COLUMNS: Final = (
    TARGET_COLUMNS
    | LEAKAGE_COLUMNS
    | CORE_DROPPED_WEATHER_COLUMNS
    | UNCERTAIN_COLUMNS
    | IDENTIFIER_ONLY_COLUMNS
    | DROP_CONSTANT_INBOUND_ATL_COLUMNS
)

COLUMN_STATUS: Final = {
    **{column: "SAFE" for column in SAFE_COLUMNS},
    **{column: "TARGET" for column in TARGET_COLUMNS},
    **{column: "LEAKAGE" for column in LEAKAGE_COLUMNS},
    **{column: WEATHER_AUDIT_STATUS for column in WEATHER_COLUMNS},
    **{column: "UNCERTAIN" for column in UNCERTAIN_COLUMNS},
    **{column: "IDENTIFIER_ONLY" for column in IDENTIFIER_ONLY_COLUMNS},
    **{column: "DROP_CONSTANT" for column in DROP_CONSTANT_INBOUND_ATL_COLUMNS},
    **{column: "CONDITIONAL" for column in CONDITIONAL_COLUMNS},
}


class LeakageRuleViolation(ValueError):
    """Raised when a candidate predictor violates the Week-2 contract."""


def assert_candidate_predictors_allowed(
    columns: Iterable[str], *, allow_conditional: bool = False
) -> None:
    """Reject targets, leakage, unresolved, identifiers, and ATL constants.

    Conditional fields remain blocked by default.  A future Week-3 caller may
    opt in only after documenting the field-specific handling required by V1.
    """
    requested = set(columns)
    forbidden = requested & FORBIDDEN_PREDICTOR_COLUMNS
    conditional = requested & CONDITIONAL_COLUMNS
    unknown = requested - set(COLUMN_STATUS)
    problems: list[str] = []
    if forbidden:
        problems.append(f"forbidden={sorted(forbidden)}")
    if conditional and not allow_conditional:
        problems.append(f"conditional_requires_explicit_review={sorted(conditional)}")
    if unknown:
        problems.append(f"unclassified={sorted(unknown)}")
    if problems:
        raise LeakageRuleViolation("Candidate X violates T-2h rules: " + "; ".join(problems))


def status_for(column: str) -> str:
    """Return the audited status; fail closed for an unknown column."""
    try:
        return COLUMN_STATUS[column]
    except KeyError as error:
        raise LeakageRuleViolation(f"Column is not classified: {column}") from error
