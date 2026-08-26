from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.data.weather_contract import (
    WeatherContractViolation,
    assert_dep_row_parity,
    is_weather_record_available_by_cutoff,
    select_point_in_time_weather_record,
    validate_weather_record_metadata,
)


UTC = timezone.utc
CUTOFF = datetime(2026, 8, 26, 7, 0, tzinfo=UTC)


def _forecast(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "record_id": "forecast-a",
        "provider": "synthetic-provider",
        "product": "synthetic-product",
        "product_version": "test-v1",
        "semantic_class": "FORECAST",
        "issue_time": datetime(2026, 8, 26, 5, 0, tzinfo=UTC),
        "publication_time": datetime(2026, 8, 26, 5, 5, tzinfo=UTC),
        "available_time": datetime(2026, 8, 26, 5, 10, tzinfo=UTC),
        "valid_time": datetime(2026, 8, 26, 8, 0, tzinfo=UTC),
        "source_timezone": "UTC",
        "location_type": "airport",
        "location_id": "ATL",
        "location_mapping_version": "test-map-v1",
        "variables": ["temperature"],
    }
    record.update(overrides)
    return record


def test_available_forecast_at_or_before_cutoff_is_potentially_eligible() -> None:
    assert is_weather_record_available_by_cutoff(_forecast(), CUTOFF) is True
    assert (
        is_weather_record_available_by_cutoff(
            _forecast(available_time=CUTOFF, publication_time=CUTOFF), CUTOFF
        )
        is True
    )


def test_valid_time_does_not_override_publication_after_cutoff() -> None:
    record = _forecast(
        valid_time=datetime(2026, 8, 26, 6, 30, tzinfo=UTC),
        publication_time=datetime(2026, 8, 26, 7, 5, tzinfo=UTC),
        available_time=datetime(2026, 8, 26, 7, 10, tzinfo=UTC),
    )

    assert is_weather_record_available_by_cutoff(record, CUTOFF) is False


def test_future_issue_is_rejected_even_when_valid_time_is_closer() -> None:
    earlier = _forecast()
    future = _forecast(
        record_id="forecast-b",
        issue_time=datetime(2026, 8, 26, 8, 0, tzinfo=UTC),
        publication_time=datetime(2026, 8, 26, 8, 2, tzinfo=UTC),
        available_time=datetime(2026, 8, 26, 8, 5, tzinfo=UTC),
        valid_time=datetime(2026, 8, 26, 7, 0, tzinfo=UTC),
    )

    assert is_weather_record_available_by_cutoff(future, CUTOFF) is False
    assert select_point_in_time_weather_record([future, earlier], CUTOFF) == earlier


def test_observation_time_before_cutoff_is_not_enough() -> None:
    record = _forecast(
        semantic_class="OBSERVATION",
        observation_time=datetime(2026, 8, 26, 6, 0, tzinfo=UTC),
        publication_time=datetime(2026, 8, 26, 7, 5, tzinfo=UTC),
        available_time=datetime(2026, 8, 26, 7, 10, tzinfo=UTC),
    )

    assert is_weather_record_available_by_cutoff(record, CUTOFF) is False


@pytest.mark.parametrize("semantic_class", ["REANALYSIS", "MODEL_ANALYSIS", "MODEL_FILL"])
def test_retrospective_semantic_classes_fail_closed_for_predictor_use(
    semantic_class: str,
) -> None:
    assert (
        is_weather_record_available_by_cutoff(
            _forecast(semantic_class=semantic_class), CUTOFF
        )
        is False
    )


def test_naive_timestamps_fail_closed() -> None:
    with pytest.raises(WeatherContractViolation, match="timezone-aware"):
        is_weather_record_available_by_cutoff(_forecast(), datetime(2026, 8, 26, 7))

    with pytest.raises(WeatherContractViolation, match="timezone-aware"):
        validate_weather_record_metadata(
            _forecast(available_time=datetime(2026, 8, 26, 5, 10))
        )


def test_aware_but_non_utc_storage_timestamp_fails_closed() -> None:
    local_offset = timezone(timedelta(hours=-4))

    with pytest.raises(WeatherContractViolation, match="normalized to UTC"):
        validate_weather_record_metadata(
            _forecast(
                available_time=datetime(
                    2026, 8, 26, 1, 10, tzinfo=local_offset
                )
            )
        )


@pytest.mark.parametrize("missing_field", ["provider", "product", "product_version"])
def test_missing_source_identity_prevents_contract_validation(missing_field: str) -> None:
    record = _forecast()
    record[missing_field] = ""

    with pytest.raises(WeatherContractViolation, match=missing_field):
        validate_weather_record_metadata(record)


def test_unknown_semantic_class_and_arrival_task_fail_closed() -> None:
    with pytest.raises(WeatherContractViolation, match="semantic_class"):
        validate_weather_record_metadata(_forecast(semantic_class="UNKNOWN"))

    with pytest.raises(WeatherContractViolation, match="departure_auxiliary"):
        validate_weather_record_metadata(_forecast(), task="arrival_core")


def test_raw_aeolus_weather_cannot_satisfy_external_contract() -> None:
    with pytest.raises(WeatherContractViolation, match="Aeolus raw Weather"):
        validate_weather_record_metadata(_forecast(variables=["O_TEMP"]))


def test_selection_is_deterministic_after_eligibility_filter() -> None:
    older = _forecast(record_id="older")
    newer_far = _forecast(
        record_id="newer-far",
        issue_time=datetime(2026, 8, 26, 6, 0, tzinfo=UTC),
        publication_time=datetime(2026, 8, 26, 6, 5, tzinfo=UTC),
        available_time=datetime(2026, 8, 26, 6, 10, tzinfo=UTC),
        valid_time=datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
    )
    newer_near = _forecast(
        record_id="newer-near",
        issue_time=newer_far["issue_time"],
        publication_time=newer_far["publication_time"],
        available_time=newer_far["available_time"],
        valid_time=datetime(2026, 8, 26, 7, 30, tzinfo=UTC),
    )

    selected = select_point_in_time_weather_record(
        [newer_far, older, newer_near], CUTOFF
    )

    assert selected == newer_near


def test_duplicate_selection_keys_fail_instead_of_arbitrary_deduplication() -> None:
    first = _forecast(record_id="first")
    duplicate = _forecast(record_id="second")

    with pytest.raises(WeatherContractViolation, match="Duplicate"):
        select_point_in_time_weather_record([first, duplicate], CUTOFF)


def test_dep_a_dep_b_target_row_parity_is_exact() -> None:
    assert_dep_row_parity(["f1", "f2"], ["f1", "f2"])

    with pytest.raises(WeatherContractViolation, match="row parity"):
        assert_dep_row_parity(["f1", "f2"], ["f1"])
