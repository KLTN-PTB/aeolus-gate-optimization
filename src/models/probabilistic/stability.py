"""Stage 5 — Neural Training Stability and Day-Block Bootstrap Framework.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 8 & Section 10

Provides:
1. Seed ensemble predictive distribution construction (exact mixture combination).
2. Algorithmic stability evaluation across pre-registered finalist seeds [s1, s2, s3].
3. Day-block bootstrap confidence intervals for paired model-vs-baseline score differences.
4. Predictive point and quantile consistency metrics across seeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BootstrapResult:
    """Statistical uncertainty summary from day/block bootstrap."""

    point_estimate_delta_crps: float
    point_estimate_improvement: float
    bootstrap_se: float
    ci_lower_delta_crps: float
    ci_upper_delta_crps: float
    ci_lower_improvement: float
    ci_upper_improvement: float
    delta_threshold: float
    lower_bound_exceeds_threshold: bool
    n_days: int
    n_flights: int
    n_bootstraps: int


def construct_seed_ensemble_mixture(
    pi_list: Sequence[np.ndarray],
    mu_list: Sequence[np.ndarray],
    sigma_list: Sequence[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Combine predictive distributions from S seeds into an exact unified mixture.

    For S seeds each with K components, the combined mixture has S * K components
    with weights pi_ens = [pi_1/S, pi_2/S, ..., pi_S/S].

    Args:
        pi_list: List of length S, each array of shape (N, K)
        mu_list: List of length S, each array of shape (N, K)
        sigma_list: List of length S, each array of shape (N, K)

    Returns:
        pi_ens: shape (N, S * K)
        mu_ens: shape (N, S * K)
        sigma_ens: shape (N, S * K)
    """
    s_seeds = len(pi_list)
    if s_seeds == 0:
        raise ValueError("pi_list cannot be empty")

    n_samples = pi_list[0].shape[0]
    for p, m, s in zip(pi_list, mu_list, sigma_list):
        if p.shape[0] != n_samples or m.shape[0] != n_samples or s.shape[0] != n_samples:
            raise ValueError("All seed arrays must have identical sample length N")

    # Scaled weights: sum over all S*K components equals 1.0
    scaled_pi = [p / float(s_seeds) for p in pi_list]
    pi_ens = np.concatenate(scaled_pi, axis=-1)
    mu_ens = np.concatenate(mu_list, axis=-1)
    sigma_ens = np.concatenate(sigma_list, axis=-1)

    return pi_ens, mu_ens, sigma_ens


def compute_day_block_bootstrap_ci(
    daily_df: pd.DataFrame,
    *,
    delta_col: str = "delta_crps",
    count_col: str = "n_flights",
    n_bootstraps: int = 2000,
    seed: int = 202601,
    alpha: float = 0.05,
    delta_threshold: float = 0.05,
) -> BootstrapResult:
    """Compute cluster/day-block bootstrap confidence intervals for paired differences.

    Args:
        daily_df: DataFrame with one row per operational flight date, containing:
                  delta_col (mean score difference candidate - baseline on that day),
                  count_col (flight count on that day).
        delta_col: Name of delta score column (e.g. delta_crps = candidate - baseline).
        count_col: Name of flight count column.
        n_bootstraps: Number of bootstrap iterations (default 2000).
        seed: Random seed for bootstrap resampling.
        alpha: Two-sided significance level (default 0.05 for 95% CI).
        delta_threshold: Pre-registered practical improvement threshold (default 0.05 min).

    Returns:
        BootstrapResult with CI and significance metrics.
    """
    if daily_df.empty:
        raise ValueError("daily_df cannot be empty")

    delta_vals = daily_df[delta_col].to_numpy(dtype=np.float64)
    counts = daily_df[count_col].to_numpy(dtype=np.float64)

    total_flights = np.sum(counts)
    if total_flights <= 0:
        raise ValueError("Total flight count must be strictly positive")

    # Weighted point estimate across all days: sum(n_d * delta_d) / sum(n_d)
    point_delta = float(np.sum(counts * delta_vals) / total_flights)
    point_improv = -point_delta

    n_days = len(daily_df)
    rng = np.random.default_rng(seed)

    # Resample day indices with replacement: shape (n_bootstraps, n_days)
    boot_indices = rng.integers(0, n_days, size=(n_bootstraps, n_days))

    # Vectorized bootstrap calculation
    boot_deltas = delta_vals[boot_indices]  # (B, M)
    boot_counts = counts[boot_indices]      # (B, M)

    boot_weighted_sum = np.sum(boot_deltas * boot_counts, axis=1)
    boot_total_counts = np.sum(boot_counts, axis=1)
    boot_point_estimates = boot_weighted_sum / boot_total_counts  # (B,)

    boot_improvements = -boot_point_estimates

    boot_se = float(np.std(boot_point_estimates, ddof=1))

    # Percentile confidence interval
    q_low = alpha / 2.0
    q_high = 1.0 - alpha / 2.0

    ci_low_delta = float(np.percentile(boot_point_estimates, q_low * 100))
    ci_high_delta = float(np.percentile(boot_point_estimates, q_high * 100))

    ci_low_improv = float(np.percentile(boot_improvements, q_low * 100))
    ci_high_improv = float(np.percentile(boot_improvements, q_high * 100))

    # Check whether lower bound of improvement CI exceeds pre-registered delta
    exceeds_threshold = bool(ci_low_improv > delta_threshold)

    return BootstrapResult(
        point_estimate_delta_crps=point_delta,
        point_estimate_improvement=point_improv,
        bootstrap_se=boot_se,
        ci_lower_delta_crps=ci_low_delta,
        ci_upper_delta_crps=ci_high_delta,
        ci_lower_improvement=ci_low_improv,
        ci_upper_improvement=ci_high_improv,
        delta_threshold=delta_threshold,
        lower_bound_exceeds_threshold=exceeds_threshold,
        n_days=n_days,
        n_flights=int(total_flights),
        n_bootstraps=n_bootstraps,
    )


def compute_algorithmic_stability(
    metrics_by_seed: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Compute mean and standard deviation across seeds for numeric metrics."""
    seed_keys = list(metrics_by_seed.keys())
    if not seed_keys:
        return {}

    first_metrics = metrics_by_seed[seed_keys[0]]
    stability_summary: dict[str, dict[str, float]] = {}

    for metric_name, val in first_metrics.items():
        if isinstance(val, (int, float, np.floating, np.integer)):
            vals = [float(metrics_by_seed[s][metric_name]) for s in seed_keys]
            stability_summary[metric_name] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }
        elif isinstance(val, dict):
            # Nested sub-dictionary (e.g. pinball_loss or interval_metrics)
            nested_summary: dict[str, dict[str, float]] = {}
            for sub_name, sub_val in val.items():
                if isinstance(sub_val, (int, float, np.floating, np.integer)):
                    sub_vals = [float(metrics_by_seed[s][metric_name][sub_name]) for s in seed_keys]
                    nested_summary[sub_name] = {
                        "mean": float(np.mean(sub_vals)),
                        "std": float(np.std(sub_vals, ddof=1)) if len(sub_vals) > 1 else 0.0,
                        "min": float(np.min(sub_vals)),
                        "max": float(np.max(sub_vals)),
                    }
            if nested_summary:
                stability_summary[metric_name] = nested_summary  # type: ignore

    return stability_summary


def compute_prediction_consistency(
    predictions_by_seed: dict[int, np.ndarray],
    quantiles_by_seed: dict[int, dict[str, np.ndarray]],
) -> dict[str, Any]:
    """Compute correlation and absolute difference between model predictions across seeds."""
    seeds = sorted(predictions_by_seed.keys())
    pairs = [(seeds[i], seeds[j]) for i in range(len(seeds)) for j in range(i + 1, len(seeds))]

    point_corrs: list[float] = []
    point_maes: list[float] = []
    quantile_maes: dict[str, list[float]] = {q_name: [] for q_name in next(iter(quantiles_by_seed.values())).keys()}

    for s1, s2 in pairs:
        p1 = predictions_by_seed[s1]
        p2 = predictions_by_seed[s2]

        corr = float(np.corrcoef(p1, p2)[0, 1])
        mae = float(np.mean(np.abs(p1 - p2)))
        point_corrs.append(corr)
        point_maes.append(mae)

        for q_name in quantile_maes.keys():
            q1 = quantiles_by_seed[s1][q_name]
            q2 = quantiles_by_seed[s2][q_name]
            quantile_maes[q_name].append(float(np.mean(np.abs(q1 - q2))))

    return {
        "mean_point_correlation": float(np.mean(point_corrs)) if point_corrs else 1.0,
        "mean_point_mae": float(np.mean(point_maes)) if point_maes else 0.0,
        "quantile_mean_mae": {
            q_name: float(np.mean(maes)) for q_name, maes in quantile_maes.items()
        },
    }
