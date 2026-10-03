"""Comprehensive Common Evaluation Engine for Probabilistic Forecasts in Aeolus.

Protocol: Phase 4 Common Distribution Contract
Scope:
- Pure evaluator accepting any PredictiveDistribution adhering to common contract
- Evaluates proper scoring rules: CRPS, Pinball losses, NLL (when applicable)
- Evaluates calibration diagnostics: Brier score (Y >= 15), ECE, MCE, and PIT
- Evaluates interval sharpness and empirical coverage (50%, 80%, 90%, 95%)
- Strict model independence: evaluator does not know model internals or modify predictions
- Capability-aware: unsupported metrics are reported as 'NOT_AVAILABLE' without imputation
"""

from __future__ import annotations

from typing import Any, Final, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import norm, t as student_t

from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionValidationError,
    PredictiveDistribution,
)
from src.evaluation.calibration import (
    compute_brier_score,
    compute_calibration_table,
    compute_pit_diagnostics,
)
from src.models.probabilistic.metrics import (
    PRE_REGISTERED_QUANTILES,
    SYMMETRIC_INTERVAL_PAIRS,
)


def compute_pinball_loss(
    y_true: np.ndarray,
    q_pred: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Compute element-wise Pinball (Quantile) loss L_alpha(y, q).

    L_alpha(y, q) = max(alpha * (y - q), (alpha - 1) * (y - q))
    """
    error = y_true - q_pred
    return np.maximum(alpha * error, (alpha - 1.0) * error)


def compute_interval_metrics(
    y_true: np.ndarray,
    q_lower: np.ndarray,
    q_upper: np.ndarray,
) -> tuple[float, float]:
    """Compute empirical coverage and mean interval width for [q_lower, q_upper]."""
    in_interval = (y_true >= q_lower) & (y_true <= q_upper)
    coverage = float(np.mean(in_interval))
    width = float(np.mean(q_upper - q_lower))
    return coverage, width


def compute_gaussian_crps(
    y_true: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
) -> np.ndarray:
    """Closed-form analytical Continuous Ranked Probability Score for Gaussian."""
    z = (y_true - mu) / sigma
    phi_z = norm.pdf(z)
    Phi_z = ndtr(z)
    return sigma * (z * (2.0 * Phi_z - 1.0) + 2.0 * phi_z - 1.0 / np.sqrt(np.pi))


def compute_gaussian_nll(
    y_true: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
) -> np.ndarray:
    """Negative Log-Likelihood for Gaussian."""
    return 0.5 * np.log(2.0 * np.pi * (sigma ** 2)) + ((y_true - mu) ** 2) / (2.0 * (sigma ** 2))


def evaluate_predictive_distribution(
    dist: PredictiveDistribution,
    y_true: np.ndarray | pd.Series,
) -> dict[str, Any]:
    """Comprehensive, capability-aware evaluator for any PredictiveDistribution.

    Guarantees:
    - Zero modification of predictions or internal state
    - Validates numerical soundness first (rejects NaN/Inf/invalid parameters)
    - Computes only valid metrics supported by the candidate's capabilities
    - Reports unsupported metrics as 'NOT_AVAILABLE'
    """
    # 1. Fail closed on numerical corruption
    dist.validate()

    y = np.asarray(y_true, dtype=np.float64)
    meta = dist.metadata()
    caps = meta.get("capabilities", {})
    metrics: dict[str, Any] = {}

    # 2. Pinball losses across pre-registered quantiles
    sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)
    if caps.get("has_quantiles", False):
        pinball_dict: dict[str, float] = {}
        for a in sorted_alphas:
            try:
                q_a = dist.quantile(a)
                loss_val = float(np.mean(compute_pinball_loss(y, q_a, a)))
                pinball_dict[f"alpha_{a:.3f}"] = round(loss_val, 4)
            except CapabilityNotSupportedError:
                pass
        if pinball_dict:
            metrics["pinball_losses"] = pinball_dict
            metrics["mean_pinball_loss"] = round(float(np.mean(list(pinball_dict.values()))), 4)
        else:
            metrics["pinball_losses"] = "NOT_AVAILABLE"
            metrics["mean_pinball_loss"] = "NOT_AVAILABLE"
    else:
        metrics["pinball_losses"] = "NOT_AVAILABLE"
        metrics["mean_pinball_loss"] = "NOT_AVAILABLE"

    # 3. CRPS evaluation
    # Compute via trapezoidal integration over pinball losses if quantiles are available
    if isinstance(metrics.get("pinball_losses"), dict):
        q_crps_sum = 0.0
        for k in range(len(sorted_alphas) - 1):
            a_k = sorted_alphas[k]
            a_next = sorted_alphas[k + 1]
            delta_a = a_next - a_k
            pin_k = metrics["pinball_losses"][f"alpha_{a_k:.3f}"]
            pin_next = metrics["pinball_losses"][f"alpha_{a_next:.3f}"]
            pinball_mid = 0.5 * (pin_k + pin_next)
            q_crps_sum += 2.0 * delta_a * pinball_mid
        metrics["crps_quantile_approx"] = round(q_crps_sum, 4)
    else:
        metrics["crps_quantile_approx"] = "NOT_AVAILABLE"

    # Analytical CRPS if Gaussian
    if meta.get("family") in {"xgb_gaussian_oof", "ngboost_normal"} and "dist_params" in meta:
        dist_params = meta["dist_params"]
        if "mu" in dist_params and "sigma" in dist_params:
            mu = dist_params["mu"]
            sigma = dist_params["sigma"]
            an_crps = float(np.mean(compute_gaussian_crps(y, mu, sigma)))
            metrics["crps"] = round(an_crps, 4)
        else:
            metrics["crps"] = metrics["crps_quantile_approx"]
    else:
        metrics["crps"] = metrics["crps_quantile_approx"]

    # 4. Negative Log-Likelihood (NLL / LogScore)
    if caps.get("has_nll", False):
        dist_params = meta.get("dist_params", {})
        if meta.get("family") in {"xgb_gaussian_oof", "ngboost_normal"} and "mu" in dist_params and "sigma" in dist_params:
            mu = dist_params["mu"]
            sigma = dist_params["sigma"]
            nll_val = float(np.mean(compute_gaussian_nll(y, mu, sigma)))
            metrics["nll"] = round(nll_val, 4)
        elif meta.get("family") == "ngboost_student_t" and "mu" in dist_params and "sigma" in dist_params and "df" in dist_params:
            mu = dist_params["mu"]
            sigma = dist_params["sigma"]
            df_vals = dist_params["df"]
            z = (y - mu) / sigma
            log_p = student_t.logpdf(z, df=df_vals) - np.log(sigma)
            nll_val = float(np.mean(-log_p))
            metrics["nll"] = round(nll_val, 4)
        else:
            metrics["nll"] = "NOT_AVAILABLE"
    else:
        metrics["nll"] = "NOT_AVAILABLE"

    # 5. Empirical Coverage and Mean Interval Width
    if caps.get("has_quantiles", False):
        cov_dict: dict[str, float] = {}
        wid_dict: dict[str, float] = {}
        for nominal_pct, (a_low, a_high) in SYMMETRIC_INTERVAL_PAIRS.items():
            try:
                ql = dist.quantile(a_low)
                qu = dist.quantile(a_high)
                cov, wid = compute_interval_metrics(y, ql, qu)
                key = f"interval_{int(nominal_pct * 100)}"
                cov_dict[key] = round(cov, 4)
                wid_dict[key] = round(wid, 2)
            except CapabilityNotSupportedError:
                pass
        metrics["empirical_coverage"] = cov_dict if cov_dict else "NOT_AVAILABLE"
        metrics["interval_widths"] = wid_dict if wid_dict else "NOT_AVAILABLE"
    else:
        metrics["empirical_coverage"] = "NOT_AVAILABLE"
        metrics["interval_widths"] = "NOT_AVAILABLE"

    # 6. Event Probability & Brier Score for Y >= 15
    if caps.get("has_probability_ge", False) or caps.get("has_p_delay_ge_15", False):
        try:
            p_15 = dist.probability_ge(15.0)
            brier = compute_brier_score(y, p_15, threshold=15.0)
            metrics["brier_score_delay_ge_15"] = round(brier, 5)
            metrics["calibration_diagnostics"] = compute_calibration_table(y, p_15, n_bins=10, threshold=15.0)
        except CapabilityNotSupportedError:
            metrics["brier_score_delay_ge_15"] = "NOT_AVAILABLE"
            metrics["calibration_diagnostics"] = {
                "status": "NOT_AVAILABLE",
                "reason": "Event probability is not supported",
            }
    else:
        metrics["brier_score_delay_ge_15"] = "NOT_AVAILABLE"
        metrics["calibration_diagnostics"] = {
            "status": "NOT_AVAILABLE",
            "reason": "Event probability is not supported",
        }

    # 7. PIT Diagnostics (Kolmogorov-Smirnov Uniformity)
    metrics["pit"] = compute_pit_diagnostics(dist, y)

    # 8. Detailed Metric Capabilities & Provenance Metadata (Task R4 Contract)
    metric_details: dict[str, dict[str, Any]] = {}
    family = meta.get("family", "")

    # Mean
    if caps.get("has_mean", False):
        try:
            m_val = dist.mean()
            metric_details["mean"] = {
                "metric_value": float(np.mean(m_val)),
                "metric_status": "SUPPORTED",
                "metric_method": "conditional_expectation",
                "is_exact": True,
                "is_approximate": False,
                "unsupported_reason": None,
            }
        except CapabilityNotSupportedError:
            metric_details["mean"] = {
                "metric_value": None,
                "metric_status": "NOT_SUPPORTED",
                "metric_method": "none",
                "is_exact": False,
                "is_approximate": False,
                "unsupported_reason": "Conditional mean is unsupported for this candidate.",
            }
    else:
        metric_details["mean"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Quantile/non-parametric models do not estimate conditional mean.",
        }

    # Median
    if caps.get("has_median", True):
        metric_details["median"] = {
            "metric_value": float(np.mean(dist.median())),
            "metric_status": "SUPPORTED",
            "metric_method": "median_quantile_0_50",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["median"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Median is unsupported.",
        }

    # Quantile
    if caps.get("has_quantiles", True):
        metric_details["quantile"] = {
            "metric_value": {k: float(np.mean(v)) for k, v in dist.quantiles.items()},
            "metric_status": "SUPPORTED",
            "metric_method": "pre_registered_9_quantiles",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["quantile"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Quantiles are unsupported.",
        }

    # CDF
    if caps.get("has_cdf", False):
        metric_details["cdf"] = {
            "metric_value": None,
            "metric_status": "SUPPORTED",
            "metric_method": "analytical_cdf" if family in {"xgb_gaussian_oof", "ngboost_normal", "ngboost_student_t"} else "empirical_step_function",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["cdf"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Quantile regression candidates do not provide a continuous CDF. Heuristic synthesis prohibited.",
        }

    # Event Probability
    if caps.get("has_probability_ge", False) or caps.get("has_p_delay_ge_15", False):
        metric_details["event_probability"] = {
            "metric_value": metrics.get("brier_score_delay_ge_15"),
            "metric_status": "SUPPORTED",
            "metric_method": "tail_probability_p_ge_15",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["event_probability"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Binary event probability is unsupported without full CDF or classification head.",
        }

    # Sampling
    if caps.get("has_sampler", False):
        metric_details["sampling"] = {
            "metric_value": None,
            "metric_status": "SUPPORTED",
            "metric_method": "pseudorandom_generative_sampling",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["sampling"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Generative sampling requires inverse CDF transform; unsupported for quantile regression.",
        }

    # CRPS
    is_gaussian = family in {"xgb_gaussian_oof", "ngboost_normal"} and "dist_params" in meta and "mu" in meta.get("dist_params", {})
    if is_gaussian:
        metric_details["crps"] = {
            "metric_value": metrics["crps"],
            "metric_status": "SUPPORTED",
            "metric_method": "analytical_gaussian_crps",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
        metric_details["exact_crps"] = {
            "metric_value": metrics["crps"],
            "metric_status": "SUPPORTED",
            "metric_method": "analytical_gaussian_crps",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["crps"] = {
            "metric_value": metrics["crps_quantile_approx"],
            "metric_status": "APPROXIMATE" if metrics["crps_quantile_approx"] != "NOT_AVAILABLE" else "NOT_SUPPORTED",
            "metric_method": "trapezoidal_pinball_integration_9q",
            "is_exact": False,
            "is_approximate": True,
            "unsupported_reason": None if metrics["crps_quantile_approx"] != "NOT_AVAILABLE" else "Pinball losses not available for CRPS integration",
        }
        metric_details["exact_crps"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Analytical closed-form CRPS is only supported for Gaussian families.",
        }

    metric_details["approximate_crps"] = {
        "metric_value": metrics["crps_quantile_approx"],
        "metric_status": "SUPPORTED" if metrics["crps_quantile_approx"] != "NOT_AVAILABLE" else "NOT_SUPPORTED",
        "metric_method": "trapezoidal_pinball_integration_9q",
        "is_exact": False,
        "is_approximate": True,
        "unsupported_reason": None if metrics["crps_quantile_approx"] != "NOT_AVAILABLE" else "Pinball losses not available",
    }

    # NLL
    if metrics.get("nll") != "NOT_AVAILABLE":
        metric_details["nll"] = {
            "metric_value": metrics["nll"],
            "metric_status": "SUPPORTED",
            "metric_method": "analytical_gaussian_nll" if is_gaussian else "analytical_student_t_nll",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        reason = (
            "Discrete empirical step function has zero density almost everywhere; continuous likelihood is undefined."
            if family in {"empirical", "empirical_carrier_hour"}
            else "Quantile regression models do not possess continuous density; NLL synthesis prohibited."
        )
        metric_details["nll"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": reason,
        }

    # PIT
    pit_res = metrics.get("pit", {})
    if pit_res.get("status") == "AVAILABLE":
        metric_details["pit"] = {
            "metric_value": pit_res,
            "metric_status": "SUPPORTED",
            "metric_method": "continuous_cdf_ks_test",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        reason = pit_res.get("reason", "Continuous PIT is not supported for this candidate.")
        metric_details["pit"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": reason,
        }

    # Coverage
    if metrics.get("empirical_coverage") != "NOT_AVAILABLE":
        metric_details["coverage"] = {
            "metric_value": metrics["empirical_coverage"],
            "metric_status": "SUPPORTED",
            "metric_method": "symmetric_interval_coverage",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["coverage"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Interval coverage requires quantiles.",
        }

    # Interval Width
    if metrics.get("interval_widths") != "NOT_AVAILABLE":
        metric_details["interval_width"] = {
            "metric_value": metrics["interval_widths"],
            "metric_status": "SUPPORTED",
            "metric_method": "symmetric_interval_width",
            "is_exact": True,
            "is_approximate": False,
            "unsupported_reason": None,
        }
    else:
        metric_details["interval_width"] = {
            "metric_value": None,
            "metric_status": "NOT_SUPPORTED",
            "metric_method": "none",
            "is_exact": False,
            "is_approximate": False,
            "unsupported_reason": "Interval widths require quantiles.",
        }

    metrics["metric_details"] = metric_details
    return metrics


def compute_point_forecast_metrics(
    y_true_reg: np.ndarray | pd.Series | Sequence[float],
    pred_reg: np.ndarray | pd.Series | Sequence[float],
    y_true_cls: np.ndarray | pd.Series | Sequence[int] | None = None,
    pred_cls_prob: np.ndarray | pd.Series | Sequence[float] | None = None,
    *,
    probability_estimator_audit: str | None = None,
    severe_threshold: float = 60.0,
) -> dict[str, Any]:
    """Compute Core Point forecast metrics under V4 Synchronized Contract.

    Metrics:
    - MAE
    - RMSE
    - R²
    - Severe Delay MAE >= 60 min
    - PR-AUC (if probability valid)
    - ROC-AUC (if probability valid)
    - Brier score (if probability valid)

    Records sample counts:
    - n_total
    - n_missing
    - n_valid
    - n_failures

    Guarantees:
    - Never declares a champion or 'best' model.
    - Fails closed on invalid probability semantics: ad-hoc mappings (e.g. sigmoid(predicted_delay))
      without an audited probability estimator are strictly rejected.
    """
    y_r = np.asarray(y_true_reg, dtype=float)
    p_r = np.asarray(pred_reg, dtype=float)
    n_total = len(y_r)

    if len(p_r) != n_total:
        raise ValueError(f"Length mismatch: y_true_reg ({n_total}) vs pred_reg ({len(p_r)})")

    valid_mask = np.isfinite(y_r) & np.isfinite(p_r)
    n_valid = int(np.sum(valid_mask))
    n_missing = int(n_total - n_valid)
    n_failures = n_missing

    y_val = y_r[valid_mask]
    p_val = p_r[valid_mask]

    res: dict[str, Any] = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_missing": n_missing,
        "n_failures": n_failures,
        "mae": round(float(mean_absolute_error(y_val, p_val)), 4) if n_valid > 0 else None,
        "rmse": round(float(np.sqrt(mean_squared_error(y_val, p_val))), 4) if n_valid > 0 else None,
        "r2": round(float(r2_score(y_val, p_val)), 4) if n_valid > 1 and np.var(y_val) > 1e-9 else None,
    }

    # Severe delay MAE (ARR_DELAY >= 60 min)
    severe_mask = valid_mask & (y_r >= severe_threshold)
    severe_count = int(np.sum(severe_mask))
    res["severe_delay_count"] = severe_count
    if severe_count > 0:
        res["severe_delay_mae_ge_60"] = round(float(mean_absolute_error(y_r[severe_mask], p_r[severe_mask])), 4)
    else:
        res["severe_delay_mae_ge_60"] = None

    # Classification metrics evaluation with strict probability verification
    if pred_cls_prob is not None and y_true_cls is not None:
        if not probability_estimator_audit:
            raise ValueError(
                "Classification probability provided without an audited probability estimator. "
                "Ad-hoc probability estimation (such as sigmoid(pred_delay)) is strictly prohibited "
                "under V4 Benchmark Protocol."
            )
        p_c = np.asarray(pred_cls_prob, dtype=float)
        y_c = np.asarray(y_true_cls, dtype=int)

        if len(p_c) != n_total or len(y_c) != n_total:
            raise ValueError("Length mismatch between classification targets and predictions.")

        cls_valid_mask = valid_mask & np.isfinite(p_c) & np.isfinite(y_c)
        p_c_valid = p_c[cls_valid_mask]
        y_c_valid = y_c[cls_valid_mask]

        if np.any(p_c_valid < 0.0) or np.any(p_c_valid > 1.0):
            raise ValueError("Classification probabilities must lie strictly in [0.0, 1.0].")

        if len(y_c_valid) > 0 and len(np.unique(y_c_valid)) > 1:
            res["pr_auc"] = round(float(average_precision_score(y_c_valid, p_c_valid)), 5)
            res["roc_auc"] = round(float(roc_auc_score(y_c_valid, p_c_valid)), 5)
            res["brier_score"] = round(float(brier_score_loss(y_c_valid, p_c_valid)), 5)
            res["probability_semantics"] = "VALID_AUDITED_ESTIMATOR"
            res["probability_estimator"] = probability_estimator_audit
        else:
            res["pr_auc"] = None
            res["roc_auc"] = None
            res["brier_score"] = None
            res["probability_semantics"] = "INSUFFICIENT_CLASS_DIVERSITY"
            res["probability_estimator"] = probability_estimator_audit
    else:
        res["pr_auc"] = None
        res["roc_auc"] = None
        res["brier_score"] = None
        res["probability_semantics"] = "NOT_AVAILABLE"
        res["probability_estimator"] = "NONE"

    return res

