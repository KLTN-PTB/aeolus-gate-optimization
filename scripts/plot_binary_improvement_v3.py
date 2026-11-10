"""Plot frozen V3 gate margins; never selects or retrains a model."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


def plot(run):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "COMPLETE" or summary.get("smoke"):
        raise ValueError("Only completed full-data results may be plotted for delivery")
    records = json.loads((run / "model_results.json").read_text(encoding="utf-8"))
    figure, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
    for ax, task in zip(axes, ("arrival", "departure")):
        target = summary["absolute_targets"][task]
        rows = [r for r in records.values() if r["task"] == task and r["seed"] == 202601]
        labels, actual, margins = [], [], []
        limits = np.array([target[k] for k in ("ap_min", "roc_min", "brier_max", "f1_min", "precision_min")])
        for row in rows:
            metrics = row["q4"]["metrics"]
            values = np.array([metrics[k] for k in ("ap", "roc_auc", "brier_score", "f1", "precision")])
            delta = values - limits
            delta[2] *= -1
            scale = np.array([.005, .005, target["brier_max"] / 1.02 * .02, .02, .05])
            margins.append(delta / scale)
            actual.append(values)
            suffix = f" DL={row['spec']['alpha']}" if row["spec"].get("alpha") else ""
            labels.append(f"{row['branch']} | {row['spec']['family']} | {row['spec']['group']}{suffix}")
        values = np.asarray(margins)
        ax.imshow(values >= 0, cmap=ListedColormap(["#FDE2E2", "#DCF3E4"]), vmin=0, vmax=1, aspect="auto")
        for i, row in enumerate(actual):
            for j, value in enumerate(row):
                passed = values[i, j] >= 0
                ax.text(j, i, f"{value:.4f}\n{'PASS' if passed else 'FAIL'}", ha="center", va="center",
                        fontsize=9, color="#166534" if passed else "#991B1B")
        ax.set_yticks(range(len(labels)), labels, fontsize=9)
        ax.set_xticks(range(5), [f"AP >= {limits[0]:.4f}", f"ROC >= {limits[1]:.4f}",
            f"Brier <= {limits[2]:.4f}", f"F1 >= {limits[3]:.4f}", f"Precision >= {limits[4]:.4f}"])
        ax.set_title(task.title() + " — all five metrics and a feasible pre-Q4 threshold required")
    figure.suptitle("Q4/2022 historical development targets — green passes, red fails; not an untouched test", fontsize=12)
    folder = run / "figures"
    folder.mkdir(exist_ok=True)
    figure.savefig(folder / "q4_acceptance.png", dpi=160)
    plt.close(figure)
    report = run / "RESULTS.vi.md"
    text = report.read_text(encoding="utf-8")
    marker = "## Biểu đồ điều kiện nghiệm thu"
    if marker not in text:
        report.write_text(text + "\n" + marker + "\n\n![Điều kiện quý IV/2022](figures/q4_acceptance.png)\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    plot(args.run)
