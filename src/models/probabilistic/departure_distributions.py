"""Core Departure Predictive Distributions and Probabilistic Candidate Models.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P5 Probabilistic Core Departure & Calibrated Sampling
Task: ModelTask.CORE_DEPARTURE (ORIGIN = "ATL", signed DEP_DELAY, cutoff CRS_DEP_TIME - 2h)

This module implements the 5 candidate probabilistic models for Core Departure:
1. DepartureEmpiricalBaseline: Non-parametric carrier x hour empirical distribution with hierarchical backoff.
2. DepartureGaussianResidualModel: Point mean (XGBoost) + stratified residual uncertainty.
3. DepartureNGBoostNormalModel: Heteroscedastic Gaussian via NGBoost Normal.
4. DepartureNGBoostStudentTModel: Heteroscedastic heavy-tail distribution via NGBoost Student-T.
5. DepartureQuantileModel: Multi-pinball quantile regression (discrete quantile grid, no continuous sampler).

All models conform to the PredictiveDistribution interface defined in src.contracts.distribution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import lightgbm as lgb
from ngboost import NGBRegressor
from ngboost.distns import Normal, T
import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionCapabilities,
    DistributionError,
    EmpiricalDistribution,
    GaussianResidualDistribution,
    NGBoostNormalDistribution,
    NGBoostStudentTDistribution,
    PredictiveDistribution,
    QuantilePredictiveDistribution,
)
from src.data.departure_preprocessing import DeparturePreprocessingPipeline
from src.features.departure_features import APPROVED_DEPARTURE_PREDICTOR_COLUMNS
from src.models.probabilistic.contracts import DEFAULT_SIGMA_FLOOR, SCREENING_SEED
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
)


MIN_EMPIRICAL_SUPPORT: Final[int] = 30


class BaseDepartureProbabilisticModel(ABC):
    """Abstract base class for all Core Departure probabilistic models."""

    def __init__(self, model_id: str, seed: int = SCREENING_SEED) -> None:
        self.model_id = model_id
        self.seed = seed
        self.is_fitted: bool = False

    @abstractmethod
    def capabilities(self) -> DistributionCapabilities:
        """Explicit capability declaration."""
        ...

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> BaseDepartureProbabilisticModel:
        """Fit model on training fold."""
        ...

    @abstractmethod
    def predict_distribution(self, X: pd.DataFrame) -> PredictiveDistribution:
        """Predict standard PredictiveDistribution object."""
        ...

    def predict_point(self, X: pd.DataFrame) -> np.ndarray:
        """Predict conditional expectation or median."""
        dist = self.predict_distribution(X)
        if dist.capabilities.supports("mean"):
            return np.asarray(dist.mean, dtype=np.float64)
        elif dist.capabilities.supports("median"):
            return np.asarray(dist.median, dtype=np.float64)
        raise CapabilityNotSupportedError(f"{self.model_id} does not support point prediction.")

    def sample(self, X: pd.DataFrame, n_samples: int, seed: int | None = None) -> np.ndarray:
        """Generate generative draws: shape (n_samples, n_flights)."""
        dist = self.predict_distribution(X)
        if not dist.capabilities.supports("sample"):
            raise CapabilityNotSupportedError(f"{self.model_id} does not support continuous sampling.")
        return dist.sample(n_samples, seed=seed)

    def quantile(self, X: pd.DataFrame, q: float | Sequence[float]) -> np.ndarray:
        """Evaluate quantile function."""
        dist = self.predict_distribution(X)
        if not dist.capabilities.supports("quantile"):
            raise CapabilityNotSupportedError(f"{self.model_id} does not support quantile queries.")
        return dist.quantile(q)

    def cdf(self, X: pd.DataFrame, value: float | np.ndarray) -> np.ndarray:
        """Evaluate CDF."""
        dist = self.predict_distribution(X)
        if not dist.capabilities.supports("cdf"):
            raise CapabilityNotSupportedError(f"{self.model_id} does not support CDF queries.")
        return dist.cdf(value)

    def probability_ge(self, X: pd.DataFrame, threshold: float = 15.0) -> np.ndarray:
        """Evaluate exceedance probability P(delay >= threshold)."""
        dist = self.predict_distribution(X)
        if not dist.capabilities.supports("probability_ge"):
            raise CapabilityNotSupportedError(f"{self.model_id} does not support exceedance probabilities.")
        return dist.probability_ge(threshold)


# =============================================================================
# CANDIDATE 1: Empirical Carrier x Hour Baseline
# =============================================================================

@dataclass
class _GroupStats:
    mean: float
    median: float
    quantiles: dict[float, float]
    p_ge_15: float
    pool: np.ndarray


class DepartureEmpiricalBaseline(BaseDepartureProbabilisticModel):
    """Candidate 1: Non-parametric carrier x scheduled-hour empirical distribution.

    Uses hierarchical backoff:
    Level 1: (carrier, scheduled_departure_hour) if sample_count >= 30
    Level 2: carrier if sample_count >= 30
    Level 3: global training target pool
    """

    def __init__(self, seed: int = SCREENING_SEED) -> None:
        super().__init__("departure_empirical_residual_v1", seed=seed)
        self.global_stats_: _GroupStats | None = None
        self.carrier_stats_: dict[str, _GroupStats] = {}
        self.carrier_hour_stats_: dict[tuple[str, int], _GroupStats] = {}

    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=True,
            median=True,
            quantile=True,
            cdf=True,
            probability_ge=True,
            sample=True,
            nll=False,  # Non-parametric step CDF has no continuous likelihood
            crps_exact=False,
            crps_approx=True,
            pit=False,
        )

    def _compute_stats(self, y_vals: np.ndarray) -> _GroupStats:
        mean_val = float(np.mean(y_vals))
        median_val = float(np.median(y_vals))
        quantiles_dict = {
            float(a): float(np.percentile(y_vals, a * 100.0))
            for a in PRE_REGISTERED_QUANTILES
        }
        p_15 = float(np.mean(y_vals >= 15.0))
        return _GroupStats(
            mean=mean_val,
            median=median_val,
            quantiles=quantiles_dict,
            p_ge_15=p_15,
            pool=y_vals,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> DepartureEmpiricalBaseline:
        y_arr = np.asarray(y, dtype=np.float64)
        carriers = X["OP_CARRIER"].astype(str).values
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(12).astype(int).values

        # 1. Global statistics
        self.global_stats_ = self._compute_stats(y_arr)

        # 2. Carrier statistics
        self.carrier_stats_ = {}
        df = pd.DataFrame({"carrier": carriers, "hour": hours, "y": y_arr})
        for c, grp in df.groupby("carrier"):
            if len(grp) >= MIN_EMPIRICAL_SUPPORT:
                self.carrier_stats_[str(c)] = self._compute_stats(grp["y"].values)

        # 3. Carrier x Hour statistics
        self.carrier_hour_stats_ = {}
        for (c, h), grp in df.groupby(["carrier", "hour"]):
            if len(grp) >= MIN_EMPIRICAL_SUPPORT:
                self.carrier_hour_stats_[(str(c), int(h))] = self._compute_stats(grp["y"].values)

        self.is_fitted = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> EmpiricalDistribution:
        if not self.is_fitted or self.global_stats_ is None:
            raise DistributionError("DepartureEmpiricalBaseline is not fitted")

        n = len(X)
        carriers = X["OP_CARRIER"].astype(str).values
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(12).astype(int).values

        means = np.empty(n, dtype=np.float64)
        medians = np.empty(n, dtype=np.float64)
        p_ge_15 = np.empty(n, dtype=np.float64)
        quantiles_dict = {float(a): np.empty(n, dtype=np.float64) for a in PRE_REGISTERED_QUANTILES}
        sample_pools = []

        for i in range(n):
            key_ch = (carriers[i], hours[i])
            c = carriers[i]
            if key_ch in self.carrier_hour_stats_:
                stats = self.carrier_hour_stats_[key_ch]
            elif c in self.carrier_stats_:
                stats = self.carrier_stats_[c]
            else:
                stats = self.global_stats_

            means[i] = stats.mean
            medians[i] = stats.median
            p_ge_15[i] = stats.p_ge_15
            sample_pools.append(stats.pool)
            for a in PRE_REGISTERED_QUANTILES:
                quantiles_dict[float(a)][i] = stats.quantiles[float(a)]

        return EmpiricalDistribution(
            mean_vals=means,
            median_vals=medians,
            quantiles_dict=quantiles_dict,
            p_ge_15_vals=p_ge_15,
            sample_pool_list=sample_pools,
            metadata_dict={"candidate_id": self.model_id, "family": "empirical"},
        )


# =============================================================================
# CANDIDATE 2: XGBoost Point Mean + Stratified Residual Uncertainty
# =============================================================================

class DepartureGaussianResidualModel(BaseDepartureProbabilisticModel):
    """Candidate 2: XGBoost point mean + stratified residual uncertainty.

    Generates Gaussian predictive distribution N(mu(X), sigma^2(X)).
    mu(X) is obtained from the fitted tree pipeline.
    sigma(X) is computed conditionally on (carrier, hour_group) from training residuals.
    """

    def __init__(
        self,
        *,
        point_model: Any | None = None,
        preprocessor: DeparturePreprocessingPipeline | None = None,
        seed: int = SCREENING_SEED,
    ) -> None:
        super().__init__("departure_gaussian_residual_v1", seed=seed)
        self.point_model = point_model
        self.preprocessor = preprocessor
        self.global_sigma_: float = 35.0
        self.group_sigma_: dict[tuple[str, str], float] = {}

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

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> DepartureGaussianResidualModel:
        y_arr = np.asarray(y, dtype=np.float64)

        # Preprocess features
        if self.preprocessor is None:
            self.preprocessor = DeparturePreprocessingPipeline(preprocessor_type="tree").fit(X)
        X_trans = self.preprocessor.transform(X)

        # Fit point regressor if not provided
        if self.point_model is None:
            import xgboost as xgb
            self.point_model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                tree_method="hist",
                n_jobs=4,
                random_state=self.seed,
            )
            self.point_model.fit(X_trans, y_arr)

        # Compute training fold residuals
        y_pred = self.point_model.predict(X_trans)
        residuals = y_arr - y_pred

        self.global_sigma_ = float(max(np.std(residuals, ddof=1), DEFAULT_SIGMA_FLOOR))

        # Stratified residual std by (carrier, hour_group)
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(12).astype(int).values
        hour_groups = pd.cut(
            hours,
            bins=[-1, 5, 11, 17, 24],
            labels=["Night", "Morning", "Afternoon", "Evening"],
        ).astype(str)
        carriers = X["OP_CARRIER"].astype(str).values

        df_res = pd.DataFrame({"carrier": carriers, "hgrp": hour_groups, "res": residuals})
        self.group_sigma_ = {}
        for (c, hg), grp in df_res.groupby(["carrier", "hgrp"]):
            if len(grp) >= 20:
                s = float(np.std(grp["res"].values, ddof=1))
                self.group_sigma_[(str(c), str(hg))] = max(s, DEFAULT_SIGMA_FLOOR)

        self.is_fitted = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> GaussianResidualDistribution:
        if not self.is_fitted or self.point_model is None or self.preprocessor is None:
            raise DistributionError("DepartureGaussianResidualModel is not fitted")

        X_trans = self.preprocessor.transform(X)
        mu = np.asarray(self.point_model.predict(X_trans), dtype=np.float64)

        n = len(X)
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(12).astype(int).values
        hour_groups = pd.cut(
            hours,
            bins=[-1, 5, 11, 17, 24],
            labels=["Night", "Morning", "Afternoon", "Evening"],
        ).astype(str)
        carriers = X["OP_CARRIER"].astype(str).values

        sigma = np.empty(n, dtype=np.float64)
        for i in range(n):
            key = (carriers[i], hour_groups[i])
            sigma[i] = self.group_sigma_.get(key, self.global_sigma_)

        sigma = np.clip(sigma, a_min=DEFAULT_SIGMA_FLOOR, a_max=500.0)

        return GaussianResidualDistribution(
            mu=mu,
            sigma=sigma,
            candidate_id=self.model_id,
            metadata_dict={"family": "gaussian_residual"},
        )


# =============================================================================
# CANDIDATE 3: NGBoost Normal (Heteroscedastic Gaussian)
# =============================================================================

class DepartureNGBoostNormalModel(BaseDepartureProbabilisticModel):
    """Candidate 3: NGBoost Normal regression.

    Jointly learns conditional mean mu(X) and conditional standard deviation sigma(X).
    """

    def __init__(
        self,
        *,
        n_estimators: int = 40,
        learning_rate: float = 0.02,
        seed: int = SCREENING_SEED,
    ) -> None:
        super().__init__("departure_ngboost_normal_v1", seed=seed)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.preprocessor: DeparturePreprocessingPipeline | None = None
        self.model: NGBRegressor | None = None

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

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> DepartureNGBoostNormalModel:
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor = DeparturePreprocessingPipeline(preprocessor_type="tree").fit(X)
        X_trans = self.preprocessor.transform(X)

        self.model = NGBRegressor(
            Dist=Normal,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            random_state=self.seed,
            verbose=False,
        )
        self.model.fit(X_trans, y_arr)
        self.is_fitted = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> NGBoostNormalDistribution:
        if not self.is_fitted or self.model is None or self.preprocessor is None:
            raise DistributionError("DepartureNGBoostNormalModel is not fitted")

        X_trans = self.preprocessor.transform(X)
        dist = self.model.pred_dist(X_trans)
        mu = np.asarray(dist.loc, dtype=np.float64)
        sigma = np.clip(
            np.maximum(np.asarray(dist.scale, dtype=np.float64), DEFAULT_SIGMA_FLOOR),
            a_min=DEFAULT_SIGMA_FLOOR,
            a_max=500.0,
        )

        return NGBoostNormalDistribution(
            mu=mu,
            sigma=sigma,
            candidate_id=self.model_id,
            metadata_dict={"family": "ngboost_normal"},
        )


# =============================================================================
# CANDIDATE 4: NGBoost Student-T (Heteroscedastic Heavy-Tail Champion)
# =============================================================================

class DepartureNGBoostStudentTModel(BaseDepartureProbabilisticModel):
    """Candidate 4: NGBoost Student-T regression.

    Jointly learns conditional mean mu(X), scale sigma(X), and degrees of freedom nu(X).
    Ensures nu >= 2.1 for strictly finite variance and stability under extreme delays.
    """

    def __init__(
        self,
        *,
        n_estimators: int = 40,
        learning_rate: float = 0.005,
        seed: int = SCREENING_SEED,
    ) -> None:
        super().__init__("departure_ngboost_student_t_v1", seed=seed)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.preprocessor: DeparturePreprocessingPipeline | None = None
        self.model: NGBRegressor | None = None

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

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> DepartureNGBoostStudentTModel:
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor = DeparturePreprocessingPipeline(preprocessor_type="tree").fit(X)
        X_trans = self.preprocessor.transform(X)

        self.model = NGBRegressor(
            Dist=T,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            random_state=self.seed,
            verbose=False,
        )
        self.model.fit(X_trans, y_arr)
        self.is_fitted = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> NGBoostStudentTDistribution:
        if not self.is_fitted or self.model is None or self.preprocessor is None:
            raise DistributionError("DepartureNGBoostStudentTModel is not fitted")

        X_trans = self.preprocessor.transform(X)
        dist = self.model.pred_dist(X_trans)
        mu = np.asarray(dist.loc, dtype=np.float64)
        sigma = np.clip(
            np.maximum(np.asarray(dist.scale, dtype=np.float64), DEFAULT_SIGMA_FLOOR),
            a_min=DEFAULT_SIGMA_FLOOR,
            a_max=500.0,
        )
        df_vals = np.clip(
            np.maximum(np.asarray(dist.df, dtype=np.float64), 2.1),
            a_min=2.1,
            a_max=100.0,
        )

        return NGBoostStudentTDistribution(
            mu=mu,
            sigma=sigma,
            df=df_vals,
            candidate_id=self.model_id,
            metadata_dict={"family": "ngboost_student_t"},
        )


# =============================================================================
# CANDIDATE 5: Multi-Pinball Quantile Regression
# =============================================================================

class DepartureQuantileModel(BaseDepartureProbabilisticModel):
    """Candidate 5: Multi-pinball quantile regression across 9 pre-registered alphas.

    Note: Strictly does not support generative sampling without explicit interpolation.
    """

    def __init__(
        self,
        *,
        alphas: Sequence[float] = PRE_REGISTERED_QUANTILES,
        n_estimators: int = 50,
        learning_rate: float = 0.05,
        seed: int = SCREENING_SEED,
    ) -> None:
        super().__init__("departure_quantile_baseline_v1", seed=seed)
        self.alphas = tuple(alphas)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.preprocessor: DeparturePreprocessingPipeline | None = None
        self.models_: dict[float, lgb.LGBMRegressor] = {}

    def capabilities(self) -> DistributionCapabilities:
        return DistributionCapabilities(
            mean=False,
            median=True,
            quantile=True,
            cdf=False,
            probability_ge=False,
            sample=False,  # Discrete quantiles cannot sample continuously
            nll=False,
            crps_exact=False,
            crps_approx=False,
            pit=False,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> DepartureQuantileModel:
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor = DeparturePreprocessingPipeline(preprocessor_type="tree").fit(X)
        X_trans = self.preprocessor.transform(X)

        self.models_ = {}
        for alpha in self.alphas:
            model = lgb.LGBMRegressor(
                objective="quantile",
                alpha=alpha,
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                random_state=self.seed,
                n_jobs=4,
                verbosity=-1,
            )
            model.fit(X_trans, y_arr)
            self.models_[alpha] = model

        self.is_fitted = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> QuantilePredictiveDistribution:
        if not self.is_fitted or self.preprocessor is None:
            raise DistributionError("DepartureQuantileModel is not fitted")

        X_trans = self.preprocessor.transform(X)
        quantiles_dict = {
            float(alpha): self.models_[alpha].predict(X_trans).astype(np.float64)
            for alpha in self.alphas
        }

        return QuantilePredictiveDistribution(
            quantiles_dict=quantiles_dict,
            candidate_id=self.model_id,
            metadata_dict={"family": "quantile_regression"},
        )
