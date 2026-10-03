"""Monte Carlo Scenario Runner for Joint Arrival Delays.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Input: frozen marginal distributions, flight metadata, frozen dependence mechanism, RNG, scenario count.
- Output: array of shape [n_scenarios, n_flights] containing sampled arrival delays in minutes.
- Scenario independence: preserves scheduled flights, samples only uncertain delays, zero leakage of realized delays.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import (
    PREDETERMINED_DEPLOYMENT_SEED,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.dependence_interface import (
    JointDependenceModel,
    MarginalDistributionProtocol,
)


class MonteCarloScenarioRunner:
    """Generates reproducible Monte Carlo arrival delay scenario matrices."""

    def __init__(
        self,
        dependence_model: JointDependenceModel,
    ) -> None:
        self.dependence_model = dependence_model

    def run_scenarios(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_scenarios: int,
        rng: np.random.Generator | int | None = None,
    ) -> np.ndarray:
        """Sample joint arrival delays across all flights for one operational day.

        Args:
            marginals: Sequence of frozen marginal predictive distributions (length n_flights).
            flight_features: DataFrame of strictly pre-cutoff schedule covariates (length n_flights).
            n_scenarios: Number of Monte Carlo scenario realizations (N).
            rng: Optional NumPy random Generator or integer seed.

        Returns:
            np.ndarray of shape (n_scenarios, n_flights) with sampled arrival delays (minutes).
        """
        n_flights = len(flight_features)
        if len(marginals) != n_flights:
            raise ProbabilisticContractViolation(
                f"Mismatch: marginals count ({len(marginals)}) != flight_features count ({n_flights})"
            )
        if n_scenarios <= 0:
            raise ValueError(f"n_scenarios must be strictly positive, got {n_scenarios}")

        # Deterministic generator resolution
        if isinstance(rng, np.random.Generator):
            active_rng = rng
        elif isinstance(rng, (int, np.integer)):
            active_rng = np.random.default_rng(int(rng))
        elif rng is None:
            active_rng = np.random.default_rng(PREDETERMINED_DEPLOYMENT_SEED)
        else:
            raise TypeError(f"Invalid rng type: {type(rng)}")

        # Step 3: Sample only uncertain quantities from frozen dependence model
        # Zero leakage of realized outcomes (ARR_DELAY is NEVER used here)
        scenario_matrix = self.dependence_model.sample_joint(
            marginals=marginals,
            flight_features=flight_features,
            n_samples=n_scenarios,
            rng=active_rng,
        )

        assert scenario_matrix.shape == (n_scenarios, n_flights), (
            f"Expected shape ({n_scenarios}, {n_flights}), got {scenario_matrix.shape}"
        )
        assert not np.isnan(scenario_matrix).any(), "Sampled scenarios contain NaN"
        assert not np.isinf(scenario_matrix).any(), "Sampled scenarios contain Inf"

        return scenario_matrix

    @staticmethod
    def compute_scenario_diagnostics(scenario_matrix: np.ndarray) -> dict[str, Any]:
        """Compute reproducibility, uniqueness, and dispersion diagnostics for a scenario matrix.

        Args:
            scenario_matrix: Array of shape (n_scenarios, n_flights).

        Returns:
            Dictionary containing matrix shape, sha256 hash, uniqueness count, and variance summary.
        """
        import hashlib
        from typing import Any

        n_scenarios, n_flights = scenario_matrix.shape
        matrix_hash = hashlib.sha256(scenario_matrix.tobytes()).hexdigest()
        unique_count = int(len(np.unique(scenario_matrix, axis=0)))
        per_flight_var = np.var(scenario_matrix, axis=0) if n_scenarios > 1 else np.zeros(n_flights)

        return {
            "scenario_shape": [int(n_scenarios), int(n_flights)],
            "scenario_matrix_hash": matrix_hash,
            "number_of_unique_scenarios": unique_count,
            "per_flight_variance_min": float(np.min(per_flight_var)),
            "per_flight_variance_mean": float(np.mean(per_flight_var)),
            "per_flight_variance_max": float(np.max(per_flight_var)),
            "is_all_scenarios_unique": bool(unique_count == n_scenarios),
        }

