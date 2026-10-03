"""Controlled Randomized Discrete Probability Integral Transform (rPIT) and Sensitivity Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 9, 13
Specification:
- Seed-controlled discrete rPIT:
  U_i = F_i(Y_i - 1) + V_i * [F_i(Y_i) - F_i(Y_i - 1)]
  where V_i ~ Uniform(0, 1) drawn via explicit seeded rng.
- Repeatability verified: identical seeds produce bitwise-identical variates.
- Sensitivity analysis across pre-defined evaluation seeds ONLY (no seed cherry-picking).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from src.models.probabilistic.contracts import (
    FINALIST_SEEDS,
    PREDETERMINED_DEPLOYMENT_SEED,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.dependence_interface import MarginalDistributionProtocol


@dataclass(frozen=True)
class PITSensitivityReport:
    """Audit report of randomized PIT sensitivity across predetermined seeds."""

    pre_defined_seeds: list[int]
    n_samples: int
    mean_std_across_seeds: float
    max_std_across_seeds: float
    is_repeatable: bool
    is_sensitivity_stable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pre_defined_seeds": self.pre_defined_seeds,
            "n_samples": self.n_samples,
            "mean_std_across_seeds": float(self.mean_std_across_seeds),
            "max_std_across_seeds": float(self.max_std_across_seeds),
            "is_repeatable": bool(self.is_repeatable),
            "is_sensitivity_stable": bool(self.is_sensitivity_stable),
        }


def compute_controlled_randomized_pit(
    y: np.ndarray,
    marginal_distributions: Sequence[MarginalDistributionProtocol],
    rng: np.random.Generator,
) -> np.ndarray:
    """Compute seed-controlled randomized PIT for discrete integer delays.

    Args:
        y: Observed integer delays, shape (n_flights,)
        marginal_distributions: Sequence of marginal distribution objects of length n_flights.
        rng: Seeded numpy Generator.

    Returns:
        u: Copula uniform variates in (0, 1), shape (n_flights,)
    """
    arr_y = np.asarray(y, dtype=np.float64)
    n = len(arr_y)
    if len(marginal_distributions) != n:
        raise ProbabilisticContractViolation(
            f"Length mismatch: y ({n}) vs marginals ({len(marginal_distributions)})"
        )
    if n == 0:
        raise ProbabilisticContractViolation("y cannot be empty")

    u = np.empty(n, dtype=np.float64)
    v = rng.uniform(1e-6, 1.0 - 1e-6, size=n)

    for i in range(n):
        val = float(arr_y[i])
        m = marginal_distributions[i]
        f_curr = float(m.cdf(val))
        # Check if discrete or continuous
        is_discrete = getattr(m, "discrete", True)
        if is_discrete:
            f_prev = float(m.cdf(val - 1.0))
            delta = max(f_curr - f_prev, 1e-12)
            u[i] = f_prev + v[i] * delta
        else:
            u[i] = f_curr

    return np.clip(u, 1e-6, 1.0 - 1e-6)


def evaluate_pit_seed_sensitivity(
    y: np.ndarray,
    marginal_distributions: Sequence[MarginalDistributionProtocol],
    *,
    seeds: tuple[int, ...] = (202601, 202602, 202603, 202604, 202605),
) -> PITSensitivityReport:
    """Assess PIT stability and repeatability across predetermined seeds."""
    arr_y = np.asarray(y, dtype=np.float64)
    n = len(arr_y)
    if n == 0:
        raise ProbabilisticContractViolation("y cannot be empty")

    # 1. Test repeatability: same seed must produce identical outputs
    rng1 = np.random.default_rng(seeds[0])
    u_run1 = compute_controlled_randomized_pit(arr_y, marginal_distributions, rng1)

    rng2 = np.random.default_rng(seeds[0])
    u_run2 = compute_controlled_randomized_pit(arr_y, marginal_distributions, rng2)

    is_repeatable = bool(np.array_equal(u_run1, u_run2))

    # 2. Run sensitivity across distinct predetermined seeds
    draws: list[np.ndarray] = []
    for s in seeds:
        rng = np.random.default_rng(s)
        u_s = compute_controlled_randomized_pit(arr_y, marginal_distributions, rng)
        draws.append(u_s)

    draws_arr = np.array(draws)  # shape (len(seeds), n)
    std_per_flight = np.std(draws_arr, axis=0)
    mean_std = float(np.mean(std_per_flight))
    max_std = float(np.max(std_per_flight))

    # Uniform random variable in interval [F(y-1), F(y)] has theoretical max std <= 1 / sqrt(12) ~ 0.288
    is_stable = bool(mean_std < 0.25)

    return PITSensitivityReport(
        pre_defined_seeds=list(seeds),
        n_samples=n,
        mean_std_across_seeds=mean_std,
        max_std_across_seeds=max_std,
        is_repeatable=is_repeatable,
        is_sensitivity_stable=is_stable,
    )
