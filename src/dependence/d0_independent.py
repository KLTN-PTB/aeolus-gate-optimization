"""D0 — Independent Joint Dependence Model.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 13 (D0)
Specification:
- Mandatory independent control baseline.
- Y_i sampled from each marginal distribution independently.
- Zero cross-flight coupling: Cov(U_i, U_j) = 0 for all i != j.
- Supports arbitrary daily flight count n_flights dynamically inferred from input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.dependence.base import BaseJointSampler


class IndependentJointSampler(BaseJointSampler):
    """D0 — Independent joint arrival delay sampler."""

    def __init__(self) -> None:
        super().__init__(name="DEP_D0_independent", family="independent")

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample independent uniform variates U ~ Uniform(0, 1)^(n_samples x n_flights)."""
        n_flights = len(flight_features)
        return rng.uniform(1e-6, 1.0 - 1e-6, size=(n_samples, n_flights))
