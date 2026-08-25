"""Bounded validation for canonical Aeolus Parquet partitions."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pandas as pd
from src.data.access_guard import DataAccessDenied, assert_data_access_allowed

manifest = json.loads((ROOT / "artifacts/manifests/processed_data_manifest_v1.json").read_text())
canonical = json.loads((ROOT / "artifacts/manifests/canonical_schema_v1.json").read_text())
expected_columns = canonical["column_order"] + ["source_year", "source_row_number", "flight_key"]
expected_types = {
    # Pandas' nullable string extension is represented as Arrow/Parquet
    # ``large_string``.  It is the physical representation of the logical
    # canonical ``string`` type, not a schema drift.
    name: {"string": "large_string", "float64": "double", "Int64": "int64"}[spec["storage_dtype"]]
    for name, spec in canonical["fields"].items()
}
for entry in manifest["years"]:
    source = ROOT / entry["source_file"]
    assert source.stat().st_size == entry["source_file_size_bytes"]
    assert source.stat().st_mtime_ns == entry["source_modified_time_ns"]
    observed = {}
    for partition in entry["partitions"]:
        path = ROOT / partition["path"]
        files = sorted(path.glob("*.parquet"))
        assert files, f"missing parquet parts: {path}"
        observed[partition["flow"]] = sum(pq.ParquetFile(item).metadata.num_rows for item in files)
        assert observed[partition["flow"]] == partition["row_count"]
        schema = pq.ParquetFile(files[0]).schema_arrow
        assert schema.names == expected_columns
        for name, expected_type in expected_types.items():
            assert str(schema.field(name).type) == expected_type, (entry["year"], name, schema.field(name).type)
    assert observed["tabular_by_year"] == entry["source_rows"]
    assert observed["inbound_atl"] <= entry["source_rows"]
    assert observed["outbound_atl"] <= entry["source_rows"]
    for flow, column in (("inbound_atl", "DEST"), ("outbound_atl", "ORIGIN")):
        scanner = ds.dataset(ROOT / next(item["path"] for item in entry["partitions"] if item["flow"] == flow), format="parquet").scanner(columns=[column], batch_size=250_000)
        for batch in scanner.to_batches():
            assert all(value == "ATL" for value in batch.column(0).to_pylist())
try:
    assert_data_access_allowed(2024, "development")
except DataAccessDenied:
    pass
else:
    raise AssertionError("2024 development access was not blocked")
# Bounded 2016 traceability check: canonicalization did not alter ARR_DELAY for
# the first source records.  It deliberately avoids reading any 2024 row here.
raw_sample = pd.read_csv(ROOT / "data/raw/tabular/2016/flight_with_weather_2016.csv", nrows=100)
processed_first_part = pq.read_table(sorted((ROOT / "data/processed/tabular_by_year/year=2016").glob("*.parquet"))[0]).to_pandas()
assert raw_sample["ARR_DELAY"].astype(float).tolist() == processed_first_part["ARR_DELAY"].head(100).astype(float).tolist()
assert processed_first_part["flight_key"].head(100).is_unique
print("processed-data validation: PASS")
