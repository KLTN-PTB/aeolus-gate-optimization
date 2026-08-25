"""Chunked, read-only canonicalization of Aeolus Tabular CSV files to Parquet."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.data.load_aeolus import load_base_config, resolve_project_root, resolve_tabular_csv
from src.data.project_logging import log_data_access

FLIGHT_KEY_VERSION = "flight_key_v1"
FLIGHT_KEY_COMPONENTS = (
    "source_year", "source_file", "source_row_number", "FL_DATE", "OP_CARRIER",
    "OP_CARRIER_FL_NUM", "ORIGIN", "DEST", "CRS_DEP_TIME",
)
ACTUAL_OR_TARGET_FIELDS = frozenset({
    "ARR_DELAY", "DEP_DELAY", "ARR_TIME", "DEP_TIME", "WHEELS_OFF", "WHEELS_ON",
    "TAXI_IN", "TAXI_OUT", "AIR_TIME", "ACTUAL_ELAPSED_TIME",
})


def flight_key_payload(record: dict[str, Any]) -> str:
    """Return the stable, pre-outcome traceability payload for one source row."""
    return "\x1f".join("" if record.get(name) is None else str(record.get(name)) for name in FLIGHT_KEY_COMPONENTS)


def make_flight_key(record: dict[str, Any]) -> str:
    """Create a deterministic non-aircraft key; actual/target fields are excluded."""
    digest = hashlib.blake2b(flight_key_payload(record).encode("utf-8"), digest_size=16).hexdigest()
    return f"{FLIGHT_KEY_VERSION}_{digest}"


def role_for_year(year: int) -> str:
    return "FINAL_HOLDOUT" if year == 2024 else "DEVELOPMENT"


def is_inbound_atl(record: dict[str, Any]) -> bool:
    return str(record.get("DEST", "")).strip() == "ATL"


def is_outbound_atl(record: dict[str, Any]) -> bool:
    return str(record.get("ORIGIN", "")).strip() == "ATL"


def _dependencies() -> tuple[Any, Any, Any]:
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - depends on execution environment
        raise RuntimeError("Canonicalization requires pandas and pyarrow.") from error
    return pd, pa, pq


class Canonicalizer:
    def __init__(self, *, project_root: Path | None = None, schema_path: Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.config = load_base_config(project_root=self.project_root)
        self.config_version = str(self.config.get("project", {}).get("version", "unknown"))
        path = schema_path or self.project_root / "artifacts" / "manifests" / "canonical_schema_v1.json"
        self.schema = json.loads(path.read_text(encoding="utf-8"))
        self.columns = list(self.schema["column_order"])
        self.schema_version = str(self.schema["canonical_schema_version"])

    def materialize_year(self, year: int, *, chunk_size: int = 250_000) -> dict[str, Any]:
        pd, pa, pq = _dependencies()
        purpose = "canonicalize_holdout" if year == 2024 else "development"
        source = resolve_tabular_csv(year, project_root=self.project_root, purpose=purpose)
        source_stat = source.stat()
        fields = self.schema["fields"]
        string_columns = [name for name in self.columns if fields[name]["storage_dtype"] == "string"]
        dtype = {name: "string" for name in string_columns}
        roots = {
            "source": self.project_root / "data" / "processed" / "tabular_by_year" / f"year={year}",
            "inbound": self.project_root / "data" / "processed" / "inbound_atl" / f"year={year}",
            "outbound": self.project_root / "data" / "processed" / "outbound_atl" / f"year={year}",
        }
        if any(root.exists() and any(root.iterdir()) for root in roots.values()):
            raise FileExistsError(f"Generated output already exists for {year}; refusing to overwrite it.")
        for root in roots.values():
            root.mkdir(parents=True, exist_ok=True)

        counts = {"source": 0, "inbound": 0, "outbound": 0}
        ordinal = 0
        part = 0
        key_temp = tempfile.TemporaryDirectory(prefix=f"aeolus_flight_keys_{year}_", dir=self.project_root / "artifacts" / "manifests")
        key_store = sqlite3.connect(Path(key_temp.name) / "keys.sqlite3")
        key_store.execute("PRAGMA journal_mode=OFF")
        key_store.execute("PRAGMA synchronous=OFF")
        key_store.execute("CREATE TABLE keys (flight_key TEXT PRIMARY KEY)")
        try:
          for chunk in pd.read_csv(source, chunksize=chunk_size, dtype=dtype, low_memory=False):
            missing = set(self.columns).difference(chunk.columns)
            if missing:
                raise ValueError(f"Canonical source is missing columns for {year}: {sorted(missing)}")
            chunk = chunk.loc[:, self.columns].copy()
            for name in self.columns:
                storage_dtype = fields[name]["storage_dtype"]
                if storage_dtype == "float64":
                    chunk[name] = pd.to_numeric(chunk[name], errors="coerce").astype("float64")
                elif storage_dtype == "Int64":
                    chunk[name] = pd.to_numeric(chunk[name], errors="coerce").astype("Int64")
            source_ordinals = range(ordinal + 1, ordinal + len(chunk) + 1)
            keys: list[str] = []
            for row_number, row in zip(source_ordinals, chunk.to_dict("records")):
                key_record = {"source_year": year, "source_file": source.name, "source_row_number": row_number, **row}
                keys.append(make_flight_key(key_record))
            before = key_store.total_changes
            key_store.executemany("INSERT OR IGNORE INTO keys(flight_key) VALUES (?)", ((key,) for key in keys))
            inserted = key_store.total_changes - before
            key_store.commit()
            if inserted != len(keys):
                raise ValueError(f"Non-unique flight_key detected for year={year}.")
            chunk.insert(len(self.columns), "source_year", year)
            chunk.insert(len(self.columns) + 1, "source_row_number", list(source_ordinals))
            chunk.insert(len(self.columns) + 2, "flight_key", keys)
            self._write_part(pa, pq, chunk, roots["source"] / f"part-{part:05d}.parquet")
            inbound = chunk.loc[chunk["DEST"].astype("string").str.strip() == "ATL"]
            outbound = chunk.loc[chunk["ORIGIN"].astype("string").str.strip() == "ATL"]
            if not inbound.empty:
                self._write_part(pa, pq, inbound, roots["inbound"] / f"part-{part:05d}.parquet")
            if not outbound.empty:
                self._write_part(pa, pq, outbound, roots["outbound"] / f"part-{part:05d}.parquet")
            counts["source"] += len(chunk)
            counts["inbound"] += len(inbound)
            counts["outbound"] += len(outbound)
            ordinal += len(chunk)
            part += 1
        finally:
            key_store.close()
            key_temp.cleanup()
        if counts["inbound"] > counts["source"] or counts["outbound"] > counts["source"]:
            raise AssertionError("ATL partition count exceeds source count")
        log_data_access(operation="materialize_canonical_tabular", config_version=self.config_version, year=year, purpose=purpose, allowed=True, reason="canonical parquet materialized without raw mutation")
        return {
            "year": year, "role": role_for_year(year), "source_file": source.relative_to(self.project_root).as_posix(),
            "source_file_size_bytes": source_stat.st_size, "source_modified_time_ns": source_stat.st_mtime_ns,
            "schema_version": self.schema_version, "config_version": self.config_version,
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "source_rows": counts["source"],
            "partitions": [{"flow": "tabular_by_year", "row_count": counts["source"], "path": roots["source"].relative_to(self.project_root).as_posix()}, {"flow": "inbound_atl", "row_count": counts["inbound"], "path": roots["inbound"].relative_to(self.project_root).as_posix()}, {"flow": "outbound_atl", "row_count": counts["outbound"], "path": roots["outbound"].relative_to(self.project_root).as_posix()}],
        }

    @staticmethod
    def _write_part(pa: Any, pq: Any, frame: Any, destination: Path) -> None:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        pq.write_table(table, destination, compression="zstd")

    def materialize_all(self, *, chunk_size: int = 250_000) -> dict[str, Any]:
        entries = [self.materialize_year(year, chunk_size=chunk_size) for year in range(2016, 2025)]
        manifest = {"manifest_version": "v1", "schema_version": self.schema_version, "logical_roadmap_equivalent": "Partitioned inbound_atl/outbound_atl Parquet datasets are the logical equivalent of atl_inbound.parquet/atl_outbound.parquet; no monolithic file is created for large data.", "flight_key_contract": {"version": FLIGHT_KEY_VERSION, "components": list(FLIGHT_KEY_COMPONENTS), "excluded_actual_or_target_fields": sorted(ACTUAL_OR_TARGET_FIELDS), "note": "flight_key is traceability-only, not an aircraft identifier or ML feature."}, "years": entries}
        output = self.project_root / "artifacts" / "manifests" / "processed_data_manifest_v1.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest

    @staticmethod
    def enrich_processed_manifest(manifest_path: Path) -> dict[str, Any]:
        """Add self-contained partition provenance without touching data files."""
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["years"]:
            for partition in entry["partitions"]:
                partition.update({
                    "year": entry["year"], "role": entry["role"], "source_rows": entry["source_rows"],
                    "output_rows": partition["row_count"], "schema_version": entry["schema_version"],
                    "config_version": entry["config_version"], "created_at_utc": entry["created_at_utc"],
                })
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest
