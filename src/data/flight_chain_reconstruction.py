"""Deterministic schedule-context reconstruction from canonical Tabular.

The reconstructed chain groups a service date, operating carrier, and
operating flight number.  It is schedule-only context and must not be
interpreted as a physical aircraft rotation, tail number, registration, or
same-aircraft chain.  Original Aeolus Flight Chain ``.pt`` archives are not
inputs to this module.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import sqlite3
import sys
import time as time_module
import tracemalloc
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby
from pathlib import Path
from statistics import median
from typing import Any, Final, Iterable, Mapping

from src.data.access_guard import assert_data_access_allowed
from src.data.canonicalize import ACTUAL_OR_TARGET_FIELDS, FLIGHT_KEY_VERSION
from src.data.leakage_rules import (
    LEAKAGE_COLUMNS,
    TARGET_COLUMNS,
    UNCERTAIN_COLUMNS,
    WEATHER_COLUMNS,
)


CHAIN_ID_VERSION: Final = "schedule_chain_v1"
DATETIME_STORAGE_AMENDMENT_VERSION: Final = (
    "canonical_datetime_storage_amendment_v1"
)
CHAIN_GROUP_COMPONENTS: Final = (
    "source_year",
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
)
SCHEDULE_SIGNATURE_VERSION: Final = "schedule_signature_v1"
PHYSICAL_AIRCRAFT_IDENTITY: Final = False
_PAYLOAD_SEPARATOR: Final = "\x1f"
_FATAL_DATETIME_CONTRACT_REASONS: Final = frozenset(
    {
        "NON_MIDNIGHT_FL_DATE_TIMESTAMP",
        "AMBIGUOUS_CANONICAL_MIDNIGHT",
        "UNEXPECTED_CANONICAL_DATE_RELATION",
    }
)

CHAIN_GROUP_FIELDS: Final = (
    "chain_id",
    "chain_version",
    "source_year",
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "member_count",
    "first_scheduled_departure",
    "last_scheduled_departure",
    "has_order_tie",
)
CHAIN_MEMBER_FIELDS: Final = (
    "chain_id",
    "chain_version",
    "chain_position",
    "flight_key",
    "schedule_signature",
    "source_year",
    "source_row_number",
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "ORIGIN",
    "DEST",
    "CRS_DEP_TIME",
    "CRS_ARR_TIME",
    "CRS_ELAPSED_TIME",
    "scheduled_departure_timestamp",
    "is_inbound_atl",
    "order_ambiguous",
)
INBOUND_TARGET_MAP_FIELDS: Final = (
    "target_flight_key",
    "chain_id",
    "chain_position",
    "chain_length",
    "source_year",
)


class ReconstructionValidationError(ValueError):
    """Raised when reconstruction cannot prove its fail-closed contract."""


class ReconstructionStagingError(ReconstructionValidationError):
    """Raised with the retained per-year staging path for diagnosis."""

    def __init__(self, message: str, *, staging_path: Path) -> None:
        self.staging_path = Path(staging_path)
        super().__init__(f"{message}; staging retained at {self.staging_path}")


class _NormalizationError(ValueError):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        display_reason = reason.replace("_", "-")
        super().__init__(f"{field} is {display_reason}")


@dataclass(frozen=True)
class _NormalizedMember:
    group_key: tuple[int, str, str, str]
    chain_id: str
    flight_key: str
    source_year: int
    source_row_number: int
    flight_date: str
    carrier: str
    flight_number: str
    origin: str
    dest: str
    crs_dep_time: str
    crs_arr_time: str | None
    crs_elapsed_time: float | None
    scheduled_departure: datetime
    schedule_signature: str


@dataclass(frozen=True)
class ReconstructionResult:
    chain_groups: list[dict[str, Any]]
    chain_members: list[dict[str, Any]]
    inbound_target_map: list[dict[str, Any]]
    metrics: dict[str, Any]
    fingerprints: dict[str, str]


def assert_project_venv(project_root: Path) -> None:
    """Require the production CLI to run from this repository's ``.venv``."""
    expected = (Path(project_root).resolve() / ".venv").resolve()
    actual = Path(sys.prefix).resolve()
    if actual != expected:
        raise RuntimeError(
            "Reconstruction must run from the repository .venv: "
            f"expected={expected}, actual={actual}"
        )


def dependency_versions() -> dict[str, str]:
    """Return runtime versions required for a self-contained manifest."""
    return {
        "python": platform.python_version(),
        "pandas": importlib.metadata.version("pandas"),
        "pyarrow": importlib.metadata.version("pyarrow"),
        "sqlite": sqlite3.sqlite_version,
    }


def assert_reconstruction_year_allowed(year: int) -> None:
    """Apply the unchanged development guard before canonical data access."""
    assert_data_access_allowed(year, "development")


def assert_output_path_safe(path: Path, *, project_root: Path) -> Path:
    """Resolve and reject any output equal to or nested beneath ``data/raw``."""
    root = Path(project_root).resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = root / resolved
    resolved = resolved.resolve()
    raw_root = (root / "data" / "raw").resolve()
    if resolved == raw_root or resolved.is_relative_to(raw_root):
        raise ReconstructionValidationError(
            f"Output path resolves under protected data/raw: {resolved}"
        )
    return resolved


def snapshot_raw_inventory(
    project_root: Path,
) -> dict[str, dict[str, int | str]]:
    """Capture path, size, and nanosecond mtime without opening raw files."""
    root = Path(project_root).resolve()
    raw_root = root / "data" / "raw"
    inventory: dict[str, dict[str, int | str]] = {}
    for source in sorted(
        (path for path in raw_root.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix(),
    ):
        stat = source.stat()
        relative = source.relative_to(root).as_posix()
        inventory[relative] = {
            "path": relative,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return inventory


def assert_raw_inventory_unchanged(
    before: Mapping[str, Mapping[str, int | str]],
    after: Mapping[str, Mapping[str, int | str]],
) -> None:
    """Fail when any raw file path, size, or nanosecond mtime differs."""
    if dict(before) != dict(after):
        before_paths = set(before)
        after_paths = set(after)
        changed = sorted(
            path
            for path in before_paths & after_paths
            if dict(before[path]) != dict(after[path])
        )
        raise ReconstructionValidationError(
            "raw inventory changed: "
            f"added={sorted(after_paths - before_paths)}, "
            f"removed={sorted(before_paths - after_paths)}, changed={changed}"
        )


def _required_text(value: object, *, field: str) -> str:
    if value is None:
        raise _NormalizationError(field, "missing")
    text = str(value).strip()
    if not text:
        raise _NormalizationError(field, "missing")
    return text


def _integral_decimal(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise _NormalizationError(field, "non_numeric")
    text = _required_text(value, field=field)
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise _NormalizationError(field, "non_numeric") from error
    if not parsed.is_finite():
        raise _NormalizationError(field, "non_finite")
    if parsed != parsed.to_integral_value():
        raise _NormalizationError(field, "non_integral")
    return int(parsed)


def _normalize_source_year(value: object) -> int:
    year = _integral_decimal(value, field="source_year")
    if year < 1:
        raise _NormalizationError("source_year", "out_of_range")
    return year


def normalize_flight_date(value: object) -> str:
    """Return the service date under the versioned storage amendment.

    ISO dates and exact-midnight canonical timestamps represent the same
    service calendar date.  A non-midnight timestamp fails closed because its
    time component cannot be silently discarded.
    """
    if isinstance(value, datetime):
        if value.time() != time.min:
            raise _NormalizationError(
                "FL_DATE", "NON_MIDNIGHT_FL_DATE_TIMESTAMP"
            )
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        text = _required_text(value, field="FL_DATE")
        try:
            parsed = date.fromisoformat(text)
        except ValueError as date_error:
            try:
                timestamp = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError as timestamp_error:
                raise _NormalizationError(
                    "FL_DATE", "invalid_date"
                ) from timestamp_error
            if timestamp.time() != time.min:
                raise _NormalizationError(
                    "FL_DATE", "NON_MIDNIGHT_FL_DATE_TIMESTAMP"
                ) from date_error
            parsed = timestamp.date()
    return parsed.isoformat()


def normalize_carrier(value: object) -> str:
    """Return the trimmed uppercase operating-carrier code."""
    return _required_text(value, field="OP_CARRIER").upper()


def normalize_flight_number(value: object) -> str:
    """Return the documented operating flight number as an integer string.

    Canonical Tabular stores ``OP_CARRIER_FL_NUM`` as float64.  Integral
    validation prevents that storage choice from becoming an encoded or
    silently rounded group identifier.
    """
    return str(_integral_decimal(value, field="OP_CARRIER_FL_NUM"))


def scheduled_departure_timestamp(
    flight_date: object, crs_dep_time: object
) -> tuple[str, datetime]:
    """Normalize approved schedule storage and return its ordering timestamp.

    Explicit HHMM ``2400`` maps to the next calendar day's midnight.  A
    canonical timestamp must remain on the normalized service date and must
    not be exact midnight because canonical midnight cannot be proven to mean
    original ``0000`` rather than ``2400``.
    """
    iso_date = normalize_flight_date(flight_date)
    canonical_timestamp: datetime | None = None
    if isinstance(crs_dep_time, str):
        try:
            canonical_timestamp = datetime.strptime(
                crs_dep_time.strip(), "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            canonical_timestamp = None
    if canonical_timestamp is not None:
        if canonical_timestamp.date().isoformat() != iso_date:
            raise _NormalizationError(
                "CRS_DEP_TIME", "UNEXPECTED_CANONICAL_DATE_RELATION"
            )
        if canonical_timestamp.time() == time.min:
            raise _NormalizationError(
                "CRS_DEP_TIME", "AMBIGUOUS_CANONICAL_MIDNIGHT"
            )
        return (
            f"{canonical_timestamp.hour:02d}{canonical_timestamp.minute:02d}",
            canonical_timestamp,
        )

    hhmm_value = _integral_decimal(crs_dep_time, field="CRS_DEP_TIME")
    if hhmm_value < 0 or hhmm_value > 2400:
        raise _NormalizationError("CRS_DEP_TIME", "out_of_range")
    if hhmm_value == 2400:
        return "2400", datetime.combine(
            date.fromisoformat(iso_date) + timedelta(days=1), time.min
        )
    hour, minute = divmod(hhmm_value, 100)
    if hour > 23 or minute > 59:
        raise _NormalizationError("CRS_DEP_TIME", "invalid_hhmm")
    return f"{hhmm_value:04d}", datetime.combine(
        date.fromisoformat(iso_date), time(hour=hour, minute=minute)
    )


def _normalized_group_components(record: Mapping[str, object]) -> tuple[object, ...]:
    return (
        _normalize_source_year(record.get("source_year")),
        normalize_flight_date(record.get("FL_DATE")),
        normalize_carrier(record.get("OP_CARRIER")),
        normalize_flight_number(record.get("OP_CARRIER_FL_NUM")),
    )


def make_chain_id(record: Mapping[str, object]) -> str:
    """Create a stable schedule-chain identifier from normalized group values."""
    payload = _PAYLOAD_SEPARATOR.join(
        str(value) for value in _normalized_group_components(record)
    )
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()
    return f"{CHAIN_ID_VERSION}_{digest}"


def _normalize_optional_code(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_optional_finite_float(value: object, *, field: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ReconstructionValidationError(f"{field} is not numeric") from error
    if not math.isfinite(parsed):
        raise ReconstructionValidationError(f"{field} is not finite")
    return parsed


def make_schedule_signature(record: Mapping[str, object]) -> str:
    """Create an audit-only natural schedule signature without merging rows."""
    group_values = _normalized_group_components(record)
    crs_dep_time, _ = scheduled_departure_timestamp(
        group_values[1], record.get("CRS_DEP_TIME")
    )
    payload_values = (
        *group_values,
        _normalize_optional_code(record.get("ORIGIN")),
        _normalize_optional_code(record.get("DEST")),
        crs_dep_time,
    )
    payload = _PAYLOAD_SEPARATOR.join(str(value) for value in payload_values)
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()
    return f"{SCHEDULE_SIGNATURE_VERSION}_{digest}"


def assert_derived_schema_safe(
    table_columns: Mapping[str, Iterable[str]],
) -> None:
    """Reject leakage, outcomes, weather, and unresolved fields from outputs."""
    forbidden_contract = (
        set(ACTUAL_OR_TARGET_FIELDS)
        | set(LEAKAGE_COLUMNS)
        | set(TARGET_COLUMNS)
        | set(WEATHER_COLUMNS)
        | set(UNCERTAIN_COLUMNS)
        | {"FLIGHTS"}
    )
    found = {
        column
        for columns in table_columns.values()
        for column in columns
        if column in forbidden_contract
    }
    if found:
        raise ReconstructionValidationError(
            f"forbidden derived fields: {sorted(found)}"
        )


def _validated_traceability(
    record: Mapping[str, object],
    *,
    expected_year: int,
    seen_keys: set[str] | None,
) -> tuple[int, int, str]:
    try:
        source_year = _normalize_source_year(record.get("source_year"))
    except _NormalizationError as error:
        raise ReconstructionValidationError(str(error)) from error
    if source_year != expected_year:
        raise ReconstructionValidationError(
            f"source_year mismatch: expected={expected_year}, observed={source_year}"
        )
    try:
        row_number = _integral_decimal(
            record.get("source_row_number"), field="source_row_number"
        )
    except _NormalizationError as error:
        raise ReconstructionValidationError(str(error)) from error
    if row_number < 1:
        raise ReconstructionValidationError("source_row_number is out of range")
    try:
        flight_key = _required_text(record.get("flight_key"), field="flight_key")
    except _NormalizationError as error:
        raise ReconstructionValidationError(str(error)) from error
    if not flight_key.startswith(f"{FLIGHT_KEY_VERSION}_"):
        raise ReconstructionValidationError(
            f"flight_key does not use {FLIGHT_KEY_VERSION}"
        )
    if seen_keys is not None:
        if flight_key in seen_keys:
            raise ReconstructionValidationError(f"duplicate flight_key: {flight_key}")
        seen_keys.add(flight_key)
    return source_year, row_number, flight_key


def _normalize_member(
    record: Mapping[str, object],
    *,
    expected_year: int,
    seen_keys: set[str],
) -> _NormalizedMember:
    source_year, row_number, flight_key = _validated_traceability(
        record, expected_year=expected_year, seen_keys=seen_keys
    )
    flight_date = normalize_flight_date(record.get("FL_DATE"))
    carrier = normalize_carrier(record.get("OP_CARRIER"))
    flight_number = normalize_flight_number(record.get("OP_CARRIER_FL_NUM"))
    crs_dep_time, departure = scheduled_departure_timestamp(
        flight_date, record.get("CRS_DEP_TIME")
    )
    origin = _normalize_optional_code(record.get("ORIGIN"))
    dest = _normalize_optional_code(record.get("DEST"))
    normalized_record: dict[str, object] = {
        "source_year": source_year,
        "FL_DATE": flight_date,
        "OP_CARRIER": carrier,
        "OP_CARRIER_FL_NUM": flight_number,
        "ORIGIN": origin,
        "DEST": dest,
        "CRS_DEP_TIME": crs_dep_time,
    }
    group_key = (source_year, flight_date, carrier, flight_number)
    return _NormalizedMember(
        group_key=group_key,
        chain_id=make_chain_id(normalized_record),
        flight_key=flight_key,
        source_year=source_year,
        source_row_number=row_number,
        flight_date=flight_date,
        carrier=carrier,
        flight_number=flight_number,
        origin=origin,
        dest=dest,
        crs_dep_time=crs_dep_time,
        crs_arr_time=_normalize_optional_text(record.get("CRS_ARR_TIME")),
        crs_elapsed_time=_normalize_optional_finite_float(
            record.get("CRS_ELAPSED_TIME"), field="CRS_ELAPSED_TIME"
        ),
        scheduled_departure=departure,
        schedule_signature=make_schedule_signature(normalized_record),
    )


def _logical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    return value


def _table_fingerprint(rows: Iterable[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    hasher = hashlib.blake2b(digest_size=32)
    for row in rows:
        payload = json.dumps(
            [_logical_value(row.get(field)) for field in fields],
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        hasher.update(payload.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _combined_fingerprint(table_fingerprints: Mapping[str, str]) -> str:
    hasher = hashlib.blake2b(digest_size=32)
    for name in ("chain_groups", "chain_members", "inbound_target_map"):
        hasher.update(f"{name}:{table_fingerprints[name]}\n".encode("ascii"))
    return hasher.hexdigest()


def reconstruct_records(
    records: Iterable[Mapping[str, object]], *, expected_year: int
) -> ReconstructionResult:
    """Reconstruct deterministic schedule context from an in-memory fixture.

    This pure logical path is used by synthetic tests.  The production path
    applies the same normalization and emission contract to a SQLite-ordered
    stream one canonical year at a time.
    """
    assert_derived_schema_safe(
        {
            "chain_groups": CHAIN_GROUP_FIELDS,
            "chain_members": CHAIN_MEMBER_FIELDS,
            "inbound_target_map": INBOUND_TARGET_MAP_FIELDS,
        }
    )
    source_rows = 0
    excluded = Counter()
    seen_keys: set[str] = set()
    normalized: list[_NormalizedMember] = []
    for record in records:
        source_rows += 1
        try:
            normalized.append(
                _normalize_member(
                    record, expected_year=expected_year, seen_keys=seen_keys
                )
            )
        except _NormalizationError as error:
            if error.reason in _FATAL_DATETIME_CONTRACT_REASONS:
                raise ReconstructionValidationError(
                    "Canonical datetime storage contract violation: "
                    f"{error.field}:{error.reason}"
                ) from error
            excluded[f"{error.field}:{error.reason}"] += 1

    normalized.sort(
        key=lambda row: (
            row.group_key,
            row.scheduled_departure,
            row.origin,
            row.dest,
            row.flight_key,
        )
    )

    chain_groups: list[dict[str, Any]] = []
    chain_members: list[dict[str, Any]] = []
    inbound_target_map: list[dict[str, Any]] = []
    ambiguous_chain_count = 0
    ambiguous_timestamp_count = 0
    ambiguous_member_count = 0
    chain_id_groups: dict[str, tuple[int, str, str, str]] = {}

    for group_key, group_iterator in groupby(normalized, key=lambda row: row.group_key):
        group_rows = list(group_iterator)
        chain_id = group_rows[0].chain_id
        previous_group = chain_id_groups.setdefault(chain_id, group_key)
        if previous_group != group_key:
            raise ReconstructionValidationError("chain_id collision across group identities")
        time_counts = Counter(row.scheduled_departure for row in group_rows)
        tied_times = {value for value, count in time_counts.items() if count > 1}
        has_tie = bool(tied_times)
        ambiguous_chain_count += int(has_tie)
        ambiguous_timestamp_count += len(tied_times)
        ambiguous_member_count += sum(time_counts[value] for value in tied_times)
        chain_groups.append(
            {
                "chain_id": chain_id,
                "chain_version": CHAIN_ID_VERSION,
                "source_year": group_key[0],
                "FL_DATE": group_key[1],
                "OP_CARRIER": group_key[2],
                "OP_CARRIER_FL_NUM": group_key[3],
                "member_count": len(group_rows),
                "first_scheduled_departure": group_rows[0].scheduled_departure,
                "last_scheduled_departure": group_rows[-1].scheduled_departure,
                "has_order_tie": has_tie,
            }
        )
        for position, row in enumerate(group_rows):
            is_ambiguous = row.scheduled_departure in tied_times
            member = {
                "chain_id": chain_id,
                "chain_version": CHAIN_ID_VERSION,
                "chain_position": position,
                "flight_key": row.flight_key,
                "schedule_signature": row.schedule_signature,
                "source_year": row.source_year,
                "source_row_number": row.source_row_number,
                "FL_DATE": row.flight_date,
                "OP_CARRIER": row.carrier,
                "OP_CARRIER_FL_NUM": row.flight_number,
                "ORIGIN": row.origin,
                "DEST": row.dest,
                "CRS_DEP_TIME": row.crs_dep_time,
                "CRS_ARR_TIME": row.crs_arr_time,
                "CRS_ELAPSED_TIME": row.crs_elapsed_time,
                "scheduled_departure_timestamp": row.scheduled_departure,
                "is_inbound_atl": row.dest == "ATL",
                "order_ambiguous": is_ambiguous,
            }
            chain_members.append(member)
            if member["is_inbound_atl"]:
                inbound_target_map.append(
                    {
                        "target_flight_key": row.flight_key,
                        "chain_id": chain_id,
                        "chain_position": position,
                        "chain_length": len(group_rows),
                        "source_year": row.source_year,
                    }
                )

    signature_counts = Counter(row["schedule_signature"] for row in chain_members)
    duplicate_signatures = [count for count in signature_counts.values() if count > 1]
    lengths = sorted(int(row["member_count"]) for row in chain_groups)
    length_distribution = {
        "min": lengths[0] if lengths else None,
        "median": median(lengths) if lengths else None,
        "p95": lengths[max(0, math.ceil(0.95 * len(lengths)) - 1)] if lengths else None,
        "max": lengths[-1] if lengths else None,
    }

    table_fingerprints = {
        "chain_groups": _table_fingerprint(chain_groups, CHAIN_GROUP_FIELDS),
        "chain_members": _table_fingerprint(chain_members, CHAIN_MEMBER_FIELDS),
        "inbound_target_map": _table_fingerprint(
            inbound_target_map, INBOUND_TARGET_MAP_FIELDS
        ),
    }
    fingerprints = {
        **table_fingerprints,
        "combined": _combined_fingerprint(table_fingerprints),
    }
    eligible_rows = len(normalized)
    mapped_rows = len(chain_members)
    metrics: dict[str, Any] = {
        "source_rows": source_rows,
        "eligible_source_rows": eligible_rows,
        "mapped_rows": mapped_rows,
        "excluded_rows": source_rows - eligible_rows,
        "exclusion_reasons": dict(sorted(excluded.items())),
        "chain_count": len(chain_groups),
        "inbound_target_count": len(inbound_target_map),
        "ambiguous_chain_count": ambiguous_chain_count,
        "ambiguous_timestamp_count": ambiguous_timestamp_count,
        "ambiguous_member_count": ambiguous_member_count,
        "duplicate_schedule_signature_count": len(duplicate_signatures),
        "duplicate_schedule_signature_excess_rows": sum(
            count - 1 for count in duplicate_signatures
        ),
        "chains_over_max_context_length": sum(length > 6 for length in lengths),
        "chain_length_distribution": length_distribution,
        "duplicate_flight_key_count": 0,
        "invalid_chain_id_count": 0,
        "multi_chain_membership_count": 0,
        "unmapped_eligible_rows": eligible_rows - mapped_rows,
        "eligible_coverage": (mapped_rows / eligible_rows) if eligible_rows else 1.0,
    }
    if mapped_rows != eligible_rows:
        raise ReconstructionValidationError("membership coverage gate failed")
    return ReconstructionResult(
        chain_groups=chain_groups,
        chain_members=chain_members,
        inbound_target_map=inbound_target_map,
        metrics=metrics,
        fingerprints=fingerprints,
    )


_CANONICAL_INPUT_FIELDS: Final = (
    "source_year",
    "source_row_number",
    "flight_key",
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "ORIGIN",
    "DEST",
    "CRS_DEP_TIME",
    "CRS_ARR_TIME",
    "CRS_ELAPSED_TIME",
)


def _arrow_dependencies() -> tuple[Any, Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.dataset as ds
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - guarded by dependency tests
        raise RuntimeError("Reconstruction requires PyArrow.") from error
    return pa, ds, pq


def _arrow_schemas(pa: Any) -> dict[str, Any]:
    return {
        "chain_groups": pa.schema(
            [
                ("chain_id", pa.string()),
                ("chain_version", pa.string()),
                ("source_year", pa.int64()),
                ("FL_DATE", pa.string()),
                ("OP_CARRIER", pa.string()),
                ("OP_CARRIER_FL_NUM", pa.string()),
                ("member_count", pa.int64()),
                ("first_scheduled_departure", pa.timestamp("us")),
                ("last_scheduled_departure", pa.timestamp("us")),
                ("has_order_tie", pa.bool_()),
            ]
        ),
        "chain_members": pa.schema(
            [
                ("chain_id", pa.string()),
                ("chain_version", pa.string()),
                ("chain_position", pa.int64()),
                ("flight_key", pa.string()),
                ("schedule_signature", pa.string()),
                ("source_year", pa.int64()),
                ("source_row_number", pa.int64()),
                ("FL_DATE", pa.string()),
                ("OP_CARRIER", pa.string()),
                ("OP_CARRIER_FL_NUM", pa.string()),
                ("ORIGIN", pa.string()),
                ("DEST", pa.string()),
                ("CRS_DEP_TIME", pa.string()),
                ("CRS_ARR_TIME", pa.string()),
                ("CRS_ELAPSED_TIME", pa.float64()),
                ("scheduled_departure_timestamp", pa.timestamp("us")),
                ("is_inbound_atl", pa.bool_()),
                ("order_ambiguous", pa.bool_()),
            ]
        ),
        "inbound_target_map": pa.schema(
            [
                ("target_flight_key", pa.string()),
                ("chain_id", pa.string()),
                ("chain_position", pa.int64()),
                ("chain_length", pa.int64()),
                ("source_year", pa.int64()),
            ]
        ),
    }


class _LogicalParquetWriter:
    def __init__(
        self,
        *,
        pa: Any,
        pq: Any,
        destination: Path,
        schema: Any,
        fields: tuple[str, ...],
        batch_size: int,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._pa = pa
        self._schema = schema
        self._fields = fields
        self._batch_size = batch_size
        self._buffer: list[dict[str, Any]] = []
        self._writer = pq.ParquetWriter(destination, schema, compression="zstd")
        self._hasher = hashlib.blake2b(digest_size=32)
        self.count = 0

    def append(self, row: dict[str, Any]) -> None:
        payload = json.dumps(
            [_logical_value(row.get(field)) for field in self._fields],
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        self._hasher.update(payload.encode("utf-8"))
        self._hasher.update(b"\n")
        self._buffer.append(row)
        self.count += 1
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        table = self._pa.Table.from_pylist(self._buffer, schema=self._schema)
        self._writer.write_table(table)
        self._buffer.clear()

    def close(self) -> str:
        self.flush()
        self._writer.close()
        return self._hasher.hexdigest()


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _percentile_from_histogram(histogram: Mapping[int, int], fraction: float) -> int | None:
    total = sum(histogram.values())
    if not total:
        return None
    target = math.ceil(total * fraction)
    cumulative = 0
    for value in sorted(histogram):
        cumulative += histogram[value]
        if cumulative >= target:
            return value
    raise AssertionError("unreachable percentile state")


class FlightChainReconstructor:
    """Memory-bounded PyArrow/SQLite reconstruction for one year at a time."""

    def __init__(
        self,
        *,
        project_root: Path,
        output_root: Path,
        chunk_size: int = 100_000,
        max_rows: int | None = None,
        dry_run: bool = False,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if max_rows is not None and max_rows <= 0:
            raise ValueError("max_rows must be positive when provided")
        self.project_root = Path(project_root).resolve()
        self.output_root = assert_output_path_safe(
            Path(output_root), project_root=self.project_root
        )
        self.chunk_size = chunk_size
        self.max_rows = max_rows
        self.dry_run = dry_run

    def _final_year_paths(self, year: int) -> dict[str, Path]:
        return {
            table_name: self.output_root / table_name / f"year={year}"
            for table_name in (
                "chain_groups",
                "chain_members",
                "inbound_target_map",
            )
        }

    def _assert_year_outputs_absent(self, year: int) -> None:
        existing = [
            path for path in self._final_year_paths(year).values() if path.exists()
        ]
        if existing:
            raise FileExistsError(
                f"Generated output already exists for year={year}; refusing to overwrite: "
                f"{[path.as_posix() for path in existing]}"
            )

    def _verify_flight_number_semantics(self, input_schema: Any) -> dict[str, Any]:
        field = input_schema.field("OP_CARRIER_FL_NUM")
        if str(field.type) != "double":
            raise ReconstructionValidationError(
                "OP_CARRIER_FL_NUM canonical storage type contradicts float64 contract: "
                f"{field.type}"
            )
        manifest_path = (
            self.project_root / "artifacts" / "manifests" / "canonical_schema_v1.json"
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata = manifest["fields"]["OP_CARRIER_FL_NUM"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ReconstructionValidationError(
                "Cannot verify OP_CARRIER_FL_NUM canonical semantics metadata"
            ) from error
        if metadata.get("storage_dtype") != "float64":
            raise ReconstructionValidationError(
                "OP_CARRIER_FL_NUM manifest contradicts float64 canonical contract"
            )
        return {
            "field": "OP_CARRIER_FL_NUM",
            "meaning": "operating_carrier_flight_number",
            "canonical_storage_dtype": "float64",
            "normalized_representation": "integral_base10_string",
            "encoded_raw_chain_values_used": False,
            "evidence": [
                "docs/dataset_audit/data_dictionary_v1.md",
                "docs/dataset_audit/flight_chain_feasibility_report.md",
                "artifacts/manifests/canonical_schema_v1.json",
            ],
        }

    @staticmethod
    def _create_staging_database(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute(
            """
            CREATE TABLE staged_rows (
                flight_key TEXT PRIMARY KEY,
                source_year INTEGER NOT NULL,
                source_row_number INTEGER NOT NULL,
                flight_date TEXT NOT NULL,
                carrier TEXT NOT NULL,
                flight_number TEXT NOT NULL,
                origin TEXT NOT NULL,
                dest TEXT NOT NULL,
                crs_dep_time TEXT NOT NULL,
                crs_arr_time TEXT,
                crs_elapsed_time REAL,
                scheduled_departure TEXT NOT NULL,
                schedule_signature TEXT NOT NULL,
                chain_id TEXT NOT NULL
            ) WITHOUT ROWID
            """
        )
        connection.execute(
            """
            CREATE INDEX idx_staged_order ON staged_rows (
                source_year, flight_date, carrier, flight_number,
                scheduled_departure, origin, dest, flight_key
            )
            """
        )
        connection.commit()
        return connection

    @staticmethod
    def _insert_tuple(row: _NormalizedMember) -> tuple[Any, ...]:
        return (
            row.flight_key,
            row.source_year,
            row.source_row_number,
            row.flight_date,
            row.carrier,
            row.flight_number,
            row.origin,
            row.dest,
            row.crs_dep_time,
            row.crs_arr_time,
            row.crs_elapsed_time,
            row.scheduled_departure.isoformat(timespec="microseconds"),
            row.schedule_signature,
            row.chain_id,
        )

    @staticmethod
    def _row_to_member(row: sqlite3.Row) -> _NormalizedMember:
        return _NormalizedMember(
            group_key=(
                int(row["source_year"]),
                str(row["flight_date"]),
                str(row["carrier"]),
                str(row["flight_number"]),
            ),
            chain_id=str(row["chain_id"]),
            flight_key=str(row["flight_key"]),
            source_year=int(row["source_year"]),
            source_row_number=int(row["source_row_number"]),
            flight_date=str(row["flight_date"]),
            carrier=str(row["carrier"]),
            flight_number=str(row["flight_number"]),
            origin=str(row["origin"]),
            dest=str(row["dest"]),
            crs_dep_time=str(row["crs_dep_time"]),
            crs_arr_time=row["crs_arr_time"],
            crs_elapsed_time=row["crs_elapsed_time"],
            scheduled_departure=datetime.fromisoformat(row["scheduled_departure"]),
            schedule_signature=str(row["schedule_signature"]),
        )

    def _ingest(
        self,
        *,
        year: int,
        dataset: Any,
        connection: sqlite3.Connection,
        staging_root: Path,
    ) -> tuple[dict[str, Any], int]:
        scanner = dataset.scanner(
            columns=list(_CANONICAL_INPUT_FIELDS),
            batch_size=self.chunk_size,
            use_threads=False,
            batch_readahead=1,
            fragment_readahead=1,
        )
        source_rows = 0
        eligible_rows = 0
        flight_number_values_observed = 0
        excluded = Counter()
        peak_staging = _directory_size(staging_root)
        insert_sql = (
            "INSERT INTO staged_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for batch in scanner.to_batches():
            if self.max_rows is not None:
                remaining = self.max_rows - source_rows
                if remaining <= 0:
                    break
                if len(batch) > remaining:
                    batch = batch.slice(0, remaining)
            inserts: list[tuple[Any, ...]] = []
            for record in batch.to_pylist():
                source_rows += 1
                try:
                    normalize_flight_number(record.get("OP_CARRIER_FL_NUM"))
                except _NormalizationError as error:
                    if error.reason != "missing":
                        flight_number_values_observed += 1
                    excluded[f"{error.field}:{error.reason}"] += 1
                    continue
                flight_number_values_observed += 1
                try:
                    member = _normalize_member(
                        record, expected_year=year, seen_keys=None
                    )
                except _NormalizationError as error:
                    excluded[f"{error.field}:{error.reason}"] += 1
                    continue
                inserts.append(self._insert_tuple(member))
            try:
                connection.executemany(insert_sql, inserts)
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ReconstructionValidationError(
                    "duplicate flight_key detected during SQLite staging"
                ) from error
            eligible_rows += len(inserts)
            peak_staging = max(peak_staging, _directory_size(staging_root))
            if self.max_rows is not None and source_rows >= self.max_rows:
                break

        contradictory_reasons = {
            key: value
            for key, value in excluded.items()
            if key.startswith("OP_CARRIER_FL_NUM:")
            and not key.endswith(":missing")
        }
        if contradictory_reasons:
            raise ReconstructionValidationError(
                "OP_CARRIER_FL_NUM values contradict integral flight-number semantics: "
                f"{dict(sorted(contradictory_reasons.items()))}"
            )
        fatal_datetime_reasons = {
            key: value
            for key, value in excluded.items()
            if key.split(":", maxsplit=1)[-1]
            in _FATAL_DATETIME_CONTRACT_REASONS
        }
        if fatal_datetime_reasons:
            raise ReconstructionValidationError(
                "Canonical datetime storage contract violation: "
                f"{dict(sorted(fatal_datetime_reasons.items()))}"
            )
        observed_count = int(
            connection.execute("SELECT COUNT(*) FROM staged_rows").fetchone()[0]
        )
        if observed_count != eligible_rows:
            raise ReconstructionValidationError("SQLite staged row count mismatch")
        if source_rows and eligible_rows == 0:
            raise ReconstructionValidationError(
                "Canonical partition has source rows but no eligible members; "
                f"normalization contract may be contradicted: {dict(sorted(excluded.items()))}"
            )
        return (
            {
                "source_rows": source_rows,
                "eligible_source_rows": eligible_rows,
                "excluded_rows": source_rows - eligible_rows,
                "exclusion_reasons": dict(sorted(excluded.items())),
                "flight_number_values_observed": flight_number_values_observed,
                "flight_number_missing_count": excluded.get(
                    "OP_CARRIER_FL_NUM:missing", 0
                ),
            },
            peak_staging,
        )

    def _write_staged_outputs(
        self,
        *,
        year: int,
        connection: sqlite3.Connection,
        staging_root: Path,
        ingestion_metrics: dict[str, Any],
        pa: Any,
        pq: Any,
    ) -> tuple[dict[str, Any], dict[str, str], dict[str, Path], int]:
        schemas = _arrow_schemas(pa)
        fields_by_table = {
            "chain_groups": CHAIN_GROUP_FIELDS,
            "chain_members": CHAIN_MEMBER_FIELDS,
            "inbound_target_map": INBOUND_TARGET_MAP_FIELDS,
        }
        assert_derived_schema_safe(fields_by_table)
        staged_paths = {
            name: staging_root
            / "publish"
            / name
            / f"year={year}"
            / "part-00000.parquet"
            for name in fields_by_table
        }
        writers = {
            name: _LogicalParquetWriter(
                pa=pa,
                pq=pq,
                destination=staged_paths[name],
                schema=schemas[name],
                fields=fields_by_table[name],
                batch_size=self.chunk_size,
            )
            for name in fields_by_table
        }
        ambiguous_chains = 0
        ambiguous_timestamps = 0
        ambiguous_members = 0
        duplicate_signature_count = 0
        duplicate_signature_excess = 0
        length_histogram: Counter[int] = Counter()
        chains_over_six = 0

        query = """
            SELECT source_year, source_row_number, flight_key, flight_date,
                   carrier, flight_number, origin, dest, crs_dep_time,
                   crs_arr_time, crs_elapsed_time, scheduled_departure,
                   schedule_signature, chain_id
            FROM staged_rows
            ORDER BY source_year, flight_date, carrier, flight_number,
                     scheduled_departure, origin, dest, flight_key
        """
        stream = (self._row_to_member(row) for row in connection.execute(query))
        try:
            for group_key, group_iterator in groupby(stream, key=lambda row: row.group_key):
                group_rows = list(group_iterator)
                chain_id = group_rows[0].chain_id
                if any(row.chain_id != chain_id for row in group_rows):
                    raise ReconstructionValidationError(
                        "one group identity produced multiple chain IDs"
                    )
                time_counts = Counter(row.scheduled_departure for row in group_rows)
                tied_times = {value for value, count in time_counts.items() if count > 1}
                ambiguous_chains += int(bool(tied_times))
                ambiguous_timestamps += len(tied_times)
                ambiguous_members += sum(time_counts[value] for value in tied_times)
                signature_counts = Counter(row.schedule_signature for row in group_rows)
                duplicate_counts = [
                    count for count in signature_counts.values() if count > 1
                ]
                duplicate_signature_count += len(duplicate_counts)
                duplicate_signature_excess += sum(count - 1 for count in duplicate_counts)
                chain_length = len(group_rows)
                length_histogram[chain_length] += 1
                chains_over_six += int(chain_length > 6)
                writers["chain_groups"].append(
                    {
                        "chain_id": chain_id,
                        "chain_version": CHAIN_ID_VERSION,
                        "source_year": group_key[0],
                        "FL_DATE": group_key[1],
                        "OP_CARRIER": group_key[2],
                        "OP_CARRIER_FL_NUM": group_key[3],
                        "member_count": chain_length,
                        "first_scheduled_departure": group_rows[0].scheduled_departure,
                        "last_scheduled_departure": group_rows[-1].scheduled_departure,
                        "has_order_tie": bool(tied_times),
                    }
                )
                for position, row in enumerate(group_rows):
                    order_ambiguous = row.scheduled_departure in tied_times
                    writers["chain_members"].append(
                        {
                            "chain_id": chain_id,
                            "chain_version": CHAIN_ID_VERSION,
                            "chain_position": position,
                            "flight_key": row.flight_key,
                            "schedule_signature": row.schedule_signature,
                            "source_year": row.source_year,
                            "source_row_number": row.source_row_number,
                            "FL_DATE": row.flight_date,
                            "OP_CARRIER": row.carrier,
                            "OP_CARRIER_FL_NUM": row.flight_number,
                            "ORIGIN": row.origin,
                            "DEST": row.dest,
                            "CRS_DEP_TIME": row.crs_dep_time,
                            "CRS_ARR_TIME": row.crs_arr_time,
                            "CRS_ELAPSED_TIME": row.crs_elapsed_time,
                            "scheduled_departure_timestamp": row.scheduled_departure,
                            "is_inbound_atl": row.dest == "ATL",
                            "order_ambiguous": order_ambiguous,
                        }
                    )
                    if row.dest == "ATL":
                        writers["inbound_target_map"].append(
                            {
                                "target_flight_key": row.flight_key,
                                "chain_id": chain_id,
                                "chain_position": position,
                                "chain_length": chain_length,
                                "source_year": row.source_year,
                            }
                        )
            table_fingerprints = {
                name: writer.close() for name, writer in writers.items()
            }
        except BaseException:
            for writer in writers.values():
                try:
                    writer.close()
                except BaseException:
                    pass
            raise

        mapped_rows = writers["chain_members"].count
        eligible_rows = int(ingestion_metrics["eligible_source_rows"])
        if mapped_rows != eligible_rows:
            raise ReconstructionValidationError("membership coverage gate failed")
        minimum = min(length_histogram) if length_histogram else None
        maximum = max(length_histogram) if length_histogram else None
        metrics = {
            **ingestion_metrics,
            "mapped_rows": mapped_rows,
            "chain_count": writers["chain_groups"].count,
            "inbound_target_count": writers["inbound_target_map"].count,
            "ambiguous_chain_count": ambiguous_chains,
            "ambiguous_timestamp_count": ambiguous_timestamps,
            "ambiguous_member_count": ambiguous_members,
            "duplicate_schedule_signature_count": duplicate_signature_count,
            "duplicate_schedule_signature_excess_rows": duplicate_signature_excess,
            "chains_over_max_context_length": chains_over_six,
            "chain_length_distribution": {
                "min": minimum,
                "median": _percentile_from_histogram(length_histogram, 0.5),
                "p95": _percentile_from_histogram(length_histogram, 0.95),
                "max": maximum,
            },
            "duplicate_flight_key_count": 0,
            "invalid_chain_id_count": 0,
            "multi_chain_membership_count": 0,
            "unmapped_eligible_rows": eligible_rows - mapped_rows,
            "eligible_coverage": (mapped_rows / eligible_rows) if eligible_rows else 1.0,
        }
        fingerprints = {
            **table_fingerprints,
            "combined": _combined_fingerprint(table_fingerprints),
        }
        return metrics, fingerprints, staged_paths, _directory_size(staging_root)

    @staticmethod
    def _validate_parquet_outputs(
        *,
        pq: Any,
        staged_paths: Mapping[str, Path],
        metrics: Mapping[str, Any],
    ) -> None:
        schemas = {
            "chain_groups": CHAIN_GROUP_FIELDS,
            "chain_members": CHAIN_MEMBER_FIELDS,
            "inbound_target_map": INBOUND_TARGET_MAP_FIELDS,
        }
        expected_counts = {
            "chain_groups": metrics["chain_count"],
            "chain_members": metrics["mapped_rows"],
            "inbound_target_map": metrics["inbound_target_count"],
        }
        for name, path in staged_paths.items():
            parquet = pq.ParquetFile(path)
            if parquet.metadata.num_rows != expected_counts[name]:
                raise ReconstructionValidationError(
                    f"Parquet row count mismatch for {name}"
                )
            if parquet.schema_arrow.names != list(schemas[name]):
                raise ReconstructionValidationError(
                    f"Parquet schema mismatch for {name}"
                )

    def _publish(self, *, year: int, staged_paths: Mapping[str, Path]) -> dict[str, str]:
        outputs: dict[str, str] = {}
        for name, source_file in staged_paths.items():
            source_year_root = source_file.parent
            destination = self._final_year_paths(year)[name]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_year_root), str(destination))
            outputs[name] = destination.relative_to(self.project_root).as_posix()
        return outputs

    def reconstruct_year(self, year: int) -> dict[str, Any]:
        """Reconstruct and validate one canonical development year."""
        assert_reconstruction_year_allowed(year)
        self._assert_year_outputs_absent(year)
        pa, ds, pq = _arrow_dependencies()
        input_root = (
            self.project_root
            / "data"
            / "processed"
            / "tabular_by_year"
            / f"year={year}"
        )
        files = sorted(input_root.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No canonical Parquet parts found: {input_root}")
        source_partition_rows = sum(
            pq.ParquetFile(path).metadata.num_rows for path in files
        )
        input_bytes = sum(path.stat().st_size for path in files)
        dataset = ds.dataset(input_root, format="parquet")
        missing = set(_CANONICAL_INPUT_FIELDS).difference(dataset.schema.names)
        if missing:
            raise ReconstructionValidationError(
                f"Canonical partition is missing required fields: {sorted(missing)}"
            )
        flight_number_semantics = self._verify_flight_number_semantics(dataset.schema)
        self.output_root.mkdir(parents=True, exist_ok=True)
        disk_free_before = shutil.disk_usage(self.output_root).free
        staging_root = (
            self.output_root
            / ".staging"
            / f"year={year}-{uuid.uuid4().hex}"
        )
        staging_root.mkdir(parents=True)
        staging_db = staging_root / "staging.sqlite3"
        raw_before = snapshot_raw_inventory(self.project_root)
        started = time_module.perf_counter()
        tracemalloc.start()
        connection: sqlite3.Connection | None = None
        peak_staging = 0
        try:
            connection = self._create_staging_database(staging_db)
            ingestion_metrics, peak_staging = self._ingest(
                year=year,
                dataset=dataset,
                connection=connection,
                staging_root=staging_root,
            )
            index_names = sorted(
                row[1]
                for row in connection.execute("PRAGMA index_list(staged_rows)").fetchall()
            )
            metrics, fingerprints, staged_paths, output_peak = self._write_staged_outputs(
                year=year,
                connection=connection,
                staging_root=staging_root,
                ingestion_metrics=ingestion_metrics,
                pa=pa,
                pq=pq,
            )
            peak_staging = max(peak_staging, output_peak, _directory_size(staging_root))
            self._validate_parquet_outputs(
                pq=pq, staged_paths=staged_paths, metrics=metrics
            )
            output_bytes = sum(path.stat().st_size for path in staged_paths.values())
            assert_raw_inventory_unchanged(
                raw_before, snapshot_raw_inventory(self.project_root)
            )
            outputs = {} if self.dry_run else self._publish(
                year=year, staged_paths=staged_paths
            )
            assert_raw_inventory_unchanged(
                raw_before, snapshot_raw_inventory(self.project_root)
            )
            current_python, peak_python = tracemalloc.get_traced_memory()
            runtime_seconds = time_module.perf_counter() - started
            sqlite_bytes = staging_db.stat().st_size
            result = {
                "year": year,
                "status": "PASS_DRY_RUN" if self.dry_run else "PASS",
                "is_complete": metrics["source_rows"] == source_partition_rows,
                "source_partition_rows": source_partition_rows,
                "max_rows": self.max_rows,
                "reconstruction_version": CHAIN_ID_VERSION,
                "datetime_storage_amendment_version": (
                    DATETIME_STORAGE_AMENDMENT_VERSION
                ),
                "flight_key_version": FLIGHT_KEY_VERSION,
                "physical_aircraft_identity": PHYSICAL_AIRCRAFT_IDENTITY,
                "flight_number_semantics": {
                    **flight_number_semantics,
                    "status": "VERIFIED",
                    "observed_value_count": metrics[
                        "flight_number_values_observed"
                    ],
                    "observed_missing_count": metrics[
                        "flight_number_missing_count"
                    ],
                    "observed_non_integral_count": 0,
                },
                "metrics": metrics,
                "fingerprints": fingerprints,
                "outputs": outputs,
                "resource_usage": {
                    "runtime_seconds": runtime_seconds,
                    "rows_per_second": (
                        metrics["source_rows"] / runtime_seconds
                        if runtime_seconds
                        else None
                    ),
                    "input_bytes": input_bytes,
                    "output_bytes": output_bytes,
                    "peak_staging_bytes": peak_staging,
                    "peak_sqlite_bytes": sqlite_bytes,
                    "peak_python_allocation_bytes": peak_python,
                    "current_python_allocation_bytes": current_python,
                    "python_allocation_caveat": (
                        "tracemalloc excludes some native PyArrow allocations"
                    ),
                    "disk_free_before_bytes": disk_free_before,
                    "disk_free_after_bytes": shutil.disk_usage(self.output_root).free,
                },
                "staging": {
                    "path": str(staging_root),
                    "database": str(staging_db),
                    "index_names": index_names,
                    "removed_after_pass": True,
                },
                "raw_integrity": {
                    "file_count": len(raw_before),
                    "path_size_mtime_unchanged": True,
                },
            }
            connection.close()
            connection = None
            shutil.rmtree(staging_root)
            return result
        except BaseException as error:
            if connection is not None:
                connection.close()
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            if isinstance(error, ReconstructionStagingError):
                raise
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise ReconstructionStagingError(
                str(error), staging_path=staging_root
            ) from error
        finally:
            if tracemalloc.is_tracing():
                tracemalloc.stop()

    def reconstruct_years(self, years: Iterable[int]) -> dict[str, Any]:
        """Run requested years sequentially without concatenating annual data."""
        requested = list(years)
        if not requested:
            raise ValueError("At least one year is required")
        raw_before = snapshot_raw_inventory(self.project_root)
        entries = [self.reconstruct_year(year) for year in requested]
        assert_raw_inventory_unchanged(
            raw_before, snapshot_raw_inventory(self.project_root)
        )
        return {
            "artifact": "reconstructed_schedule_flight_chain",
            "version": "v1",
            "datetime_storage_amendment_version": (
                DATETIME_STORAGE_AMENDMENT_VERSION
            ),
            "source": "canonical_tabular",
            "raw_chain_used_for_mapping": False,
            "physical_aircraft_identity": PHYSICAL_AIRCRAFT_IDENTITY,
            "dependencies": dependency_versions(),
            "years": entries,
            "overall_status": (
                "FULL_DATA_PASS"
                if requested == list(range(2016, 2024))
                and all(entry["is_complete"] for entry in entries)
                else "PARTIAL_DATA_PASS"
            ),
        }
