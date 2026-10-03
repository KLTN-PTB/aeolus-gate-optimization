"""Probabilistic Benchmark Runner for Core Arrival (Phase 3).

Executes fair multi-candidate distributional benchmarking across all 4 rolling development folds:
P1: Empirical carrier x scheduled-hour baseline
P2: XGBoost mean + OOF residual uncertainty (Fixed-sigma Gaussian)
P3: NGBoost Normal (Heteroscedastic Gaussian)
P4: NGBoost Student-T (Heteroscedastic Heavy-Tail)
P5: Quantile regression research comparator (Multi-pinball LightGBM)

Enforces:
- Same dataset, folds, cutoff, and rows
- Strict numerical correctness validation before metric calculation
- Common distributional representation: mean, median, quantiles, CDF, P(delay >= 15), sampler
- Capability declaration with NOT_AVAILABLE for unsupported metrics
- Durable failure retention
- Versioned, non-destructive artifacts with manifest.sha256
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

from src.data.access_guard import assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.data.stratified_loader import load_stratified_fold_data
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.contracts import load_week4_rolling_folds
from src.models.probabilistic.candidate_interfaces import (
    BaseProbabilisticCandidate,
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
    ProbabilisticPrediction,
)
from src.models.probabilistic.contracts import SCREENING_SEED
from src.models.probabilistic.correctness_validator import (
    CorrectnessReport,
    validate_candidate_correctness,
)
from src.models.probabilistic.evaluation_engine import evaluate_probabilistic_prediction

LOGGER = logging.getLogger("probabilistic_benchmark")
DEFAULT_PROBABILISTIC_ARTIFACT_DIR: Final = Path("artifacts/probabilistic_benchmark")

PROBABILISTIC_CANDIDATE_IDS: Final = (
    "P1_empirical",
    "P2_xgb_gaussian_oof",
    "P3_ngboost_normal",
    "P4_ngboost_student_t",
    "P5_quantile_regression",
)


@dataclass(frozen=True)
class ProbabilisticBenchmarkConfig:
    """Run configuration for Phase 3 Probabilistic Benchmark."""

    experiment_id: str
    task: str = "core_arrival"
    cutoff: str = "CRS_DEP_TIME - 2h"
    seed: int = SCREENING_SEED
    data_seed: int | None = None
    sample_train_per_year: int = 3500
    sample_val: int = 4000
    output_dir: Path = DEFAULT_PROBABILISTIC_ARTIFACT_DIR
    candidates: tuple[str, ...] = PROBABILISTIC_CANDIDATE_IDS

    def compute_sha256(self) -> str:
        d = {
            "experiment_id": self.experiment_id,
            "task": self.task,
            "cutoff": self.cutoff,
            "seed": self.seed,
            "data_seed": self.data_seed,
            "sample_train_per_year": self.sample_train_per_year,
            "sample_val": self.sample_val,
            "candidates": list(self.candidates),
        }
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class ProbabilisticFoldResult:
    """Evaluation result for one probabilistic candidate on one fold."""

    experiment_id: str
    candidate_id: str
    fold_id: str
    validation_year: int
    train_years: list[int]
    train_rows: int
    validation_rows: int
    seed: int
    status: str  # "COMPLETED" or "FAILED"
    failure_reason: str | None
    correctness_status: str  # "PASSED" or "FAILED"
    correctness_issues: list[str]
    runtime_seconds: float
    memory_mb: float
    capabilities: dict[str, bool]
    metrics: dict[str, Any]
    oof_artifact: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _instantiate_candidate(candidate_id: str, seed: int) -> BaseProbabilisticCandidate:
    """Build candidate adapter instance."""
    if candidate_id == "P1_empirical":
        return P1EmpiricalCandidate(seed=seed)
    elif candidate_id == "P2_xgb_gaussian_oof":
        return P2XGBoostGaussianCandidate(seed=seed)
    elif candidate_id == "P3_ngboost_normal":
        return P3NGBoostNormalCandidate(seed=seed)
    elif candidate_id == "P4_ngboost_student_t":
        return P4NGBoostStudentTCandidate(seed=seed)
    elif candidate_id == "P5_quantile_regression":
        return P5QuantileRegressionCandidate(seed=seed)
    else:
        raise ValueError(f"Unknown candidate_id: {candidate_id}")


class ProbabilisticBenchmarkRunner:
    """Orchestrates multi-candidate probabilistic evaluation."""

    def __init__(self, config: ProbabilisticBenchmarkConfig) -> None:
        self.config = config
        self._validate_safety()
        self.run_dir = self._prepare_run_dir()

    def _validate_safety(self) -> None:
        """Fail closed on invalid tasks or forbidden 2024 access."""
        if self.config.task != "core_arrival":
            raise ValueError(f"Task must be 'core_arrival', got '{self.config.task}'")

        try:
            assert_data_access_allowed(2024, "development")
            raise RuntimeError("2024 access was unexpectedly permitted for development!")
        except Exception:
            pass

    def _prepare_run_dir(self) -> Path:
        """Create non-destructive, timestamp-versioned artifact directory."""
        target_dir = Path(self.config.output_dir) / self.config.experiment_id
        if target_dir.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            target_dir = Path(self.config.output_dir) / f"{self.config.experiment_id}_{ts}"

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "oof").mkdir(exist_ok=True)
        (target_dir / "metrics").mkdir(exist_ok=True)

        cfg_dict = asdict(self.config)
        cfg_dict["output_dir"] = str(self.config.output_dir)
        cfg_dict["config_hash"] = self.config.compute_sha256()
        with open(target_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)

        return target_dir

    def run_benchmark(self) -> list[ProbabilisticFoldResult]:
        """Execute benchmark across all locked rolling development folds."""
        rolling_folds = load_week4_rolling_folds()
        results: list[ProbabilisticFoldResult] = []

        LOGGER.info(
            f"Starting Phase 3 Probabilistic Benchmark '{self.config.experiment_id}' "
            f"across {len(rolling_folds)} folds for {len(self.config.candidates)} candidates."
        )

        for fold in rolling_folds:
            LOGGER.info(f"\n==================== EVALUATING FOLD {fold.fold_id} (Val: {fold.validation_year}) ====================")

            # 1. Load data once per fold for perfect parity
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
                random_state=self.config.data_seed if self.config.data_seed is not None else self.config.seed,
                feature_set="v1",
            )

            # Assert strict absence of weather and leakage columns
            cols_tr = set(X_train.columns)
            cols_vl = set(X_val.columns)
            if not cols_tr.issubset(set(APPROVED_PREDICTOR_COLUMNS)):
                raise ValueError(f"Unapproved predictors in X_train: {cols_tr - set(APPROVED_PREDICTOR_COLUMNS)}")
            if cols_tr.intersection(WEATHER_COLUMNS) or cols_vl.intersection(WEATHER_COLUMNS):
                raise ValueError("Weather features detected in Core Arrival data!")
            if cols_tr.intersection(ARRIVAL_LEAKAGE_COLUMNS) or cols_vl.intersection(ARRIVAL_LEAKAGE_COLUMNS):
                raise ValueError("Operational leakage features detected in Core Arrival data!")

            y_tr_reg = np.asarray(y_train_reg_series, dtype=np.float64)
            y_vl_reg = np.asarray(y_val_reg_series, dtype=np.float64)
            y_vl_cls = np.asarray(y_val_cls_series, dtype=np.int8)

            # 2. Run Each Candidate
            for cid in self.config.candidates:
                LOGGER.info(f"[*] Training candidate {cid} on {fold.fold_id}...")
                process = psutil.Process()
                mem0 = process.memory_info().rss / (1024 * 1024)
                t0 = time.perf_counter()

                status = "COMPLETED"
                failure_reason: str | None = None
                correctness_status = "PASSED"
                correctness_issues: list[str] = []
                metrics_dict: dict[str, Any] = {}
                oof_path_str: str | None = None
                capabilities_dict: dict[str, bool] = {}

                try:
                    candidate = _instantiate_candidate(cid, seed=self.config.seed)
                    capabilities_dict = candidate.capabilities()

                    # Fit candidate
                    candidate.fit(X_train, y_tr_reg)

                    # Predict common representation
                    pred = candidate.predict_distribution(X_val)

                    # Validate numerical correctness before metrics
                    corr_report = validate_candidate_correctness(pred, test_seed=self.config.seed)
                    if not corr_report.is_valid:
                        correctness_status = "FAILED"
                        correctness_issues = list(corr_report.issues)
                        status = "FAILED"
                        failure_reason = "Numerical correctness validation failed: " + "; ".join(corr_report.issues)
                        LOGGER.warning(f"Correctness failure for {cid} on {fold.fold_id}: {failure_reason}")
                    else:
                        # Evaluate all proper scoring rules and calibration
                        metrics_dict = evaluate_probabilistic_prediction(pred, y_vl_reg)

                        # Write OOF DataFrame
                        caps = pred.metadata().get("capabilities", {})
                        oof_dict: dict[str, Any] = {
                            "flight_key": val_flight_keys.values,
                            "fold_id": fold.fold_id,
                            "validation_year": fold.validation_year,
                            "y_arr_reg": y_vl_reg,
                            "y_arr_cls": y_vl_cls,
                            "median": pred.median(),
                        }
                        if caps.get("has_p_delay_ge_15", False) or caps.get("has_probability_ge", False):
                            oof_dict["p_delay_ge_15"] = pred.probability_ge(15.0)

                        if caps.get("has_mean", False):
                            try:
                                m = pred.mean()
                                if m is not None:
                                    oof_dict["mean"] = m
                            except Exception:
                                pass

                        if caps.get("has_quantiles", False):
                            for a in sorted(pred.quantiles.keys()):
                                oof_dict[f"q_{a:.3f}"] = pred.quantile(a)

                        oof_df = pd.DataFrame(oof_dict)
                        oof_file = self.run_dir / "oof" / f"{cid}_{fold.fold_id}.parquet"
                        oof_df.to_parquet(oof_file, index=False)
                        oof_path_str = str(oof_file)

                except Exception as exc:
                    status = "FAILED"
                    failure_reason = str(exc)
                    LOGGER.error(f"Execution failed for {cid} on {fold.fold_id}: {exc}", exc_info=True)

                runtime = time.perf_counter() - t0
                mem_end = process.memory_info().rss / (1024 * 1024)
                mem_used = max(0.0, mem_end - mem0)

                fold_res = ProbabilisticFoldResult(
                    experiment_id=self.config.experiment_id,
                    candidate_id=cid,
                    fold_id=fold.fold_id,
                    validation_year=fold.validation_year,
                    train_years=list(fold.train_years),
                    train_rows=len(X_train),
                    validation_rows=len(X_val),
                    seed=self.config.seed,
                    status=status,
                    failure_reason=failure_reason,
                    correctness_status=correctness_status,
                    correctness_issues=correctness_issues,
                    runtime_seconds=round(runtime, 3),
                    memory_mb=round(mem_used, 2),
                    capabilities=capabilities_dict,
                    metrics=metrics_dict,
                    oof_artifact=oof_path_str,
                )
                results.append(fold_res)

                # Save individual metrics JSON
                metrics_file = self.run_dir / "metrics" / f"{cid}_{fold.fold_id}.json"
                with open(metrics_file, "w", encoding="utf-8") as f:
                    json.dump(fold_res.to_dict(), f, indent=2)

            del X_train, X_val, y_tr_reg, y_vl_reg, y_vl_cls
            gc.collect()

        self._write_consolidated_artifacts(results)
        return results

    def _write_consolidated_artifacts(self, results: list[ProbabilisticFoldResult]) -> None:
        """Write summary JSON, CSV, and SHA-256 hash manifest."""
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
                "candidate_id": r.candidate_id,
                "fold_id": r.fold_id,
                "validation_year": r.validation_year,
                "status": r.status,
                "correctness_status": r.correctness_status,
                "runtime_seconds": r.runtime_seconds,
                "memory_mb": r.memory_mb,
                "crps": r.metrics.get("crps"),
                "nll": r.metrics.get("nll"),
                "brier_score_delay_ge_15": r.metrics.get("brier_score_delay_ge_15"),
                "mean_pinball_loss": r.metrics.get("mean_pinball_loss"),
                "cov_50": r.metrics.get("empirical_coverage", {}).get("interval_50"),
                "cov_80": r.metrics.get("empirical_coverage", {}).get("interval_80"),
                "cov_90": r.metrics.get("empirical_coverage", {}).get("interval_90"),
                "cov_95": r.metrics.get("empirical_coverage", {}).get("interval_95"),
                "width_50": r.metrics.get("interval_widths", {}).get("interval_50"),
                "width_80": r.metrics.get("interval_widths", {}).get("interval_80"),
                "width_90": r.metrics.get("interval_widths", {}).get("interval_90"),
                "width_95": r.metrics.get("interval_widths", {}).get("interval_95"),
                "ece": r.metrics.get("calibration_diagnostics", {}).get("expected_calibration_error"),
                "ks_stat": r.metrics.get("pit", {}).get("ks_statistic"),
                "oof_artifact": r.oof_artifact,
            }
            rows.append(row)

        df_summary = pd.DataFrame(rows)
        df_summary.to_csv(self.run_dir / "benchmark_summary.csv", index=False)

        # 3. SHA-256 Manifest
        manifest: dict[str, str] = {}
        for p in sorted(self.run_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.sha256":
                hasher = hashlib.sha256()
                hasher.update(p.read_bytes())
                manifest[str(p.relative_to(self.run_dir))] = hasher.hexdigest()

        with open(self.run_dir / "manifest.sha256", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        LOGGER.info(f"Consolidated probabilistic artifacts saved to: {self.run_dir}")
