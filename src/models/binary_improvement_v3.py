"""V3 calibrated classifiers, portable DL experts and frozen acceptance gates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import brier_score_loss, precision_recall_curve, log_loss
from scipy.sparse import hstack

from src.features.binary_improvement import prepare_frame
from src.models.binary_improvement import (ProbabilityCalibrator, binary_metrics,
    positive_probability, validate_probabilities, paired_block_bootstrap)


@dataclass
class CarrierCalibrator:
    method: str = "sigmoid"
    regularization: float = 1.0
    min_rows: int = 1000
    min_positives: int = 100
    global_calibrator: Any = None
    model: Any = None
    encoder: Any = None
    supported: set = field(default_factory=set)

    def fit(self, p, y, carriers):
        p = validate_probabilities(p, len(y))
        carriers = pd.Series(np.asarray(carriers)).fillna("__MISSING__").astype(str)
        if self.method != "carrier":
            self.global_calibrator = ProbabilityCalibrator(self.method).fit(p, y)
            return self
        self.global_calibrator = ProbabilityCalibrator("sigmoid").fit(p, y)
        stats = pd.DataFrame({"carrier": carriers, "y": np.asarray(y)}).groupby("carrier").y.agg(["count", "sum"])
        self.supported = set(stats.index[(stats["count"] >= self.min_rows) & (stats["sum"] >= self.min_positives)])
        self.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
        categories = self.encoder.fit_transform(carriers.to_numpy().reshape(-1, 1))
        design = hstack([logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1), categories]).tocsr()
        self.model = LogisticRegression(C=self.regularization, max_iter=400, random_state=202601).fit(design, y)
        if self.model.coef_[0, 0] <= 0:
            raise ValueError("Non-monotone within-carrier calibrator rejected")
        return self

    def transform(self, p, carriers):
        p = validate_probabilities(p)
        if not len(p):
            return p
        result = self.global_calibrator.transform(p)
        if self.method == "carrier":
            carrier = pd.Series(np.asarray(carriers)).fillna("__MISSING__").astype(str)
            mask = carrier.isin(self.supported).to_numpy()
            if mask.any():
                cats = self.encoder.transform(carrier.to_numpy().reshape(-1, 1))
                design = hstack([logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1), cats]).tocsr()
                result[mask] = positive_probability(self.model, design[mask])
        return validate_probabilities(result)


def choose_calibration(fit, select, policy):
    """Inputs: probability, label, carrier tuples; no threshold or score labels."""
    scores = {}
    specifications = [("identity", 1), ("sigmoid", 1), ("isotonic", 1)] + [("carrier", c) for c in (.1, 1., 10.)]
    for method, c in specifications:
        name = method if method != "carrier" else f"carrier_{c}"
        try:
            model = CarrierCalibrator(method, c, policy["group_min_rows"], policy["group_min_positives"]).fit(*fit)
            p = model.transform(select[0], select[2])
            scores[name] = {"brier_score": float(brier_score_loss(select[1], p)),
                "log_loss": float(log_loss(select[1], p, labels=[0, 1])), "method": method, "C": c}
        except ValueError as exc:
            scores[name] = {"status": "REJECTED", "reason": str(exc)}
    valid = {name: value for name, value in scores.items() if "brier_score" in value}
    if not valid:
        raise ValueError("No valid probability calibrator")
    best = min(v["brier_score"] for v in valid.values())
    # Prefer simple calibration within the same declared Brier indifference band.
    order = ["sigmoid", "identity", "isotonic", "carrier_0.1", "carrier_1.0", "carrier_10.0"]
    chosen = next(name for name in order if name in valid and valid[name]["brier_score"] <= best + policy["calibration_indifference"])
    spec = valid[chosen]
    pooled = tuple(np.concatenate([np.asarray(fit[i]), np.asarray(select[i])]) for i in range(3))
    model = CarrierCalibrator(spec["method"], spec["C"], policy["group_min_rows"], policy["group_min_positives"]).fit(*pooled)
    return model, {"chosen": chosen, "scores": scores}


def fixed_precision_threshold(y, p, floor):
    y = np.asarray(y)
    p = validate_probabilities(p, len(y))
    if len(np.unique(y)) != 2 or not 0 <= floor <= 1:
        raise ValueError("Threshold requires binary labels and a valid fixed floor")
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    feasible = np.flatnonzero(precision[:-1] >= floor)
    if not len(feasible):
        return {"status": "NO_FEASIBLE_THRESHOLD", "threshold": .5, "precision_floor": float(floor)}
    best = max(feasible, key=lambda i: (f1[i], precision[i], thresholds[i]))
    return {"status": "SELECTED", "threshold": float(thresholds[best]), "precision_floor": float(floor),
            "f1": float(f1[best]), "precision": float(precision[best]), "recall": float(recall[best])}


def absolute_gate(metrics, targets, threshold_info):
    checks = {"ap": metrics["ap"] >= targets["ap_min"],
        "roc_auc": metrics["roc_auc"] >= targets["roc_min"],
        "brier_score": metrics["brier_score"] <= targets["brier_max"],
        "f1": metrics["f1"] >= targets["f1_min"],
        "precision": metrics["precision"] >= targets["precision_min"],
        "threshold_feasible": threshold_info["status"] == "SELECTED"}
    return {"passed": bool(all(checks.values())), "checks": {k: bool(v) for k, v in checks.items()},
            "targets": targets}


@dataclass
class V3Bundle:
    encoder: Any
    classifier: Any
    expert: Any = None
    alpha: float = 0.
    calibrator: Any = None
    threshold: float = .5
    metadata: dict = field(default_factory=dict)
    classes_: np.ndarray = field(default_factory=lambda: np.array([0, 1]))

    def components(self, X):
        if not len(X):
            return np.empty(0), np.empty(0)
        data = self.encoder.transform(X)
        global_p = positive_probability(self.classifier, data)
        expert_p = global_p.copy()
        mask = X.OP_CARRIER.eq("DL").to_numpy()
        if self.expert is not None and mask.any():
            subset = data.loc[mask] if isinstance(data, pd.DataFrame) else data[mask]
            expert_p[mask] = positive_probability(self.expert, subset)
        return global_p, expert_p

    def raw_probability(self, X):
        global_p, expert_p = self.components(X)
        return (1 - self.alpha) * global_p + self.alpha * expert_p

    def predict_proba(self, X):
        p = self.raw_probability(X)
        if self.calibrator is not None:
            p = self.calibrator.transform(p, X.OP_CARRIER)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(np.int8)

    def predict_schedule(self, raw):
        X = prepare_frame(raw, self.metadata["task"], inference=True)
        p = self.predict_proba(X)[:, 1]
        return pd.DataFrame({"flight_key": X["__key"], "p_delay": p,
                             "predicted_delayed": p >= self.threshold, "decision_threshold": self.threshold})

    def to_cpu(self):
        for classifier in (self.classifier, self.expert):
            if classifier is not None and hasattr(classifier, "get_booster"):
                classifier.set_params(device="cpu")
        self.metadata["inference_device"] = "cpu"
        return self


def bootstrap_with_f1(dates, y, candidate, baseline, candidate_threshold, baseline_threshold,
                      iterations=1000, seed=202601):
    result = paired_block_bootstrap(dates, y, candidate, baseline, iterations=iterations, seed=seed)
    date = pd.to_datetime(dates)
    _, blocks = np.unique(((date - date.min()).dt.days // 7).to_numpy(), return_inverse=True)
    count = int(blocks.max()) + 1
    y = np.asarray(y)
    statistics = []
    for p, threshold in [(candidate, candidate_threshold), (baseline, baseline_threshold)]:
        pred = np.asarray(p) >= threshold
        statistics.append([np.bincount(blocks, weights=mask, minlength=count)
                           for mask in [pred & (y == 1), pred & (y == 0), ~pred & (y == 1)]])
    rng = np.random.default_rng(seed)
    delta = []
    for _ in range(iterations):
        w = rng.multinomial(count, np.full(count, 1 / count))
        f1s = []
        for tp, fp, fn in statistics:
            tp, fp, fn = np.dot(w, tp), np.dot(w, fp), np.dot(w, fn)
            f1s.append(2 * tp / max(1, 2 * tp + fp + fn))
        delta.append(f1s[0] - f1s[1])
    result.setdefault("delta_ci_95", {})["f1"] = [float(v) for v in np.quantile(delta, [.025, .975])]
    return result
