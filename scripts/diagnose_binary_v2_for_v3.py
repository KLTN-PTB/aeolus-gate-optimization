"""Persist descriptive V2 error analysis; oracle thresholds are not deployable."""
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve
from src.models.binary_improvement import binary_metrics
from src.models.binary_improvement_execution import digest, write_json


def diagnose(parent, output):
    result = {"role": "posthoc_historical_error_analysis_not_model_selection_input",
        "oracle_thresholds_deployable": False, "tasks": {}}
    for task in ("arrival", "departure"):
        feature_path = parent / "cache" / task / "2022.parquet"
        features = pd.read_parquet(feature_path)
        records = {}
        for name in ("xgboost_baseline", "xgboost_candidate", "hgb_candidate"):
            path = parent / task / f"{name}_2022.parquet"
            rows = pd.read_parquet(path)
            old = json.loads((parent / task / f"{name}_metrics.json").read_text())
            floor = old["threshold_selection"]["precision_floor"]
            quarters = {}
            for quarter in range(1, 5):
                f = rows.loc[rows["__date"].dt.quarter.eq(quarter)]
                p, y = f.probability.to_numpy(), f["__target"].to_numpy()
                precision, recall, thresholds = precision_recall_curve(y, p)
                f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
                valid = np.flatnonzero(precision[:-1] >= floor)
                best = max(valid, key=lambda i: f1[i]) if len(valid) else None
                quarters[quarter] = {"metrics": binary_metrics(y, p, f.threshold.iloc[0]),
                    "mean_probability": float(p.mean()),
                    "oracle_f1_diagnostic_only": float(f1[best]) if best is not None else None,
                    "oracle_threshold_diagnostic_only": float(thresholds[best]) if best is not None else None}
            q4 = rows.loc[rows["__date"].dt.quarter.eq(4)].merge(features[["__key", "OP_CARRIER"]], on="__key", validate="one_to_one")
            groups = {carrier: binary_metrics(f["__target"], f.probability, f.threshold.iloc[0])
                      for carrier, f in q4.groupby("OP_CARRIER")}
            q4["fn"] = q4["__target"].eq(1) & q4.probability.lt(q4.threshold)
            by_day = q4.groupby("__date").agg(n=("__target", "size"), positives=("__target", "sum"), fn=("fn", "sum"))
            records[name] = {"prediction_source_sha256": digest(path), "quarters": quarters,
                "q4_carriers": groups, "top_fn_days": by_day.nlargest(10, "fn").to_dict("index"),
                "top_10_fn_day_share": float(by_day.nlargest(10, "fn").fn.sum() / max(1, by_day.fn.sum()))}
        result["tasks"][task] = {"models": records,
            "q4_prepared_missing_counts": features.loc[features["__date"].dt.quarter.eq(4)].isna().sum().to_dict(),
            "quarter_prevalence": features.groupby(features["__date"].dt.quarter)["__target"].mean().to_dict()}
    # JSON object keys must be strings, including calendar-day diagnostic keys.
    for value in result["tasks"].values():
        for record in value["models"].values():
            record["top_fn_days"] = {str(k): v for k, v in record["top_fn_days"].items()}
    write_json(output, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=ROOT / "artifacts/binary_improvement_v2/full_fixed_iterations_20261021")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/binary_improvement_v3/diagnostic_v2_20261021.json")
    args = parser.parse_args()
    diagnose(args.parent, args.output)
