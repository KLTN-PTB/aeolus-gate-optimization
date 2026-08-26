"""Audit-only canonical schedule date/time representation analysis.

This module does not participate in Flight Chain reconstruction and does not
change production normalization.  It scans only approved canonical columns in
bounded PyArrow batches after the existing development access guard succeeds.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
import platform
import time as time_module
from typing import Any, Final

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.data.access_guard import assert_data_access_allowed


AUDIT_COLUMNS: Final = (
    "FL_DATE",
    "CRS_DEP_TIME",
    "CRS_ARR_TIME",
    "source_year",
    "source_row_number",
    "flight_key",
)

_TIMESTAMP_SPACE_FORMAT: Final = "%Y-%m-%d %H:%M:%S"
_TIMESTAMP_T_FORMAT: Final = "%Y-%m-%dT%H:%M:%S"
_ISO_DATE_FORMAT: Final = "%Y-%m-%d"


class CanonicalDatetimeAuditError(ValueError):
    """Raised when canonical audit input or accounting fails closed."""


def _false_if_null(mask: pa.Array) -> pa.Array:
    return pc.fill_null(mask, False)


def _mask_count(mask: pa.Array) -> int:
    value = pc.sum(pc.cast(_false_if_null(mask), pa.int64())).as_py()
    return int(value or 0)


def _and(*masks: pa.Array) -> pa.Array:
    result = masks[0]
    for mask in masks[1:]:
        result = pc.and_kleene(result, mask)
    return _false_if_null(result)


def _or(*masks: pa.Array) -> pa.Array:
    result = masks[0]
    for mask in masks[1:]:
        result = pc.or_kleene(result, mask)
    return _false_if_null(result)


def _not(mask: pa.Array) -> pa.Array:
    return _false_if_null(pc.invert(_false_if_null(mask)))


def _parse_storage_strings(values: pa.Array) -> dict[str, pa.Array]:
    """Parse exact storage formats for representation evidence only."""
    stripped = pc.utf8_trim_whitespace(values)
    timestamp_space = pc.strptime(
        stripped,
        format=_TIMESTAMP_SPACE_FORMAT,
        unit="s",
        error_is_null=True,
    )
    timestamp_t_raw = pc.strptime(
        stripped,
        format=_TIMESTAMP_T_FORMAT,
        unit="s",
        error_is_null=True,
    )
    timestamp_t = pc.if_else(
        pc.is_null(timestamp_space), timestamp_t_raw, pa.scalar(None, pa.timestamp("s"))
    )
    iso_date_raw = pc.strptime(
        stripped,
        format=_ISO_DATE_FORMAT,
        unit="s",
        error_is_null=True,
    )
    any_timestamp = pc.coalesce(timestamp_space, timestamp_t)
    iso_date = pc.if_else(
        pc.is_null(any_timestamp), iso_date_raw, pa.scalar(None, pa.timestamp("s"))
    )
    calendar_timestamp = pc.coalesce(any_timestamp, iso_date)
    return {
        "stripped": stripped,
        "timestamp_space": timestamp_space,
        "timestamp_t": timestamp_t,
        "timestamp": any_timestamp,
        "iso_date": iso_date,
        "calendar_timestamp": calendar_timestamp,
    }


def _valid_hhmm_mask(stripped: pa.Array) -> pa.Array:
    syntax = _false_if_null(
        pc.match_substring_regex(stripped, r"^\d{1,4}(?:\.0+)?$")
    )
    canonical = pc.replace_substring_regex(stripped, pattern=r"\.0+$", replacement="")
    numeric_text = pc.if_else(syntax, canonical, pa.scalar(None, canonical.type))
    numeric = pc.cast(numeric_text, pa.int32(), safe=False)
    hour = pc.divide(numeric, 100)
    minute = pc.subtract(numeric, pc.multiply(hour, 100))
    ordinary = _and(
        pc.greater_equal(numeric, 0),
        pc.less_equal(numeric, 2359),
        pc.less_equal(minute, 59),
    )
    return _and(syntax, _or(ordinary, pc.equal(numeric, 2400)))


def _clock_midnight_mask(timestamps: pa.Array) -> pa.Array:
    return _and(
        pc.is_valid(timestamps),
        pc.equal(pc.hour(timestamps), 0),
        pc.equal(pc.minute(timestamps), 0),
        pc.equal(pc.second(timestamps), 0),
    )


def _counter_from_values(values: pa.Array, *, width: int = 2) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in pc.value_counts(values).to_pylist():
        value = item["values"]
        if value is not None:
            counts[f"{int(value):0{width}d}"] += int(item["counts"])
    return counts


def _min_max_date(calendar_timestamps: pa.Array) -> tuple[str | None, str | None]:
    dates = pc.cast(calendar_timestamps, pa.date32())
    bounds = pc.min_max(dates).as_py()
    minimum: date | None = bounds["min"]
    maximum: date | None = bounds["max"]
    return (
        minimum.isoformat() if minimum is not None else None,
        maximum.isoformat() if maximum is not None else None,
    )


class ScheduleDatetimeAuditAccumulator:
    """Accumulate exact schedule representation metrics without retaining batches."""

    def __init__(self, *, year: int, example_limit: int = 3) -> None:
        if example_limit < 1:
            raise ValueError("example_limit must be positive")
        self.year = int(year)
        self.example_limit = int(example_limit)
        self.total_rows = 0
        self.batch_count = 0
        self.source_year_mismatch_count = 0
        self.source_row_number_null_count = 0
        self.flight_key_null_count = 0
        self._field_counts: dict[str, Counter[str]] = {
            name: Counter() for name in ("FL_DATE", "CRS_DEP_TIME", "CRS_ARR_TIME")
        }
        self._relations: dict[str, Counter[str]] = {
            name: Counter() for name in ("CRS_DEP_TIME", "CRS_ARR_TIME")
        }
        self._hour_counts: dict[str, Counter[str]] = {
            name: Counter() for name in ("CRS_DEP_TIME", "CRS_ARR_TIME")
        }
        self._minute_counts: dict[str, Counter[str]] = {
            name: Counter() for name in ("CRS_DEP_TIME", "CRS_ARR_TIME")
        }
        self._examples: dict[str, dict[str, list[dict[str, object]]]] = {
            name: defaultdict(list)
            for name in ("FL_DATE", "CRS_DEP_TIME", "CRS_ARR_TIME")
        }
        self._min_dates: list[str] = []
        self._max_dates: list[str] = []

    def _capture(
        self,
        *,
        field: str,
        category: str,
        mask: pa.Array,
        batch: pa.RecordBatch,
    ) -> None:
        destination = self._examples[field][category]
        remaining = self.example_limit - len(destination)
        if remaining <= 0:
            return
        indices = pc.indices_nonzero(_false_if_null(mask))
        if len(indices) == 0:
            return
        selected = batch.take(indices.slice(0, remaining)).to_pylist()
        for row in selected:
            destination.append({name: row.get(name) for name in AUDIT_COLUMNS})

    def _consume_flight_date(
        self, batch: pa.RecordBatch, parsed: Mapping[str, pa.Array]
    ) -> None:
        values = batch.column(batch.schema.get_field_index("FL_DATE"))
        valid = pc.is_valid(values)
        timestamp = parsed["timestamp"]
        timestamp_valid = pc.is_valid(timestamp)
        timestamp_midnight = _clock_midnight_mask(timestamp)
        timestamp_non_midnight = _and(timestamp_valid, _not(timestamp_midnight))
        iso_valid = pc.is_valid(parsed["iso_date"])
        recognized = _or(timestamp_valid, iso_valid)
        missing = pc.is_null(values)
        unrecognized = _and(valid, _not(recognized))

        counts = self._field_counts["FL_DATE"]
        counts["missing"] += _mask_count(missing)
        counts["timestamp_space_seconds"] += _mask_count(
            pc.is_valid(parsed["timestamp_space"])
        )
        counts["timestamp_t_seconds"] += _mask_count(
            pc.is_valid(parsed["timestamp_t"])
        )
        counts["iso_date"] += _mask_count(iso_valid)
        counts["unrecognized"] += _mask_count(unrecognized)
        counts["timestamp_midnight"] += _mask_count(timestamp_midnight)
        counts["timestamp_non_midnight"] += _mask_count(timestamp_non_midnight)

        minimum, maximum = _min_max_date(parsed["calendar_timestamp"])
        if minimum is not None:
            self._min_dates.append(minimum)
        if maximum is not None:
            self._max_dates.append(maximum)

        self._capture(
            field="FL_DATE",
            category="timestamp_midnight",
            mask=timestamp_midnight,
            batch=batch,
        )
        self._capture(
            field="FL_DATE",
            category="timestamp_non_midnight",
            mask=timestamp_non_midnight,
            batch=batch,
        )
        self._capture(
            field="FL_DATE", category="iso_date", mask=iso_valid, batch=batch
        )
        self._capture(
            field="FL_DATE", category="missing", mask=missing, batch=batch
        )
        self._capture(
            field="FL_DATE",
            category="unrecognized",
            mask=unrecognized,
            batch=batch,
        )

    def _consume_schedule_time(
        self,
        *,
        field: str,
        batch: pa.RecordBatch,
        parsed: Mapping[str, pa.Array],
        flight_date_timestamp: pa.Array,
    ) -> None:
        values = batch.column(batch.schema.get_field_index(field))
        valid = pc.is_valid(values)
        timestamp = parsed["timestamp"]
        timestamp_valid = pc.is_valid(timestamp)
        hhmm = _and(_valid_hhmm_mask(parsed["stripped"]), _not(timestamp_valid))
        missing = pc.is_null(values)
        recognized = _or(timestamp_valid, hhmm)
        unrecognized = _and(valid, _not(recognized))

        counts = self._field_counts[field]
        counts["missing"] += _mask_count(missing)
        counts["timestamp_space_seconds"] += _mask_count(
            pc.is_valid(parsed["timestamp_space"])
        )
        counts["timestamp_t_seconds"] += _mask_count(
            pc.is_valid(parsed["timestamp_t"])
        )
        counts["hhmm"] += _mask_count(hhmm)
        counts["unrecognized"] += _mask_count(unrecognized)

        flight_date_valid = pc.is_valid(flight_date_timestamp)
        comparable = _and(timestamp_valid, flight_date_valid)
        unavailable = _and(timestamp_valid, _not(flight_date_valid))
        time_date = pc.cast(pc.cast(timestamp, pa.date32()), pa.int32())
        flight_date = pc.cast(
            pc.cast(flight_date_timestamp, pa.date32()), pa.int32()
        )
        difference = pc.subtract(time_date, flight_date)
        same = _and(comparable, pc.equal(difference, 0))
        next_date = _and(comparable, pc.equal(difference, 1))
        previous = _and(comparable, pc.equal(difference, -1))
        greater_than_one = _and(comparable, pc.greater(pc.abs(difference), 1))
        midnight = _clock_midnight_mask(timestamp)
        same_midnight = _and(same, midnight)
        same_non_midnight = _and(same, _not(midnight))
        next_midnight = _and(next_date, midnight)
        next_non_midnight = _and(next_date, _not(midnight))

        relations = self._relations[field]
        relations["same_date"] += _mask_count(same)
        relations["next_calendar_date"] += _mask_count(next_date)
        relations["previous_calendar_date"] += _mask_count(previous)
        relations["difference_greater_than_1_day"] += _mask_count(greater_than_one)
        relations["timestamp_relation_unavailable"] += _mask_count(unavailable)
        relations["same_date_midnight"] += _mask_count(same_midnight)
        relations["same_date_non_midnight"] += _mask_count(same_non_midnight)
        relations["next_day_midnight"] += _mask_count(next_midnight)
        relations["next_day_non_midnight"] += _mask_count(next_non_midnight)

        self._hour_counts[field].update(_counter_from_values(pc.hour(timestamp)))
        self._minute_counts[field].update(_counter_from_values(pc.minute(timestamp)))

        categories = {
            "timestamp": timestamp_valid,
            "hhmm": hhmm,
            "missing": missing,
            "unrecognized": unrecognized,
            "same_date_midnight": same_midnight,
            "same_date_non_midnight": same_non_midnight,
            "next_day_midnight": next_midnight,
            "next_day_non_midnight": next_non_midnight,
            "previous_date": previous,
            "difference_greater_than_1_day": greater_than_one,
            "timestamp_relation_unavailable": unavailable,
        }
        for category, mask in categories.items():
            self._capture(field=field, category=category, mask=mask, batch=batch)

    def consume(self, batch: pa.RecordBatch) -> None:
        missing = set(AUDIT_COLUMNS).difference(batch.schema.names)
        if missing:
            raise ValueError(f"Audit batch is missing required columns: {sorted(missing)}")
        self.total_rows += len(batch)
        self.batch_count += 1

        source_year = batch.column(batch.schema.get_field_index("source_year"))
        self.source_year_mismatch_count += _mask_count(
            _or(pc.is_null(source_year), pc.not_equal(source_year, self.year))
        )
        source_row_number = batch.column(
            batch.schema.get_field_index("source_row_number")
        )
        flight_key = batch.column(batch.schema.get_field_index("flight_key"))
        self.source_row_number_null_count += source_row_number.null_count
        self.flight_key_null_count += flight_key.null_count

        flight_date_values = batch.column(batch.schema.get_field_index("FL_DATE"))
        flight_date_parsed = _parse_storage_strings(flight_date_values)
        self._consume_flight_date(batch, flight_date_parsed)
        for field in ("CRS_DEP_TIME", "CRS_ARR_TIME"):
            values = batch.column(batch.schema.get_field_index(field))
            parsed = _parse_storage_strings(values)
            self._consume_schedule_time(
                field=field,
                batch=batch,
                parsed=parsed,
                flight_date_timestamp=flight_date_parsed["calendar_timestamp"],
            )

    def _finish_flight_date(self, arrow_type: str) -> dict[str, object]:
        counts = self._field_counts["FL_DATE"]
        timestamp_like = (
            counts["timestamp_space_seconds"] + counts["timestamp_t_seconds"]
        )
        representations = {
            name: counts[name]
            for name in (
                "iso_date",
                "missing",
                "timestamp_space_seconds",
                "timestamp_t_seconds",
                "unrecognized",
            )
            if counts[name]
        }
        return {
            "arrow_type": arrow_type,
            "null_count": counts["missing"],
            "timestamp_like_count": timestamp_like,
            "iso_date_count": counts["iso_date"],
            "parseable_calendar_date_count": timestamp_like + counts["iso_date"],
            "non_parseable_count": counts["unrecognized"],
            "timestamp_midnight_count": counts["timestamp_midnight"],
            "timestamp_non_midnight_count": counts["timestamp_non_midnight"],
            "min_date": min(self._min_dates) if self._min_dates else None,
            "max_date": max(self._max_dates) if self._max_dates else None,
            "representation_counts": representations,
            "examples": dict(sorted(self._examples["FL_DATE"].items())),
        }

    def _finish_schedule_time(self, field: str, arrow_type: str) -> dict[str, object]:
        counts = self._field_counts[field]
        relations = self._relations[field]
        timestamp_like = (
            counts["timestamp_space_seconds"] + counts["timestamp_t_seconds"]
        )
        relation_payload = {
            name: relations[name]
            for name in (
                "same_date",
                "next_calendar_date",
                "previous_calendar_date",
                "difference_greater_than_1_day",
            )
        }
        other_date = (
            relations["previous_calendar_date"]
            + relations["difference_greater_than_1_day"]
            + (relations["next_day_non_midnight"] if field == "CRS_DEP_TIME" else 0)
        )
        return {
            "arrow_type": arrow_type,
            "null_count": counts["missing"],
            "timestamp_like_count": timestamp_like,
            "hhmm_like_count": counts["hhmm"],
            "invalid_unrecognized_count": counts["unrecognized"],
            "representation_counts": {
                name: counts[name]
                for name in (
                    "hhmm",
                    "missing",
                    "timestamp_space_seconds",
                    "timestamp_t_seconds",
                    "unrecognized",
                )
                if counts[name]
            },
            "date_relations": relation_payload,
            "timestamp_relation_unavailable_count": relations[
                "timestamp_relation_unavailable"
            ],
            "same_date_count": relations["same_date"],
            "next_date_count": relations["next_calendar_date"],
            "same_date_midnight_count": relations["same_date_midnight"],
            "same_date_non_midnight_count": relations["same_date_non_midnight"],
            "next_day_midnight_count": relations["next_day_midnight"],
            "next_day_non_midnight_count": relations["next_day_non_midnight"],
            "other_date_count": other_date,
            "hour_distribution": dict(sorted(self._hour_counts[field].items())),
            "minute_distribution": dict(
                sorted(self._minute_counts[field].items())
            ),
            "examples": dict(sorted(self._examples[field].items())),
        }

    def finish(self, *, arrow_types: Mapping[str, str]) -> dict[str, object]:
        required_types = {"FL_DATE", "CRS_DEP_TIME", "CRS_ARR_TIME"}
        missing = required_types.difference(arrow_types)
        if missing:
            raise ValueError(f"Missing Arrow storage types: {sorted(missing)}")
        return {
            "year": self.year,
            "total_rows": self.total_rows,
            "batch_count": self.batch_count,
            "source_year_mismatch_count": self.source_year_mismatch_count,
            "source_row_number_null_count": self.source_row_number_null_count,
            "flight_key_null_count": self.flight_key_null_count,
            "FL_DATE": self._finish_flight_date(arrow_types["FL_DATE"]),
            "CRS_DEP_TIME": self._finish_schedule_time(
                "CRS_DEP_TIME", arrow_types["CRS_DEP_TIME"]
            ),
            "CRS_ARR_TIME": self._finish_schedule_time(
                "CRS_ARR_TIME", arrow_types["CRS_ARR_TIME"]
            ),
        }


def validate_year_audit(result: Mapping[str, Any]) -> None:
    """Fail closed when representation or relation categories do not partition rows."""
    total_rows = int(result["total_rows"])
    flight_date = result["FL_DATE"]
    flight_date_accounted = sum(
        int(flight_date[name])
        for name in (
            "null_count",
            "timestamp_like_count",
            "iso_date_count",
            "non_parseable_count",
        )
    )
    if flight_date_accounted != total_rows:
        raise CanonicalDatetimeAuditError(
            "FL_DATE representation accounting mismatch: "
            f"accounted={flight_date_accounted} total={total_rows}"
        )
    for field in ("CRS_DEP_TIME", "CRS_ARR_TIME"):
        schedule = result[field]
        representation_accounted = sum(
            int(schedule[name])
            for name in (
                "null_count",
                "timestamp_like_count",
                "hhmm_like_count",
                "invalid_unrecognized_count",
            )
        )
        if representation_accounted != total_rows:
            raise CanonicalDatetimeAuditError(
                f"{field} representation accounting mismatch: "
                f"accounted={representation_accounted} total={total_rows}"
            )
        relation_accounted = sum(
            int(value) for value in schedule["date_relations"].values()
        ) + int(schedule["timestamp_relation_unavailable_count"])
        if relation_accounted != int(schedule["timestamp_like_count"]):
            raise CanonicalDatetimeAuditError(
                f"{field} relation accounting mismatch: "
                f"accounted={relation_accounted} "
                f"timestamp_like={schedule['timestamp_like_count']}"
            )


def audit_canonical_year(
    project_root: Path, year: int, *, batch_size: int = 100_000
) -> dict[str, object]:
    """Audit one complete development partition with a bounded Arrow scanner."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    assert_data_access_allowed(year, "development")
    root = Path(project_root).resolve()
    partition = root / "data" / "processed" / "tabular_by_year" / f"year={year}"
    files = sorted(partition.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No canonical Parquet files found: {partition}")

    dataset = ds.dataset(partition, format="parquet")
    missing = set(AUDIT_COLUMNS).difference(dataset.schema.names)
    if missing:
        raise CanonicalDatetimeAuditError(
            f"Canonical partition is missing required columns: {sorted(missing)}"
        )
    arrow_types = {
        field: str(dataset.schema.field(field).type)
        for field in ("FL_DATE", "CRS_DEP_TIME", "CRS_ARR_TIME")
    }
    partition_row_count = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
    partition_bytes = sum(path.stat().st_size for path in files)
    accumulator = ScheduleDatetimeAuditAccumulator(year=year)
    scanner = dataset.scanner(
        columns=list(AUDIT_COLUMNS),
        batch_size=batch_size,
        use_threads=False,
        batch_readahead=1,
        fragment_readahead=1,
    )
    started = time_module.perf_counter()
    for batch in scanner.to_batches():
        accumulator.consume(batch)
    runtime_seconds = time_module.perf_counter() - started
    result = accumulator.finish(arrow_types=arrow_types)
    validate_year_audit(result)
    if result["total_rows"] != partition_row_count:
        raise CanonicalDatetimeAuditError(
            "Canonical audit row accounting mismatch: "
            f"scanned={result['total_rows']} metadata={partition_row_count}"
        )
    result.update(
        {
            "projected_columns": list(AUDIT_COLUMNS),
            "partition_file_count": len(files),
            "partition_row_count": partition_row_count,
            "partition_bytes": partition_bytes,
            "runtime_seconds": runtime_seconds,
            "rows_per_second": (
                partition_row_count / runtime_seconds if runtime_seconds else None
            ),
        }
    )
    return result


def audit_development_years(
    project_root: Path,
    years: Any,
    *,
    batch_size: int = 100_000,
) -> dict[str, object]:
    """Audit requested years sequentially; never concatenate annual data."""
    requested = [int(year) for year in years]
    if not requested:
        raise ValueError("At least one audit year is required")
    if len(set(requested)) != len(requested):
        raise ValueError("Duplicate audit year is not allowed")
    requested = sorted(requested)
    started = time_module.perf_counter()
    entries = [
        audit_canonical_year(project_root, year, batch_size=batch_size)
        for year in requested
    ]
    return {
        "artifact": "canonical_schedule_datetime_representation_audit",
        "audit_version": "v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "canonical_tabular_by_year",
        "purpose": "development_representation_audit",
        "audited_years": requested,
        "full_development_scope_complete": requested == list(range(2016, 2024)),
        "projected_columns": list(AUDIT_COLUMNS),
        "batch_size": batch_size,
        "bounded_memory": True,
        "dependencies": {
            "python": platform.python_version(),
            "pyarrow": pa.__version__,
        },
        "total_rows": sum(int(entry["total_rows"]) for entry in entries),
        "runtime_seconds": time_module.perf_counter() - started,
        "years": entries,
        "decision": "PENDING_EVIDENCE_REVIEW",
    }
