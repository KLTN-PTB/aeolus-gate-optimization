import json
from pathlib import Path

from src.data.chain_inspection import _parse_chain_filename, inspect_chain_archive


ROOT = Path(__file__).resolve().parents[1]


def test_filename_parser_supports_observed_orders() -> None:
    assert _parse_chain_filename("test_flight_chain_2016.pt") == ("test", 2016)
    assert _parse_chain_filename("flight_chain_test_2024.pt") == ("test", 2024)


def test_metadata_inspection_does_not_read_tensor_storage() -> None:
    source = ROOT / "data" / "raw" / "chain" / "2016" / "test_flight_chain_2016.pt"
    before = (source.stat().st_size, source.stat().st_mtime_ns)

    report = inspect_chain_archive(source, project_root=ROOT)

    after = (source.stat().st_size, source.stat().st_mtime_ns)
    assert report["year"] == 2016
    assert report["split"] == "test"
    assert report["container"] == "pytorch_zip_archive"
    assert report["tensor_count"] == 5
    assert [tensor["shape"][1:] for tensor in report["tensors"]] == [
        (6, 7),
        (6, 8),
        (6, 2),
        (),
        (6, 2),
    ]
    assert [tensor["dtype"] for tensor in report["tensors"]] == [
        "float32",
        "int16",
        "int8",
        "int64",
        "int16",
    ]
    assert report["storage_payload_bytes_read"] == 0
    assert report["pickle_metadata_bytes_read"] <= 64 * 1024
    assert before == after


def test_generated_manifest_covers_all_archives_and_records_drift() -> None:
    path = ROOT / "artifacts" / "manifests" / "flight_chain_structure_audit_v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["file_count"] == 27
    assert manifest["years"] == list(range(2016, 2025))
    assert manifest["total_source_bytes"] == 13_751_334_923
    assert manifest["cross_year_structure_consistent"] is False
    assert all(report["storage_payload_bytes_read"] == 0 for report in manifest["reports"])

    by_year = {
        year: [report for report in manifest["reports"] if report["year"] == year]
        for year in range(2016, 2025)
    }
    assert all(len(reports) == 3 for reports in by_year.values())
    assert all(report["tensor_count"] == 5 for year in range(2016, 2024) for report in by_year[year])
    assert all(report["tensor_count"] == 4 for report in by_year[2024])
