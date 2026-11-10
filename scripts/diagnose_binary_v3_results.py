"""Posthoc historical V3 diagnosis; never changes models or locked decisions."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve


def diagnose(run):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "COMPLETE" or summary["smoke"]:
        raise ValueError("Diagnosis requires completed full-data results")
    if any(value["status"] != "NO_Q4_PASS" for value in summary["tasks"].values()):
        raise ValueError("This failure-diagnosis report requires NO_Q4_PASS for both tasks")
    records = json.loads((run / "model_results.json").read_text(encoding="utf-8"))
    result = {"role": "posthoc_historical_diagnosis_only", "oracle_thresholds_deployable": False,
              "locked_decisions_changed": False, "tasks": {}}
    lines = ["", "## Phân tích sau thực nghiệm", "",
             "Phần này chỉ giải thích kết quả lịch sử, không thay đổi model, ngưỡng hoặc quyết định đã khóa.",
             "Ngưỡng oracle được tính bằng cách nhìn trước nhãn quý IV; chỉ là chẩn đoán và không được triển khai.", ""]
    for task in ("arrival", "departure"):
        targets = summary["absolute_targets"][task]
        primary = {name: record for name, record in records.items()
                   if record["task"] == task and record["seed"] == 202601}
        predictions = pd.read_parquet(run / "predictions" / f"{task}_q4.parquet")
        cache = ROOT / summary["config"]["baseline_run"] / "cache" / task / "2022.parquet"
        population = pd.read_parquet(cache, columns=["__date", "__target"])
        monthly = population.groupby(population["__date"].dt.month)["__target"].agg(["size", "mean"])
        models = {}
        for name, record in primary.items():
            precision, recall, thresholds = precision_recall_curve(predictions["__target"], predictions[name])
            precision, recall = precision[:-1], recall[:-1]
            f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-15)
            feasible = np.flatnonzero(precision >= targets["precision_min"])
            best = max(feasible, key=lambda i: (f1[i], precision[i], thresholds[i]))
            models[name] = {"role": record["role"], "actual_q4": record["q4"]["metrics"],
                "failed_checks": [key for key, passed in record["q4"]["gate"]["checks"].items() if not passed],
                "threshold_period": record["threshold_selection"],
                "oracle_q4_with_fixed_precision_floor": {"f1": float(f1[best]),
                    "precision": float(precision[best]), "recall": float(recall[best]),
                    "threshold": float(thresholds[best]), "deployable": False},
                "paired_delta_ci_95": record["q4"]["uncertainty"]["delta_ci_95"]}
        highest_f1 = max(models, key=lambda name: models[name]["actual_q4"]["f1"])
        maximum_oracle = max(record["oracle_q4_with_fixed_precision_floor"]["f1"] for record in models.values())
        result["tasks"][task] = {"monthly_prevalence_2022": {
            str(month): {"n": int(row["size"]), "prevalence": float(row["mean"])} for month, row in monthly.iterrows()},
            "precision_floor_to_september_prevalence_ratio": targets["precision_min"] / float(monthly.loc[9, "mean"]),
            "highest_observed_f1_model_not_a_deployment_selection": highest_f1,
            "maximum_oracle_f1_at_fixed_floor_primary_models": maximum_oracle, "models": models}
        lines.extend([f"### {task}", "",
            f"Tỷ lệ trễ tháng 7/8/9 lần lượt: {monthly.loc[7, 'mean']:.2%}, {monthly.loc[8, 'mean']:.2%}, {monthly.loc[9, 'mean']:.2%}.",
            f"Sàn Precision cố định {targets['precision_min']:.6f} bằng {targets['precision_min'] / monthly.loc[9, 'mean']:.2f} lần tỷ lệ trễ tháng 9.",
            "Đây là dịch chuyển phân phối quan sát được giữa các giai đoạn calibration và chọn ngưỡng; mức ảnh hưởng nhân quả riêng chưa được tách.", "",
            "| Model seed chính | F1 đã khóa | Oracle F1 cùng sàn Precision (không triển khai) | Điều kiện chưa đạt |",
            "|---|---:|---:|---|"])
        for name, record in models.items():
            lines.append(f"| {name} | {record['actual_q4']['f1']:.6f} | "
                         f"{record['oracle_q4_with_fixed_precision_floor']['f1']:.6f} | {', '.join(record['failed_checks'])} |")
        lines.append("")
        descriptive = models[highest_f1]
        baseline = json.loads((ROOT / summary["config"]["baseline_run"] / task /
                               "xgboost_baseline_metrics.json").read_text(encoding="utf-8"))["q4_selected_threshold"]
        lines.extend([f"Model có F1 quan sát cao nhất ở seed chính: `{highest_f1}`. "
                      "Đây là mô tả kết quả, không phải chọn model để triển khai.", ""])
        for metric in ("ap", "f1"):
            actual = descriptive["actual_q4"][metric]
            interval = descriptive["paired_delta_ci_95"][metric]
            lines.append(f"- {metric}: V2 {baseline[metric]:.6f} → V3 {actual:.6f}; "
                         f"chênh lệch {actual - baseline[metric]:+.6f}, CI 95% [{interval[0]:+.6f}, {interval[1]:+.6f}].")
        lines.append("")
        if maximum_oracle < targets["f1_min"]:
            lines.extend([f"Ngay cả F1 oracle cao nhất trong {len(models)} model seed chính ({maximum_oracle:.6f}) "
                          f"vẫn dưới mốc {targets['f1_min']:.6f} khi giữ sàn Precision.",
                          "Vì vậy, chỉ sửa ngưỡng của các model này chưa đủ; cần cải thiện khả năng phân biệt/xếp hạng trong một thử nghiệm tiếp theo.", ""])
    departure_control = result["tasks"]["departure"]["models"]["departure_B_control_s202601"]
    passed_count = sum(record["q4"]["gate"]["passed"] for record in records.values())
    lines.extend(["### Kết luận và hướng tiếp theo", "",
        f"Có {passed_count}/{len(records)} bản seed chính và seed chẩn đoán vượt mọi mốc Q4. "
        "Quyết định giữ nguyên `NO_Q4_PASS` cho cả hai bài toán vì không có model seed chính đạt đủ.",
        "Departure nhánh B cho thấy rủi ro chuyển ngưỡng từ tháng 9 sang quý IV: "
        f"đối chứng B có F1 oracle {departure_control['oracle_q4_with_fixed_precision_floor']['f1']:.6f} "
        f"so với mốc {summary['absolute_targets']['departure']['f1_min']:.6f} khi nhìn trước nhãn; "
        f"F1 thực tế tại ngưỡng đã khóa là {departure_control['actual_q4']['f1']:.6f}.",
        "Đây là bằng chứng chẩn đoán cần kiểm tra một chính sách chọn ngưỡng bền vững hơn qua nhiều giai đoạn trước quý IV, "
        "không phải căn cứ dùng ngưỡng oracle làm model đạt yêu cầu.",
        "Thử nghiệm tiếp theo cần khóa lại giao thức trước khi chạy: kiểm tra ngưỡng trên nhiều cửa sổ thời gian lịch sử, "
        "tách tác động của sàn Precision khỏi chất lượng xếp hạng và nghiên cứu thêm tín hiệu biết được tại T-2h cho Arrival. "
        "Quý IV/2022 và 2023 vẫn chỉ là dữ liệu phát triển đã xem; không thể gọi kết quả tiếp theo trên chúng là kiểm thử chưa từng xem.", ""])
    (run / "posthoc_diagnosis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    path = run / "RESULTS.vi.md"
    current = path.read_text(encoding="utf-8")
    marker = "## Phân tích sau thực nghiệm"
    if marker in current:
        current = current.split(marker)[0].rstrip() + "\n"
    path.write_text(current + "\n".join(lines), encoding="utf-8")
    print(json.dumps({task: {"highest_observed_f1_model": record["highest_observed_f1_model_not_a_deployment_selection"],
                             "maximum_oracle_f1_at_fixed_floor": record["maximum_oracle_f1_at_fixed_floor_primary_models"]}
                      for task, record in result["tasks"].items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    diagnose(args.run.resolve())
