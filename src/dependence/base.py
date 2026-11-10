"""Base Joint Sampler Protocol and Unified Interface.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15
Provides:
1. Unified JointSampler interface:
   joint_sampler.sample(
       marginal_distributions,
       flight_metadata,
       rng,
       n_samples=...
   )
2. Dynamic flight count inference (arbitrary daily n_flights).
3. Pre-cutoff covariate audit (strictly zero realized outcomes).
4. Backward compatibility with sample_joint() and sample_copula().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import (
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.dependence_interface import MarginalDistributionProtocol

FORBIDDEN_POST_CUTOFF_COLUMNS: frozenset[str] = frozenset({
    "ARR_DELAY",
    "DEP_DELAY",
    "ARR_TIME",
    "DEP_TIME",
    "ACTUAL_ELAPSED_TIME",
    "AIR_TIME",
    "TAXI_IN",
    "TAXI_OUT",
    "WHEELS_ON",
    "WHEELS_OFF",
    "CANCELLED",
    "CANCELLATION_CODE",
    "DIVERTED",
    "CARRIER_DELAY",
    "WEATHER_DELAY",
    "NAS_DELAY",
    "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
})


def validate_flight_batch_inputs(
    marginal_distributions: Sequence[MarginalDistributionProtocol],
    flight_metadata: pd.DataFrame,
) -> int:
    """Validate inputs for daily joint sampling and infer flight count n_flights.

    Args:
        marginal_distributions: Sequence of marginal distribution objects.
        flight_metadata: pd.DataFrame containing pre-cutoff flight features.

    Returns:
        n_flights: Inferred flight count for the day.
    """
    if not isinstance(flight_metadata, pd.DataFrame):
        raise ProbabilisticContractViolation("flight_metadata must be a pandas DataFrame")

    n_flights = len(flight_metadata)
    if n_flights == 0:
        raise ProbabilisticContractViolation("flight_metadata cannot be empty (0 flights)")

    if len(marginal_distributions) != n_flights:
        raise ProbabilisticContractViolation(
            f"Marginal count ({len(marginal_distributions)}) does not match flight_metadata count ({n_flights})"
        )

    # Pre-cutoff leakage guard: zero realized outcome columns permitted
    found_forbidden = FORBIDDEN_POST_CUTOFF_COLUMNS.intersection(flight_metadata.columns)
    if found_forbidden:
        raise ProbabilisticContractViolation(
            f"flight_metadata contains forbidden post-cutoff realized columns: {sorted(found_forbidden)}"
        )

    return n_flights


class BaseJointSampler(ABC):
    """Abstract base class for all joint dependence samplers (D0, D1, D2, D3)."""

    def __init__(self, name: str, family: str) -> None:
        self.name = name
        self.family = family

    @abstractmethod
    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint uniform copula variates U in (0, 1)^(n_samples x n_flights).

        Must infer daily flight count dynamically without assuming fixed dimensions.
        """
        ...

    def sample(
        self,
        marginal_distributions: Sequence[MarginalDistributionProtocol],
        flight_metadata: pd.DataFrame,
        rng: np.random.Generator,
        *,
        n_samples: int = 1000,
    ) -> np.ndarray:
        """Primary unified sampling interface.

        joint_sampler.sample(marginal_distributions, flight_metadata, rng)

        Args:
            marginal_distributions: Sequence of length n_flights.
            flight_metadata: Pre-cutoff features DataFrame with length n_flights.
            rng: Seeded np.random.Generator.
            n_samples: Number of joint scenarios to draw (default 1000).

        Returns:
            np.ndarray of shape (n_samples, n_flights) with finite delay samples.
        """
        n_flights = validate_flight_batch_inputs(marginal_distributions, flight_metadata)

        u = self.sample_copula(flight_metadata, n_samples, rng)
        if u.shape != (n_samples, n_flights):
            raise ProbabilisticContractViolation(
                f"Copula sample shape {u.shape} does not match expected ({n_samples}, {n_flights})"
            )

        y_samples = np.empty((n_samples, n_flights), dtype=np.float64)
        for i in range(n_flights):
            y_samples[:, i] = marginal_distributions[i].quantile(u[:, i])

        if not np.all(np.isfinite(y_samples)):
            raise ProbabilisticContractViolation("Produced joint samples contain non-finite values (NaN/Inf)")

        return y_samples

    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Backward-compatible alias for existing pipeline stages."""
        return self.sample(
            marginal_distributions=marginals,
            flight_metadata=flight_features,
            rng=rng,
            n_samples=n_samples,
        )
