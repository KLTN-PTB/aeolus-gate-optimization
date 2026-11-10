"""Probabilistic evaluation metrics for Core Arrival baselines and candidates.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 8, 9, 10
Metrics:
1. Proper scoring: CRPS (Gaussian, Student-T, empirical), NLL / LogScore.
2. Calibration & coverage: empirical coverage at nominal levels (50%, 80%, 90%, 95%).
3. Sharpness & interval width.
4. Pinball loss for quantiles.
5. Quantile crossing rate.
6. Event probabilities: Brier score on Y >= 15, Y >= 60, Y >= 120.
7. Daily aggregation for paired day/block bootstrap.
"""

from __future__ import annotations

from typing import Final, Mapping, Sequence
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import t as student_t

EVENT_THRESHOLDS: Final = (15.0, 60.0, 120.0)
PRE_REGISTERED_QUANTILES: Final = (
    0.025,
    0.05,
    0.10,
    0.25,
    0.50,
    0.75,
    0.90,
    0.95,
    0.975,
)
SYMMETRIC_INTERVAL_PAIRS: Final = {
    0.50: (0.25, 0.75),
    0.80: (0.10, 0.90),
    0.90: (0.05, 0.95),
    0.95: (0.025, 0.975),
}


def compute_gaussian_crps(
    y_true: np.ndarray, mu: np.ndarray, sigma: np.ndarray
) -> np.ndarray:
    """Compute analytical Gaussian CRPS (Gneiting & Raftery, 2007).

    CRPS(y, mu, sigma) = sigma * [ z * (2*Phi(z) - 1) + 2*phi(z) - 1/sqrt(pi) ]
    where z = (y - mu) / sigma.
    """
    y = np.asarray(y_true, dtype=np.float64)
    m = np.asarray(mu, dtype=np.float64)
    s = np.asarray(sigma, dtype=np.float64)

    s = np.maximum(s, 1e-6)
    z = (y - m) / s
    phi_z = np.exp(-0.5 * z**2) / np.sqrt(2.0 * np.pi)
    Phi_z = ndtr(z)
    crps = s * (z * (2.0 * Phi_z - 1.0) + 2.0 * phi_z - 1.0 / np.sqrt(np.pi))
    return np.maximum(crps, 0.0)


def compute_pinball_loss(
    y_true: np.ndarray, q_pred: np.ndarray, alpha: float
) -> np.ndarray:
    """Compute pinball / quantile loss for quantile level alpha in (0, 1)."""
    y = np.asarray(y_true, dtype=np.float64)
    q = np.asarray(q_pred, dtype=np.float64)
    diff = y - q
    return np.maximum(alpha * diff, (alpha - 1.0) * diff)


def compute_brier_score(y_true: np.ndarray, p_pred: np.ndarray, threshold: float) -> float:
    """Compute Brier score for event Y >= threshold."""
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(p_pred, dtype=np.float64)
    actual_indicator = (y >= threshold).astype(np.float64)
    return float(np.mean((p - actual_indicator) ** 2))


def compute_quantile_coverage(y_true: np.ndarray, q_pred: np.ndarray) -> float:
    """Compute empirical coverage fraction: mean(y <= q_pred)."""
    y = np.asarray(y_true, dtype=np.float64)
    q = np.asarray(q_pred, dtype=np.float64)
    return float(np.mean(y <= q))


def compute_interval_metrics(
    y_true: np.ndarray, q_lower: np.ndarray, q_upper: np.ndarray
) -> tuple[float, float]:
    """Compute empirical coverage and mean width for interval [q_lower, q_upper]."""
    y = np.asarray(y_true, dtype=np.float64)
    ql = np.asarray(q_lower, dtype=np.float64)
    qu = np.asarray(q_upper, dtype=np.float64)
    coverage = float(np.mean((y >= ql) & (y <= qu)))
    mean_width = float(np.mean(qu - ql))
    return coverage, mean_width


def compute_quantile_crossing_rate(
    quantile_preds: Mapping[float, np.ndarray]
) -> tuple[float, int]:
    """Compute crossing rate across sorted quantiles.

    Returns:
        (crossing_rate, total_crossing_violations)
        crossing_rate: fraction of samples with at least one inversion q_alpha1 > q_alpha2 (alpha1 < alpha2).
    """
    sorted_alphas = sorted(quantile_preds.keys())
    if len(sorted_alphas) <= 1:
        return 0.0, 0

    n_samples = len(quantile_preds[sorted_alphas[0]])
    has_crossing = np.zeros(n_samples, dtype=bool)
    total_inversions = 0

    for i in range(len(sorted_alphas) - 1):
        a_low = sorted_alphas[i]
        q_low = quantile_preds[a_low]
        for j in range(i + 1, len(sorted_alphas)):
            a_high = sorted_alphas[j]
            q_high = quantile_preds[a_high]
            inversions = q_low > q_high
            total_inversions += int(np.sum(inversions))
            has_crossing |= inversions

    crossing_rate = float(np.mean(has_crossing))
    return crossing_rate, total_inversions


def compute_gaussian_event_probability(
    mu: np.ndarray, sigma: np.ndarray, threshold: float
) -> np.ndarray:
    """Compute P(Y >= threshold) for Gaussian distribution: 1 - Phi((threshold - mu)/sigma)."""
    s = np.maximum(sigma, 1e-6)
    z = (threshold - mu) / s
    return 1.0 - ndtr(z)


def compute_gaussian_nll(y_true: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Compute negative log-likelihood for Gaussian distribution."""
    y = np.asarray(y_true, dtype=np.float64)
    s = np.maximum(sigma, 1e-6)
    return np.log(s) + 0.5 * np.log(2.0 * np.pi) + 0.5 * ((y - mu) / s) ** 2


def build_daily_aggregation_table(
    flight_dates: pd.Series | np.ndarray,
    per_flight_crps: np.ndarray | None,
    per_flight_nll: np.ndarray | None,
    per_flight_brier_15: np.ndarray,
    per_flight_brier_60: np.ndarray,
) -> pd.DataFrame:
    """Aggregate per-flight metrics by date for block bootstrap comparison."""
    dt_parsed = pd.to_datetime(flight_dates)
    dates = dt_parsed.strftime("%Y-%m-%d") if hasattr(dt_parsed, "strftime") else dt_parsed.dt.strftime("%Y-%m-%d")
    df = pd.DataFrame(
        {
            "flight_date": dates,
            "brier_15": per_flight_brier_15,
            "brier_60": per_flight_brier_60,
        }
    )
    if per_flight_crps is not None:
        df["crps"] = per_flight_crps
    if per_flight_nll is not None:
        df["nll"] = per_flight_nll

    agg_dict: dict[str, str | tuple[str, str]] = {
        "flight_count": ("flight_date", "count"),
        "mean_brier_15": ("brier_15", "mean"),
        "mean_brier_60": ("brier_60", "mean"),
    }
    if per_flight_crps is not None:
        agg_dict["mean_crps"] = ("crps", "mean")
    if per_flight_nll is not None:
        agg_dict["mean_nll"] = ("nll", "mean")

    daily = df.groupby("flight_date").agg(**agg_dict).reset_index()
    return daily
