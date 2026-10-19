"""Dedicated subprocess entrypoint; no model deserialization from user input."""
from __future__ import annotations
import logging
import json
from pathlib import Path
import sys

import pandas as pd

from web_dashboard.contracts import RunRequest
from web_dashboard.pipeline import run_pipeline
from web_dashboard.storage import Store


def execute(root: Path, run_id: str) -> None:
    store = Store(root)
    run = store.run(run_id)
    try:
        request = RunRequest.model_validate(run["config"])
        with store.connect() as db:
            db.execute("UPDATE runs SET config=? WHERE id=?", (json.dumps(request.model_dump(mode="json")), run_id))
        report = store.dataset(request.dataset_id)
        if not report or not report["can_run"]:
            raise ValueError("Dữ liệu chưa vượt qua kiểm tra đầu vào.")
        table = pd.read_parquet(root / "datasets" / request.dataset_id / "normalized.parquet")
        def progress(stage):
            store.update(run_id, status="running", stage=stage)
        run_pipeline(table, request, root / "runs" / run_id, report, progress)
        store.update(run_id, status="completed", stage="done")
    except Exception as exc:
        logging.exception("End-to-end run failed")
        store.update(run_id, status="failed", stage=store.run(run_id)["stage"], error=str(exc))


if __name__ == "__main__":
    execute(Path(sys.argv[1]), sys.argv[2])
