from __future__ import annotations

from pathlib import Path

import yaml

from src.data.load_aeolus import iter_tabular_chunks, read_tabular_header, resolve_tabular_csv


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


def test_header_and_chunk_streaming_do_not_mutate_source(tmp_path: Path) -> None:
    root, source = _make_project(
        tmp_path,
        "FL_DATE,OP_CARRIER,ARR_DELAY\n2016-01-01,AA,20\n2016-01-02,DL,-5\n2016-01-03,AA,15\n",
    )
    before = source.read_bytes()
    before_mtime = source.stat().st_mtime_ns

    assert read_tabular_header(2016, project_root=root) == ["FL_DATE", "OP_CARRIER", "ARR_DELAY"]
    chunks = list(iter_tabular_chunks(2016, project_root=root, chunk_size=2))

    assert [len(chunk.rows) for chunk in chunks] == [2, 1]
    assert [chunk.start_row for chunk in chunks] == [1, 3]
    assert chunks[0].rows[0]["OP_CARRIER"] == "AA"
    assert source.read_bytes() == before
    assert source.stat().st_mtime_ns == before_mtime


def test_column_selection_and_bounded_read(tmp_path: Path) -> None:
    root, _ = _make_project(
        tmp_path,
        "FL_DATE,OP_CARRIER,ARR_DELAY\n2016-01-01,AA,20\n2016-01-02,DL,-5\n",
    )
    chunks = list(
        iter_tabular_chunks(
            2016,
            project_root=root,
            chunk_size=10,
            columns=["ARR_DELAY"],
            max_rows=1,
        )
    )

    assert len(chunks) == 1
    assert chunks[0].rows == [{"ARR_DELAY": "20"}]
    assert resolve_tabular_csv(2016, project_root=root).name == "flight_with_weather_2016.csv"
