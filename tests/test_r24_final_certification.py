"""Test Suite for R24 Final Evidence Certification V3.

Verifies:
1. Manifest existence, validity, and SHA-256 sidecar checksum integrity.
2. Mandatory certification status: strictly 'CERTIFIED_WITH_LIMITATIONS'.
3. Cryptographic lineage chain across Freeze V3, Post-Holdout V3, and Selection V3.
4. Decoupled operational roles and fail-closed block on joint overall champion.
5. Downstream operational summary: 84 cases, 0 failures, 0 hard constraint violations.
6. Comprehensive claim boundary matrix with enforced bans on real-world, oracle, and 100% reproducibility claims.
7. Publication documentation in docs/audit/FINAL_EVIDENCE_CERTIFICATION_V3.md.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "final_evidence_certification_v3.json"
SIDECAR_PATH = ROOT / "artifacts" / "manifests" / "final_evidence_certification_v3.sha256"
CLAIM_AUDIT_PATH = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v3.json"
REPRO_AUDIT_PATH = ROOT / "artifacts" / "audit" / "final_reproducibility_audit_v3.json"
DOC_PATH = ROOT / "docs" / "audit" / "FINAL_EVIDENCE_CERTIFICATION_V3.md"


def test_manifest_and_sidecar_checksum() -> None:
    """Verify final certification manifest matches its SHA-256 sidecar."""
    assert MANIFEST_PATH.is_file(), f"Missing manifest: {MANIFEST_PATH}"
    assert SIDECAR_PATH.is_file(), f"Missing sidecar: {SIDECAR_PATH}"

    computed_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    sidecar_sha = SIDECAR_PATH.read_text(encoding="utf-8").strip().split()[0]
    assert computed_sha == sidecar_sha, f"Checksum mismatch: {computed_sha} != {sidecar_sha}"


def test_certification_status_is_certified_with_limitations() -> None:
    """Verify certification status is strictly CERTIFIED_WITH_LIMITATIONS."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert payload["certification_status"] == "CERTIFIED_WITH_LIMITATIONS"
    assert payload["manifest_version"] == "final_evidence_certification_v3"
    assert payload["certifying_authority"] == "AEOLUS_V4_FORENSIC_CERTIFICATION_COUNCIL"

    # Strictly ban false promotional statuses
    assert payload["certification_status"] not in {
        "SCIENTIFICALLY_PROVEN",
        "ERROR_FREE_RESEARCH",
        "100_PERCENT_REPRODUCIBLE",
        "UNCONDITIONALLY_CERTIFIED",
    }


def test_cryptographic_lineage_chain() -> None:
    """Verify all lineage hashes match actual frozen and evaluated manifests."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lineage = payload["cryptographic_lineage"]

    freeze_sha = (ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v3.sha256").read_text().split()[0]
    post_holdout_sha = (ROOT / "artifacts" / "post_holdout_v3" / "post_holdout_evaluation_manifest_v3.sha256").read_text().split()[0]
    model_sel_sha = (ROOT / "artifacts" / "manifests" / "academic_model_selection_v3.sha256").read_text().split()[0]

    assert lineage["system_freeze_manifest_v3_sha256"] == freeze_sha
    assert lineage["post_holdout_evaluation_manifest_v3_sha256"] == post_holdout_sha
    assert lineage["academic_model_selection_v3_sha256"] == model_sel_sha


def test_decoupled_operational_roles() -> None:
    """Verify decoupled operational roles and fail-closed block on joint overall champion."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    roles = payload["decoupled_model_champions"]

    # Role A: Point Prediction
    assert "arrival_linear_baseline_v1" in roles["point_prediction_role"]["champions"]
    assert "arrival_weighted_ensemble_v1" in roles["point_prediction_role"]["champions"]
    assert roles["point_prediction_role"]["status_2023_dev"] == "TIED_WITHIN_0.10_MIN_INDIFFERENCE_BAND"
    assert roles["point_prediction_role"]["status_2024_holdout"] == "NOT_TIED_DIFFERENCE_EXCEEDS_0.10_MIN"
    assert roles["point_prediction_role"]["overall_status"] == "NO_SINGLE_OVERALL_CHAMPION_ASSERTED"

    # Role B: Probabilistic Forecasting
    assert roles["probabilistic_forecasting_role"]["champion"] == "P5_quantile_regression"
    assert roles["probabilistic_forecasting_role"]["continuous_density"] == "NOT_AVAILABLE"

    # Role C: Downstream Simulation
    assert roles["downstream_simulation_role"]["candidate"] == "P4_ngboost_student_t"
    assert roles["downstream_simulation_role"]["capability"] == "PARAMETRIC_CONTINUOUS_DENSITY_ENABLED"

    # Joint overall champion
    assert roles["joint_overall_champion"] == "BLOCKED_FAIL_CLOSED"


def test_operational_downstream_summary() -> None:
    """Verify 84 evaluation runs, 0 failures, 0 violations, and 0 conflicts."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summary = payload["operational_evaluation_summary"]

    assert summary["evaluation_cases"] == 84
    assert summary["scenarios_evaluated"] == 4
    assert summary["solvers_evaluated"] == 3
    assert summary["total_unaccounted_failures"] == 0
    assert summary["hard_constraint_violations_observed"] == 0
    assert summary["realized_conflicts_observed"] == 0
    assert summary["semantics_enforced"] == "SCALAR_FORECAST_IMPACT"


def test_claim_boundary_matrix_and_bans() -> None:
    """Verify claim boundary matrix enforces all mandatory bans and status constraints."""
    assert CLAIM_AUDIT_PATH.is_file()
    audit = json.loads(CLAIM_AUDIT_PATH.read_text(encoding="utf-8"))
    claims = audit["claims"]
    assert len(claims) >= 12

    valid_statuses = {
        "CONFIRMED",
        "SUPPORTED_WITH_LIMITATION",
        "CORRECTED",
        "NOT_SUPPORTED",
        "BLOCKED",
        "HISTORICAL_ONLY",
    }

    claim_map = {c["claim_id"]: c for c in claims}

    # All claims must have valid status and non-empty allowed/prohibited wording
    for c in claims:
        assert c["certification_status"] in valid_statuses
        assert len(c["allowed_wording"].strip()) > 0
        assert len(c["prohibited_wording"].strip()) > 0

    # 1. Real-world gate claim ban
    c_real = claim_map["CLAIM_08_REAL_WORLD_GATE_OPERATIONS"]
    assert c_real["certification_status"] == "CORRECTED"
    assert "Real airfield deployment" in c_real["prohibited_wording"]

    # 2. Oracle equivalence claim ban
    c_oracle = claim_map["CLAIM_09_ORACLE_EQUIVALENCE"]
    assert c_oracle["certification_status"] == "CORRECTED"
    assert "Equivalent to Oracle" in c_oracle["prohibited_wording"]

    # 3. CRN 82.4% variance reduction ban
    c_crn = claim_map["CLAIM_06_CRN_VARIANCE_REDUCTION"]
    assert c_crn["certification_status"] == "NOT_SUPPORTED"

    # 4. MC N=500 optimality ban
    c_mc = claim_map["CLAIM_07_MC_N500_OPTIMALITY"]
    assert c_mc["certification_status"] == "NOT_SUPPORTED"

    # 5. 100% reproducibility ban
    c_repro = claim_map["CLAIM_13_REPRODUCIBILITY_STANDARDS"]
    assert c_repro["certification_status"] == "HISTORICAL_ONLY"


def test_markdown_report_exists_and_accurate() -> None:
    """Verify markdown certification document exists and reflects certified status."""
    assert DOC_PATH.is_file()
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "CERTIFIED_WITH_LIMITATIONS" in content
    assert "AEOLUS_V4_FORENSIC_CERTIFICATION_COUNCIL" in content
    assert "SCALAR_FORECAST_IMPACT" in content
    assert "NO claims of real-world airport operations" in content
