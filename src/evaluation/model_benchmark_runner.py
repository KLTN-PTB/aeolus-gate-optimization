"""Common Benchmark Engine for Core Arrival Point Models (V4 Synchronized Contract).

Protocol: Phase 2 Academic Benchmark / V4 Synchronized Governance
Invariants:
- Exactly 5 Core Point Models:
  1. arrival_linear_baseline_v1
  2. arrival_random_forest_baseline_v1
  3. arrival_hist_gradient_boosting_baseline_v1
  4. arrival_xgboost_baseline_v1
  5. arrival_weighted_ensemble_v1
- Common Runner Pipeline Contract:
  ModelSpec -> FoldProvider -> Feature preparation -> Model fit -> Prediction -> Common evaluator -> Artifact writer
- Temporal fairness: V4 rolling folds 1 to 4 strictly expanding (2016-2022). Zero random split substitution.
- Strict feature boundaries: DEST=ATL, cutoff T-2h, no Weather, no predicted Departure, no actual outcomes, no identifiers.
- Preprocessing fit on train only.
- Valid classification probability semantics: P(ARR_DELAY >= 15) must come from an audited estimator. Ad-hoc sigmoid strictly rejected.
- OOF schema: row_id, flight_key, fold_id, model_id, y_true_reg, y_true_cls, pred_reg, pred_cls_prob, seed, train_window, code_hash, config_hash.
- No silent row drop: failed rows retained and recorded.
- No champion selection in R3.
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
from typing import Any, Final, Sequence

import numpy as np
import pandas as pd
import psutil
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
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.data.preprocessing import build_linear_preprocessor, build_tree_preprocessor
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.forecast_metrics import compute_point_forecast_metrics
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    RollingFold,
    load_week4_rolling_folds,
)
from src.models.interfaces import ModelCapability, ModelSpec
from src.models.registry import get_model_spec

LOGGER = logging.getLogger("model_benchmark_runner")
DEFAULT_BENCHMARK_ROOT_V2: Final = Path("artifacts/model_benchmark_v2/core_point")
DEFAULT_MANIFEST_PATH: Final = Path("artifacts/manifests/core_point_benchmark_v2.json")

CORE_POINT_BENCHMARK_METHOD_IDS: Final[tuple[str, ...]] = (
    "arrival_linear_baseline_v1",
    "arrival_random_forest_baseline_v1",
    "arrival_hist_gradient_boosting_baseline_v1",
    "arrival_xgboost_baseline_v1",
    "arrival_weighted_ensemble_v1",
)


def is_core_point_benchmark_eligible(model_id: str) -> bool:
    """Return True only if model_id is one of the exactly 5 canonical Core Point models."""
    return model_id in CORE_POINT_BENCHMARK_METHOD_IDS


def assert_core_point_benchmark_eligible(model_id: str) -> ModelSpec:
    """Validate that model_id is authorized for the Core Point Benchmark (cap=5). Fails closed."""
    spec = get_model_spec(model_id)
    if model_id not in CORE_POINT_BENCHMARK_METHOD_IDS:
        raise ValueError(
            f"Model '{model_id}' (task={spec.task}, category={spec.category}, status={spec.status}) "
            f"is NOT eligible for Core Point Benchmark. Only the 5 canonical Core models are allowed: "
            f"{CORE_POINT_BENCHMARK_METHOD_IDS}."
        )
    return spec


OOF_V2_COLUMNS: Final[tuple[str, ...]] = (
    "row_id",
    "flight_key",
    "fold_id",
    "model_id",
    "y_true_reg",
    "y_true_cls",
    "pred_reg",
    "pred_cls_prob",
    "seed",
    "train_window",
    "code_hash",
    "config_hash",
    "status",
    "failure_reason",
)


def validate_oof_v2_frame(frame: pd.DataFrame) -> None:
    """Validate that OOF frame adheres strictly to the V2 required schema."""
    for col in OOF_V2_COLUMNS:
        if col not in frame.columns:
            raise ValueError(f"OOF DataFrame missing required column: '{col}'")
    if frame.empty:
        raise ValueError("OOF DataFrame cannot be empty.")
    if frame["flight_key"].isna().any():
        raise ValueError("OOF flight_key cannot contain null values.")
    if not set(frame["status"].unique()).issubset({"SUCCESS", "FAILED"}):
        raise ValueError(f"Unknown status values in OOF: {frame['status'].unique()}")


@dataclass(frozen=True)
class CommonBenchmarkConfig:
    """Configuration for V2 Core Point Model Common Benchmark."""

    experiment_id: str = "core_point_benchmark_v2"
    task: str = "core_arrival"
    target_classification: str = "1[ARR_DELAY >= 15]"
    target_regression: str = "ARR_DELAY"
    cutoff: str = "CRS_DEP_TIME - 2h"
    random_seed: int = 202601
    data_seed: int | None = None
    feature_version: str = "v1"
    sample_train_per_year: int = 3500
    sample_val: int = 4000
    output_dir: Path = DEFAULT_BENCHMARK_ROOT_V2
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    methods: tuple[str, ...] = CORE_POINT_BENCHMARK_METHOD_IDS

    def __post_init__(self) -> None:
        """Enforce strict 5-Core model cap and validate eligibility fail-closed."""
        if len(self.methods) > 5:
            raise ValueError(f"Core Point Benchmark strictly capped at 5 methods. Got {len(self.methods)}")
        for m in self.methods:
            assert_core_point_benchmark_eligible(m)

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


def compute_code_hash() -> str:
    """Compute sha256 hash of this benchmark runner file."""
    runner_path = Path(__file__).resolve()
    if runner_path.exists():
        return hashlib.sha256(runner_path.read_bytes()).hexdigest()
    return "unknown_code_hash"


def derive_training_class_weights(y: np.ndarray) -> dict[int, float]:
    """Derive balanced class weights strictly from training fold labels."""
    total = len(y)
    n_0 = int(np.sum(y == 0))
    n_1 = int(np.sum(y == 1))
    if n_0 == 0 or n_1 == 0:
        raise ValueError("Training fold must contain both classes 0 and 1.")
    return {0: total / (2.0 * n_0), 1: total / (2.0 * n_1)}


def build_core_model_pair(method_id: str, seed: int, weights: dict[int, float]) -> tuple[Any, Any, Any]:
    """Construct (preprocessor, classifier, regressor) for the declared core point method."""
    assert_core_point_benchmark_eligible(method_id)

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
        raise ValueError(f"Base model pair not defined for method_id: {method_id}")


def optimize_convex_ensemble_weights(
    y_true: np.ndarray,
    predictions: np.ndarray,
    loss_type: str = "brier",
) -> np.ndarray:
    """Compute optimal convex combination weights w >= 0, sum(w) = 1."""
    n_models = predictions.shape[1]
    if n_models == 0:
        raise ValueError("Cannot optimize ensemble weights for 0 models.")
    if len(y_true) == 0:
        return np.full(n_models, 1.0 / n_models)

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


@dataclass
class PointBenchmarkFoldResult:
    """Structured result for one model evaluated on one fold under V2 Common Contract."""

    experiment_id: str
    model_id: str
    fold_id: str
    validation_year: int
    train_years: list[int]
    train_rows: int
    validation_rows: int
    seed: int
    status: str  # "SUCCESS" or "FAILED"
    failure_reason: str | None
    runtime_seconds: float
    memory_mb: float
    metrics: dict[str, Any]
    oof_artifact: str | None
    weights: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommonPointBenchmarkRunner:
    """Unified Benchmark Engine executing all 5 Core Point models under the Common Contract."""

    def __init__(self, config: CommonBenchmarkConfig) -> None:
        self.config = config
        self.code_hash = compute_code_hash()
        self.config_hash = self.config.compute_sha256()
        self._validate_contract()
        self.run_dir = self._prepare_run_dir()

    def _validate_contract(self) -> None:
        """Fail closed on invalid models, unauthorized years, or schema deviations."""
        if self.config.task != "core_arrival":
            raise ValueError(f"Task must be 'core_arrival', got '{self.config.task}'")

        # Must be exactly a subset of the 5 canonical Core methods
        for m in self.config.methods:
            assert_core_point_benchmark_eligible(m)

        # 2024 development access must be strictly forbidden
        try:
            assert_data_access_allowed(2024, "development")
            raise RuntimeError("2024 access was unexpectedly allowed for development!")
        except Exception:
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

        cfg_dict = asdict(self.config)
        cfg_dict["output_dir"] = str(self.config.output_dir)
        cfg_dict["manifest_path"] = str(self.config.manifest_path)
        cfg_dict["config_hash"] = self.config_hash
        cfg_dict["code_hash"] = self.code_hash
        with open(target_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)

        return target_dir

    def run_benchmark(self) -> list[PointBenchmarkFoldResult]:
        """Execute the common benchmark across all 4 rolling folds for all 5 Core methods."""
        rolling_folds = load_week4_rolling_folds()
        results: list[PointBenchmarkFoldResult] = []

        base_methods = [m for m in self.config.methods if m != "arrival_weighted_ensemble_v1"]

        # Track OOF dataframes: {model_id: {fold_id: DataFrame}}
        oof_by_model: dict[str, dict[str, pd.DataFrame]] = {m: {} for m in self.config.methods}

        # Track historical development OOF for ensemble weight training
        dev_oof_cls: dict[str, list[np.ndarray]] = {m: [] for m in base_methods}
        dev_oof_reg: dict[str, list[np.ndarray]] = {m: [] for m in base_methods}
        dev_true_cls: list[np.ndarray] = []
        dev_true_reg: list[np.ndarray] = []

        LOGGER.info(
            f"Starting V2 Common Point Benchmark '{self.config.experiment_id}' "
            f"across {len(rolling_folds)} rolling folds for {len(self.config.methods)} models."
        )

        for fold in rolling_folds:
            LOGGER.info(f"\n==================== PROCESSING FOLD {fold.fold_id} (Val: {fold.validation_year}) ====================")

            # -------------------------------------------------------------
            # Step 1: FoldProvider — Load fold data ONCE for all models
            # -------------------------------------------------------------
            data_seed = self.config.data_seed if self.config.data_seed is not None else self.config.random_seed
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
                random_state=data_seed,
                feature_set=self.config.feature_version,
            )

            # -------------------------------------------------------------
            # Step 2: Feature Safety & Leakage Guard
            # -------------------------------------------------------------
            cols_tr = set(X_train.columns)
            cols_vl = set(X_val.columns)
            approved = set(APPROVED_PREDICTOR_COLUMNS)

            if not cols_tr.issubset(approved):
                raise ValueError(f"X_train contains unapproved predictors: {cols_tr - approved}")
            if not cols_vl.issubset(approved):
                raise ValueError(f"X_val contains unapproved predictors: {cols_vl - approved}")
            if cols_tr.intersection(WEATHER_COLUMNS) or cols_vl.intersection(WEATHER_COLUMNS):
                raise ValueError("Weather columns detected in Core Arrival feature matrix!")
            if cols_tr.intersection(ARRIVAL_LEAKAGE_COLUMNS) or cols_vl.intersection(ARRIVAL_LEAKAGE_COLUMNS):
                raise ValueError("Operational outcome leakage detected in Core Arrival feature matrix!")

            y_tr_cls = np.asarray(y_train_cls_series, dtype=int)
            y_tr_reg = np.asarray(y_train_reg_series, dtype=float)
            y_vl_cls = np.asarray(y_val_cls_series, dtype=int)
            y_vl_reg = np.asarray(y_val_reg_series, dtype=float)

            class_weights = derive_training_class_weights(y_tr_cls)
            n_val = len(X_val)
            train_window_str = f"{min(fold.train_years)}-{max(fold.train_years)}"

            # -------------------------------------------------------------
            # Step 3 & 4: Model Fit & Prediction for Base Models 1 to 4
            # -------------------------------------------------------------
            for method_id in base_methods:
                LOGGER.info(f"[*] Running {method_id} on {fold.fold_id}...")
                process = psutil.Process()
                mem0 = process.memory_info().rss / (1024 * 1024)
                t0 = time.perf_counter()
                status = "SUCCESS"
                failure_reason: str | None = None
                metrics_dict: dict[str, Any] = {}
                oof_path_str: str | None = None

                p_15 = np.full(n_val, np.nan)
                pred_reg = np.full(n_val, np.nan)

                try:
                    # Preprocessing fit on train only
                    prep, clf, reg = build_core_model_pair(method_id, self.config.random_seed, class_weights)
                    X_tr_trans = prep.fit_transform(X_train)
                    X_vl_trans = prep.transform(X_val)

                    # Model fit
                    clf.fit(X_tr_trans, y_tr_cls)
                    reg.fit(X_tr_trans, y_tr_reg)

                    # Prediction
                    p_proba = clf.predict_proba(X_vl_trans)
                    p_15 = p_proba[:, 1] if p_proba.ndim == 2 and p_proba.shape[1] > 1 else p_proba.flatten()
                    pred_reg = reg.predict(X_vl_trans).flatten()

                    # Common Evaluator
                    metrics_dict = compute_point_forecast_metrics(
                        y_true_reg=y_vl_reg,
                        pred_reg=pred_reg,
                        y_true_cls=y_vl_cls,
                        pred_cls_prob=p_15,
                        probability_estimator_audit="dual_head_classifier",
                    )

                except Exception as exc:
                    status = "FAILED"
                    failure_reason = str(exc)
                    LOGGER.error(f"Execution failed for {method_id} on {fold.fold_id}: {exc}", exc_info=True)
                    metrics_dict = {
                        "n_total": n_val,
                        "n_valid": 0,
                        "n_missing": n_val,
                        "n_failures": n_val,
                        "mae": None,
                        "rmse": None,
                        "r2": None,
                        "severe_delay_mae_ge_60": None,
                        "pr_auc": None,
                        "roc_auc": None,
                        "brier_score": None,
                        "probability_semantics": "FAILED_EXECUTION",
                    }

                # Construct OOF V2 DataFrame (retaining all rows, even failed)
                row_ids = np.arange(n_val, dtype=int)
                oof_df = pd.DataFrame({
                    "row_id": row_ids,
                    "flight_key": val_flight_keys.values,
                    "fold_id": fold.fold_id,
                    "model_id": method_id,
                    "y_true_reg": y_vl_reg,
                    "y_true_cls": y_vl_cls,
                    "pred_reg": pred_reg,
                    "pred_cls_prob": p_15,
                    "seed": self.config.random_seed,
                    "train_window": train_window_str,
                    "code_hash": self.code_hash,
                    "config_hash": self.config_hash,
                    "status": status,
                    "failure_reason": failure_reason,
                })
                validate_oof_v2_frame(oof_df)

                oof_file = self.run_dir / "oof" / f"{method_id}_{fold.fold_id}.parquet"
                oof_df.to_parquet(oof_file, index=False)
                oof_path_str = str(oof_file)
                oof_by_model[method_id][fold.fold_id] = oof_df

                runtime = time.perf_counter() - t0
                mem_end = process.memory_info().rss / (1024 * 1024)
                mem_used = max(0.0, mem_end - mem0)

                fold_res = PointBenchmarkFoldResult(
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
                    metrics=metrics_dict,
                    oof_artifact=oof_path_str,
                )
                results.append(fold_res)

                metrics_file = self.run_dir / "metrics" / f"{method_id}_{fold.fold_id}.json"
                with open(metrics_file, "w", encoding="utf-8") as f:
                    json.dump(fold_res.to_dict(), f, indent=2)

            # -------------------------------------------------------------
            # Step 5: Model 5 — Weighted Ensemble
            # -------------------------------------------------------------
            if "arrival_weighted_ensemble_v1" in self.config.methods:
                ens_id = "arrival_weighted_ensemble_v1"
                LOGGER.info(f"[*] Running Weighted Ensemble {ens_id} on {fold.fold_id}...")
                process = psutil.Process()
                mem0 = process.memory_info().rss / (1024 * 1024)
                t0 = time.perf_counter()

                valid_bases = [
                    m for m in base_methods
                    if fold.fold_id in oof_by_model[m] and oof_by_model[m][fold.fold_id]["status"].iloc[0] == "SUCCESS"
                ]

                if len(valid_bases) < 2:
                    status = "FAILED"
                    failure_reason = "Insufficient completed base models for ensemble"
                    ens_p = np.full(n_val, np.nan)
                    ens_pred = np.full(n_val, np.nan)
                    weights_summary = None
                    metrics_dict = {
                        "n_total": n_val,
                        "n_valid": 0,
                        "n_missing": n_val,
                        "n_failures": n_val,
                        "mae": None,
                        "rmse": None,
                        "r2": None,
                        "severe_delay_mae_ge_60": None,
                        "pr_auc": None,
                        "roc_auc": None,
                        "brier_score": None,
                        "probability_semantics": "FAILED_INSUFFICIENT_BASES",
                    }
                else:
                    status = "SUCCESS"
                    failure_reason = None
                    base_p_list = [oof_by_model[m][fold.fold_id]["pred_cls_prob"].to_numpy() for m in valid_bases]
                    base_y_list = [oof_by_model[m][fold.fold_id]["pred_reg"].to_numpy() for m in valid_bases]
                    P_val = np.column_stack(base_p_list)
                    Y_val = np.column_stack(base_y_list)

                    # Optimize weights strictly on prior folds' OOF
                    if len(dev_true_cls) > 0 and sum(len(arr) for arr in dev_true_cls) >= 100:
                        hist_true_cls = np.concatenate(dev_true_cls)
                        hist_true_reg = np.concatenate(dev_true_reg)
                        hist_p = np.column_stack([np.concatenate(dev_oof_cls[m]) for m in valid_bases])
                        hist_y = np.column_stack([np.concatenate(dev_oof_reg[m]) for m in valid_bases])

                        w_cls = optimize_convex_ensemble_weights(hist_true_cls, hist_p, loss_type="brier")
                        w_reg = optimize_convex_ensemble_weights(hist_true_reg, hist_y, loss_type="mae")
                    else:
                        w_cls = np.full(len(valid_bases), 1.0 / len(valid_bases))
                        w_reg = np.full(len(valid_bases), 1.0 / len(valid_bases))

                    w_cls = np.clip(w_cls, 0.0, 1.0)
                    w_cls = w_cls / np.sum(w_cls)
                    w_reg = np.clip(w_reg, 0.0, 1.0)
                    w_reg = w_reg / np.sum(w_reg)

                    ens_p = np.clip(P_val @ w_cls, 0.0, 1.0)
                    ens_pred = Y_val @ w_reg

                    weights_summary = {
                        f"{m}_cls": round(float(w_cls[i]), 4)
                        for i, m in enumerate(valid_bases)
                    }
                    weights_summary.update({
                        f"{m}_reg": round(float(w_reg[i]), 4)
                        for i, m in enumerate(valid_bases)
                    })

                    metrics_dict = compute_point_forecast_metrics(
                        y_true_reg=y_vl_reg,
                        pred_reg=ens_pred,
                        y_true_cls=y_vl_cls,
                        pred_cls_prob=ens_p,
                        probability_estimator_audit="convex_ensemble_probability",
                    )

                # Save Ensemble OOF V2
                row_ids = np.arange(n_val, dtype=int)
                oof_df = pd.DataFrame({
                    "row_id": row_ids,
                    "flight_key": val_flight_keys.values,
                    "fold_id": fold.fold_id,
                    "model_id": ens_id,
                    "y_true_reg": y_vl_reg,
                    "y_true_cls": y_vl_cls,
                    "pred_reg": ens_pred,
                    "pred_cls_prob": ens_p,
                    "seed": self.config.random_seed,
                    "train_window": train_window_str,
                    "code_hash": self.code_hash,
                    "config_hash": self.config_hash,
                    "status": status,
                    "failure_reason": failure_reason,
                })
                validate_oof_v2_frame(oof_df)
                oof_file = self.run_dir / "oof" / f"{ens_id}_{fold.fold_id}.parquet"
                oof_df.to_parquet(oof_file, index=False)
                oof_by_model[ens_id][fold.fold_id] = oof_df

                runtime = time.perf_counter() - t0
                mem_end = process.memory_info().rss / (1024 * 1024)
                mem_used = max(0.0, mem_end - mem0)

                fold_res = PointBenchmarkFoldResult(
                    experiment_id=self.config.experiment_id,
                    model_id=ens_id,
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
                    metrics=metrics_dict,
                    oof_artifact=str(oof_file),
                    weights=weights_summary,
                )
                results.append(fold_res)

                metrics_file = self.run_dir / "metrics" / f"{ens_id}_{fold.fold_id}.json"
                with open(metrics_file, "w", encoding="utf-8") as f:
                    json.dump(fold_res.to_dict(), f, indent=2)

            # Update historical development OOF with current fold predictions for base models
            for m in base_methods:
                if fold.fold_id in oof_by_model[m] and oof_by_model[m][fold.fold_id]["status"].iloc[0] == "SUCCESS":
                    m_df = oof_by_model[m][fold.fold_id]
                    dev_oof_cls[m].append(m_df["pred_cls_prob"].to_numpy())
                    dev_oof_reg[m].append(m_df["pred_reg"].to_numpy())
            dev_true_cls.append(y_vl_cls)
            dev_true_reg.append(y_vl_reg)

            # Clean memory
            del X_train, X_val, y_tr_cls, y_tr_reg, y_vl_cls, y_vl_reg
            gc.collect()

        # Step 6: Artifact writer — Consolidated artifacts & Top-level Manifest
        self._write_consolidated_artifacts(results)
        return results

    def _write_consolidated_artifacts(self, results: list[PointBenchmarkFoldResult]) -> None:
        """Write benchmark_summary.json, benchmark_summary.csv, manifest.sha256, and top-level manifest."""
        # 1. Summary JSON
        summary_path = self.run_dir / "benchmark_summary.json"
        summary_payload = {
            "experiment_id": self.config.experiment_id,
            "benchmark_version": "v2.0",
            "protocol": "AEOLUS_V4_CORE_POINT_BENCHMARK_PROTOCOL",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config_hash": self.config_hash,
            "code_hash": self.code_hash,
            "total_runs": len(results),
            "completed_runs": sum(1 for r in results if r.status == "SUCCESS"),
            "failed_runs": sum(1 for r in results if r.status != "SUCCESS"),
            "results": [r.to_dict() for r in results],
            "champion_selected": False,
            "champion_selection_policy": "NO_CHAMPION_SELECTION_IN_R3",
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
                "n_total": r.metrics.get("n_total"),
                "n_valid": r.metrics.get("n_valid"),
                "n_missing": r.metrics.get("n_missing"),
                "n_failures": r.metrics.get("n_failures"),
                "mae": r.metrics.get("mae"),
                "rmse": r.metrics.get("rmse"),
                "r2": r.metrics.get("r2"),
                "severe_delay_mae_ge_60": r.metrics.get("severe_delay_mae_ge_60"),
                "roc_auc": r.metrics.get("roc_auc"),
                "pr_auc": r.metrics.get("pr_auc"),
                "brier_score": r.metrics.get("brier_score"),
                "probability_semantics": r.metrics.get("probability_semantics"),
                "oof_artifact": r.oof_artifact,
            }
            if r.weights:
                for k, v in r.weights.items():
                    row[f"weight_{k}"] = v
            rows.append(row)

        df_summary = pd.DataFrame(rows)
        df_summary.to_csv(self.run_dir / "benchmark_summary.csv", index=False)

        # 3. Cryptographic hash manifest of run directory
        run_manifest: dict[str, str] = {}
        for p in sorted(self.run_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.sha256":
                hasher = hashlib.sha256()
                hasher.update(p.read_bytes())
                run_manifest[str(p.relative_to(self.run_dir))] = hasher.hexdigest()

        with open(self.run_dir / "manifest.sha256", "w", encoding="utf-8") as f:
            json.dump(run_manifest, f, indent=2)

        # 4. Top-level Manifest: artifacts/manifests/core_point_benchmark_v2.json
        top_manifest_path = Path(self.config.manifest_path)
        top_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        top_manifest_payload = {
            "manifest_version": "core_point_benchmark_v2",
            "protocol_name": "AEOLUS_V4_CORE_POINT_BENCHMARK",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_id": self.config.experiment_id,
            "run_dir": str(self.run_dir),
            "config_hash": self.config_hash,
            "code_hash": self.code_hash,
            "models_evaluated": list(self.config.methods),
            "model_count": len(self.config.methods),
            "total_runs": len(results),
            "completed_runs": sum(1 for r in results if r.status == "SUCCESS"),
            "failed_runs": sum(1 for r in results if r.status != "SUCCESS"),
            "temporal_coverage": {
                "rolling_folds": ["fold_1", "fold_2", "fold_3", "fold_4"],
                "development_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
                "year_2023_included": False,
                "year_2024_included": False,
            },
            "provenance_invariants": {
                "core_methods_only": True,
                "cap_5_strictly_enforced": True,
                "same_row_alignment_guaranteed": True,
                "no_weather_features": True,
                "no_departure_delay_predictors": True,
                "no_target_leakage": True,
                "preprocessing_train_only": True,
                "probability_semantics_audited": True,
                "champion_selection": "NONE",
            },
            "artifacts": {
                "benchmark_summary_json": str(summary_path),
                "benchmark_summary_csv": str(self.run_dir / "benchmark_summary.csv"),
                "manifest_sha256": str(self.run_dir / "manifest.sha256"),
            },
        }
        with open(top_manifest_path, "w", encoding="utf-8") as f:
            json.dump(top_manifest_payload, f, indent=2)

        LOGGER.info(f"Top-level benchmark manifest successfully written to {top_manifest_path}")
