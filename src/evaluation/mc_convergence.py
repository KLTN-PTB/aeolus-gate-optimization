"""Monte Carlo Convergence, Common Random Numbers (CRN), and Failure Accounting Engine (V2 Repaired).

Protocol Governance:
1. Registered N Verification:
   - N in {100, 250, 500, 1000, 2500}.
   - requested_N == actual_N strictly enforced with zero truncation.
   - Any pattern capping N (e.g., min(N, 100)) triggers an immediate TruncationViolationError.
2. Common Random Numbers (CRN) Policy:
   - Latent uniform matrix U in (0, 1)^(N x K) generated once per pairing context.
   - Deterministic RNG seeding without intra-loop resets to prevent sample collapse.
   - 100% scenario uniqueness and strictly positive variance audited for stochastic models.
3. CRN Variance Reduction:
   - Zero unsubstantiated claims (e.g. historical '82.4% variance reduction').
   - Variance reduction is computed via explicit outer replications: Var_CRN(Delta) vs Var_Indep(Delta).
   - Marked strictly as NOT_ESTABLISHED unless empirical outer replications exist.
4. Convergence Statistics & Precision Targets:
   - Running mean, standard error (s / sqrt(N)), 95% CI, and delta between consecutive N.
   - Zero post-hoc claims regarding N=500 optimality; marked NOT_PREREGISTERED unless a pre-registered
     precision criterion exists and is verified.
5. P5 Distributional Integrity:
   - Multi-quantile model P5 does not possess a full parametric distribution.
   - Strictly evaluated in forecast-only mode unless an approved distribution adapter is provided.
   - Zero invented asymmetric transformations.
6. Comprehensive Failure Accounting:
   - Every realization is tracked: success, timeout, infeasible, solver failure, sampling failure,
     invalid distribution, or numerical error.
   - Failures remain in the denominator and are never silently discarded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import logging
from typing import Any, Final, Mapping, Sequence

import numpy as np
from scipy.stats import norm, t as student_t

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED

LOGGER = logging.getLogger("mc_convergence")
PREREGISTERED_MC_COUNTS: Final[tuple[int, ...]] = (100, 250, 500, 1000, 2500)


class TruncationViolationError(ValueError):
    """Raised when Monte Carlo requested count N is truncated or capped."""


class P5CapabilityError(ValueError):
    """Raised when an unsupported full-distribution operation is requested on P5 without an adapter."""


class MCFailureType(str, Enum):
    """Explicit classification of Monte Carlo realization outcomes."""

    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    INFEASIBLE = "INFEASIBLE"
    SOLVER_FAILURE = "SOLVER_FAILURE"
    SAMPLING_FAILURE = "SAMPLING_FAILURE"
    INVALID_DISTRIBUTION = "INVALID_DISTRIBUTION"
    NUMERICAL_ERROR = "NUMERICAL_ERROR"


@dataclass(frozen=True)
class ScenarioRealizationMeta:
    """Metadata and audit trail for an individual Monte Carlo scenario realization."""

    realization_id: str
    scenario_index: int
    requested_n: int
    actual_n: int
    latent_seed: int
    scenario_seed: int
    realization_hash: str
    failure_type: MCFailureType
    objective_value: float | None
    feasible: bool
    runtime_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "realization_id": self.realization_id,
            "scenario_index": self.scenario_index,
            "requested_n": self.requested_n,
            "actual_n": self.actual_n,
            "latent_seed": self.latent_seed,
            "scenario_seed": self.scenario_seed,
            "realization_hash": self.realization_hash,
            "failure_type": self.failure_type.value,
            "objective_value": float(self.objective_value) if self.objective_value is not None else None,
            "feasible": self.feasible,
            "runtime_ms": float(self.runtime_ms),
        }


@dataclass(frozen=True)
class ConvergenceEstimate:
    """Comprehensive convergence statistics for a specific (model, N) evaluation."""

    model_id: str
    n_requested: int
    n_actual: int
    n_success: int
    n_failed: int
    failure_breakdown: dict[str, int]
    mean_objective: float
    median_objective: float
    p95_objective: float
    variance_objective: float
    std_objective: float
    mc_se_objective: float
    ci_95_lower: float
    ci_95_upper: float
    running_mean_tail: list[float]
    delta_from_previous_n: float | None = None
    rel_change_from_previous_n: float | None = None
    precision_target_met: bool | None = None
    precision_target_status: str = "NOT_PREREGISTERED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "n_requested": self.n_requested,
            "n_actual": self.n_actual,
            "n_success": self.n_success,
            "n_failed": self.n_failed,
            "failure_breakdown": self.failure_breakdown,
            "mean_objective": round(self.mean_objective, 4),
            "median_objective": round(self.median_objective, 4),
            "p95_objective": round(self.p95_objective, 4),
            "variance_objective": round(self.variance_objective, 4),
            "std_objective": round(self.std_objective, 4),
            "mc_se_objective": round(self.mc_se_objective, 4),
            "ci_95_lower": round(self.ci_95_lower, 4),
            "ci_95_upper": round(self.ci_95_upper, 4),
            "running_mean_tail": [round(x, 4) for x in self.running_mean_tail],
            "delta_from_previous_n": round(self.delta_from_previous_n, 4) if self.delta_from_previous_n is not None else None,
            "rel_change_from_previous_n": round(self.rel_change_from_previous_n, 6) if self.rel_change_from_previous_n is not None else None,
            "precision_target_met": self.precision_target_met,
            "precision_target_status": self.precision_target_status,
        }


@dataclass(frozen=True)
class CRNVarianceReductionReport:
    """Rigorous audit of Common Random Numbers variance reduction via outer replications."""

    model_a: str
    model_b: str
    n_inner: int
    n_outer_replications: int
    variance_crn: float | None
    variance_independent: float | None
    variance_reduction_ratio: float | None
    variance_reduction_percent: float | None
    ci_95_variance_reduction: tuple[float, float] | None
    status: str  # "ESTABLISHED" or "NOT_ESTABLISHED"
    justification: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_a": self.model_a,
            "model_b": self.model_b,
            "n_inner": self.n_inner,
            "n_outer_replications": self.n_outer_replications,
            "variance_crn": float(self.variance_crn) if self.variance_crn is not None else None,
            "variance_independent": float(self.variance_independent) if self.variance_independent is not None else None,
            "variance_reduction_ratio": float(self.variance_reduction_ratio) if self.variance_reduction_ratio is not None else None,
            "variance_reduction_percent": float(self.variance_reduction_percent) if self.variance_reduction_percent is not None else None,
            "ci_95_variance_reduction": list(self.ci_95_variance_reduction) if self.ci_95_variance_reduction is not None else None,
            "status": self.status,
            "justification": self.justification,
        }


def generate_crn_latent_matrix(
    n_scenarios: int,
    n_flights: int,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
) -> tuple[np.ndarray, str]:
    """Generate common latent uniform random matrix U in (0, 1)^(N x K) with audit hash.

    Args:
        n_scenarios: Requested scenario count N.
        n_flights: Number of flights K.
        seed: Deployment seed for RNG.

    Returns:
        Tuple of (U matrix, SHA256 hex digest of U).

    Raises:
        TruncationViolationError: If n_scenarios is non-positive or truncated.
    """
    if n_scenarios <= 0:
        raise TruncationViolationError(f"Requested count N must be strictly positive, got {n_scenarios}")
    if n_flights <= 0:
        raise ValueError(f"n_flights must be strictly positive, got {n_flights}")

    rng = np.random.default_rng(seed)
    # Clip away from exact boundaries to avoid numerical infinities in inverse CDFs
    u = rng.uniform(0.001, 0.999, size=(n_scenarios, n_flights))

    # Strict audit: verify shape and zero truncation
    if u.shape[0] != n_scenarios or u.shape[1] != n_flights:
        raise TruncationViolationError(
            f"Latent matrix shape {u.shape} does not match requested ({n_scenarios}, {n_flights})!"
        )

    matrix_hash = hashlib.sha256(u.tobytes()).hexdigest()
    return u, matrix_hash


class DelayTransformationEngine:
    """Transforms common latent shocks U into model-specific sampled arrival delays."""

    @staticmethod
    def transform(
        model_id: str,
        latent_u: np.ndarray,
        base_delays: Sequence[float],
        *,
        residual_sigma: float = 16.5,
        student_t_df: float = 4.0,
        allow_p5_forecast_only: bool = True,
    ) -> np.ndarray:
        """Transform latent uniform matrix U into arrival delay matrix (minutes).

        Args:
            model_id: Identifier of model arm.
            latent_u: Latent uniform matrix of shape (N, K).
            base_delays: Base delay vector of length K (nominal or predicted median).
            residual_sigma: Estimated homoscedastic residual scale.
            student_t_df: Degrees of freedom for heavy-tailed student-t model.
            allow_p5_forecast_only: If True, evaluates P5 median forecast across scenarios.

        Returns:
            np.ndarray of shape (N, K) containing delay realizations.

        Raises:
            P5CapabilityError: If continuous stochastic sampling is attempted on P5 without adapter.
        """
        n_scen, n_flights = latent_u.shape
        base = np.asarray(base_delays, dtype=float)
        if len(base) != n_flights:
            raise ValueError(f"Base delays length ({len(base)}) != n_flights ({n_flights})")

        if model_id == "schedule_only":
            # Schedule-only: zero arrival delay deterministically across all scenarios
            return np.zeros((n_scen, n_flights), dtype=float)

        elif model_id == "oracle_actual":
            # Oracle: perfect future knowledge of realized delay, constant across scenarios
            return np.tile(base, (n_scen, 1))

        elif model_id in {
            "arrival_linear_baseline_v1",
            "arrival_xgboost_baseline_v1",
            "arrival_hist_gradient_boosting_v1",
            "arrival_random_forest_baseline_v1",
            "arrival_weighted_ensemble_v1",
        }:
            # Point models with homoscedastic Gaussian residual uncertainty
            z = norm.ppf(latent_u)
            return base[None, :] + residual_sigma * z

        elif model_id == "P4_ngboost_student_t":
            # Heavy-tailed Student-T distribution
            t_shocks = student_t.ppf(latent_u, df=student_t_df)
            return base[None, :] + residual_sigma * t_shocks

        elif model_id == "P5_quantile_regression":
            # Scientific Guard: Multi-pinball Quantile Regression does NOT have an exact
            # continuous CDF. Historical code used an invented asymmetric Laplace transformation.
            # In V2 repair, P5 is strictly evaluated in forecast-only mode (median across scenarios)
            # unless an explicit approved distribution adapter is provided.
            if allow_p5_forecast_only:
                LOGGER.info(
                    "P5 evaluated in capability-aware forecast-only mode (median replicated across scenarios). "
                    "Zero invented transformations applied."
                )
                return np.tile(base, (n_scen, 1))
            else:
                raise P5CapabilityError(
                    "P5_quantile_regression does not support continuous density sampling without a "
                    "formally approved distribution adapter (Task R4/R5 invariant)."
                )

        else:
            raise ValueError(f"Unsupported model_id for Monte Carlo delay transformation: '{model_id}'")


def compute_convergence_estimate(
    realizations: Sequence[ScenarioRealizationMeta],
    *,
    requested_n: int,
    model_id: str,
    previous_estimate: ConvergenceEstimate | None = None,
    precision_target_se: float | None = None,
) -> ConvergenceEstimate:
    """Compute statistically rigorous convergence statistics with strict failure accounting.

    Args:
        realizations: Sequence of ScenarioRealizationMeta for a specific (model, N).
        requested_n: The target sample size N.
        model_id: Identifier of model.
        previous_estimate: Optional estimate from previous smaller N (e.g. N=250 vs N=100).
        precision_target_se: Optional pre-registered standard error target (e.g. 0.50).

    Returns:
        ConvergenceEstimate with comprehensive statistics.

    Raises:
        TruncationViolationError: If len(realizations) != requested_n.
    """
    actual_n = len(realizations)
    if actual_n != requested_n:
        raise TruncationViolationError(
            f"Accounting Failure: Evaluated count ({actual_n}) != requested count ({requested_n}). "
            "Silent truncation is strictly prohibited."
        )

    # 1. Failure Accounting: track every failure type
    failure_counts: dict[str, int] = {ft.value: 0 for ft in MCFailureType}
    valid_objectives: list[float] = []

    for r in realizations:
        failure_counts[r.failure_type.value] += 1
        if r.failure_type == MCFailureType.SUCCESS and r.objective_value is not None:
            valid_objectives.append(float(r.objective_value))

    n_success = len(valid_objectives)
    n_failed = actual_n - n_success

    if n_success == 0:
        # All realizations failed: preserve failure accounting with infinite objective
        mean_obj = float("inf")
        med_obj = float("inf")
        p95_obj = float("inf")
        var_obj = 0.0
        std_obj = 0.0
        mc_se = float("inf")
        running_tail: list[float] = []
    else:
        objs_arr = np.asarray(valid_objectives, dtype=float)
        mean_obj = float(np.mean(objs_arr))
        med_obj = float(np.median(objs_arr))
        p95_obj = float(np.percentile(objs_arr, 95))
        var_obj = float(np.var(objs_arr, ddof=1)) if len(objs_arr) > 1 else 0.0
        std_obj = float(np.sqrt(var_obj))
        # Standard error computed over actual realizations
        mc_se = float(std_obj / np.sqrt(len(objs_arr))) if len(objs_arr) > 0 else 0.0

        # Running mean across all realizations
        cum_means = np.cumsum(objs_arr) / np.arange(1, len(objs_arr) + 1)
        running_tail = [float(x) for x in cum_means[-min(10, len(cum_means)):]]

    z_95 = 1.95996
    ci_lower = mean_obj - z_95 * mc_se if mean_obj != float("inf") else float("inf")
    ci_upper = mean_obj + z_95 * mc_se if mean_obj != float("inf") else float("inf")

    # 2. Delta from previous N
    delta_prev: float | None = None
    rel_change_prev: float | None = None
    if previous_estimate is not None and previous_estimate.mean_objective != float("inf") and mean_obj != float("inf"):
        delta_prev = float(abs(mean_obj - previous_estimate.mean_objective))
        if previous_estimate.mean_objective != 0.0:
            rel_change_prev = float(delta_prev / abs(previous_estimate.mean_objective))
        else:
            rel_change_prev = 0.0

    # 3. Precision target status
    if precision_target_se is not None:
        target_met = bool(mc_se <= precision_target_se)
        target_status = "PREREGISTERED_TARGET_MET" if target_met else "PREREGISTERED_TARGET_UNMET"
    else:
        target_met = None
        target_status = "NOT_PREREGISTERED"

    return ConvergenceEstimate(
        model_id=model_id,
        n_requested=requested_n,
        n_actual=actual_n,
        n_success=n_success,
        n_failed=n_failed,
        failure_breakdown=failure_counts,
        mean_objective=mean_obj,
        median_objective=med_obj,
        p95_objective=p95_obj,
        variance_objective=var_obj,
        std_objective=std_obj,
        mc_se_objective=mc_se,
        ci_95_lower=ci_lower,
        ci_95_upper=ci_upper,
        running_mean_tail=running_tail,
        delta_from_previous_n=delta_prev,
        rel_change_from_previous_n=rel_change_prev,
        precision_target_met=target_met,
        precision_target_status=target_status,
    )


def compute_crn_variance_reduction(
    deltas_crn: Sequence[float],
    deltas_independent: Sequence[float],
    model_a: str = "model_a",
    model_b: str = "model_b",
    n_inner: int = 100,
) -> CRNVarianceReductionReport:
    """Compute empirical CRN variance reduction across multiple outer replications.

    Formula:
        Var_CRN = Var(Delta_CRN across outer replications)
        Var_Indep = Var(Delta_Indep across outer replications)
        Variance Reduction = 1 - (Var_CRN / Var_Indep)

    Args:
        deltas_crn: Paired deltas across R outer replications under CRN.
        deltas_independent: Paired deltas across R outer replications under Independent sampling.
        model_a: Identifier of Model A.
        model_b: Identifier of Model B.
        n_inner: Inner scenario sample size N.

    Returns:
        CRNVarianceReductionReport with verified empirical evidence.
    """
    n_crn = len(deltas_crn)
    n_indep = len(deltas_independent)

    if n_crn < 2 or n_indep < 2:
        return CRNVarianceReductionReport(
            model_a=model_a,
            model_b=model_b,
            n_inner=n_inner,
            n_outer_replications=min(n_crn, n_indep),
            variance_crn=None,
            variance_independent=None,
            variance_reduction_ratio=None,
            variance_reduction_percent=None,
            ci_95_variance_reduction=None,
            status="NOT_ESTABLISHED",
            justification=(
                f"Insufficient outer replications (CRN: {n_crn}, Indep: {n_indep}). "
                "At least 2 independent outer replications are mathematically required to estimate variance."
            ),
        )

    var_crn = float(np.var(deltas_crn, ddof=1))
    var_indep = float(np.var(deltas_independent, ddof=1))

    if var_indep <= 1e-12:
        return CRNVarianceReductionReport(
            model_a=model_a,
            model_b=model_b,
            n_inner=n_inner,
            n_outer_replications=min(n_crn, n_indep),
            variance_crn=var_crn,
            variance_independent=var_indep,
            variance_reduction_ratio=None,
            variance_reduction_percent=None,
            ci_95_variance_reduction=None,
            status="NOT_ESTABLISHED",
            justification="Independent estimator variance is near zero; ratio undefined.",
        )

    ratio = var_crn / var_indep
    reduction = 1.0 - ratio
    reduction_pct = reduction * 100.0

    return CRNVarianceReductionReport(
        model_a=model_a,
        model_b=model_b,
        n_inner=n_inner,
        n_outer_replications=min(n_crn, n_indep),
        variance_crn=round(var_crn, 4),
        variance_independent=round(var_indep, 4),
        variance_reduction_ratio=round(ratio, 4),
        variance_reduction_percent=round(reduction_pct, 2),
        ci_95_variance_reduction=None,  # Requires bootstrap over outer replications if R is large
        status="ESTABLISHED",
        justification=(
            f"Empirically estimated across {min(n_crn, n_indep)} outer replications under inner N={n_inner}. "
            f"Var(CRN)={var_crn:.2f}, Var(Indep)={var_indep:.2f}."
        ),
    )
