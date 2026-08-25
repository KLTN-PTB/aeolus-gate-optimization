from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.leakage_rules import (
    CLASSIFICATION_THRESHOLD_MINUTES,
    CONDITIONAL_COLUMNS,
    CORE_DROPPED_WEATHER_COLUMNS,
    CORE_WEATHER_POLICY,
    FORBIDDEN_PREDICTOR_COLUMNS,
    LEAKAGE_COLUMNS,
    LeakageRuleViolation,
    PREDICTION_CUTOFF_HOURS,
    SAFE_COLUMNS,
    TARGET_COLUMNS,
    WEATHER_COLUMNS,
    WEATHER_AUDIT_STATUS,
    assert_candidate_predictors_allowed,
    status_for,
)


EXPECTED_ACTUAL_FIELDS = {
    "DEP_TIME", "DEP_DELAY", "TAXI_OUT", "WHEELS_OFF", "WHEELS_ON",
    "TAXI_IN", "ARR_TIME", "ACTUAL_ELAPSED_TIME", "AIR_TIME",
}


def test_locked_prediction_contract() -> None:
    assert PREDICTION_CUTOFF_HOURS == 2
    assert CLASSIFICATION_THRESHOLD_MINUTES == 15
    assert TARGET_COLUMNS == {"ARR_DELAY", "y_cls"}


def test_all_realized_operation_fields_are_leakage_and_rejected() -> None:
    assert LEAKAGE_COLUMNS == EXPECTED_ACTUAL_FIELDS
    for column in EXPECTED_ACTUAL_FIELDS:
        assert status_for(column) == "LEAKAGE"
        with pytest.raises(LeakageRuleViolation, match="forbidden"):
            assert_candidate_predictors_allowed([column])


@pytest.mark.parametrize("column", sorted(TARGET_COLUMNS | WEATHER_COLUMNS))
def test_targets_and_unsafe_weather_cannot_enter_candidate_x(column: str) -> None:
    assert column in FORBIDDEN_PREDICTOR_COLUMNS
    with pytest.raises(LeakageRuleViolation):
        assert_candidate_predictors_allowed([column])


def test_weather_audit_fails_closed_for_all_canonical_weather_fields() -> None:
    assert CORE_WEATHER_POLICY == "DROP"
    assert CORE_DROPPED_WEATHER_COLUMNS == WEATHER_COLUMNS
    assert WEATHER_AUDIT_STATUS == "INSUFFICIENT_EVIDENCE"
    assert {status_for(column) for column in WEATHER_COLUMNS} == {
        "INSUFFICIENT_EVIDENCE"
    }


def test_weather_policy_covers_exact_canonical_weather_role() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads((root / "artifacts/manifests/canonical_schema_v1.json").read_text())
    canonical_weather = {
        name
        for name, metadata in schema["fields"].items()
        if metadata["schema_role"] == "weather"
    }
    assert WEATHER_COLUMNS == canonical_weather


def test_safe_schedule_set_is_allowed() -> None:
    assert_candidate_predictors_allowed(SAFE_COLUMNS)


def test_conditional_fields_require_explicit_review() -> None:
    with pytest.raises(LeakageRuleViolation, match="conditional_requires_explicit_review"):
        assert_candidate_predictors_allowed(CONDITIONAL_COLUMNS)
    assert_candidate_predictors_allowed(CONDITIONAL_COLUMNS, allow_conditional=True)


def test_every_canonical_and_traceability_column_is_classified() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads((root / "artifacts/manifests/canonical_schema_v1.json").read_text())
    expected = set(schema["column_order"]) | {"flight_key", "source_row_number", "source_year", "y_cls"}
    assert {column for column in expected if status_for(column)} == expected


def test_unknown_columns_fail_closed() -> None:
    with pytest.raises(LeakageRuleViolation, match="unclassified"):
        assert_candidate_predictors_allowed(["UNREGISTERED_FIELD"])
