"""Portable probability bundles and evaluation for binary_improvement_v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             confusion_matrix, log_loss, precision_recall_curve,
                             roc_auc_score)

from src.features.binary_improvement import prepare_frame


def validate_probabilities(p, n: int | None = None) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    if p.ndim != 1 or (n is not None and len(p) != n):
        raise ValueError("Expected one aligned positive-class probability per row")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Probabilities must be finite and within [0, 1]")
    return p


def positive_probability(estimator, X) -> np.ndarray:
    classes = np.asarray(estimator.classes_)
    where = np.flatnonzero(classes == 1)
    if len(where) != 1:
        raise ValueError("Estimator must explicitly contain positive class 1")
    return validate_probabilities(estimator.predict_proba(X)[:, where[0]], X.shape[0])


@dataclass
class ProbabilityCalibrator:
    method: str = "identity"
    estimator: Any = None

    def fit(self, p, y):
        p = validate_probabilities(p, len(y))
        if len(np.unique(y)) != 2:
            raise ValueError("Calibration requires both classes")
        if self.method == "sigmoid":
            self.estimator = LogisticRegression(C=1e6, max_iter=300, random_state=202601)
            self.estimator.fit(logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1), y)
            if self.estimator.coef_[0, 0] <= 0:
                raise ValueError("Sigmoid calibration must preserve ranking")
        elif self.method == "isotonic":
            self.estimator = IsotonicRegression(out_of_bounds="clip").fit(p, y)
        elif self.method != "identity":
            raise ValueError("Unknown calibration method")
        return self

    def transform(self, p):
        p = validate_probabilities(p)
        if not len(p):
            return p
        if self.method == "sigmoid":
            p = positive_probability(self.estimator, logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1))
        elif self.method == "isotonic":
            p = self.estimator.predict(p)
        return validate_probabilities(p)


def select_calibrator(q1_p, q1_y, q2_p, q2_y, *, indifference=0.001):
    scores, fitted = {}, {}
    for name in ("identity", "sigmoid", "isotonic"):
        cal = ProbabilityCalibrator(name).fit(q1_p, q1_y)
        p = cal.transform(q2_p)
        scores[name] = {"brier_score": float(brier_score_loss(q2_y, p)),
                        "log_loss": float(log_loss(q2_y, p, labels=[0, 1]))}
        fitted[name] = cal
    best_brier = min(v["brier_score"] for v in scores.values())
    # Frozen simplicity order within the predeclared indifference band.
    choice = next(name for name in ("sigmoid", "identity", "isotonic")
                  if scores[name]["brier_score"] <= best_brier + indifference)
    cal = ProbabilityCalibrator(choice).fit(
        np.concatenate([q1_p, q2_p]), np.concatenate([q1_y, q2_y]))
    return cal, scores


def select_threshold(y, p, precision_multiplier: float = 1.5) -> dict:
    y = np.asarray(y)
    p = validate_probabilities(p, len(y))
    if not len(y) or len(np.unique(y)) != 2:
        raise ValueError("Threshold selection requires both classes")
    precision, recall, thresholds = precision_recall_curve(y, p)
    precision, recall = precision[:-1], recall[:-1]
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-15)
    floor = float(np.mean(y) * precision_multiplier)
    valid = np.flatnonzero(precision >= floor)
    if not len(valid):
        return {"threshold": 0.5, "precision_floor": floor, "status": "NO_FEASIBLE_THRESHOLD"}
    best = max(valid, key=lambda i: (f1[i], precision[i], thresholds[i]))
    return {"threshold": float(thresholds[best]), "precision_floor": floor,
            "status": "SELECTED", "selection_f1": float(f1[best]),
            "selection_precision": float(precision[best]), "selection_recall": float(recall[best])}


def binary_metrics(y, p, threshold: float = 0.5) -> dict:
    y = np.asarray(y, dtype=np.int8)
    p = validate_probabilities(p, len(y))
    if not len(y):
        return {"n": 0, "status": "EMPTY"}
    tn, fp, fn, tp = confusion_matrix(y, p >= threshold, labels=[0, 1]).ravel()
    precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
    bins = np.minimum((p * 10).astype(int), 9)
    count = np.bincount(bins, minlength=10)
    sump = np.bincount(bins, weights=p, minlength=10)
    sumy = np.bincount(bins, weights=y, minlength=10)
    ece = float(np.abs(sump - sumy).sum() / len(y))
    if len(np.unique(y)) == 2:
        pr, re, _ = precision_recall_curve(y, p)
    else:
        pr, re = np.array([]), np.array([])
    return {"n": len(y), "prevalence": float(y.mean()), "threshold": float(threshold),
            "ap": float(average_precision_score(y, p)) if y.sum() else None,
            "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            "brier_score": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1])), "ece_10": ece,
            "precision": float(precision), "recall": float(recall),
            "f1": float(2 * precision * recall / max(1e-15, precision + recall)),
            "alert_rate": float((p >= threshold).mean()),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "recall_at_precision": {str(floor): float(re[pr >= floor].max(initial=0))
                                    for floor in (0.3, 0.4, 0.5)},
            "reliability": [{"count": int(count[i]),
                             "mean_probability": float(sump[i] / count[i]) if count[i] else None,
                             "observed_rate": float(sumy[i] / count[i]) if count[i] else None}
                            for i in range(10)]}


def promotion_gate(candidate: dict, baseline: dict, threshold_info: dict, policy: dict | None = None) -> dict:
    policy = policy or {}
    checks = {
        "ap_gain": candidate["ap"] - baseline["ap"] >= policy.get("ap_min_gain", 0.005),
        "roc_noninferiority": candidate["roc_auc"] >= baseline["roc_auc"] - policy.get("roc_max_drop", 0.005),
        "brier_guard": candidate["brier_score"] <= baseline["brier_score"] * (1 + policy.get("brier_max_relative_increase", 0.02)),
        "f1_gain": candidate["f1"] >= baseline["f1"] + policy.get("f1_min_gain", 0.02),
        "precision_floor": candidate["precision"] >= threshold_info["precision_floor"],
        "threshold_feasible": threshold_info["status"] == "SELECTED",
    }
    return {"passed": bool(all(checks.values())), "checks": {k: bool(v) for k, v in checks.items()}}


@dataclass
class BinaryModelBundle:
    encoder: Any
    preprocessor: Any
    classifier: Any
    calibrator: ProbabilityCalibrator = field(default_factory=ProbabilityCalibrator)
    threshold: float = 0.5
    metadata: dict = field(default_factory=dict)
    classes_: np.ndarray = field(default_factory=lambda: np.array([0, 1]))

    def raw_probability(self, X: pd.DataFrame) -> np.ndarray:
        if not len(X):
            return np.empty(0)
        features = self.preprocessor.transform(self.encoder.transform(X))
        return positive_probability(self.classifier, features)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.calibrator.transform(self.raw_probability(X))
        return np.column_stack([1 - p, p])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(np.int8)

    def predict_schedule(self, raw: pd.DataFrame) -> pd.DataFrame:
        frame = prepare_frame(raw, self.metadata["task"], inference=True)
        p = self.predict_proba(frame)[:, 1]
        return pd.DataFrame({"flight_key": frame["__key"], "p_delay": p,
                             "predicted_delayed": p >= self.threshold,
                             "decision_threshold": self.threshold})


def paired_block_bootstrap(dates, y, candidate, baseline, *, iterations=1000, seed=202601):
    """Paired 7-calendar-day block bootstrap; sort scores once, retain tied scores."""
    dates = pd.to_datetime(dates)
    block = ((dates - dates.min()).dt.days // 7).to_numpy()
    _, block = np.unique(block, return_inverse=True)
    n_blocks = int(block.max()) + 1
    y = np.asarray(y)
    orderings = []
    for p in (candidate, baseline):
        order = np.argsort(-np.asarray(p), kind="stable")
        starts = np.r_[0, np.flatnonzero(np.diff(np.asarray(p)[order])) + 1]
        orderings.append((order, starts))
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(iterations):
        counts = rng.multinomial(n_blocks, np.full(n_blocks, 1 / n_blocks))
        w = counts[block]
        if not (np.dot(w, y) and np.dot(w, 1 - y)):
            continue
        scores = []
        for order, starts in orderings:
            positives = np.add.reduceat((w * y)[order], starts)
            negatives = np.add.reduceat((w * (1 - y))[order], starts)
            tp, fp = np.cumsum(positives), np.cumsum(negatives)
            ap = np.sum(positives / tp[-1] * np.divide(tp, tp + fp, out=np.zeros_like(tp, dtype=float), where=(tp + fp) > 0))
            auc = np.trapezoid(np.r_[0, tp / tp[-1]], np.r_[0, fp / fp[-1]])
            scores.append((ap, auc))
        brier_delta = np.average((y - candidate) ** 2 - (y - baseline) ** 2, weights=w)
        differences.append([scores[0][0] - scores[1][0], scores[0][1] - scores[1][1], brier_delta])
    if not differences:
        return {"status": "INSUFFICIENT_BLOCKS"}
    return {"status": "COMPLETE", "iterations": len(differences), "block_days": 7,
            "interpretation": "historical paired uncertainty, not an untouched-test claim",
            "delta_ci_95": {name: [float(v) for v in np.quantile(np.asarray(differences)[:, i], [0.025, 0.975])]
                            for i, name in enumerate(["ap", "roc_auc", "brier_score"])}}
