"""D1 — Scenario / Schedule-Block Joint Dependence Model.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 14 (D1)
Specification:
- Scenario conditioning conditioned strictly on pre-cutoff covariates known by T-2h.
- Zero conditioning on realized delay, cancellation, actual ATC, or actual weather.
- Hierarchical factor structure:
  Z_i = w_day * Z_day + w_block * Z_block(i) + w_idio * Z_idio,i
  where w_day^2 + w_block^2 + w_idio^2 = 1.0.
- Guarantees valid exchangeable joint distribution and exact PSD for arbitrary daily n_flights.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import ndtr

from src.dependence.base import (
    FORBIDDEN_POST_CUTOFF_COLUMNS,
    BaseJointSampler,
)
from src.models.probabilistic.contracts import ProbabilisticContractViolation

# Approved carriers considered mainline at KATL
MAINLINE_CARRIERS: frozenset[str] = frozenset({"AA", "DL", "UA", "WN"})


class ScenarioBlockJointSampler(BaseJointSampler):
    """D1 — Scenario / schedule-block hierarchical factor sampler."""

    def __init__(
        self,
        *,
        day_factor_weight: float = 0.20,
        block_factor_weight: float = 0.25,
    ) -> None:
        super().__init__(name="DEP_D1_scenario_block", family="scenario_block")
        self.day_factor_weight = float(day_factor_weight)
        self.block_factor_weight = float(block_factor_weight)

        total_var = self.day_factor_weight**2 + self.block_factor_weight**2
        if total_var >= 1.0:
            raise ProbabilisticContractViolation(
                f"Sum of squared factor weights must be < 1.0 (got {total_var})"
            )
        self.idiosyncratic_weight = float(np.sqrt(1.0 - total_var))

    def _assign_schedule_blocks(self, flight_features: pd.DataFrame) -> list[str]:
        """Assign each flight to a schedule block using ONLY pre-cutoff covariates."""
        # Audit no post-cutoff information is present
        found_forbidden = FORBIDDEN_POST_CUTOFF_COLUMNS.intersection(flight_features.columns)
        if found_forbidden:
            raise ProbabilisticContractViolation(
                f"D1 block assignment encountered realized post-cutoff columns: {sorted(found_forbidden)}"
            )

        blocks: list[str] = []
        dep_hours = flight_features.get("scheduled_departure_hour")
        carriers = flight_features.get("OP_CARRIER")

        n = len(flight_features)
        for idx in range(n):
            hr = int(dep_hours.iloc[idx]) if dep_hours is not None else 12
            c = str(carriers.iloc[idx]).strip() if carriers is not None else "OTHER"

            if hr < 12:
                time_block = "MORN"
            elif hr < 18:
                time_block = "AFTN"
            else:
                time_block = "EVEN"

            tier = "MAIN" if c in MAINLINE_CARRIERS else "REG"
            blocks.append(f"{time_block}_{tier}")

        return blocks

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample copula variates via hierarchical latent factors for arbitrary daily n."""
        n_flights = len(flight_features)
        if n_flights == 0:
            raise ProbabilisticContractViolation("flight_features cannot be empty")

        blocks = self._assign_schedule_blocks(flight_features)
        unique_blocks = sorted(set(blocks))
        block_to_idx = {b: i for i, b in enumerate(unique_blocks)}
        n_blocks = len(unique_blocks)

        # 1. Day-level common factor: shape (n_samples, 1)
        z_day = rng.standard_normal(size=(n_samples, 1))

        # 2. Block-level factors: shape (n_samples, n_blocks)
        z_block = rng.standard_normal(size=(n_samples, n_blocks))

        # 3. Idiosyncratic flight shocks: shape (n_samples, n_flights)
        z_idio = rng.standard_normal(size=(n_samples, n_flights))

        # Map block factors to flights: shape (n_samples, n_flights)
        flight_block_indices = np.array([block_to_idx[b] for b in blocks], dtype=int)
        z_block_mapped = z_block[:, flight_block_indices]

        # Combine into unit-variance latent variables
        z_total = (
            self.day_factor_weight * z_day
            + self.block_factor_weight * z_block_mapped
            + self.idiosyncratic_weight * z_idio
        )

        # Transform to uniform copula coordinates via standard normal CDF
        u = ndtr(z_total)
        return np.clip(u, 1e-6, 1.0 - 1e-6)
