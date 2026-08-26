"""Pure validation rules for the future point-in-time Weather source.

This module is a Week 3C contract implementation only.  It does not download,
read, join, or materialize Weather data.  Passing these record-level checks is
necessary but not sufficient for a provider-level provenance PASS.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any


DEPARTURE_TASK = "departure_auxiliary"
WEATHER_SEMANTIC_CLASSES = frozenset(
    {"FORECAST", "OBSERVATION", "REANALYSIS", "MODEL_ANALYSIS", "MODEL_FILL"}
)
RETROSPECTIVE_CLASSES = frozenset(
    {"REANALYSIS", "MODEL_ANALYSIS", "MODEL_FILL"}
)
AEOLUS_RAW_WEATHER_COLUMNS = frozenset(
    {"O_TEMP", "O_PRCP", "O_WSPD", "D_TEMP", "D_PRCP", "D_WSPD"}
)


class WeatherContractViolation(ValueError):
    """Raised when Weather metadata cannot satisfy the fail-closed contract."""


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WeatherContractViolation(f"{field} must be a non-empty string")
    return value


def _aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise WeatherContractViolation(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise WeatherContractViolation(f"{field} must be timezone-aware")
    if value.utcoffset().total_seconds() != 0:
        raise WeatherContractViolation(f"{field} must be normalized to UTC")
    return value


def validate_weather_record_metadata(
    record: Mapping[str, Any],
    *,
    task: str = DEPARTURE_TASK,
) -> None:
    """Validate the minimum source, time, location, and variable metadata.

    Validation does not approve a provider.  The complete W1--W15 provenance
    audit remains required before DEP-B can be enabled.
    """

    if task != DEPARTURE_TASK:
        raise WeatherContractViolation(
            "Weather contract is restricted to departure_auxiliary"
        )

    for field in ("provider", "product", "product_version"):
        _required_text(record, field)

    semantic_class = _required_text(record, "semantic_class")
    if semantic_class not in WEATHER_SEMANTIC_CLASSES:
        raise WeatherContractViolation(
            f"semantic_class must be one of {sorted(WEATHER_SEMANTIC_CLASSES)}"
        )

    for field in ("publication_time", "available_time", "valid_time"):
        _aware_datetime(record.get(field), field)
    if semantic_class == "FORECAST":
        _aware_datetime(record.get("issue_time"), "issue_time")
    elif semantic_class == "OBSERVATION":
        _aware_datetime(record.get("observation_time"), "observation_time")

    _required_text(record, "source_timezone")
    _required_text(record, "location_type")
    _required_text(record, "location_id")
    _required_text(record, "location_mapping_version")

    variables = record.get("variables")
    if not isinstance(variables, Sequence) or isinstance(variables, (str, bytes)):
        raise WeatherContractViolation("variables must be a non-string sequence")
    variable_names = {str(variable) for variable in variables}
    if variable_names & AEOLUS_RAW_WEATHER_COLUMNS:
        raise WeatherContractViolation(
            "Aeolus raw Weather fields cannot satisfy the external Weather contract"
        )


def is_weather_record_available_by_cutoff(
    record: Mapping[str, Any],
    cutoff: datetime,
    *,
    task: str = DEPARTURE_TASK,
) -> bool:
    """Return whether a validated record was knowable by the target cutoff."""

    cutoff_aware = _aware_datetime(cutoff, "cutoff")
    validate_weather_record_metadata(record, task=task)
    semantic_class = str(record["semantic_class"])
    if semantic_class in RETROSPECTIVE_CLASSES:
        return False

    publication_time = _aware_datetime(record["publication_time"], "publication_time")
    available_time = _aware_datetime(record["available_time"], "available_time")
    if publication_time > cutoff_aware or available_time > cutoff_aware:
        return False

    if semantic_class == "FORECAST":
        return _aware_datetime(record["issue_time"], "issue_time") <= cutoff_aware
    return _aware_datetime(record["observation_time"], "observation_time") <= cutoff_aware


def _duplicate_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    semantic_time = (
        record.get("issue_time")
        if record.get("semantic_class") == "FORECAST"
        else record.get("observation_time")
    )
    return (
        record.get("provider"),
        record.get("product"),
        record.get("product_version"),
        record.get("location_id"),
        semantic_time,
        record.get("valid_time"),
    )


def _selection_key(record: Mapping[str, Any], cutoff: datetime) -> tuple[Any, ...]:
    semantic_time = (
        record["issue_time"]
        if record["semantic_class"] == "FORECAST"
        else record["publication_time"]
    )
    valid_time = _aware_datetime(record["valid_time"], "valid_time")
    return (
        -semantic_time.timestamp(),
        abs((valid_time - cutoff).total_seconds()),
        str(record["provider"]),
        str(record["product"]),
        str(record["product_version"]),
        str(record["location_id"]),
        str(record.get("record_id", "")),
    )


def select_point_in_time_weather_record(
    records: Iterable[Mapping[str, Any]],
    cutoff: datetime,
    *,
    task: str = DEPARTURE_TASK,
) -> Mapping[str, Any] | None:
    """Select one eligible record using the contract's deterministic order.

    Availability is always filtered before issue recency or valid-time
    proximity.  Duplicate semantic keys are rejected rather than resolved by
    input order.
    """

    cutoff_aware = _aware_datetime(cutoff, "cutoff")
    eligible: list[Mapping[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        validate_weather_record_metadata(record, task=task)
        key = _duplicate_key(record)
        if key in seen:
            raise WeatherContractViolation(
                "Duplicate provider/product/location/issue-or-observation/valid key"
            )
        seen.add(key)
        if is_weather_record_available_by_cutoff(record, cutoff_aware, task=task):
            eligible.append(record)

    if not eligible:
        return None
    return min(eligible, key=lambda item: _selection_key(item, cutoff_aware))


def assert_dep_row_parity(
    dep_a_row_ids: Sequence[str], dep_b_row_ids: Sequence[str]
) -> None:
    """Require DEP-A and DEP-B to contain the exact same ordered target rows."""

    if tuple(dep_a_row_ids) != tuple(dep_b_row_ids):
        raise WeatherContractViolation(
            "DEP-A/DEP-B row parity requires identical ordered target rows"
        )
