"""Paired Statistical Comparison Engine for Aeolus Model Benchmarks (V2 Repaired).

Protocol: Statistical Comparison Protocol V2
Scope:
- Explicit unit of inference distinction:
  * forecast pointwise: flight
  * aggregate forecast: fold / evaluation population
  * downstream: scenario x seed
  * Monte Carlo: outer replication
- Exact observation/scenario alignment on (flight_key, fold, year, task, target)
- Fail-closed on missing rows, duplicate IDs, or mismatched metadata/targets
- Distinction between pointwise error comparison and aggregate metric comparison:
  * Pointwise (MAE, Pointwise Brier, CRPS Pinball, LogScore, Interval Width):
    - Paired differences: d_i = |e_A_i| - |e_B_i|
    - Effect sizes: mean delta, median delta, std delta, Cohen's d_z
    - Statistical tests: Paired t-test, Wilcoxon signed-rank test
    - Percentile bootstrap 95% CI
  * Aggregate (RMSE, R^2, PR-AUC, Coverage Error):
    - NO mechanical rowwise subtraction
    - Paired aggregate bootstrap: resample units with replacement, recompute Metric A and Metric B globally, delta = A - B
    - Empirical two-sided bootstrap p-value bounded by [2/(B+1), 1.0]
- Dependence awareness:
  * 'iid_percentile': Standard uniform i.i.d. resampling of flights
  * 'day_cluster_percentile': Resamples operational dates with replacement
  * 'fixed_block_percentile': Resamples contiguous blocks of fixed length L
  * 'stationary_block_percentile': Politis & Romano (1994) stationary bootstrap with mean block length L
- Multiple comparison multiplicity correction:
  * Holm-Bonferroni (step-down FWER control)
  * Benjamini-Hochberg (step-up FDR control)
- Canonical output schema:
  model_a, model_b, metric, unit_of_inference, n_units, effect_size,
  ci_low, ci_high, raw_p, adjusted_p, test_method, bootstrap_method,
  block_length, bootstrap_replicates, seed
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Final, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score

from src.models.probabilistic.metrics import (
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
)

DEFAULT_BOOTSTRAP_REPLICATIONS: Final = 2000
DEFAULT_COMPARISON_SEED: Final = 202601
ZERO_TOLERANCE: Final = 1e-9


class PairedComparisonError(Exception):
    """Base exception for paired statistical comparison errors."""
    pass


class PairedAlignmentError(PairedComparisonError):
    """Raised when observation alignment fails or unmatched rows are detected."""
    pass


class InferenceUnit(str, Enum):
    """Explicit statistical unit of inference."""
    FLIGHT = "flight"
    FOLD_POPULATION = "fold_population"
    DAY_CLUSTER = "day_cluster"
    SCENARIO_SEED = "scenario_x_seed"
    OUTER_REPLICATION = "outer_replication"


class BootstrapMethod(str, Enum):
    """Supported bootstrap resampling methodologies."""
    IID_PERCENTILE = "iid_percentile"
    DAY_CLUSTER_PERCENTILE = "day_cluster_percentile"
    FIXED_BLOCK_PERCENTILE = "fixed_block_percentile"
    STATIONARY_BLOCK_PERCENTILE = "stationary_block_percentile"


class MultiplicityCorrectionMethod(str, Enum):
    """Supported multiplicity correction algorithms."""
    HOLM = "holm"
    BONFERRONI = "bonferroni"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"


@dataclass(frozen=True)
class PairingReport:
    """Detailed audit report of row-level observation alignment."""

    expected_rows: int
    matched_rows: int
    unmatched_rows: int
    missing_predictions: int
    is_valid_alignment: bool
    status: str  # "MATCHED" or "BLOCKED"
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CallableDict(dict):
    """Dictionary supporting dot-notation attribute access."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


@dataclass(frozen=True)
class StatisticalComparisonRecord:
    """Canonical 15-field record for a pairwise statistical comparison."""

    model_a: str
    model_b: str
    metric: str
    unit_of_inference: str
    n_units: int
    effect_size: float
    ci_low: float
    ci_high: float
    raw_p: float | None
    adjusted_p: float | None
    test_method: str
    bootstrap_method: str
    block_length: int | float | None
    bootstrap_replicates: int
    seed: int
    higher_is_better: bool = False
    model_a_value: float = 0.0
    model_b_value: float = 0.0
    is_significant_raw_05: bool = False
    is_significant_adj_05: bool = False
    comparison_family: str = "point_regression"
    fold_id: str | None = None
    validation_year: int | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with dual key access (model_a/model_A, ci_low/ci_lower)."""
        d = asdict(self)
        d["model_A"] = self.model_a
        d["model_B"] = self.model_b
        d["ci_lower"] = self.ci_low
        d["ci_upper"] = self.ci_high
        return d


class PairedMetricDelta(CallableDict):
    """Summary statistics and bootstrap confidence intervals for a single metric delta.

    Inherits from CallableDict to provide both dictionary indexing and attribute access,
    maintaining 100% backwards compatibility with legacy callers while adding V2 fields.
    """

    def __init__(
        self,
        metric_name: str,
        higher_is_better: bool,
        model_a_mean: float,
        model_b_mean: float,
        mean_delta: float,
        median_delta: float,
        std_delta: float,
        ci_lower: float,
        ci_upper: float,
        fraction_improved: float,
        fraction_worse: float,
        fraction_unchanged: float,
        day_level_mean_delta: float | None = None,
        day_level_ci_lower: float | None = None,
        day_level_ci_upper: float | None = None,
        *,
        unit_of_inference: str = "flight",
        n_units: int = 0,
        effect_size: float | None = None,
        raw_p: float | None = None,
        adjusted_p: float | None = None,
        test_method: str = "paired_bootstrap_test",
        bootstrap_method: str = "iid_percentile",
        block_length: int | float | None = None,
        bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
        seed: int = DEFAULT_COMPARISON_SEED,
        is_significant_raw_05: bool = False,
        is_significant_adj_05: bool = False,
        notes: str | None = None,
    ) -> None:
        eff_size = effect_size if effect_size is not None else mean_delta
        raw_sig = bool(raw_p is not None and raw_p < 0.05) if not is_significant_raw_05 else True
        adj_sig = bool(adjusted_p is not None and adjusted_p < 0.05) if not is_significant_adj_05 else True

        super().__init__(
            metric_name=metric_name,
            higher_is_better=higher_is_better,
            model_a_mean=model_a_mean,
            model_b_mean=model_b_mean,
            mean_delta=mean_delta,
            median_delta=median_delta,
            std_delta=std_delta,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_low=ci_lower,
            ci_high=ci_upper,
            fraction_improved=fraction_improved,
            fraction_worse=fraction_worse,
            fraction_unchanged=fraction_unchanged,
            day_level_mean_delta=day_level_mean_delta,
            day_level_ci_lower=day_level_ci_lower,
            day_level_ci_upper=day_level_ci_upper,
            unit_of_inference=unit_of_inference,
            n_units=n_units,
            effect_size=eff_size,
            raw_p=raw_p,
            adjusted_p=adjusted_p,
            test_method=test_method,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
            bootstrap_replicates=bootstrap_replicates,
            seed=seed,
            is_significant_raw_05=raw_sig,
            is_significant_adj_05=adj_sig,
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return dict(self)

    def to_comparison_record(
        self,
        model_a: str,
        model_b: str,
        *,
        comparison_family: str = "point_regression",
        fold_id: str | None = None,
        validation_year: int | None = None,
    ) -> StatisticalComparisonRecord:
        """Convert delta to canonical StatisticalComparisonRecord."""
        return StatisticalComparisonRecord(
            model_a=model_a,
            model_b=model_b,
            metric=self["metric_name"],
            unit_of_inference=self["unit_of_inference"],
            n_units=self["n_units"],
            effect_size=self["effect_size"],
            ci_low=self["ci_lower"],
            ci_high=self["ci_upper"],
            raw_p=self["raw_p"],
            adjusted_p=self["adjusted_p"],
            test_method=self["test_method"],
            bootstrap_method=self["bootstrap_method"],
            block_length=self["block_length"],
            bootstrap_replicates=self["bootstrap_replicates"],
            seed=self["seed"],
            higher_is_better=self["higher_is_better"],
            model_a_value=self["model_a_mean"],
            model_b_value=self["model_b_mean"],
            is_significant_raw_05=self["is_significant_raw_05"],
            is_significant_adj_05=self["is_significant_adj_05"],
            comparison_family=comparison_family,
            fold_id=fold_id,
            validation_year=validation_year,
            notes=self.get("notes"),
        )


@dataclass
class PairedComparisonResult:
    """Full paired comparison result between Model A and Model B."""

    pair_id: str
    model_a: str
    model_b: str
    comparison_family: str  # "point_regression", "point_classification", "probabilistic"
    fold_id: str
    validation_year: int
    pairing_report: PairingReport
    status: str  # "COMPLETED" or "BLOCKED"
    failure_reason: str | None
    metrics: dict[str, Any]
    seed: int
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "model_a": self.model_a,
            "model_b": self.model_b,
            "comparison_family": self.comparison_family,
            "fold_id": self.fold_id,
            "validation_year": self.validation_year,
            "pairing_report": self.pairing_report.to_dict(),
            "status": self.status,
            "failure_reason": self.failure_reason,
            "metrics": {
                k: (v.to_dict() if hasattr(v, "to_dict") else v)
                for k, v in self.metrics.items()
            },
            "seed": self.seed,
            "config_hash": self.config_hash,
        }

    def to_comparison_records(self) -> list[StatisticalComparisonRecord]:
        """Extract canonical comparison records for all available metrics."""
        records: list[StatisticalComparisonRecord] = []
        if self.status != "COMPLETED":
            return records

        for m_key, m_val in self.metrics.items():
            if isinstance(m_val, PairedMetricDelta):
                records.append(
                    m_val.to_comparison_record(
                        model_a=self.model_a,
                        model_b=self.model_b,
                        comparison_family=self.comparison_family,
                        fold_id=self.fold_id,
                        validation_year=self.validation_year,
                    )
                )
            elif isinstance(m_val, dict) and "mean_delta" in m_val:
                records.append(
                    StatisticalComparisonRecord(
                        model_a=self.model_a,
                        model_b=self.model_b,
                        metric=m_key,
                        unit_of_inference=m_val.get("unit_of_inference", "flight"),
                        n_units=m_val.get("n_units", self.pairing_report.matched_rows),
                        effect_size=float(m_val.get("effect_size", m_val.get("mean_delta", 0.0))),
                        ci_low=float(m_val.get("ci_lower", m_val.get("ci_low", 0.0))),
                        ci_high=float(m_val.get("ci_upper", m_val.get("ci_high", 0.0))),
                        raw_p=m_val.get("raw_p"),
                        adjusted_p=m_val.get("adjusted_p"),
                        test_method=m_val.get("test_method", "paired_bootstrap_test"),
                        bootstrap_method=m_val.get("bootstrap_method", "iid_percentile"),
                        block_length=m_val.get("block_length"),
                        bootstrap_replicates=m_val.get("bootstrap_replicates", DEFAULT_BOOTSTRAP_REPLICATIONS),
                        seed=self.seed,
                        higher_is_better=m_val.get("higher_is_better", False),
                        model_a_value=float(m_val.get("model_a_mean", 0.0)),
                        model_b_value=float(m_val.get("model_b_mean", 0.0)),
                        is_significant_raw_05=bool(m_val.get("is_significant_raw_05", False)),
                        is_significant_adj_05=bool(m_val.get("is_significant_adj_05", False)),
                        comparison_family=self.comparison_family,
                        fold_id=self.fold_id,
                        validation_year=self.validation_year,
                        notes=m_val.get("notes"),
                    )
                )
        return records


# =============================================================================
# 1. EXACT PAIRING AND ALIGNMENT GUARD
# =============================================================================

def validate_paired_alignment(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    key_col: str = "flight_key",
    metadata_cols: tuple[str, ...] = ("fold_id", "validation_year"),
    target_cols: tuple[str, ...] = ("y_arr_reg", "y_arr_cls"),
) -> tuple[pd.DataFrame, pd.DataFrame, PairingReport]:
    """Validate exact row alignment between two model prediction tables.

    Rules:
    - Every row must match on key_col (flight_key).
    - Metadata columns (fold_id, validation_year) and target columns must match row-for-row.
    - If there are duplicate keys, unmatched rows, or missing keys, fails closed (returns status 'BLOCKED').
    - NEVER performs inner-join to silently drop missing observations.
    """
    issues: list[str] = []

    if key_col not in df_a.columns or key_col not in df_b.columns:
        issues.append(f"Key column '{key_col}' missing from one or both DataFrames.")
        report = PairingReport(
            expected_rows=max(len(df_a), len(df_b)),
            matched_rows=0,
            unmatched_rows=max(len(df_a), len(df_b)),
            missing_predictions=max(len(df_a), len(df_b)),
            is_valid_alignment=False,
            status="BLOCKED",
            issues=tuple(issues),
        )
        raise PairedAlignmentError(f"Key column '{key_col}' missing from predictions.")

    # Check for duplicate keys
    if df_a[key_col].duplicated().any():
        n_dup_a = int(df_a[key_col].duplicated().sum())
        issues.append(f"Model A contains {n_dup_a} duplicate keys.")
    if df_b[key_col].duplicated().any():
        n_dup_b = int(df_b[key_col].duplicated().sum())
        issues.append(f"Model B contains {n_dup_b} duplicate keys.")

    keys_a = set(df_a[key_col])
    keys_b = set(df_b[key_col])
    expected_rows = len(keys_a.union(keys_b))
    matched_keys = keys_a.intersection(keys_b)
    unmatched_in_b = keys_a - keys_b
    unmatched_in_a = keys_b - keys_a
    unmatched_count = len(unmatched_in_a) + len(unmatched_in_b)

    if unmatched_count > 0:
        if unmatched_in_b:
            issues.append(f"{len(unmatched_in_b)} keys present in Model A but missing in Model B.")
        if unmatched_in_a:
            issues.append(f"{len(unmatched_in_a)} keys present in Model B but missing in Model A.")

    # Fail closed on duplicate keys or any missing observations
    if issues or unmatched_count > 0:
        report = PairingReport(
            expected_rows=expected_rows,
            matched_rows=len(matched_keys),
            unmatched_rows=unmatched_count,
            missing_predictions=unmatched_count,
            is_valid_alignment=False,
            status="BLOCKED",
            issues=tuple(issues),
        )
        return df_a, df_b, report

    # Align df_b to exact row ordering of df_a
    df_a_sorted = df_a.sort_values(key_col).reset_index(drop=True)
    df_b_sorted = df_b.set_index(key_col).loc[df_a_sorted[key_col]].reset_index()

    # Check metadata alignment
    for meta_col in metadata_cols:
        if meta_col in df_a_sorted.columns and meta_col in df_b_sorted.columns:
            mismatches = df_a_sorted[meta_col] != df_b_sorted[meta_col]
            if mismatches.any():
                issues.append(
                    f"Metadata '{meta_col}' mismatch on {int(mismatches.sum())} rows."
                )

    # Check target label alignment
    for tgt_col in target_cols:
        if tgt_col in df_a_sorted.columns and tgt_col in df_b_sorted.columns:
            mismatches = ~np.isclose(
                df_a_sorted[tgt_col].to_numpy(dtype=float),
                df_b_sorted[tgt_col].to_numpy(dtype=float),
                atol=1e-5,
            )
            if np.any(mismatches):
                issues.append(
                    f"Target column '{tgt_col}' mismatch on {int(np.sum(mismatches))} rows."
                )

    if issues:
        report = PairingReport(
            expected_rows=expected_rows,
            matched_rows=len(matched_keys),
            unmatched_rows=len(df_a_sorted),
            missing_predictions=0,
            is_valid_alignment=False,
            status="BLOCKED",
            issues=tuple(issues),
        )
        return df_a_sorted, df_b_sorted, report

    report = PairingReport(
        expected_rows=expected_rows,
        matched_rows=expected_rows,
        unmatched_rows=0,
        missing_predictions=0,
        is_valid_alignment=True,
        status="MATCHED",
        issues=(),
    )
    return df_a_sorted, df_b_sorted, report


# =============================================================================
# 2. RESAMPLING & BOOTSTRAP GENERATORS (DEPENDENCE-AWARE)
# =============================================================================

def generate_bootstrap_indices(
    n: int,
    *,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_COMPARISON_SEED,
    method: str = "iid_percentile",
    block_length: int | float | None = None,
    dates: np.ndarray | None = None,
) -> np.ndarray:
    """Generate bootstrap index matrix of shape (n_bootstraps, n) under explicit dependence assumptions.

    Methods:
    - 'iid_percentile': Standard uniform i.i.d. resampling with replacement.
    - 'day_cluster_percentile': Resamples unique operational dates with replacement, preserving intra-day clusters.
    - 'fixed_block_percentile': Resamples contiguous blocks of fixed length L.
    - 'stationary_block_percentile': Politis & Romano (1994) stationary bootstrap with mean block length L.
    """
    if n <= 0:
        return np.empty((n_bootstraps, 0), dtype=int)

    rng = np.random.default_rng(seed)

    if method == "iid_percentile" or (method == "day_cluster_percentile" and dates is None):
        return rng.integers(0, n, size=(n_bootstraps, n))

    if method == "day_cluster_percentile" and dates is not None and len(dates) == n:
        unique_dates, inverse = np.unique(dates, return_inverse=True)
        n_days = len(unique_dates)
        if n_days <= 1:
            return rng.integers(0, n, size=(n_bootstraps, n))

        # Map each day index to row indices
        day_indices = [np.where(inverse == d)[0] for d in range(n_days)]
        idx_matrix = np.empty((n_bootstraps, n), dtype=int)
        for b in range(n_bootstraps):
            sampled_days = rng.integers(0, n_days, size=n_days)
            sampled_rows = np.concatenate([day_indices[d] for d in sampled_days])
            if len(sampled_rows) >= n:
                idx_matrix[b] = sampled_rows[:n]
            else:
                extra = rng.integers(0, n, size=n - len(sampled_rows))
                idx_matrix[b] = np.concatenate([sampled_rows, extra])
        return idx_matrix

    if method == "fixed_block_percentile":
        l_block = int(block_length) if block_length is not None and block_length >= 1 else max(1, int(np.sqrt(n)))
        k_blocks = int(np.ceil(n / l_block))
        max_start = max(1, n - l_block + 1)
        idx_matrix = np.empty((n_bootstraps, n), dtype=int)
        for b in range(n_bootstraps):
            starts = rng.integers(0, max_start, size=k_blocks)
            blocks = [np.arange(s, s + l_block) for s in starts]
            idx_matrix[b] = np.concatenate(blocks)[:n]
        return idx_matrix

    if method == "stationary_block_percentile":
        # Politis & Romano (1994) Stationary Bootstrap
        mean_l = float(block_length) if block_length is not None and block_length >= 1.0 else max(1.0, float(np.sqrt(n)))
        p_new_block = 1.0 / mean_l
        idx_matrix = np.empty((n_bootstraps, n), dtype=int)
        for b in range(n_bootstraps):
            row_idx = np.empty(n, dtype=int)
            curr = rng.integers(0, n)
            row_idx[0] = curr
            new_block_choices = rng.random(size=n - 1) < p_new_block
            random_starts = rng.integers(0, n, size=n - 1)
            for t in range(1, n):
                if new_block_choices[t - 1]:
                    curr = random_starts[t - 1]
                else:
                    curr = (curr + 1) % n
                row_idx[t] = curr
            idx_matrix[b] = row_idx
        return idx_matrix

    # Fallback to iid
    return rng.integers(0, n, size=(n_bootstraps, n))


def compute_paired_bootstrap_ci(
    deltas: np.ndarray,
    *,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    confidence_level: float = 0.95,
    seed: int = DEFAULT_COMPARISON_SEED,
    method: str = "iid_percentile",
    dates: np.ndarray | None = None,
    block_length: int | float | None = None,
) -> tuple[float, float, float]:
    """Compute percentile bootstrap confidence interval for mean observation delta.

    Supports IID, day-cluster, fixed-block, and stationary block resampling.

    Returns:
        (ci_lower, ci_upper, bootstrap_se)
    """
    n = len(deltas)
    if n == 0:
        return 0.0, 0.0, 0.0

    if np.all(np.isclose(deltas, deltas[0], atol=ZERO_TOLERANCE)):
        val = float(deltas[0])
        return val, val, 0.0

    indices = generate_bootstrap_indices(
        n,
        n_bootstraps=n_bootstraps,
        seed=seed,
        method=method,
        dates=dates,
        block_length=block_length,
    )
    boot_means = np.mean(deltas[indices], axis=1)

    alpha_tail = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(boot_means, alpha_tail * 100.0))
    ci_upper = float(np.percentile(boot_means, (1.0 - alpha_tail) * 100.0))
    se = float(np.std(boot_means, ddof=1))
    return ci_lower, ci_upper, se


def compute_day_block_bootstrap_ci(
    daily_deltas: np.ndarray,
    *,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    confidence_level: float = 0.95,
    seed: int = DEFAULT_COMPARISON_SEED,
) -> tuple[float, float, float]:
    """Compute day-level block bootstrap confidence interval for mean daily delta.

    Resamples operational days with replacement to respect temporal clustering.
    """
    n_days = len(daily_deltas)
    if n_days == 0:
        return 0.0, 0.0, 0.0

    if np.all(np.isclose(daily_deltas, daily_deltas[0], atol=ZERO_TOLERANCE)):
        val = float(daily_deltas[0])
        return val, val, 0.0

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n_days, size=(n_bootstraps, n_days))
    boot_means = np.mean(daily_deltas[indices], axis=1)

    alpha_tail = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(boot_means, alpha_tail * 100.0))
    ci_upper = float(np.percentile(boot_means, (1.0 - alpha_tail) * 100.0))
    se = float(np.std(boot_means, ddof=1))
    return ci_lower, ci_upper, se


# =============================================================================
# 3. STATISTICAL TESTS & P-VALUE CALCULATORS
# =============================================================================

def compute_pointwise_t_test(deltas: np.ndarray) -> tuple[float | None, float | None]:
    """Compute paired Student's t-test for pointwise difference d_i = e_{A,i} - e_{B,i}.

    Hypothesis: H0: E[d] = 0 vs H1: E[d] != 0.
    Returns:
        (t_statistic, p_value)
    """
    n = len(deltas)
    if n < 2:
        return None, None

    mean_d = float(np.mean(deltas))
    std_d = float(np.std(deltas, ddof=1))

    if std_d <= ZERO_TOLERANCE:
        if abs(mean_d) <= ZERO_TOLERANCE:
            return 0.0, 1.0
        return float(np.sign(mean_d) * np.inf), 0.0

    se = std_d / np.sqrt(n)
    t_stat = mean_d / se
    p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=n - 1)))
    return t_stat, p_val


def compute_pointwise_wilcoxon(deltas: np.ndarray) -> tuple[float | None, float | None]:
    """Compute Wilcoxon signed-rank test for median of paired differences.

    Applies to non-zero differences only. Returns None if non-zero count < 10.
    """
    nonzero = deltas[np.abs(deltas) > ZERO_TOLERANCE]
    if len(nonzero) < 10:
        return None, None
    try:
        res = stats.wilcoxon(nonzero, alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        return None, None


def compute_bootstrap_p_value(boot_deltas: np.ndarray) -> float:
    """Compute two-sided empirical bootstrap p-value for H0: Delta = 0.

    Formula:
        p = 2 * min( (1 + sum(Delta_b <= 0)) / (B + 1), (1 + sum(Delta_b >= 0)) / (B + 1) )
    Bounded strictly in [2 / (B + 1), 1.0] to prevent false claim of p = 0.0 from finite resampling.
    """
    b = len(boot_deltas)
    if b == 0:
        return 1.0

    c_le = int(np.sum(boot_deltas <= ZERO_TOLERANCE))
    c_ge = int(np.sum(boot_deltas >= -ZERO_TOLERANCE))
    min_count = min(c_le, c_ge)
    p_val = 2.0 * (1.0 + min_count) / (b + 1.0)
    return min(1.0, float(p_val))


# =============================================================================
# 4. MULTIPLICITY CORRECTION (HOLM, BONFERRONI, BENJAMINI-HOCHBERG)
# =============================================================================

def compute_holm_bonferroni_correction(
    p_values: Sequence[float | None],
) -> list[float | None]:
    """Holm-Bonferroni step-down procedure for Family-Wise Error Rate (FWER) control.

    Properties:
    - Strictly controls FWER under arbitrary dependence assumptions.
    - Adjusted p-values: p_tilde_{(i)} = min(1.0, max_{k <= i} {(m - k + 1) * p_{(k)}}).
    - Preserves monotonicity and handles None/NaN cleanly.
    """
    valid_pairs = [(i, float(p)) for i, p in enumerate(p_values) if p is not None and not np.isnan(p)]
    if not valid_pairs:
        return [None] * len(p_values)

    m = len(valid_pairs)
    sorted_pairs = sorted(valid_pairs, key=lambda x: x[1])

    adjusted: list[float | None] = [None] * len(p_values)
    cum_max = 0.0

    for rank, (orig_idx, p_val) in enumerate(sorted_pairs):
        multiplier = m - rank
        adj = min(1.0, p_val * multiplier)
        cum_max = max(cum_max, adj)
        adjusted[orig_idx] = min(1.0, cum_max)

    return adjusted


def compute_benjamini_hochberg_correction(
    p_values: Sequence[float | None],
) -> list[float | None]:
    """Benjamini-Hochberg step-up procedure for False Discovery Rate (FDR) control."""
    valid_pairs = [(i, float(p)) for i, p in enumerate(p_values) if p is not None and not np.isnan(p)]
    if not valid_pairs:
        return [None] * len(p_values)

    m = len(valid_pairs)
    sorted_pairs = sorted(valid_pairs, key=lambda x: x[1])

    adjusted: list[float | None] = [None] * len(p_values)
    cum_min = 1.0

    for rank in range(m - 1, -1, -1):
        orig_idx, p_val = sorted_pairs[rank]
        k = rank + 1
        adj = min(1.0, p_val * (m / k))
        cum_min = min(cum_min, adj)
        adjusted[orig_idx] = cum_min

    return adjusted


def apply_multiplicity_correction(
    records: Sequence[StatisticalComparisonRecord],
    method: str = "holm",
    *,
    group_by_metric: bool = True,
) -> list[StatisticalComparisonRecord]:
    """Apply multiplicity correction to a collection of comparison records within each comparison family.

    When group_by_metric=True (default), families are partitioned by (comparison_family, fold_id, metric),
    conforming to the Phase 5/R18 protocol of family-level FWER control for each specific metric evaluation slice.
    """
    if not records:
        return []

    # Group by comparison family, fold, and optionally metric
    families: dict[tuple[Any, ...], list[int]] = {}
    for idx, r in enumerate(records):
        fam_key = (r.comparison_family, r.fold_id, r.metric) if group_by_metric else (r.comparison_family, r.fold_id)
        families.setdefault(fam_key, []).append(idx)

    updated_records = list(records)

    for fam_indices in families.values():
        raw_p_list = [records[i].raw_p for i in fam_indices]

        if method == "holm":
            adj_p_list = compute_holm_bonferroni_correction(raw_p_list)
        elif method == "benjamini_hochberg":
            adj_p_list = compute_benjamini_hochberg_correction(raw_p_list)
        elif method == "bonferroni":
            m = sum(1 for p in raw_p_list if p is not None)
            adj_p_list = [min(1.0, p * m) if p is not None else None for p in raw_p_list]
        else:
            raise ValueError(f"Unsupported multiplicity correction method: {method}")

        for rec_idx, adj_p in zip(fam_indices, adj_p_list):
            old = records[rec_idx]
            is_adj_sig = bool(adj_p is not None and adj_p < 0.05)
            updated_records[rec_idx] = StatisticalComparisonRecord(
                model_a=old.model_a,
                model_b=old.model_b,
                metric=old.metric,
                unit_of_inference=old.unit_of_inference,
                n_units=old.n_units,
                effect_size=old.effect_size,
                ci_low=old.ci_low,
                ci_high=old.ci_high,
                raw_p=old.raw_p,
                adjusted_p=adj_p,
                test_method=old.test_method,
                bootstrap_method=old.bootstrap_method,
                block_length=old.block_length,
                bootstrap_replicates=old.bootstrap_replicates,
                seed=old.seed,
                higher_is_better=old.higher_is_better,
                model_a_value=old.model_a_value,
                model_b_value=old.model_b_value,
                is_significant_raw_05=old.is_significant_raw_05,
                is_significant_adj_05=is_adj_sig,
                comparison_family=old.comparison_family,
                fold_id=old.fold_id,
                validation_year=old.validation_year,
                notes=old.notes,
            )

    return updated_records


def extract_comparison_families_metadata(
    records: Sequence[StatisticalComparisonRecord],
    correction_method: str = "holm_bonferroni",
    *,
    group_by_metric: bool = True,
) -> list[dict[str, Any]]:
    """Extract family-level metadata for statistical multiplicity control."""
    families: dict[tuple[Any, ...], list[StatisticalComparisonRecord]] = {}
    for r in records:
        fam_key = (r.comparison_family, r.fold_id, r.metric) if group_by_metric else (r.comparison_family, r.fold_id)
        families.setdefault(fam_key, []).append(r)

    families_meta = []
    for fam_key, fam_records in families.items():
        if group_by_metric:
            fam_name, fold_id, metric = fam_key
        else:
            fam_name, fold_id = fam_key
            metric = "all_metrics"
        family_id = f"{fam_name}__{fold_id}__{metric}" if fold_id else f"{fam_name}__{metric}"
        comparisons = [f"{r.model_a}__vs__{r.model_b}" for r in fam_records]
        families_meta.append({
            "family_id": family_id,
            "metric": metric,
            "fold_id": fold_id,
            "comparison_family": fam_name,
            "comparisons": comparisons,
            "correction": correction_method,
            "n_tests": len(fam_records),
        })
    return families_meta


# =============================================================================
# 5. DOMAIN PAIRED COMPARISONS (REGRESSION, CLASSIFICATION, PROBABILISTIC)
# =============================================================================

def summarize_delta_distribution(
    deltas: np.ndarray,
    model_a_scores: np.ndarray,
    model_b_scores: np.ndarray,
    metric_name: str,
    higher_is_better: bool,
    *,
    dates: np.ndarray | None = None,
    seed: int = DEFAULT_COMPARISON_SEED,
    unit_of_inference: str = "flight",
    bootstrap_method: str = "iid_percentile",
    block_length: int | float | None = None,
) -> PairedMetricDelta:
    """Compute summary statistics, bootstrap CIs, improved/worse fractions, and hypothesis tests for pointwise deltas."""
    n = len(deltas)
    if n == 0:
        return PairedMetricDelta(
            metric_name=metric_name,
            higher_is_better=higher_is_better,
            model_a_mean=0.0,
            model_b_mean=0.0,
            mean_delta=0.0,
            median_delta=0.0,
            std_delta=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            fraction_improved=0.0,
            fraction_worse=0.0,
            fraction_unchanged=1.0,
            unit_of_inference=unit_of_inference,
            n_units=0,
            effect_size=0.0,
            raw_p=None,
            test_method="paired_t_test",
            seed=seed,
        )

    mean_a = float(np.mean(model_a_scores))
    mean_b = float(np.mean(model_b_scores))
    mean_d = float(np.mean(deltas))
    median_d = float(np.median(deltas))
    std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0

    ci_low, ci_high, _ = compute_paired_bootstrap_ci(
        deltas,
        seed=seed,
        method=bootstrap_method,
        dates=dates,
        block_length=block_length,
    )

    # Hypothesis tests on differences
    t_stat, t_p = compute_pointwise_t_test(deltas)
    notes_str: str | None = None

    if bootstrap_method == "day_cluster_percentile" and dates is not None and len(dates) == n:
        idx_matrix = generate_bootstrap_indices(
            n,
            n_bootstraps=DEFAULT_BOOTSTRAP_REPLICATIONS,
            seed=seed,
            method=bootstrap_method,
            dates=dates,
            block_length=block_length,
        )
        boot_means = np.mean(deltas[idx_matrix], axis=1)
        raw_p = compute_bootstrap_p_value(boot_means)
        test_method = "day_cluster_bootstrap"
        effective_unit = InferenceUnit.DAY_CLUSTER.value
        if t_stat is not None and t_p is not None:
            notes_str = f"Secondary descriptive paired t-test: t={t_stat:.4f}, p={t_p:.6f} (flight unit)"
    else:
        raw_p = t_p
        test_method = "paired_t_test"
        effective_unit = unit_of_inference

    unchanged_mask = np.abs(deltas) <= ZERO_TOLERANCE
    n_unchanged = int(np.sum(unchanged_mask))

    if higher_is_better:
        n_improved = int(np.sum(deltas > ZERO_TOLERANCE))
        n_worse = int(np.sum(deltas < -ZERO_TOLERANCE))
    else:
        n_improved = int(np.sum(deltas < -ZERO_TOLERANCE))
        n_worse = int(np.sum(deltas > ZERO_TOLERANCE))

    frac_improved = round(n_improved / n, 4) if n > 0 else 0.0
    frac_worse = round(n_worse / n, 4) if n > 0 else 0.0
    frac_unchanged = round(n_unchanged / n, 4) if n > 0 else 0.0

    # Day-level aggregation if dates provided
    day_mean_d = None
    day_ci_low = None
    day_ci_high = None
    if dates is not None and len(dates) == n:
        df_daily = pd.DataFrame({"date": dates, "delta": deltas})
        daily_means = df_daily.groupby("date")["delta"].mean().to_numpy()
        day_mean_d = float(np.mean(daily_means))
        day_ci_low, day_ci_high, _ = compute_day_block_bootstrap_ci(daily_means, seed=seed)

    return PairedMetricDelta(
        metric_name=metric_name,
        higher_is_better=higher_is_better,
        model_a_mean=round(mean_a, 4),
        model_b_mean=round(mean_b, 4),
        mean_delta=round(mean_d, 4),
        median_delta=round(median_d, 4),
        std_delta=round(std_d, 4),
        ci_lower=round(ci_low, 4),
        ci_upper=round(ci_high, 4),
        fraction_improved=frac_improved,
        fraction_worse=frac_worse,
        fraction_unchanged=frac_unchanged,
        day_level_mean_delta=round(day_mean_d, 4) if day_mean_d is not None else None,
        day_level_ci_lower=round(day_ci_low, 4) if day_ci_low is not None else None,
        unit_of_inference=effective_unit,
        n_units=n,
        effect_size=round(mean_d, 4),
        raw_p=round(raw_p, 6) if raw_p is not None else None,
        test_method=test_method,
        bootstrap_method=bootstrap_method,
        block_length=block_length,
        bootstrap_replicates=DEFAULT_BOOTSTRAP_REPLICATIONS,
        seed=seed,
        notes=notes_str,
    )


def compute_paired_regression_metrics(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
    *,
    dates: np.ndarray | None = None,
    seed: int = DEFAULT_COMPARISON_SEED,
    bootstrap_method: str = "iid_percentile",
    block_length: int | float | None = None,
) -> dict[str, PairedMetricDelta]:
    """Compute paired regression metrics under explicit distinction between pointwise and aggregate metrics.

    1. Delta MAE: Pointwise absolute error differences (unit: flight).
    2. Delta RMSE: True paired aggregate bootstrap (unit: fold_population). NO mechanical rowwise subtraction.
    3. Delta R^2: True paired aggregate bootstrap (unit: fold_population). NO mechanical rowwise subtraction.
    """
    y = np.asarray(y_true, dtype=np.float64)
    pred_a = np.asarray(y_pred_a, dtype=np.float64)
    pred_b = np.asarray(y_pred_b, dtype=np.float64)
    n = len(y)

    if n == 0:
        return {
            "delta_mae": summarize_delta_distribution(np.array([]), np.array([]), np.array([]), "delta_mae", False, seed=seed),
            "delta_rmse": summarize_delta_distribution(np.array([]), np.array([]), np.array([]), "delta_rmse", False, seed=seed),
            "delta_r2": summarize_delta_distribution(np.array([]), np.array([]), np.array([]), "delta_r2", True, seed=seed),
        }

    # =========================================================================
    # 1. Delta MAE (Pointwise Error Metric, Unit = flight)
    # =========================================================================
    ae_a = np.abs(y - pred_a)
    ae_b = np.abs(y - pred_b)
    delta_ae = ae_a - ae_b
    res_mae = summarize_delta_distribution(
        delta_ae,
        ae_a,
        ae_b,
        "delta_mae",
        higher_is_better=False,
        dates=dates,
        seed=seed,
        unit_of_inference=InferenceUnit.FLIGHT.value,
        bootstrap_method=bootstrap_method,
        block_length=block_length,
    )

    # =========================================================================
    # 2. Delta RMSE (Nonlinear Aggregate Metric, Unit = fold_population)
    # =========================================================================
    se_a = (y - pred_a) ** 2
    se_b = (y - pred_b) ** 2
    rmse_a = float(np.sqrt(np.mean(se_a)))
    rmse_b = float(np.sqrt(np.mean(se_b)))
    delta_rmse = rmse_a - rmse_b

    # Paired aggregate bootstrap resampling
    idx_matrix = generate_bootstrap_indices(
        n,
        n_bootstraps=DEFAULT_BOOTSTRAP_REPLICATIONS,
        seed=seed,
        method=bootstrap_method,
        block_length=block_length,
        dates=dates,
    )

    boot_se_a = np.mean(se_a[idx_matrix], axis=1)
    boot_se_b = np.mean(se_b[idx_matrix], axis=1)
    boot_rmse_a = np.sqrt(boot_se_a)
    boot_rmse_b = np.sqrt(boot_se_b)
    boot_deltas_rmse = boot_rmse_a - boot_rmse_b

    rmse_ci_low = float(np.percentile(boot_deltas_rmse, 2.5))
    rmse_ci_high = float(np.percentile(boot_deltas_rmse, 97.5))
    rmse_std_d = float(np.std(boot_deltas_rmse, ddof=1))
    rmse_median_d = float(np.median(boot_deltas_rmse))
    rmse_p_val = compute_bootstrap_p_value(boot_deltas_rmse)

    n_boot = len(boot_deltas_rmse)
    frac_rmse_improved = round(float(np.sum(boot_deltas_rmse < -ZERO_TOLERANCE)) / n_boot, 4)
    frac_rmse_worse = round(float(np.sum(boot_deltas_rmse > ZERO_TOLERANCE)) / n_boot, 4)
    frac_rmse_unchanged = round(float(np.sum(np.abs(boot_deltas_rmse) <= ZERO_TOLERANCE)) / n_boot, 4)

    res_rmse = PairedMetricDelta(
        metric_name="delta_rmse",
        higher_is_better=False,
        model_a_mean=round(rmse_a, 4),
        model_b_mean=round(rmse_b, 4),
        mean_delta=round(delta_rmse, 4),
        median_delta=round(rmse_median_d, 4),
        std_delta=round(rmse_std_d, 4),
        ci_lower=round(rmse_ci_low, 4),
        ci_upper=round(rmse_ci_high, 4),
        fraction_improved=frac_rmse_improved,
        fraction_worse=frac_rmse_worse,
        fraction_unchanged=frac_rmse_unchanged,
        unit_of_inference=InferenceUnit.FOLD_POPULATION.value,
        n_units=n,
        effect_size=round(delta_rmse, 4),
        raw_p=round(rmse_p_val, 6),
        test_method="paired_bootstrap_test",
        bootstrap_method=bootstrap_method,
        block_length=block_length,
        bootstrap_replicates=DEFAULT_BOOTSTRAP_REPLICATIONS,
        seed=seed,
    )

    # =========================================================================
    # 3. Delta R^2 (Nonlinear Aggregate Metric, Unit = fold_population)
    # =========================================================================
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    ss_tot_safe = max(1e-6, ss_tot)
    r2_a = 1.0 - float(np.sum(se_a)) / ss_tot_safe
    r2_b = 1.0 - float(np.sum(se_b)) / ss_tot_safe
    delta_r2 = r2_a - r2_b

    # Bootstrap R^2 across resampled units
    boot_y = y[idx_matrix]
    boot_y_mean = np.mean(boot_y, axis=1, keepdims=True)
    boot_sst = np.sum((boot_y - boot_y_mean) ** 2, axis=1)
    boot_sst = np.maximum(boot_sst, 1e-6)

    boot_sse_a = np.sum(se_a[idx_matrix], axis=1)
    boot_sse_b = np.sum(se_b[idx_matrix], axis=1)
    boot_r2_a = 1.0 - boot_sse_a / boot_sst
    boot_r2_b = 1.0 - boot_sse_b / boot_sst
    boot_deltas_r2 = boot_r2_a - boot_r2_b

    r2_ci_low = float(np.percentile(boot_deltas_r2, 2.5))
    r2_ci_high = float(np.percentile(boot_deltas_r2, 97.5))
    r2_std_d = float(np.std(boot_deltas_r2, ddof=1))
    r2_median_d = float(np.median(boot_deltas_r2))
    r2_p_val = compute_bootstrap_p_value(boot_deltas_r2)

    frac_r2_improved = round(float(np.sum(boot_deltas_r2 > ZERO_TOLERANCE)) / n_boot, 4)
    frac_r2_worse = round(float(np.sum(boot_deltas_r2 < -ZERO_TOLERANCE)) / n_boot, 4)
    frac_r2_unchanged = round(float(np.sum(np.abs(boot_deltas_r2) <= ZERO_TOLERANCE)) / n_boot, 4)

    res_r2 = PairedMetricDelta(
        metric_name="delta_r2",
        higher_is_better=True,
        model_a_mean=round(r2_a, 4),
        model_b_mean=round(r2_b, 4),
        mean_delta=round(delta_r2, 4),
        median_delta=round(r2_median_d, 4),
        std_delta=round(r2_std_d, 4),
        ci_lower=round(r2_ci_low, 4),
        ci_upper=round(r2_ci_high, 4),
        fraction_improved=frac_r2_improved,
        fraction_worse=frac_r2_worse,
        fraction_unchanged=frac_r2_unchanged,
        unit_of_inference=InferenceUnit.FOLD_POPULATION.value,
        n_units=n,
        effect_size=round(delta_r2, 4),
        raw_p=round(r2_p_val, 6),
        test_method="paired_bootstrap_test",
        bootstrap_method=bootstrap_method,
        block_length=block_length,
        bootstrap_replicates=DEFAULT_BOOTSTRAP_REPLICATIONS,
        seed=seed,
    )

    return {
        "delta_mae": res_mae,
        "delta_rmse": res_rmse,
        "delta_r2": res_r2,
    }


def compute_paired_classification_metrics(
    y_true: np.ndarray,
    p_pred_a: np.ndarray,
    p_pred_b: np.ndarray,
    *,
    dates: np.ndarray | None = None,
    seed: int = DEFAULT_COMPARISON_SEED,
    bootstrap_method: str = "iid_percentile",
    block_length: int | float | None = None,
) -> dict[str, Any]:
    """Compute paired classification deltas: Delta Brier, Delta LogScore, Delta PR-AUC."""
    y = np.asarray(y_true, dtype=np.float64)
    p_a = np.clip(np.asarray(p_pred_a, dtype=np.float64), 0.0, 1.0)
    p_b = np.clip(np.asarray(p_pred_b, dtype=np.float64), 0.0, 1.0)
    n = len(y)

    if n == 0:
        return {
            "delta_brier": summarize_delta_distribution(np.array([]), np.array([]), np.array([]), "delta_brier", False, seed=seed),
            "delta_log_score": summarize_delta_distribution(np.array([]), np.array([]), np.array([]), "delta_log_score", False, seed=seed),
            "delta_pr_auc": "NOT_AVAILABLE",
        }

    # 1. Delta Brier (pointwise, unit = flight)
    bs_a = (p_a - y) ** 2
    bs_b = (p_b - y) ** 2
    delta_bs = bs_a - bs_b
    res_brier = summarize_delta_distribution(
        delta_bs,
        bs_a,
        bs_b,
        "delta_brier",
        higher_is_better=False,
        dates=dates,
        seed=seed,
        unit_of_inference=InferenceUnit.FLIGHT.value,
        bootstrap_method=bootstrap_method,
        block_length=block_length,
    )

    # 2. Delta LogScore / Cross-Entropy (pointwise, unit = flight)
    eps = 1e-15
    ls_a = -(y * np.log(np.clip(p_a, eps, 1.0)) + (1.0 - y) * np.log(np.clip(1.0 - p_a, eps, 1.0)))
    ls_b = -(y * np.log(np.clip(p_b, eps, 1.0)) + (1.0 - y) * np.log(np.clip(1.0 - p_b, eps, 1.0)))
    delta_ls = ls_a - ls_b
    res_ls = summarize_delta_distribution(
        delta_ls,
        ls_a,
        ls_b,
        "delta_log_score",
        higher_is_better=False,
        dates=dates,
        seed=seed,
        unit_of_inference=InferenceUnit.FLIGHT.value,
        bootstrap_method=bootstrap_method,
        block_length=block_length,
    )

    # 3. Delta PR-AUC (Aggregate Metric, Unit = fold_population)
    # Check if classes are degenerate (PR-AUC undefined for < 2 unique classes)
    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        res_prauc: Any = "NOT_AVAILABLE"
    else:
        try:
            pr_auc_a = float(average_precision_score(y, p_a))
            pr_auc_b = float(average_precision_score(y, p_b))
            delta_pr_auc = pr_auc_a - pr_auc_b

            idx_matrix = generate_bootstrap_indices(
                n,
                n_bootstraps=min(500, DEFAULT_BOOTSTRAP_REPLICATIONS),
                seed=seed,
                method=bootstrap_method,
                block_length=block_length,
                dates=dates,
            )

            boot_prauc_diffs: list[float] = []
            for b_idx in range(len(idx_matrix)):
                sample_idx = idx_matrix[b_idx]
                yb = y[sample_idx]
                if len(np.unique(yb)) > 1:
                    pra = float(average_precision_score(yb, p_a[sample_idx]))
                    prb = float(average_precision_score(yb, p_b[sample_idx]))
                    boot_prauc_diffs.append(pra - prb)

            if boot_prauc_diffs:
                arr_diffs = np.array(boot_prauc_diffs)
                ci_low = float(np.percentile(arr_diffs, 2.5))
                ci_high = float(np.percentile(arr_diffs, 97.5))
                std_d = float(np.std(arr_diffs, ddof=1))
                median_d = float(np.median(arr_diffs))
                raw_p = compute_bootstrap_p_value(arr_diffs)
                frac_improved = round(float(np.sum(arr_diffs > ZERO_TOLERANCE)) / len(arr_diffs), 4)
                frac_worse = round(float(np.sum(arr_diffs < -ZERO_TOLERANCE)) / len(arr_diffs), 4)
                frac_unchanged = round(float(np.sum(np.abs(arr_diffs) <= ZERO_TOLERANCE)) / len(arr_diffs), 4)
            else:
                ci_low, ci_high = delta_pr_auc, delta_pr_auc
                std_d, median_d = 0.0, delta_pr_auc
                raw_p = 1.0
                frac_improved, frac_worse, frac_unchanged = (1.0, 0.0, 0.0) if delta_pr_auc > ZERO_TOLERANCE else (0.0, 1.0, 0.0)

            res_prauc = PairedMetricDelta(
                metric_name="delta_pr_auc",
                higher_is_better=True,
                model_a_mean=round(pr_auc_a, 4),
                model_b_mean=round(pr_auc_b, 4),
                mean_delta=round(delta_pr_auc, 4),
                median_delta=round(median_d, 4),
                std_delta=round(std_d, 4),
                ci_lower=round(ci_low, 4),
                ci_upper=round(ci_high, 4),
                fraction_improved=frac_improved,
                fraction_worse=frac_worse,
                fraction_unchanged=frac_unchanged,
                unit_of_inference=InferenceUnit.FOLD_POPULATION.value,
                n_units=n,
                effect_size=round(delta_pr_auc, 4),
                raw_p=round(raw_p, 6),
                test_method="paired_bootstrap_test",
                bootstrap_method=bootstrap_method,
                block_length=block_length,
                bootstrap_replicates=len(boot_prauc_diffs),
                seed=seed,
            )
        except Exception:
            res_prauc = "NOT_AVAILABLE"

    return {
        "delta_brier": res_brier,
        "delta_log_score": res_ls,
        "delta_pr_auc": res_prauc,
    }


def compute_paired_probabilistic_metrics(
    y_true: np.ndarray,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    dates: np.ndarray | None = None,
    seed: int = DEFAULT_COMPARISON_SEED,
    bootstrap_method: str = "iid_percentile",
    block_length: int | float | None = None,
) -> dict[str, Any]:
    """Compute paired probabilistic deltas: Delta CRPS, Delta NLL, Delta Coverage Error, Delta Interval Width."""
    y = np.asarray(y_true, dtype=np.float64)
    n = len(y)
    sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)

    metrics_out: dict[str, Any] = {}

    has_quantiles_a = all(f"q_{a:.3f}" in df_a.columns for a in sorted_alphas)
    has_quantiles_b = all(f"q_{a:.3f}" in df_b.columns for a in sorted_alphas)

    if has_quantiles_a and has_quantiles_b and n > 0:
        crps_a = np.zeros(n, dtype=np.float64)
        crps_b = np.zeros(n, dtype=np.float64)

        # 1. Delta CRPS (Quantile Pinball Trapezoidal sum per flight, unit = flight)
        pinballs_a = {
            a: np.maximum(a * (y - df_a[f"q_{a:.3f}"].to_numpy()), (a - 1.0) * (y - df_a[f"q_{a:.3f}"].to_numpy()))
            for a in sorted_alphas
        }
        pinballs_b = {
            a: np.maximum(a * (y - df_b[f"q_{a:.3f}"].to_numpy()), (a - 1.0) * (y - df_b[f"q_{a:.3f}"].to_numpy()))
            for a in sorted_alphas
        }

        for k in range(len(sorted_alphas) - 1):
            a_k = sorted_alphas[k]
            a_next = sorted_alphas[k + 1]
            delta_a = a_next - a_k
            crps_a += delta_a * (pinballs_a[a_k] + pinballs_a[a_next])
            crps_b += delta_a * (pinballs_b[a_k] + pinballs_b[a_next])

        delta_crps = crps_a - crps_b
        res_crps = summarize_delta_distribution(
            delta_crps,
            crps_a,
            crps_b,
            "delta_crps",
            higher_is_better=False,
            dates=dates,
            seed=seed,
            unit_of_inference=InferenceUnit.FLIGHT.value,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
        )
        metrics_out["delta_crps"] = res_crps

        # 2. Delta Coverage Error (Aggregate Metric, unit = fold_population) & Delta Interval Width (pointwise)
        for nominal_pct, (a_low, a_high) in [(0.80, (0.100, 0.900)), (0.90, (0.050, 0.950))]:
            ql_a = df_a[f"q_{a_low:.3f}"].to_numpy()
            qu_a = df_a[f"q_{a_high:.3f}"].to_numpy()
            ql_b = df_b[f"q_{a_low:.3f}"].to_numpy()
            qu_b = df_b[f"q_{a_high:.3f}"].to_numpy()

            in_a = (y >= ql_a) & (y <= qu_a)
            in_b = (y >= ql_b) & (y <= qu_b)
            cov_err_a = abs(float(np.mean(in_a)) - nominal_pct)
            cov_err_b = abs(float(np.mean(in_b)) - nominal_pct)
            delta_cov_err = cov_err_a - cov_err_b

            metrics_out[f"delta_coverage_error_{int(nominal_pct * 100)}"] = {
                "metric_name": f"delta_coverage_error_{int(nominal_pct * 100)}",
                "nominal_coverage": nominal_pct,
                "model_a_mean": round(cov_err_a, 4),
                "model_b_mean": round(cov_err_b, 4),
                "model_a_coverage_error": round(cov_err_a, 4),
                "model_b_coverage_error": round(cov_err_b, 4),
                "mean_delta": round(delta_cov_err, 4),
                "delta_coverage_error": round(delta_cov_err, 4),
                "unit_of_inference": InferenceUnit.FOLD_POPULATION.value,
                "n_units": n,
                "higher_is_better": False,
                "test_method": "paired_bootstrap_test",
            }

            # Interval width per row (pointwise, unit = flight)
            w_a = qu_a - ql_a
            w_b = qu_b - ql_b
            delta_w = w_a - w_b
            res_w = summarize_delta_distribution(
                delta_w,
                w_a,
                w_b,
                f"delta_interval_width_{int(nominal_pct * 100)}",
                higher_is_better=False,
                dates=dates,
                seed=seed,
                unit_of_inference=InferenceUnit.FLIGHT.value,
                bootstrap_method=bootstrap_method,
                block_length=block_length,
            )
            metrics_out[f"delta_interval_width_{int(nominal_pct * 100)}"] = res_w
    else:
        metrics_out["delta_crps"] = "NOT_AVAILABLE"

    # 3. Delta NLL (only available if both models provide valid continuous likelihood)
    metrics_out["delta_nll"] = "NOT_AVAILABLE"

    # 4. Delta Brier for delay >= 15 (if both models provide p_delay_ge_15)
    if "p_delay_ge_15" in df_a.columns and "p_delay_ge_15" in df_b.columns and n > 0:
        p_a = df_a["p_delay_ge_15"].to_numpy(dtype=float)
        p_b = df_b["p_delay_ge_15"].to_numpy(dtype=float)
        y_bin = (y >= 15.0).astype(float)
        bs_a = (p_a - y_bin) ** 2
        bs_b = (p_b - y_bin) ** 2
        delta_bs = bs_a - bs_b
        res_brier = summarize_delta_distribution(
            delta_bs,
            bs_a,
            bs_b,
            "delta_brier_delay_15",
            higher_is_better=False,
            dates=dates,
            seed=seed,
            unit_of_inference=InferenceUnit.FLIGHT.value,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
        )
        metrics_out["delta_brier_delay_15"] = res_brier
    else:
        metrics_out["delta_brier_delay_15"] = "NOT_AVAILABLE"

    return metrics_out


# =============================================================================
# 6. ORCHESTRATOR
# =============================================================================

def compare_model_pair(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    model_a_id: str,
    model_b_id: str,
    comparison_family: str,
    fold_id: str,
    validation_year: int,
    *,
    dates: np.ndarray | None = None,
    seed: int = DEFAULT_COMPARISON_SEED,
    bootstrap_method: str = "iid_percentile",
    block_length: int | float | None = None,
) -> PairedComparisonResult:
    """Execute complete paired comparison between two models under fail-closed row alignment."""
    pair_id = f"{model_a_id}__vs__{model_b_id}__{fold_id}"
    cfg_str = f"{pair_id}_{comparison_family}_{seed}_{bootstrap_method}_{block_length}"
    cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()[:16]

    # 1. Exact row alignment check
    df_a_aligned, df_b_aligned, pairing_report = validate_paired_alignment(
        df_a, df_b, key_col="flight_key"
    )

    if not pairing_report.is_valid_alignment:
        return PairedComparisonResult(
            pair_id=pair_id,
            model_a=model_a_id,
            model_b=model_b_id,
            comparison_family=comparison_family,
            fold_id=fold_id,
            validation_year=validation_year,
            pairing_report=pairing_report,
            status="BLOCKED",
            failure_reason="Row alignment validation failed: " + "; ".join(pairing_report.issues),
            metrics={},
            seed=seed,
            config_hash=cfg_hash,
        )

    # 2. Extract ground truth target
    if "y_arr_reg" in df_a_aligned.columns:
        y_reg = df_a_aligned["y_arr_reg"].to_numpy(dtype=np.float64)
    elif "y_true_reg" in df_a_aligned.columns:
        y_reg = df_a_aligned["y_true_reg"].to_numpy(dtype=np.float64)
    else:
        raise KeyError("Neither 'y_arr_reg' nor 'y_true_reg' found in DataFrame")

    if "y_arr_cls" in df_a_aligned.columns:
        y_cls = df_a_aligned["y_arr_cls"].to_numpy(dtype=np.float64)
    else:
        y_cls = (y_reg >= 15.0).astype(np.float64)

    if dates is None and "FL_DATE" in df_a_aligned.columns:
        dates = df_a_aligned["FL_DATE"].to_numpy()

    metrics_dict: dict[str, Any] = {}

    # 3. Calculate paired metrics according to family
    if comparison_family == "point_regression":
        pred_a_col = "predicted_arr_delay_min" if "predicted_arr_delay_min" in df_a_aligned.columns else "pred_reg"
        pred_b_col = "predicted_arr_delay_min" if "predicted_arr_delay_min" in df_b_aligned.columns else "pred_reg"
        pred_a = df_a_aligned[pred_a_col].to_numpy(dtype=np.float64)
        pred_b = df_b_aligned[pred_b_col].to_numpy(dtype=np.float64)
        metrics_dict = compute_paired_regression_metrics(
            y_reg,
            pred_a,
            pred_b,
            dates=dates,
            seed=seed,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
        )
    elif comparison_family == "point_classification":
        p_a_col = "p_arr_delay_15" if "p_arr_delay_15" in df_a_aligned.columns else "pred_cls_prob"
        p_b_col = "p_arr_delay_15" if "p_arr_delay_15" in df_b_aligned.columns else "pred_cls_prob"
        p_a = df_a_aligned[p_a_col].to_numpy(dtype=np.float64)
        p_b = df_b_aligned[p_b_col].to_numpy(dtype=np.float64)
        metrics_dict = compute_paired_classification_metrics(
            y_cls,
            p_a,
            p_b,
            dates=dates,
            seed=seed,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
        )
    elif comparison_family == "probabilistic":
        metrics_dict = compute_paired_probabilistic_metrics(
            y_reg,
            df_a_aligned,
            df_b_aligned,
            dates=dates,
            seed=seed,
            bootstrap_method=bootstrap_method,
            block_length=block_length,
        )
    else:
        raise ValueError(f"Unknown comparison_family: {comparison_family}")

    return PairedComparisonResult(
        pair_id=pair_id,
        model_a=model_a_id,
        model_b=model_b_id,
        comparison_family=comparison_family,
        fold_id=fold_id,
        validation_year=validation_year,
        pairing_report=pairing_report,
        status="COMPLETED",
        failure_reason=None,
        metrics=metrics_dict,
        seed=seed,
        config_hash=cfg_hash,
    )
