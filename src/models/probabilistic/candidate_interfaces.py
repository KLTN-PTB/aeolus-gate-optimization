"""Common distributional prediction interface and candidate adapters for Aeolus.

Protocol: Phase 4 Common Distribution Contract
Scope:
- BaseProbabilisticCandidate abstract interface
- Standardized PredictiveDistribution returns across all 5 Core Candidates:
  P1: Empirical carrier x scheduled-hour baseline with hierarchical backoff
  P2: XGBoost mean + OOF residual uncertainty (Fixed-sigma Gaussian)
  P3: NGBoost Normal (Heteroscedastic Gaussian)
  P4: NGBoost Student-T (Heteroscedastic Heavy-Tail)
  P5: Quantile regression research comparator (Multi-pinball LightGBM)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Final, Sequence

import numpy as np
import pandas as pd

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    ProbabilisticPrediction,
    QuantilePredictiveDistribution,
)
from src.models.probabilistic.baselines import (
    B1EmpiricalDistribution,
    B2XGBoostGaussian,
    B3NGBoostNormal,
    B4LightGBMQuantile,
    B5NGBoostStudentT,
)
from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PREDETERMINED_DEPLOYMENT_SEED,
    SCREENING_SEED,
)
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
)


class BaseProbabilisticCandidate(ABC):
    """Abstract interface for Core Arrival probabilistic candidates."""

    def __init__(self, candidate_id: str, seed: int = SCREENING_SEED) -> None:
        self.candidate_id = candidate_id
        self.seed = seed
        self.is_fitted_ = False

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Declare supported capabilities."""
        ...

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> BaseProbabilisticCandidate:
        """Fit candidate on training fold."""
        ...

    @abstractmethod
    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        """Predict common distributional representation on validation fold."""
        ...


# =========================================================================
# P1: Empirical carrier x scheduled-hour baseline
# =========================================================================

class P1EmpiricalCandidate(BaseProbabilisticCandidate):
    """P1 — Empirical carrier x scheduled-hour distribution with hierarchical backoff."""

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("P1_empirical", seed=seed)
        self.underlying_ = B1EmpiricalDistribution()
        self.y_history_: np.ndarray | None = None
        self.carrier_history_: dict[str, np.ndarray] = {}
        self.carrier_hour_history_: dict[tuple[str, int], np.ndarray] = {}

    def capabilities(self) -> dict[str, bool]:
        return {
            "has_mean": True,
            "has_median": True,
            "has_quantiles": True,
            "has_cdf": True,
            "has_probability_ge": True,
            "has_p_delay_ge_15": True,
            "has_sampler": True,
            "has_nll": False,  # Non-parametric empirical distribution has no continuous likelihood
            "has_crps": True,
            "has_pit": False,  # Discrete step CDF produces invalid continuous PIT
        }

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> P1EmpiricalCandidate:
        y_arr = np.asarray(y, dtype=np.float64)
        self.y_history_ = y_arr
        self.underlying_.fit(X, y_arr)

        carriers = X["OP_CARRIER"].astype(str).to_numpy()
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(0).astype(int).to_numpy()

        self.carrier_history_ = {}
        for c in np.unique(carriers):
            mask = carriers == c
            if np.sum(mask) >= self.underlying_.min_support:
                self.carrier_history_[c] = y_arr[mask]

        self.carrier_hour_history_ = {}
        df_tmp = pd.DataFrame({"c": carriers, "h": hours, "y": y_arr})
        for (c, h), group in df_tmp.groupby(["c", "h"]):
            if len(group) >= self.underlying_.min_support:
                self.carrier_hour_history_[(str(c), int(h))] = group["y"].to_numpy()

        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        dist = self.underlying_.predict_distribution(X)
        n = len(X)
        mu = dist["mu"]
        quantiles = dist["quantiles"]
        median = quantiles[0.50]
        p_15 = np.clip(dist["event_probs"][15.0], 0.0, 1.0)

        carriers = X["OP_CARRIER"].astype(str).to_numpy()
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(0).astype(int).to_numpy()

        row_histories: list[np.ndarray] = []
        for i in range(n):
            key = (carriers[i], hours[i])
            if key in self.carrier_hour_history_:
                row_histories.append(self.carrier_hour_history_[key])
            elif carriers[i] in self.carrier_history_:
                row_histories.append(self.carrier_history_[carriers[i]])
            else:
                row_histories.append(self.y_history_)

        return EmpiricalDistribution(
            mean_vals=mu,
            median_vals=median,
            quantiles_dict=quantiles,
            p_ge_15_vals=p_15,
            sample_pool_list=row_histories,
            metadata_dict={
                "candidate_id": self.candidate_id,
                "family": "empirical_carrier_hour",
                "role": "EMPIRICAL_RESIDUAL_BASELINE",
                "has_pit": False,
            },
        )


# =========================================================================
# P2: XGBoost mean + OOF residual uncertainty (Fixed-sigma Gaussian)
# =========================================================================

class P2XGBoostGaussianCandidate(BaseProbabilisticCandidate):
    """P2 — XGBoost point mean with cross-fitted OOF residual variance (Fixed-sigma Gaussian)."""

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("P2_xgb_gaussian_oof", seed=seed)
        self.underlying_ = B2XGBoostGaussian(n_estimators=100, learning_rate=0.05, seed=seed)

    def capabilities(self) -> dict[str, bool]:
        return {
            "has_mean": True,
            "has_median": True,
            "has_quantiles": True,
            "has_cdf": True,
            "has_probability_ge": True,
            "has_p_delay_ge_15": True,
            "has_sampler": True,
            "has_nll": True,
            "has_crps": True,
            "has_pit": True,
        }

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> P2XGBoostGaussianCandidate:
        self.underlying_.fit(X, y)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        dist = self.underlying_.predict_distribution(X)
        mu = dist["mu"]
        sigma = np.maximum(dist["sigma"], DEFAULT_SIGMA_FLOOR)

        return GaussianResidualDistribution(
            mu=mu,
            sigma=sigma,
            family="xgb_gaussian_oof",
            candidate_id=self.candidate_id,
            metadata_dict={
                "candidate_id": self.candidate_id,
                "family": "xgb_gaussian_oof",
                "role": "HOMOSCEDASTIC_PARAMETRIC_BASELINE",
                "has_pit": True,
            },
        )


# =========================================================================
# P3: NGBoost Normal (Heteroscedastic Gaussian)
# =========================================================================

class P3NGBoostNormalCandidate(BaseProbabilisticCandidate):
    """P3 — NGBoost Normal with heteroscedastic location and scale."""

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("P3_ngboost_normal", seed=seed)
        self.underlying_ = B3NGBoostNormal(n_estimators=50, learning_rate=0.01, seed=seed)

    def capabilities(self) -> dict[str, bool]:
        return {
            "has_mean": True,
            "has_median": True,
            "has_quantiles": True,
            "has_cdf": True,
            "has_probability_ge": True,
            "has_p_delay_ge_15": True,
            "has_sampler": True,
            "has_nll": True,
            "has_crps": True,
            "has_pit": True,
        }

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> P3NGBoostNormalCandidate:
        self.underlying_.fit(X, y)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        dist = self.underlying_.predict_distribution(X)
        mu = dist["mu"]
        sigma = np.maximum(dist["sigma"], DEFAULT_SIGMA_FLOOR)

        return NGBoostNormalDistribution(
            mu=mu,
            sigma=sigma,
            candidate_id=self.candidate_id,
            metadata_dict={
                "candidate_id": self.candidate_id,
                "family": "ngboost_normal",
                "role": "HETEROSCEDASTIC_PARAMETRIC_GAUSSIAN",
                "has_pit": True,
            },
        )


# =========================================================================
# P4: NGBoost Student-T (Heteroscedastic Heavy-Tail)
# =========================================================================

class P4NGBoostStudentTCandidate(BaseProbabilisticCandidate):
    """P4 — NGBoost Student-T (historical/research heavy-tail candidate)."""

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("P4_ngboost_student_t", seed=seed)
        self.underlying_ = B5NGBoostStudentT(n_estimators=40, learning_rate=0.005, seed=seed)

    def capabilities(self) -> dict[str, bool]:
        return {
            "has_mean": True,
            "has_median": True,
            "has_quantiles": True,
            "has_cdf": True,
            "has_probability_ge": True,
            "has_p_delay_ge_15": True,
            "has_sampler": True,
            "has_nll": True,
            "has_crps": True,
            "has_pit": True,
        }

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> P4NGBoostStudentTCandidate:
        self.underlying_.fit(X, y)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        dist = self.underlying_.predict_distribution(X)
        mu = dist["mu"]
        sigma = np.maximum(dist["sigma"], DEFAULT_SIGMA_FLOOR)
        df_vals = np.maximum(dist["df"], 2.1)

        return NGBoostStudentTDistribution(
            mu=mu,
            sigma=sigma,
            df=df_vals,
            candidate_id=self.candidate_id,
            metadata_dict={
                "candidate_id": self.candidate_id,
                "family": "ngboost_student_t",
                "role": "historical_candidate",
                "has_pit": True,
            },
        )


# =========================================================================
# P5: Quantile Regression Research Comparator (Multi-pinball LightGBM)
# =========================================================================

class P5QuantileRegressionCandidate(BaseProbabilisticCandidate):
    """P5 — Quantile regression research comparator via multi-pinball loss.

    Strictly conforms to Phase 4 protocol:
    - Only possesses quantile capabilities.
    - Zero heuristic CDF synthesis.
    """

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("P5_quantile_regression", seed=seed)
        self.underlying_ = B4LightGBMQuantile(
            alphas=PRE_REGISTERED_QUANTILES,
            n_estimators=80,
            learning_rate=0.05,
            seed=seed,
        )

    def capabilities(self) -> dict[str, bool]:
        return {
            "has_mean": False,  # Non-parametric quantile models have no natural mean
            "has_median": True,
            "has_quantiles": True,
            "has_cdf": False,  # Heuristic CDF synthesis strictly prohibited
            "has_probability_ge": False,
            "has_p_delay_ge_15": False,
            "has_sampler": False,  # Generative sampling unsupported without full CDF
            "has_nll": False,  # No continuous likelihood
            "has_crps": True,  # Via quantile pinball loss integration
            "has_pit": False,  # Continuous PIT strictly unsupported
        }

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> P5QuantileRegressionCandidate:
        self.underlying_.fit(X, y)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        raw_quantiles = self.underlying_.predict_quantiles(X)
        sorted_alphas = sorted(PRE_REGISTERED_QUANTILES)

        # Monotone rearrangement (Chernozhukov et al., 2010) to strictly enforce non-crossing
        q_matrix = np.column_stack([raw_quantiles[a] for a in sorted_alphas])
        q_sorted_matrix = np.sort(q_matrix, axis=1)

        quantiles: dict[float, np.ndarray] = {
            a: q_sorted_matrix[:, i] for i, a in enumerate(sorted_alphas)
        }

        return QuantilePredictiveDistribution(
            quantiles_dict=quantiles,
            candidate_id=self.candidate_id,
            metadata_dict={
                "candidate_id": self.candidate_id,
                "family": "quantile_regression",
                "role": "QUANTILE_FORECAST_ONLY",
                "has_pit": False,
            },
        )


PROBABILISTIC_CANDIDATE_REGISTRY: dict[str, type[BaseProbabilisticCandidate]] = {
    "P1_empirical": P1EmpiricalCandidate,
    "P2_xgb_gaussian_oof": P2XGBoostGaussianCandidate,
    "P3_ngboost_normal": P3NGBoostNormalCandidate,
    "P4_ngboost_student_t": P4NGBoostStudentTCandidate,
    "P5_quantile_regression": P5QuantileRegressionCandidate,
}


def get_probabilistic_candidate(
    candidate_id: str,
    seed: int = SCREENING_SEED,
) -> BaseProbabilisticCandidate:
    """Retrieve probabilistic candidate instance by registered ID."""
    if candidate_id not in PROBABILISTIC_CANDIDATE_REGISTRY:
        raise KeyError(
            f"Unknown candidate_id '{candidate_id}'. Registered candidates: "
            f"{list(PROBABILISTIC_CANDIDATE_REGISTRY.keys())}"
        )
    return PROBABILISTIC_CANDIDATE_REGISTRY[candidate_id](seed=seed)
