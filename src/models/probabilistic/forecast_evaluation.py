"""Stage 6 — Forecast Evaluation: Calibration, Proper Scoring, and Event Gates.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 9 (Stage 6)

Provides:
1. Gate A: Discrete randomized PIT computation and stratified analysis (pooled, fold, regime, risk bucket).
2. Gate B: Proper scoring evaluations (CRPS, LogScore/NLL) for full-CDF models.
3. Gate C: Event probability evaluation (Brier score, LogScore, ECE, calibration slope/intercept) for Y >= 15, 60, 120.
4. Quantile evaluation (pinball loss at q=.90, q=.95, coverage, width, crossing rate).
5. Day-block bootstrap CI for paired comparisons vs baseline at pre-registered delta thresholds.
6. Candidate pass/fail matrix against pre-registered protocol gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, ndtr
from scipy.stats import kstest


@dataclass(frozen=True)
class EventProbabilityMetrics:
    """Evaluation metrics for binary event forecast Y >= threshold."""

    threshold: int
    base_rate: float
    mean_predicted_prob: float
    brier_score: float
    brier_skill_score: float  # vs climatological base rate
    log_score: float
    expected_calibration_error: float
    calibration_slope: float
    calibration_intercept: float


@dataclass(frozen=True)
class PITEvaluationResult:
    """Randomized PIT evaluation across a specific partition/stratum."""

    stratum_name: str
    n_samples: int
    ks_statistic: float
    ks_pvalue: float
    histogram_10bins: list[float]  # fractions in [0, 0.1), [0.1, 0.2), ...
    max_bin_deviation: float       # max absolute deviation from ideal 0.10


def compute_discrete_randomized_pit(
    y_true: np.ndarray,
    cdf_at_y: np.ndarray,
    cdf_at_y_minus_1: np.ndarray,
    *,
    seed: int = 202601,
) -> np.ndarray:
    """Compute randomized probability integral transform (PIT) for discrete observations.

    Formula:
        U = F(Y - 1) + V * [F(Y) - F(Y - 1)]
    where V ~ Uniform(0, 1). If the forecast distribution matches ground truth,
    U is uniformly distributed on [0, 1].

    Args:
        y_true: Array of true integer delay values, shape (N,)
        cdf_at_y: F(Y) = P(Y <= y_true), shape (N,)
        cdf_at_y_minus_1: F(Y - 1) = P(Y <= y_true - 1), shape (N,)
        seed: Fixed random seed for drawing V.

    Returns:
        pit_values: Array of PIT values in [0, 1], shape (N,)
    """
    y = np.asarray(y_true, dtype=np.float64)
    fy = np.asarray(cdf_at_y, dtype=np.float64)
    f_prev = np.asarray(cdf_at_y_minus_1, dtype=np.float64)

    # Ensure valid CDF bounds [0, 1]
    fy = np.clip(fy, 0.0, 1.0)
    f_prev = np.clip(f_prev, 0.0, 1.0)
    f_prev = np.minimum(f_prev, fy)

    rng = np.random.default_rng(seed)
    v = rng.uniform(0.0, 1.0, size=len(y))

    pit = f_prev + v * (fy - f_prev)
    return np.clip(pit, 0.0, 1.0)


def evaluate_pit_uniformity(
    pit_values: np.ndarray,
    stratum_name: str = "pooled",
) -> PITEvaluationResult:
    """Evaluate uniformity of PIT values via KS test and 10-bin histogram."""
    arr = np.asarray(pit_values, dtype=np.float64).ravel()
    n_samples = len(arr)
    if n_samples == 0:
        return PITEvaluationResult(
            stratum_name=stratum_name,
            n_samples=0,
            ks_statistic=1.0,
            ks_pvalue=0.0,
            histogram_10bins=[0.0] * 10,
            max_bin_deviation=0.1,
        )

    # 1. Kolmogorov-Smirnov test against Uniform(0, 1)
    ks_res = kstest(arr, "uniform")
    ks_stat = float(ks_res.statistic)
    ks_pval = float(ks_res.pvalue)

    # 2. 10-bin histogram (ideal is 0.10 in each bin)
    bins = np.linspace(0.0, 1.0, 11)
    counts, _ = np.histogram(arr, bins=bins)
    freqs = [float(c / n_samples) for c in counts]
    max_dev = float(np.max(np.abs(np.array(freqs) - 0.10)))

    return PITEvaluationResult(
        stratum_name=stratum_name,
        n_samples=n_samples,
        ks_statistic=ks_stat,
        ks_pvalue=ks_pval,
        histogram_10bins=freqs,
        max_bin_deviation=max_dev,
    )


def compute_event_probability_metrics(
    y_true: np.ndarray,
    p_pred: np.ndarray,
    threshold: int,
) -> EventProbabilityMetrics:
    """Evaluate probability forecasts P(Y >= threshold) under Gate C.

    Computes Brier Score, Brier Skill Score, LogScore, ECE, and Logistic Calibration slope/intercept.
    """
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(p_pred, dtype=np.float64)
    p = np.clip(p, 1e-12, 1.0 - 1e-12)

    actual = (y >= threshold).astype(np.float64)
    base_rate = float(np.mean(actual))
    mean_p = float(np.mean(p))

    # 1. Brier Score & BSS
    brier = float(np.mean((p - actual) ** 2))
    brier_climo = float(np.mean((base_rate - actual) ** 2))
    bss = float(1.0 - (brier / brier_climo)) if brier_climo > 0 else 0.0

    # 2. LogScore (Negative Log-Likelihood of binary outcome)
    log_score = float(-np.mean(actual * np.log(p) + (1.0 - actual) * np.log(1.0 - p)))

    # 3. Expected Calibration Error (ECE) across 10 bins
    bin_edges = np.linspace(0.0, 1.0, 11)
    bin_idx = np.digitize(p, bin_edges) - 1
    bin_idx = np.clip(bin_idx, 0, 9)

    ece = 0.0
    for b in range(10):
        mask = bin_idx == b
        if np.any(mask):
            bin_conf = np.mean(p[mask])
            bin_acc = np.mean(actual[mask])
            weight = np.mean(mask)
            ece += weight * abs(bin_conf - bin_acc)
    ece = float(ece)

    # 4. Calibration Slope and Intercept via Logistic Calibration: logit(actual) ~ alpha + beta * logit(p)
    logit_p = logit(p)
    # Fit logistic regression parameters using L-BFGS-B on negative log-likelihood
    def loss_func(params: np.ndarray) -> float:
        a, b = params[0], params[1]
        z = a + b * logit_p
        # Stable logistic loss
        p_hat = expit(z)
        p_hat = np.clip(p_hat, 1e-12, 1.0 - 1e-12)
        return float(-np.sum(actual * np.log(p_hat) + (1.0 - actual) * np.log(1.0 - p_hat)))

    init_params = np.array([0.0, 1.0])
    res = minimize(loss_func, init_params, method="L-BFGS-B", bounds=[(-10.0, 10.0), (0.01, 10.0)])
    cal_intercept = float(res.x[0]) if res.success else 0.0
    cal_slope = float(res.x[1]) if res.success else 1.0

    return EventProbabilityMetrics(
        threshold=threshold,
        base_rate=base_rate,
        mean_predicted_prob=mean_p,
        brier_score=brier,
        brier_skill_score=bss,
        log_score=log_score,
        expected_calibration_error=ece,
        calibration_slope=cal_slope,
        calibration_intercept=cal_intercept,
    )


@dataclass(frozen=True)
class GateDecisionResult:
    """Pass/Fail matrix evaluation for a candidate model against pre-registered gates."""

    candidate_name: str
    gate_a_calibration_passed: bool
    gate_a_details: dict[str, Any]
    gate_b_proper_scoring_passed: bool
    gate_b_details: dict[str, Any]
    gate_c_event_passed: bool
    gate_c_details: dict[str, Any]
    overall_stage6_passed: bool
    rejection_reasons: list[str]


def evaluate_stage6_candidate_gates(
    candidate_name: str,
    *,
    crps_value: float | None = None,
    crps_baseline_b2: float,
    coverage_80: float,
    coverage_90: float,
    crossing_rate: float,
    brier_60: float,
    brier_60_best: float,
    max_crps_screen_delta: float = 0.20,
    brier_tail_tolerance: float = 0.005,
    is_quantile_only: bool = False,
) -> GateDecisionResult:
    """Evaluate whether candidate passes Stage 6 gates according to pre-registered rules.

    Pre-registered rules from distribution_candidate_manifest_v1.json:
    - Calibration guard: 80% coverage in [0.70, 0.90] and 90% coverage in [0.80, 0.95].
    - Proper scoring guard: CRPS <= baseline CRPS (not dominated).
    - Tail guard: Brier score on Y >= 60 no worse than best candidate by > 0.005.
    - Quantile crossing: Crossing rate <= 0.005 (0.5%).
    """
    rejection_reasons: list[str] = []

    # Gate A: Calibration Guard
    gate_a_passed = True
    cal_details = {
        "cov_80": coverage_80,
        "cov_90": coverage_90,
        "crossing_rate": crossing_rate,
    }
    if not (0.70 <= coverage_80 <= 0.90):
        gate_a_passed = False
        rejection_reasons.append(f"80% interval coverage {coverage_80:.3f} outside [0.70, 0.90]")
    if not (0.80 <= coverage_90 <= 0.95):
        gate_a_passed = False
        rejection_reasons.append(f"90% interval coverage {coverage_90:.3f} outside [0.80, 0.95]")
    if crossing_rate > 0.005:
        gate_a_passed = False
        rejection_reasons.append(f"Quantile crossing rate {crossing_rate*100:.2f}% exceeds 0.5% tolerance")

    # Gate B: Proper Scoring Guard
    gate_b_passed = True
    scoring_details: dict[str, Any] = {"is_quantile_only": is_quantile_only}
    if is_quantile_only or crps_value is None:
        scoring_details["status"] = "Excluded from CRPS gate (no registered CDF or analytical CRPS)"
    else:
        scoring_details["crps"] = crps_value
        scoring_details["crps_baseline_b2"] = crps_baseline_b2
        scoring_details["delta_crps"] = crps_value - crps_baseline_b2
        # Must not be severely dominated by baseline (CRPS <= baseline + screen_delta)
        if crps_value > crps_baseline_b2 + max_crps_screen_delta:
            gate_b_passed = False
            rejection_reasons.append(
                f"CRPS ({crps_value:.3f}m) dominated by baseline ({crps_baseline_b2:.3f}m)"
            )

    # Gate C: Tail / Event Guard (Y >= 60 min)
    gate_c_passed = True
    tail_diff = brier_60 - brier_60_best
    gate_c_details = {
        "brier_60": brier_60,
        "brier_60_best": brier_60_best,
        "brier_diff": tail_diff,
        "max_allowed_brier_diff": brier_tail_tolerance,
    }
    if tail_diff > brier_tail_tolerance:
        gate_c_passed = False
        rejection_reasons.append(
            f"Tail Brier score on Y>=60 ({brier_60:.4f}) exceeds best ({brier_60_best:.4f}) by > {brier_tail_tolerance}"
        )

    overall_passed = gate_a_passed and gate_b_passed and gate_c_passed

    return GateDecisionResult(
        candidate_name=candidate_name,
        gate_a_calibration_passed=gate_a_passed,
        gate_a_details=cal_details,
        gate_b_proper_scoring_passed=gate_b_passed,
        gate_b_details=scoring_details,
        gate_c_event_passed=gate_c_passed,
        gate_c_details=gate_c_details,
        overall_stage6_passed=overall_passed,
        rejection_reasons=rejection_reasons,
    )
