"""Package completed research bundles for CPU inference with verified lineage.

Does not train, tune, choose a new model or modify a dashboard registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(variable, "8")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from src.models.binary_improvement import paired_block_bootstrap, binary_metrics
from src.models.binary_improvement_execution import digest, write_json


def package(run: Path, output: Path, *, bootstrap=True):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "COMPLETE" or summary.get("smoke"):
        raise ValueError("Only a completed full-data run may be packaged")
    for relative, expected in summary["environment"]["source_hashes"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Experiment source changed after training: {relative}")
    if output.exists():
        raise FileExistsError("Use a new release directory; never overwrite a model")
    output.mkdir(parents=True)
    manifest = {"protocol": "binary_improvement_v2", "source_run": str(run.relative_to(ROOT)),
        "source_summary_sha256": digest(run / "summary.json"),
        "inference_device": "cpu", "dashboard_active": False, "optimizer_active": False,
        "untouched_test_available": False, "tasks": {}}
    for task, result in summary["tasks"].items():
        task_dir = output / task
        task_dir.mkdir()
        splits = []
        for year in range(2016, 2024):
            cache = run / "cache" / task / f"{year}.parquet"
            rows = pd.read_parquet(cache, columns=["__key", "__date", "__target"])
            groups = rows.groupby(rows["__date"].dt.quarter) if year == 2022 else [(None, rows)]
            for quarter, group in groups:
                roles = {1: "calibration_fit", 2: "calibration_selection_then_refit",
                         3: "threshold_selection", 4: "candidate_selection"}
                role = roles[quarter] if year == 2022 else ("historical_confirmation" if year == 2023 else "development_training")
                keys = "\n".join(sorted(group["__key"].astype(str)))
                splits.append({"year": year, "quarter": quarter, "role": role,
                    "n": len(group), "positive_count": int(group["__target"].sum()),
                    "first_date": str(group["__date"].min()), "last_date": str(group["__date"].max()),
                    "sorted_flight_keys_sha256": hashlib.sha256(keys.encode()).hexdigest()})
        write_json(task_dir / "split_manifest.json", {"splits": splits,
            "rolling_folds": [{"train_years": list(range(2016, year)), "validation_year": year}
                              for year in (2019, 2020, 2021)], "blocked_years": [2024]})
        frame = pd.read_parquet(run / task / "historical_predictions_2023.parquet")
        baseline = frame["xgboost_baseline"].to_numpy()
        records = {}
        for name, record in result["models"].items():
            if name == "constant_baseline":
                continue
            source = run / task / f"{name}.joblib"
            parent_hash = digest(source)
            if parent_hash != record["model_sha256"]:
                raise ValueError("Model checksum differs from frozen evaluation evidence")
            model = joblib.load(source)
            sample = pd.read_parquet(run / task / "reload_sample.parquet")
            expected = model.predict_proba(sample)
            if hasattr(model.classifier, "get_booster"):
                model.classifier.set_params(device="cpu")
            model.metadata["portable_inference_device"] = "cpu"
            model.metadata["source_model_sha256"] = parent_hash
            target = task_dir / f"{name}.joblib"
            joblib.dump(model, target, compress=3)
            check_path = task_dir / "reload.npy"
            code = "import joblib,pandas as pd,numpy as np,sys; m=joblib.load(sys.argv[1]); np.save(sys.argv[3],m.predict_proba(pd.read_parquet(sys.argv[2])))"
            child = subprocess.run([sys.executable, "-c", code, str(target),
                str(run / task / "reload_sample.parquet"), str(check_path)],
                cwd=ROOT, capture_output=True, text=True, timeout=90)
            if child.returncode:
                raise RuntimeError(child.stderr)
            np.testing.assert_allclose(np.load(check_path), expected, rtol=1e-6, atol=1e-7)
            check_path.unlink()
            info = {"path": str(target.relative_to(output)), "sha256": digest(target),
                "parent_sha256": parent_hash, "threshold": model.threshold,
                "calibration": model.calibrator.method,
                "features": model.metadata["feature_set"], "fresh_cpu_reload": "PASS",
                "historical_2023": record["historical_2023"],
                "q4_promotion_gate": record.get("q4_promotion_gate")}
            if bootstrap and name.endswith("candidate"):
                info["historical_paired_uncertainty"] = paired_block_bootstrap(
                    frame["__date"], frame["__target"].to_numpy(), frame[name].to_numpy(), baseline,
                    iterations=summary["config"]["evaluation"]["bootstrap_iterations"],
                    seed=summary["config"]["seed"])
            records[name] = info
            print(f"Packaged {task}/{name}: CPU reload PASS", flush=True)
        manifest["tasks"][task] = {"recommendation": result["recommendation"], "models": records}
        write_json(output / "manifest.json", manifest)
    (output / "README.md").write_text(
        "# Portable binary research models\n\n"
        "These files include each model's encoder, preprocessing, calibration and decision threshold.\n"
        "They use CPU inference; the repository and pinned dependencies are required.\n"
        "No training dataset or separate encoder/calibrator download is required for inference.\n"
        "Consult manifest.json for the frozen decision and historical metrics for each task.\n"
        "These are historical research results, not untouched-test certification.\n"
        "Dashboard and optimizer activation remain false.\n\n"
        "```python\nimport joblib\nmodel = joblib.load('<release>/arrival/xgboost_candidate.joblib')\n"
        "result = model.predict_schedule(canonical_schedule_dataframe)\n```\n",
        encoding="utf-8")
    write_results(manifest, run, output)


def write_results(manifest, run, output):
    lines = ["# Kết quả cải thiện phân loại nhị phân V2", "",
        "Giữ dự đoán T-2h và nhãn trễ từ 15 phút; dùng dữ liệu sẵn có.",
        "Kết quả năm 2023 là đối chiếu lịch sử, không phải tập kiểm thử chưa từng được xem.",
        "Không truy cập dữ liệu 2024. Chưa kích hoạt model mới trên dashboard hoặc optimizer.", ""]
    for task, result in manifest["tasks"].items():
        lines.extend([f"## {task.title()}", "",
            "So sánh dưới đây dùng cùng các chuyến bay năm 2023, cùng protocol huấn luyện và chọn ngưỡng.", "",
            "| Model | AP | ROC-AUC | Brier ↓ | Precision | Recall | F1 | Ngưỡng |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for name, record in result["models"].items():
            m = record["historical_2023"]["selected_threshold"]
            values = " | ".join(f"{m[k]:.4f}" for k in ("ap", "roc_auc", "brier_score", "precision", "recall", "f1", "threshold"))
            lines.append(f"| {name} | {values} |")
        lines.extend(["", "Quyết định đã khóa trước khi xem đối chiếu 2023: `" + result["recommendation"]["status"] + "`.", ""])
        for name, record in result["models"].items():
            gate = record.get("q4_promotion_gate")
            if gate:
                failed = [k for k, passed in gate["checks"].items() if not passed]
                lines.append(f"- `{name}`: điều kiện quý IV/2022 chưa đạt: {', '.join(failed) if failed else 'không có'}.")
            ci = record.get("historical_paired_uncertainty", {}).get("delta_ci_95", {}).get("ap")
            if ci:
                lines.append(f"- `{name}`: khoảng tin cậy 95% cho chênh lệch AP so với baseline: [{ci[0]:.5f}, {ci[1]:.5f}], bootstrap ghép cặp theo khối 7 ngày.")
        lines.append("")
    legacy_path = ROOT / "artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet"
    if legacy_path.exists():
        old = pd.read_parquet(legacy_path, columns=["flight_key", "y_true", "prob_xgboost_calibrated"])
        current = pd.read_parquet(run / "departure/historical_predictions_2023.parquet")
        joined = current.merge(old, left_on="__key", right_on="flight_key", validate="one_to_one")
        if len(joined) != len(current) or len(joined) != len(old) or not np.array_equal(joined["__target"], joined["y_true"]):
            raise ValueError("Legacy/current Departure populations do not match")
        previous = binary_metrics(joined["y_true"], joined["prob_xgboost_calibrated"])
        write_json(output / "legacy_departure_comparison.json", {"same_rows": len(joined),
            "labels_match": True, "legacy_calibrated_xgboost_at_0_5": previous,
            "new_models": {n: r["historical_2023"]["selected_threshold"]
                           for n, r in manifest["tasks"]["departure"]["models"].items()},
            "limitation": "Training years and calibration splits differ; gains cannot be attributed only to HPO or only to threshold selection"})
        lines.extend(["## Đối chiếu Departure với classifier cũ", "",
            f"Đã ghép đúng {len(joined):,} chuyến và kiểm tra nhãn trùng khớp. Model cũ tại ngưỡng 0,5: "
            f"AP {previous['ap']:.4f}, Recall {previous['recall']:.4f}, F1 {previous['f1']:.4f}.",
            "Các model mới dùng giai đoạn huấn luyện và chia calibration khác, nên không quy toàn bộ thay đổi cho riêng HPO hoặc riêng ngưỡng.", ""])
    controls_path = run / "baseline_controls/results.json"
    if controls_path.exists():
        controls = json.loads(controls_path.read_text(encoding="utf-8"))
        if controls["status"] == "COMPLETE":
            lines.extend(["## Đối chứng trên các fold thời gian", "",
                "Các baseline dùng cấu hình cố định và cùng toàn bộ dòng validation với ứng viên; bảng này không thay đổi quyết định đã khóa.", "",
                "| Bài toán | Năm validation | AP baseline | AP XGBoost mới | AP HGB mới |",
                "|---|---:|---:|---:|---:|"])
            for task, record in controls["tasks"].items():
                for fold in record["folds"]:
                    lines.append(f"| {task} | {fold['validation_year']} | {fold['baseline']['ap']:.4f} | "
                                 f"{fold['candidates']['xgboost_candidate']['ap']:.4f} | {fold['candidates']['hgb_candidate']['ap']:.4f} |")
            lines.append("")
    lines.extend(["## Sử dụng và giới hạn", "",
        "Mỗi file joblib chứa đủ encoder, preprocessor, classifier, calibrator và ngưỡng. Bản đóng gói dùng CPU và đã kiểm tra nạp ở tiến trình Python mới.",
        "Giữ cùng mã nguồn và cài requirements-binary.txt. Không cần dữ liệu huấn luyện khi suy luận.",
        "Các model chưa đạt mọi điều kiện nâng cấp được giữ làm ứng viên nghiên cứu. Không chọn lại cấu hình/ngưỡng dựa trên năm 2023.",
        "Số liệu OOF Arrival trước đây thuộc quần thể khác; không so sánh trực tiếp với bảng năm 2023 này.", ""])
    (output / "RESULTS.vi.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--skip-bootstrap", action="store_true", help="Skip extra diagnostic CIs; frozen decision unchanged")
    args = parser.parse_args()
    package(args.run.resolve(), args.output.resolve(), bootstrap=not args.skip_bootstrap)
