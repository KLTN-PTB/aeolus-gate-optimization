"""Independently audit a completed V3 run without fitting or selecting models."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from src.features.binary_improvement import prepare_frame, source_columns
from src.models.binary_improvement import binary_metrics
from src.models.binary_improvement_v3 import absolute_gate
from src.models.binary_v3_execution import EXPECTED_TARGETS
from src.models.binary_v3_protocol import roles_for


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_metrics(actual, expected):
    for name in ("ap", "roc_auc", "brier_score", "precision", "recall", "f1"):
        np.testing.assert_allclose(actual[name], expected[name], atol=1e-12, rtol=0,
                                   err_msg=f"Stored metric differs: {name}")


def raw_sample(task):
    """Read schedule columns only, from the explicitly allowed 2023 partition."""
    flow = "inbound_atl" if task == "arrival" else "outbound_atl"
    files = sorted((ROOT / "data/processed" / flow / "year=2023").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No local 2023 inference sample for {task}")
    columns = [name for name in source_columns(task) if name not in ("ARR_DELAY", "DEP_DELAY")]
    batch = next(ds.dataset(files, format="parquet").to_batches(columns=columns, batch_size=32))
    return batch.to_pandas().iloc[:16].copy()


def validate(run):
    run = run.resolve()
    summary = read_json(run / "summary.json")
    if summary["status"] != "COMPLETE" or summary.get("smoke"):
        raise ValueError("Delivery validation requires a completed full-data run")
    config = read_json(run / "resolved_config.json")
    records = read_json(run / "model_results.json")
    freeze = read_json(run / "selection_freeze.json")
    decision = read_json(run / "q4_decision_freeze.json")
    assert freeze["status"] == "FROZEN_BEFORE_Q4"
    assert decision["status"] == "FROZEN_Q4_DECISION"
    assert set(records) == set(freeze["models"])
    checks = {}

    for task, expected in EXPECTED_TARGETS.items():
        for name, value in expected.items():
            assert summary["absolute_targets"][task][name] == value
            assert freeze["absolute_targets"][task][name] == value
    checks["unchanged_v2_targets"] = "PASS"

    for relative, expected in summary["environment"]["source_hashes"].items():
        assert digest(run / "source_snapshot" / relative) == expected
        assert digest(ROOT / relative) == expected, f"Source changed since freeze: {relative}"
    sources = read_json(run / "data_sources.json")
    for key, source in sources.items():
        assert 2016 <= int(key.rsplit("_", 1)[1]) <= 2023
        for item in source.get("files", [source]):
            assert digest(ROOT / item["path"]) == item["sha256"]
    checks["source_snapshots_and_data_hashes"] = "PASS"
    checks["no_2024_data_source"] = "PASS"

    events = [json.loads(line) for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
    for path in (run / "event_fallback").glob("*.json"):
        events.append(read_json(path))
    time_of = lambda event: datetime.fromisoformat(event["at"])
    frozen_at = datetime.fromisoformat(freeze["at"])
    decision_at = datetime.fromisoformat(decision["at"])
    q4_events = [event for event in events if event["stage"] == "q4_scored"]
    confirmation = [event for event in events if event["stage"] == "historical_confirmation_complete"]
    assert len(q4_events) == len(records) and len(confirmation) == 2
    assert all(frozen_at <= time_of(event) <= decision_at for event in q4_events)
    assert all(decision_at <= time_of(event) for event in confirmation)
    checks["freeze_and_confirmation_event_order"] = "PASS"

    trials = {}
    for path in sorted(run.glob("*.sqlite3")):
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
            trials[path.stem] = dict(connection.execute("SELECT state, COUNT(*) FROM trials GROUP BY state"))
    assert len(trials) == 12
    assert all(not counts.get("RUNNING", 0) for counts in trials.values())
    assert sum(sum(counts.values()) for counts in trials.values()) <= 192
    verification = [read_json(path) for path in (run / "verification").glob("*.json")]
    complete = [item for item in verification if item["status"] == "COMPLETE"]
    for item in complete:
        assert {fold["quarter"] for fold in item["records"]} == set(config["verification_quarters"])
    checks["historical_verification_roles"] = "PASS"

    baseline_run = ROOT / config["baseline_run"]
    models = {}
    for task in config["tasks"]:
        predictions = pd.read_parquet(run / "predictions" / f"{task}_q4.parquet")
        original = pd.read_parquet(baseline_run / task / "xgboost_baseline_2022.parquet")
        original = original.loc[pd.to_datetime(original["__date"]).dt.quarter.eq(4)]
        assert len(predictions) == len(original)
        assert predictions["__key"].is_unique and original["__key"].is_unique
        aligned = original.set_index("__key").loc[predictions["__key"]]
        np.testing.assert_array_equal(predictions["__target"], aligned["__target"])
        np.testing.assert_array_equal(predictions["frozen_v2"], aligned.probability)
        baseline_record = read_json(baseline_run / task / "xgboost_baseline_metrics.json")
        assert digest(baseline_run / task / "xgboost_baseline_metrics.json") == summary["absolute_targets"][task]["baseline_metrics_sha256"]
        compare_metrics(binary_metrics(predictions["__target"], aligned.probability,
                        float(aligned.threshold.iloc[0])), baseline_record["q4_selected_threshold"])
        sample = raw_sample(task)
        prepared = prepare_frame(sample, task, inference=True)
        historical = pd.read_parquet(run / "predictions" / f"{task}_2023.parquet")
        for identifier, record in records.items():
            if record["task"] != task:
                continue
            frozen = freeze["models"][identifier]
            path = (run / record["path"]).resolve()
            assert path.is_relative_to(run)
            assert digest(path) == record["sha256"] == frozen["sha256"]
            assert record["threshold"] == frozen["threshold"]
            assert record["cpu_reload"] == "PASS"
            bundle = joblib.load(path)
            assert bundle.metadata["inference_device"] == "cpu"
            assert bundle.threshold == record["threshold"]
            assert bundle.alpha == record["spec"]["alpha"]
            assert bundle.metadata["smoke"] is False
            assert bundle.metadata["untouched_test_available"] is False
            assert bundle.metadata["train_end"] == str(roles_for(record["branch"], "2022Q4").train_end)
            assert bundle.metadata["cutoff_hours"] == 2 and bundle.metadata["delay_minutes"] == 15
            assert record["threshold_selection"]["precision_floor"] == EXPECTED_TARGETS[task]["precision_min"]
            for classifier in (bundle.classifier, bundle.expert):
                if classifier is not None and hasattr(classifier, "get_booster"):
                    assert classifier.get_params()["device"] == "cpu"
                    booster_config = json.loads(classifier.get_booster().save_config())
                    assert booster_config["learner"]["generic_param"]["device"] == "cpu"
            inference = bundle.predict_schedule(sample)
            assert len(inference) == len(prepared)
            np.testing.assert_array_equal(inference.flight_key, prepared["__key"])
            assert np.isfinite(inference.p_delay).all() and inference.p_delay.between(0, 1).all()
            np.testing.assert_allclose(inference.p_delay, bundle.predict_proba(prepared)[:, 1], atol=1e-12, rtol=0)
            np.testing.assert_array_equal(inference.predicted_delayed, inference.p_delay >= bundle.threshold)
            metrics = binary_metrics(predictions["__target"], predictions[identifier], record["threshold"])
            compare_metrics(metrics, record["q4"]["metrics"])
            gate = absolute_gate(metrics, EXPECTED_TARGETS[task], record["threshold_selection"])
            assert gate["checks"] == record["q4"]["gate"]["checks"]
            assert gate["passed"] == record["q4"]["gate"]["passed"]
            if record["seed"] == config["seed"]:
                related = [item for item in records.values() if item["task"] == task
                           and item["branch"] == record["branch"] and item["spec"] == record["spec"]]
                stability = {str(item["seed"]): item["q4"]["gate"]["passed"] for item in related}
                assert set(stability) == {str(seed) for seed in [config["seed"], *config["stability_seeds"]]}
                assert stability == record["seed_stability"]
                assert all(stability.values()) == record["all_seeds_pass"]
                uncertainty = record["q4"]["uncertainty"]
                assert uncertainty["iterations"] == 1000 and uncertainty["block_days"] == 7
                assert set(uncertainty["delta_ci_95"]) >= {"ap", "roc_auc", "brier_score", "f1"}
                compare_metrics(binary_metrics(historical["__target"], historical[identifier], record["threshold"]),
                                record["historical_2023"]["metrics"])
            models[identifier] = {"sha256": record["sha256"], "cpu_schedule_inference": "PASS",
                                  "q4_metrics_recomputed": "PASS", "size_bytes": path.stat().st_size}
        task_decision = decision["tasks"][task]
        primary_pass = [record for record in records.values() if record["task"] == task
                        and record["seed"] == config["seed"] and record["q4"]["gate"]["passed"]]
        assert bool(primary_pass) == (task_decision["status"] == "Q4_PASS")
        if primary_pass:
            winner = records[task_decision["model_id"]]
            assert winner in primary_pass
            assert task_decision["winner_role"] == winner["role"]
            best_ap = max(item["q4"]["metrics"]["ap"] for item in primary_pass)
            tied = [item for item in primary_pass if item["q4"]["metrics"]["ap"] >= best_ap - .005]
            expected_winner = min(tied, key=lambda item: (item["q4"]["metrics"]["brier_score"], item["q4"]["inference_seconds"]))
            assert winner["id"] == expected_winner["id"]
        assert task_decision == summary["tasks"][task]
    checks["q4_full_population_labels_and_v2_baseline"] = "PASS"
    checks["portable_cpu_models_raw_schedule_inference"] = "PASS"
    checks["q4_and_2023_metrics_recomputed"] = "PASS"
    checks["bootstrap_policy_and_frozen_decisions"] = "PASS"

    report = {"status": "PASS", "at": datetime.now(timezone.utc).isoformat(),
              "run": str(run.relative_to(ROOT)), "checks": checks, "trials": trials,
              "complete_verifications": len(complete), "models": models,
              "goal_both_tasks_pass": all(value["status"] == "Q4_PASS" for value in decision["tasks"].values())}
    (run / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_path = run / "RESULTS.vi.md"
    text = report_path.read_text(encoding="utf-8")
    marker = "## Nghiệm thu độc lập"
    if marker not in text:
        lines = ["", marker, "", f"Kiểm tra tính toàn vẹn: **PASS**, {len(models)} model CPU.",
                 "Đã tính lại chỉ số Q4/2022 và năm 2023 từ dự đoán lưu trên đĩa, đối chiếu đầy đủ quần thể với V2,",
                 "kiểm tra mã băm và thử suy luận từ lịch bay không có cột nhãn. Chi tiết: `validation.json`.", ""]
        implementation_path = run / "implementation_checks.json"
        if implementation_path.exists():
            regression = read_json(implementation_path)["regression"]
            lines.extend([f"Kiểm thử hồi quy: **{regression['passed']} ca đạt**.", ""])
        for task, value in decision["tasks"].items():
            if value["status"] != "Q4_PASS":
                continue
            winner = records[value["model_id"]]
            lines.extend([f"### {task}: `{winner['id']}`", "",
                f"Vai trò: `{winner['role']}`; ổn định cả ba seed: `{winner['all_seeds_pass']}`.",
                f"Nhóm đặc trưng `{winner['spec']['group']}`, họ `{winner['spec']['family']}`, "
                f"cửa sổ năm `{winner['spec']['window']}` (0 = toàn bộ), alpha DL `{winner['spec']['alpha']}`.",
                "Khoảng tin cậy 95% cho chênh lệch so với V2 (1.000 mẫu khối ghép cặp 7 ngày):", ""])
            for name, interval in winner["q4"]["uncertainty"]["delta_ci_95"].items():
                lines.append(f"- {name}: [{interval[0]:.6f}, {interval[1]:.6f}].")
            lines.append("")
        report_path.write_text(text + "\n".join(lines), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    result = validate(args.run)
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "model_count": len(result["models"]), "goal_both_tasks_pass": result["goal_both_tasks_pass"]}, indent=2))
