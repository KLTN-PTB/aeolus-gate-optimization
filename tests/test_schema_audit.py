from __future__ import annotations

from pathlib import Path

import yaml

from src.data.schema_audit import SchemaAuditor


def _make_project(tmp_path: Path, csv_text: str) -> tuple[Path, Path]:
    source = tmp_path / "data" / "raw" / "tabular" / "2016" / "flight_with_weather_2016.csv"
    source.parent.mkdir(parents=True)
    source.write_text(csv_text, encoding="utf-8")
    config_path = tmp_path / "configs" / "base.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        yaml.safe_dump({"project": {"version": "test"}, "data": {"raw_tabular_path": "data/raw/tabular"}}),
        encoding="utf-8",
    )
    return tmp_path, source


def test_streaming_audit_aggregates_target_dates_missingness_and_cardinality(tmp_path: Path) -> None:
    root, source = _make_project(
        tmp_path,
        "FL_DATE,OP_CARRIER,ORIGIN,DEST,ARR_DELAY,O_TEMP,ORIGIN_INDEX,DEST_INDEX\n"
        "2016-01-01,AA,BOS,ATL,20,10,1,2\n"
        "2016-01-02,DL,JFK,ATL,-5,inf,3,2\n"
        "2016-01-03,AA,BOS,ATL,15,,1,2\n"
        "2016-01-01,AA,BOS,ATL,20,10,1,2\n",
    )
    before = source.read_bytes()
    before_mtime = source.stat().st_mtime_ns
    auditor = SchemaAuditor(project_root=root, manifest_directory=root / "manifests")

    summary = auditor.audit_year(2016, chunk_size=2, write_summary=False)

    assert summary["row_count"] == 4
    assert summary["chunks_processed"] == 2
    assert summary["fl_date"]["min"] == "2016-01-01"
    assert summary["fl_date"]["max"] == "2016-01-03"
    assert summary["missing"]["O_TEMP"]["count"] == 1
    assert summary["arr_delay"]["gte_15"] == {"count": 3, "rate_among_finite": 0.75}
    assert summary["categorical_cardinality"]["OP_CARRIER"] == 2
    assert summary["categorical_cardinality"]["ORIGIN"] == 2
    assert summary["categorical_cardinality"]["DEST"] == 1
    assert summary["airport_index"]["ORIGIN_INDEX"] == {"exists": True, "cardinality": 2}
    assert summary["duplicate_rows"]["count"] == 1
    assert summary["numeric_quality"]["O_TEMP"]["inf_count"] == 1
    assert source.read_bytes() == before
    assert source.stat().st_mtime_ns == before_mtime


def test_malformed_schema_and_resume_are_reported(tmp_path: Path) -> None:
    root, _ = _make_project(tmp_path, "FL_DATE,OP_CARRIER\n2016-01-01,AA\n")
    manifest_dir = root / "manifests"
    auditor = SchemaAuditor(project_root=root, manifest_directory=manifest_dir)

    summary = auditor.audit_year(
        2016,
        chunk_size=1,
        reference_schema={"columns": ["FL_DATE", "ARR_DELAY"], "observed_dtypes": {"FL_DATE": "string"}},
    )
    resumed = auditor.audit_year(2016, chunk_size=1, resume=True)

    assert summary["arr_delay"]["available"] is False
    assert summary["schema_difference"]["missing_from_observed"] == ["ARR_DELAY"]
    assert (manifest_dir / "schema_2016.json").is_file()
    assert resumed["resumed"] is True
