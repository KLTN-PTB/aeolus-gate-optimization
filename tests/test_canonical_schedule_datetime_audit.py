from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.audit_canonical_schedule_datetime import (
    build_parser,
    parse_development_years,
)
from src.data.access_guard import DataAccessDenied
from src.data.canonical_schedule_datetime_audit import (
    AUDIT_COLUMNS,
    CanonicalDatetimeAuditError,
    ScheduleDatetimeAuditAccumulator,
    audit_canonical_year,
    audit_development_years,
    validate_year_audit,
)


def _audit_rows() -> list[dict[str, object]]:
    values = [
        ("2016-01-01 00:00:00", "2016-01-01 09:30:00", "2016-01-01 11:45:00"),
        ("2016-01-01 00:00:00", "2016-01-02 00:00:00", "2016-01-02 01:00:00"),
        ("2016-01-02 00:00:00", "2016-01-02 00:00:00", "2016-01-01 23:00:00"),
        ("2016-01-03 00:00:00", "2016-01-02 23:55:00", "2016-01-03 10:00:00"),
        ("2016-01-04 00:00:00", "2016-01-06 12:00:00", "2016-01-06 14:00:00"),
        ("2016-01-05 09:00:00", "2016-01-05 10:00:00", "2016-01-05 11:00:00"),
        ("2016-01-06", "800", "1030"),
        ("not-a-date", "not-a-time", "also-invalid"),
        (None, None, None),
    ]
    return [
        {
            "FL_DATE": flight_date,
            "CRS_DEP_TIME": departure,
            "CRS_ARR_TIME": arrival,
            "source_year": 2016,
            "source_row_number": index,
            "flight_key": f"flight_key_v1_literal_{index}",
        }
        for index, (flight_date, departure, arrival) in enumerate(values, start=1)
    ]


def test_arrow_accumulator_accounts_for_representations_and_date_relations() -> None:
    accumulator = ScheduleDatetimeAuditAccumulator(year=2016, example_limit=2)
    batch = pa.RecordBatch.from_pylist(_audit_rows())

    accumulator.consume(batch)
    result = accumulator.finish(
        arrow_types={
            "FL_DATE": "large_string",
            "CRS_DEP_TIME": "large_string",
            "CRS_ARR_TIME": "large_string",
        }
    )

    assert AUDIT_COLUMNS == (
        "FL_DATE",
        "CRS_DEP_TIME",
        "CRS_ARR_TIME",
        "source_year",
        "source_row_number",
        "flight_key",
    )
    assert result["year"] == 2016
    assert result["total_rows"] == 9

    flight_date = result["FL_DATE"]
    assert flight_date["arrow_type"] == "large_string"
    assert flight_date["null_count"] == 1
    assert flight_date["timestamp_like_count"] == 6
    assert flight_date["iso_date_count"] == 1
    assert flight_date["parseable_calendar_date_count"] == 7
    assert flight_date["non_parseable_count"] == 1
    assert flight_date["timestamp_midnight_count"] == 5
    assert flight_date["timestamp_non_midnight_count"] == 1
    assert flight_date["min_date"] == "2016-01-01"
    assert flight_date["max_date"] == "2016-01-06"
    assert flight_date["representation_counts"] == {
        "iso_date": 1,
        "missing": 1,
        "timestamp_space_seconds": 6,
        "unrecognized": 1,
    }

    departure = result["CRS_DEP_TIME"]
    assert departure["null_count"] == 1
    assert departure["timestamp_like_count"] == 6
    assert departure["hhmm_like_count"] == 1
    assert departure["invalid_unrecognized_count"] == 1
    assert departure["date_relations"] == {
        "same_date": 3,
        "next_calendar_date": 1,
        "previous_calendar_date": 1,
        "difference_greater_than_1_day": 1,
    }
    assert departure["same_date_midnight_count"] == 1
    assert departure["next_day_midnight_count"] == 1
    assert departure["other_date_count"] == 2
    assert departure["hour_distribution"] == {
        "00": 2,
        "09": 1,
        "10": 1,
        "12": 1,
        "23": 1,
    }
    assert departure["minute_distribution"] == {"00": 4, "30": 1, "55": 1}

    arrival = result["CRS_ARR_TIME"]
    assert arrival["timestamp_like_count"] == 6
    assert arrival["hhmm_like_count"] == 1
    assert arrival["invalid_unrecognized_count"] == 1
    assert arrival["date_relations"] == {
        "same_date": 3,
        "next_calendar_date": 1,
        "previous_calendar_date": 1,
        "difference_greater_than_1_day": 1,
    }
    assert arrival["same_date_count"] == 3
    assert arrival["next_date_count"] == 1
    assert arrival["other_date_count"] == 2

    next_day_examples = departure["examples"]["next_day_midnight"]
    assert next_day_examples == [
        {
            "FL_DATE": "2016-01-01 00:00:00",
            "CRS_DEP_TIME": "2016-01-02 00:00:00",
            "CRS_ARR_TIME": "2016-01-02 01:00:00",
            "source_year": 2016,
            "source_row_number": 2,
            "flight_key": "flight_key_v1_literal_2",
        }
    ]


def test_arrow_accumulator_is_deterministic_across_batch_boundaries() -> None:
    rows = _audit_rows()
    one_batch = ScheduleDatetimeAuditAccumulator(year=2016, example_limit=2)
    one_batch.consume(pa.RecordBatch.from_pylist(rows))

    split_batches = ScheduleDatetimeAuditAccumulator(year=2016, example_limit=2)
    split_batches.consume(pa.RecordBatch.from_pylist(rows[:4]))
    split_batches.consume(pa.RecordBatch.from_pylist(rows[4:]))

    arrow_types = {
        "FL_DATE": "large_string",
        "CRS_DEP_TIME": "large_string",
        "CRS_ARR_TIME": "large_string",
    }
    one_result = one_batch.finish(arrow_types=arrow_types)
    split_result = split_batches.finish(arrow_types=arrow_types)
    assert one_result.pop("batch_count") == 1
    assert split_result.pop("batch_count") == 2
    assert one_result == split_result


def test_year_audit_validation_rejects_unaccounted_representation_rows() -> None:
    accumulator = ScheduleDatetimeAuditAccumulator(year=2016)
    accumulator.consume(pa.RecordBatch.from_pylist(_audit_rows()))
    result = accumulator.finish(
        arrow_types={
            "FL_DATE": "string",
            "CRS_DEP_TIME": "string",
            "CRS_ARR_TIME": "string",
        }
    )
    validate_year_audit(result)

    result["CRS_DEP_TIME"]["invalid_unrecognized_count"] = 0
    with pytest.raises(CanonicalDatetimeAuditError, match="representation accounting"):
        validate_year_audit(result)


def _write_partition(
    project_root: Path,
    *,
    year: int = 2016,
    rows: list[dict[str, object]] | None = None,
) -> Path:
    partition = (
        project_root / "data" / "processed" / "tabular_by_year" / f"year={year}"
    )
    partition.mkdir(parents=True)
    records = rows or _audit_rows()
    table = pa.Table.from_pylist(
        [{**row, "ARR_DELAY": float(index)} for index, row in enumerate(records)]
    )
    destination = partition / "part-00000.parquet"
    pq.write_table(table, destination)
    return destination


def test_canonical_year_scanner_projects_only_approved_columns(tmp_path: Path) -> None:
    _write_partition(tmp_path)

    result = audit_canonical_year(tmp_path, 2016, batch_size=4)

    assert result["year"] == 2016
    assert result["projected_columns"] == list(AUDIT_COLUMNS)
    assert "ARR_DELAY" not in result["projected_columns"]
    assert result["partition_file_count"] == 1
    assert result["partition_row_count"] == 9
    assert result["total_rows"] == 9
    assert result["batch_count"] == 3
    assert result["source_year_mismatch_count"] == 0
    assert result["source_row_number_null_count"] == 0
    assert result["flight_key_null_count"] == 0
    assert result["FL_DATE"]["timestamp_like_count"] == 6


def test_canonical_year_scanner_fails_closed_on_missing_projected_column(
    tmp_path: Path,
) -> None:
    rows = _audit_rows()
    for row in rows:
        row.pop("CRS_ARR_TIME")
    _write_partition(tmp_path, rows=rows)

    with pytest.raises(CanonicalDatetimeAuditError, match="missing required columns"):
        audit_canonical_year(tmp_path, 2016, batch_size=4)


def test_canonical_year_scanner_blocks_2024_before_opening_partition(
    tmp_path: Path,
) -> None:
    with pytest.raises(DataAccessDenied, match="sealed from development"):
        audit_canonical_year(tmp_path, 2024, batch_size=4)


def test_development_audit_rejects_duplicate_and_out_of_scope_years(
    tmp_path: Path,
) -> None:
    _write_partition(tmp_path)
    manifest = audit_development_years(tmp_path, [2016], batch_size=4)
    assert manifest["audited_years"] == [2016]
    assert manifest["years"][0]["total_rows"] == 9
    assert manifest["projected_columns"] == list(AUDIT_COLUMNS)

    with pytest.raises(ValueError, match="Duplicate audit year"):
        audit_development_years(tmp_path, [2016, 2016], batch_size=4)
    with pytest.raises(ValueError, match="Unsupported Aeolus year"):
        audit_development_years(tmp_path, [2015], batch_size=4)


def test_audit_cli_parses_only_development_years_and_positive_batch_size() -> None:
    assert parse_development_years("2016-2018,2020,2023") == [
        2016,
        2017,
        2018,
        2020,
        2023,
    ]
    with pytest.raises(ValueError, match="development years 2016-2023"):
        parse_development_years("2024")

    parser = build_parser()
    defaults = parser.parse_args([])
    assert defaults.years == "2016-2023"
    assert defaults.batch_size == 100_000
    assert defaults.output == Path(
        "artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json"
    )
    with pytest.raises(SystemExit):
        parser.parse_args(["--batch-size", "0"])
