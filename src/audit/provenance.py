"""Provenance Graph and Traceability Framework for Aeolus Stages 8-11.

Traces full provenance chain:
metric -> prediction/simulation artifact -> candidate/system ID -> model artifact
-> preprocessing -> calibration -> dependence config -> seed -> dataset/split -> selection decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


def compute_sha256(filepath: Path) -> str:
    """Compute file SHA-256 digest or return missing string."""
    if not filepath.exists():
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class AuditTableRecord:
    """Standardized record for the audit table required by Step 2."""

    artifact_id: str
    stage: str
    year: int
    role: str
    input_dataset: str
    candidate_id: str
    model_hash: str
    config_hash: str
    seed: int | list[int]
    selection_dependency: str
    holdout_dependency: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricTraceRecord:
    """Full lineage trace for an individual reported metric."""

    metric_name: str
    metric_value: Any
    metric_type: str  # "forecast_evaluation" or "downstream_simulation"
    stage: str
    year: int
    source_artifact: str
    candidate_id: str
    marginal_candidate_id: str
    dependence_candidate_id: str
    model_artifact_path: str
    model_artifact_hash: str
    preprocessing_spec: str
    calibration_spec: str
    dependence_config: dict[str, Any]
    seed_policy: dict[str, Any]
    dataset_split: str
    selection_dependency: str
    holdout_dependency: str
    validity_status: str
    audit_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProvenanceTracker:
    """Constructs and queries the provenance graph across Stages 8 to 11."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or Path(__file__).resolve().parents[2]
        self.manifest_dir = self.root / "artifacts" / "manifests"
        self.prob_dir = self.root / "artifacts" / "probabilistic"
        self.eval_dir = self.root / "artifacts" / "evaluation"

    def build_audit_table(self) -> list[AuditTableRecord]:
        """Construct the comprehensive audit table across all Stage 8-11 artifacts."""
        records: list[AuditTableRecord] = []

        # 1. Stage 8 Manifest
        s8_path = self.manifest_dir / "selected_system_manifest_v1.json"
        if s8_path.exists():
            s8_data = json.loads(s8_path.read_text(encoding="utf-8"))
            s8_hash = compute_sha256(s8_path)
            cand_id = s8_data.get("selected_winning_system", {}).get("candidate_id", "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula")
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/manifests/selected_system_manifest_v1.json",
                    stage="STAGE_8_SYSTEM_SELECTION",
                    year=2023,
                    role="DEVELOPMENT_MODEL_SELECTION",
                    input_dataset="inbound_atl/year=2016-2022 (train) + year=2023 (selection sample 5000)",
                    candidate_id=cand_id,
                    model_hash="checkpoint_unserialized_fitted_in_memory",
                    config_hash=s8_hash,
                    seed=202601,
                    selection_dependency="artifacts/manifests/probabilistic_stage7_system_candidates_v1.json",
                    holdout_dependency="NONE (2024 claimed sealed)",
                    status="VALID_ONE_TIME_SELECTION",
                )
            )

        # 2. Stage 9 Manifest
        s9_path = self.manifest_dir / "probabilistic_stage9_gate_simulation_v1.json"
        if s9_path.exists():
            s9_hash = compute_sha256(s9_path)
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json",
                    stage="STAGE_9_GATE_SIMULATION",
                    year=2023,
                    role="DOWNSTREAM_GATE_SIMULATION_UTILITY",
                    input_dataset="inbound_atl/year=2023 (same 25 multi-flight days / 529 flights from Stage 8)",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    model_hash="refit_in_memory_seed_202601",
                    config_hash=s9_hash,
                    seed=202601,
                    selection_dependency="artifacts/manifests/selected_system_manifest_v1.json",
                    holdout_dependency="NONE (2024 claimed sealed)",
                    status="POST_SELECTION_REUSE_OF_2023_DATA",
                )
            )

        # 3. Stage 10 Frozen Model Weights
        w_path = self.prob_dir / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        w_hash = compute_sha256(w_path) if w_path.exists() else "MISSING"
        if w_path.exists():
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib",
                    stage="STAGE_10_FULL_SYSTEM_FREEZE",
                    year=2022,
                    role="FROZEN_MODEL_CHECKPOINT",
                    input_dataset="inbound_atl/year=2016-2022 (7000 stratified training rows)",
                    candidate_id="B5_ngboost_student_t",
                    model_hash=w_hash,
                    config_hash=w_hash,
                    seed=202601,
                    selection_dependency="artifacts/manifests/selected_system_manifest_v1.json",
                    holdout_dependency="NONE",
                    status="FROZEN_MODEL_WEIGHTS",
                )
            )

        # 4. Stage 10 Full System Freeze Manifest
        s10_path = self.manifest_dir / "full_system_freeze_manifest_v1.json"
        if s10_path.exists():
            s10_hash = compute_sha256(s10_path)
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/manifests/full_system_freeze_manifest_v1.json",
                    stage="STAGE_10_FULL_SYSTEM_FREEZE",
                    year=2024,
                    role="PRE_HOLDOUT_FREEZE_MANIFEST",
                    input_dataset="N/A (Configuration specification locking 20 components)",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    model_hash=w_hash,
                    config_hash=s10_hash,
                    seed=202601,
                    selection_dependency="artifacts/manifests/selected_system_manifest_v1.json",
                    holdout_dependency="GATE_KEEPER_FOR_2024",
                    status="INCOMPLETE_FREEZE_MISSING_GIT_HASH_AND_SIM_CONFIG_MISMATCH",
                )
            )

        # 5. Stage 10 System Freeze Manifest (for access guard)
        guard_m_path = self.manifest_dir / "system_freeze_manifest.json"
        if guard_m_path.exists():
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/manifests/system_freeze_manifest.json",
                    stage="STAGE_10_ACCESS_GUARD_AUTHORIZATION",
                    year=2024,
                    role="ACCESS_GUARD_AUTHORIZER",
                    input_dataset="N/A",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    model_hash=w_hash,
                    config_hash=compute_sha256(guard_m_path),
                    seed=202601,
                    selection_dependency="full_system_freeze_manifest_v1.json",
                    holdout_dependency="AUTHORIZES_2024_FINAL_EVALUATION",
                    status="FREEZE_FLAG_ACTIVE",
                )
            )

        # 6. Stage 11 Final Holdout Manifest
        s11_path = self.manifest_dir / "final_holdout_2024_evaluation_v1.json"
        if s11_path.exists():
            s11_hash = compute_sha256(s11_path)
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/manifests/final_holdout_2024_evaluation_v1.json",
                    stage="STAGE_11_FINAL_HOLDOUT",
                    year=2024,
                    role="FINAL_HOLDOUT",
                    input_dataset="inbound_atl/year=2024 (5000 stratified flights, 25 days / 579 simulation flights)",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    model_hash=w_hash,
                    config_hash=s11_hash,
                    seed=202601,
                    selection_dependency="full_system_freeze_manifest_v1.json",
                    holdout_dependency="OPENED_2024_OBSERVED_OUTCOME",
                    status="PREVIOUSLY_OPENED_HOLDOUT_SUBSEQUENT_CHANGES_ARE_POST_HOLDOUT",
                )
            )

        # 7. Stage 11 Parquet Predictions
        parquet_path = self.eval_dir / "final_holdout_2024" / "holdout_predictions_2024.parquet"
        if parquet_path.exists():
            records.append(
                AuditTableRecord(
                    artifact_id="artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet",
                    stage="STAGE_11_FINAL_HOLDOUT",
                    year=2024,
                    role="HOLDOUT_PREDICTION_PAYLOAD",
                    input_dataset="inbound_atl/year=2024 (5000 instances)",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    model_hash=w_hash,
                    config_hash=compute_sha256(parquet_path),
                    seed=202601,
                    selection_dependency="full_system_freeze_manifest_v1.json",
                    holdout_dependency="2024_GROUND_TRUTH_REALIZED_DELAYS",
                    status="STATIC_SAVED_PREDICTIONS",
                )
            )

        return records

    def build_metric_provenance_traces(self) -> list[MetricTraceRecord]:
        """Trace full lineage for every key metric reported in Stages 8-11."""
        traces: list[MetricTraceRecord] = []

        # Load manifests
        s8_file = self.manifest_dir / "selected_system_manifest_v1.json"
        s9_file = self.manifest_dir / "probabilistic_stage9_gate_simulation_v1.json"
        s10_file = self.manifest_dir / "full_system_freeze_manifest_v1.json"
        s11_file = self.manifest_dir / "final_holdout_2024_evaluation_v1.json"
        w_file = self.prob_dir / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        w_hash = compute_sha256(w_file) if w_file.exists() else "MISSING"

        # --- Stage 8 Metrics ---
        if s8_file.exists():
            s8 = json.loads(s8_file.read_text(encoding="utf-8"))
            win = s8.get("selected_winning_system", {})
            m_metrics = win.get("marginal_metrics", {})
            j_metrics = win.get("joint_metrics", {})

            # Marginal CRPS 2023
            traces.append(
                MetricTraceRecord(
                    metric_name="marginal_crps_2023",
                    metric_value=m_metrics.get("crps"),
                    metric_type="forecast_evaluation",
                    stage="STAGE_8_SYSTEM_SELECTION",
                    year=2023,
                    source_artifact="artifacts/manifests/selected_system_manifest_v1.json",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    marginal_candidate_id="B5_ngboost_student_t",
                    dependence_candidate_id="DEP_D2_gaussian_copula",
                    model_artifact_path="in-memory fit of B5NGBoostStudentT(50, lr=0.005)",
                    model_artifact_hash="unserialized_at_stage8",
                    preprocessing_spec="TreePreprocessor fit on 2016-2022 (sample=1000/yr)",
                    calibration_spec="Discrete rPIT on Student-T with df_floor=2.1, sigma_floor=1.0",
                    dependence_config={"temporal_length_scale": 120.0, "carrier_corr": 0.15, "psd_floor": 1e-6},
                    seed_policy={"deployment_seed": 202601},
                    dataset_split="val_year=2023, sample_val=5000",
                    selection_dependency="artifacts/manifests/probabilistic_stage7_system_candidates_v1.json",
                    holdout_dependency="2024 sealed",
                    validity_status="VALID_FORECAST_EVALUATION",
                    audit_notes=["Evaluated strictly on 2023 validation sample.", "Proper scoring gate passed."],
                )
            )

            # Daily aggregate CRPS 2023
            traces.append(
                MetricTraceRecord(
                    metric_name="daily_aggregate_crps_2023",
                    metric_value=j_metrics.get("daily_aggregate_crps"),
                    metric_type="forecast_evaluation",
                    stage="STAGE_8_SYSTEM_SELECTION",
                    year=2023,
                    source_artifact="artifacts/manifests/selected_system_manifest_v1.json",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    marginal_candidate_id="B5_ngboost_student_t",
                    dependence_candidate_id="DEP_D2_gaussian_copula",
                    model_artifact_path="in-memory fit of B5NGBoostStudentT(50, lr=0.005)",
                    model_artifact_hash="unserialized_at_stage8",
                    preprocessing_spec="TreePreprocessor fit on 2016-2022",
                    calibration_spec="Discrete rPIT",
                    dependence_config={"family": "Gaussian copula", "tau": 120.0, "rho": 0.15},
                    seed_policy={"deployment_seed": 202601, "scenarios": 200},
                    dataset_split="30 multi-flight days in 2023 (>=8 flights/day)",
                    selection_dependency="artifacts/manifests/probabilistic_stage7_system_candidates_v1.json",
                    holdout_dependency="2024 sealed",
                    validity_status="VALID_JOINT_FORECAST_METRIC",
                    audit_notes=["Joint delay aggregation evaluated across 30 operational days in 2023."],
                )
            )

        # --- Stage 9 Metrics ---
        if s9_file.exists():
            s9 = json.loads(s9_file.read_text(encoding="utf-8"))
            benefit = s9.get("downstream_measurable_benefit", {})

            # Conflict Occurrence Error Reduction
            traces.append(
                MetricTraceRecord(
                    metric_name="conflict_occurrence_error_reduction_2023",
                    metric_value=benefit.get("conflict_occurrence_error_reduction"),
                    metric_type="downstream_simulation",
                    stage="STAGE_9_GATE_SIMULATION",
                    year=2023,
                    source_artifact="artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    marginal_candidate_id="B5_ngboost_student_t",
                    dependence_candidate_id="DEP_D2_gaussian_copula",
                    model_artifact_path="in-memory fit of B5NGBoostStudentT(50, lr=0.005)",
                    model_artifact_hash="unserialized_at_stage9",
                    preprocessing_spec="TreePreprocessor fit on 2016-2022",
                    calibration_spec="Discrete rPIT",
                    dependence_config={"family": "Gaussian copula", "tau": 120.0, "rho": 0.15},
                    seed_policy={"deployment_seed": 202601, "scenarios_per_day": 100},
                    dataset_split="25 multi-flight days / 529 flights from 2023 (REUSED from Stage 8)",
                    selection_dependency="artifacts/manifests/selected_system_manifest_v1.json",
                    holdout_dependency="2024 sealed",
                    validity_status="POST_SELECTION_REUSE_INVALID_CLAIM_LABELING",
                    audit_notes=[
                        "CRITICAL: 25 days / 529 flights overlap 100% with Stage 8 selection sample.",
                        "CRITICAL: Ground truth is synthetic turn simulation with assumed 45m turnaround, NOT real airport gate logs.",
                        "CRITICAL: Value 83.7% is relative error reduction in synthetic conflict rate between D2 and D0, not real-world gate conflict reduction.",
                    ],
                )
            )

        # --- Stage 11 Metrics ---
        if s11_file.exists():
            s11 = json.loads(s11_file.read_text(encoding="utf-8"))
            m11 = s11.get("marginal_forecast_metrics_2024", {})
            b11 = s11.get("downstream_benefit_summary_2024", {})

            # Marginal CRPS 2024
            traces.append(
                MetricTraceRecord(
                    metric_name="marginal_crps_2024_holdout",
                    metric_value=m11.get("crps"),
                    metric_type="forecast_evaluation",
                    stage="STAGE_11_FINAL_HOLDOUT",
                    year=2024,
                    source_artifact="artifacts/manifests/final_holdout_2024_evaluation_v1.json",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    marginal_candidate_id="B5_ngboost_student_t",
                    dependence_candidate_id="DEP_D2_gaussian_copula",
                    model_artifact_path="artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib",
                    model_artifact_hash=w_hash,
                    preprocessing_spec="TreePreprocessor fit strictly on 2016-2022 (7000 rows)",
                    calibration_spec="Discrete rPIT on Student-T with df_floor=2.1, sigma_floor=1.0",
                    dependence_config={"family": "Gaussian copula", "tau": 120.0, "rho": 0.15},
                    seed_policy={"deployment_seed": 202601},
                    dataset_split="year=2024 (5000 stratified flights across 12 months)",
                    selection_dependency="full_system_freeze_manifest_v1.json",
                    holdout_dependency="2024_FINAL_HOLDOUT_EVALUATION",
                    validity_status="HISTORICAL_HOLDOUT_RESULT_NOW_POST_HOLDOUT",
                    audit_notes=[
                        "Model weights loaded directly from frozen joblib without retuning.",
                        "CRPS was 17.133m vs 16.867m in 2023 dev (gap +0.266m).",
                        "2024 was opened at 2026-09-27T18:23:46; subsequent code changes in repository are POST_HOLDOUT.",
                    ],
                )
            )

            # Conflict Occurrence Error Reduction 2024
            traces.append(
                MetricTraceRecord(
                    metric_name="conflict_occurrence_error_reduction_2024",
                    metric_value=b11.get("conflict_occurrence_error_reduction"),
                    metric_type="downstream_simulation",
                    stage="STAGE_11_FINAL_HOLDOUT",
                    year=2024,
                    source_artifact="artifacts/manifests/final_holdout_2024_evaluation_v1.json",
                    candidate_id="SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula",
                    marginal_candidate_id="B5_ngboost_student_t",
                    dependence_candidate_id="DEP_D2_gaussian_copula",
                    model_artifact_path="artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib",
                    model_artifact_hash=w_hash,
                    preprocessing_spec="TreePreprocessor fit strictly on 2016-2022",
                    calibration_spec="Discrete rPIT",
                    dependence_config={"family": "Gaussian copula", "tau": 120.0, "rho": 0.15},
                    seed_policy={"deployment_seed": 202601, "scenarios_per_day": 100},
                    dataset_split="25 multi-flight days / 579 flights in 2024",
                    selection_dependency="full_system_freeze_manifest_v1.json",
                    holdout_dependency="2024_FINAL_HOLDOUT_EVALUATION",
                    validity_status="CONTRADICTED_BY_TEXT_CLAIM",
                    audit_notes=[
                        "CRITICAL: The numeric value is -3.87234 (-387.2%), meaning D2 increased conflict occurrence error by 387% compared to D0 on 2024 holdout.",
                        "CRITICAL: Text finding in recorded_findings falsely claimed '>75% error reduction'.",
                        "CRITICAL: Ground truth is synthetic turn simulation with 30 contact gates, NOT real airport gate logs.",
                    ],
                )
            )

        return traces
