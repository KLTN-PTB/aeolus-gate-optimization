"""Correctness and Numerical Validity Guard for Probabilistic Predictions (Phase 4).

Protocol: Phase 4 Common Distribution Contract
Scope:
Capability-aware numerical safety validation before calculating metrics:
1. Finite values (no NaN, no Inf) on all supported outputs
2. Probability in [0, 1] for candidates supporting event probabilities
3. Quantile monotonicity across sorted alphas for candidates supporting quantiles
4. CDF non-decreasing across delay domain for candidates supporting continuous CDF
5. Valid sampling (correct shape, finite draws, determinism) for candidates supporting samplers
6. Valid distribution parameters (sigma > 0, df > 2.0 for Student-T)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Sequence

import numpy as np

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionValidationError,
    PredictiveDistribution,
)
from src.models.probabilistic.contracts import DEFAULT_SIGMA_FLOOR
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES


@dataclass(frozen=True)
class CorrectnessReport:
    """Report detailing numerical correctness validation."""

    is_valid: bool
    issues: tuple[str, ...]
    checked_tests: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": list(self.issues),
            "checked_tests": list(self.checked_tests),
        }


def validate_candidate_correctness(
    prediction: PredictiveDistribution,
    *,
    test_seed: int = 202601,
) -> CorrectnessReport:
    """Validate that candidate predictions are mathematically and numerically sound."""
    issues: list[str] = []
    tests_run: list[str] = []

    caps = prediction.metadata().get("capabilities", {})

    # 1. Distribution contract internal validation
    tests_run.append("contract_validate_check")
    try:
        prediction.validate()
    except DistributionValidationError as val_err:
        issues.append(f"Validation error: {val_err}")
    except Exception as exc:
        issues.append(f"Unexpected validation exception: {exc}")

    # 2. Probability in [0, 1] if supported
    if caps.get("has_p_delay_ge_15", False) or caps.get("has_probability_ge", False):
        tests_run.append("probability_bounds_check")
        try:
            p_15 = prediction.probability_ge(15.0)
            if np.any(p_15 < -1e-6) or np.any(p_15 > 1.0 + 1e-6):
                issues.append(
                    f"Event probability P(delay >= 15) outside [0, 1]: min={np.min(p_15)}, max={np.max(p_15)}"
                )
        except CapabilityNotSupportedError:
            pass

    # 3. Quantile monotonicity if supported
    if caps.get("has_quantiles", False):
        tests_run.append("quantile_monotonicity_check")
        sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)
        for i in range(len(sorted_alphas) - 1):
            a_low = sorted_alphas[i]
            a_high = sorted_alphas[i + 1]
            try:
                q_low = prediction.quantile(a_low)
                q_high = prediction.quantile(a_high)
                inversions = q_low > (q_high + 1e-5)
                if np.any(inversions):
                    issues.append(
                        f"Quantile monotonicity violation: q_{a_low} > q_{a_high} on {np.sum(inversions)} rows"
                    )
            except CapabilityNotSupportedError:
                pass

    # 4. CDF non-decreasing check if supported
    if caps.get("has_cdf", False):
        tests_run.append("cdf_non_decreasing_check")
        grid = np.linspace(-60.0, 180.0, 15)
        try:
            cdf_evals = [prediction.cdf(y) for y in grid]
            for j in range(len(grid) - 1):
                f_j = cdf_evals[j]
                f_next = cdf_evals[j + 1]
                if np.any(f_j > f_next + 1e-6):
                    issues.append(
                        f"CDF decrease detected between y={grid[j]} and y={grid[j+1]}"
                    )
            f_first = cdf_evals[0]
            f_last = cdf_evals[-1]
            if np.any(f_first < -1e-6) or np.any(f_last > 1.0 + 1e-6):
                issues.append("CDF evaluations exceed valid range [0, 1]")
        except CapabilityNotSupportedError:
            pass

    # 5. Valid sampling check if supported
    if caps.get("has_sampler", False):
        tests_run.append("sampling_validity_check")
        n_sample_draws = 40
        try:
            samples1 = prediction.sample(n_sample_draws, seed=test_seed)
            n_flights = len(prediction.median())
            if samples1.shape != (n_sample_draws, n_flights):
                issues.append(
                    f"Sampler returned shape {samples1.shape}, expected ({n_sample_draws}, {n_flights})"
                )
            if not np.all(np.isfinite(samples1)):
                issues.append("Sampler produced NaN or Inf draws")

            # Determinism under fixed seed
            tests_run.append("sampling_determinism_check")
            samples2 = prediction.sample(n_sample_draws, seed=test_seed)
            if not np.array_equal(samples1, samples2):
                issues.append("Sampler is non-deterministic under identical random seed")

            samples_diff = prediction.sample(n_sample_draws, seed=test_seed + 100)
            if np.array_equal(samples1, samples_diff):
                issues.append("Sampler ignored seed variation and returned identical draws")

        except CapabilityNotSupportedError:
            pass
        except Exception as exc:
            issues.append(f"Sampler raised exception: {exc}")

    # 6. Valid distribution parameters
    meta = prediction.metadata()
    if meta.get("family") in {"xgb_gaussian_oof", "ngboost_normal", "ngboost_student_t"}:
        tests_run.append("distribution_parameter_validity")
        params = meta.get("dist_params", {})
        if "sigma" in params:
            sigma = params["sigma"]
            if np.any(sigma <= 0.0):
                issues.append(f"Parametric sigma must be strictly positive: min={np.min(sigma)}")
        if "df" in params:
            df = params["df"]
            if np.any(df <= 2.0):
                issues.append(f"Student-T df must be strictly > 2.0 for finite variance: min={np.min(df)}")

    return CorrectnessReport(
        is_valid=len(issues) == 0,
        issues=tuple(issues),
        checked_tests=tuple(tests_run),
    )
