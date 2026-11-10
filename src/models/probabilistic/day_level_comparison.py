"""Day-Level Block-Bootstrap Paired Comparison Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 8, 9, 10
Stage 6 Day-Level Comparison:
1. Daily Score Aggregation:
   Groups flight-level evaluation scores by operational date to form day-level averages.
   S_d^(cand) = mean_{i in d} Score_i^(cand)
   S_d^(base) = mean_{i in d} Score_i^(base)
   Delta_d = S_d^(cand) - S_d^(base)
2. Day-Block Paired Bootstrap:
   Resamples operational days with replacement (B=2000 replications) under predetermined seed.
   Constructs 95% percentile bootstrap confidence intervals [CI_lower, CI_upper].
3. Gate & Decision Criteria:
   - Statistical superiority: CI_upper < 0 (candidate strictly beats baseline).
   - Practical significance: CI_upper < -delta_effect_size (improvement exceeds effect size).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import (
    FORECAST_EFFECT_SIZE_DELTA,
    PREDETERMINED_DEPLOYMENT_SEED,
    ProbabilisticContractViolation,
)


@dataclass(frozen=True)
class MetricComparisonResult:
    """Summary of paired comparison for a single evaluation metric."""

    metric_name: str
    higher_is_better: bool
    n_flights: int
    n_days: int
    candidate_mean: float
    baseline_mean: float
    mean_difference: float  # candidate - baseline
    ci_lower: float
    ci_upper: float
    bootstrap_se: float
    p_candidate_better: float
    is_statistically_superior: bool
    is_practically_significant: bool
    effect_size_delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "higher_is_better": self.higher_is_better,
            "n_flights": self.n_flights,
            "n_days": self.n_days,
            "candidate_mean": float(self.candidate_mean),
            "baseline_mean": float(self.baseline_mean),
            "mean_difference": float(self.mean_difference),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "bootstrap_se": float(self.bootstrap_se),
            "p_candidate_better": float(self.p_candidate_better),
            "is_statistically_superior": bool(self.is_statistically_superior),
            "is_practically_significant": bool(self.is_practically_significant),
            "effect_size_delta": float(self.effect_size_delta),
        }


@dataclass(frozen=True)
class MultiMetricDayComparisonResult:
    """Summary across multiple evaluation metrics with daily score table."""

    candidate_name: str
    baseline_name: str
    n_flights: int
    n_days: int
    metrics: dict[str, MetricComparisonResult]
    daily_table: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "baseline_name": self.baseline_name,
            "n_flights": self.n_flights,
            "n_days": self.n_days,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
        }


def compute_day_level_bootstrap_ci(
    daily_differences: np.ndarray,
    *,
    n_bootstraps: int = 2000,
    confidence_level: float = 0.95,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
) -> tuple[float, float, float, np.ndarray]:
    """Compute percentile bootstrap CI for mean daily paired difference.

    Args:
        daily_differences: Array of Delta_d = S_d^(cand) - S_d^(base), shape (D,)
        n_bootstraps: Number of bootstrap resamples (default 2000).
        confidence_level: Nominal confidence level (default 0.95).
        seed: Fixed random seed for reproducibility.

    Returns:
        (ci_lower, ci_upper, bootstrap_se, boot_means)
    """
    diffs = np.asarray(daily_differences, dtype=np.float64).ravel()
    d_count = len(diffs)
    if d_count == 0:
        raise ProbabilisticContractViolation("daily_differences cannot be empty")

    rng = np.random.default_rng(seed)
    # Vectorized resampling of shape (B, D)
    sample_indices = rng.integers(0, d_count, size=(n_bootstraps, d_count))
    boot_means = np.mean(diffs[sample_indices], axis=1)

    alpha = 1.0 - confidence_level
    ci_lower = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    boot_se = float(np.std(boot_means, ddof=1))

    return ci_lower, ci_upper, boot_se, boot_means


def compare_candidate_vs_baseline_daily(
    flight_dates: Sequence[str] | pd.Series | np.ndarray,
    candidate_scores: Mapping[str, np.ndarray] | np.ndarray,
    baseline_scores: Mapping[str, np.ndarray] | np.ndarray,
    *,
    candidate_name: str = "candidate",
    baseline_name: str = "baseline",
    n_bootstraps: int = 2000,
    confidence_level: float = 0.95,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
    effect_size_deltas: Mapping[str, float] | None = None,
    higher_is_better_map: Mapping[str, bool] | None = None,
) -> MultiMetricDayComparisonResult:
    """Execute rigorous paired day-level bootstrap comparison across metrics.

    Args:
        flight_dates: Date identifiers for each flight, shape (N,)
        candidate_scores: Per-flight scores {metric_name: array} or single array
        baseline_scores: Per-flight scores {metric_name: array} or single array
        candidate_name: Identifier for candidate model
        baseline_name: Identifier for baseline model
        n_bootstraps: Number of bootstrap draws
        confidence_level: Nominal CI level
        seed: Predetermined deployment seed
        effect_size_deltas: Minimum practical effect size per metric
        higher_is_better_map: Direction of superiority per metric
    """
    dt_series = pd.to_datetime(pd.Series(flight_dates))
    date_strings = dt_series.dt.strftime("%Y-%m-%d")
    n_flights = len(date_strings)

    # Standardize dictionary format
    if isinstance(candidate_scores, np.ndarray):
        cand_dict = {"crps": candidate_scores}
    else:
        cand_dict = {str(k): np.asarray(v) for k, v in candidate_scores.items()}

    if isinstance(baseline_scores, np.ndarray):
        base_dict = {"crps": baseline_scores}
    else:
        base_dict = {str(k): np.asarray(v) for k, v in baseline_scores.items()}

    common_metrics = sorted(set(cand_dict.keys()).intersection(base_dict.keys()))
    if not common_metrics:
        raise ProbabilisticContractViolation("No common metrics between candidate and baseline")

    deltas_map = effect_size_deltas or {"crps": FORECAST_EFFECT_SIZE_DELTA}
    hib_map = higher_is_better_map or {}

    # Build per-flight dataframe
    df_data: dict[str, Any] = {"flight_date": date_strings.values}
    for m in common_metrics:
        if len(cand_dict[m]) != n_flights or len(base_dict[m]) != n_flights:
            raise ProbabilisticContractViolation(
                f"Metric '{m}' array length mismatch: cand={len(cand_dict[m])}, base={len(base_dict[m])}, n_flights={n_flights}"
            )
        df_data[f"cand_{m}"] = cand_dict[m]
        df_data[f"base_{m}"] = base_dict[m]

    flight_df = pd.DataFrame(df_data)

    # Aggregate by date
    agg_spec: dict[str, tuple[str, str]] = {"flight_count": ("flight_date", "count")}
    for m in common_metrics:
        agg_spec[f"cand_{m}"] = (f"cand_{m}", "mean")
        agg_spec[f"base_{m}"] = (f"base_{m}", "mean")

    daily_df = flight_df.groupby("flight_date").agg(**agg_spec).reset_index()
    n_days = len(daily_df)

    metric_results: dict[str, MetricComparisonResult] = {}

    for m in common_metrics:
        cand_daily = daily_df[f"cand_{m}"].to_numpy()
        base_daily = daily_df[f"base_{m}"].to_numpy()
        daily_diff = cand_daily - base_daily
        daily_df[f"diff_{m}"] = daily_diff

        higher_is_better = hib_map.get(m, False)
        effect_delta = float(deltas_map.get(m, 0.0))

        ci_low, ci_high, se, boot_means = compute_day_level_bootstrap_ci(
            daily_diff,
            n_bootstraps=n_bootstraps,
            confidence_level=confidence_level,
            seed=seed,
        )

        cand_mean = float(np.mean(cand_daily))
        base_mean = float(np.mean(base_daily))
        mean_diff = float(np.mean(daily_diff))

        if higher_is_better:
            p_better = float(np.mean(boot_means > 0.0))
            is_stat_sup = bool(ci_low > 0.0)
            is_prac_sig = bool(ci_low > effect_delta)
        else:
            p_better = float(np.mean(boot_means < 0.0))
            is_stat_sup = bool(ci_high < 0.0)
            is_prac_sig = bool(ci_high < -effect_delta)

        metric_results[m] = MetricComparisonResult(
            metric_name=m,
            higher_is_better=higher_is_better,
            n_flights=n_flights,
            n_days=n_days,
            candidate_mean=cand_mean,
            baseline_mean=base_mean,
            mean_difference=mean_diff,
            ci_lower=ci_low,
            ci_upper=ci_high,
            bootstrap_se=se,
            p_candidate_better=p_better,
            is_statistically_superior=is_stat_sup,
            is_practically_significant=is_prac_sig,
            effect_size_delta=effect_delta,
        )

    return MultiMetricDayComparisonResult(
        candidate_name=candidate_name,
        baseline_name=baseline_name,
        n_flights=n_flights,
        n_days=n_days,
        metrics=metric_results,
        daily_table=daily_df,
    )
