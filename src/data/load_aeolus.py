"""Read-only, chunked access to Aeolus Tabular CSV files.

The loader deliberately uses the standard-library CSV reader so the schema-audit
infrastructure remains usable before optional dataframe dependencies are installed.
It never writes to ``data/raw`` and never materializes a complete year in memory.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import yaml

from src.data.access_guard import assert_data_access_allowed


DEFAULT_CONFIG_RELATIVE_PATH = Path("configs/base.yaml")
SUPPORTED_YEARS = frozenset(range(2016, 2025))


@dataclass(frozen=True)
class TabularChunk:
    """One bounded sequence of CSV records from a single year."""

    year: int
    chunk_number: int
    start_row: int
    rows: list[dict[str, str | None]]


def resolve_project_root(project_root: Path | None = None) -> Path:
    """Resolve the root from an explicit path or the repository layout."""
    if project_root is not None:
        return Path(project_root).resolve()

    candidate = Path(__file__).resolve().parents[2]
    if (candidate / DEFAULT_CONFIG_RELATIVE_PATH).is_file():
        return candidate
    raise FileNotFoundError("Could not resolve project root containing configs/base.yaml")


def load_base_config(
    *, project_root: Path | None = None, config_path: Path | None = None
) -> dict:
    """Load the project config without introducing an absolute local path."""
    root = resolve_project_root(project_root)
    path = Path(config_path) if config_path is not None else root / DEFAULT_CONFIG_RELATIVE_PATH
    if not path.is_absolute():
        path = root / path
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return config


def _raw_tabular_root(config: Mapping[str, object], project_root: Path) -> Path:
    try:
        raw_path = config["data"]["raw_tabular_path"]  # type: ignore[index]
    except (KeyError, TypeError) as error:
        raise ValueError("Missing data.raw_tabular_path in configuration") from error
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("data.raw_tabular_path must be a non-empty string")
    path = Path(raw_path)
    return path if path.is_absolute() else project_root / path


def resolve_tabular_csv(
    year: int,
    *,
    project_root: Path | None = None,
    config_path: Path | None = None,
    purpose: str = "schema_audit",
) -> Path:
    """Return the expected source CSV after applying the data-access guard."""
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"Unsupported Aeolus year: {year}")
    assert_data_access_allowed(year, purpose)
    root = resolve_project_root(project_root)
    config = load_base_config(project_root=root, config_path=config_path)
    source = _raw_tabular_root(config, root) / str(year) / f"flight_with_weather_{year}.csv"
    if not source.is_file():
        raise FileNotFoundError(f"Expected Tabular CSV does not exist: {source}")
    return source


def read_tabular_header(
    year: int,
    *,
    project_root: Path | None = None,
    config_path: Path | None = None,
    purpose: str = "schema_audit",
) -> list[str]:
    """Read only the CSV header for a year."""
    source = resolve_tabular_csv(
        year,
        project_root=project_root,
        config_path=config_path,
        purpose=purpose,
    )
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), None)
    if not header:
        raise ValueError(f"CSV has no header: {source}")
    if len(header) != len(set(header)):
        raise ValueError(f"CSV header contains duplicate columns: {source}")
    return header


def iter_tabular_chunks(
    year: int,
    *,
    chunk_size: int,
    project_root: Path | None = None,
    config_path: Path | None = None,
    columns: Sequence[str] | None = None,
    max_rows: int | None = None,
    purpose: str = "schema_audit",
) -> Iterator[TabularChunk]:
    """Stream one Aeolus year in bounded record chunks.

    ``max_rows`` is intended for explicit dry-runs and tests. It limits records
    yielded without changing or truncating the source file.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_rows is not None and max_rows < 0:
        raise ValueError("max_rows must be non-negative or None")

    source = resolve_tabular_csv(
        year,
        project_root=project_root,
        config_path=config_path,
        purpose=purpose,
    )
    header = read_tabular_header(
        year,
        project_root=project_root,
        config_path=config_path,
        purpose=purpose,
    )
    selected_columns = list(columns) if columns is not None else header
    unknown_columns = set(selected_columns).difference(header)
    if unknown_columns:
        raise ValueError(f"Requested columns are absent from {year}: {sorted(unknown_columns)}")

    yielded_rows = 0
    chunk_number = 0
    rows: list[dict[str, str | None]] = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != header:
            raise ValueError(f"Header changed while opening source: {source}")
        for row in reader:
            if max_rows is not None and yielded_rows >= max_rows:
                break
            selected = {column: row.get(column) for column in selected_columns}
            rows.append(selected)
            yielded_rows += 1
            if len(rows) == chunk_size:
                yield TabularChunk(year, chunk_number, yielded_rows - len(rows) + 1, rows)
                chunk_number += 1
                rows = []
        if rows:
            yield TabularChunk(year, chunk_number, yielded_rows - len(rows) + 1, rows)


def stream_tabular_year(**kwargs: object) -> Iterator[TabularChunk]:
    """Alias for callers that prefer an explicit streaming API name."""
    return iter_tabular_chunks(**kwargs)  # type: ignore[arg-type]
