"""Locked interface and specifications for Joint Dependence modeling.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16
Requirements:
1. Must handle variable daily flight counts n_d (no fixed n x n correlation assumption).
2. Must condition strictly on pre-cutoff information (scheduled times, carrier mix, traffic density).
   Conditioning on realized delays, cancellations, or actual weather is strictly prohibited.
3. Must guarantee valid joint distribution (positive semi-definite covariance/correlation matrices).
4. Discrete-PIT handling: randomized probability integral transform with controlled seed and
   sensitivity evaluation across draws.
5. No double-counting: dependence layer must not replicate variance already captured by marginals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final, Protocol, Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import (
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)

MIN_PSD_EIGENVALUE: Final = 1e-6


class MarginalDistributionProtocol(Protocol):
    """Protocol for single-flight marginal predictive distributions."""

    def cdf(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate CDF at y."""
        ...

    def quantile(self, p: np.ndarray | float) -> np.ndarray | float | int:
        """Evaluate quantile function Q(p)."""
        ...

    def sample(self, n_samples: int, rng: np.random.Generator) -> np.ndarray:
        """Sample from the marginal distribution."""
        ...


@dataclass(frozen=True)
class DayFlightBatch:
    """One operational day of flights with strictly pre-cutoff information."""

    flight_date: str
    flight_features: pd.DataFrame  # strictly pre-cutoff features
    observed_delays: np.ndarray | None = None  # ground truth for calibration/audit

    def __post_init__(self) -> None:
        if self.flight_features.empty:
            raise ProbabilisticContractViolation("DayFlightBatch flight_features cannot be empty")
        # Validate no forbidden post-cutoff or unauthorized columns
        forbidden = {"DEP_DELAY", "DEP_TIME", "ARR_TIME", "TAXI_OUT", "TAXI_IN", "WHEELS_OFF", "WHEELS_ON"}
        found_forbidden = forbidden.intersection(self.flight_features.columns)
        if found_forbidden:
            raise ProbabilisticContractViolation(
                f"DayFlightBatch contains realized post-cutoff columns: {sorted(found_forbidden)}"
            )
        # Check predictors match approved set
        unapproved = set(self.flight_features.columns).difference(PROBABILISTIC_PREDICTOR_COLUMNS)
        if unapproved:
            raise ProbabilisticContractViolation(
                f"DayFlightBatch contains unapproved predictor columns: {sorted(unapproved)}"
            )

    @property
    def n_flights(self) -> int:
        return len(self.flight_features)


class PSDPolicy:
    """Ensures positive semi-definiteness for correlation and covariance matrices."""

    @staticmethod
    def ensure_psd(
        matrix: np.ndarray,
        *,
        min_eigenvalue: float = MIN_PSD_EIGENVALUE,
        is_correlation: bool = True,
    ) -> np.ndarray:
        """Project a symmetric matrix to the nearest positive semi-definite matrix."""
        from src.dependence.psd import validate_and_project_psd
        corrected, _ = validate_and_project_psd(
            matrix, min_eigenvalue=min_eigenvalue, is_correlation=is_correlation
        )
        return corrected

    @staticmethod
    def validate_with_diagnostics(
        matrix: np.ndarray,
        *,
        min_eigenvalue: float = MIN_PSD_EIGENVALUE,
        is_correlation: bool = True,
    ):
        """Project matrix to PSD cone and return both corrected matrix and PSDDiagnostic."""
        from src.dependence.psd import validate_and_project_psd
        return validate_and_project_psd(
            matrix, min_eigenvalue=min_eigenvalue, is_correlation=is_correlation
        )


class DiscretePITPolicy:
    """Controlled randomized Probability Integral Transform for discrete margins."""

    @staticmethod
    def compute_randomized_pit(
        y: np.ndarray,
        marginal_cdfs: Sequence[MarginalDistributionProtocol],
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Compute randomized PIT: U_i = F_i(Y_i - 1) + V_i * [F_i(Y_i) - F_i(Y_i - 1)].

        Args:
            y: Observed integer delays, shape (n_flights,)
            marginal_cdfs: Sequence of length n_flights
            rng: Seeded numpy Generator

        Returns:
            u: Uniform variates in (0, 1), shape (n_flights,)
        """
        n = len(y)
        if len(marginal_cdfs) != n:
            raise ProbabilisticContractViolation("Length of y and marginal_cdfs must match")

        u = np.empty(n, dtype=np.float64)
        v = rng.uniform(1e-6, 1.0 - 1e-6, size=n)

        for i in range(n):
            val = float(y[i])
            f_curr = float(marginal_cdfs[i].cdf(val))
            f_prev = float(marginal_cdfs[i].cdf(val - 1.0))
            u[i] = f_prev + v[i] * max(f_curr - f_prev, 1e-12)

        return np.clip(u, 1e-6, 1.0 - 1e-6)

    @staticmethod
    def evaluate_pit_sensitivity(
        y: np.ndarray,
        marginal_cdfs: Sequence[MarginalDistributionProtocol],
        *,
        n_draws: int = 10,
        base_seed: int = 202601,
    ) -> dict[str, float]:
        """Assess sensitivity of copula uniform coordinates across randomized draws."""
        draws = []
        for draw_idx in range(n_draws):
            rng = np.random.default_rng(base_seed + draw_idx)
            u = DiscretePITPolicy.compute_randomized_pit(y, marginal_cdfs, rng)
            draws.append(u)

        draws_arr = np.array(draws)  # shape (n_draws, n_flights)
        std_per_flight = np.std(draws_arr, axis=0)

        return {
            "n_draws": float(n_draws),
            "mean_u_std_across_draws": float(np.mean(std_per_flight)),
            "max_u_std_across_draws": float(np.max(std_per_flight)),
            "sensitivity_stable": float(np.mean(std_per_flight) < 0.25),
        }


class JointDependenceModel(ABC):
    """Abstract interface for all joint dependence mechanisms (D0, D1, D2, D3)."""

    @abstractmethod
    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint uniform copula variates U in [0, 1]^(n_samples x n_flights).

        Must handle arbitrary daily flight count n_flights without assuming fixed dimension.
        """
        ...

    @abstractmethod
    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint arrival delays for one flight day.

        Args:
            marginals: Sequence of length n_flights containing marginal distributions.
            flight_features: pd.DataFrame with strictly pre-cutoff approved columns.
            n_samples: Number of joint Monte Carlo scenarios.
            rng: Seeded generator for reproducibility.

        Returns:
            np.ndarray of shape (n_samples, n_flights) of joint delay samples.
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
        """Unified sampling interface: joint_sampler.sample(marginal_distributions, flight_metadata, rng)."""
        return self.sample_joint(
            marginals=marginal_distributions,
            flight_features=flight_metadata,
            n_samples=n_samples,
            rng=rng,
        )
