import pandas as pd
import pytest

from web_dashboard.contracts import RunRequest
from web_dashboard.normalization import InputError, normalize_files
from web_dashboard.pipeline import make_legs, pair_schedule_legs


def normalize(tmp_path, table):
    path = tmp_path / "raw.parquet"
    table.to_parquet(path, index=False)
    return normalize_files([path])


def test_schedule_only_normalization_and_pairing(tmp_path, raw_table):
    table, report = normalize(tmp_path, raw_table)
    assert report["can_run"] and report["dates"] == [{"date": "2026-07-01", "arrivals": 2, "departures": 2, "total": 4}]
    pairs = pair_schedule_legs(make_legs(table, "2026-07-01"), 45)
    assert len(pairs) == 3
    assert sum(pair.is_paired for pair in pairs) == 1
    assert not any(pair.is_verified for pair in pairs)
    assert sum(bool(p.arrival_leg_id) + bool(p.departure_leg_id) for p in pairs) == 4
    assert all("ARR_DELAY" not in row for row in report["preview"])


def test_sfo_midnight_and_2400(tmp_path, raw_table):
    row = raw_table.head(1).copy()
    row.loc[0, ["ORIGIN", "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME"]] = ["SFO", 2330, 730, 300]
    table, report = normalize(tmp_path, row)
    assert report["can_run"] and table.iloc[0].service_date == "2026-07-02"
    assert table.iloc[0].prediction_cutoff_utc == "2026-07-02T04:30:00+00:00"
    row.loc[0, ["ORIGIN", "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME"]] = ["MCO", 2400, 130, 90]
    table, report = normalize(tmp_path, row)
    assert report["can_run"] and table.iloc[0].service_date == "2026-07-02"


@pytest.mark.parametrize("field,value", [("CRS_DEP_TIME", 2560), ("ORIGIN", "ZZZ"),
                                        ("CRS_ARR_TIME", 2300), ("OP_CARRIER", None),
                                        ("CRS_ELAPSED_TIME", float("nan")), ("FL_DATE", "2024-01-01")])
def test_bad_rows_block_execution(tmp_path, raw_table, field, value):
    raw_table[field] = raw_table[field].astype(object)
    raw_table.loc[0, field] = value
    _, report = normalize(tmp_path, raw_table)
    assert not report["can_run"] and report["invalid_rows"] >= 1


def test_aliases_duplicates_and_precomputed_rejection(tmp_path, raw_table):
    _, report = normalize(tmp_path, raw_table.rename(columns={"FL_DATE": "FlightDate", "CRS_DEP_TIME": "CRSDepTime"}))
    assert report["can_run"]
    _, report = normalize(tmp_path, pd.concat([raw_table, raw_table.head(1)], ignore_index=True))
    assert not report["can_run"] and report["invalid_rows"] == 1
    raw_table["predicted_arrival_min"] = 10
    with pytest.raises(InputError, match="không phải raw"):
        normalize(tmp_path, raw_table)


def test_no_carrier_only_pairing(tmp_path, raw_table):
    raw_table["TAIL_NUM"] = None
    table, _ = normalize(tmp_path, raw_table)
    assert len(pair_schedule_legs(make_legs(table, "2026-07-01"), 45)) == 4


def test_calendar_conflict_and_fractional_clock_fail(tmp_path, raw_table):
    raw_table["MONTH"] = 8
    _, report = normalize(tmp_path, raw_table)
    assert report["invalid_rows"] == 4
    raw_table = raw_table.drop(columns="MONTH")
    raw_table["CRS_DEP_TIME"] = raw_table.CRS_DEP_TIME.astype(float)
    raw_table.loc[0, "CRS_DEP_TIME"] = 800.5
    _, report = normalize(tmp_path, raw_table)
    assert report["invalid_rows"] == 1


def test_upload_timezone_extension_does_not_modify_research_map(tmp_path, raw_table):
    from src.data.time_normalization import AIRPORT_IANA_TIMEZONES
    original = dict(AIRPORT_IANA_TIMEZONES)
    raw_table = raw_table.head(1).copy()
    raw_table.loc[0, ["ORIGIN", "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME"]] = ["RNO", 800, 1500, 240]
    _, report = normalize(tmp_path, raw_table)
    assert report["can_run"]
    assert AIRPORT_IANA_TIMEZONES == original


def test_contract_prevents_invalid_capacity():
    from pydantic import ValidationError
    for changes in ({"contact_gates": 0}, {"remote_gates": -1}, {"service_date": "2024-01-01"},
                    {"preset": "large", "contact_gates": 20}, {"default_dwell_min": 20}):
        with pytest.raises(ValidationError):
            RunRequest.model_validate({"dataset_id": "a" * 32, "service_date": "2026-07-01", **changes})
