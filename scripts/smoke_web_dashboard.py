"""Exercise the running local API, including its real worker subprocess.

Default input is explicitly illustrative; --file uses a real raw Parquet.
This does not open or automate a browser.
"""
import argparse
import io
import json
from pathlib import Path
import re
import time
import zipfile

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--file", type=Path, action="append")
    parser.add_argument("--date", default="2026-07-01")
    parser.add_argument("--solver", choices=["greedy", "cpsat", "hybrid"], default="greedy")
    parser.add_argument("--gates", type=int, default=150)
    parser.add_argument("--remote", type=int, default=0)
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=180) as client:
        page = client.get("/")
        page.raise_for_status()
        for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text):
            client.get(asset).raise_for_status()
        if args.file:
            files = [("files", (path.name, path.read_bytes(), "application/octet-stream")) for path in args.file]
        else:
            sample = client.get("/api/example.parquet")
            sample.raise_for_status()
            files = [("files", ("ILLUSTRATIVE_ONLY_ATL_schedule.parquet", sample.content, "application/octet-stream"))]
        uploaded = client.post("/api/datasets", files=files)
        uploaded.raise_for_status()
        report = uploaded.json()
        if not report["can_run"]:
            raise ValueError(json.dumps(report, ensure_ascii=True))
        run = client.post("/api/runs", json={"dataset_id": report["id"], "service_date": args.date,
            "solver": args.solver, "preset": "custom", "contact_gates": args.gates, "remote_gates": args.remote})
        run.raise_for_status()
        run_id = run.json()["id"]
        print(json.dumps({"run_id": run_id, "dates": report["dates"], "solver": args.solver}), flush=True)
        deadline = time.monotonic() + 620
        while time.monotonic() < deadline:
            status = client.get(f"/api/runs/{run_id}").json()
            if status["status"] == "completed":
                break
            if status["status"] in ("failed", "interrupted"):
                raise RuntimeError(status)
            time.sleep(.5)
        else:
            raise TimeoutError("Worker did not finish")
        result = client.get(f"/api/runs/{run_id}/results")
        result.raise_for_status()
        summary = result.json()["summary"]
        assert summary["feasible"] and summary["independent_verifier_valid"], summary
        bundle = client.get(f"/api/runs/{run_id}/exports/bundle")
        bundle.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert "normalized.parquet" in archive.namelist()
            assert "predictions.parquet" in archive.namelist()
        print(json.dumps({"summary": summary, "bundle_bytes": len(bundle.content)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
