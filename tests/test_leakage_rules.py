from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.leakage_rules import (
    AEOLUS_RAW_WEATHER_AUDIT_STATUS,
    AEOLUS_RAW_WEATHER_POLICY,
    ARRIVAL_CLASSIFICATION_LABEL,
    ARRIVAL_REGRESSION_LABEL,
    ARRIVAL_REGRESSION_TARGET,
    ARRIVAL_TASK,
    CLASSIFICATION_THRESHOLD_MINUTES,
    CONDITIONAL_COLUMNS,
    CORE_DROPPED_WEATHER_COLUMNS,
    CORE_WEATHER_POLICY,
    DEPARTURE_CLASSIFICATION_LABEL,
    DEPARTURE_CLASSIFICATION_TARGET,
    DEPARTURE_TASK,
    LEAKAGE_COLUMNS,
    LeakageRuleViolation,
    POINT_IN_TIME_WEATHER_ENABLED,
    POINT_IN_TIME_WEATHER_STATUS,
    PREDICTION_CUTOFF_HOURS,
    SAFE_COLUMNS,
    TARGET_COLUMNS,
    WEATHER_COLUMNS,
    assert_candidate_predictors_allowed,
    status_for,
)


ACTUAL_FIELDS_EXCEPT_DELAYS = {
    "DEP_TIME",
    "TAXI_OUT",
    "WHEELS_OFF",
    "WHEELS_ON",
    "TAXI_IN",
    "ARR_TIME",
    "ACTUAL_ELAPSED_TIME",
    "AIR_TIME",
}


def test_locked_v4_prediction_constants_and_compatibility_aliases() -> None:
    assert PREDICTION_CUTOFF_HOURS == 2
    assert CLASSIFICATION_THRESHOLD_MINUTES == 15
    assert ARRIVAL_REGRESSION_TARGET == "ARR_DELAY"
    assert ARRIVAL_CLASSIFICATION_LABEL == "y_arr_cls"
    assert ARRIVAL_REGRESSION_LABEL == "y_arr_reg"
    assert DEPARTURE_CLASSIFICATION_TARGET == "DEP_DELAY"
    assert DEPARTURE_CLASSIFICATION_LABEL == "y_dep_cls"
    assert TARGET_COLUMNS == {
        "ARR_DELAY",
        "y_arr_cls",
        "y_arr_reg",
        "DEP_DELAY",
        "y_dep_cls",
    }
    assert LEAKAGE_COLUMNS == ACTUAL_FIELDS_EXCEPT_DELAYS | {"DEP_DELAY"}


@pytest.mark.parametrize("column", ["ARR_DELAY", "y_arr_cls", "y_arr_reg"])
def test_arrival_task_marks_only_arrival_outcomes_as_targets(column: str) -> None:
    assert status_for(column, task=ARRIVAL_TASK) == "TARGET"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=ARRIVAL_TASK)


@pytest.mark.parametrize("column", ["DEP_DELAY", "y_dep_cls"])
def test_arrival_task_rejects_departure_outcomes(column: str) -> None:
    assert status_for(column, task=ARRIVAL_TASK) == "LEAKAGE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=ARRIVAL_TASK)


@pytest.mark.parametrize("column", ["DEP_DELAY", "y_dep_cls"])
def test_departure_task_marks_only_departure_outcomes_as_targets(column: str) -> None:
    assert status_for(column, task=DEPARTURE_TASK) == "TARGET"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=DEPARTURE_TASK)


@pytest.mark.parametrize("column", ["ARR_DELAY", "y_arr_cls", "y_arr_reg"])
def test_departure_task_rejects_arrival_future_outcomes(column: str) -> None:
    assert status_for(column, task=DEPARTURE_TASK) == "LEAKAGE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=DEPARTURE_TASK)


@pytest.mark.parametrize("task", [ARRIVAL_TASK, DEPARTURE_TASK])
@pytest.mark.parametrize("column", sorted(ACTUAL_FIELDS_EXCEPT_DELAYS))
def test_both_tasks_reject_realized_operation_fields(task: str, column: str) -> None:
    assert status_for(column, task=task) == "LEAKAGE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=task)


@pytest.mark.parametrize("task", [ARRIVAL_TASK, DEPARTURE_TASK])
@pytest.mark.parametrize("column", sorted(WEATHER_COLUMNS))
def test_raw_aeolus_weather_fails_closed_for_both_tasks(
    task: str, column: str
) -> None:
    assert status_for(column, task=task) == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([column], task=task)


def test_weather_contract_keeps_raw_drop_and_external_weather_disabled() -> None:
    assert AEOLUS_RAW_WEATHER_AUDIT_STATUS == "INSUFFICIENT_EVIDENCE"
    assert AEOLUS_RAW_WEATHER_POLICY == "DROP"
    assert CORE_WEATHER_POLICY == AEOLUS_RAW_WEATHER_POLICY
    assert CORE_DROPPED_WEATHER_COLUMNS == WEATHER_COLUMNS
    assert POINT_IN_TIME_WEATHER_STATUS == "AUDIT_REQUIRED"
    assert POINT_IN_TIME_WEATHER_ENABLED is False


def test_weather_policy_covers_exact_canonical_weather_role() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "artifacts/manifests/canonical_schema_v1.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_weather = {
        name
        for name, metadata in schema["fields"].items()
        if metadata["schema_role"] == "weather"
    }
    assert WEATHER_COLUMNS == canonical_weather


def test_arrival_constants_and_departure_constants_are_task_specific() -> None:
    for column in {"DEST", "DEST_INDEX", "D_LATITUDE", "D_LONGITUDE"}:
        assert status_for(column, task=ARRIVAL_TASK) == "DROP_CONSTANT"
        with pytest.raises(LeakageRuleViolation, match="forbidden"):
            assert_candidate_predictors_allowed([column], task=ARRIVAL_TASK)

    for column in {"ORIGIN", "ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}:
        assert status_for(column, task=DEPARTURE_TASK) == "DROP_CONSTANT"
        with pytest.raises(LeakageRuleViolation, match="forbidden"):
            assert_candidate_predictors_allowed([column], task=DEPARTURE_TASK)


def test_safe_schedule_sets_are_task_specific_and_allowed() -> None:
    assert_candidate_predictors_allowed(SAFE_COLUMNS)
    assert_candidate_predictors_allowed(
        {
            "FL_DATE",
            "OP_CARRIER",
            "OP_CARRIER_FL_NUM",
            "DEST",
            "CRS_DEP_TIME",
            "CRS_ARR_TIME",
            "CRS_ELAPSED_TIME",
            "MONTH",
            "DAY_OF_MONTH",
            "DAY_OF_WEEK",
        },
        task=DEPARTURE_TASK,
    )


@pytest.mark.parametrize(
    ("task", "conditional"),
    [
        (ARRIVAL_TASK, {"ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}),
        (DEPARTURE_TASK, {"DEST_INDEX", "D_LATITUDE", "D_LONGITUDE"}),
    ],
)
def test_conditional_fields_require_explicit_review(
    task: str, conditional: set[str]
) -> None:
    with pytest.raises(
        LeakageRuleViolation, match="conditional_requires_explicit_review"
    ):
        assert_candidate_predictors_allowed(conditional, task=task)
    assert_candidate_predictors_allowed(
        conditional, task=task, allow_conditional=True
    )


@pytest.mark.parametrize("task", [ARRIVAL_TASK, DEPARTURE_TASK])
def test_every_canonical_and_traceability_column_is_classified(task: str) -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "artifacts/manifests/canonical_schema_v1.json").read_text(
            encoding="utf-8"
        )
    )
    expected = set(schema["column_order"]) | {
        "flight_key",
        "source_row_number",
        "source_year",
        "y_arr_cls",
        "y_arr_reg",
        "y_dep_cls",
    }
    assert {column for column in expected if status_for(column, task=task)} == expected


def test_unknown_columns_and_external_weather_fail_closed() -> None:
    for field in ["UNREGISTERED_FIELD", "weather_point_in_time_v1_temperature"]:
        with pytest.raises(LeakageRuleViolation, match="unclassified"):
            assert_candidate_predictors_allowed([field])
        with pytest.raises(LeakageRuleViolation, match="not classified"):
            status_for(field)


def test_unknown_task_fails_closed_before_field_classification() -> None:
    with pytest.raises(LeakageRuleViolation, match="Unknown prediction task"):
        assert_candidate_predictors_allowed(["FL_DATE"], task="unknown_task")
    with pytest.raises(LeakageRuleViolation, match="Unknown prediction task"):
        status_for("FL_DATE", task="unknown_task")


def test_arrival_is_the_backward_compatible_default_task() -> None:
    assert status_for("ARR_DELAY") == "TARGET"
    assert status_for("DEST") == "DROP_CONSTANT"
    assert CONDITIONAL_COLUMNS == {"ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"}
