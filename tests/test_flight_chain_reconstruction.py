from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.reconstruct_flight_chain import build_parser, parse_years

from src.data.flight_chain_reconstruction import (
    CHAIN_GROUP_FIELDS,
    CHAIN_GROUP_COMPONENTS,
    CHAIN_ID_VERSION,
    CHAIN_MEMBER_FIELDS,
    DATETIME_STORAGE_AMENDMENT_VERSION,
    FlightChainReconstructor,
    INBOUND_TARGET_MAP_FIELDS,
    PHYSICAL_AIRCRAFT_IDENTITY,
    ReconstructionValidationError,
    ReconstructionStagingError,
    assert_derived_schema_safe,
    assert_output_path_safe,
    assert_project_venv,
    assert_raw_inventory_unchanged,
    assert_reconstruction_year_allowed,
    dependency_versions,
    make_chain_id,
    normalize_carrier,
    normalize_flight_date,
    normalize_flight_number,
    reconstruct_records,
    scheduled_departure_timestamp,
    snapshot_raw_inventory,
)
from src.data.access_guard import DataAccessDenied
from src.data.leakage_rules import (
    LEAKAGE_COLUMNS,
    TARGET_COLUMNS,
    UNCERTAIN_COLUMNS,
    WEATHER_COLUMNS,
)


ROOT = Path(__file__).resolve().parents[1]


def _group_record() -> dict[str, object]:
    return {
        "source_year": 2016,
        "FL_DATE": " 2016-01-01 ",
        "OP_CARRIER": " aa ",
        "OP_CARRIER_FL_NUM": 123.0,
    }


def test_project_venv_guard_rejects_a_different_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "different-env"))

    with pytest.raises(RuntimeError, match=r"repository \.venv"):
        assert_project_venv(ROOT)


def test_dependency_versions_identify_the_runtime_stack() -> None:
    observed = dependency_versions()

    assert {"python", "pandas", "pyarrow", "sqlite"} <= observed.keys()
    assert all(observed.values())


def test_chain_id_is_stable_after_contract_normalization() -> None:
    first = _group_record()
    equivalent = {
        **first,
        "FL_DATE": "2016-01-01",
        "OP_CARRIER": "AA",
        "OP_CARRIER_FL_NUM": "123.0",
    }

    assert make_chain_id(first) == make_chain_id(equivalent)
    assert make_chain_id(first).startswith(f"{CHAIN_ID_VERSION}_")
    assert CHAIN_GROUP_COMPONENTS == (
        "source_year",
        "FL_DATE",
        "OP_CARRIER",
        "OP_CARRIER_FL_NUM",
    )


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    [
        ("OP_CARRIER", "DL"),
        ("FL_DATE", "2016-01-02"),
        ("OP_CARRIER_FL_NUM", 124),
    ],
)
def test_chain_id_changes_when_a_group_component_changes(
    changed_field: str, changed_value: object
) -> None:
    base = _group_record()

    assert make_chain_id(base) != make_chain_id(
        {**base, changed_field: changed_value}
    )


def test_group_component_normalizers_are_strict_and_canonical() -> None:
    assert normalize_flight_date(" 2016-01-01 ") == "2016-01-01"
    assert normalize_carrier(" aa ") == "AA"
    assert normalize_flight_number(123.0) == "123"
    assert normalize_flight_number(" 123.0 ") == "123"

    with pytest.raises(ValueError, match="non-integral"):
        normalize_flight_number("123.5")


def test_flight_date_accepts_iso_and_canonical_midnight_timestamp() -> None:
    assert normalize_flight_date("2016-01-01") == "2016-01-01"
    assert normalize_flight_date("2016-01-01 00:00:00") == "2016-01-01"


@pytest.mark.parametrize(
    "raw",
    ["2016-01-01 09:00:00", datetime(2016, 1, 1, 9, 0)],
)
def test_flight_date_rejects_non_midnight_timestamps(raw: object) -> None:
    with pytest.raises(ValueError) as error:
        normalize_flight_date(raw)

    assert getattr(error.value, "reason", None) == (
        "NON_MIDNIGHT_FL_DATE_TIMESTAMP"
    )


@pytest.mark.parametrize(
    ("raw", "expected_hhmm", "expected_timestamp"),
    [
        (5, "0005", datetime(2016, 1, 1, 0, 5)),
        (45, "0045", datetime(2016, 1, 1, 0, 45)),
        (800, "0800", datetime(2016, 1, 1, 8, 0)),
        (1530, "1530", datetime(2016, 1, 1, 15, 30)),
        (2400, "2400", datetime(2016, 1, 2, 0, 0)),
    ],
)
def test_scheduled_departure_parses_hhmm_and_rolls_2400_to_next_day(
    raw: object, expected_hhmm: str, expected_timestamp: datetime
) -> None:
    assert scheduled_departure_timestamp("2016-01-01", raw) == (
        expected_hhmm,
        expected_timestamp,
    )


@pytest.mark.parametrize(
    "raw",
    [None, "", -1, 12.5, 60, 1260, 2360, 2401, float("inf"), "not-a-time"],
)
def test_scheduled_departure_rejects_invalid_hhmm_values(raw: object) -> None:
    with pytest.raises(ValueError):
        scheduled_departure_timestamp("2016-01-01", raw)


@pytest.mark.parametrize(
    ("raw", "expected_hhmm", "expected_timestamp"),
    [
        (
            "2016-01-01 09:00:00",
            "0900",
            datetime(2016, 1, 1, 9, 0),
        ),
        (
            "2016-01-01 00:05:00",
            "0005",
            datetime(2016, 1, 1, 0, 5),
        ),
    ],
)
def test_scheduled_departure_accepts_same_date_canonical_timestamps(
    raw: str, expected_hhmm: str, expected_timestamp: datetime
) -> None:
    assert scheduled_departure_timestamp(
        "2016-01-01 00:00:00", raw
    ) == (expected_hhmm, expected_timestamp)


def test_scheduled_departure_rejects_ambiguous_canonical_midnight() -> None:
    with pytest.raises(ValueError) as error:
        scheduled_departure_timestamp(
            "2016-01-01 00:00:00", "2016-01-01 00:00:00"
        )

    assert getattr(error.value, "reason", None) == (
        "AMBIGUOUS_CANONICAL_MIDNIGHT"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "2015-12-31 23:59:00",
        "2016-01-02 00:00:00",
        "2016-01-02 09:00:00",
    ],
)
def test_scheduled_departure_rejects_unexpected_canonical_date_relation(
    raw: str,
) -> None:
    with pytest.raises(ValueError) as error:
        scheduled_departure_timestamp("2016-01-01", raw)

    assert getattr(error.value, "reason", None) == (
        "UNEXPECTED_CANONICAL_DATE_RELATION"
    )


def test_reconstructed_context_never_claims_physical_aircraft_identity() -> None:
    assert PHYSICAL_AIRCRAFT_IDENTITY is False


def _member_record(
    *,
    flight_key: str,
    row_number: int,
    departure: object,
    origin: str,
    dest: str,
    carrier: object = "AA",
    flight_number: object = 123.0,
    flight_date: object = "2016-01-01",
) -> dict[str, object]:
    return {
        "source_year": 2016,
        "source_row_number": row_number,
        "flight_key": flight_key,
        "FL_DATE": flight_date,
        "OP_CARRIER": carrier,
        "OP_CARRIER_FL_NUM": flight_number,
        "ORIGIN": origin,
        "DEST": dest,
        "CRS_DEP_TIME": departure,
        "CRS_ARR_TIME": "1500",
        "CRS_ELAPSED_TIME": 120.0,
    }


def test_reconstruct_records_groups_and_orders_schedule_context() -> None:
    records = [
        _member_record(
            flight_key="flight_key_v1_c",
            row_number=3,
            departure=1200,
            origin="JFK",
            dest="ATL",
        ),
        _member_record(
            flight_key="flight_key_v1_a",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ORD",
        ),
        _member_record(
            flight_key="flight_key_v1_b",
            row_number=2,
            departure=800,
            origin="ATL",
            dest="JFK",
        ),
        _member_record(
            flight_key="flight_key_v1_d",
            row_number=4,
            departure=900,
            origin="BOS",
            dest="ATL",
            flight_date="2016-01-02",
        ),
    ]

    result = reconstruct_records(records, expected_year=2016)

    first_chain = result.chain_groups[0]
    assert first_chain["member_count"] == 3
    assert first_chain["has_order_tie"] is True
    first_members = [
        row
        for row in result.chain_members
        if row["chain_id"] == first_chain["chain_id"]
    ]
    assert [row["flight_key"] for row in first_members] == [
        "flight_key_v1_b",
        "flight_key_v1_a",
        "flight_key_v1_c",
    ]
    assert [row["chain_position"] for row in first_members] == [0, 1, 2]
    assert [row["order_ambiguous"] for row in first_members] == [True, True, False]
    assert result.chain_members[-1]["chain_id"] != first_chain["chain_id"]

    assert result.inbound_target_map == [
        {
            "target_flight_key": "flight_key_v1_c",
            "chain_id": first_chain["chain_id"],
            "chain_position": 2,
            "chain_length": 3,
            "source_year": 2016,
        },
        {
            "target_flight_key": "flight_key_v1_d",
            "chain_id": result.chain_groups[1]["chain_id"],
            "chain_position": 0,
            "chain_length": 1,
            "source_year": 2016,
        },
    ]


def test_reconstruction_is_independent_of_input_order() -> None:
    records = [
        _member_record(
            flight_key="flight_key_v1_a",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ATL",
        ),
        _member_record(
            flight_key="flight_key_v1_b",
            row_number=2,
            departure=1200,
            origin="JFK",
            dest="ATL",
        ),
    ]

    forward = reconstruct_records(records, expected_year=2016)
    reversed_result = reconstruct_records(list(reversed(records)), expected_year=2016)

    assert forward.chain_groups == reversed_result.chain_groups
    assert forward.chain_members == reversed_result.chain_members
    assert forward.inbound_target_map == reversed_result.inbound_target_map
    assert forward.fingerprints == reversed_result.fingerprints


def test_duplicate_flight_key_fails_closed() -> None:
    records = [
        _member_record(
            flight_key="flight_key_v1_duplicate",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ATL",
        ),
        _member_record(
            flight_key="flight_key_v1_duplicate",
            row_number=2,
            departure=900,
            origin="JFK",
            dest="ATL",
        ),
    ]

    with pytest.raises(ReconstructionValidationError, match="duplicate flight_key"):
        reconstruct_records(records, expected_year=2016)


def test_duplicate_natural_signature_is_reported_without_merging() -> None:
    first = _member_record(
        flight_key="flight_key_v1_first",
        row_number=1,
        departure=800,
        origin="BOS",
        dest="ATL",
    )
    second = {**first, "flight_key": "flight_key_v1_second", "source_row_number": 2}

    result = reconstruct_records([first, second], expected_year=2016)

    assert len(result.chain_members) == 2
    assert result.metrics["duplicate_schedule_signature_count"] == 1
    assert result.metrics["duplicate_schedule_signature_excess_rows"] == 1


def test_missing_group_and_departure_fields_are_excluded_with_reasons() -> None:
    valid = _member_record(
        flight_key="flight_key_v1_valid",
        row_number=1,
        departure=800,
        origin="BOS",
        dest="ATL",
    )
    missing_date = {
        **valid,
        "flight_key": "flight_key_v1_missing_date",
        "source_row_number": 2,
        "FL_DATE": None,
    }
    fractional_number = {
        **valid,
        "flight_key": "flight_key_v1_fractional_number",
        "source_row_number": 3,
        "OP_CARRIER_FL_NUM": 123.5,
    }
    missing_time = {
        **valid,
        "flight_key": "flight_key_v1_missing_time",
        "source_row_number": 4,
        "CRS_DEP_TIME": None,
    }

    result = reconstruct_records(
        [valid, missing_date, fractional_number, missing_time], expected_year=2016
    )

    assert len(result.chain_members) == 1
    assert result.metrics["source_rows"] == 4
    assert result.metrics["eligible_source_rows"] == 1
    assert result.metrics["excluded_rows"] == 3
    assert result.metrics["exclusion_reasons"] == {
        "CRS_DEP_TIME:missing": 1,
        "FL_DATE:missing": 1,
        "OP_CARRIER_FL_NUM:non_integral": 1,
    }
    assert result.metrics["mapped_rows"] == result.metrics["eligible_source_rows"]


def test_derived_output_contract_rejects_leakage_and_unsafe_fields() -> None:
    safe_tables = {
        "chain_groups": CHAIN_GROUP_FIELDS,
        "chain_members": CHAIN_MEMBER_FIELDS,
        "inbound_target_map": INBOUND_TARGET_MAP_FIELDS,
    }
    assert_derived_schema_safe(safe_tables)
    output_columns = set().union(*(set(columns) for columns in safe_tables.values()))
    assert output_columns.isdisjoint(
        LEAKAGE_COLUMNS | TARGET_COLUMNS | WEATHER_COLUMNS | UNCERTAIN_COLUMNS | {"FLIGHTS"}
    )

    with pytest.raises(ReconstructionValidationError, match="forbidden derived fields"):
        assert_derived_schema_safe({"unsafe": [*CHAIN_MEMBER_FIELDS, "ARR_DELAY"]})


def test_output_path_guard_rejects_every_path_under_raw(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "data" / "raw" / "tabular").mkdir(parents=True)
    (project_root / "data" / "raw" / "chain").mkdir(parents=True)

    with pytest.raises(ReconstructionValidationError, match="data/raw"):
        assert_output_path_safe(project_root / "data" / "raw", project_root=project_root)
    with pytest.raises(ReconstructionValidationError, match="data/raw"):
        assert_output_path_safe(
            project_root / "data" / "processed" / ".." / "raw" / "chain" / "derived",
            project_root=project_root,
        )

    accepted = assert_output_path_safe(
        project_root / "data" / "processed" / "derived", project_root=project_root
    )
    assert accepted == (project_root / "data" / "processed" / "derived").resolve()


def test_output_path_guard_resolves_a_link_into_raw(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    raw_target = project_root / "data" / "raw" / "tabular"
    raw_target.mkdir(parents=True)
    link = project_root / "linked-output"
    try:
        link.symlink_to(raw_target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink is unavailable: {error}")

    with pytest.raises(ReconstructionValidationError, match="data/raw"):
        assert_output_path_safe(link / "derived", project_root=project_root)


def test_raw_inventory_detects_path_size_and_mtime_changes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    tabular = project_root / "data" / "raw" / "tabular" / "2016"
    chain = project_root / "data" / "raw" / "chain" / "2016"
    tabular.mkdir(parents=True)
    chain.mkdir(parents=True)
    tabular_file = tabular / "flight.csv"
    chain_file = chain / "chain.pt"
    tabular_file.write_text("source", encoding="utf-8")
    chain_file.write_bytes(b"archive")

    before = snapshot_raw_inventory(project_root)

    assert set(before) == {
        "data/raw/chain/2016/chain.pt",
        "data/raw/tabular/2016/flight.csv",
    }
    assert before["data/raw/chain/2016/chain.pt"]["size"] == 7
    assert before["data/raw/chain/2016/chain.pt"]["mtime_ns"] > 0
    assert_raw_inventory_unchanged(before, snapshot_raw_inventory(project_root))

    tabular_file.write_text("source changed", encoding="utf-8")
    with pytest.raises(ReconstructionValidationError, match="raw inventory changed"):
        assert_raw_inventory_unchanged(before, snapshot_raw_inventory(project_root))


def test_reconstruction_development_access_keeps_2024_sealed() -> None:
    with pytest.raises(DataAccessDenied, match="sealed from development"):
        assert_reconstruction_year_allowed(2024)

    assert_reconstruction_year_allowed(2023)


def _write_canonical_fixture(
    project_root: Path, records: list[dict[str, object]]
) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    partition = (
        project_root / "data" / "processed" / "tabular_by_year" / "year=2016"
    )
    partition.mkdir(parents=True)
    (project_root / "data" / "raw" / "tabular").mkdir(parents=True)
    (project_root / "data" / "raw" / "chain").mkdir(parents=True)
    manifest_root = project_root / "artifacts" / "manifests"
    manifest_root.mkdir(parents=True)
    (manifest_root / "canonical_schema_v1.json").write_text(
        json.dumps(
            {
                "canonical_schema_version": "v1",
                "fields": {
                    "OP_CARRIER_FL_NUM": {
                        "storage_dtype": "float64",
                        "schema_role": "numeric",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    destination = partition / "part-00000.parquet"
    pq.write_table(pa.Table.from_pylist(records), destination)
    return destination


def test_sqlite_engine_writes_validated_partitioned_outputs(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    records = [
        _member_record(
            flight_key="flight_key_v1_a",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ORD",
        ),
        _member_record(
            flight_key="flight_key_v1_b",
            row_number=2,
            departure=800,
            origin="ATL",
            dest="JFK",
        ),
        _member_record(
            flight_key="flight_key_v1_c",
            row_number=3,
            departure=1200,
            origin="JFK",
            dest="ATL",
        ),
    ]
    _write_canonical_fixture(project_root, records)
    output_root = project_root / "data" / "processed" / "derived"
    reconstructor = FlightChainReconstructor(
        project_root=project_root,
        output_root=output_root,
        chunk_size=2,
    )

    result = reconstructor.reconstruct_year(2016)

    assert result["status"] == "PASS"
    assert result["is_complete"] is True
    assert result["metrics"]["source_rows"] == 3
    assert result["metrics"]["mapped_rows"] == 3
    assert result["metrics"]["chain_count"] == 1
    assert result["metrics"]["inbound_target_count"] == 1
    assert result["flight_number_semantics"]["observed_value_count"] == 3
    assert result["flight_number_semantics"]["observed_missing_count"] == 0
    assert result["flight_number_semantics"]["observed_non_integral_count"] == 0
    assert result["staging"]["removed_after_pass"] is True
    assert not Path(result["staging"]["path"]).exists()
    assert result["staging"]["index_names"] == [
        "idx_staged_order",
        "sqlite_autoindex_staged_rows_1",
    ]
    assert result["resource_usage"]["peak_staging_bytes"] > 0
    assert result["resource_usage"]["peak_python_allocation_bytes"] > 0
    assert result["resource_usage"]["input_bytes"] > 0
    assert result["resource_usage"]["output_bytes"] > 0

    expected_counts = {
        "chain_groups": 1,
        "chain_members": 3,
        "inbound_target_map": 1,
    }
    import pyarrow.parquet as pq

    for table_name, expected_count in expected_counts.items():
        path = output_root / table_name / "year=2016" / "part-00000.parquet"
        parquet = pq.ParquetFile(path)
        assert parquet.metadata.num_rows == expected_count
        assert parquet.schema_arrow.names == list(
            {
                "chain_groups": CHAIN_GROUP_FIELDS,
                "chain_members": CHAIN_MEMBER_FIELDS,
                "inbound_target_map": INBOUND_TARGET_MAP_FIELDS,
            }[table_name]
        )

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        reconstructor.reconstruct_year(2016)


def test_sqlite_engine_has_deterministic_logical_fingerprints(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    records = [
        _member_record(
            flight_key="flight_key_v1_b",
            row_number=2,
            departure=1200,
            origin="JFK",
            dest="ATL",
        ),
        _member_record(
            flight_key="flight_key_v1_a",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ATL",
        ),
    ]
    _write_canonical_fixture(project_root, records)

    first = FlightChainReconstructor(
        project_root=project_root,
        output_root=project_root / "data" / "processed" / "derived-first",
        chunk_size=1,
    ).reconstruct_year(2016)
    second = FlightChainReconstructor(
        project_root=project_root,
        output_root=project_root / "data" / "processed" / "derived-second",
        chunk_size=2,
    ).reconstruct_year(2016)

    assert first["fingerprints"] == second["fingerprints"]
    assert first["metrics"] == second["metrics"]


def test_sqlite_engine_reuses_stored_flight_key_with_canonical_timestamps(
    tmp_path: Path,
) -> None:
    import pyarrow.parquet as pq

    project_root = tmp_path / "project"
    stored_flight_key = "flight_key_v1_stored_identifier_must_not_change"
    record = _member_record(
        flight_key=stored_flight_key,
        row_number=1,
        departure="2016-01-01 09:00:00",
        origin="BOS",
        dest="ATL",
        flight_date="2016-01-01 00:00:00",
    )
    _write_canonical_fixture(project_root, [record])
    output_root = project_root / "data" / "processed" / "derived"

    result = FlightChainReconstructor(
        project_root=project_root,
        output_root=output_root,
        chunk_size=1,
    ).reconstruct_year(2016)

    assert result["datetime_storage_amendment_version"] == (
        DATETIME_STORAGE_AMENDMENT_VERSION
    )
    members_path = (
        project_root / result["outputs"]["chain_members"] / "part-00000.parquet"
    )
    members = pq.read_table(members_path).to_pylist()
    assert members[0]["flight_key"] == stored_flight_key
    assert members[0]["FL_DATE"] == "2016-01-01"
    assert members[0]["CRS_DEP_TIME"] == "0900"
    assert members[0]["scheduled_departure_timestamp"] == datetime(
        2016, 1, 1, 9, 0
    )


def test_failed_year_preserves_staging_without_publishing_outputs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    records = [
        _member_record(
            flight_key="flight_key_v1_duplicate",
            row_number=1,
            departure=800,
            origin="BOS",
            dest="ATL",
        ),
        _member_record(
            flight_key="flight_key_v1_duplicate",
            row_number=2,
            departure=900,
            origin="JFK",
            dest="ATL",
        ),
    ]
    _write_canonical_fixture(project_root, records)
    output_root = project_root / "data" / "processed" / "derived"
    reconstructor = FlightChainReconstructor(
        project_root=project_root,
        output_root=output_root,
        chunk_size=1,
    )

    with pytest.raises(ReconstructionStagingError, match="duplicate flight_key") as error:
        reconstructor.reconstruct_year(2016)

    assert error.value.staging_path.is_dir()
    assert not (output_root / "chain_members" / "year=2016").exists()
    assert_output_path_safe(error.value.staging_path, project_root=project_root)


def test_ambiguous_canonical_midnight_aborts_year_without_publishing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    records = [
        _member_record(
            flight_key="flight_key_v1_valid",
            row_number=1,
            departure="2016-01-01 09:00:00",
            origin="BOS",
            dest="ATL",
            flight_date="2016-01-01 00:00:00",
        ),
        _member_record(
            flight_key="flight_key_v1_ambiguous_midnight",
            row_number=2,
            departure="2016-01-01 00:00:00",
            origin="JFK",
            dest="ATL",
            flight_date="2016-01-01 00:00:00",
        ),
    ]
    _write_canonical_fixture(project_root, records)
    output_root = project_root / "data" / "processed" / "derived"
    reconstructor = FlightChainReconstructor(
        project_root=project_root,
        output_root=output_root,
        chunk_size=1,
    )

    with pytest.raises(
        ReconstructionStagingError, match="AMBIGUOUS_CANONICAL_MIDNIGHT"
    ) as error:
        reconstructor.reconstruct_year(2016)

    assert error.value.staging_path.is_dir()
    assert not (output_root / "chain_members" / "year=2016").exists()


def test_unexpected_canonical_departure_date_aborts_year_without_publishing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    invalid = _member_record(
        flight_key="flight_key_v1_unexpected_date_relation",
        row_number=1,
        departure="2016-01-02 09:00:00",
        origin="BOS",
        dest="ATL",
        flight_date="2016-01-01 00:00:00",
    )
    _write_canonical_fixture(project_root, [invalid])
    output_root = project_root / "data" / "processed" / "derived"

    with pytest.raises(
        ReconstructionStagingError, match="UNEXPECTED_CANONICAL_DATE_RELATION"
    ) as error:
        FlightChainReconstructor(
            project_root=project_root,
            output_root=output_root,
            chunk_size=1,
        ).reconstruct_year(2016)

    assert error.value.staging_path.is_dir()
    assert not (output_root / "chain_members" / "year=2016").exists()


def test_flight_number_semantics_are_checked_before_other_normalization(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    contradictory = _member_record(
        flight_key="flight_key_v1_bad_flight_number",
        row_number=1,
        departure="2016-01-01 09:00:00",
        origin="BOS",
        dest="ATL",
        flight_date="2016-01-01 00:00:00",
        flight_number=123.5,
    )
    _write_canonical_fixture(project_root, [contradictory])

    with pytest.raises(
        ReconstructionStagingError,
        match="OP_CARRIER_FL_NUM values contradict integral flight-number semantics",
    ):
        FlightChainReconstructor(
            project_root=project_root,
            output_root=project_root / "data" / "processed" / "derived",
            chunk_size=1,
        ).reconstruct_year(2016)


def test_cli_year_parser_supports_ranges_and_rejects_out_of_scope_years() -> None:
    assert parse_years("2016-2018,2020,2023") == [2016, 2017, 2018, 2020, 2023]
    assert parse_years("2023,2016,2023") == [2016, 2023]

    with pytest.raises(ValueError, match="Unsupported reconstruction year"):
        parse_years("2015")
    with pytest.raises(ValueError, match="ascending"):
        parse_years("2020-2019")


def test_cli_defaults_to_development_period_and_validates_positive_sizes() -> None:
    parser = build_parser()

    defaults = parser.parse_args([])
    assert defaults.years == "2016-2023"
    assert defaults.output_root is None
    assert defaults.chunk_size == 100_000
    assert defaults.max_rows is None
    assert defaults.dry_run is False

    with pytest.raises(SystemExit):
        parser.parse_args(["--chunk-size", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--max-rows", "-1"])
