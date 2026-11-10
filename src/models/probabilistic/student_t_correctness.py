"""Mathematically Exact Student-T Distribution and Numerical Likelihood Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 3, 4, 7
Features:
1. Numerically stable log[T_nu(b) - T_nu(a)] for extreme tails (no underflow/cancellation).
2. Exact integer quantiles: Q(p) = min{ y in Z : F(y) >= p } = ceil(mu + sigma * t_ppf(p) - 0.5).
3. Exact analytical Student-T CRPS (Jordan, Krueger, Lerch 2019 / Gneiting & Raftery 2007).
4. Consistent discrete event probabilities: P(Y >= k) = 1 - F(k - 1) = T_nu_sf((k - 0.5 - mu) / sigma).
5. Strict parameter guard enforcement (sigma >= sigma_floor, df >= df_floor).
"""

from __future__ import annotations

from typing import Sequence
import numpy as np
from scipy.special import beta as beta_fn
from scipy.stats import t as student_t

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.dependence_interface import MarginalDistributionProtocol
from src.models.probabilistic.likelihood import log1mexp


def log_student_t_diff(
    a: np.ndarray | float,
    b: np.ndarray | float,
    df: np.ndarray | float,
) -> np.ndarray | float:
    """Accurately compute log[T_nu(b) - T_nu(a)] for a < b across all tail regimes.

    Prevents catastrophic cancellation when T_nu(b) ~ T_nu(a) in deep tails.
    """
    is_scalar = np.isscalar(a) and np.isscalar(b) and np.isscalar(df)
    arr_a = np.asarray(a, dtype=np.float64)
    arr_b = np.asarray(b, dtype=np.float64)
    arr_df = np.asarray(df, dtype=np.float64)

    # Broadcast shapes
    arr_a, arr_b, arr_df = np.broadcast_arrays(arr_a, arr_b, arr_df)
    res = np.empty_like(arr_a)

    # Degenerate cases
    invalid = arr_a >= arr_b
    if np.any(invalid):
        res[invalid] = -np.inf

    valid = ~invalid
    if not np.any(valid):
        return float(res.item()) if is_scalar else res

    # 1. Right tail: a >= 0 (both 0 <= a < b)
    # Using survival function sf(x) = 1 - cdf(x):
    # T_nu(b) - T_nu(a) = sf(a) - sf(b) = sf(a) * (1 - exp(logsf(b) - logsf(a)))
    right = valid & (arr_a >= 0.0)
    if np.any(right):
        ar, br, dfr = arr_a[right], arr_b[right], arr_df[right]
        l_sa = student_t.logsf(ar, df=dfr)
        l_sb = student_t.logsf(br, df=dfr)
        delta = np.maximum(l_sa - l_sb, 1e-15)
        res[right] = l_sa + log1mexp(delta)

    # 2. Left tail: b <= 0 (both a < b <= 0)
    # T_nu(b) - T_nu(a) = cdf(b) * (1 - exp(logcdf(a) - logcdf(b)))
    left = valid & (arr_b <= 0.0)
    if np.any(left):
        al, bl, dfl = arr_a[left], arr_b[left], arr_df[left]
        l_cb = student_t.logcdf(bl, df=dfl)
        l_ca = student_t.logcdf(al, df=dfl)
        delta = np.maximum(l_cb - l_ca, 1e-15)
        res[left] = l_cb + log1mexp(delta)

    # 3. Straddle regime: a < 0 < b
    mid = valid & (arr_a < 0.0) & (arr_b > 0.0)
    if np.any(mid):
        am, bm, dfm = arr_a[mid], arr_b[mid], arr_df[mid]
        diff = student_t.cdf(bm, df=dfm) - student_t.cdf(am, df=dfm)
        safe = diff > 1e-7
        mid_res = np.empty_like(am)
        if np.any(safe):
            mid_res[safe] = np.log(np.maximum(diff[safe], 1e-300))
        if np.any(~safe):
            l_cb = student_t.logcdf(bm[~safe], df=dfm[~safe])
            l_ca = student_t.logcdf(am[~safe], df=dfm[~safe])
            delta = np.maximum(l_cb - l_ca, 1e-15)
            mid_res[~safe] = l_cb + log1mexp(delta)
        res[mid] = mid_res

    if is_scalar:
        return float(res.item())
    return res


def analytical_student_t_crps(
    y: np.ndarray | float,
    mu: np.ndarray | float,
    sigma: np.ndarray | float,
    df: np.ndarray | float,
) -> np.ndarray | float:
    """Exact analytical Continuous Ranked Probability Score for Student-T distribution.

    Reference: Jordan, Krueger, Lerch (2019), 'Evaluating Probabilistic Forecasts with scoringRules'.
    Requires df > 1 for finite first moment.
    """
    is_scalar = np.isscalar(y) and np.isscalar(mu) and np.isscalar(sigma) and np.isscalar(df)
    arr_y = np.asarray(y, dtype=np.float64)
    arr_m = np.asarray(mu, dtype=np.float64)
    arr_s = np.asarray(sigma, dtype=np.float64)
    arr_d = np.maximum(np.asarray(df, dtype=np.float64), 1.0001)

    arr_y, arr_m, arr_s, arr_d = np.broadcast_arrays(arr_y, arr_m, arr_s, arr_d)

    arr_s = np.maximum(arr_s, 1e-6)
    z = (arr_y - arr_m) / arr_s
    fz = student_t.pdf(z, df=arr_d)
    Fz = student_t.cdf(z, df=arr_d)

    term1 = z * (2.0 * Fz - 1.0)
    term2 = 2.0 * fz * (arr_d + z**2) / (arr_d - 1.0)
    term3 = (2.0 * np.sqrt(arr_d) / (arr_d - 1.0)) * beta_fn(0.5, arr_d - 0.5) / (beta_fn(0.5, arr_d / 2.0) ** 2)

    crps = arr_s * (term1 + term2 - term3)
    res = np.maximum(crps, 0.0)

    if is_scalar:
        return float(res.item())
    return res


class StudentTDistribution:
    """Parametric Student-t predictive distribution with verified discrete & continuous interfaces."""

    def __init__(
        self,
        mu: float,
        sigma: float,
        df: float,
        *,
        discrete: bool = True,
        sigma_floor: float = DEFAULT_SIGMA_FLOOR,
        df_floor: float = 2.1,
    ) -> None:
        self.mu = float(mu)
        self.sigma_floor = float(sigma_floor)
        self.df_floor = float(df_floor)

        if sigma < self.sigma_floor - 1e-7:
            raise ValueError(f"sigma must be strictly >= sigma_floor ({self.sigma_floor}), got {sigma}")
        self.sigma = float(max(sigma, self.sigma_floor))

        if df < self.df_floor - 1e-7:
            raise ValueError(f"degrees of freedom df must be strictly >= df_floor ({self.df_floor}), got {df}")
        self.df = float(max(df, self.df_floor))

        self.discrete = discrete

    def cdf(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate non-decreasing CDF: F(y) = P(Y <= y)."""
        is_scalar = np.isscalar(y)
        arr = np.asarray(y, dtype=np.float64)

        if self.discrete:
            # Discrete integer arrival: F(y) = P(Y <= y) = T_nu((y + 0.5 - mu) / sigma)
            z = (arr + 0.5 - self.mu) / self.sigma
        else:
            # Continuous arrival: F(y) = T_nu((y - mu) / sigma)
            z = (arr - self.mu) / self.sigma

        res = student_t.cdf(z, df=self.df)
        if is_scalar:
            return float(res.item()) if hasattr(res, "item") else float(res)
        return res

    def log_prob(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate log P(Y=y) (discrete) or log p(y) (continuous)."""
        is_scalar = np.isscalar(y)
        arr = np.asarray(y, dtype=np.float64)

        if self.discrete:
            a = (arr - 0.5 - self.mu) / self.sigma
            b = (arr + 0.5 - self.mu) / self.sigma
            res = log_student_t_diff(a, b, self.df)
        else:
            z = (arr - self.mu) / self.sigma
            res = student_t.logpdf(z, df=self.df) - np.log(self.sigma)

        if is_scalar:
            return float(res.item()) if hasattr(res, "item") else float(res)
        return res

    def prob(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate PMF P(Y=y) or PDF p(y)."""
        return np.exp(self.log_prob(y))

    def quantile(self, p: np.ndarray | float) -> np.ndarray | float | int:
        """Evaluate exact quantile function Q(p).

        For discrete: Q(p) = min{ y in Z : F(y) >= p } = ceil(mu + sigma * T_nu^-1(p) - 0.5).
        For continuous: Q(p) = mu + sigma * T_nu^-1(p).
        """
        is_scalar = np.isscalar(p)
        arr_p = np.clip(np.asarray(p, dtype=np.float64), 1e-12, 1.0 - 1e-12)
        z = student_t.ppf(arr_p, df=self.df)

        if self.discrete:
            # Exact integer minimum: ceil(mu + sigma * z - 0.5)
            res = np.ceil(self.mu + self.sigma * z - 0.5).astype(np.int64)
            if is_scalar:
                return int(res.item()) if hasattr(res, "item") else int(res)
            return res

        res_cont = self.mu + self.sigma * z
        if is_scalar:
            return float(res_cont.item()) if hasattr(res_cont, "item") else float(res_cont)
        return res_cont

    def event_prob(self, threshold: float | int) -> float:
        """Evaluate event probability P(Y >= threshold) consistently with CDF."""
        k = float(threshold)
        if self.discrete:
            # P(Y >= k) = 1 - P(Y <= k - 1) = 1 - F(k - 1) = sf((k - 0.5 - mu) / sigma)
            z = (k - 0.5 - self.mu) / self.sigma
        else:
            # Continuous: P(Y >= k) = 1 - F(k) = sf((k - mu) / sigma)
            z = (k - self.mu) / self.sigma

        return float(student_t.sf(z, df=self.df))

    def sample(self, n_samples: int, rng: np.random.Generator | None = None) -> np.ndarray:
        """Sample from the Student-t predictive distribution."""
        if rng is None:
            rng = np.random.default_rng()

        z = rng.standard_t(df=self.df, size=n_samples)
        cont_draws = self.mu + self.sigma * z
        if self.discrete:
            # Discrete integer sampling rounds continuous location to nearest integer
            return np.rint(cont_draws).astype(np.int64)
        return cont_draws

    def crps(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate exact analytical Student-T CRPS."""
        return analytical_student_t_crps(y, self.mu, self.sigma, self.df)
