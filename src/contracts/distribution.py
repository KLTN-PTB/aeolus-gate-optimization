"""Common Distribution Contract and Predictive Distribution Implementations for Aeolus.

Protocol: Phase 4 Common Distribution Contract
Scope:
- PredictiveDistribution abstract base interface
- Standard batch query operations: mean(), median(), quantile(q), cdf(x), probability_ge(threshold), sample(n, seed)
- Strict fail-closed numerical safety validation
- Zero heuristic CDF synthesis for models lacking native CDF
- Specialized distribution adapters for:
  1. Empirical
  2. XGBoost Residual Gaussian
  3. NGBoost Normal
  4. NGBoost Student-T
  5. Quantile Regression
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
from scipy.special import ndtr
from scipy.stats import norm, t as student_t

from src.models.probabilistic.contracts import DEFAULT_SIGMA_FLOOR
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
)


class DistributionError(Exception):
    """Base exception for distribution contract errors."""
    pass


class CapabilityNotSupportedError(DistributionError):
    """Raised when an unsupported distributional query is invoked."""
    pass


class DistributionValidationError(DistributionError, ValueError):
    """Raised when numerical safety validation detects invalid/non-finite values."""
    pass


class CallableArray(np.ndarray):
    """ndarray that behaves both as a standard array and a nullary callable returning itself."""

    def __new__(cls, input_array: Any) -> CallableArray:
        obj = np.asarray(input_array, dtype=np.float64).view(cls)
        return obj

    def __call__(self, *args: Any, **kwargs: Any) -> CallableArray:
        return self


class CallableDict(dict):
    """Dictionary that behaves both as a standard dict and a nullary callable returning itself."""

    def __call__(self, *args: Any, **kwargs: Any) -> CallableDict:
        return self


class hybrid_contract_property:
    """Descriptor that allows method to be accessed both as an attribute and a nullary method."""

    def __init__(
        self,
        func: Callable[[Any], Any],
        fset: Callable[[Any, Any], None] | None = None,
    ) -> None:
        self.func = func
        self.fset = fset
        self.__doc__ = func.__doc__

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        if instance is None:
            return self
        return self.func(instance)

    def __set__(self, instance: Any, value: Any) -> None:
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(instance, value)

    def setter(self, fset: Callable[[Any, Any], None]) -> hybrid_contract_property:
        return hybrid_contract_property(self.func, fset)


class DistributionCapabilities(CallableDict):
    """Explicit, immutable capability declaration for PredictiveDistribution.

    Enforces that capability accounting is declared rather than inferred from method presence.
    """

    REQUIRED_CAPABILITIES: Final[tuple[str, ...]] = (
        "mean",
        "median",
        "quantile",
        "cdf",
        "probability_ge",
        "sample",
        "nll",
        "crps_exact",
        "crps_approx",
        "pit",
    )

    def __init__(
        self,
        mean: bool = False,
        median: bool = False,
        quantile: bool = False,
        cdf: bool = False,
        probability_ge: bool = False,
        sample: bool = False,
        nll: bool = False,
        crps_exact: bool = False,
        crps_approx: bool = False,
        pit: bool = False,
        **extra: Any,
    ) -> None:
        super().__init__()
        # Handle aliases passed as kwargs
        if "has_mean" in extra:
            mean = extra.pop("has_mean")
        if "has_median" in extra:
            median = extra.pop("has_median")
        if "has_quantiles" in extra:
            quantile = extra.pop("has_quantiles")
        if "has_cdf" in extra:
            cdf = extra.pop("has_cdf")
        if "has_probability_ge" in extra or "has_p_delay_ge_15" in extra:
            probability_ge = extra.pop("has_probability_ge", extra.pop("has_p_delay_ge_15", probability_ge))
        if "has_sampler" in extra or "has_sample" in extra:
            sample = extra.pop("has_sampler", extra.pop("has_sample", sample))
        if "has_nll" in extra:
            nll = extra.pop("has_nll")
        if "has_crps_exact" in extra:
            crps_exact = extra.pop("has_crps_exact")
        if "has_crps_approx" in extra:
            crps_approx = extra.pop("has_crps_approx")
        if "has_pit" in extra:
            pit = extra.pop("has_pit")

        # 1. Canonical capability fields
        self["mean"] = bool(mean)
        self["median"] = bool(median)
        self["quantile"] = bool(quantile)
        self["cdf"] = bool(cdf)
        self["probability_ge"] = bool(probability_ge)
        self["sample"] = bool(sample)
        self["nll"] = bool(nll)
        self["crps_exact"] = bool(crps_exact)
        self["crps_approx"] = bool(crps_approx)
        self["pit"] = bool(pit)

        # 2. Backwards-compatibility aliases
        self["has_mean"] = bool(mean)
        self["has_median"] = bool(median)
        self["has_quantiles"] = bool(quantile)
        self["has_cdf"] = bool(cdf)
        self["has_probability_ge"] = bool(probability_ge)
        self["has_p_delay_ge_15"] = bool(probability_ge)
        self["has_sampler"] = bool(sample)
        self["has_sample"] = bool(sample)
        self["has_nll"] = bool(nll)
        self["has_crps"] = bool(crps_exact or crps_approx)
        self["has_crps_exact"] = bool(crps_exact)
        self["has_crps_approx"] = bool(crps_approx)
        self["has_pit"] = bool(pit)

        for k, v in extra.items():
            self[k] = v

    def supports(self, capability: str) -> bool:
        """Check whether a specific capability is supported."""
        key = capability.lower()
        if key.startswith("has_"):
            key = key[4:]
        if key == "quantiles":
            key = "quantile"
        if key == "sampler":
            key = "sample"
        return bool(self.get(key, False))

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        raise AttributeError(f"'DistributionCapabilities' object has no attribute '{name}'")


class PredictiveDistribution(ABC):
    """Abstract Base Contract for all predictive distributions in Aeolus.

    Enforces batch evaluation, explicit capability accounting, and strict numerical safety.
    """

    @hybrid_contract_property
    @abstractmethod
    def mean(self) -> CallableArray:
        """Expected value E[Y] per flight. Shape: (N,).

        Raises CapabilityNotSupportedError if candidate does not support conditional expectation.
        """
        ...

    @hybrid_contract_property
    @abstractmethod
    def median(self) -> CallableArray:
        """Median Q(0.50) per flight. Shape: (N,)."""
        ...

    @abstractmethod
    def quantile(self, q: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Evaluate quantile function Q(alpha) for alpha in (0, 1).

        Batch form:
        - If q is scalar float: returns (N,) array.
        - If q is Sequence/ndarray of length K: returns (K, N) array.
        """
        ...

    @abstractmethod
    def cdf(self, x: float | np.ndarray) -> np.ndarray:
        """Evaluate Cumulative Distribution Function F(x) = P(Y <= x).

        Batch form:
        - If x is scalar float: returns (N,) array.
        - If x is 1D array of shape (N,): pointwise evaluation out[i] = F_i(x_i).
        - If x is 1D array of shape (M,) with M != N: grid evaluation out[m, i] = F_i(x[m]).

        Raises CapabilityNotSupportedError if candidate does not support continuous CDF.
        """
        ...

    @abstractmethod
    def probability_ge(self, threshold: float | np.ndarray = 15.0) -> np.ndarray:
        """Event probability P(Y >= threshold) per flight. Shape: (N,).

        Raises CapabilityNotSupportedError if candidate does not support event probability.
        """
        ...

    @abstractmethod
    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        """Draw n pseudorandom samples per flight. Shape: (n, N).

        Must be deterministic given a fixed seed.
        Raises CapabilityNotSupportedError if candidate does not support generative sampling.
        """
        ...

    @abstractmethod
    def validate(self) -> None:
        """Perform numerical safety verification.

        Rejects: NaN, Inf, invalid sigma (<= 0), invalid probabilities (< 0 or > 1),
        non-monotonic quantiles, non-monotonic CDF, invalid sample shapes.

        Raises DistributionValidationError on failure (fail-closed).
        """
        ...

    @hybrid_contract_property
    @abstractmethod
    def metadata(self) -> CallableDict:
        """Dictionary containing candidate_id, family, capabilities, and distribution parameters."""
        ...

    @hybrid_contract_property
    @abstractmethod
    def capabilities(self) -> DistributionCapabilities:
        """Explicit capability declaration object declaring supported operations."""
        ...

    # =========================================================================
    # Backwards-compatibility properties and accessors
    # =========================================================================

    @property
    def p_delay_ge_15(self) -> CallableArray:
        """Convenience property for P(delay >= 15)."""
        if hasattr(self, "_override_p_15") and self._override_p_15 is not None:
            return CallableArray(self._override_p_15)
        caps = self.capabilities
        if not caps.supports("probability_ge") and not caps.get("has_p_delay_ge_15", False):
            raise CapabilityNotSupportedError("P(delay >= 15) is not supported for this candidate.")
        return CallableArray(self.probability_ge(15.0))

    @p_delay_ge_15.setter
    def p_delay_ge_15(self, val: np.ndarray) -> None:
        self._override_p_15 = np.asarray(val, dtype=np.float64)

    @property
    def quantiles(self) -> dict[float, np.ndarray]:
        """Convenience property mapping pre-registered alphas to arrays."""
        if not self.capabilities.supports("quantile"):
            raise CapabilityNotSupportedError("Quantile evaluation is not supported for this candidate.")
        return {float(a): self.quantile(a) for a in PRE_REGISTERED_QUANTILES}

    @property
    def sampler(self) -> Callable[[int, int | None], np.ndarray]:
        """Convenience property returning callable sample(n, seed)."""
        if not self.capabilities.supports("sample"):
            raise CapabilityNotSupportedError("Sampling is not supported for this candidate.")
        return self.sample

    @property
    def cdf_func(self) -> Callable[[float | np.ndarray], np.ndarray]:
        """Convenience property returning cdf callable."""
        if not self.capabilities.supports("cdf"):
            raise CapabilityNotSupportedError("CDF evaluation is not supported for this candidate.")
        return self.cdf

    @property
    def dist_params(self) -> dict[str, Any]:
        """Convenience property returning distribution parameters."""
        return self.metadata.get("dist_params", {})

    def validate_finite(self) -> list[str]:
        """Legacy helper for test compatibility returning list of issues."""
        try:
            self.validate()
            return []
        except DistributionValidationError as exc:
            return [str(exc)]


# Alias for backwards compatibility with Phase 3 tests
ProbabilisticPrediction = PredictiveDistribution


# =============================================================================
# ADAPTER 1: Empirical Distribution
# =============================================================================

class EmpiricalDistribution(PredictiveDistribution):
    """Empirical distribution adapter based on carrier x scheduled-hour grouping."""

    def __init__(
        self,
        mean_vals: np.ndarray,
        median_vals: np.ndarray,
        quantiles_dict: dict[float, np.ndarray],
        p_ge_15_vals: np.ndarray,
        sample_pool_list: list[np.ndarray],
        metadata_dict: dict[str, Any] | None = None,
    ) -> None:
        self._mean = np.asarray(mean_vals, dtype=np.float64)
        self._median = np.asarray(median_vals, dtype=np.float64)
        self._quantiles = {float(k): np.asarray(v, dtype=np.float64) for k, v in quantiles_dict.items()}
        self._p_ge_15 = np.asarray(p_ge_15_vals, dtype=np.float64)
        self._sample_pools = sample_pool_list
        self._n_flights = len(self._median)
        self._metadata = metadata_dict or {}

    @hybrid_contract_property
    def mean(self) -> CallableArray:
        return CallableArray(self._mean)

    @hybrid_contract_property
    def median(self) -> CallableArray:
        return CallableArray(self._median)

    def quantile(self, q: float | Sequence[float] | np.ndarray) -> np.ndarray:
        if np.isscalar(q):
            alpha = float(q)
            if not 0.0 < alpha < 1.0:
                raise ValueError(f"Quantile alpha must be in (0, 1), got {alpha}")
            if alpha in self._quantiles:
                return CallableArray(self._quantiles[alpha])
            # Empirical quantile from sample pools
            res = np.array([float(np.quantile(pool, alpha)) for pool in self._sample_pools], dtype=np.float64)
            return CallableArray(res)
        else:
            alphas = np.asarray(q, dtype=np.float64)
            if np.any(alphas <= 0.0) or np.any(alphas >= 1.0):
                raise ValueError("All quantile alphas must be strictly in (0, 1)")
            res = np.array([self.quantile(a) for a in alphas], dtype=np.float64)
            return CallableArray(res)

    def cdf(self, x: float | np.ndarray) -> np.ndarray:
        if np.isscalar(x):
            val = float(x)
            res = np.array([float(np.mean(pool <= val)) for pool in self._sample_pools], dtype=np.float64)
            return CallableArray(res)
        x_arr = np.asarray(x, dtype=np.float64)
        if x_arr.shape == (self._n_flights,):
            res = np.array([float(np.mean(pool <= x_arr[i])) for i, pool in enumerate(self._sample_pools)], dtype=np.float64)
            return CallableArray(res)
        elif x_arr.ndim == 1:
            out = np.zeros((len(x_arr), self._n_flights), dtype=np.float64)
            for m, xm in enumerate(x_arr):
                out[m] = self.cdf(xm)
            return CallableArray(out)
        else:
            raise ValueError(f"Unsupported CDF input shape: {x_arr.shape}")

    def probability_ge(self, threshold: float | np.ndarray = 15.0) -> np.ndarray:
        if np.isscalar(threshold) and float(threshold) == 15.0:
            return CallableArray(self._p_ge_15)
        if np.isscalar(threshold):
            thr = float(threshold)
            res = np.array([float(np.mean(pool >= thr)) for pool in self._sample_pools], dtype=np.float64)
            return CallableArray(res)
        t_arr = np.asarray(threshold, dtype=np.float64)
        res = np.array([float(np.mean(pool >= t_arr[i])) for i, pool in enumerate(self._sample_pools)], dtype=np.float64)
        return CallableArray(res)

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        if n <= 0:
            raise ValueError(f"Sample size n must be positive, got {n}")
        rng = np.random.default_rng(seed)
        draws = np.zeros((n, self._n_flights), dtype=np.float64)
        for i, pool in enumerate(self._sample_pools):
            draws[:, i] = rng.choice(pool, size=n, replace=True)
        return CallableArray(draws)

    def validate(self) -> None:
        if not np.all(np.isfinite(self._mean)):
            raise DistributionValidationError("Empirical mean contains NaN or Inf.")
        if not np.all(np.isfinite(self._median)):
            raise DistributionValidationError("Empirical median contains NaN or Inf.")
        if np.any(self._p_ge_15 < 0.0) or np.any(self._p_ge_15 > 1.0):
            raise DistributionValidationError("Empirical probability_ge out of [0, 1].")
        for i, pool in enumerate(self._sample_pools):
            if len(pool) == 0:
                raise DistributionValidationError(f"Sample pool at flight {i} is empty.")
            if not np.all(np.isfinite(pool)):
                raise DistributionValidationError(f"Sample pool at flight {i} contains NaN or Inf.")
        sorted_alphas = sorted(self._quantiles.keys())
        for j in range(len(sorted_alphas) - 1):
            a_cur, a_nxt = sorted_alphas[j], sorted_alphas[j + 1]
            if np.any(self._quantiles[a_cur] > self._quantiles[a_nxt] + 1e-6):
                raise DistributionValidationError(
                    f"Quantile monotonicity violated: q({a_cur}) > q({a_nxt})"
                )

    @hybrid_contract_property
    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=True,
            median=True,
            quantile=True,
            cdf=True,
            probability_ge=True,
            sample=True,
            nll=False,
            crps_exact=False,
            crps_approx=True,
            pit=False,
        )

    @hybrid_contract_property
    def metadata(self) -> CallableDict:
        caps = self.capabilities
        res = {
            "candidate_id": self._metadata.get("candidate_id", "P1_empirical"),
            "family": self._metadata.get("family", "empirical"),
            "role": self._metadata.get("role", "EMPIRICAL_RESIDUAL_BASELINE"),
            "capabilities": caps,
            "n_flights": self._n_flights,
        }
        res.update(self._metadata)
        res["capabilities"] = caps
        return CallableDict(res)


# =============================================================================
# ADAPTER 2 & 3: Gaussian Distributions (Residual and Heteroscedastic)
# =============================================================================

class GaussianResidualDistribution(PredictiveDistribution):
    """Gaussian distribution adapter (Analytical Homoscedastic or Heteroscedastic)."""

    def __init__(
        self,
        mu: np.ndarray,
        sigma: float | np.ndarray,
        family: str = "xgb_gaussian_oof",
        candidate_id: str = "P2_xgb_gaussian_oof",
        metadata_dict: dict[str, Any] | None = None,
    ) -> None:
        self._mu = np.asarray(mu, dtype=np.float64)
        self._n_flights = len(self._mu)
        if np.isscalar(sigma):
            self._sigma = np.full(self._n_flights, float(sigma), dtype=np.float64)
        else:
            self._sigma = np.asarray(sigma, dtype=np.float64)
        self._family = family
        self._candidate_id = candidate_id
        self._metadata = metadata_dict or {}

    @hybrid_contract_property
    def mean(self) -> CallableArray:
        return CallableArray(self._mu)

    @hybrid_contract_property
    def median(self) -> CallableArray:
        return CallableArray(self._mu)

    @median.setter
    def median(self, val: np.ndarray) -> None:
        self._mu = np.asarray(val, dtype=np.float64)

    def quantile(self, q: float | Sequence[float] | np.ndarray) -> np.ndarray:
        if np.isscalar(q):
            alpha = float(q)
            if not 0.0 < alpha < 1.0:
                raise ValueError(f"Quantile alpha must be in (0, 1), got {alpha}")
            res = self._mu + self._sigma * norm.ppf(alpha)
            return CallableArray(res)
        else:
            alphas = np.asarray(q, dtype=np.float64)
            if np.any(alphas <= 0.0) or np.any(alphas >= 1.0):
                raise ValueError("All quantile alphas must be strictly in (0, 1)")
            z = norm.ppf(alphas)
            res = self._mu[np.newaxis, :] + self._sigma[np.newaxis, :] * z[:, np.newaxis]
            return CallableArray(res)

    def cdf(self, x: float | np.ndarray) -> np.ndarray:
        if np.isscalar(x):
            z = (float(x) - self._mu) / self._sigma
            return CallableArray(ndtr(z))
        x_arr = np.asarray(x, dtype=np.float64)
        if x_arr.shape == (self._n_flights,):
            z = (x_arr - self._mu) / self._sigma
            return CallableArray(ndtr(z))
        elif x_arr.ndim == 1:
            z = (x_arr[:, np.newaxis] - self._mu[np.newaxis, :]) / self._sigma[np.newaxis, :]
            return CallableArray(ndtr(z))
        else:
            raise ValueError(f"Unsupported CDF input shape: {x_arr.shape}")

    def probability_ge(self, threshold: float | np.ndarray = 15.0) -> np.ndarray:
        if np.isscalar(threshold) and float(threshold) == 15.0 and hasattr(self, "_override_p_15") and self._override_p_15 is not None:
            return CallableArray(self._override_p_15)
        return CallableArray(np.clip(1.0 - self.cdf(threshold), 0.0, 1.0))

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        if n <= 0:
            raise ValueError(f"Sample size n must be positive, got {n}")
        rng = np.random.default_rng(seed)
        standard_draws = rng.standard_normal(size=(n, self._n_flights))
        res = self._mu[np.newaxis, :] + self._sigma[np.newaxis, :] * standard_draws
        return CallableArray(res)

    def validate(self) -> None:
        if not np.all(np.isfinite(self._mu)):
            raise DistributionValidationError("Gaussian mu contains NaN or Inf.")
        if not np.all(np.isfinite(self._sigma)):
            raise DistributionValidationError("Gaussian sigma contains NaN or Inf.")
        if np.any(self._sigma <= 0.0):
            raise DistributionValidationError("Gaussian sigma must be strictly positive (> 0).")
        if hasattr(self, "_override_p_15") and self._override_p_15 is not None:
            if np.any(self._override_p_15 < 0.0) or np.any(self._override_p_15 > 1.0):
                raise DistributionValidationError("Overridden probability_ge out of [0, 1].")

    @hybrid_contract_property
    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=True,
            median=True,
            quantile=True,
            cdf=True,
            probability_ge=True,
            sample=True,
            nll=True,
            crps_exact=True,
            crps_approx=True,
            pit=True,
        )

    @hybrid_contract_property
    def metadata(self) -> CallableDict:
        caps = self.capabilities
        res = {
            "candidate_id": self._candidate_id,
            "family": self._family,
            "role": self._metadata.get("role", "HOMOSCEDASTIC_PARAMETRIC_BASELINE"),
            "capabilities": caps,
            "n_flights": self._n_flights,
            "dist_params": {"mu": self._mu, "sigma": self._sigma},
        }
        res.update(self._metadata)
        res["capabilities"] = caps
        res["dist_params"] = {"mu": self._mu, "sigma": self._sigma}
        return CallableDict(res)


class NGBoostNormalDistribution(GaussianResidualDistribution):
    """NGBoost heteroscedastic Normal distribution adapter."""

    def __init__(
        self,
        mu: np.ndarray,
        sigma: np.ndarray,
        candidate_id: str = "P3_ngboost_normal",
        metadata_dict: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            mu=mu,
            sigma=sigma,
            family="ngboost_normal",
            candidate_id=candidate_id,
            metadata_dict=metadata_dict,
        )

    @hybrid_contract_property
    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=True,
            median=True,
            quantile=True,
            cdf=True,
            probability_ge=True,
            sample=True,
            nll=True,
            crps_exact=True,
            crps_approx=True,
            pit=True,
        )

    @hybrid_contract_property
    def metadata(self) -> CallableDict:
        caps = self.capabilities
        res = {
            "candidate_id": self._candidate_id,
            "family": "ngboost_normal",
            "role": self._metadata.get("role", "HETEROSCEDASTIC_PARAMETRIC_GAUSSIAN"),
            "capabilities": caps,
            "n_flights": self._n_flights,
            "dist_params": {"mu": self._mu, "sigma": self._sigma},
        }
        res.update(self._metadata)
        res["capabilities"] = caps
        res["dist_params"] = {"mu": self._mu, "sigma": self._sigma}
        return CallableDict(res)


# =============================================================================
# ADAPTER 4: Student-T Distribution
# =============================================================================

class NGBoostStudentTDistribution(PredictiveDistribution):
    """Heteroscedastic Student-T distribution adapter (historical/research heavy-tail candidate)."""

    def __init__(
        self,
        mu: np.ndarray,
        sigma: np.ndarray,
        df: np.ndarray,
        candidate_id: str = "P4_ngboost_student_t",
        metadata_dict: dict[str, Any] | None = None,
    ) -> None:
        self._mu = np.asarray(mu, dtype=np.float64)
        self._sigma = np.maximum(np.asarray(sigma, dtype=np.float64), DEFAULT_SIGMA_FLOOR)
        self._df = np.maximum(np.asarray(df, dtype=np.float64), 2.1)
        self._n_flights = len(self._mu)
        self._candidate_id = candidate_id
        self._metadata = metadata_dict or {}

    @hybrid_contract_property
    def mean(self) -> CallableArray:
        return CallableArray(self._mu)

    @hybrid_contract_property
    def median(self) -> CallableArray:
        return CallableArray(self._mu)

    def quantile(self, q: float | Sequence[float] | np.ndarray) -> np.ndarray:
        if np.isscalar(q):
            alpha = float(q)
            if not 0.0 < alpha < 1.0:
                raise ValueError(f"Quantile alpha must be in (0, 1), got {alpha}")
            res = student_t.ppf(alpha, df=self._df, loc=self._mu, scale=self._sigma)
            return CallableArray(res)
        else:
            alphas = np.asarray(q, dtype=np.float64)
            if np.any(alphas <= 0.0) or np.any(alphas >= 1.0):
                raise ValueError("All quantile alphas must be strictly in (0, 1)")
            out = np.zeros((len(alphas), self._n_flights), dtype=np.float64)
            for k, a in enumerate(alphas):
                out[k] = student_t.ppf(a, df=self._df, loc=self._mu, scale=self._sigma)
            return CallableArray(out)

    def cdf(self, x: float | np.ndarray) -> np.ndarray:
        if np.isscalar(x):
            res = student_t.cdf(float(x), df=self._df, loc=self._mu, scale=self._sigma)
            return CallableArray(res)
        x_arr = np.asarray(x, dtype=np.float64)
        if x_arr.shape == (self._n_flights,):
            res = student_t.cdf(x_arr, df=self._df, loc=self._mu, scale=self._sigma)
            return CallableArray(res)
        elif x_arr.ndim == 1:
            out = np.zeros((len(x_arr), self._n_flights), dtype=np.float64)
            for m, xm in enumerate(x_arr):
                out[m] = student_t.cdf(xm, df=self._df, loc=self._mu, scale=self._sigma)
            return CallableArray(out)
        else:
            raise ValueError(f"Unsupported CDF input shape: {x_arr.shape}")

    def probability_ge(self, threshold: float | np.ndarray = 15.0) -> np.ndarray:
        return CallableArray(np.clip(1.0 - self.cdf(threshold), 0.0, 1.0))

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        if n <= 0:
            raise ValueError(f"Sample size n must be positive, got {n}")
        rng = np.random.default_rng(seed)
        t_draws = rng.standard_t(self._df, size=(n, self._n_flights))
        res = self._mu[np.newaxis, :] + self._sigma[np.newaxis, :] * t_draws
        return CallableArray(res)

    def validate(self) -> None:
        if not np.all(np.isfinite(self._mu)):
            raise DistributionValidationError("Student-T mu contains NaN or Inf.")
        if not np.all(np.isfinite(self._sigma)):
            raise DistributionValidationError("Student-T sigma contains NaN or Inf.")
        if np.any(self._sigma <= 0.0):
            raise DistributionValidationError("Student-T sigma must be strictly positive (> 0).")
        if not np.all(np.isfinite(self._df)):
            raise DistributionValidationError("Student-T df contains NaN or Inf.")
        if np.any(self._df <= 2.0):
            raise DistributionValidationError("Student-T df must be strictly > 2.0 for finite variance.")

    @hybrid_contract_property
    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=True,
            median=True,
            quantile=True,
            cdf=True,
            probability_ge=True,
            sample=True,
            nll=True,
            crps_exact=False,
            crps_approx=True,
            pit=True,
        )

    @hybrid_contract_property
    def metadata(self) -> CallableDict:
        caps = self.capabilities
        res = {
            "candidate_id": self._candidate_id,
            "family": "ngboost_student_t",
            "role": self._metadata.get("role", "historical_candidate"),
            "status": "historical_candidate",
            "capabilities": caps,
            "n_flights": self._n_flights,
            "dist_params": {"mu": self._mu, "sigma": self._sigma, "df": self._df},
        }
        res.update(self._metadata)
        res["capabilities"] = caps
        res["dist_params"] = {"mu": self._mu, "sigma": self._sigma, "df": self._df}
        return CallableDict(res)


# =============================================================================
# ADAPTER 5: Quantile Predictive Distribution
# =============================================================================

class QuantilePredictiveDistribution(PredictiveDistribution):
    """Pure Quantile regression predictive distribution adapter.

    Contract:
    - Quantile models only possess quantile capabilities.
    - Full CDF is NOT synthesized by ad-hoc heuristics (strictly prohibited).
    - Mean, continuous CDF, event probability, generative sampling, and NLL are unsupported.
    """

    def __init__(
        self,
        quantiles_dict: dict[float, np.ndarray],
        candidate_id: str = "P5_quantile_regression",
        metadata_dict: dict[str, Any] | None = None,
    ) -> None:
        self._quantiles = {float(k): np.asarray(v, dtype=np.float64) for k, v in quantiles_dict.items()}
        sorted_alphas = sorted(self._quantiles.keys())
        if not sorted_alphas:
            raise ValueError("QuantilePredictiveDistribution requires non-empty quantiles dict.")
        self._n_flights = len(self._quantiles[sorted_alphas[0]])
        self._candidate_id = candidate_id
        self._metadata = metadata_dict or {}

    @hybrid_contract_property
    def mean(self) -> CallableArray:
        raise CapabilityNotSupportedError(
            "Quantile models do not support conditional expectation without heuristic tail extrapolation."
        )

    @hybrid_contract_property
    def median(self) -> CallableArray:
        if 0.5 in self._quantiles:
            return CallableArray(self._quantiles[0.5])
        return CallableArray(self.quantile(0.5))

    def quantile(self, q: float | Sequence[float] | np.ndarray) -> np.ndarray:
        if np.isscalar(q):
            alpha = float(q)
            if not 0.0 < alpha < 1.0:
                raise ValueError(f"Quantile alpha must be in (0, 1), got {alpha}")
            if alpha in self._quantiles:
                return CallableArray(self._quantiles[alpha])
            sorted_alphas = sorted(self._quantiles.keys())
            if alpha < sorted_alphas[0] or alpha > sorted_alphas[-1]:
                raise CapabilityNotSupportedError(
                    f"Alpha {alpha} is outside pre-registered quantile grid [{sorted_alphas[0]}, {sorted_alphas[-1]}]; "
                    "extrapolation heuristics are prohibited."
                )
            alpha_arr = np.array(sorted_alphas)
            idx = np.searchsorted(alpha_arr, alpha)
            a_low, a_high = alpha_arr[idx - 1], alpha_arr[idx]
            q_low, q_high = self._quantiles[a_low], self._quantiles[a_high]
            weight = (alpha - a_low) / (a_high - a_low)
            res = q_low + weight * (q_high - q_low)
            return CallableArray(res)
        else:
            alphas = np.asarray(q, dtype=np.float64)
            if np.any(alphas <= 0.0) or np.any(alphas >= 1.0):
                raise ValueError("All quantile alphas must be strictly in (0, 1)")
            res = np.array([self.quantile(float(a)) for a in alphas], dtype=np.float64)
            return CallableArray(res)

    def cdf(self, x: float | np.ndarray) -> np.ndarray:
        raise CapabilityNotSupportedError(
            "Quantile regression candidates do not provide a continuous CDF. "
            "Heuristic CDF synthesis is prohibited by protocol."
        )

    def probability_ge(self, threshold: float | np.ndarray = 15.0) -> np.ndarray:
        raise CapabilityNotSupportedError(
            "Event probability P(Y >= threshold) is unsupported without full CDF or binary head."
        )

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        raise CapabilityNotSupportedError(
            "Generative sampling is unsupported for pure quantile regression models without full continuous CDF."
        )

    def validate(self) -> None:
        for a, q in self._quantiles.items():
            if not np.all(np.isfinite(q)):
                raise DistributionValidationError(f"Quantile alpha={a} contains NaN or Inf.")
            if len(q) != self._n_flights:
                raise DistributionValidationError(
                    f"Quantile alpha={a} length {len(q)} does not match n_flights {self._n_flights}."
                )
        sorted_alphas = sorted(self._quantiles.keys())
        for j in range(len(sorted_alphas) - 1):
            a_cur, a_nxt = sorted_alphas[j], sorted_alphas[j + 1]
            if np.any(self._quantiles[a_cur] > self._quantiles[a_nxt] + 1e-6):
                raise DistributionValidationError(
                    f"Quantile crossing detected: q({a_cur}) > q({a_nxt})"
                )

    @hybrid_contract_property
    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=False,
            median=True,
            quantile=True,
            cdf=False,
            probability_ge=False,
            sample=False,
            nll=False,
            crps_exact=False,
            crps_approx=True,
            pit=False,
        )

    @hybrid_contract_property
    def metadata(self) -> CallableDict:
        caps = self.capabilities
        res = {
            "candidate_id": self._candidate_id,
            "family": "quantile_regression",
            "role": self._metadata.get("role", "QUANTILE_FORECAST_ONLY"),
            "capabilities": caps,
            "n_flights": self._n_flights,
        }
        res.update(self._metadata)
        res["capabilities"] = caps
        return CallableDict(res)
