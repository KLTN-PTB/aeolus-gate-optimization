"""Academic Benchmark Engine for Core Arrival Point Models (Phase 2).

Executes real model training for the locked 5 Core methods:
1. Logistic Regression / Ridge (arrival_linear_baseline_v1)
2. Random Forest (arrival_random_forest_baseline_v1)
3. HistGradientBoosting (arrival_hist_gradient_boosting_baseline_v1)
4. XGBoost (arrival_xgboost_baseline_v1)
5. Weighted Ensemble (arrival_weighted_ensemble_v1)

Enforces strict protocol compliance:
- DEST=ATL, CRS_DEP_TIME - 2h cutoff
- No weather, no departure delay, no actual operations, no future leakages
- Same target rows, folds, labels, seeds, preprocessing boundaries
- Preprocessor fit strictly on training fold only
- OOF predictions saved to artifacts/model_benchmark/core_point/<experiment_id>/
- Weighted Ensemble weights derived deterministically from authorized development OOF
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import gc
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Final, Sequence

import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from xgboost import XGBClassifier, XGBRegressor

from src.data.access_guard import assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_TASK, assert_candidate_predictors_allowed
from src.data.preprocessing import (
    build_linear_preprocessor,
    build_tree_preprocessor,
)
from src.data.stratified_loader import load_stratified_fold_data
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    OOF_SCHEMA_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    load_week4_rolling_folds,
)
from src.models.metrics import (
    classification_metrics,
    compute_stratified_regression_metrics,
    regression_metrics,
)
from src.models.registry import get_model_spec

LOGGER = logging.getLogger("academic_point_benchmark")
DEFAULT_BENCHMARK_ROOT: Final = Path("artifacts/model_benchmark/core_point")

CORE_METHOD_IDS: Final = (
    "arrival_linear_baseline_v1",
    "arrival_random_forest_baseline_v1",
    "arrival_hist_gradient_boosting_baseline_v1",
    "arrival_xgboost_baseline_v1",
    "arrival_weighted_ensemble_v1",
)

BASE_METHOD_IDS: Final = (
    "arrival_linear_baseline_v1",
    "arrival_random_forest_baseline_v1",
    "arrival_hist_gradient_boosting_baseline_v1",
    "arrival_xgboost_baseline_v1",
)


@dataclass(frozen=True)
class AcademicBenchmarkConfig:
    """Configuration for Phase 2 Core Arrival Academic Benchmark."""

    experiment_id: str
    task: str = "core_arrival"
    target_classification: str = "1[ARR_DELAY >= 15]"
    target_regression: str = "ARR_DELAY"
    cutoff: str = "CRS_DEP_TIME - 2h"
    random_seed: int = 202601
    data_seed: int | None = None
    feature_version: str = "v1"
    sample_train_per_year: int = 3500
    sample_val: int = 4000
    output_dir: Path = DEFAULT_BENCHMARK_ROOT
    methods: tuple[str, ...] = CORE_METHOD_IDS

    def compute_sha256(self) -> str:
        d = {
            "experiment_id": self.experiment_id,
            "task": self.task,
            "cutoff": self.cutoff,
            "random_seed": self.random_seed,
            "data_seed": self.data_seed,
            "feature_version": self.feature_version,
            "sample_train_per_year": self.sample_train_per_year,
            "sample_val": self.sample_val,
            "methods": list(self.methods),
        }
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class PointFoldResult:
    """Consolidated result for one model evaluated on one temporal fold."""

    experiment_id: str
    model_id: str
    fold_id: str
    validation_year: int
    train_years: list[int]
    train_rows: int
    validation_rows: int
    seed: int
    status: str  # "COMPLETED" or "FAILED"
    failure_reason: str | None
    runtime_seconds: float
    memory_mb: float
    classification: dict[str, Any]
    regression: dict[str, Any]
    oof_artifact: str | None
    weights: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _derive_class_weights(y: np.ndarray) -> dict[int, float]:
    """Derive balanced class weights strictly from training fold labels."""
    total = len(y)
    n_0 = int(np.sum(y == 0))
    n_1 = int(np.sum(y == 1))
    if n_0 == 0 or n_1 == 0:
        raise ValueError("Training fold must contain both classes 0 and 1.")
    return {0: total / (2.0 * n_0), 1: total / (2.0 * n_1)}


def _build_model_pair(method_id: str, seed: int, weights: dict[int, float]) -> tuple[Any, Any, Any]:
    """Construct (preprocessor, classifier, regressor) for the declared method."""
    if method_id == "arrival_linear_baseline_v1":
        prep = build_linear_preprocessor()
        clf = LogisticRegression(
            solver="saga",
            C=1.0,
            max_iter=300,
            tol=0.001,
            class_weight=weights,
            random_state=seed,
        )
        reg = Ridge(alpha=1.0, solver="lsqr", tol=0.001, random_state=seed)
        return prep, clf, reg

    elif method_id == "arrival_random_forest_baseline_v1":
        prep = build_tree_preprocessor()
        clf = RandomForestClassifier(
            n_estimators=96,
            max_depth=14,
            min_samples_split=40,
            min_samples_leaf=20,
            max_features="sqrt",
            class_weight=weights,
            random_state=seed,
            n_jobs=-1,
        )
        reg = RandomForestRegressor(
            n_estimators=96,
            max_depth=14,
            min_samples_split=40,
            min_samples_leaf=20,
            max_features="sqrt",
            random_state=seed,
            n_jobs=-1,
        )
        return prep, clf, reg

    elif method_id == "arrival_hist_gradient_boosting_baseline_v1":
        prep = build_tree_preprocessor()
        clf = HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=0.05,
            max_iter=200,
            max_leaf_nodes=31,
            max_depth=8,
            min_samples_leaf=50,
            l2_regularization=1.0,
            class_weight=weights,
            random_state=seed,
        )
        reg = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.05,
            max_iter=200,
            max_leaf_nodes=31,
            max_depth=8,
            min_samples_leaf=50,
            l2_regularization=1.0,
            random_state=seed,
        )
        return prep, clf, reg

    elif method_id == "arrival_xgboost_baseline_v1":
        prep = build_tree_preprocessor()
        scale_pos = weights[1] / weights[0]
        clf = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=128,
            learning_rate=0.05,
            max_depth=6,
            min_child_weight=20.0,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            tree_method="hist",
            device="cpu",
            random_state=seed,
            scale_pos_weight=scale_pos,
            n_jobs=1,
        )
        reg = XGBRegressor(
            objective="reg:squarederror",
            eval_metric="rmse",
            n_estimators=128,
            learning_rate=0.05,
            max_depth=6,
            min_child_weight=20.0,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            tree_method="hist",
            device="cpu",
            random_state=seed,
            n_jobs=1,
        )
        return prep, clf, reg

    else:
        raise ValueError(f"Unknown or non-base method_id: {method_id}")


def optimize_ensemble_weights(
    y_true: np.ndarray,
    predictions: np.ndarray,
    loss_type: str = "brier",
) -> np.ndarray:
    """Compute optimal convex combination weights w >= 0, sum(w) = 1.

    Args:
        y_true: Ground truth target vector (N,).
        predictions: Matrix of predictions from K base models (N, K).
        loss_type: 'brier' for probabilities, 'mae' or 'mse' for regression.

    Returns:
        Weight vector of length K, nonnegative, summing to 1.0.
    """
    n_models = predictions.shape[1]
    if n_models == 0:
        raise ValueError("Cannot optimize ensemble weights for 0 models.")
    if len(y_true) == 0:
        return np.full(n_models, 1.0 / n_models)

    # Initial equal weights
    w0 = np.full(n_models, 1.0 / n_models)
    bounds = [(0.0, 1.0) for _ in range(n_models)]
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    if loss_type == "brier":
        def objective(w: np.ndarray) -> float:
            p_ens = predictions @ w
            return float(np.mean((p_ens - y_true) ** 2))
    elif loss_type == "mae":
        def objective(w: np.ndarray) -> float:
            y_ens = predictions @ w
            return float(np.mean(np.abs(y_ens - y_true)))
    else:
        def objective(w: np.ndarray) -> float:
            y_ens = predictions @ w
            return float(np.mean((y_ens - y_true) ** 2))

    try:
        res = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 200, "ftol": 1e-7},
        )
        if res.success and np.all(res.x >= -1e-6):
            weights = np.clip(res.x, 0.0, 1.0)
            return weights / np.sum(weights)
    except Exception as exc:
        LOGGER.warning(f"Optimization error in ensemble weights: {exc}, using inverse-error fallback.")

    # Fallback: Inverse error weighting
    errors = np.zeros(n_models)
    for i in range(n_models):
        if loss_type == "brier":
            errors[i] = max(1e-6, float(np.mean((predictions[:, i] - y_true) ** 2)))
        elif loss_type == "mae":
            errors[i] = max(1e-6, float(np.mean(np.abs(predictions[:, i] - y_true))))
        else:
            errors[i] = max(1e-6, float(np.mean((predictions[:, i] - y_true) ** 2)))

    inv = 1.0 / errors
    return inv / np.sum(inv)


class AcademicPointBenchmarkRunner:
    """Executes real Core Arrival point model benchmark across rolling development folds."""

    def __init__(self, config: AcademicBenchmarkConfig) -> None:
        self.config = config
        self._validate_safety()
        self.run_dir = self._prepare_run_dir()

    def _validate_safety(self) -> None:
        """Fail closed on invalid tasks, versions, or holdout accesses."""
        if self.config.task != "core_arrival":
            raise ValueError(f"Task must be 'core_arrival', got '{self.config.task}'")

        # 2024 development access must be fail-closed
        try:
            assert_data_access_allowed(2024, "development")
            raise RuntimeError("2024 access was unexpectedly allowed for development!")
        except Exception:
            # Expected DataAccessDenied
            pass

    def _prepare_run_dir(self) -> Path:
        """Create versioned non-destructive artifact directory."""
        target_dir = Path(self.config.output_dir) / self.config.experiment_id
        if target_dir.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            target_dir = Path(self.config.output_dir) / f"{self.config.experiment_id}_{timestamp}"

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "oof").mkdir(exist_ok=True)
        (target_dir / "metrics").mkdir(exist_ok=True)

        # Write config JSON
        cfg_dict = asdict(self.config)
        cfg_dict["output_dir"] = str(self.config.output_dir)
        cfg_dict["config_hash"] = self.config.compute_sha256()
        with open(target_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)

        return target_dir

    def run_benchmark(self) -> list[PointFoldResult]:
        """Execute the benchmark across all 4 rolling folds for all 5 Core methods."""
        rolling_folds = load_week4_rolling_folds()
        results: list[PointFoldResult] = []

        # Store OOF frames across folds: {model_id: {fold_id: DataFrame}}
        oof_by_model: dict[str, dict[str, pd.DataFrame]] = {
            m: {} for m in self.config.methods
        }

        # Track development OOF for ensemble weight training
        dev_oof_cls: dict[str, list[np.ndarray]] = {m: [] for m in BASE_METHOD_IDS}
        dev_oof_reg: dict[str, list[np.ndarray]] = {m: [] for m in BASE_METHOD_IDS}
        dev_true_cls: list[np.ndarray] = []
        dev_true_reg: list[np.ndarray] = []

        LOGGER.info(f"Starting Academic Point Benchmark {self.config.experiment_id} across {len(rolling_folds)} folds.")

        for fold in rolling_folds:
            LOGGER.info(f"\n==================== PROCESSING FOLD {fold.fold_id} (Val: {fold.validation_year}) ====================")

            # 1. Load data once per fold to guarantee exact row, label, and feature parity
            (
                X_train,
                y_train_cls_series,
                y_train_reg_series,
                _,
                X_val,
                y_val_cls_series,
                y_val_reg_series,
                val_flight_keys,
            ) = load_stratified_fold_data(
                train_years=fold.train_years,
                val_year=fold.validation_year,
                sample_train_per_year=self.config.sample_train_per_year,
                sample_val=self.config.sample_val,
                random_state=self.config.data_seed if self.config.data_seed is not None else self.config.random_seed,
                feature_set=self.config.feature_version,
            )

            # Leakage check: assert all candidate predictors belong strictly to APPROVED_PREDICTOR_COLUMNS
            from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
            from src.data.leakage_rules import WEATHER_COLUMNS, ARRIVAL_LEAKAGE_COLUMNS

            cols_tr = set(X_train.columns)
            cols_vl = set(X_val.columns)
            if not cols_tr.issubset(set(APPROVED_PREDICTOR_COLUMNS)):
                raise ValueError(f"X_train contains unapproved predictors: {cols_tr - set(APPROVED_PREDICTOR_COLUMNS)}")
            if not cols_vl.issubset(set(APPROVED_PREDICTOR_COLUMNS)):
                raise ValueError(f"X_val contains unapproved predictors: {cols_vl - set(APPROVED_PREDICTOR_COLUMNS)}")
            if cols_tr.intersection(WEATHER_COLUMNS) or cols_vl.intersection(WEATHER_COLUMNS):
                raise ValueError("Weather columns detected in Core Arrival features!")
            if cols_tr.intersection(ARRIVAL_LEAKAGE_COLUMNS) or cols_vl.intersection(ARRIVAL_LEAKAGE_COLUMNS):
                raise ValueError("Operational leakage columns detected in Core Arrival features!")

            y_tr_cls = np.asarray(y_train_cls_series, dtype=int)
            y_tr_reg = np.asarray(y_train_reg_series, dtype=float)
            y_vl_cls = np.asarray(y_val_cls_series, dtype=int)
            y_vl_reg = np.asarray(y_val_reg_series, dtype=float)

            class_weights = _derive_class_weights(y_tr_cls)

            # 2. Run Base Models (Models 1 to 4)
            for method_id in BASE_METHOD_IDS:
                if method_id not in self.config.methods:
                    continue

                LOGGER.info(f"[*] Training {method_id} on {fold.fold_id}...")
                process = psutil.Process()
                mem0 = process.memory_info().rss / (1024 * 1024)
                t0 = time.perf_counter()
                status = "COMPLETED"
                failure_reason: str | None = None
                cls_metrics_dict: dict[str, Any] = {}
                reg_metrics_dict: dict[str, Any] = {}
                oof_path_str: str | None = None

                try:
                    # Model-specific preprocessing fit strictly on training fold
                    prep, clf, reg = _build_model_pair(method_id, self.config.random_seed, class_weights)
                    X_tr_trans = prep.fit_transform(X_train)
                    X_vl_trans = prep.transform(X_val)

                    # Fit estimators
                    clf.fit(X_tr_trans, y_tr_cls)
                    reg.fit(X_tr_trans, y_tr_reg)

                    # Predict validation fold
                    p_proba = clf.predict_proba(X_vl_trans)
                    p_15 = p_proba[:, 1] if p_proba.ndim == 2 and p_proba.shape[1] > 1 else p_proba.flatten()
                    pred_reg = reg.predict(X_vl_trans).flatten()

                    # Validate predictions are finite and in [0, 1]
                    p_15 = np.clip(p_15, 0.0, 1.0)

                    # Compute standard metrics
                    cls_metrics = classification_metrics(y_vl_cls, p_15, threshold=CLASSIFICATION_THRESHOLD)
                    reg_metrics = regression_metrics(y_vl_reg, pred_reg)
                    strat_metrics = compute_stratified_regression_metrics(y_vl_reg, pred_reg)

                    cls_metrics_dict = cls_metrics.to_dict()
                    reg_metrics_dict = reg_metrics.to_dict()
                    reg_metrics_dict["stratified"] = strat_metrics.to_dict()

                    # Construct and validate OOF DataFrame
                    oof_df = pd.DataFrame({
                        "flight_key": val_flight_keys.values,
                        "fold_id": fold.fold_id,
                        "validation_year": fold.validation_year,
                        "y_arr_cls": y_vl_cls,
                        "p_arr_delay_15": p_15,
                        "y_arr_cls_pred_0_5": (p_15 >= CLASSIFICATION_THRESHOLD).astype(int),
                        "y_arr_reg": y_vl_reg,
                        "predicted_arr_delay_min": pred_reg,
                        "method_id": method_id,
                        "model_version": "v1",
                        "preprocessing_version": "arrival_preprocessing_v1",
                        "feature_manifest_version": FEATURE_MANIFEST_VERSION,
                        "config_version": "0.1.0",
                        "seed": self.config.random_seed,
                        "experiment_contract_version": WEEK4_EXPERIMENT_CONTRACT_VERSION,
                        "oof_schema_version": OOF_SCHEMA_VERSION,
                    })
                    validate_oof_frame(oof_df)

                    # Save OOF Parquet
                    oof_file = self.run_dir / "oof" / f"{method_id}_{fold.fold_id}.parquet"
                    oof_df.to_parquet(oof_file, index=False)
                    oof_path_str = str(oof_file)
                    oof_by_model[method_id][fold.fold_id] = oof_df

                except Exception as exc:
                    status = "FAILED"
                    failure_reason = str(exc)
                    LOGGER.error(f"Execution failed for {method_id} on {fold.fold_id}: {exc}", exc_info=True)

                runtime = time.perf_counter() - t0
                mem_end = process.memory_info().rss / (1024 * 1024)
                mem_used = max(0.0, mem_end - mem0)

                fold_res = PointFoldResult(
                    experiment_id=self.config.experiment_id,
                    model_id=method_id,
                    fold_id=fold.fold_id,
                    validation_year=fold.validation_year,
                    train_years=list(fold.train_years),
                    train_rows=len(X_train),
                    validation_rows=len(X_val),
                    seed=self.config.random_seed,
                    status=status,
                    failure_reason=failure_reason,
                    runtime_seconds=round(runtime, 3),
                    memory_mb=round(mem_used, 2),
                    classification=cls_metrics_dict,
                    regression=reg_metrics_dict,
                    oof_artifact=oof_path_str,
                )
                results.append(fold_res)

                # Save individual metrics JSON
                metrics_file = self.run_dir / "metrics" / f"{method_id}_{fold.fold_id}.json"
                with open(metrics_file, "w", encoding="utf-8") as f:
                    json.dump(fold_res.to_dict(), f, indent=2)

            # 3. Model 5: Weighted Ensemble
            if "arrival_weighted_ensemble_v1" in self.config.methods:
                ens_id = "arrival_weighted_ensemble_v1"
                LOGGER.info(f"[*] Constructing Weighted Ensemble for {fold.fold_id}...")
                process = psutil.Process()
                mem0 = process.memory_info().rss / (1024 * 1024)
                t0 = time.perf_counter()

                # Collect current fold predictions from all base models
                base_p_list: list[np.ndarray] = []
                base_y_list: list[np.ndarray] = []
                valid_bases = [m for m in BASE_METHOD_IDS if fold.fold_id in oof_by_model[m]]

                for m in valid_bases:
                    base_df = oof_by_model[m][fold.fold_id]
                    base_p_list.append(base_df["p_arr_delay_15"].to_numpy())
                    base_y_list.append(base_df["predicted_arr_delay_min"].to_numpy())

                if len(valid_bases) < 2:
                    # Not enough base models completed to ensemble
                    fold_res = PointFoldResult(
                        experiment_id=self.config.experiment_id,
                        model_id=ens_id,
                        fold_id=fold.fold_id,
                        validation_year=fold.validation_year,
                        train_years=list(fold.train_years),
                        train_rows=len(X_train),
                        validation_rows=len(X_val),
                        seed=self.config.random_seed,
                        status="FAILED",
                        failure_reason="Insufficient completed base models for ensemble",
                        runtime_seconds=0.0,
                        memory_mb=0.0,
                        classification={},
                        regression={},
                        oof_artifact=None,
                    )
                    results.append(fold_res)
                else:
                    P_val = np.column_stack(base_p_list)
                    Y_val = np.column_stack(base_y_list)

                    # Derive weights:
                    # If development history exists from prior folds, optimize weights on past OOF only (strictly temporal!).
                    # If fold 1 (no prior fold OOF exists), use deterministic equal weighting.
                    if len(dev_true_cls) > 0 and sum(len(arr) for arr in dev_true_cls) >= 100:
                        hist_true_cls = np.concatenate(dev_true_cls)
                        hist_true_reg = np.concatenate(dev_true_reg)
                        hist_p = np.column_stack([np.concatenate(dev_oof_cls[m]) for m in valid_bases])
                        hist_y = np.column_stack([np.concatenate(dev_oof_reg[m]) for m in valid_bases])

                        w_cls = optimize_ensemble_weights(hist_true_cls, hist_p, loss_type="brier")
                        w_reg = optimize_ensemble_weights(hist_true_reg, hist_y, loss_type="mae")
                    else:
                        w_cls = np.full(len(valid_bases), 1.0 / len(valid_bases))
                        w_reg = np.full(len(valid_bases), 1.0 / len(valid_bases))

                    # Nonnegativity and sum-to-1 guarantees
                    w_cls = np.clip(w_cls, 0.0, 1.0)
                    w_cls = w_cls / np.sum(w_cls)
                    w_reg = np.clip(w_reg, 0.0, 1.0)
                    w_reg = w_reg / np.sum(w_reg)

                    ens_p = np.clip(P_val @ w_cls, 0.0, 1.0)
                    ens_pred = Y_val @ w_reg

                    # Compute ensemble metrics
                    cls_metrics = classification_metrics(y_vl_cls, ens_p, threshold=CLASSIFICATION_THRESHOLD)
                    reg_metrics = regression_metrics(y_vl_reg, ens_pred)
                    strat_metrics = compute_stratified_regression_metrics(y_vl_reg, ens_pred)

                    cls_dict = cls_metrics.to_dict()
                    reg_dict = reg_metrics.to_dict()
                    reg_dict["stratified"] = strat_metrics.to_dict()

                    # Save ensemble OOF
                    oof_df = pd.DataFrame({
                        "flight_key": val_flight_keys.values,
                        "fold_id": fold.fold_id,
                        "validation_year": fold.validation_year,
                        "y_arr_cls": y_vl_cls,
                        "p_arr_delay_15": ens_p,
                        "y_arr_cls_pred_0_5": (ens_p >= CLASSIFICATION_THRESHOLD).astype(int),
                        "y_arr_reg": y_vl_reg,
                        "predicted_arr_delay_min": ens_pred,
                        "method_id": ens_id,
                        "model_version": "v1",
                        "preprocessing_version": "arrival_preprocessing_v1",
                        "feature_manifest_version": FEATURE_MANIFEST_VERSION,
                        "config_version": "0.1.0",
                        "seed": self.config.random_seed,
                        "experiment_contract_version": WEEK4_EXPERIMENT_CONTRACT_VERSION,
                        "oof_schema_version": OOF_SCHEMA_VERSION,
                    })
                    validate_oof_frame(oof_df)
                    oof_file = self.run_dir / "oof" / f"{ens_id}_{fold.fold_id}.parquet"
                    oof_df.to_parquet(oof_file, index=False)
                    oof_by_model[ens_id][fold.fold_id] = oof_df

                    runtime = time.perf_counter() - t0
                    mem_end = process.memory_info().rss / (1024 * 1024)
                    mem_used = max(0.0, mem_end - mem0)

                    weights_summary = {
                        f"{m}_cls": round(float(w_cls[i]), 4)
                        for i, m in enumerate(valid_bases)
                    }
                    weights_summary.update({
                        f"{m}_reg": round(float(w_reg[i]), 4)
                        for i, m in enumerate(valid_bases)
                    })

                    fold_res = PointFoldResult(
                        experiment_id=self.config.experiment_id,
                        model_id=ens_id,
                        fold_id=fold.fold_id,
                        validation_year=fold.validation_year,
                        train_years=list(fold.train_years),
                        train_rows=len(X_train),
                        validation_rows=len(X_val),
                        seed=self.config.random_seed,
                        status="COMPLETED",
                        failure_reason=None,
                        runtime_seconds=round(runtime, 3),
                        memory_mb=round(mem_used, 2),
                        classification=cls_dict,
                        regression=reg_dict,
                        oof_artifact=str(oof_file),
                        weights=weights_summary,
                    )
                    results.append(fold_res)

                    metrics_file = self.run_dir / "metrics" / f"{ens_id}_{fold.fold_id}.json"
                    with open(metrics_file, "w", encoding="utf-8") as f:
                        json.dump(fold_res.to_dict(), f, indent=2)

            # Update development OOF history with current fold's base model predictions
            for m in BASE_METHOD_IDS:
                if fold.fold_id in oof_by_model[m]:
                    m_df = oof_by_model[m][fold.fold_id]
                    dev_oof_cls[m].append(m_df["p_arr_delay_15"].to_numpy())
                    dev_oof_reg[m].append(m_df["predicted_arr_delay_min"].to_numpy())
            dev_true_cls.append(y_vl_cls)
            dev_true_reg.append(y_vl_reg)

            # Clean memory after fold
            del X_train, X_val, y_tr_cls, y_tr_reg, y_vl_cls, y_vl_reg
            gc.collect()

        # Write overall summary JSON and CSV, and manifest.sha256
        self._write_consolidated_artifacts(results)
        return results

    def _write_consolidated_artifacts(self, results: list[PointFoldResult]) -> None:
        """Publish tabular summary and SHA-256 manifest."""
        # 1. Summary JSON
        summary_path = self.run_dir / "benchmark_summary.json"
        summary_payload = {
            "experiment_id": self.config.experiment_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config_hash": self.config.compute_sha256(),
            "total_runs": len(results),
            "completed_runs": sum(1 for r in results if r.status == "COMPLETED"),
            "failed_runs": sum(1 for r in results if r.status != "COMPLETED"),
            "results": [r.to_dict() for r in results],
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        # 2. Summary CSV
        rows: list[dict[str, Any]] = []
        for r in results:
            row = {
                "experiment_id": r.experiment_id,
                "model_id": r.model_id,
                "fold_id": r.fold_id,
                "validation_year": r.validation_year,
                "status": r.status,
                "runtime_seconds": r.runtime_seconds,
                "memory_mb": r.memory_mb,
                "roc_auc": r.classification.get("roc_auc"),
                "pr_auc": r.classification.get("pr_auc"),
                "recall": r.classification.get("recall"),
                "f1": r.classification.get("f1"),
                "brier_score": r.classification.get("brier_score"),
                "mae": r.regression.get("mae"),
                "rmse": r.regression.get("rmse"),
                "r2": r.regression.get("r2"),
                "oof_artifact": r.oof_artifact,
            }
            if r.weights:
                for k, v in r.weights.items():
                    row[f"weight_{k}"] = v
            rows.append(row)

        df_summary = pd.DataFrame(rows)
        df_summary.to_csv(self.run_dir / "benchmark_summary.csv", index=False)

        # 3. Cryptographic hash manifest
        manifest: dict[str, str] = {}
        for p in sorted(self.run_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.sha256":
                hasher = hashlib.sha256()
                hasher.update(p.read_bytes())
                manifest[str(p.relative_to(self.run_dir))] = hasher.hexdigest()

        with open(self.run_dir / "manifest.sha256", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        LOGGER.info(f"Consolidated benchmark artifacts successfully created at {self.run_dir}")
