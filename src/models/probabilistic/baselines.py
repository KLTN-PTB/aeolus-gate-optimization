"""Implementation of Stage 1 Distributional Baselines (B1, B2, B3, B4, B5).

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Stage 1
Baselines:
- B1: Empirical carrier x scheduled-hour with hierarchical backoff.
- B2: XGBoost point mean + cross-fitted/OOF residual uncertainty (fixed-sigma Gaussian).
- B3: NGBoost Normal (heteroscedastic Gaussian).
- B4: LightGBM Quantile (multi-pinball regression).
- B5: NGBoost Student-T (heavy-tail candidate).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

import lightgbm as lgb
from ngboost import NGBRegressor
from ngboost.distns import Normal, T
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import norm, t as student_t
from sklearn.base import BaseEstimator
from sklearn.model_selection import KFold
from sklearn.preprocessing import OrdinalEncoder
import xgboost as xgb

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.metrics import (
    EVENT_THRESHOLDS,
    PRE_REGISTERED_QUANTILES,
    compute_gaussian_crps,
    compute_gaussian_event_probability,
    compute_gaussian_nll,
)

B1_MIN_SUPPORT: Final = 30


class TreePreprocessor:
    """Fold-safe ordinal and numeric preprocessor for tree-based baselines."""

    def __init__(self) -> None:
        self.numeric_cols = [
            "CRS_ELAPSED_TIME",
            "calendar_year",
            "calendar_month",
            "calendar_day_of_month",
            "calendar_day_of_week",
            "is_weekend",
            "scheduled_departure_hour",
            "scheduled_departure_minute",
        ]
        self.categorical_cols = ["OP_CARRIER", "ORIGIN", "OP_CARRIER_FL_NUM"]
        self.medians_: dict[str, float] = {}
        self.encoder_: OrdinalEncoder | None = None
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame) -> "TreePreprocessor":
        self.medians_ = {}
        for c in self.numeric_cols:
            vals = pd.to_numeric(X[c], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(vals)
            self.medians_[c] = float(np.median(vals[valid])) if np.any(valid) else 0.0

        cat_df = X[self.categorical_cols].astype(str).fillna("__MISSING__")
        self.encoder_ = OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
            encoded_missing_value=-1,
            dtype=np.float64,
        )
        self.encoder_.fit(cat_df)
        self.is_fitted_ = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_ or self.encoder_ is None:
            raise ProbabilisticContractViolation("TreePreprocessor is not fitted")

        n = len(X)
        num_arr = np.empty((n, len(self.numeric_cols)), dtype=np.float64)
        for i, c in enumerate(self.numeric_cols):
            vals = pd.to_numeric(X[c], errors="coerce").to_numpy(dtype=np.float64)
            med = self.medians_[c]
            num_arr[:, i] = np.where(np.isfinite(vals), vals, med)

        cat_df = X[self.categorical_cols].astype(str).fillna("__MISSING__")
        cat_arr = self.encoder_.transform(cat_df)

        return np.column_stack([num_arr, cat_arr])


# =========================================================================
# B1: Empirical carrier x scheduled-hour with hierarchical backoff
# =========================================================================

@dataclass(frozen=True)
class EmpiricalGroupStats:
    count: int
    mean: float
    sigma: float
    quantiles: dict[float, float]
    event_probs: dict[float, float]


class B1EmpiricalDistribution:
    """B1 — Empirical carrier x scheduled-hour distribution with backoff.

    Hierarchy: carrier x hour -> carrier -> global.
    """

    def __init__(self, *, min_support: int = B1_MIN_SUPPORT) -> None:
        self.min_support = min_support
        self.global_stats_: EmpiricalGroupStats | None = None
        self.carrier_stats_: dict[str, EmpiricalGroupStats] = {}
        self.carrier_hour_stats_: dict[tuple[str, int], EmpiricalGroupStats] = {}
        self.is_fitted_ = False

    def _calc_stats(self, values: np.ndarray) -> EmpiricalGroupStats:
        count = len(values)
        mean_val = float(np.mean(values))
        std_val = float(np.std(values))
        sigma_val = max(std_val, DEFAULT_SIGMA_FLOOR)
        q_dict = {
            float(alpha): float(np.quantile(values, alpha))
            for alpha in PRE_REGISTERED_QUANTILES
        }
        ev_dict = {
            float(thresh): float(np.mean(values >= thresh))
            for thresh in EVENT_THRESHOLDS
        }
        return EmpiricalGroupStats(
            count=count,
            mean=mean_val,
            sigma=sigma_val,
            quantiles=q_dict,
            event_probs=ev_dict,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "B1EmpiricalDistribution":
        y_arr = np.asarray(y, dtype=np.float64)
        carriers = X["OP_CARRIER"].astype(str).to_numpy()
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(0).astype(int).to_numpy()

        # Global stats
        self.global_stats_ = self._calc_stats(y_arr)

        # Carrier stats
        self.carrier_stats_ = {}
        unique_carriers = np.unique(carriers)
        for c in unique_carriers:
            c_mask = carriers == c
            if np.sum(c_mask) >= self.min_support:
                self.carrier_stats_[c] = self._calc_stats(y_arr[c_mask])

        # Carrier x hour stats
        self.carrier_hour_stats_ = {}
        df_tmp = pd.DataFrame({"carrier": carriers, "hour": hours, "y": y_arr})
        for (c, h), group in df_tmp.groupby(["carrier", "hour"]):
            if len(group) >= self.min_support:
                self.carrier_hour_stats_[(str(c), int(h))] = self._calc_stats(group["y"].to_numpy())

        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, Any]:
        if not self.is_fitted_ or self.global_stats_ is None:
            raise ProbabilisticContractViolation("B1 is not fitted")

        n = len(X)
        carriers = X["OP_CARRIER"].astype(str).to_numpy()
        hours = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").fillna(0).astype(int).to_numpy()

        mu = np.empty(n, dtype=np.float64)
        sigma = np.empty(n, dtype=np.float64)
        quantiles: dict[float, np.ndarray] = {
            alpha: np.empty(n, dtype=np.float64) for alpha in PRE_REGISTERED_QUANTILES
        }
        event_probs: dict[float, np.ndarray] = {
            thresh: np.empty(n, dtype=np.float64) for thresh in EVENT_THRESHOLDS
        }
        backoff_levels = []  # "carrier_hour", "carrier", "global"

        for i in range(n):
            key_ch = (carriers[i], hours[i])
            c = carriers[i]
            if key_ch in self.carrier_hour_stats_:
                stats = self.carrier_hour_stats_[key_ch]
                level = "carrier_hour"
            elif c in self.carrier_stats_:
                stats = self.carrier_stats_[c]
                level = "carrier"
            else:
                stats = self.global_stats_
                level = "global"

            mu[i] = stats.mean
            sigma[i] = stats.sigma
            for alpha in PRE_REGISTERED_QUANTILES:
                quantiles[alpha][i] = stats.quantiles[alpha]
            for thresh in EVENT_THRESHOLDS:
                event_probs[thresh][i] = stats.event_probs[thresh]
            backoff_levels.append(level)

        return {
            "mu": mu,
            "sigma": sigma,
            "quantiles": quantiles,
            "event_probs": event_probs,
            "backoff_levels": backoff_levels,
        }


# =========================================================================
# B2: XGBoost point mean + predictive uncertainty
# =========================================================================

class B2XGBoostGaussian:
    """B2 — XGBoost point mean + cross-fitted OOF residual uncertainty.

    Output distribution: Fixed-sigma Gaussian N(mu(X), sigma_OOF^2).
    """

    def __init__(
        self,
        *,
        n_estimators: int = 100,
        learning_rate: float = 0.05,
        max_depth: int = 6,
        seed: int = 202601,
        n_oof_splits: int = 3,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.seed = seed
        self.n_oof_splits = n_oof_splits
        self.preprocessor_ = TreePreprocessor()
        self.model_: xgb.XGBRegressor | None = None
        self.sigma_oof_: float = 0.0
        self.in_sample_sigma_: float = 0.0
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "B2XGBoostGaussian":
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor_.fit(X)
        X_trans = self.preprocessor_.transform(X)

        # 1. Generate cross-fitted OOF predictions strictly on outer-train
        kf = KFold(n_splits=self.n_oof_splits, shuffle=True, random_state=self.seed)
        oof_preds = np.empty_like(y_arr)

        for train_idx, val_idx in kf.split(X_trans):
            fold_model = xgb.XGBRegressor(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                objective="reg:absoluteerror",
                random_state=self.seed,
                n_jobs=1,
                tree_method="hist",
            )
            fold_model.fit(X_trans[train_idx], y_arr[train_idx])
            oof_preds[val_idx] = fold_model.predict(X_trans[val_idx])

        # 2. Compute OOF residuals and estimate sigma_oof
        oof_residuals = y_arr - oof_preds
        self.sigma_oof_ = max(float(np.std(oof_residuals)), DEFAULT_SIGMA_FLOOR)

        # 3. Fit final production point model on entire outer-train
        self.model_ = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            max_depth=self.max_depth,
            objective="reg:absoluteerror",
            random_state=self.seed,
            n_jobs=1,
            tree_method="hist",
        )
        self.model_.fit(X_trans, y_arr)

        # Audit check: compute in-sample sigma to prove they differ
        in_sample_preds = self.model_.predict(X_trans)
        self.in_sample_sigma_ = float(np.std(y_arr - in_sample_preds))

        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, Any]:
        if not self.is_fitted_ or self.model_ is None:
            raise ProbabilisticContractViolation("B2 is not fitted")

        X_trans = self.preprocessor_.transform(X)
        mu = self.model_.predict(X_trans).astype(np.float64)
        sigma = np.full_like(mu, self.sigma_oof_)

        quantiles = {}
        for alpha in PRE_REGISTERED_QUANTILES:
            z_alpha = norm.ppf(alpha)
            quantiles[alpha] = mu + z_alpha * sigma

        event_probs = {}
        for thresh in EVENT_THRESHOLDS:
            event_probs[thresh] = compute_gaussian_event_probability(mu, sigma, thresh)

        return {
            "mu": mu,
            "sigma": sigma,
            "quantiles": quantiles,
            "event_probs": event_probs,
            "distribution_type": "fixed_sigma_gaussian",
        }


# =========================================================================
# B3: NGBoost Normal (Heteroscedastic Gaussian)
# =========================================================================

class B3NGBoostNormal:
    """B3 — NGBoost Normal (heteroscedastic location and scale)."""

    def __init__(
        self,
        *,
        n_estimators: int = 60,
        learning_rate: float = 0.01,
        seed: int = 202601,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.seed = seed
        self.preprocessor_ = TreePreprocessor()
        self.model_: NGBRegressor | None = None
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "B3NGBoostNormal":
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor_.fit(X)
        X_trans = self.preprocessor_.transform(X)

        self.model_ = NGBRegressor(
            Dist=Normal,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            random_state=self.seed,
            verbose=False,
        )
        self.model_.fit(X_trans, y_arr)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, Any]:
        if not self.is_fitted_ or self.model_ is None:
            raise ProbabilisticContractViolation("B3 is not fitted")

        X_trans = self.preprocessor_.transform(X)
        dist = self.model_.pred_dist(X_trans)
        mu = dist.loc.astype(np.float64)
        sigma = np.clip(np.maximum(dist.scale.astype(np.float64), DEFAULT_SIGMA_FLOOR), a_min=DEFAULT_SIGMA_FLOOR, a_max=1000.0)

        quantiles = {}
        for alpha in PRE_REGISTERED_QUANTILES:
            z_alpha = norm.ppf(alpha)
            quantiles[alpha] = mu + z_alpha * sigma

        event_probs = {}
        for thresh in EVENT_THRESHOLDS:
            event_probs[thresh] = compute_gaussian_event_probability(mu, sigma, thresh)

        return {
            "mu": mu,
            "sigma": sigma,
            "quantiles": quantiles,
            "event_probs": event_probs,
            "distribution_type": "heteroscedastic_gaussian",
        }


# =========================================================================
# B4: LightGBM Quantile
# =========================================================================

class B4LightGBMQuantile:
    """B4 — LightGBM quantile regression across pre-registered alphas."""

    def __init__(
        self,
        *,
        alphas: Sequence[float] = PRE_REGISTERED_QUANTILES,
        n_estimators: int = 100,
        learning_rate: float = 0.05,
        seed: int = 202601,
    ) -> None:
        self.alphas = tuple(alphas)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.seed = seed
        self.preprocessor_ = TreePreprocessor()
        self.models_: dict[float, lgb.LGBMRegressor] = {}
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "B4LightGBMQuantile":
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor_.fit(X)
        X_trans = self.preprocessor_.transform(X)

        self.models_ = {}
        for alpha in self.alphas:
            model = lgb.LGBMRegressor(
                objective="quantile",
                alpha=alpha,
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                random_state=self.seed,
                n_jobs=1,
                verbosity=-1,
            )
            model.fit(X_trans, y_arr)
            self.models_[alpha] = model

        self.is_fitted_ = True
        return self

    def predict_quantiles(self, X: pd.DataFrame) -> dict[float, np.ndarray]:
        if not self.is_fitted_:
            raise ProbabilisticContractViolation("B4 is not fitted")

        X_trans = self.preprocessor_.transform(X)
        return {
            alpha: self.models_[alpha].predict(X_trans).astype(np.float64)
            for alpha in self.alphas
        }


# =========================================================================
# B5: NGBoost Student-T (Heavy-tail candidate)
# =========================================================================

class B5NGBoostStudentT:
    """B5 — NGBoost Student-T regression."""

    def __init__(
        self,
        *,
        n_estimators: int = 50,
        learning_rate: float = 0.005,
        seed: int = 202601,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.seed = seed
        self.preprocessor_ = TreePreprocessor()
        self.model_: NGBRegressor | None = None
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "B5NGBoostStudentT":
        y_arr = np.asarray(y, dtype=np.float64)
        self.preprocessor_.fit(X)
        X_trans = self.preprocessor_.transform(X)

        self.model_ = NGBRegressor(
            Dist=T,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            random_state=self.seed,
            verbose=False,
        )
        self.model_.fit(X_trans, y_arr)
        self.is_fitted_ = True
        return self

    def predict_distribution(self, X: pd.DataFrame) -> dict[str, Any]:
        if not self.is_fitted_ or self.model_ is None:
            raise ProbabilisticContractViolation("B5 is not fitted")

        X_trans = self.preprocessor_.transform(X)
        dist = self.model_.pred_dist(X_trans)
        mu = np.asarray(dist.loc, dtype=np.float64)
        sigma = np.maximum(np.asarray(dist.scale, dtype=np.float64), DEFAULT_SIGMA_FLOOR)
        df_vals = np.maximum(np.asarray(dist.df, dtype=np.float64), 2.1)

        quantiles = {}
        for alpha in PRE_REGISTERED_QUANTILES:
            t_alpha = student_t.ppf(alpha, df=df_vals)
            quantiles[alpha] = mu + t_alpha * sigma

        event_probs = {}
        for thresh in EVENT_THRESHOLDS:
            z = (thresh - mu) / sigma
            event_probs[thresh] = 1.0 - student_t.cdf(z, df=df_vals)

        return {
            "mu": mu,
            "sigma": sigma,
            "df": df_vals,
            "quantiles": quantiles,
            "event_probs": event_probs,
            "distribution_type": "student_t",
        }
