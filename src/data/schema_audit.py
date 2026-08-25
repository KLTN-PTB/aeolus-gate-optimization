"""Memory-bounded schema auditing for one Aeolus Tabular year at a time.

This module reports observed structure and data-quality metadata. It does not make
feature-safety decisions, preprocess records, or write into raw-data folders.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import logging
import math
import sqlite3
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.data.load_aeolus import (
    TabularChunk,
    iter_tabular_chunks,
    load_base_config,
    read_tabular_header,
    resolve_project_root,
    resolve_tabular_csv,
)


AUDIT_VERSION = "0.1.0"
DEFAULT_CHUNK_SIZE = 100_000
WEATHER_NAME_TOKENS = ("TEMP", "PRCP", "WSPD", "WEATHER", "WX")
CATEGORY_COLUMNS = ("OP_CARRIER", "ORIGIN", "DEST", "ORIGIN_INDEX", "DEST_INDEX")


def _logger() -> logging.Logger:
    logger = logging.getLogger("aeolus.schema_audit")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def _is_missing(value: str | None) -> bool:
    return value is None or not value.strip() or value.strip().casefold() in {"na", "nan", "null", "none"}


def _parse_float(value: str | None) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _infer_value_kind(value: str | None) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    try:
        int(text)
        return "integer"
    except ValueError:
        pass
    try:
        float(text)
        return "float"
    except ValueError:
        return "string"


def _summarize_kinds(kinds: set[str]) -> str:
    if not kinds:
        return "all_missing"
    if kinds == {"integer"}:
        return "integer"
    if kinds.issubset({"integer", "float"}):
        return "float"
    return "string"


def _parse_flight_date(value: str | None) -> datetime | None:
    if _is_missing(value):
        return None
    try:
        return datetime.fromisoformat(str(value).strip()).replace(tzinfo=None)
    except ValueError:
        return None


def _row_digest(row: Mapping[str, str | None], columns: Iterable[str]) -> str:
    payload = json.dumps(
        ["" if row.get(column) is None else str(row.get(column)) for column in columns],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


class _SQLiteAuditStore:
    """Disk-backed exact category counting and bounded-memory duplicate indicator."""

    def __init__(self, temporary_root: Path) -> None:
        temporary_root.mkdir(parents=True, exist_ok=True)
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="aeolus_schema_audit_", dir=temporary_root
        )
        self._database_path = Path(self._temporary_directory.name) / "audit.sqlite3"
        self.connection = sqlite3.connect(self._database_path)
        # This is a disposable, per-year audit cache.  Keeping it on disk gives
        # duplicate detection a bounded RAM profile even for multi-million-row
        # CSVs.  Durability is unnecessary because the cache is discarded after
        # a summary has been written.
        self.connection.execute("PRAGMA journal_mode=OFF")
        self.connection.execute("PRAGMA synchronous=OFF")
        self.connection.execute("PRAGMA temp_store=FILE")
        self.connection.execute(
            "CREATE TABLE category_values (field TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(field, value))"
        )
        self.connection.execute("CREATE TABLE row_hashes (digest TEXT PRIMARY KEY)")

    def add_categories(self, field: str, values: Iterable[str]) -> None:
        self.connection.executemany(
            "INSERT OR IGNORE INTO category_values(field, value) VALUES (?, ?)",
            ((field, value) for value in values),
        )

    def add_row_hashes(self, digests: Iterable[str]) -> int:
        before = self.connection.total_changes
        self.connection.executemany(
            "INSERT OR IGNORE INTO row_hashes(digest) VALUES (?)",
            ((digest,) for digest in digests),
        )
        return self.connection.total_changes - before

    def commit(self) -> None:
        self.connection.commit()

    def cardinality(self, field: str) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM category_values WHERE field = ?", (field,)
            ).fetchone()[0]
        )

    def close(self) -> None:
        self.connection.close()
        self._temporary_directory.cleanup()


def _source_signature(source: Path, project_root: Path) -> dict[str, Any]:
    stat = source.stat()
    return {
        "source_relative_path": source.resolve().relative_to(project_root.resolve()).as_posix(),
        "file_size_bytes": stat.st_size,
        "modified_time_ns": stat.st_mtime_ns,
        "modified_time_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _load_reference(reference_schema: Mapping[str, Any] | Path | None) -> Mapping[str, Any] | None:
    if reference_schema is None:
        return None
    if isinstance(reference_schema, Path):
        with reference_schema.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, Mapping):
            raise ValueError("Reference schema JSON must be an object")
        return loaded
    return reference_schema


def compare_schema(
    columns: list[str], observed_dtypes: Mapping[str, str], reference_schema: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """Describe differences only; never classify fields as safe or unsafe."""
    if reference_schema is None:
        return None
    reference_columns = list(reference_schema.get("columns", []))
    reference_dtypes = reference_schema.get("observed_dtypes", {})
    if not isinstance(reference_dtypes, Mapping):
        reference_dtypes = {}
    shared = [column for column in columns if column in reference_columns]
    return {
        "reference_provided": True,
        "missing_from_observed": [column for column in reference_columns if column not in columns],
        "extra_in_observed": [column for column in columns if column not in reference_columns],
        "column_order_matches": columns == reference_columns,
        "dtype_differences": {
            column: {"observed": observed_dtypes[column], "reference": reference_dtypes[column]}
            for column in shared
            if column in reference_dtypes and observed_dtypes[column] != reference_dtypes[column]
        },
    }


class SchemaAuditor:
    """Audit a year by streaming CSV chunks and writing a resumable JSON summary."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        config_path: Path | None = None,
        manifest_directory: Path | None = None,
        audit_version: str = AUDIT_VERSION,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.config_path = config_path
        self.config = load_base_config(project_root=self.project_root, config_path=config_path)
        self.audit_version = audit_version
        self.config_version = str(self.config.get("project", {}).get("version", "unknown"))
        self.manifest_directory = (
            Path(manifest_directory)
            if manifest_directory is not None
            else self.project_root / "artifacts" / "manifests" / "schema_audit"
        )

    def manifest_path(self, year: int) -> Path:
        return self.manifest_directory / f"schema_{year}.json"

    def _can_resume(self, year: int, signature: Mapping[str, Any], chunk_size: int) -> dict[str, Any] | None:
        path = self.manifest_path(year)
        try:
            with path.open("r", encoding="utf-8") as handle:
                summary = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(summary, dict):
            return None
        expected = {
            "year": year,
            "audit_version": self.audit_version,
            "config_version": self.config_version,
            "chunk_size": chunk_size,
            "source_signature": dict(signature),
            "is_complete": True,
        }
        if all(summary.get(key) == value for key, value in expected.items()):
            summary["resumed"] = True
            return summary
        return None

    def audit_year(
        self,
        year: int,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        reference_schema: Mapping[str, Any] | Path | None = None,
        resume: bool = False,
        max_rows: int | None = None,
        write_summary: bool = True,
    ) -> dict[str, Any]:
        """Audit one year; dry-runs must use ``write_summary=False``.

        A completed summary is written only for a complete scan. This prevents a
        bounded dry-run from being mistaken for a resumable full-year audit.
        """
        if max_rows is not None and write_summary:
            raise ValueError("Dry-run max_rows requires write_summary=False")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        source = resolve_tabular_csv(
            year,
            project_root=self.project_root,
            config_path=self.config_path,
            purpose="schema_audit",
        )
        signature = _source_signature(source, self.project_root)
        if resume and max_rows is None:
            resumed = self._can_resume(year, signature, chunk_size)
            if resumed is not None:
                _logger().info("schema audit resume skip year=%s", year)
                return resumed

        # Pandas is optional: the tested standard-library implementation below
        # remains the compatibility fallback.  When available, its vectorised
        # chunk operations are required for the full 15 GB Week-2 audit.
        try:
            import pandas as pandas  # type: ignore[import-not-found]
        except ImportError:
            pandas = None
        if pandas is not None:
            return self._audit_year_with_pandas(
                year,
                source=source,
                signature=signature,
                chunk_size=chunk_size,
                reference=reference_schema,
                max_rows=max_rows,
                write_summary=write_summary,
                pandas=pandas,
            )

        columns = read_tabular_header(
            year,
            project_root=self.project_root,
            config_path=self.config_path,
            purpose="schema_audit",
        )
        reference = _load_reference(reference_schema)
        missing_counts = {column: 0 for column in columns}
        type_kinds: dict[str, set[str]] = {column: set() for column in columns}
        numeric_nonmissing: dict[str, int] = defaultdict(int)
        numeric_invalid: dict[str, int] = defaultdict(int)
        numeric_inf: dict[str, int] = defaultdict(int)
        total_rows = 0
        chunks_processed = 0
        invalid_date_count = 0
        date_min: datetime | None = None
        date_max: datetime | None = None
        target_available = "ARR_DELAY" in columns
        target_missing = 0
        target_invalid = 0
        target_finite_count = 0
        target_gte_15_count = 0
        target_sum = 0.0
        target_sum_squares = 0.0
        target_min: float | None = None
        target_max: float | None = None
        store = _SQLiteAuditStore(self.manifest_directory / ".temporary")
        duplicate_rows = 0

        started_at = time.perf_counter()
        try:
            for chunk in iter_tabular_chunks(
                year,
                chunk_size=chunk_size,
                project_root=self.project_root,
                config_path=self.config_path,
                max_rows=max_rows,
                purpose="schema_audit",
            ):
                self._process_chunk(
                    chunk,
                    columns=columns,
                    missing_counts=missing_counts,
                    type_kinds=type_kinds,
                    numeric_nonmissing=numeric_nonmissing,
                    numeric_invalid=numeric_invalid,
                    numeric_inf=numeric_inf,
                    store=store,
                )
                for row in chunk.rows:
                    total_rows += 1
                    if "FL_DATE" in columns:
                        parsed_date = _parse_flight_date(row.get("FL_DATE"))
                        if _is_missing(row.get("FL_DATE")):
                            pass
                        elif parsed_date is None:
                            invalid_date_count += 1
                        else:
                            date_min = parsed_date if date_min is None or parsed_date < date_min else date_min
                            date_max = parsed_date if date_max is None or parsed_date > date_max else date_max
                    if target_available:
                        raw_target = row.get("ARR_DELAY")
                        value = _parse_float(raw_target)
                        if _is_missing(raw_target):
                            target_missing += 1
                        elif value is None or not math.isfinite(value):
                            target_invalid += 1
                        else:
                            target_finite_count += 1
                            target_gte_15_count += int(value >= 15)
                            target_sum += value
                            target_sum_squares += value * value
                            target_min = value if target_min is None else min(target_min, value)
                            target_max = value if target_max is None else max(target_max, value)
                inserted = store.add_row_hashes(_row_digest(row, columns) for row in chunk.rows)
                duplicate_rows += len(chunk.rows) - inserted
                store.commit()
                chunks_processed += 1
                _logger().info(
                    "schema audit progress year=%s chunk=%s rows=%s",
                    year,
                    chunk.chunk_number,
                    total_rows,
                )
                del chunk
                gc.collect()
        finally:
            cardinalities = {column: store.cardinality(column) for column in CATEGORY_COLUMNS if column in columns}
            store.close()

        observed_dtypes = {column: _summarize_kinds(type_kinds[column]) for column in columns}
        target_mean = target_sum / target_finite_count if target_finite_count else None
        target_std = None
        if target_finite_count and target_mean is not None:
            variance = max(0.0, (target_sum_squares / target_finite_count) - (target_mean * target_mean))
            target_std = math.sqrt(variance)
        numeric_quality = {
            column: {
                "nonmissing_numeric_count": numeric_nonmissing[column],
                "non_numeric_nonmissing_count": numeric_invalid[column],
                "nan_count": missing_counts[column],
                "inf_count": numeric_inf[column],
            }
            for column in columns
            if observed_dtypes[column] in {"integer", "float"}
        }
        summary: dict[str, Any] = {
            "year": year,
            "audit_version": self.audit_version,
            "config_version": self.config_version,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "chunk_size": chunk_size,
            "source_signature": signature,
            "is_complete": max_rows is None,
            "dry_run_max_rows": max_rows,
            "resumed": False,
            "columns": columns,
            "column_order": columns,
            "column_count": len(columns),
            "observed_dtypes": observed_dtypes,
            "row_count": total_rows,
            "chunks_processed": chunks_processed,
            "missing": {
                column: {
                    "count": missing_counts[column],
                    "rate": (missing_counts[column] / total_rows) if total_rows else None,
                }
                for column in columns
            },
            "fl_date": {
                "available": "FL_DATE" in columns,
                "min": date_min.date().isoformat() if date_min is not None else None,
                "max": date_max.date().isoformat() if date_max is not None else None,
                "invalid_nonmissing_count": invalid_date_count,
            },
            "arr_delay": {
                "available": target_available,
                "missing_count": target_missing if target_available else None,
                "invalid_or_nonfinite_count": target_invalid if target_available else None,
                "finite_count": target_finite_count if target_available else None,
                "distribution": {
                    "min": target_min,
                    "max": target_max,
                    "mean": target_mean,
                    "population_std": target_std,
                }
                if target_available
                else None,
                "gte_15": {
                    "count": target_gte_15_count,
                    "rate_among_finite": (target_gte_15_count / target_finite_count)
                    if target_finite_count
                    else None,
                }
                if target_available
                else None,
            },
            "categorical_cardinality": cardinalities,
            "weather_columns": [
                column for column in columns if any(token in column.upper() for token in WEATHER_NAME_TOKENS)
            ],
            "airport_index": {
                column: {"exists": column in columns, "cardinality": cardinalities.get(column)}
                for column in ("ORIGIN_INDEX", "DEST_INDEX")
            },
            "duplicate_rows": {
                "strategy": "sqlite_blake2b_128_streaming",
                "indicator": duplicate_rows > 0,
                "count": duplicate_rows,
                "collision_caveat": "128-bit digest collision risk is negligible but non-zero.",
            },
            "numeric_quality": numeric_quality,
            "schema_difference": compare_schema(columns, observed_dtypes, reference),
            "runtime_seconds": round(time.perf_counter() - started_at, 3),
        }
        if write_summary:
            self.manifest_directory.mkdir(parents=True, exist_ok=True)
            with self.manifest_path(year).open("w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2, sort_keys=True)
                handle.write("\n")
        return summary

    def _audit_year_with_pandas(
        self,
        year: int,
        *,
        source: Path,
        signature: Mapping[str, Any],
        chunk_size: int,
        reference: Mapping[str, Any] | Path | None,
        max_rows: int | None,
        write_summary: bool,
        pandas: Any,
    ) -> dict[str, Any]:
        """Vectorised, bounded-memory implementation used for full-year scans.

        The CSV is consumed as independent pandas chunks.  Only aggregate
        counters, compact dtype state, and a temporary SQLite hash index survive
        between chunks; no raw record collection is retained.
        """
        columns = read_tabular_header(
            year,
            project_root=self.project_root,
            config_path=self.config_path,
            purpose="schema_audit",
        )
        reference_schema = _load_reference(reference)
        missing_counts = {column: 0 for column in columns}
        dtype_kinds: dict[str, set[str]] = {column: set() for column in columns}
        numeric_nonmissing: dict[str, int] = defaultdict(int)
        numeric_invalid: dict[str, int] = defaultdict(int)
        numeric_inf: dict[str, int] = defaultdict(int)
        total_rows = 0
        chunks_processed = 0
        invalid_date_count = 0
        date_min: Any = None
        date_max: Any = None
        target_available = "ARR_DELAY" in columns
        target_missing = target_invalid = target_finite_count = target_gte_15_count = 0
        target_sum = target_sum_squares = 0.0
        target_min: float | None = None
        target_max: float | None = None
        duplicate_rows = 0
        started_at = time.perf_counter()
        store = _SQLiteAuditStore(self.manifest_directory / ".temporary")

        def missing_mask(series: Any) -> Any:
            text = series.astype("string").str.strip().str.casefold()
            return series.isna() | text.isin(("", "na", "nan", "null", "none"))

        def dtype_kind(series: Any) -> str:
            api = pandas.api.types
            if api.is_integer_dtype(series.dtype):
                return "integer"
            if api.is_float_dtype(series.dtype):
                return "float"
            if api.is_bool_dtype(series.dtype):
                return "boolean"
            if api.is_datetime64_any_dtype(series.dtype):
                return "datetime"
            return "string"

        remaining = max_rows
        try:
            reader = pandas.read_csv(source, chunksize=chunk_size, low_memory=False)
            for raw_chunk in reader:
                if remaining is not None:
                    if remaining <= 0:
                        break
                    chunk = raw_chunk.iloc[:remaining].copy()
                    remaining -= len(chunk)
                else:
                    chunk = raw_chunk
                if chunk.empty:
                    continue

                chunk_rows = len(chunk)
                total_rows += chunk_rows
                chunks_processed += 1
                for column in columns:
                    series = chunk[column]
                    mask = missing_mask(series)
                    missing_counts[column] += int(mask.sum())
                    dtype_kinds[column].add(dtype_kind(series))
                    if pandas.api.types.is_numeric_dtype(series.dtype):
                        values = pandas.to_numeric(series, errors="coerce")
                        numeric_nonmissing[column] += int((~mask).sum())
                        numeric_invalid[column] += int(((~mask) & values.isna()).sum())
                        if pandas.api.types.is_float_dtype(values.dtype):
                            numeric_inf[column] += int(pandas.Series(values).isin((float("inf"), float("-inf"))).sum())

                if "FL_DATE" in columns:
                    original_dates = chunk["FL_DATE"]
                    date_missing = missing_mask(original_dates)
                    parsed_dates = pandas.to_datetime(original_dates, errors="coerce", format="mixed")
                    invalid_date_count += int(((~date_missing) & parsed_dates.isna()).sum())
                    valid_dates = parsed_dates.dropna()
                    if not valid_dates.empty:
                        local_min, local_max = valid_dates.min(), valid_dates.max()
                        date_min = local_min if date_min is None or local_min < date_min else date_min
                        date_max = local_max if date_max is None or local_max > date_max else date_max

                if target_available:
                    original_target = chunk["ARR_DELAY"]
                    target_mask = missing_mask(original_target)
                    values = pandas.to_numeric(original_target, errors="coerce")
                    finite = values.notna() & ~values.isin((float("inf"), float("-inf")))
                    target_missing += int(target_mask.sum())
                    target_invalid += int(((~target_mask) & ~finite).sum())
                    finite_values = values[finite]
                    if not finite_values.empty:
                        target_finite_count += len(finite_values)
                        target_gte_15_count += int((finite_values >= 15).sum())
                        target_sum += float(finite_values.sum())
                        target_sum_squares += float((finite_values * finite_values).sum())
                        local_min, local_max = float(finite_values.min()), float(finite_values.max())
                        target_min = local_min if target_min is None else min(target_min, local_min)
                        target_max = local_max if target_max is None else max(target_max, local_max)

                for column in CATEGORY_COLUMNS:
                    if column in columns:
                        values = chunk.loc[~missing_mask(chunk[column]), column].astype("string").str.strip().unique()
                        store.add_categories(column, (str(value) for value in values))

                # Two independent 64-bit vectorised hashes are persisted in a
                # disk-backed SQLite index.  This detects cross-chunk duplicate
                # rows without retaining raw rows in RAM.
                first = pandas.util.hash_pandas_object(chunk, index=False, hash_key="0123456789abcdef")
                second = pandas.util.hash_pandas_object(chunk, index=False, hash_key="fedcba9876543210")
                digests = (f"{int(a):016x}{int(b):016x}" for a, b in zip(first, second))
                inserted = store.add_row_hashes(digests)
                duplicate_rows += chunk_rows - inserted
                store.commit()
                _logger().info(
                    "schema audit progress year=%s chunk=%s rows=%s",
                    year,
                    chunks_processed - 1,
                    total_rows,
                )
                del raw_chunk, chunk
        finally:
            cardinalities = {column: store.cardinality(column) for column in CATEGORY_COLUMNS if column in columns}
            store.close()

        def combined_dtype(kinds: set[str]) -> str:
            if not kinds:
                return "all_missing"
            if kinds == {"integer"}:
                return "integer"
            if kinds.issubset({"integer", "float"}):
                return "float"
            return "string" if "string" in kinds else sorted(kinds)[0]

        observed_dtypes = {column: combined_dtype(dtype_kinds[column]) for column in columns}
        target_mean = target_sum / target_finite_count if target_finite_count else None
        target_std = None
        if target_finite_count and target_mean is not None:
            target_std = math.sqrt(max(0.0, (target_sum_squares / target_finite_count) - target_mean**2))
        summary: dict[str, Any] = {
            "year": year,
            "audit_version": self.audit_version,
            "config_version": self.config_version,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "chunk_size": chunk_size,
            "source_signature": signature,
            "is_complete": max_rows is None,
            "dry_run_max_rows": max_rows,
            "resumed": False,
            "columns": columns,
            "column_order": columns,
            "column_count": len(columns),
            "observed_dtypes": observed_dtypes,
            "row_count": total_rows,
            "chunks_processed": chunks_processed,
            "missing": {column: {"count": missing_counts[column], "rate": (missing_counts[column] / total_rows) if total_rows else None} for column in columns},
            "fl_date": {"available": "FL_DATE" in columns, "min": date_min.date().isoformat() if date_min is not None else None, "max": date_max.date().isoformat() if date_max is not None else None, "invalid_nonmissing_count": invalid_date_count},
            "arr_delay": {"available": target_available, "missing_count": target_missing if target_available else None, "invalid_or_nonfinite_count": target_invalid if target_available else None, "finite_count": target_finite_count if target_available else None, "distribution": {"min": target_min, "max": target_max, "mean": target_mean, "population_std": target_std} if target_available else None, "gte_15": {"count": target_gte_15_count, "rate_among_finite": (target_gte_15_count / target_finite_count) if target_finite_count else None} if target_available else None},
            "categorical_cardinality": cardinalities,
            "weather_columns": [column for column in columns if any(token in column.upper() for token in WEATHER_NAME_TOKENS)],
            "airport_index": {column: {"exists": column in columns, "cardinality": cardinalities.get(column)} for column in ("ORIGIN_INDEX", "DEST_INDEX")},
            "duplicate_rows": {"strategy": "sqlite_pandas_dualhash128_streaming", "indicator": duplicate_rows > 0, "count": duplicate_rows, "collision_caveat": "Two 64-bit hashes are used; collision risk is negligible but non-zero."},
            "numeric_quality": {column: {"nonmissing_numeric_count": numeric_nonmissing[column], "non_numeric_nonmissing_count": numeric_invalid[column], "nan_count": missing_counts[column], "inf_count": numeric_inf[column]} for column in columns if observed_dtypes[column] in {"integer", "float"}},
            "schema_difference": compare_schema(columns, observed_dtypes, reference_schema),
            "runtime_seconds": round(time.perf_counter() - started_at, 3),
            "execution_backend": "pandas_chunked",
        }
        if write_summary:
            self.manifest_directory.mkdir(parents=True, exist_ok=True)
            with self.manifest_path(year).open("w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2, sort_keys=True)
                handle.write("\n")
        return summary

    @staticmethod
    def _process_chunk(
        chunk: TabularChunk,
        *,
        columns: list[str],
        missing_counts: dict[str, int],
        type_kinds: dict[str, set[str]],
        numeric_nonmissing: dict[str, int],
        numeric_invalid: dict[str, int],
        numeric_inf: dict[str, int],
        store: _SQLiteAuditStore,
    ) -> None:
        for column in CATEGORY_COLUMNS:
            if column in columns:
                store.add_categories(
                    column,
                    (str(row[column]).strip() for row in chunk.rows if not _is_missing(row.get(column))),
                )
        for row in chunk.rows:
            for column in columns:
                value = row.get(column)
                if _is_missing(value):
                    missing_counts[column] += 1
                    continue
                kind = _infer_value_kind(value)
                if kind is not None:
                    type_kinds[column].add(kind)
                numeric_value = _parse_float(value)
                if numeric_value is None:
                    numeric_invalid[column] += 1
                else:
                    numeric_nonmissing[column] += 1
                    if math.isinf(numeric_value):
                        numeric_inf[column] += 1
