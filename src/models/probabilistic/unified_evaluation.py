"""Unified Probabilistic Evaluation Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 8, 9, 10
Stage 6 Unified Metrics:
1. Proper Scoring Rules:
   - CRPS: exact analytical Student-T, exact closed-form Gaussian mixture,
     or quantile-based approximation.
   - NLL / LogScore: discrete -log P(Y=y) or continuous -log p(y).
2. Interval Calibration & Sharpness:
   - Coverage and mean width at nominal levels (50%, 80%, 90%, 95%).
3. Event Probability Metrics (Y >= 15, 60, 120):
   - Base rate, mean forecast probability, Brier score, LogScore, Expected Calibration Error (ECE).
4. Pinball Loss:
   - Pre-registered quantiles (0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975).
5. Quantile Crossing & Monotonic Rearrangement:
   - Crossing violation rate and optional sorted rearrangement.
6. Discrete Randomized PIT (rPIT):
   - Kolmogorov-Smirnov test and 10-bin histogram deviation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import expit, logit, ndtr
from scipy.stats import kstest

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PREDETERMINED_DEPLOYMENT_SEED,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.correctness import GaussianMixtureDistribution
from src.models.probabilistic.dependence_interface import MarginalDistributionProtocol
from src.models.probabilistic.forecast_evaluation import (
    PITEvaluationResult,
    compute_discrete_randomized_pit,
    evaluate_pit_uniformity,
)
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
    compute_gaussian_crps,
    compute_pinball_loss,
    compute_quantile_crossing_rate,
)
from src.models.probabilistic.student_t_correctness import (
    StudentTDistribution,
    analytical_student_t_crps,
    log_student_t_diff,
)


@dataclass(frozen=True)
class IntervalMetrics:
    """Interval coverage and sharpness summary."""

    nominal_level: float
    coverage: float
    mean_width: float
    q_lower_nominal: float
    q_upper_nominal: float


@dataclass(frozen=True)
class EventMetrics:
    """Binary event probability metrics for Y >= threshold."""

    threshold: int
    base_rate: float
    mean_predicted_prob: float
    brier_score: float
    log_score: float
    expected_calibration_error: float


@dataclass(frozen=True)
class UnifiedEvaluationResult:
    """Comprehensive evaluation result produced by the unified API."""

    sample_count: int
    discrete: bool
    crps_mean: float | None
    crps_per_sample: np.ndarray | None
    nll_mean: float | None
    nll_per_sample: np.ndarray | None
    intervals: dict[float, IntervalMetrics]
    event_metrics: dict[int, EventMetrics]
    pinball_losses: dict[float, float]
    quantile_crossing_rate: float
    quantile_crossing_inversions: int
    rpit_result: PITEvaluationResult | None

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to JSON-serializable dictionary."""
        return {
            "sample_count": self.sample_count,
            "discrete": self.discrete,
            "crps_mean": float(self.crps_mean) if self.crps_mean is not None else None,
            "nll_mean": float(self.nll_mean) if self.nll_mean is not None else None,
            "intervals": {
                f"{k:.2f}": asdict(v) for k, v in self.intervals.items()
            },
            "event_metrics": {
                str(k): asdict(v) for k, v in self.event_metrics.items()
            },
            "pinball_losses": {
                f"{k:.3f}": float(v) for k, v in self.pinball_losses.items()
            },
            "quantile_crossing_rate": float(self.quantile_crossing_rate),
            "quantile_crossing_inversions": int(self.quantile_crossing_inversions),
            "rpit_result": asdict(self.rpit_result) if self.rpit_result is not None else None,
        }


def compute_expected_calibration_error(
    y_true_binary: np.ndarray,
    p_pred: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE) with equal-width probability bins."""
    actual = np.asarray(y_true_binary, dtype=np.float64)
    probs = np.clip(np.asarray(p_pred, dtype=np.float64), 1e-12, 1.0 - 1e-12)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.digitize(probs, bin_edges) - 1
    bin_idx = np.clip(bin_idx, 0, n_bins - 1)

    ece = 0.0
    n = len(actual)
    if n == 0:
        return 0.0

    for b in range(n_bins):
        mask = bin_idx == b
        if np.any(mask):
            bin_conf = np.mean(probs[mask])
            bin_acc = np.mean(actual[mask])
            weight = np.sum(mask) / n
            ece += weight * abs(bin_conf - bin_acc)
    return float(ece)


def rearrange_quantiles_monotonically(
    quantiles_dict: Mapping[float, np.ndarray],
) -> dict[float, np.ndarray]:
    """Apply monotonic rearrangement to sorted quantile curves.

    Reference: Chernozhukov, Fernandez-Val, Galichon (2010),
    'Quantile and Probability Curves Without Crossing'.
    """
    sorted_alphas = sorted(quantiles_dict.keys())
    q_matrix = np.column_stack([quantiles_dict[a] for a in sorted_alphas])
    sorted_q_matrix = np.sort(q_matrix, axis=-1)
    return {
        alpha: sorted_q_matrix[:, i]
        for i, alpha in enumerate(sorted_alphas)
    }


def compute_quantile_crps_approximation(
    y_true: np.ndarray,
    quantile_preds: Mapping[float, np.ndarray],
) -> np.ndarray:
    """Approximate CRPS from a set of quantile forecasts using the pinball integral.

    CRPS(F, y) = 2 * int_0^1 Pinball_alpha(y, Q(alpha)) d_alpha.
    Uses trapezoidal integration over sorted quantile levels.
    """
    y = np.asarray(y_true, dtype=np.float64)
    sorted_alphas = sorted(quantile_preds.keys())
    m = len(sorted_alphas)
    if m == 0:
        return np.zeros_like(y)

    pinball_mat = np.column_stack([
        compute_pinball_loss(y, quantile_preds[a], a) for a in sorted_alphas
    ])  # shape (N, M)

    if m == 1:
        return 2.0 * pinball_mat[:, 0]

    alphas_arr = np.array(sorted_alphas)
    # Trapezoidal integration along axis 1
    integral = np.trapezoid(pinball_mat, x=alphas_arr, axis=-1)
    # Normalize by covered interval (alpha_max - alpha_min)
    interval_span = alphas_arr[-1] - alphas_arr[0]
    if interval_span > 0:
        integral = integral / interval_span
    return 2.0 * integral


def evaluate_probabilistic_predictions(
    y_true: np.ndarray | Sequence[float | int],
    *,
    distribution: MarginalDistributionProtocol | Sequence[MarginalDistributionProtocol] | None = None,
    student_t_params: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
    gaussian_mixture_params: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
    quantiles: Mapping[float, np.ndarray] | None = None,
    discrete: bool = True,
    compute_rpit: bool = True,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
    rearrange_quantiles: bool = False,
) -> UnifiedEvaluationResult:
    """Execute unified probabilistic evaluation across all protocol gates.

    Supports:
    1. Direct Student-t parametric vector `(mu, sigma, df)`.
    2. Direct Gaussian Mixture parametric vector `(pi, mu, sigma)`.
    3. Single `MarginalDistributionProtocol` or sequence of distribution objects.
    4. Explicit quantile map `{alpha: q_preds}` for non-parametric baselines.
    """
    y_arr = np.asarray(y_true, dtype=np.float64)
    n_samples = len(y_arr)
    if n_samples == 0:
        raise ProbabilisticContractViolation("y_true cannot be empty")

    q_dict: dict[float, np.ndarray] = {}
    crps_per_sample: np.ndarray | None = None
    nll_per_sample: np.ndarray | None = None
    cdf_at_y: np.ndarray | None = None
    cdf_at_y_minus_1: np.ndarray | None = None
    event_probs: dict[int, np.ndarray] = {}

    # Case 1: Vectorized Student-T parameters
    if student_t_params is not None:
        mu, sigma, df = student_t_params
        mu = np.broadcast_to(np.asarray(mu, dtype=np.float64), (n_samples,))
        sigma = np.broadcast_to(np.asarray(sigma, dtype=np.float64), (n_samples,))
        df = np.broadcast_to(np.asarray(df, dtype=np.float64), (n_samples,))

        crps_per_sample = analytical_student_t_crps(y_arr, mu, sigma, df)

        if discrete:
            a = (y_arr - 0.5 - mu) / sigma
            b = (y_arr + 0.5 - mu) / sigma
            nll_per_sample = -log_student_t_diff(a, b, df)
            cdf_at_y = StudentTDistribution(0.0, 1.0, 3.0, discrete=True).cdf(
                (y_arr + 0.5 - mu) / sigma
            )
            # F(y - 1)
            cdf_at_y_minus_1 = StudentTDistribution(0.0, 1.0, 3.0, discrete=True).cdf(
                (y_arr - 0.5 - mu) / sigma
            )
        else:
            z = (y_arr - mu) / sigma
            from scipy.stats import t as sc_t
            nll_per_sample = -(sc_t.logpdf(z, df=df) - np.log(sigma))
            cdf_at_y = sc_t.cdf(z, df=df)
            cdf_at_y_minus_1 = cdf_at_y

        # Quantiles
        from scipy.stats import t as sc_t
        for alpha in PRE_REGISTERED_QUANTILES:
            z_q = sc_t.ppf(alpha, df=df)
            if discrete:
                q_dict[alpha] = np.ceil(mu + sigma * z_q - 0.5).astype(np.int64)
            else:
                q_dict[alpha] = mu + sigma * z_q

        # Event probabilities Y >= threshold
        for thr in EVENT_THRESHOLDS:
            k = float(thr)
            if discrete:
                z_k = (k - 0.5 - mu) / sigma
            else:
                z_k = (k - mu) / sigma
            event_probs[int(thr)] = sc_t.sf(z_k, df=df)

    # Case 2: Vectorized Gaussian Mixture parameters
    elif gaussian_mixture_params is not None:
        pi, mu, sigma = gaussian_mixture_params
        pi = np.asarray(pi, dtype=np.float64)
        mu = np.asarray(mu, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)

        if pi.ndim == 1:
            pi = np.tile(pi, (n_samples, 1))
            mu = np.tile(mu, (n_samples, 1))
            sigma = np.tile(sigma, (n_samples, 1))

        from src.models.probabilistic.distribution_ablation import (
            gaussian_mixture_crps,
            vectorized_discrete_mixture_quantile,
        )
        from src.models.probabilistic.likelihood import (
            continuous_mixture_log_prob,
            discrete_mixture_cdf,
            discretized_mixture_log_prob,
        )

        crps_per_sample = gaussian_mixture_crps(y_arr, pi, mu, sigma)

        if discrete:
            nll_per_sample = -discretized_mixture_log_prob(y_arr, pi, mu, sigma)
            cdf_at_y = discrete_mixture_cdf(y_arr, pi, mu, sigma)
            cdf_at_y_minus_1 = discrete_mixture_cdf(y_arr - 1.0, pi, mu, sigma)
        else:
            nll_per_sample = -continuous_mixture_log_prob(y_arr, pi, mu, sigma)
            # Continuous CDF: sum_k pi_k Phi((y - mu)/sigma)
            z_cont = (y_arr[:, None] - mu) / sigma
            cdf_at_y = np.sum(pi * ndtr(z_cont), axis=-1)
            cdf_at_y_minus_1 = cdf_at_y

        for alpha in PRE_REGISTERED_QUANTILES:
            if discrete:
                q_dict[alpha] = vectorized_discrete_mixture_quantile(alpha, pi, mu, sigma)
            else:
                # Continuous quantiles via fast bisection or root-finding
                q_vals = np.empty(n_samples, dtype=np.float64)
                for i in range(n_samples):
                    gm = GaussianMixtureDistribution(pi[i], mu[i], sigma[i], discrete=False)
                    q_vals[i] = float(gm.quantile(alpha))
                q_dict[alpha] = q_vals

        for thr in EVENT_THRESHOLDS:
            k = float(thr)
            if discrete:
                z_k = -(k - 0.5 - mu) / sigma
            else:
                z_k = -(k - mu) / sigma
            event_probs[int(thr)] = np.sum(pi * ndtr(z_k), axis=-1)

    # Case 3: Marginal Distribution Object or Sequence
    elif distribution is not None:
        if not isinstance(distribution, Sequence):
            dist_list = [distribution] * n_samples
        else:
            dist_list = list(distribution)
            if len(dist_list) != n_samples:
                raise ProbabilisticContractViolation(
                    f"Mismatch between distribution sequence ({len(dist_list)}) and y_true ({n_samples})"
                )

        crps_vals = np.empty(n_samples, dtype=np.float64)
        nll_vals = np.empty(n_samples, dtype=np.float64)
        cdf_y_vals = np.empty(n_samples, dtype=np.float64)
        cdf_y_prev_vals = np.empty(n_samples, dtype=np.float64)

        for i, d in enumerate(dist_list):
            yi = y_arr[i]
            if hasattr(d, "crps"):
                crps_vals[i] = float(d.crps(yi))
            else:
                crps_vals[i] = np.nan

            if hasattr(d, "log_prob"):
                nll_vals[i] = -float(d.log_prob(yi))
            else:
                nll_vals[i] = np.nan

            cdf_y_vals[i] = float(d.cdf(yi))
            if discrete:
                cdf_y_prev_vals[i] = float(d.cdf(yi - 1.0))
            else:
                cdf_y_prev_vals[i] = cdf_y_vals[i]

        crps_per_sample = crps_vals if not np.all(np.isnan(crps_vals)) else None
        nll_per_sample = nll_vals if not np.all(np.isnan(nll_vals)) else None
        cdf_at_y = cdf_y_vals
        cdf_at_y_minus_1 = cdf_y_prev_vals

        for alpha in PRE_REGISTERED_QUANTILES:
            q_dict[alpha] = np.array([d.quantile(alpha) for d in dist_list])

        for thr in EVENT_THRESHOLDS:
            if hasattr(dist_list[0], "event_prob"):
                event_probs[int(thr)] = np.array([d.event_prob(thr) for d in dist_list])
            else:
                # Derive from CDF
                if discrete:
                    event_probs[int(thr)] = np.array([1.0 - d.cdf(thr - 1.0) for d in dist_list])
                else:
                    event_probs[int(thr)] = np.array([1.0 - d.cdf(thr) for d in dist_list])

    # Case 4: Explicit Quantile Map
    elif quantiles is not None:
        q_dict = {float(a): np.asarray(arr, dtype=np.float64) for a, arr in quantiles.items()}
        # Compute quantile-based CRPS approximation
        crps_per_sample = compute_quantile_crps_approximation(y_arr, q_dict)
        nll_per_sample = None
        cdf_at_y = None
        cdf_at_y_minus_1 = None
    else:
        raise ProbabilisticContractViolation(
            "Must provide one of: distribution, student_t_params, gaussian_mixture_params, or quantiles"
        )

    # Check and optionally rearrange quantiles
    crossing_rate, total_inversions = compute_quantile_crossing_rate(q_dict)
    if rearrange_quantiles and total_inversions > 0:
        q_dict = rearrange_quantiles_monotonically(q_dict)
        crossing_rate, total_inversions = 0.0, 0

    # Compute Interval Metrics
    intervals_res: dict[float, IntervalMetrics] = {}
    for nom_level, (a_low, a_high) in SYMMETRIC_INTERVAL_PAIRS.items():
        if a_low in q_dict and a_high in q_dict:
            ql = q_dict[a_low]
            qu = q_dict[a_high]
            cov = float(np.mean((y_arr >= ql) & (y_arr <= qu)))
            width = float(np.mean(qu - ql))
            intervals_res[nom_level] = IntervalMetrics(
                nominal_level=nom_level,
                coverage=cov,
                mean_width=width,
                q_lower_nominal=a_low,
                q_upper_nominal=a_high,
            )

    # Compute Event Metrics
    event_res: dict[int, EventMetrics] = {}
    for thr in EVENT_THRESHOLDS:
        thr_int = int(thr)
        actual_bin = (y_arr >= thr).astype(np.float64)
        base_rate = float(np.mean(actual_bin))

        if thr_int in event_probs:
            p_thr = np.clip(event_probs[thr_int], 1e-12, 1.0 - 1e-12)
            mean_p = float(np.mean(p_thr))
            brier = float(np.mean((p_thr - actual_bin) ** 2))
            log_score = float(-np.mean(actual_bin * np.log(p_thr) + (1.0 - actual_bin) * np.log(1.0 - p_thr)))
            ece = compute_expected_calibration_error(actual_bin, p_thr)
            event_res[thr_int] = EventMetrics(
                threshold=thr_int,
                base_rate=base_rate,
                mean_predicted_prob=mean_p,
                brier_score=brier,
                log_score=log_score,
                expected_calibration_error=ece,
            )

    # Compute Pinball Losses
    pinball_res: dict[float, float] = {}
    for alpha, q_vals in q_dict.items():
        loss = compute_pinball_loss(y_arr, q_vals, alpha)
        pinball_res[alpha] = float(np.mean(loss))

    # Compute rPIT
    rpit_res: PITEvaluationResult | None = None
    if compute_rpit and cdf_at_y is not None:
        if discrete and cdf_at_y_minus_1 is not None:
            pit_vals = compute_discrete_randomized_pit(
                y_arr, cdf_at_y, cdf_at_y_minus_1, seed=seed
            )
        else:
            pit_vals = np.clip(cdf_at_y, 0.0, 1.0)
        rpit_res = evaluate_pit_uniformity(pit_vals, stratum_name="unified_evaluation")

    crps_mean = float(np.mean(crps_per_sample)) if crps_per_sample is not None else None
    nll_mean = float(np.mean(nll_per_sample)) if nll_per_sample is not None else None

    return UnifiedEvaluationResult(
        sample_count=n_samples,
        discrete=discrete,
        crps_mean=crps_mean,
        crps_per_sample=crps_per_sample,
        nll_mean=nll_mean,
        nll_per_sample=nll_per_sample,
        intervals=intervals_res,
        event_metrics=event_res,
        pinball_losses=pinball_res,
        quantile_crossing_rate=crossing_rate,
        quantile_crossing_inversions=total_inversions,
        rpit_result=rpit_res,
    )
