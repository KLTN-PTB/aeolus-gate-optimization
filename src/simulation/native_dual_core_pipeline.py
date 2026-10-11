"""Native Dual-Core Predict-then-Optimize Pipeline Engine.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P07 Native Dual-Core Predict-Then-Optimize Pipeline

Implements the authoritative, zero-leakage pipeline:
Canonical Data
  -> Point-in-Time Features (Cutoff: CRS_DEP_TIME - 2 hours)
  -> Cryptographically Verified Native Model Checkpoints
  -> Native Model Inference (Arrival + Departure)
  -> Standardized Prediction Contract (14+ fields with provenance)
  -> Inbound-Outbound Aircraft Turn Pairing (1-to-1 cardinality)
  -> DualTurnEngine Physical Timeline Synthesis
  -> DualCoreGateOptimizerAdapter (RBAC enforcement)
  -> Authoritative Multi-Solver Execution (Greedy, CP-SAT, SA, Hybrid)
  -> Independent Hard-Constraint Verification & Metric Audit
  -> Full Run Manifest & Export Artifacts
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Final, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.data.departure_preprocessing import DeparturePreprocessingPipeline
from src.data.leakage_rules import (
    ARRIVAL_TASK,
    CORE_DEPARTURE_TASK,
    LeakageRuleViolation,
    assert_candidate_predictors_allowed,
)
from src.data.pairing_validator import PairingValidationSummary, PairingValidator
from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    RAW_SAFE_SOURCE_COLUMNS as DEP_RAW_SAFE_COLUMNS,
    prepare_departure_inference,
)
from src.features.tabular_features import (
    APPROVED_PREDICTOR_COLUMNS as ARR_APPROVED_COLUMNS,
    RAW_SAFE_SOURCE_COLUMNS as ARR_RAW_SAFE_COLUMNS,
)
from src.models.interfaces import ModelCategory, ModelSpec, ModelStatus, ModelTask
from src.models.registry import (
    _MODEL_CATALOG,
    get_model_spec,
    is_downstream_eligible,
)
from src.optimization.adapter import (
    DualCoreGateOptimizerAdapter,
    RoleAccessViolationError,
    UncertifiedModelError,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    SolverStatus,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.dual_prediction_turn import (
    CouplingAssumption,
    DualAircraftTurn,
    DualTurnEngine,
    LegPrediction,
    SimulationMode,
)

LOGGER = logging.getLogger("native_dual_core_pipeline")

# Canonical Checkpoint Constants
P4_ARRIVAL_CHECKPOINT_PATH: Final[Path] = Path("artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib")
P4_ARRIVAL_SHA256: Final[str] = "e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f"

DEP_XGB_CHECKPOINT_PATH: Final[Path] = Path("artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib")
DEP_XGB_SHA256: Final[str] = "e483df5fd03ce4d0eefe7b431fc289b6804589c62eda17b48fb8051849f4f6e1"
DEP_TREE_PREPROCESSOR_PATH: Final[Path] = Path("artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib")
DEP_TREE_PREPROCESSOR_SHA256: Final[str] = "ce2bb0f6f0e0ed650df3ae82306013360de5c0fafac5814307e99dfb69f62017"

DEP_RIDGE_CHECKPOINT_PATH: Final[Path] = Path("artifacts/dual_core/models/departure_ridge_baseline_v1.joblib")
DEP_RIDGE_SHA256: Final[str] = "a9a9834aecd1af10cc3967cb1108c750b200a6802586e5eb41180285cbde5aae"
DEP_LIN_PREPROCESSOR_PATH: Final[Path] = Path("artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib")
DEP_LIN_PREPROCESSOR_SHA256: Final[str] = "377a2aeafbe1969e01ef86038ec6aad974fd83ee871107e39412da7d9902e7d2"

ALLOWLISTED_MODEL_ROOTS: Final[tuple[str, ...]] = (
    "artifacts",
    "src/artifacts",
    "models",
    "temp",
    "scratch",
)


class ProvenanceMode(str, Enum):
    """Declared provenance mode for flight delay predictions."""

    NATIVE_INFERENCE = "NATIVE_INFERENCE"
    PRECOMPUTED_PREDICTION = "PRECOMPUTED_PREDICTION"
    SYNTHETIC_SIMULATION = "SYNTHETIC_SIMULATION"
    SCHEDULE_BASELINE = "SCHEDULE_BASELINE"


class TargetSemantics(str, Enum):
    """Semantic meaning of the continuous prediction target."""

    ARRIVAL_DELAY_SIGNED = "ARRIVAL_DELAY_SIGNED"
    DEPARTURE_DELAY_SIGNED = "DEPARTURE_DELAY_SIGNED"


class CheckpointVerificationError(RuntimeError):
    """Raised when model checkpoint loading fails integrity or security verification."""


class FeatureContractViolation(ValueError):
    """Raised when feature inputs fail schema, type, or boundary contracts."""


@dataclass(frozen=True)
class StandardizedPredictionRecord:
    """Immutable prediction record meeting the Section V Prediction Contract."""

    flight_id: str
    flight_direction: str
    airport: str
    prediction_cutoff_utc: str
    model_id: str
    model_role: str
    model_version: str
    model_sha256: str
    feature_schema_version: str
    target_name: str
    target_semantics: str
    predicted_delay_min: float
    prediction_timestamp_utc: str
    provenance_mode: str
    probability_delay_15: float | None = None
    predictive_quantiles: Mapping[str, float] | None = None
    distribution_parameters: Mapping[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with JSON-serializable types."""
        d = asdict(self)
        if self.predictive_quantiles is not None:
            d["predictive_quantiles"] = dict(self.predictive_quantiles)
        if self.distribution_parameters is not None:
            d["distribution_parameters"] = dict(self.distribution_parameters)
        return d


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a local file."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Checkpoint file not found: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_checkpoint_path_allowlist(
    checkpoint_path: Path,
    allowlist: Sequence[str] = ALLOWLISTED_MODEL_ROOTS,
) -> Path:
    """Ensure checkpoint path is within allowlisted local directories."""
    raw_str = str(checkpoint_path).strip()
    norm_slash = raw_str.replace("\\", "/").lower()
    if (
        not raw_str
        or norm_slash.startswith(("http:", "https:", "ftp:"))
        or "://" in norm_slash
        or norm_slash.startswith("//")
    ):
        raise CheckpointVerificationError(
            f"Untrusted or remote checkpoint URL rejected: {checkpoint_path}"
        )

    resolved = Path(checkpoint_path).resolve()
    resolved_str = str(resolved).replace("\\", "/").lower()

    # Check against allowlist prefixes
    is_allowed = False
    for allowed_prefix in allowlist:
        norm_prefix = allowed_prefix.replace("\\", "/").lower()
        if norm_prefix in resolved_str:
            is_allowed = True
            break

    if not is_allowed:
        raise CheckpointVerificationError(
            f"Checkpoint path '{resolved}' is outside allowlisted directories: {allowlist}"
        )

    return resolved


def verify_and_load_checkpoint(
    checkpoint_path: Path,
    expected_sha256: str | None = None,
    allowlist: Sequence[str] = ALLOWLISTED_MODEL_ROOTS,
) -> tuple[Any, dict[str, Any]]:
    """Verify cryptographic hash and load serialized checkpoint.

    Returns:
        Tuple of (deserialized model/preprocessor object, audit metadata).
    """
    p = verify_checkpoint_path_allowlist(checkpoint_path, allowlist=allowlist)
    if not p.exists():
        raise FileNotFoundError(f"Missing model checkpoint: {p}")

    actual_hash = compute_file_sha256(p)
    if expected_sha256 is not None and actual_hash.lower() != expected_sha256.lower():
        raise CheckpointVerificationError(
            f"SHA-256 hash mismatch for checkpoint '{p.name}'! "
            f"Expected {expected_sha256}, got {actual_hash}"
        )

    loaded_obj = joblib.load(p)
    file_stat = p.stat()
    meta = {
        "checkpoint_path": str(p).replace("\\", "/"),
        "sha256": actual_hash,
        "expected_sha256": expected_sha256,
        "file_size_bytes": file_stat.st_size,
        "object_type": f"{loaded_obj.__class__.__module__}.{loaded_obj.__class__.__name__}",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_status": "VERIFIED_VALID",
    }
    return loaded_obj, meta


def validate_pipeline_model(model_id: str, expected_task: str) -> ModelSpec:
    """Validate model registration, role, and downstream eligibility fail-closed."""
    if not model_id or not isinstance(model_id, str):
        raise UncertifiedModelError(f"Invalid model_id '{model_id}'")

    if model_id not in _MODEL_CATALOG:
        raise UncertifiedModelError(
            f"Model '{model_id}' is unknown or not registered. Fail-closed."
        )

    spec = get_model_spec(model_id)

    # Auxiliary Departure is strictly forbidden from downstream gate optimization
    if (
        spec.task == ModelTask.AUXILIARY_DEPARTURE.value
        or spec.category == ModelCategory.AUXILIARY_DEPARTURE.value
    ):
        raise RoleAccessViolationError(
            f"Model '{model_id}' is an Auxiliary Departure model (task={spec.task}). "
            "Auxiliary departure models are research-only and strictly forbidden from downstream optimization."
        )

    # Core Departure role and certification checks
    if expected_task in (ModelTask.CORE_DEPARTURE.value, "core_departure", "DEP"):
        if spec.task != ModelTask.CORE_DEPARTURE.value:
            raise RoleAccessViolationError(
                f"Model '{model_id}' has task '{spec.task}', expected '{ModelTask.CORE_DEPARTURE.value}'."
            )
        if spec.selection_role != "GATE_OUT_PREDICTION":
            raise UncertifiedModelError(
                f"Core Departure model '{model_id}' has selection_role='{spec.selection_role}'. "
                "Requires certified selection_role='GATE_OUT_PREDICTION' to feed gate optimization."
            )
        if not spec.downstream_eligible:
            raise UncertifiedModelError(
                f"Departure model '{model_id}' has downstream_eligible=False. Fail-closed."
            )

    # Core Arrival role and certification checks
    elif expected_task in (ModelTask.CORE_ARRIVAL.value, "core_arrival", "ARR"):
        if spec.task != ModelTask.CORE_ARRIVAL.value:
            raise RoleAccessViolationError(
                f"Model '{model_id}' has task '{spec.task}', expected '{ModelTask.CORE_ARRIVAL.value}'."
            )
        if not spec.downstream_eligible:
            raise UncertifiedModelError(
                f"Arrival model '{model_id}' has downstream_eligible=False. Fail-closed."
            )

    return spec


def prepare_arrival_features_for_inference(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare zero-leakage Core Arrival predictor matrix for inference without targets.

    Enforces:
    - No target columns or actual outcomes leaked (ARR_DELAY, DEP_DELAY, etc.).
    - Strict column set matching approved 11 features.
    - Cutoff at CRS_DEP_TIME - 2 hours.
    """
    forbidden_leakage = {
        "ARR_DELAY", "DEP_DELAY", "ARR_TIME", "DEP_TIME",
        "TAXI_IN", "TAXI_OUT", "WHEELS_ON", "WHEELS_OFF",
        "ACTUAL_ELAPSED_TIME", "AIR_TIME", "CANCELLED", "DIVERTED",
    }

    # Ensure no future actuals are present as predictors
    leaked = set(frame.columns).intersection(forbidden_leakage)
    # If caller has ARR_DELAY for evaluation, strip it before predictor construction
    clean_frame = frame.drop(columns=list(leaked), errors="ignore").copy()

    required_sources = set(ARR_RAW_SAFE_COLUMNS)
    missing = required_sources - set(clean_frame.columns)
    if missing:
        raise FeatureContractViolation(
            f"Core Arrival inference input missing source columns: {sorted(missing)}"
        )

    # Parse timestamps
    flight_date = pd.to_datetime(
        clean_frame["FL_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    if flight_date.isna().any():
        flight_date = pd.to_datetime(clean_frame["FL_DATE"], errors="coerce")
    departure = pd.to_datetime(
        clean_frame["CRS_DEP_TIME"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    if departure.isna().any():
        departure = pd.to_datetime(clean_frame["CRS_DEP_TIME"], errors="coerce")

    if flight_date.isna().any() or departure.isna().any():
        raise FeatureContractViolation("Missing or invalid FL_DATE / CRS_DEP_TIME timestamps")

    calendar_dow = (flight_date.dt.dayofweek + 1).astype("int64")

    X = pd.DataFrame(index=clean_frame.index)
    X["CRS_ELAPSED_TIME"] = pd.to_numeric(clean_frame["CRS_ELAPSED_TIME"], errors="coerce").astype("float64")
    X["calendar_year"] = flight_date.dt.year.astype("int64")
    X["calendar_month"] = flight_date.dt.month.astype("int64")
    X["calendar_day_of_month"] = flight_date.dt.day.astype("int64")
    X["calendar_day_of_week"] = calendar_dow
    X["is_weekend"] = calendar_dow.isin([6, 7]).astype("int8")
    X["scheduled_departure_hour"] = departure.dt.hour.astype("int64")
    X["scheduled_departure_minute"] = departure.dt.minute.astype("int64")
    X["OP_CARRIER"] = clean_frame["OP_CARRIER"].astype(str).str.strip()
    X["ORIGIN"] = clean_frame["ORIGIN"].astype(str).str.strip()
    X["OP_CARRIER_FL_NUM"] = pd.to_numeric(
        clean_frame["OP_CARRIER_FL_NUM"], errors="coerce"
    ).fillna(0).astype(int).astype(str)

    # Check for NaN in numeric
    if X["CRS_ELAPSED_TIME"].isna().any():
        raise FeatureContractViolation("CRS_ELAPSED_TIME contains missing values")

    # Align columns to exact approved order
    X = X.loc[:, list(ARR_APPROVED_COLUMNS)]

    # Assert raw source columns are allowed under Arrival leakage rules
    assert_candidate_predictors_allowed(ARR_RAW_SAFE_COLUMNS, task=ARRIVAL_TASK)

    prediction_cutoff = departure - pd.Timedelta(hours=2)
    return X, prediction_cutoff


def generate_contact_and_remote_gates(
    n_contact_gates: int,
    *,
    allow_overflow: bool = True,
    max_overflow: int | None = None,
    pooled_remote: bool = False,
) -> list[Gate]:
    """Generate contact gates plus optional overflow remote stand(s)."""
    gates: list[Gate] = []
    for i in range(1, n_contact_gates + 1):
        gates.append(
            Gate(
                gate_id=f"G{i:02d}",
                gate_index=i - 1,
                resource_type=GateResourceType.CONTACT_GATE,
                capacity=1,
                is_overflow=False,
            )
        )
    if allow_overflow and (max_overflow is None or max_overflow > 0):
        if max_overflow is None:
            gates.append(
                Gate(
                    gate_id="OVERFLOW_APRON",
                    gate_index=len(gates),
                    resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
                    capacity=math.inf,
                    is_overflow=True,
                )
            )
        elif pooled_remote:
            gates.append(
                Gate(
                    gate_id="REMOTE_POOL",
                    gate_index=len(gates),
                    resource_type=GateResourceType.FINITE_REMOTE_STAND,
                    capacity=max_overflow,
                    is_overflow=True,
                )
            )
        else:
            for ov_idx in range(1, max_overflow + 1):
                gates.append(
                    Gate(
                        gate_id=f"OVERFLOW_STAND_{ov_idx:02d}",
                        gate_index=len(gates),
                        resource_type=GateResourceType.FINITE_REMOTE_STAND,
                        capacity=1,
                        is_overflow=True,
                    )
                )
    return gates


@dataclass
class NativeDualCorePipelineConfig:
    """Execution configuration for the Native Dual-Core pipeline."""

    airport: str = "ATL"
    arrival_model_id: str = "b5_ngboost_student_t"
    arrival_checkpoint_path: Path = P4_ARRIVAL_CHECKPOINT_PATH
    arrival_expected_sha256: str | None = P4_ARRIVAL_SHA256
    departure_model_id: str = "departure_certified_point_v1"
    departure_checkpoint_path: Path = DEP_XGB_CHECKPOINT_PATH
    departure_expected_sha256: str | None = DEP_XGB_SHA256
    departure_preprocessor_path: Path | None = DEP_TREE_PREPROCESSOR_PATH
    departure_preprocessor_sha256: str | None = DEP_TREE_PREPROCESSOR_SHA256

    simulation_mode: SimulationMode = SimulationMode.DUAL_POINT
    coupling_assumption: CouplingAssumption = CouplingAssumption.INDEPENDENT
    provenance_mode: ProvenanceMode = ProvenanceMode.NATIVE_INFERENCE

    min_turnaround_min: int = 45
    default_dwell_min: int = 60
    separation_buffer_min: int = 15

    n_contact_gates: int = 20
    allow_overflow: bool = True
    max_overflow: int | None = 5
    pooled_remote: bool = False

    solver_name: str = "CPSat"
    time_limit_seconds: float = 5.0
    random_seed: int = 202601

    reassignment_weight: float = 10.0
    overflow_weight: float = 200.0
    delay_weight: float = 0.0
    conflict_weight: float = 1000.0
    risk_weight: float = 0.0


@dataclass
class NativeDualCorePipelineResult:
    """Comprehensive outputs from the Native Dual-Core pipeline run."""

    config: NativeDualCorePipelineConfig
    predictions: list[StandardizedPredictionRecord]
    turns: list[DualAircraftTurn]
    flights: list[Flight]
    gates: list[Gate]
    pairing_summary: PairingValidationSummary
    optimization_result: OptimizationResult
    constraint_diagnostic: ConstraintDiagnostic
    re_evaluated_objective: float
    manifest: dict[str, Any]
    artifacts_dir: Path | None = None


class NativeDualCorePipeline:
    """Orchestrator for end-to-end native ML inference and gate optimization."""

    def __init__(self, config: NativeDualCorePipelineConfig | None = None) -> None:
        self.config = config or NativeDualCorePipelineConfig()

    def load_and_verify_models(self) -> dict[str, Any]:
        """Validate model registry certification and load native joblib checkpoints."""
        loaded_models: dict[str, Any] = {}

        # 1. Validate and load Arrival Model
        arr_spec = validate_pipeline_model(
            self.config.arrival_model_id, expected_task=ModelTask.CORE_ARRIVAL.value
        )
        arr_model, arr_meta = verify_and_load_checkpoint(
            self.config.arrival_checkpoint_path,
            expected_sha256=self.config.arrival_expected_sha256,
        )
        loaded_models["arrival"] = {
            "model": arr_model,
            "spec": arr_spec,
            "meta": arr_meta,
        }

        # 2. Validate and load Departure Model (if dual-core enabled)
        if self.config.simulation_mode != SimulationMode.ARRIVAL_ONLY_LEGACY:
            dep_spec = validate_pipeline_model(
                self.config.departure_model_id, expected_task=ModelTask.CORE_DEPARTURE.value
            )
            dep_model, dep_meta = verify_and_load_checkpoint(
                self.config.departure_checkpoint_path,
                expected_sha256=self.config.departure_expected_sha256,
            )

            dep_preprocessor = None
            prep_meta = None
            if self.config.departure_preprocessor_path is not None:
                dep_preprocessor, prep_meta = verify_and_load_checkpoint(
                    self.config.departure_preprocessor_path,
                    expected_sha256=self.config.departure_preprocessor_sha256,
                )

            loaded_models["departure"] = {
                "model": dep_model,
                "preprocessor": dep_preprocessor,
                "spec": dep_spec,
                "meta": dep_meta,
                "prep_meta": prep_meta,
            }

        return loaded_models

    def run_native_inference(
        self,
        inbound_df: pd.DataFrame,
        outbound_df: pd.DataFrame,
        loaded_models: dict[str, Any],
    ) -> tuple[list[StandardizedPredictionRecord], dict[str, float]]:
        """Run native model inference for inbound and outbound flights."""
        prediction_records: list[StandardizedPredictionRecord] = []
        delay_lookup: dict[str, float] = {}
        now_utc = datetime.now(timezone.utc).isoformat()

        # A. Arrival Inference
        arr_entry = loaded_models["arrival"]
        arr_model = arr_entry["model"]
        arr_spec = arr_entry["spec"]
        arr_meta = arr_entry["meta"]

        if not inbound_df.empty:
            X_arr, cutoffs_arr = prepare_arrival_features_for_inference(inbound_df)
            flight_ids_arr = [
                str(k) for k in inbound_df.get("flight_key", inbound_df.index)
            ]

            # Probabilistic distribution or Point prediction
            if getattr(arr_spec, "probabilistic", False) and hasattr(arr_model, "predict_distribution"):
                dist = arr_model.predict_distribution(X_arr)
                mu = np.asarray(dist["mu"], dtype=float)
                sigma = np.asarray(dist["sigma"], dtype=float)
                df_val = np.asarray(dist["df"], dtype=float)

                # Validate distribution parameters
                if not np.all(np.isfinite(mu)) or not np.all(np.isfinite(sigma)) or not np.all(np.isfinite(df_val)):
                    raise ValueError("Non-finite distribution parameters detected in native arrival inference")
                if np.any(sigma <= 0.0):
                    raise ValueError("Non-positive sigma detected in native arrival distribution")
                if np.any(df_val <= 2.0):
                    raise ValueError("Degrees of freedom df <= 2 detected in Student-T distribution")

                # Compute quantiles and P(delay >= 15)
                for i, fid in enumerate(flight_ids_arr):
                    m_i = float(mu[i])
                    s_i = float(sigma[i])
                    nu_i = float(df_val[i])
                    # Student-T survival function for P(Y >= 15)
                    p_15 = float(student_t.sf((15.0 - m_i) / s_i, df=nu_i))
                    q10 = float(m_i + s_i * student_t.ppf(0.10, df=nu_i))
                    q50 = m_i
                    q90 = float(m_i + s_i * student_t.ppf(0.90, df=nu_i))

                    rec = StandardizedPredictionRecord(
                        flight_id=fid,
                        flight_direction="ARR",
                        airport=self.config.airport,
                        prediction_cutoff_utc=str(cutoffs_arr.iloc[i]),
                        model_id=arr_spec.model_id,
                        model_role=arr_spec.task,
                        model_version=arr_spec.artifact_version,
                        model_sha256=arr_meta["sha256"],
                        feature_schema_version=arr_spec.feature_version,
                        target_name="ARR_DELAY",
                        target_semantics=TargetSemantics.ARRIVAL_DELAY_SIGNED.value,
                        predicted_delay_min=round(m_i, 2),
                        prediction_timestamp_utc=now_utc,
                        provenance_mode=self.config.provenance_mode.value,
                        probability_delay_15=round(p_15, 4),
                        predictive_quantiles={"q10": round(q10, 2), "q50": round(q50, 2), "q90": round(q90, 2)},
                        distribution_parameters={"mu": round(m_i, 2), "sigma": round(s_i, 2), "df": round(nu_i, 2)},
                    )
                    prediction_records.append(rec)
                    delay_lookup[fid] = m_i
            else:
                # Standard Point Regressor
                preds = np.asarray(arr_model.predict(X_arr), dtype=float)
                for i, fid in enumerate(flight_ids_arr):
                    p_val = float(preds[i])
                    rec = StandardizedPredictionRecord(
                        flight_id=fid,
                        flight_direction="ARR",
                        airport=self.config.airport,
                        prediction_cutoff_utc=str(cutoffs_arr.iloc[i]),
                        model_id=arr_spec.model_id,
                        model_role=arr_spec.task,
                        model_version=arr_spec.artifact_version,
                        model_sha256=arr_meta["sha256"],
                        feature_schema_version=arr_spec.feature_version,
                        target_name="ARR_DELAY",
                        target_semantics=TargetSemantics.ARRIVAL_DELAY_SIGNED.value,
                        predicted_delay_min=round(p_val, 2),
                        prediction_timestamp_utc=now_utc,
                        provenance_mode=self.config.provenance_mode.value,
                    )
                    prediction_records.append(rec)
                    delay_lookup[fid] = p_val

        # B. Departure Inference (if dual-core enabled)
        if self.config.simulation_mode != SimulationMode.ARRIVAL_ONLY_LEGACY and not outbound_df.empty:
            dep_entry = loaded_models["departure"]
            dep_model = dep_entry["model"]
            dep_prep = dep_entry["preprocessor"]
            dep_spec = dep_entry["spec"]
            dep_meta = dep_entry["meta"]

            prep_inf = prepare_departure_inference(outbound_df)
            X_dep = prep_inf.X
            cutoffs_dep = prep_inf.prediction_cutoff
            flight_ids_dep = [
                str(k) for k in outbound_df.get("flight_key", outbound_df.index)
            ]

            X_dep_trans = dep_prep.transform(X_dep) if dep_prep is not None else X_dep
            preds_dep = np.asarray(dep_model.predict(X_dep_trans), dtype=float)

            for i, fid in enumerate(flight_ids_dep):
                d_val = float(preds_dep[i])
                rec = StandardizedPredictionRecord(
                    flight_id=fid,
                    flight_direction="DEP",
                    airport=self.config.airport,
                    prediction_cutoff_utc=str(cutoffs_dep.iloc[i]),
                    model_id=dep_spec.model_id,
                    model_role=dep_spec.task,
                    model_version=dep_spec.artifact_version,
                    model_sha256=dep_meta["sha256"],
                    feature_schema_version=dep_spec.feature_version,
                    target_name="DEP_DELAY",
                    target_semantics=TargetSemantics.DEPARTURE_DELAY_SIGNED.value,
                    predicted_delay_min=round(d_val, 2),
                    prediction_timestamp_utc=now_utc,
                    provenance_mode=self.config.provenance_mode.value,
                )
                prediction_records.append(rec)
                delay_lookup[fid] = d_val

        return prediction_records, delay_lookup

    def build_turns_from_pairs(
        self,
        legs: Mapping[str, FlightLeg],
        pairs: Sequence[TurnPair],
        delay_lookup: Mapping[str, float],
    ) -> tuple[list[DualAircraftTurn], PairingValidationSummary]:
        """Validate pairs and synthesize DualAircraftTurn domain entities."""
        validator = PairingValidator(min_turnaround_min=self.config.min_turnaround_min)
        valid_pairs, summary = validator.validate_pairs(legs, pairs)

        engine = DualTurnEngine(
            min_turnaround_min=self.config.min_turnaround_min,
            default_dwell_min=self.config.default_dwell_min,
            separation_buffer_min=self.config.separation_buffer_min,
        )

        turns: list[DualAircraftTurn] = []
        for pair in valid_pairs:
            arr_delay = delay_lookup.get(pair.arrival_leg_id, 0.0) if pair.arrival_leg_id else 0.0
            dep_delay = delay_lookup.get(pair.departure_leg_id, 0.0) if pair.departure_leg_id else 0.0

            turn = engine.synthesize_turn(
                pair=pair,
                legs=legs,
                arrival_prediction=arr_delay,
                departure_prediction=dep_delay if self.config.simulation_mode != SimulationMode.ARRIVAL_ONLY_LEGACY else None,
                mode=self.config.simulation_mode,
                coupling_assumption=self.config.coupling_assumption if self.config.simulation_mode == SimulationMode.DUAL_PROBABILISTIC else None,
            )
            turns.append(turn)

        return turns, summary

    def execute_solver(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
    ) -> tuple[OptimizationResult, ConstraintDiagnostic, float]:
        """Run selected solver and perform independent hard constraint audit."""
        opt_cfg = GateOptimizationConfig(
            reassignment_weight=self.config.reassignment_weight,
            overflow_weight=self.config.overflow_weight,
            delay_weight=self.config.delay_weight,
            conflict_weight=self.config.conflict_weight,
            risk_weight=self.config.risk_weight,
            time_limit_seconds=self.config.time_limit_seconds,
            random_seed=self.config.random_seed,
            min_turnaround_minutes=self.config.min_turnaround_min,
            default_dwell_minutes=self.config.default_dwell_min,
            separation_buffer_minutes=self.config.separation_buffer_min,
            dual_core_gate_enabled=self.config.simulation_mode != SimulationMode.ARRIVAL_ONLY_LEGACY,
        )

        s_name = self.config.solver_name.lower()
        if "cpsat" in s_name or "cp_sat" in s_name:
            solver = CPSatGateSolver(config=opt_cfg)
        elif "greedy" in s_name:
            solver = DeterministicGreedyGateSolver(config=opt_cfg)
        elif "hybrid" in s_name:
            solver = HybridGateSolver(config=opt_cfg)
        elif "sa" in s_name or "anneal" in s_name:
            sa_cfg = SAConfig(
                time_budget_seconds=self.config.time_limit_seconds,
                seed=self.config.random_seed,
            )
            solver = SimulatedAnnealingGateSolver(config=opt_cfg, sa_config=sa_cfg)
        else:
            raise ValueError(f"Unknown solver name '{self.config.solver_name}'")

        # Solve assignment
        result = solver.solve(flights, gates, allow_overflow=self.config.allow_overflow)

        # Independent Hard-Constraint Audit outside solver
        diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gates,
            assignments=result.assignments,
        )

        # Independent Objective Re-evaluation
        eval_res = evaluate_gate_assignment(
            assignments=result.assignments,
            flights=flights,
            gates=gates,
            config=opt_cfg,
            runtime_ms=result.runtime_ms,
            solver_status=result.status,
            solver_name=self.config.solver_name,
        )

        return result, diag, eval_res.objective_value

    def run(
        self,
        inbound_df: pd.DataFrame,
        outbound_df: pd.DataFrame,
        legs: Mapping[str, FlightLeg],
        pairs: Sequence[TurnPair],
        *,
        output_dir: Path | None = None,
    ) -> NativeDualCorePipelineResult:
        """Execute end-to-end native Predict-then-Optimize pipeline."""
        t_start = time.perf_counter()

        # Step 1: Load and verify models
        LOGGER.info("Step 1: Verifying and loading model checkpoints...")
        loaded_models = self.load_and_verify_models()

        # Step 2: Native model inference
        LOGGER.info("Step 2: Executing native model inference...")
        predictions, delay_lookup = self.run_native_inference(
            inbound_df=inbound_df,
            outbound_df=outbound_df,
            loaded_models=loaded_models,
        )

        # Step 3: Turn pairing and physical timeline synthesis
        LOGGER.info("Step 3: Synthesizing aircraft turns and physical timelines...")
        turns, pairing_summary = self.build_turns_from_pairs(legs, pairs, delay_lookup)

        # Step 4: Optimization domain conversion via adapter
        LOGGER.info("Step 4: Converting turns to optimization flights via RBAC adapter...")
        dual_enabled = self.config.simulation_mode != SimulationMode.ARRIVAL_ONLY_LEGACY
        adapter = DualCoreGateOptimizerAdapter(
            config=GateOptimizationConfig(
                dual_core_gate_enabled=dual_enabled,
                min_turnaround_minutes=self.config.min_turnaround_min,
                default_dwell_minutes=self.config.default_dwell_min,
                separation_buffer_minutes=self.config.separation_buffer_min,
            )
        )
        flights = adapter.turns_to_flights(
            turns,
            departure_model_id=self.config.departure_model_id if dual_enabled else None,
            arrival_model_id=self.config.arrival_model_id if dual_enabled else None,
        )

        # Step 5: Build gate topology
        LOGGER.info("Step 5: Generating gate resources...")
        gates = generate_contact_and_remote_gates(
            n_contact_gates=self.config.n_contact_gates,
            allow_overflow=self.config.allow_overflow,
            max_overflow=self.config.max_overflow,
            pooled_remote=self.config.pooled_remote,
        )

        # Step 6: Solver execution and independent verification
        LOGGER.info("Step 6: Executing solver and independent audit...")
        opt_res, diag, re_eval_obj = self.execute_solver(flights, gates)

        t_elapsed = time.perf_counter() - t_start

        reassignments_count = sum(
            1 for f in flights
            if f.nominal_gate_id is not None
            and opt_res.assignments.get(f.flight_id) is not None
            and opt_res.assignments[f.flight_id].gate_id != f.nominal_gate_id
        )

        # Step 7: Build comprehensive run manifest
        manifest = {
            "pipeline": "NativeDualCorePredictThenOptimizePipeline",
            "phase": "P07",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(t_elapsed, 4),
            "config": {
                "airport": self.config.airport,
                "simulation_mode": self.config.simulation_mode.value,
                "solver_name": self.config.solver_name,
                "time_limit_seconds": self.config.time_limit_seconds,
                "random_seed": self.config.random_seed,
                "n_contact_gates": self.config.n_contact_gates,
                "max_overflow": self.config.max_overflow,
                "arrival_model_id": self.config.arrival_model_id,
                "departure_model_id": self.config.departure_model_id if dual_enabled else "N/A",
                "provenance_mode": self.config.provenance_mode.value,
            },
            "model_provenance": {
                "arrival": loaded_models["arrival"]["meta"],
                "departure": loaded_models["departure"]["meta"] if "departure" in loaded_models else None,
            },
            "pairing_summary": asdict(pairing_summary),
            "counts": {
                "inbound_legs": len(inbound_df),
                "outbound_legs": len(outbound_df),
                "predictions_generated": len(predictions),
                "turns_synthesized": len(turns),
                "flights_optimized": len(flights),
                "gates_available": len(gates),
            },
            "optimization": {
                "status": opt_res.status,
                "feasible": opt_res.feasible,
                "objective_value": round(opt_res.objective_value, 4),
                "re_evaluated_objective": round(re_eval_obj, 4),
                "runtime_ms": round(opt_res.runtime_ms, 2),
                "independent_verifier_valid": diag.is_valid,
                "hard_constraint_violations": diag.hard_constraint_violations_count,
                "conflicts_count": diag.conflict_count,
                "reassignments_count": reassignments_count,
                "contact_count": diag.contact_count,
                "remote_count": diag.remote_count,
                "unassigned_count": diag.unassigned_count,
            },
        }

        pipeline_result = NativeDualCorePipelineResult(
            config=self.config,
            predictions=predictions,
            turns=turns,
            flights=flights,
            gates=gates,
            pairing_summary=pairing_summary,
            optimization_result=opt_res,
            constraint_diagnostic=diag,
            re_evaluated_objective=re_eval_obj,
            manifest=manifest,
            artifacts_dir=output_dir,
        )

        if output_dir is not None:
            self.export_artifacts(output_dir, pipeline_result)

        return pipeline_result

    def export_artifacts(
        self,
        output_dir: Path,
        result: NativeDualCorePipelineResult,
    ) -> None:
        """Export artifacts to disk meeting Section XIV requirements."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # 1. run_manifest.json
        with open(out / "run_manifest.json", "w", encoding="utf-8") as f:
            json.dump(result.manifest, f, indent=2)

        # 2. predictions_sample.csv
        pred_dicts = [p.to_dict() for p in result.predictions]
        pred_df = pd.DataFrame(pred_dicts)
        pred_df.to_csv(out / "predictions_sample.csv", index=False)

        # 3. turn_pairing_audit.json
        with open(out / "turn_pairing_audit.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "pairing_summary": asdict(result.pairing_summary),
                    "turns_count": len(result.turns),
                    "turns_sample": [t.to_dict() for t in result.turns[:20]],
                },
                f,
                indent=2,
            )

        # 4. optimization_result.json
        with open(out / "optimization_result.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "status": result.optimization_result.status,
                    "feasible": result.optimization_result.feasible,
                    "objective_value": result.optimization_result.objective_value,
                    "re_evaluated_objective": result.re_evaluated_objective,
                    "runtime_ms": result.optimization_result.runtime_ms,
                    "diagnostics": result.constraint_diagnostic.to_dict(),
                    "assignments": {
                        fid: asdict(assign)
                        for fid, assign in result.optimization_result.assignments.items()
                    },
                },
                f,
                indent=2,
            )
