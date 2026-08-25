from __future__ import annotations

import json
from pathlib import Path

from src.data.canonicalize import ACTUAL_OR_TARGET_FIELDS, FLIGHT_KEY_COMPONENTS, is_inbound_atl, is_outbound_atl, make_flight_key, role_for_year


def _record() -> dict[str, object]:
    return {"source_year": 2016, "source_file": "flight_with_weather_2016.csv", "source_row_number": 1, "FL_DATE": "2016-01-01", "OP_CARRIER": "AA", "OP_CARRIER_FL_NUM": 100, "ORIGIN": "BOS", "DEST": "ATL", "CRS_DEP_TIME": "0800", "ARR_DELAY": 12.0, "DEP_DELAY": 5.0, "ARR_TIME": "1010"}


def test_flight_key_is_deterministic_and_excludes_actual_target_fields() -> None:
    first = _record()
    second = _record()
    second.update({"ARR_DELAY": 999.0, "DEP_DELAY": -99.0, "ARR_TIME": "2359"})
    assert make_flight_key(first) == make_flight_key(second)
    assert set(FLIGHT_KEY_COMPONENTS).isdisjoint(ACTUAL_OR_TARGET_FIELDS)


def test_flight_key_uses_source_row_ordinal_for_traceable_uniqueness() -> None:
    keys = set()
    for row_number in range(1, 101):
        record = _record()
        record["source_row_number"] = row_number
        keys.add(make_flight_key(record))
    assert len(keys) == 100


def test_canonical_schema_order_and_target_storage_are_versioned() -> None:
    schema = json.loads((Path(__file__).parents[1] / "artifacts/manifests/canonical_schema_v1.json").read_text())
    assert schema["column_order"][0:5] == ["FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST"]
    assert schema["fields"]["ARR_DELAY"]["storage_dtype"] == "float64"
    assert schema["fields"]["ARR_DELAY"]["schema_role"] == "target"


def test_atl_predicates_and_final_holdout_role() -> None:
    assert is_inbound_atl({"DEST": "ATL"})
    assert not is_inbound_atl({"DEST": "BOS"})
    assert is_outbound_atl({"ORIGIN": "ATL"})
    assert not is_outbound_atl({"ORIGIN": "BOS"})
    assert role_for_year(2024) == "FINAL_HOLDOUT"
    assert role_for_year(2023) == "DEVELOPMENT"


def test_processed_manifest_matches_unmodified_raw_metadata() -> None:
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "artifacts/manifests/processed_data_manifest_v1.json").read_text())
    for entry in manifest["years"]:
        source = root / entry["source_file"]
        assert source.stat().st_size == entry["source_file_size_bytes"]
        assert source.stat().st_mtime_ns == entry["source_modified_time_ns"]
