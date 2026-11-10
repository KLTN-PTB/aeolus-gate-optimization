"""Calibration and PIT Diagnostics for Probabilistic Forecasts in Aeolus.

Protocol: Phase 4 Common Distribution Contract
Scope:
- Brier score for event classification Y >= threshold
- Reliability diagram, Expected Calibration Error (ECE), and Maximum Calibration Error (MCE)
- Probability Integral Transform (PIT) Kolmogorov-Smirnov diagnostic
- Capability-aware evaluation: reports NOT_AVAILABLE if distribution lacks CDF
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kstest

from src.contracts.distribution import CapabilityNotSupportedError, PredictiveDistribution


def compute_brier_score(
    y_true: np.ndarray | pd.Series,
    p_pred: np.ndarray,
    threshold: float = 15.0,
) -> float:
    """Compute Brier Score: Mean squared error of predicted event probabilities.

    BS = (1/N) * sum_i (p_i - 1[y_i >= threshold])^2
    """
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(p_pred, dtype=np.float64)
    if len(y) != len(p):
        raise ValueError(f"Length mismatch: len(y)={len(y)} vs len(p)={len(p)}")
    if np.any(p < 0.0) or np.any(p > 1.0):
        raise ValueError("Probabilities must lie in [0, 1]")

    y_binary = (y >= threshold).astype(np.float64)
    return float(np.mean((p - y_binary) ** 2))


def compute_calibration_table(
    y_true: np.ndarray | pd.Series,
    p_pred: np.ndarray,
    n_bins: int = 10,
    threshold: float = 15.0,
) -> dict[str, Any]:
    """Compute reliability table, ECE, and MCE for predicted event probabilities."""
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(p_pred, dtype=np.float64)
    n = len(y)
    if n == 0:
        return {
            "expected_calibration_error": 0.0,
            "maximum_calibration_error": 0.0,
            "reliability_table": [],
        }

    y_binary = (y >= threshold).astype(np.float64)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(p, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    reliability_table: list[dict[str, Any]] = []
    ece = 0.0
    mce = 0.0

    for b in range(n_bins):
        mask = bin_indices == b
        count_b = int(np.sum(mask))
        if count_b > 0:
            mean_pred = float(np.mean(p[mask]))
            obs_freq = float(np.mean(y_binary[mask]))
            gap = abs(mean_pred - obs_freq)
            ece += gap * (count_b / n)
            mce = max(mce, gap)
            reliability_table.append({
                "bin": b,
                "bin_range": f"[{bin_edges[b]:.2f}, {bin_edges[b+1]:.2f}]",
                "count": count_b,
                "mean_pred": round(mean_pred, 4),
                "observed_freq": round(obs_freq, 4),
                "abs_gap": round(gap, 4),
            })

    return {
        "expected_calibration_error": round(ece, 4),
        "maximum_calibration_error": round(mce, 4),
        "reliability_table": reliability_table,
    }


def compute_pit_diagnostics(
    dist: PredictiveDistribution,
    y_true: np.ndarray | pd.Series,
) -> dict[str, Any]:
    """Compute Probability Integral Transform (PIT) diagnostics u_i = F_i(y_i).

    Tests u against Uniform(0, 1) via Kolmogorov-Smirnov test.
    If dist does not support continuous CDF, returns 'NOT_AVAILABLE' without error.
    """
    meta = dist.metadata() if callable(dist.metadata) else dist.metadata
    caps = meta.get("capabilities", {})
    if not caps.get("has_cdf", False):
        return {
            "status": "NOT_AVAILABLE",
            "reason": "Candidate does not support continuous CDF",
        }
    if caps.get("has_pit") is False or meta.get("has_pit") is False:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "Candidate does not support continuous PIT (e.g. step CDF or quantile-only)",
        }
    if meta.get("role") == "QUANTILE_FORECAST_ONLY":
        return {
            "status": "NOT_AVAILABLE",
            "reason": "Quantile forecast model does not support continuous CDF or continuous PIT",
        }

    y = np.asarray(y_true, dtype=np.float64)
    n = len(y)
    try:
        u_vals = dist.cdf(y)
        u_clipped = np.clip(u_vals, 1e-6, 1.0 - 1e-6)
        ks_res = kstest(u_clipped, "uniform")
        hist_counts, _ = np.histogram(u_clipped, bins=10)
        unif_dev = float(np.std(hist_counts / n - 0.10))
        return {
            "status": "AVAILABLE",
            "ks_statistic": round(float(ks_res.statistic), 4),
            "ks_pvalue": round(float(ks_res.pvalue), 6),
            "uniformity_dev": round(unif_dev, 4),
        }
    except CapabilityNotSupportedError:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "Candidate does not support continuous CDF",
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}
