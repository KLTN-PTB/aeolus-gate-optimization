"""Concrete implementations of joint dependence models for complete system candidates.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16, 17
Dependence candidate families:
- D0: Independent baseline (mandatory control)
- D1: Scenario / schedule-block dependence (conditioned strictly on pre-cutoff covariates)
- D2: Gaussian copula (pre-cutoff spatial/temporal kernel + PSD guarantee)
- D3: Tail-dependent Student-T copula (conditionally opened on development co-exceedance failure of D2)

Requirements:
1. Arbitrary daily flight count n_d supported (no fixed n x n matrix assumption).
2. Conditioning strictly restricted to pre-cutoff schedule covariates known by T-2h.
3. Zero conditioning on realized delays, cancellations, ATC, or actual weather.
4. Positive semi-definiteness (PSD) guaranteed for all correlation/covariance constructions.
5. Discrete randomized PIT with locked seed control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import norm, t as student_t

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.correctness import GaussianMixtureDistribution
from src.models.probabilistic.dependence_interface import (
    DayFlightBatch,
    DiscretePITPolicy,
    JointDependenceModel,
    MarginalDistributionProtocol,
    MIN_PSD_EIGENVALUE,
    PSDPolicy,
)


# =============================================================================
# Parametric Student-T Marginal Distribution Wrapper (for B5)
# =============================================================================

class StudentTMarginalDistribution:
    """Parametric Student-t distribution implementing MarginalDistributionProtocol."""

    def __init__(
        self,
        mu: float,
        sigma: float,
        df: float,
        *,
        discrete: bool = True,
        sigma_floor: float = DEFAULT_SIGMA_FLOOR,
    ) -> None:
        self.mu = float(mu)
        self.sigma = max(float(sigma), float(sigma_floor))
        self.df = max(float(df), 2.1)  # Variance exists for df > 2
        self.discrete = discrete

    def cdf(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate Student-t CDF at y."""
        is_scalar = np.isscalar(y)
        arr = np.asarray(y, dtype=np.float64)
        if self.discrete:
            z = (arr + 0.5 - self.mu) / self.sigma
        else:
            z = (arr - self.mu) / self.sigma
        res = student_t.cdf(z, df=self.df)
        if is_scalar:
            return float(res.item())
        return res

    def quantile(self, p: np.ndarray | float) -> np.ndarray | float | int:
        """Evaluate Student-t quantile function Q(p)."""
        is_scalar = np.isscalar(p)
        arr_p = np.clip(np.asarray(p, dtype=np.float64), 1e-6, 1.0 - 1e-6)
        z = student_t.ppf(arr_p, df=self.df)
        if self.discrete:
            # Exact integer minimum: ceil(mu + sigma * z - 0.5)
            res = np.ceil(self.mu + self.sigma * z - 0.5).astype(int)
        else:
            res = self.mu + self.sigma * z
        if is_scalar:
            return int(res.item()) if hasattr(res, "item") else int(res)
        return res

    def sample(self, n_samples: int, rng: np.random.Generator | None = None) -> np.ndarray:
        """Sample from the Student-t distribution."""
        if rng is None:
            rng = np.random.default_rng()
        z = rng.standard_t(df=self.df, size=n_samples)
        raw = self.mu + self.sigma * z
        if self.discrete:
            return np.round(raw).astype(int)
        return raw


class FrozenQuantileDistribution:
    """Marginal predictive distribution backed by frozen pre-computed quantiles."""

    def __init__(self, q_dict: dict[float, float], *, discrete: bool = True) -> None:
        self.alphas = np.array(sorted(q_dict.keys()), dtype=np.float64)
        self.q_vals = np.array([float(q_dict[a]) for a in self.alphas], dtype=np.float64)
        self.discrete = discrete

    def quantile(self, p: np.ndarray | float) -> np.ndarray | float | int:
        """Evaluate quantile function Q(p) via linear interpolation on frozen quantiles."""
        is_scalar = np.isscalar(p)
        arr_p = np.clip(np.asarray(p, dtype=np.float64), 1e-5, 1.0 - 1e-5)
        res = np.interp(arr_p, self.alphas, self.q_vals)
        if self.discrete:
            res = np.round(res).astype(int)
        if is_scalar:
            return res.item()
        return res

    def cdf(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate CDF at y via inverse linear interpolation."""
        is_scalar = np.isscalar(y)
        arr_y = np.asarray(y, dtype=np.float64)
        res = np.interp(arr_y, self.q_vals, self.alphas)
        if is_scalar:
            return float(res.item())
        return res

    def sample(self, n_samples: int, rng: np.random.Generator | None = None) -> np.ndarray:
        """Sample from the distribution."""
        if rng is None:
            rng = np.random.default_rng()
        u = rng.uniform(1e-5, 1.0 - 1e-5, size=n_samples)
        return self.quantile(u)


# =============================================================================
# D0: Independent Baseline Dependence Model
# =============================================================================

class IndependentDependenceModel(JointDependenceModel):
    """D0 — Independent sampling from marginal predictive distributions.

    Mandatory baseline to prove whether joint dependence structure adds value.
    """

    def __init__(self) -> None:
        self.name = "DEP_D0_independent"
        self.family = "independent"

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample independent uniform copula variates U ~ Uniform(0, 1)^(n_samples x n_flights)."""
        n_flights = len(flight_features)
        return rng.uniform(1e-6, 1.0 - 1e-6, size=(n_samples, n_flights))

    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint arrival delays independently per flight."""
        n_flights = len(flight_features)
        if len(marginals) != n_flights:
            raise ProbabilisticContractViolation("Length of marginals must match flight_features count")

        u = self.sample_copula(flight_features, n_samples, rng)
        y_samples = np.empty((n_samples, n_flights), dtype=np.float64)
        for i in range(n_flights):
            y_samples[:, i] = marginals[i].quantile(u[:, i])
        return y_samples


# =============================================================================
# D1: Scenario / Block Dependence Model
# =============================================================================

class ScenarioBlockDependenceModel(JointDependenceModel):
    """D1 — Scenario / schedule-block dependence.

    Conditioned strictly on pre-cutoff covariates known by T-2h:
    - Schedule time block: Morning (00:00-11:59), Afternoon (12:00-17:59), Evening (18:00-23:59).
    - Carrier category: Mainline vs Regional.
    - Day-level common factor + block-level common factor + idiosyncratic shock.

    Guarantees valid exchangeable joint distribution for arbitrary daily n_flights.
    """

    def __init__(
        self,
        *,
        day_factor_weight: float = 0.20,
        block_factor_weight: float = 0.25,
    ) -> None:
        self.name = "DEP_D1_scenario_block"
        self.family = "scenario_block"
        self.day_factor_weight = float(day_factor_weight)
        self.block_factor_weight = float(block_factor_weight)

        total_weight = self.day_factor_weight**2 + self.block_factor_weight**2
        if total_weight >= 1.0:
            raise ProbabilisticContractViolation("Sum of squared factor weights must be < 1.0")
        self.idiosyncratic_weight = float(np.sqrt(1.0 - total_weight))

    def _assign_schedule_blocks(self, flight_features: pd.DataFrame) -> list[str]:
        """Assign each flight to a pre-cutoff schedule block."""
        blocks = []
        for _, row in flight_features.iterrows():
            dep_hour = int(row.get("scheduled_departure_hour", 12))
            carrier = str(row.get("OP_CARRIER", "OTHER")).strip()

            if dep_hour < 12:
                time_block = "MORN"
            elif dep_hour < 18:
                time_block = "AFTN"
            else:
                time_block = "EVEN"

            carrier_tier = "MAIN" if carrier in {"AA", "DL", "UA", "WN"} else "REG"
            blocks.append(f"{time_block}_{carrier_tier}")
        return blocks

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample copula variates via hierarchical latent schedule-block factors."""
        n_flights = len(flight_features)
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

        # Map block factors to flights
        flight_block_indices = np.array([block_to_idx[b] for b in blocks], dtype=int)
        z_block_mapped = z_block[:, flight_block_indices]

        # Combine into standard normal latent variables
        z_total = (
            self.day_factor_weight * z_day
            + self.block_factor_weight * z_block_mapped
            + self.idiosyncratic_weight * z_idio
        )

        # Transform to uniform copula coordinates via standard normal CDF
        u = norm.cdf(z_total)
        return np.clip(u, 1e-6, 1.0 - 1e-6)

    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint arrival delays under block dependence."""
        n_flights = len(flight_features)
        if len(marginals) != n_flights:
            raise ProbabilisticContractViolation("Length of marginals must match flight_features count")

        u = self.sample_copula(flight_features, n_samples, rng)
        y_samples = np.empty((n_samples, n_flights), dtype=np.float64)
        for i in range(n_flights):
            y_samples[:, i] = marginals[i].quantile(u[:, i])
        return y_samples


# =============================================================================
# D2: Gaussian Copula with Pre-cutoff Covariance Kernel
# =============================================================================

class GaussianCopulaDependenceModel(JointDependenceModel):
    """D2 — Gaussian copula with pre-cutoff correlation kernel.

    Constructs pairwise correlation from scheduled departure time proximity and carrier match:
    K(i, j) = (1 - rho_carrier) * exp(-|t_i - t_j|^2 / (2 * length_scale^2)) + rho_carrier * delta(c_i, c_j)

    Guarantees PSD for arbitrary daily n_flights via PSDPolicy projection.
    """

    def __init__(
        self,
        *,
        temporal_length_scale_minutes: float = 120.0,
        carrier_correlation: float = 0.15,
        min_eigenvalue: float = MIN_PSD_EIGENVALUE,
    ) -> None:
        self.name = "DEP_D2_gaussian_copula"
        self.family = "gaussian_copula"
        self.length_scale = float(temporal_length_scale_minutes)
        self.rho_carrier = float(carrier_correlation)
        self.min_eigenvalue = float(min_eigenvalue)
        self.last_raw_matrix: np.ndarray | None = None
        self.last_corrected_matrix: np.ndarray | None = None
        self.last_psd_diagnostic: Any = None

    def construct_correlation_matrix(self, flight_features: pd.DataFrame) -> np.ndarray:
        """Construct guaranteed PSD correlation matrix from pre-cutoff features."""
        n_flights = len(flight_features)
        if n_flights <= 0:
            raise ProbabilisticContractViolation(
                f"flight_features cannot be empty (n_flights={n_flights} must be >= 1)"
            )
        if n_flights == 1:
            raw = np.ones((1, 1), dtype=np.float64)
            corr, diag = PSDPolicy.validate_with_diagnostics(
                raw, min_eigenvalue=self.min_eigenvalue, is_correlation=True
            )
            self.last_raw_matrix = raw
            self.last_corrected_matrix = corr
            self.last_psd_diagnostic = diag
            return corr

        dep_hours = flight_features["scheduled_departure_hour"].to_numpy(dtype=np.float64)
        dep_mins = flight_features.get("scheduled_departure_minute", 0)
        if isinstance(dep_mins, pd.Series):
            dep_mins = dep_mins.to_numpy(dtype=np.float64)
        else:
            dep_mins = np.zeros(n_flights, dtype=np.float64)

        times_min = dep_hours * 60.0 + dep_mins
        carriers = flight_features["OP_CARRIER"].astype(str).to_numpy()

        # Compute temporal distance matrix
        diff_times = times_min[:, None] - times_min[None, :]
        rbf_temporal = np.exp(-0.5 * (diff_times / self.length_scale) ** 2)

        # Carrier matching matrix
        carrier_match = (carriers[:, None] == carriers[None, :]).astype(np.float64)

        # Combined correlation matrix
        raw_corr = (1.0 - self.rho_carrier) * rbf_temporal + self.rho_carrier * carrier_match
        np.fill_diagonal(raw_corr, 1.0)

        # Guarantee Positive Semi-Definiteness and record separate diagnostic
        corr, diagnostic = PSDPolicy.validate_with_diagnostics(
            raw_corr, min_eigenvalue=self.min_eigenvalue, is_correlation=True
        )
        self.last_raw_matrix = raw_corr
        self.last_corrected_matrix = corr
        self.last_psd_diagnostic = diagnostic
        return corr

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample copula variates via multivariate Gaussian with guaranteed PSD correlation."""
        corr = self.construct_correlation_matrix(flight_features)
        n_flights = len(flight_features)

        # Cholesky decomposition of guaranteed PSD matrix
        try:
            l_mat = np.linalg.cholesky(corr)
        except np.linalg.LinAlgError:
            # Fallback projection if numerical precision causes tiny negative eigenvalue
            corr_reg = PSDPolicy.ensure_psd(corr, min_eigenvalue=1e-4, is_correlation=True)
            l_mat = np.linalg.cholesky(corr_reg)

        z_iid = rng.standard_normal(size=(n_samples, n_flights))
        z_correlated = z_iid @ l_mat.T

        u = norm.cdf(z_correlated)
        return np.clip(u, 1e-6, 1.0 - 1e-6)

    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint arrival delays under Gaussian copula."""
        n_flights = len(flight_features)
        if len(marginals) != n_flights:
            raise ProbabilisticContractViolation("Length of marginals must match flight_features count")

        u = self.sample_copula(flight_features, n_samples, rng)
        y_samples = np.empty((n_samples, n_flights), dtype=np.float64)
        for i in range(n_flights):
            y_samples[:, i] = marginals[i].quantile(u[:, i])
        return y_samples


# =============================================================================
# D3: Tail-Dependent Copula Model (Student-T Copula)
# =============================================================================

class TailDependentCopulaModel(JointDependenceModel):
    """D3 — Tail-dependent Student-T copula.

    Latent structure:
    Z ~ N(0, Sigma)
    W ~ Chi2(nu) / nu
    T = Z / sqrt(W) ~ t_nu(0, Sigma)
    U_i = F_{t, nu}(T_i)

    Generates strictly positive upper and lower tail dependence lambda > 0.
    Conditionally opened ONLY when pre-registered evidence gate confirms D2 tail co-exceedance failure.
    """

    def __init__(
        self,
        *,
        degrees_of_freedom: float = 6.0,
        temporal_length_scale_minutes: float = 120.0,
        carrier_correlation: float = 0.15,
        min_eigenvalue: float = MIN_PSD_EIGENVALUE,
    ) -> None:
        self.name = "DEP_D3_tail_copula"
        self.family = "tail_copula"
        self.nu = max(float(degrees_of_freedom), 3.0)
        self.length_scale = float(temporal_length_scale_minutes)
        self.rho_carrier = float(carrier_correlation)
        self.min_eigenvalue = float(min_eigenvalue)

    def construct_correlation_matrix(self, flight_features: pd.DataFrame) -> np.ndarray:
        """Construct guaranteed PSD correlation matrix."""
        n_flights = len(flight_features)
        if n_flights <= 0:
            raise ProbabilisticContractViolation(
                f"flight_features cannot be empty (n_flights={n_flights} must be >= 1)"
            )
        if n_flights == 1:
            return np.ones((1, 1), dtype=np.float64)

        dep_hours = flight_features["scheduled_departure_hour"].to_numpy(dtype=np.float64)
        dep_mins = flight_features.get("scheduled_departure_minute", 0)
        if isinstance(dep_mins, pd.Series):
            dep_mins = dep_mins.to_numpy(dtype=np.float64)
        else:
            dep_mins = np.zeros(n_flights, dtype=np.float64)

        times_min = dep_hours * 60.0 + dep_mins
        carriers = flight_features["OP_CARRIER"].astype(str).to_numpy()

        diff_times = times_min[:, None] - times_min[None, :]
        rbf_temporal = np.exp(-0.5 * (diff_times / self.length_scale) ** 2)
        carrier_match = (carriers[:, None] == carriers[None, :]).astype(np.float64)
        corr = (1.0 - self.rho_carrier) * rbf_temporal + self.rho_carrier * carrier_match

        return PSDPolicy.ensure_psd(corr, min_eigenvalue=self.min_eigenvalue, is_correlation=True)

    def sample_copula(
        self,
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample copula variates via multivariate Student-T with common scaling shock."""
        corr = self.construct_correlation_matrix(flight_features)
        n_flights = len(flight_features)

        try:
            l_mat = np.linalg.cholesky(corr)
        except np.linalg.LinAlgError:
            corr_reg = PSDPolicy.ensure_psd(corr, min_eigenvalue=1e-4, is_correlation=True)
            l_mat = np.linalg.cholesky(corr_reg)

        z_correlated = rng.standard_normal(size=(n_samples, n_flights)) @ l_mat.T

        # Common chi-square shock per scenario: shape (n_samples, 1)
        w = rng.chisquare(df=self.nu, size=(n_samples, 1)) / self.nu
        t_variates = z_correlated / np.sqrt(w)

        u = student_t.cdf(t_variates, df=self.nu)
        return np.clip(u, 1e-6, 1.0 - 1e-6)

    def sample_joint(
        self,
        marginals: Sequence[MarginalDistributionProtocol],
        flight_features: pd.DataFrame,
        n_samples: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Sample joint arrival delays under tail-dependent Student-T copula."""
        n_flights = len(flight_features)
        if len(marginals) != n_flights:
            raise ProbabilisticContractViolation("Length of marginals must match flight_features count")

        u = self.sample_copula(flight_features, n_samples, rng)
        y_samples = np.empty((n_samples, n_flights), dtype=np.float64)
        for i in range(n_flights):
            y_samples[:, i] = marginals[i].quantile(u[:, i])
        return y_samples


# =============================================================================
# Pre-Registered Evidence Gate for D3 (Tail Copula)
# =============================================================================

@dataclass(frozen=True)
class TailCopulaGateResult:
    """Outcome of pre-registered diagnostic gate determining whether D3 is opened."""

    empirical_co_exceedance_q90: float
    d2_simulated_co_exceedance_q90: float
    co_exceedance_deficit: float
    deficit_threshold: float
    d3_tail_copula_opened: bool
    diagnostic_rationale: str


def evaluate_tail_copula_evidence_gate(
    historical_pairs_both_ge60: int,
    total_eligible_pairs: int,
    d2_expected_pairs_ge60: float,
    *,
    deficit_threshold: float = 0.005,
) -> TailCopulaGateResult:
    """Evaluate pre-registered diagnostic evidence gate for conditionally opening D3.

    Rule from dependence_candidate_manifest_v1.json:
    - Compute empirical probability of joint severe delay co-exceedance on development data.
    - If empirical co-exceedance exceeds D2 (Gaussian copula) prediction by > deficit_threshold (0.005),
      then D2 has proven tail co-exceedance failure, and D3 is OPENED.
    - Otherwise, D3 remains CLOSED to prevent unconstrained hypothesis expansion.
    """
    p_emp = float(historical_pairs_both_ge60 / max(total_eligible_pairs, 1))
    p_d2 = float(d2_expected_pairs_ge60 / max(total_eligible_pairs, 1))
    deficit = float(p_emp - p_d2)

    opened = bool(deficit > deficit_threshold)
    if opened:
        rationale = (
            f"D3 Tail Copula is OPENED: Empirical development severe delay co-exceedance ({p_emp:.4f}) "
            f"exceeds Gaussian copula expectation ({p_d2:.4f}) by {deficit:.4f} > threshold {deficit_threshold:.4f}."
        )
    else:
        rationale = (
            f"D3 Tail Copula remains CLOSED: Empirical development co-exceedance ({p_emp:.4f}) "
            f"is adequately modeled by Gaussian copula ({p_d2:.4f}), deficit {deficit:.4f} <= threshold {deficit_threshold:.4f}."
        )

    return TailCopulaGateResult(
        empirical_co_exceedance_q90=p_emp,
        d2_simulated_co_exceedance_q90=p_d2,
        co_exceedance_deficit=deficit,
        deficit_threshold=deficit_threshold,
        d3_tail_copula_opened=opened,
        diagnostic_rationale=rationale,
    )
