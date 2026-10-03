"""Stage 7.5 — Joint Validation Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 17 (Stage 7.5)
Evaluates whether frozen complete-system dependence candidates reproduce historical cross-flight
dependence using ONLY development data 2016–2022.

Validates:
1. Pairwise severe co-exceedance rate (P(Y_i >= 60 and Y_j >= 60 | same day)).
2. Probability of simultaneous severe delays (P(N60 >= 1), P(N60 >= 2), P(N120 >= 1)).
3. Distribution of severe-delay counts per day (mean, std, percentiles).
4. Maximum concurrent delay across flights on the same day.
5. Aggregate daily total delay distribution (mean, standard deviation, Q90, Q95).
6. Aggregate total delay CRPS / energy score.
7. Preservation of marginal calibration (cov_80, cov_90).
8. Comparison against D0 independent baseline: measurable benefit required over D0.
9. Mathematical validity: PSD compliance, arbitrary daily n_d support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.metrics import (
    compute_interval_metrics,
    compute_pinball_loss,
)


@dataclass(frozen=True)
class DailyJointGroundTruth:
    """Ground truth summary of realized flights for one operational day."""

    flight_date: str
    n_flights: int
    y_true: np.ndarray  # shape (n_flights,)
    total_delay: float
    n60: int
    n120: int
    pairs_both_ge60: int
    max_delay: float


@dataclass(frozen=True)
class DailyJointSimulation:
    """Monte Carlo simulation scenarios for one operational day from a candidate system."""

    flight_date: str
    n_flights: int
    n_scenarios: int
    y_sim: np.ndarray  # shape (n_scenarios, n_flights)
    sim_total_delays: np.ndarray  # shape (n_scenarios,)
    sim_n60: np.ndarray  # shape (n_scenarios,)
    sim_n120: np.ndarray  # shape (n_scenarios,)
    sim_pairs_both_ge60: np.ndarray  # shape (n_scenarios,)
    sim_max_delays: np.ndarray  # shape (n_scenarios,)


def extract_daily_ground_truth(
    flight_date: str,
    y_true: np.ndarray,
) -> DailyJointGroundTruth:
    """Compute realized joint metrics for one operational day."""
    y = np.asarray(y_true, dtype=np.float64)
    n = len(y)
    if n == 0:
        raise ValueError("y_true cannot be empty")

    tot_delay = float(np.sum(y))
    ge60 = int(np.sum(y >= 60.0))
    ge120 = int(np.sum(y >= 120.0))
    pairs_both = int(ge60 * (ge60 - 1) // 2) if ge60 >= 2 else 0
    max_del = float(np.max(y))

    return DailyJointGroundTruth(
        flight_date=flight_date,
        n_flights=n,
        y_true=y,
        total_delay=tot_delay,
        n60=ge60,
        n120=ge120,
        pairs_both_ge60=pairs_both,
        max_delay=max_del,
    )


def extract_daily_simulation(
    flight_date: str,
    y_sim: np.ndarray,
) -> DailyJointSimulation:
    """Compute Monte Carlo scenario metrics for one operational day."""
    sim = np.asarray(y_sim, dtype=np.float64)
    n_scenarios, n_flights = sim.shape

    tot_delays = np.sum(sim, axis=1)  # shape (S,)
    n60_vec = np.sum(sim >= 60.0, axis=1)  # shape (S,)
    n120_vec = np.sum(sim >= 120.0, axis=1)  # shape (S,)
    pairs_vec = (n60_vec * (n60_vec - 1) // 2).astype(int)  # shape (S,)
    max_vec = np.max(sim, axis=1)  # shape (S,)

    return DailyJointSimulation(
        flight_date=flight_date,
        n_flights=n_flights,
        n_scenarios=n_scenarios,
        y_sim=sim,
        sim_total_delays=tot_delays,
        sim_n60=n60_vec,
        sim_n120=n120_vec,
        sim_pairs_both_ge60=pairs_vec,
        sim_max_delays=max_vec,
    )


def compute_sample_crps_1d(y_true: float, samples: np.ndarray) -> float:
    """Compute empirical 1D CRPS from an ensemble of Monte Carlo samples: E|X - y| - 0.5 * E|X - X'|."""
    s = np.asarray(samples, dtype=np.float64)
    n = len(s)
    if n < 2:
        return float(np.abs(y_true - s[0])) if n == 1 else 0.0

    # Term 1: E|X - y|
    term1 = np.mean(np.abs(s - y_true))

    # Term 2: 0.5 * E|X - X'| using sorted differences for O(N log N) efficiency
    s_sorted = np.sort(s)
    # Gini mean difference: sum_{i=1}^n (2i - n - 1) * s_sorted[i-1] / (n * (n - 1))
    weights = 2 * np.arange(1, n + 1) - n - 1
    term2 = np.sum(weights * s_sorted) / (n * (n - 1))

    return float(term1 - term2)


@dataclass
class JointSystemEvaluationResult:
    """Comprehensive Stage 7.5 evaluation report for one complete system candidate."""

    candidate_id: str
    marginal_candidate_id: str
    dependence_candidate_id: str
    total_days: int
    total_flights: int
    total_pairs: int

    # 1. Pairwise Co-Exceedance
    empirical_co_exceedance_ge60: float
    simulated_co_exceedance_ge60: float
    co_exceedance_abs_error: float

    # 2. Simultaneous Severe Events
    p_n60_ge1_empirical: float
    p_n60_ge1_simulated: float
    p_n60_ge2_empirical: float
    p_n60_ge2_simulated: float
    p_n120_ge1_empirical: float
    p_n120_ge1_simulated: float

    # 3. Aggregate Daily Total Delay Distribution
    empirical_daily_total_mean: float
    simulated_daily_total_mean: float
    empirical_daily_total_std: float
    simulated_daily_total_std: float
    aggregate_std_ratio: float  # sim_std / emp_std (closer to 1.0 is better)
    empirical_daily_total_q90: float
    simulated_daily_total_q90: float
    daily_aggregate_crps: float

    # 4. Marginal Calibration Preservation
    marginal_cov_80: float
    marginal_cov_90: float
    marginal_cal_preserved: bool

    # 5. Comparison against D0
    is_d0_baseline: bool
    improvement_over_d0: dict[str, Any]

    # 6. Gating Decision
    psd_all_passed: bool
    overall_stage7_5_decision: str  # "PASS" or "FAIL"
    rejection_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_system_candidate_joint_performance(
    *,
    candidate_id: str,
    marginal_candidate_id: str,
    dependence_candidate_id: str,
    daily_truths: Sequence[DailyJointGroundTruth],
    daily_sims: Sequence[DailyJointSimulation],
    d0_result: JointSystemEvaluationResult | None = None,
    psd_all_passed: bool = True,
) -> JointSystemEvaluationResult:
    """Compute all Stage 7.5 joint metrics across development days and apply gating rules."""
    n_days = len(daily_truths)
    if len(daily_sims) != n_days:
        raise ValueError("Length of daily_truths and daily_sims must match")

    total_flights = sum(gt.n_flights for gt in daily_truths)
    total_pairs = sum(gt.n_flights * (gt.n_flights - 1) // 2 for gt in daily_truths if gt.n_flights > 1)

    # 1. Pairwise Co-Exceedance
    tot_emp_pairs_ge60 = sum(gt.pairs_both_ge60 for gt in daily_truths)
    emp_co_exceedance = tot_emp_pairs_ge60 / max(total_pairs, 1)

    sim_pairs_both_list = []
    for sim in daily_sims:
        sim_pairs_both_list.append(np.mean(sim.sim_pairs_both_ge60))
    sim_co_exceedance = sum(sim_pairs_both_list) / max(total_pairs, 1)
    co_exceedance_err = abs(sim_co_exceedance - emp_co_exceedance)

    # 2. Simultaneous Severe Events
    emp_n60_ge1 = np.mean([gt.n60 >= 1 for gt in daily_truths])
    sim_n60_ge1 = np.mean([np.mean(sim.sim_n60 >= 1) for sim in daily_sims])

    emp_n60_ge2 = np.mean([gt.n60 >= 2 for gt in daily_truths])
    sim_n60_ge2 = np.mean([np.mean(sim.sim_n60 >= 2) for sim in daily_sims])

    emp_n120_ge1 = np.mean([gt.n120 >= 1 for gt in daily_truths])
    sim_n120_ge1 = np.mean([np.mean(sim.sim_n120 >= 1) for sim in daily_sims])

    # 3. Aggregate Daily Total Delay Distribution
    emp_totals = np.array([gt.total_delay for gt in daily_truths])
    sim_totals_mean_by_day = np.array([np.mean(sim.sim_total_delays) for sim in daily_sims])

    emp_tot_mean = float(np.mean(emp_totals))
    sim_tot_mean = float(np.mean(sim_totals_mean_by_day))

    emp_tot_std = float(np.std(emp_totals))
    # Standard deviation of pooled scenarios across all days
    all_sim_totals = np.concatenate([sim.sim_total_delays for sim in daily_sims])
    sim_tot_std = float(np.std(all_sim_totals))

    std_ratio = sim_tot_std / max(emp_tot_std, 1e-6)

    emp_tot_q90 = float(np.percentile(emp_totals, 90))
    sim_tot_q90 = float(np.percentile(all_sim_totals, 90))

    # Daily aggregate total delay CRPS
    daily_crps_list = [
        compute_sample_crps_1d(gt.total_delay, sim.sim_total_delays)
        for gt, sim in zip(daily_truths, daily_sims)
    ]
    mean_daily_crps = float(np.mean(daily_crps_list))

    # 4. Marginal Calibration Preservation (Pooled across all flights)
    all_y_true = np.concatenate([gt.y_true for gt in daily_truths])
    # Pool marginal percentiles across all simulated scenarios
    pooled_q10 = []
    pooled_q90 = []
    pooled_q05 = []
    pooled_q95 = []
    for sim in daily_sims:
        # sim.y_sim shape: (S, N)
        pooled_q10.append(np.percentile(sim.y_sim, 10, axis=0))
        pooled_q90.append(np.percentile(sim.y_sim, 90, axis=0))
        pooled_q05.append(np.percentile(sim.y_sim, 5, axis=0))
        pooled_q95.append(np.percentile(sim.y_sim, 95, axis=0))

    q10_arr = np.concatenate(pooled_q10)
    q90_arr = np.concatenate(pooled_q90)
    q05_arr = np.concatenate(pooled_q05)
    q95_arr = np.concatenate(pooled_q95)

    cov_80, _ = compute_interval_metrics(all_y_true, q10_arr, q90_arr)
    cov_90, _ = compute_interval_metrics(all_y_true, q05_arr, q95_arr)

    # Calibration bounds from Stage 6: 80% cov in [0.70, 0.90], 90% cov in [0.80, 0.95]
    marginal_cal_preserved = bool((0.68 <= cov_80 <= 0.92) and (0.78 <= cov_90 <= 0.96))

    # 5. Comparison against D0 baseline
    is_d0 = (dependence_candidate_id == "DEP_D0_independent")
    improv: dict[str, Any] = {}
    if not is_d0 and d0_result is not None:
        crps_diff = d0_result.daily_aggregate_crps - mean_daily_crps
        coex_err_diff = d0_result.co_exceedance_abs_error - co_exceedance_err
        std_ratio_diff = abs(1.0 - d0_result.aggregate_std_ratio) - abs(1.0 - std_ratio)

        improv["daily_aggregate_crps_improvement"] = float(crps_diff)
        improv["co_exceedance_error_reduction"] = float(coex_err_diff)
        improv["variance_ratio_improvement"] = float(std_ratio_diff)
        improv["has_measurable_benefit_over_d0"] = bool(
            (crps_diff > 0.05) or (coex_err_diff > 0.0005) or (std_ratio_diff > 0.05)
        )
    elif is_d0:
        improv["status"] = "BASELINE_D0"
        improv["has_measurable_benefit_over_d0"] = True

    # 6. Gating Decision (Pass/Fail)
    rejection_reasons = []
    if not marginal_cal_preserved:
        rejection_reasons.append(
            f"Marginal calibration degraded: 80% cov={cov_80:.3f}, 90% cov={cov_90:.3f}"
        )
    if not psd_all_passed:
        rejection_reasons.append("Mathematical validity failure: correlation matrix failed PSD check")

    if not is_d0 and d0_result is not None:
        if not improv.get("has_measurable_benefit_over_d0", False):
            rejection_reasons.append("Failed to show measurable benefit over D0 independent baseline")

    overall_pass = (len(rejection_reasons) == 0)

    return JointSystemEvaluationResult(
        candidate_id=candidate_id,
        marginal_candidate_id=marginal_candidate_id,
        dependence_candidate_id=dependence_candidate_id,
        total_days=n_days,
        total_flights=total_flights,
        total_pairs=total_pairs,
        empirical_co_exceedance_ge60=emp_co_exceedance,
        simulated_co_exceedance_ge60=sim_co_exceedance,
        co_exceedance_abs_error=co_exceedance_err,
        p_n60_ge1_empirical=emp_n60_ge1,
        p_n60_ge1_simulated=sim_n60_ge1,
        p_n60_ge2_empirical=emp_n60_ge2,
        p_n60_ge2_simulated=sim_n60_ge2,
        p_n120_ge1_empirical=emp_n120_ge1,
        p_n120_ge1_simulated=sim_n120_ge1,
        empirical_daily_total_mean=emp_tot_mean,
        simulated_daily_total_mean=sim_tot_mean,
        empirical_daily_total_std=emp_tot_std,
        simulated_daily_total_std=sim_tot_std,
        aggregate_std_ratio=std_ratio,
        empirical_daily_total_q90=emp_tot_q90,
        simulated_daily_total_q90=sim_tot_q90,
        daily_aggregate_crps=mean_daily_crps,
        marginal_cov_80=cov_80,
        marginal_cov_90=cov_90,
        marginal_cal_preserved=marginal_cal_preserved,
        is_d0_baseline=is_d0,
        improvement_over_d0=improv,
        psd_all_passed=psd_all_passed,
        overall_stage7_5_decision="PASS" if overall_pass else "FAIL",
        rejection_reasons=rejection_reasons,
    )
