"""D2 — Gaussian Copula Joint Dependence Model with Pre-cutoff Covariance Kernel.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 15 (D2)
Specification:
- Constructs pairwise correlation from scheduled departure time proximity and carrier match:
  K(i, j) = (1 - rho_carrier) * exp(-|t_i - t_j|^2 / (2 * tau^2)) + rho_carrier * delta(c_i, c_j)
- Kernel audit verified:
  - Units of time difference: minutes from midnight [0, 1440].
  - tau = 120.0 minutes (temporal length scale).
  - rho_carrier = 0.15 (same carrier correlation).
  - Diagonal behavior: strictly 1.0 (since delta(c_i, c_i)=1 and exp(0)=1).
  - Normalization: bounded in [0, 1].
- Supports arbitrary daily flight count n_flights (no fixed dimension).
- Guarantees PSD via explicit spectral projection with full pre-correction diagnostics and distortion reporting.
- Keeps raw and corrected correlation matrices strictly separate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import ndtr

from src.dependence.base import BaseJointSampler
from src.dependence.psd import (
    MIN_PSD_EIGENVALUE,
    PSDDiagnostic,
    validate_and_project_psd,
)
from src.models.probabilistic.contracts import ProbabilisticContractViolation


class GaussianCopulaJointSampler(BaseJointSampler):
    """D2 — Gaussian copula joint arrival delay sampler."""

    def __init__(
        self,
        *,
        temporal_length_scale_minutes: float = 120.0,
        carrier_correlation: float = 0.15,
        min_eigenvalue: float = MIN_PSD_EIGENVALUE,
    ) -> None:
        super().__init__(name="DEP_D2_gaussian_copula", family="gaussian_copula")
        self.length_scale = float(temporal_length_scale_minutes)
        self.rho_carrier = float(carrier_correlation)
        self.min_eigenvalue = float(min_eigenvalue)

        self.last_raw_matrix: np.ndarray | None = None
        self.last_corrected_matrix: np.ndarray | None = None
        self.last_psd_diagnostic: PSDDiagnostic | None = None

    def construct_correlation_matrices(
        self, flight_features: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, PSDDiagnostic]:
        """Construct raw and corrected PSD correlation matrices for arbitrary daily n.

        Returns:
            (raw_matrix, corrected_matrix, psd_diagnostic)
        """
        n_flights = len(flight_features)
        if n_flights == 0:
            raise ProbabilisticContractViolation("flight_features cannot be empty")

        if n_flights == 1:
            raw_mat = np.ones((1, 1), dtype=np.float64)
            corr_mat, diag = validate_and_project_psd(
                raw_mat, min_eigenvalue=self.min_eigenvalue, is_correlation=True
            )
            self.last_raw_matrix = raw_mat
            self.last_corrected_matrix = corr_mat
            self.last_psd_diagnostic = diag
            return raw_mat, corr_mat, diag

        # Extract departure time in minutes from midnight
        dep_hours = flight_features.get("scheduled_departure_hour")
        if dep_hours is None:
            hours_arr = np.full(n_flights, 12.0, dtype=np.float64)
        else:
            hours_arr = dep_hours.to_numpy(dtype=np.float64)

        dep_mins = flight_features.get("scheduled_departure_minute")
        if dep_mins is None:
            mins_arr = np.zeros(n_flights, dtype=np.float64)
        else:
            mins_arr = dep_mins.to_numpy(dtype=np.float64)

        times_min = hours_arr * 60.0 + mins_arr

        # Extract carrier
        carriers = flight_features.get("OP_CARRIER")
        if carriers is None:
            carrier_arr = np.array(["OTHER"] * n_flights)
        else:
            carrier_arr = carriers.astype(str).to_numpy()

        # 1. RBF Temporal distance kernel: exp(-0.5 * ((t_i - t_j) / tau)^2)
        diff_times = times_min[:, None] - times_min[None, :]
        rbf_temporal = np.exp(-0.5 * (diff_times / self.length_scale) ** 2)

        # 2. Carrier matching kernel: delta(c_i, c_j)
        carrier_match = (carrier_arr[:, None] == carrier_arr[None, :]).astype(np.float64)

        # 3. Composite raw correlation matrix
        raw_corr = (1.0 - self.rho_carrier) * rbf_temporal + self.rho_carrier * carrier_match
        np.fill_diagonal(raw_corr, 1.0)

        # 4. PSD Validation, Diagnostic calculation, and Projection
        corrected_corr, diagnostic = validate_and_project_psd(
            raw_corr,
            min_eigenvalue=self.min_eigenvalue,
            is_correlation=True,
        )

        self.last_raw_matrix = raw_corr
        self.last_corrected_matrix = corrected_corr
        self.last_psd_diagnostic = diagnostic

        return raw_corr, corrected_corr, diagnostic

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample copula variates via multivariate Gaussian with guaranteed PSD correlation."""
        _, corr_mat, _ = self.construct_correlation_matrices(flight_features)
        n_flights = len(flight_features)

        # Cholesky factorization of guaranteed PSD matrix
        try:
            l_mat = np.linalg.cholesky(corr_mat)
        except np.linalg.LinAlgError:
            # High-precision fallback if numerical jitter causes tiny negative eigenvalue
            corr_mat_safe, _ = validate_and_project_psd(
                corr_mat, min_eigenvalue=1e-4, is_correlation=True
            )
            l_mat = np.linalg.cholesky(corr_mat_safe)

        z_iid = rng.standard_normal(size=(n_samples, n_flights))
        z_correlated = z_iid @ l_mat.T

        u = ndtr(z_correlated)
        return np.clip(u, 1e-6, 1.0 - 1e-6)

    def get_last_diagnostic(self) -> PSDDiagnostic | None:
        """Retrieve PSD diagnostic from the most recent correlation construction."""
        return self.last_psd_diagnostic
