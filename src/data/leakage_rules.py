"""Task-aware prediction-time leakage rules for the V4 T-2h contract.

The default task remains the core Arrival task for backward compatibility.
This module classifies columns and rejects unsafe candidate predictors; it
does not fit, transform, encode, impute, or otherwise preprocess data.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final


ARRIVAL_TASK: Final = "arrival_core"
DEPARTURE_TASK: Final = "departure_auxiliary"
SUPPORTED_TASKS: Final = frozenset({ARRIVAL_TASK, DEPARTURE_TASK})

PREDICTION_CUTOFF_HOURS: Final = 2
CLASSIFICATION_THRESHOLD_MINUTES: Final = 15

ARRIVAL_REGRESSION_TARGET: Final = "ARR_DELAY"
ARRIVAL_CLASSIFICATION_LABEL: Final = "y_arr_cls"
ARRIVAL_REGRESSION_LABEL: Final = "y_arr_reg"
DEPARTURE_CLASSIFICATION_TARGET: Final = "DEP_DELAY"
DEPARTURE_CLASSIFICATION_LABEL: Final = "y_dep_cls"

BASE_SCHEDULE_COLUMNS: Final = frozenset(
    {
        "FL_DATE",
        "OP_CARRIER",
        "OP_CARRIER_FL_NUM",
        "CRS_DEP_TIME",
        "CRS_ARR_TIME",
        "CRS_ELAPSED_TIME",
        "MONTH",
        "DAY_OF_MONTH",
        "DAY_OF_WEEK",
    }
)
ARRIVAL_SAFE_COLUMNS: Final = BASE_SCHEDULE_COLUMNS | {"ORIGIN"}
DEPARTURE_SAFE_COLUMNS: Final = BASE_SCHEDULE_COLUMNS | {"DEST"}

ARRIVAL_TARGET_COLUMNS: Final = frozenset(
    {
        ARRIVAL_REGRESSION_TARGET,
        ARRIVAL_CLASSIFICATION_LABEL,
        ARRIVAL_REGRESSION_LABEL,
    }
)
DEPARTURE_TARGET_COLUMNS: Final = frozenset(
    {DEPARTURE_CLASSIFICATION_TARGET, DEPARTURE_CLASSIFICATION_LABEL}
)

ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS: Final = frozenset(
    {
        "DEP_TIME",
        "TAXI_OUT",
        "WHEELS_OFF",
        "WHEELS_ON",
        "TAXI_IN",
        "ARR_TIME",
        "ACTUAL_ELAPSED_TIME",
        "AIR_TIME",
    }
)
ARRIVAL_LEAKAGE_COLUMNS: Final = (
    ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS | DEPARTURE_TARGET_COLUMNS
)
DEPARTURE_LEAKAGE_COLUMNS: Final = (
    ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS | ARRIVAL_TARGET_COLUMNS
)

WEATHER_COLUMNS: Final = frozenset(
    {"O_TEMP", "O_PRCP", "O_WSPD", "D_TEMP", "D_PRCP", "D_WSPD"}
)
AEOLUS_RAW_WEATHER_AUDIT_STATUS: Final = "INSUFFICIENT_EVIDENCE"
AEOLUS_RAW_WEATHER_POLICY: Final = "DROP"
POINT_IN_TIME_WEATHER_STATUS: Final = "AUDIT_REQUIRED"
POINT_IN_TIME_WEATHER_ENABLED: Final = False

UNCERTAIN_COLUMNS: Final = frozenset({"FLIGHTS"})
IDENTIFIER_ONLY_COLUMNS: Final = frozenset(
    {"flight_key", "source_row_number", "source_year"}
)

DROP_CONSTANT_INBOUND_ATL_COLUMNS: Final = frozenset(
    {"DEST", "DEST_INDEX", "D_LATITUDE", "D_LONGITUDE"}
)
DROP_CONSTANT_OUTBOUND_ATL_COLUMNS: Final = frozenset(
    {"ORIGIN", "ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}
)
ARRIVAL_CONDITIONAL_COLUMNS: Final = frozenset(
    {"ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}
)
DEPARTURE_CONDITIONAL_COLUMNS: Final = frozenset(
    {"DEST_INDEX", "D_LATITUDE", "D_LONGITUDE"}
)

TASK_SAFE_COLUMNS: Final = {
    ARRIVAL_TASK: ARRIVAL_SAFE_COLUMNS,
    DEPARTURE_TASK: DEPARTURE_SAFE_COLUMNS,
}
TASK_TARGET_COLUMNS: Final = {
    ARRIVAL_TASK: ARRIVAL_TARGET_COLUMNS,
    DEPARTURE_TASK: DEPARTURE_TARGET_COLUMNS,
}
TASK_LEAKAGE_COLUMNS: Final = {
    ARRIVAL_TASK: ARRIVAL_LEAKAGE_COLUMNS,
    DEPARTURE_TASK: DEPARTURE_LEAKAGE_COLUMNS,
}
TASK_DROP_CONSTANT_COLUMNS: Final = {
    ARRIVAL_TASK: DROP_CONSTANT_INBOUND_ATL_COLUMNS,
    DEPARTURE_TASK: DROP_CONSTANT_OUTBOUND_ATL_COLUMNS,
}
TASK_CONDITIONAL_COLUMNS: Final = {
    ARRIVAL_TASK: ARRIVAL_CONDITIONAL_COLUMNS,
    DEPARTURE_TASK: DEPARTURE_CONDITIONAL_COLUMNS,
}


def _column_status_for_task(task: str) -> dict[str, str]:
    return {
        **{column: "SAFE" for column in TASK_SAFE_COLUMNS[task]},
        **{column: "TARGET" for column in TASK_TARGET_COLUMNS[task]},
        **{column: "LEAKAGE" for column in TASK_LEAKAGE_COLUMNS[task]},
        **{
            column: AEOLUS_RAW_WEATHER_AUDIT_STATUS
            for column in WEATHER_COLUMNS
        },
        **{column: "UNCERTAIN" for column in UNCERTAIN_COLUMNS},
        **{column: "IDENTIFIER_ONLY" for column in IDENTIFIER_ONLY_COLUMNS},
        **{
            column: "DROP_CONSTANT"
            for column in TASK_DROP_CONSTANT_COLUMNS[task]
        },
        **{column: "CONDITIONAL" for column in TASK_CONDITIONAL_COLUMNS[task]},
    }


TASK_COLUMN_STATUS: Final = {
    task: _column_status_for_task(task) for task in SUPPORTED_TASKS
}
TASK_FORBIDDEN_PREDICTOR_COLUMNS: Final = {
    task: (
        TASK_TARGET_COLUMNS[task]
        | TASK_LEAKAGE_COLUMNS[task]
        | WEATHER_COLUMNS
        | UNCERTAIN_COLUMNS
        | IDENTIFIER_ONLY_COLUMNS
        | TASK_DROP_CONSTANT_COLUMNS[task]
    )
    for task in SUPPORTED_TASKS
}

# Backward-compatible Arrival aliases used by historical scripts and the
# reconstructed schedule-chain safety checks.  They do not approve raw Aeolus
# Weather or change any raw/reconstructed Chain semantics.
REGRESSION_TARGET: Final = ARRIVAL_REGRESSION_TARGET
CLASSIFICATION_TARGET: Final = ARRIVAL_CLASSIFICATION_LABEL
SAFE_COLUMNS: Final = ARRIVAL_SAFE_COLUMNS
TARGET_COLUMNS: Final = ARRIVAL_TARGET_COLUMNS | DEPARTURE_TARGET_COLUMNS
LEAKAGE_COLUMNS: Final = (
    ACTUAL_OPERATION_COLUMNS_EXCEPT_DELAY_TARGETS | {"DEP_DELAY"}
)
WEATHER_AUDIT_STATUS: Final = AEOLUS_RAW_WEATHER_AUDIT_STATUS
CORE_WEATHER_POLICY: Final = AEOLUS_RAW_WEATHER_POLICY
CORE_DROPPED_WEATHER_COLUMNS: Final = WEATHER_COLUMNS
CONDITIONAL_COLUMNS: Final = ARRIVAL_CONDITIONAL_COLUMNS
FORBIDDEN_PREDICTOR_COLUMNS: Final = TASK_FORBIDDEN_PREDICTOR_COLUMNS[
    ARRIVAL_TASK
]
COLUMN_STATUS: Final = TASK_COLUMN_STATUS[ARRIVAL_TASK]


class LeakageRuleViolation(ValueError):
    """Raised when a candidate predictor violates the V4 task contract."""


def _validate_task(task: str) -> None:
    if task not in SUPPORTED_TASKS:
        raise LeakageRuleViolation(
            f"Unknown prediction task: {task!r}; supported={sorted(SUPPORTED_TASKS)}"
        )


def assert_candidate_predictors_allowed(
    columns: Iterable[str],
    *,
    task: str = ARRIVAL_TASK,
    allow_conditional: bool = False,
) -> None:
    """Reject unsafe candidate predictors under the selected task contract.

    Conditional location fields remain blocked by default and require an
    explicit reviewed opt-in.  Unknown tasks, unknown columns, and future
    external Weather fields fail closed.
    """
    _validate_task(task)
    requested = set(columns)
    forbidden = requested & TASK_FORBIDDEN_PREDICTOR_COLUMNS[task]
    conditional = requested & TASK_CONDITIONAL_COLUMNS[task]
    unknown = requested - set(TASK_COLUMN_STATUS[task])
    problems: list[str] = []
    if forbidden:
        problems.append(f"forbidden={sorted(forbidden)}")
    if conditional and not allow_conditional:
        problems.append(
            f"conditional_requires_explicit_review={sorted(conditional)}"
        )
    if unknown:
        problems.append(f"unclassified={sorted(unknown)}")
    if problems:
        raise LeakageRuleViolation(
            f"Candidate X violates T-2h {task} rules: " + "; ".join(problems)
        )


def status_for(column: str, *, task: str = ARRIVAL_TASK) -> str:
    """Return a task-specific audited status and fail closed when unknown."""
    _validate_task(task)
    try:
        return TASK_COLUMN_STATUS[task][column]
    except KeyError as error:
        raise LeakageRuleViolation(
            f"Column is not classified for {task}: {column}"
        ) from error
