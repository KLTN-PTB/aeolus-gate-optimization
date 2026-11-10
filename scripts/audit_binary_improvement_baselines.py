"""Add full rolling baseline controls without changing any frozen decision.

Reads only the completed run's prepared 2016–2021 cache. No tuning and no
calibration/test labels are consumed. Candidate metrics come from their
already completed matching rolling folds.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import json

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from src.models.binary_improvement import binary_metrics
from src.models.binary_improvement_execution import Experiment, digest, write_json


def audit(run: Path):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "COMPLETE" or summary.get("smoke"):
        raise ValueError("A completed full-data experiment is required")
    for path, expected in summary["environment"]["source_hashes"].items():
        if digest(ROOT / path) != expected:
            raise ValueError("Training source hash mismatch")
    folder = run / "baseline_controls"
    folder.mkdir(exist_ok=False)
    experiment = Experiment(summary["config"], folder)
    results = {"status": "RUNNING", "role": "descriptive_fixed_baseline_controls_no_reselection",
               "source_summary_sha256": digest(run / "summary.json"), "tasks": {}}
    with threadpool_limits(limits=summary["config"]["budget"]["threads"]):
        experiment.probe_gpu()
        for task in ("arrival", "departure"):
            rows = pd.concat([pd.read_parquet(run / "cache" / task / f"{year}.parquet")
                              for year in range(2016, 2022)], ignore_index=True)
            spec = summary["tasks"][task]["models"]["xgboost_baseline"]["spec"]
            folds = []
            for year in (2019, 2020, 2021):
                train, valid = rows.loc[rows["__year"] < year], rows.loc[rows["__year"] == year]
                _, p, seconds = experiment.fit_bundle(task, spec, train, valid, experiment.deadline)
                metrics = binary_metrics(valid["__target"], p)
                constant = binary_metrics(valid["__target"], np.full(len(valid), train["__target"].mean()))
                candidates = {}
                for name in ("xgboost_candidate", "hgb_candidate"):
                    record = json.loads((run / task / f"verification_{name}.json").read_text())
                    candidate = next(f["metrics"] for f in record["folds"] if f["validation_year"] == year)
                    assert candidate["n"] == metrics["n"]
                    candidates[name] = {"ap": candidate["ap"], "ap_delta": candidate["ap"] - metrics["ap"]}
                folds.append({"validation_year": year, "baseline": metrics, "constant": constant,
                              "candidates": candidates, "seconds": seconds})
                experiment.event("baseline_control_complete", task=task, year=year, ap=metrics["ap"])
            results["tasks"][task] = {"folds": folds,
                "baseline_macro_ap": float(np.mean([f["baseline"]["ap"] for f in folds]))}
            write_json(folder / "results.json", results)
    results["status"] = "COMPLETE"
    write_json(folder / "results.json", results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    audit(args.run.resolve())
