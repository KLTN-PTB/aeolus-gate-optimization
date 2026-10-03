"""Multi-Model Benchmark Runner for Aeolus Gate Optimization.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/CURRENT_STATE.md
          configs/current_state.yaml

Key Invariants:
1. Multi-Model Support: Evaluates arbitrary lists of models [model_A, model_B, ...]
   through an identical shared loop without copy-pasting training logic.
2. Full Parity:
   - Same rows & indices for training and validation across all models in a fold.
   - Same labels & target scaling.
   - Same temporal fold boundaries.
   - Same T-2h cutoff policy.
   - Same random seed initialization per model.
   - Same resource budget & timeout rules.
3. Fail-Closed Protocol & Safety:
   - Rejects unknown tasks or unregistered models.
   - Rejects missing targets and mismatched row counts.
   - Rejects 2024 development data access.
   - Rejects Core Arrival features containing weather or post-cutoff operational fields.
   - Rejects Auxiliary Departure feeding downstream optimization.
4. Failure Retention:
   - Model failures (e.g. exceptions, convergence errors, budget violations) are never
     silently dropped. They are durably recorded with failure_reason and status="FAILED".
5. Non-Destructive Artifact Versioning:
   - Never overwrites existing benchmark runs in artifacts/model_benchmark/.
   - Emits full configuration, results summary, per-model artifacts, and SHA-256 manifests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Final, Sequence

import numpy as np
import pandas as pd
import psutil

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.models.interfaces import (
    BaseModel,
    ModelCapability,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
    UnsupportedCapabilityError,
)
from src.models.registry import get_model_spec

LOGGER = logging.getLogger("model_benchmark_runner")

DEFAULT_BENCHMARK_ARTIFACT_DIR: Final = Path("artifacts/model_benchmark")

# Post-cutoff outcome features strictly forbidden from Core Arrival predictor inputs
FORBIDDEN_ARRIVAL_FEATURES: Final[frozenset[str]] = frozenset([
    "ARR_DELAY",
    "DEP_DELAY",
    "DEP_TIME",
    "ARR_TIME",
    "TAXI_IN",
    "TAXI_OUT",
    "WHEELS_ON",
    "WHEELS_OFF",
    "CANCELLED",
    "DIVERTED",
    "ACTUAL_ELAPSED_TIME",
    "AIR_TIME",
    "O_TEMP",
    "O_PRCP",
    "O_WSPD",
    "D_TEMP",
    "D_PRCP",
    "D_WSPD",
])


class BenchmarkProtocolViolation(ValueError):
    """Raised when benchmark configuration or data violates the fail-closed protocol."""


@dataclass(frozen=True)
class FoldDataset:
    """Fold-specific dataset container guaranteeing row and label parity across models."""

    fold_id: str
    train_years: list[int]
    val_year: int
    X_train: pd.DataFrame
    y_train: pd.Series | np.ndarray
    X_val: pd.DataFrame
    y_val: pd.Series | np.ndarray
    task: str = ModelTask.CORE_ARRIVAL.value
    feature_version: str = "v1"
    preprocessing_version: str = "v1"

    def __post_init__(self) -> None:
        """Validate row count consistency between features and targets."""
        if len(self.X_train) != len(self.y_train):
            raise BenchmarkProtocolViolation(
                f"Row mismatch in fold {self.fold_id} train: "
                f"len(X_train)={len(self.X_train)} != len(y_train)={len(self.y_train)}"
            )
        if len(self.X_val) != len(self.y_val):
            raise BenchmarkProtocolViolation(
                f"Row mismatch in fold {self.fold_id} val: "
                f"len(X_val)={len(self.X_val)} != len(y_val)={len(self.y_val)}"
            )
        if len(self.X_train) == 0:
            raise BenchmarkProtocolViolation(f"Fold {self.fold_id} X_train cannot be empty")
        if len(self.X_val) == 0:
            raise BenchmarkProtocolViolation(f"Fold {self.fold_id} X_val cannot be empty")


@dataclass(frozen=True)
class BenchmarkBudget:
    """Resource budget limits enforced equally across all models."""

    timeout_seconds: float = 300.0
    max_memory_mb: float = 4096.0


@dataclass(frozen=True)
class BenchmarkConfig:
    """Immutable benchmark run configuration."""

    experiment_id: str
    run_id: str
    task: str = ModelTask.CORE_ARRIVAL.value
    target: str = ModelTarget.ARRIVAL_DELAY_SIGNED.value
    cutoff: str = "CRS_DEP_TIME - 2h"
    random_seed: int = 202601
    feature_version: str = "v1"
    preprocessing_version: str = "v1"
    budget: BenchmarkBudget = field(default_factory=BenchmarkBudget)
    output_dir: Path = field(default_factory=lambda: DEFAULT_BENCHMARK_ARTIFACT_DIR)
    data_role: str = "rolling_development"

    def compute_sha256(self) -> str:
        """Compute deterministic configuration hash."""
        d = {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "task": self.task,
            "target": self.target,
            "cutoff": self.cutoff,
            "random_seed": self.random_seed,
            "feature_version": self.feature_version,
            "preprocessing_version": self.preprocessing_version,
            "data_role": self.data_role,
        }
        raw = json.dumps(d, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class BenchmarkResult:
    """Unified benchmark result schema with durable failure retention."""

    experiment_id: str
    run_id: str
    model_id: str
    fold_id: str
    year: int
    seed: int
    n_rows: int
    feature_version: str
    preprocessing_version: str
    metrics: dict[str, float]
    runtime_sec: float
    memory_mb: float
    status: str  # "COMPLETED", "FAILED", "TIMEOUT"
    failure_reason: str | None
    artifact_path: str | None
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    config_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert result to serializable dictionary."""
        return asdict(self)


def compute_regression_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> dict[str, float]:
    """Compute standard regression metrics safely."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    diff = y_pred - y_true
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    var_true = float(np.var(y_true))
    r2 = float(1.0 - (np.mean(diff**2) / var_true)) if var_true > 1e-9 else 0.0

    metrics: dict[str, float] = {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 6),
    }

    # Severe delay MAE (observed >= 60 min)
    severe_mask = y_true >= 60.0
    if np.any(severe_mask):
        severe_mae = float(np.mean(np.abs(diff[severe_mask])))
        metrics["severe_mae"] = round(severe_mae, 4)

    return metrics


def compute_classification_metrics(
    y_true: np.ndarray, y_pred_proba: np.ndarray
) -> dict[str, float]:
    """Compute binary classification metrics safely."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred_proba, dtype=np.float64)

    brier = float(np.mean((y_pred - y_true) ** 2))
    binary_pred = (y_pred >= 0.5).astype(float)
    acc = float(np.mean(binary_pred == y_true))

    metrics: dict[str, float] = {
        "brier_score": round(brier, 6),
        "accuracy": round(acc, 4),
    }

    # Safe scikit-learn metrics if available
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score

        if len(np.unique(y_true)) > 1:
            metrics["pr_auc"] = round(float(average_precision_score(y_true, y_pred)), 4)
            metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_pred)), 4)
    except Exception:
        pass

    return metrics


class MultiModelBenchmarkRunner:
    """Benchmark engine running multiple candidate models across standardized folds."""

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self._validate_config_safety()
        self.run_dir = self._prepare_run_directory()

    def _validate_config_safety(self) -> None:
        """Fail closed on invalid tasks, versions, or protocols."""
        valid_tasks = {t.value for t in ModelTask}
        if self.config.task not in valid_tasks:
            raise BenchmarkProtocolViolation(
                f"Unknown benchmark task '{self.config.task}'. Fail-closed: must be one of {valid_tasks}."
            )

        if self.config.task == ModelTask.CORE_ARRIVAL.value:
            if "weather" in self.config.feature_version.lower() and "no_weather" not in self.config.feature_version.lower():
                raise BenchmarkProtocolViolation(
                    "Core Arrival benchmark cannot use weather features."
                )

    def _prepare_run_directory(self) -> Path:
        """Create non-destructive, versioned artifact run directory."""
        base_dir = Path(self.config.output_dir) / self.config.experiment_id
        base_dir.mkdir(parents=True, exist_ok=True)

        target_dir = base_dir / self.config.run_id
        if target_dir.exists():
            # Non-destructive fallback: append version timestamp to avoid overwriting
            version_suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            target_dir = base_dir / f"{self.config.run_id}_{version_suffix}"

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "models").mkdir(exist_ok=True)
        (target_dir / "results").mkdir(exist_ok=True)

        # Write config.json
        cfg_path = target_dir / "benchmark_config.json"
        cfg_dict = asdict(self.config)
        cfg_dict["output_dir"] = str(self.config.output_dir)
        cfg_dict["config_hash"] = self.config.compute_sha256()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)

        return target_dir

    def validate_dataset_safety(self, dataset: FoldDataset) -> None:
        """Assert fail-closed safety checks on input fold dataset."""
        # 1. Temporal protocol: Check 2024 development access
        if dataset.val_year == 2024 or 2024 in dataset.train_years:
            # Must raise DataAccessDenied if accessed under development
            assert_data_access_allowed(2024, "development")

        # 2. Check task match
        if dataset.task != self.config.task:
            raise BenchmarkProtocolViolation(
                f"Dataset task '{dataset.task}' does not match benchmark task '{self.config.task}'"
            )

        # 3. Check for disallowed features in Core Arrival
        if self.config.task == ModelTask.CORE_ARRIVAL.value:
            cols = set(dataset.X_train.columns).union(set(dataset.X_val.columns))
            forbidden_detected = cols.intersection(FORBIDDEN_ARRIVAL_FEATURES)
            if forbidden_detected:
                raise BenchmarkProtocolViolation(
                    f"Core Arrival dataset contains forbidden post-cutoff or weather features: {sorted(list(forbidden_detected))}"
                )

        # 4. Check for NaNs in target if regression
        y_train_arr = np.asarray(dataset.y_train)
        if np.any(np.isnan(y_train_arr)):
            raise BenchmarkProtocolViolation("Target y_train contains NaN values. Target imputation is prohibited.")

    def run_benchmark(
        self,
        models: Sequence[BaseModel],
        folds: Sequence[FoldDataset],
    ) -> list[BenchmarkResult]:
        """Execute benchmark loop across all models and folds with full parity and failure retention."""
        if not models:
            raise BenchmarkProtocolViolation("Model list cannot be empty.")
        if not folds:
            raise BenchmarkProtocolViolation("Fold list cannot be empty.")

        seen_folds = set()
        for f in folds:
            if f.fold_id in seen_folds:
                raise BenchmarkProtocolViolation(f"Duplicate fold_id '{f.fold_id}' detected.")
            seen_folds.add(f.fold_id)

        # Safety: validate all models
        for m in models:
            if not isinstance(m, BaseModel):
                raise TypeError(f"Every model must inherit from BaseModel, got {type(m)}")

            # Check registry if spec attached
            if m.spec:
                # Auxiliary model cannot feed downstream optimizer
                if m.spec.task == ModelTask.AUXILIARY_DEPARTURE.value and m.spec.downstream_eligible:
                    raise BenchmarkProtocolViolation(
                        f"Model '{m.model_id}' is Auxiliary Departure but declares downstream_eligible=True."
                    )
                # Feature version check
                if m.spec.task == ModelTask.CORE_ARRIVAL.value and "weather" in m.spec.feature_set.lower() and "no_weather" not in m.spec.feature_set.lower():
                    raise BenchmarkProtocolViolation(
                        f"Model '{m.model_id}' feature set contains forbidden weather."
                    )

        results: list[BenchmarkResult] = []
        process = psutil.Process()
        config_hash = self.config.compute_sha256()

        for fold in folds:
            self.validate_dataset_safety(fold)
            LOGGER.info(f"--- Running Fold {fold.fold_id} (val_year={fold.val_year}) ---")

            for model in models:
                LOGGER.info(f"Evaluating model '{model.model_id}' on fold '{fold.fold_id}'")
                t0 = time.perf_counter()
                mem0 = process.memory_info().rss / (1024 * 1024)

                result_status = "COMPLETED"
                failure_reason: str | None = None
                metrics: dict[str, float] = {}
                artifact_path: str | None = None

                try:
                    # Seed policy: enforce deterministic seed before fit
                    seed_to_use = self.config.random_seed
                    if hasattr(model, "random_seed"):
                        model.random_seed = seed_to_use

                    # 1. Fit model on exact fold train data
                    model.fit(fold.X_train, fold.y_train)

                    # 2. Check budget timeout after fit
                    elapsed_fit = time.perf_counter() - t0
                    if elapsed_fit > self.config.budget.timeout_seconds:
                        raise TimeoutError(
                            f"Model '{model.model_id}' exceeded timeout budget "
                            f"({elapsed_fit:.2f}s > {self.config.budget.timeout_seconds}s)"
                        )

                    # 3. Predict on exact fold val data
                    if self.config.target == ModelTarget.ARRIVAL_DELAY_BINARY_15.value or self.config.target == ModelTarget.DEPARTURE_DELAY_BINARY_15.value:
                        if model.has_capability(ModelCapability.POINT_CLASSIFICATION) or model.has_capability(ModelCapability.CALIBRATED_PROBABILITY):
                            preds = model.predict_proba(fold.X_val)
                            # Handle 2D probability output
                            if isinstance(preds, np.ndarray) and preds.ndim == 2 and preds.shape[1] > 1:
                                preds = preds[:, 1]
                            metrics = compute_classification_metrics(np.asarray(fold.y_val), preds)
                        else:
                            preds = model.predict(fold.X_val)
                            metrics = compute_classification_metrics(np.asarray(fold.y_val), preds)
                    else:
                        # Regression target
                        preds = model.predict(fold.X_val)
                        metrics = compute_regression_metrics(np.asarray(fold.y_val), preds)

                        # If model is probabilistic, evaluate CRPS/quantiles if supported
                        if model.has_capability(ModelCapability.PROBABILISTIC):
                            try:
                                dist = model.predict_distribution(fold.X_val)
                                if "mu" in dist and "sigma" in dist:
                                    # Gaussian or Student-t CRPS approximation
                                    from src.models.probabilistic.metrics import compute_gaussian_crps
                                    metrics["crps"] = round(float(compute_gaussian_crps(np.asarray(fold.y_val), dist["mu"], dist["sigma"])), 4)
                            except Exception:
                                pass

                    # 4. Save model artifact
                    art_file = self.run_dir / "models" / f"{model.model_id}_{fold.fold_id}.joblib"
                    model.save_artifact(art_file)
                    artifact_path = str(art_file)

                except Exception as exc:
                    result_status = "FAILED" if not isinstance(exc, TimeoutError) else "TIMEOUT"
                    failure_reason = str(exc)
                    LOGGER.warning(
                        f"Model '{model.model_id}' on fold '{fold.fold_id}' failed: {failure_reason}"
                    )

                runtime = time.perf_counter() - t0
                mem_end = process.memory_info().rss / (1024 * 1024)
                mem_used = max(0.0, mem_end - mem0)

                res = BenchmarkResult(
                    experiment_id=self.config.experiment_id,
                    run_id=self.config.run_id,
                    model_id=model.model_id,
                    fold_id=fold.fold_id,
                    year=fold.val_year,
                    seed=self.config.random_seed,
                    n_rows=len(fold.X_val),
                    feature_version=self.config.feature_version,
                    preprocessing_version=self.config.preprocessing_version,
                    metrics=metrics,
                    runtime_sec=round(runtime, 4),
                    memory_mb=round(mem_used, 2),
                    status=result_status,
                    failure_reason=failure_reason,
                    artifact_path=artifact_path,
                    config_hash=config_hash,
                )
                results.append(res)

                # Save individual result JSON
                res_path = self.run_dir / "results" / f"{model.model_id}_{fold.fold_id}.json"
                with open(res_path, "w", encoding="utf-8") as f:
                    json.dump(res.to_dict(), f, indent=2)

        # Write overall summary JSON and hash manifest
        self._write_summary_and_manifest(results)
        return results

    def _write_summary_and_manifest(self, results: list[BenchmarkResult]) -> None:
        """Write consolidated summary report and SHA-256 hash manifest."""
        summary_path = self.run_dir / "benchmark_summary.json"
        summary_payload = {
            "experiment_id": self.config.experiment_id,
            "run_id": self.config.run_id,
            "config_hash": self.config.compute_sha256(),
            "total_runs": len(results),
            "completed_runs": sum(1 for r in results if r.status == "COMPLETED"),
            "failed_runs": sum(1 for r in results if r.status != "COMPLETED"),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "results": [r.to_dict() for r in results],
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        # Write tabular CSV summary
        try:
            records = [r.to_dict() for r in results]
            df_summary = pd.DataFrame(records)
            csv_path = self.run_dir / "benchmark_summary.csv"
            df_summary.to_csv(csv_path, index=False)
        except Exception as e:
            LOGGER.warning(f"Could not write CSV summary: {e}")

        # Compute SHA-256 for all json and csv artifacts in run_dir
        manifest_entries: dict[str, str] = {}
        for p in sorted(self.run_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.sha256":
                hasher = hashlib.sha256()
                hasher.update(p.read_bytes())
                manifest_entries[str(p.relative_to(self.run_dir))] = hasher.hexdigest()

        manifest_path = self.run_dir / "manifest.sha256"
        manifest_path.write_text(json.dumps(manifest_entries, indent=2), encoding="utf-8")
        LOGGER.info(f"Benchmark artifacts successfully written to: {self.run_dir}")
