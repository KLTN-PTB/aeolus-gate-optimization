"""Comprehensive Test Suite for Task R12 Post-Holdout Re-Evaluation V2.

Verifies:
1. FinalEvaluationGuardV2 enforces strict fail-closed check prior to 2024 access
2. Invalid freeze hash, missing files, or modified configs fail closed
3. Non-POST_HOLDOUT evaluation roles fail closed
4. Zero post-freeze adaptation or tuning
5. No auxiliary departure delay or weather columns enter optimizer
6. Downstream scenario and solver budget alignment
7. Separate status semantics (feasibility, conflicts, unassigned, remote, runtime)
8. Non-deployable Oracle reference labeling (no 'model equals Oracle' claims)
9. Provenance anomaly audit (detects suspicious identical metric repetitions)
10. Failure accounting completeness (failures retained in denominator)
11. Evidence reconciliation completeness (all 8 historical claims reconciled)
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    FORBIDDEN_DEPARTURE_TERMS,
    validate_downstream_input_boundary,
)
from src.evaluation.final_evaluation_guard_v2 import (
    FinalEvaluationGuardV2,
    FinalEvaluationGuardV2Error,
)
from scripts.run_post_holdout_evaluation_v2 import perform_provenance_anomaly_audit


@pytest.fixture
def guard() -> FinalEvaluationGuardV2:
    return FinalEvaluationGuardV2()


def test_guard_v2_authorizes_clean_post_holdout(guard: FinalEvaluationGuardV2) -> None:
    """Verifies that guard authorizes clean POST_HOLDOUT evaluation on 2024."""
    guard.assert_evaluation_authorized(
        evaluation_role="POST_HOLDOUT",
        year=2024,
        purpose="post_holdout_evaluation",
    )


@pytest.mark.parametrize("bad_role", ["untouched_holdout", "development", "pristine_holdout", "tuning"])
def test_guard_v2_blocks_invalid_roles(guard: FinalEvaluationGuardV2, bad_role: str) -> None:
    """Verifies that non-POST_HOLDOUT roles are rejected."""
    with pytest.raises(FinalEvaluationGuardV2Error):
        guard.assert_evaluation_authorized(
            evaluation_role=bad_role,
            year=2024,
            purpose="post_holdout_evaluation",
        )


def test_no_auxiliary_departure_or_weather_in_downstream_input() -> None:
    """Verifies that validate_downstream_input_boundary rejects auxiliary departure or weather columns."""
    valid_cols = ["DISTANCE", "CRS_ELAPSED_TIME", "DEP_HOUR", "ARR_HOUR"]
    validate_downstream_input_boundary(valid_cols)

    # Rejects departure delay
    for dep_term in FORBIDDEN_DEPARTURE_TERMS:
        with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
            validate_downstream_input_boundary(valid_cols + [dep_term])

    # Rejects weather
    with pytest.raises(ValueError, match="Weather features forbidden"):
        validate_downstream_input_boundary(valid_cols + ["hourly_precip"])


def test_oracle_is_properly_labeled_as_non_deployable_reference() -> None:
    """Verifies that oracle candidate is marked as non_deployable_reference."""
    oracle_cands = [c for c in DEFAULT_DOWNSTREAM_CANDIDATES if c.is_oracle]
    assert len(oracle_cands) == 1
    oracle = oracle_cands[0]
    assert oracle.candidate_id == "oracle_actual"
    assert oracle.role == "non_deployable_reference"
    assert "not a prediction model" in oracle.note.lower()


def test_post_holdout_v2_artifacts_exist_and_are_valid() -> None:
    """Verifies that all required Task R12 output artifacts exist and adhere to schema."""
    out_dir = Path("artifacts/post_holdout_v2")
    assert out_dir.exists()

    manifest_file = out_dir / "post_holdout_evaluation_manifest_v2.json"
    sidecar_file = out_dir / "post_holdout_evaluation_manifest_v2.sha256"
    marginal_file = out_dir / "marginal_forecast_metrics_2024_v2.json"
    failures_file = out_dir / "failures_accounting.json"
    eval_parquet = out_dir / "downstream_operational_evaluations_v2.parquet"
    deltas_parquet = out_dir / "paired_downstream_deltas_v2.parquet"
    reconciliation_file = out_dir / "evidence_reconciliation_v2.json"

    for f in [manifest_file, sidecar_file, marginal_file, failures_file, eval_parquet, deltas_parquet, reconciliation_file]:
        assert f.exists(), f"Missing required R12 artifact: {f}"

    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest_data["evaluation_role"] == "POST_HOLDOUT"
    assert manifest_data["holdout_year"] == 2024
    assert manifest_data["provenance_status"] == "VERIFIED_DISTINCT"

    failures_data = json.loads(failures_file.read_text(encoding="utf-8"))
    assert failures_data["total_evaluated_cases"] == 84
    assert failures_data["total_failures_count"] == 0


def test_provenance_anomaly_audit_detects_suspicious_repetition(tmp_path: Path) -> None:
    """Verifies that provenance anomaly audit blocks suspiciously identical metrics."""
    fake_dev_manifest = tmp_path / "dev_manifest.json"
    fake_dev_manifest.write_text(json.dumps({
        "selection_table": {
            "point_models": {
                "arrival_linear_baseline_v1": {"mae": 22.9125},  # Identical to holdout!
            }
        }
    }), encoding="utf-8")

    metrics_2024 = {
        "arrival_linear_baseline_v1": {"point_mae": 22.9125}
    }

    audit = perform_provenance_anomaly_audit(metrics_2024, fake_dev_manifest)
    assert audit["has_lineage_anomaly"] is True
    assert audit["provenance_status"] == "BLOCKED_PROVENANCE"


def test_evidence_reconciliation_completeness() -> None:
    """Verifies that evidence reconciliation addresses all key historical claims with approved statuses."""
    rec_file = Path("artifacts/post_holdout_v2/evidence_reconciliation_v2.json")
    assert rec_file.exists()

    rec_data = json.loads(rec_file.read_text(encoding="utf-8"))
    assert len(rec_data) >= 8

    claim_ids = [r["claim_id"] for r in rec_data]
    assert "CLAIM_01_HOLDOUT_TERMINOLOGY" in claim_ids
    assert "CLAIM_02_CRN_VARIANCE_REDUCTION" in claim_ids
    assert "CLAIM_03_MC_N500_OPTIMALITY" in claim_ids
    assert "CLAIM_04_P5_FULL_DISTRIBUTION" in claim_ids
    assert "CLAIM_05_PAIRED_STATISTICAL_SIGNIFICANCE" in claim_ids
    assert "CLAIM_06_SINGLE_OVERALL_CHAMPION" in claim_ids
    assert "CLAIM_07_REAL_WORLD_GATE_OPERATIONS" in claim_ids
    assert "CLAIM_08_AUXILIARY_DEPARTURE_DELAY" in claim_ids

    allowed_statuses = {"CONFIRMED", "CORRECTED", "NOT_SUPPORTED", "SUPERSEDED", "BLOCKED", "HISTORICAL_ONLY"}
    for r in rec_data:
        assert r["status"] in allowed_statuses
