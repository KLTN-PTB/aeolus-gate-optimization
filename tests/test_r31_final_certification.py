"""Test Suite for AEOLUS V4 Task R31: Final Forensic Certification.

Verifies:
1. test_final_manifest_actual_sha
2. test_freeze_manifest_actual_sha
3. test_claim_audit_actual_sha
4. test_repro_audit_actual_sha
5. test_exact_13_claims
6. test_no_duplicate_claims
7. test_no_unclassified_claims
8. test_r25_pass
9. test_r26_pass
10. test_r27_pass
11. test_r28_pass
12. test_r29_pass
13. test_r30_pass
14. test_temporal_governance
15. test_no_2024_adaptation
16. test_p4_p5_separation
17. test_downstream_scalar_semantics
18. test_synthetic_environment_boundary
19. test_oracle_boundary
20. test_mc_claim_boundary
21. test_reproducibility_boundary
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
from typing import Final

ROOT = Path(__file__).resolve().parents[1]

CERT_PATH: Final = ROOT / "artifacts" / "audit" / "final_evidence_certification_v4.json"
CERT_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_evidence_certification_v4.json.sha256"

FREEZE_PATH: Final = ROOT / "artifacts" / "audit" / "final_freeze_manifest_v4.json"
FREEZE_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_freeze_manifest_v4.json.sha256"

CLAIM_AUDIT_PATH: Final = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v4.json"
CLAIM_AUDIT_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v4.json.sha256"

REPRO_PATH: Final = ROOT / "artifacts" / "audit" / "final_reproducibility_audit_v4.json"
REPRO_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_reproducibility_audit_v4.json.sha256"

DOC_PATH: Final = ROOT / "docs" / "audit" / "FINAL_EVIDENCE_CERTIFICATION_V4.md"
DOC_SIDECAR: Final = ROOT / "docs" / "audit" / "FINAL_EVIDENCE_CERTIFICATION_V4.md.sha256"

EXPECTED_13_CLAIM_IDS: Final[tuple[str, ...]] = (
    "CLAIM_01_TEMPORAL_POST_HOLDOUT",
    "CLAIM_02_POINT_CHAMPION_SELECTION",
    "CLAIM_03_PROBABILISTIC_P5_CRPS",
    "CLAIM_04_PROBABILISTIC_P4_STUDENT_T",
    "CLAIM_05_SINGLE_OVERALL_CHAMPION",
    "CLAIM_06_CRN_VARIANCE_REDUCTION",
    "CLAIM_07_MC_N500_OPTIMALITY",
    "CLAIM_08_REAL_WORLD_GATE_OPERATIONS",
    "CLAIM_09_ORACLE_EQUIVALENCE",
    "CLAIM_10_DOWNSTREAM_SEMANTICS",
    "CLAIM_11_STATISTICAL_SIGNIFICANCE",
    "CLAIM_12_AUXILIARY_DEPARTURE_DELAY",
    "CLAIM_13_REPRODUCIBILITY_STANDARDS",
)

VALID_STATUSES: Final[set[str]] = {
    "CORRECTED",
    "SUPPORTED_WITH_LIMITATION",
    "BLOCKED",
    "NOT_SUPPORTED",
    "HISTORICAL_ONLY",
}


def compute_sha256(path: Path) -> str:
    """Read actual raw bytes and compute hexadecimal SHA-256."""
    assert path.is_file(), f"File does not exist: {path}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def cert_data() -> dict:
    assert CERT_PATH.is_file(), f"Missing final certification manifest: {CERT_PATH}"
    return json.loads(CERT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def freeze_data() -> dict:
    assert FREEZE_PATH.is_file(), f"Missing final freeze manifest: {FREEZE_PATH}"
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def claim_data() -> dict:
    assert CLAIM_AUDIT_PATH.is_file(), f"Missing claim boundary audit: {CLAIM_AUDIT_PATH}"
    return json.loads(CLAIM_AUDIT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def repro_data() -> dict:
    assert REPRO_PATH.is_file(), f"Missing reproducibility audit: {REPRO_PATH}"
    return json.loads(REPRO_PATH.read_text(encoding="utf-8"))


# =============================================================================
# MANDATORY 21 TESTS FOR R31
# =============================================================================

def test_final_manifest_actual_sha():
    """1. Verify actual byte SHA256 of final_evidence_certification_v4.json matches sidecar."""
    actual_sha = compute_sha256(CERT_PATH)
    sidecar_sha = CERT_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha, f"Final cert manifest hash mismatch: {actual_sha} != {sidecar_sha}"


def test_freeze_manifest_actual_sha(cert_data):
    """2. Verify actual byte SHA256 of final_freeze_manifest_v4.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(FREEZE_PATH)
    sidecar_sha = FREEZE_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha, f"Freeze manifest hash mismatch: {actual_sha} != {sidecar_sha}"
    recorded_sha = cert_data["cryptographic_lineage"]["final_freeze_manifest_v4_sha256"]
    assert actual_sha == recorded_sha, f"Recorded freeze hash mismatch: {actual_sha} != {recorded_sha}"


def test_claim_audit_actual_sha(cert_data):
    """3. Verify actual byte SHA256 of final_claim_boundary_audit_v4.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(CLAIM_AUDIT_PATH)
    sidecar_sha = CLAIM_AUDIT_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha, f"Claim audit hash mismatch: {actual_sha} != {sidecar_sha}"
    recorded_sha = cert_data["cryptographic_lineage"]["final_claim_boundary_audit_v4_sha256"]
    assert actual_sha == recorded_sha, f"Recorded claim audit hash mismatch: {actual_sha} != {recorded_sha}"


def test_repro_audit_actual_sha(cert_data):
    """4. Verify actual byte SHA256 of final_reproducibility_audit_v4.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(REPRO_PATH)
    sidecar_sha = REPRO_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha, f"Repro audit hash mismatch: {actual_sha} != {sidecar_sha}"
    recorded_sha = cert_data["cryptographic_lineage"]["final_reproducibility_audit_v4_sha256"]
    assert actual_sha == recorded_sha, f"Recorded repro audit hash mismatch: {actual_sha} != {recorded_sha}"


def test_exact_13_claims(claim_data):
    """5. Verify exact 13 claims exist matching the approved claim taxonomy."""
    claims = claim_data["claims"]
    assert len(claims) == 13
    actual_ids = tuple(c["claim_id"] for c in claims)
    assert actual_ids == EXPECTED_13_CLAIM_IDS


def test_no_duplicate_claims(claim_data):
    """6. Verify zero duplicate claim IDs exist."""
    claims = claim_data["claims"]
    claim_ids = [c["claim_id"] for c in claims]
    assert len(claim_ids) == len(set(claim_ids))
    assert claim_data.get("zero_duplicate_claims") is True


def test_no_unclassified_claims(claim_data):
    """7. Verify zero unclassified claims; all statuses belong to approved taxonomy."""
    assert claim_data.get("zero_unclassified_claims") is True
    for c in claim_data["claims"]:
        assert c["status"] in VALID_STATUSES, f"Invalid status {c['status']} for claim {c['claim_id']}"


def test_r25_pass(cert_data):
    """8. Verify Phase R25 passed with point selection consistency reconciled."""
    assert cert_data["phase_statuses"]["R25"] == "PASS"
    r25_path = ROOT / "artifacts" / "audit" / "r25_point_selection_consistency.json"
    assert r25_path.is_file()
    r25_data = json.loads(r25_path.read_text(encoding="utf-8"))
    assert r25_data.get("task_id") == "R25_POINT_SELECTION_CONSISTENCY"
    num_audit = r25_data.get("numerical_audit", {})
    assert num_audit["year_2023_selection_slice"]["is_tied_under_band"] is True
    assert num_audit["year_2024_post_holdout"]["is_tied_under_band"] is False


def test_r26_pass(cert_data):
    """9. Verify Phase R26 passed with equal-total-compute contract (T=2.0s across 112 runs)."""
    assert cert_data["phase_statuses"]["R26"] == "PASS"
    r26_contract_path = ROOT / "artifacts" / "audit" / "r26_solver_compute_contract.json"
    assert r26_contract_path.is_file()
    contract = json.loads(r26_contract_path.read_text(encoding="utf-8"))
    assert contract.get("total_wall_clock_budget_seconds") == 2.0
    assert contract.get("verdict") == "CERTIFIED_EQUAL_TOTAL_COMPUTE_CONTRACT"


def test_r27_pass(cert_data):
    """10. Verify Phase R27 passed with byte-level SHA256 test hardening."""
    assert cert_data["phase_statuses"]["R27"] == "PASS"
    r27_path = ROOT / "artifacts" / "audit" / "r27_certification_test_hardening.json"
    assert r27_path.is_file()
    r27_data = json.loads(r27_path.read_text(encoding="utf-8"))
    assert r27_data.get("audit_verdict") == "PASS"


def test_r28_pass(cert_data):
    """11. Verify Phase R28 passed with P4 continuous density & P5 discrete quantiles certified."""
    assert cert_data["phase_statuses"]["R28"] == "PASS"
    r28_path = ROOT / "artifacts" / "audit" / "r28_probabilistic_capability_matrix.json"
    assert r28_path.is_file()
    r28_data = json.loads(r28_path.read_text(encoding="utf-8"))
    assert r28_data.get("task_id") == "R28_PROBABILISTIC_METRIC_CALIBRATION_DEPENDENCY_AUDIT"
    assert r28_data.get("total_models") == 5


def test_r29_pass(cert_data):
    """12. Verify Phase R29 passed with full execution provenance (224 runs mapped, 0 unclassified)."""
    assert cert_data["phase_statuses"]["R29"] == "PASS"
    r29_path = ROOT / "artifacts" / "audit" / "r29_execution_provenance_reconciliation.json"
    assert r29_path.is_file()
    r29_data = json.loads(r29_path.read_text(encoding="utf-8"))
    assert r29_data.get("status") == "PASS"
    assert r29_data["summary"]["total_evidence_runs"] == 224
    assert r29_data["summary"]["unclassified_runs_count"] == 0


def test_r30_pass(cert_data):
    """13. Verify Phase R30 passed with 18-domain final status matrix and 0 unresolved P0 blockers."""
    assert cert_data["phase_statuses"]["R30"] == "PASS"
    r30_path = ROOT / "artifacts" / "audit" / "r30_final_evidence_reconciliation.json"
    assert r30_path.is_file()
    r30_data = json.loads(r30_path.read_text(encoding="utf-8"))
    assert r30_data.get("status") == "PASS"
    assert r30_data["summary"]["total_domains_audited"] == 18
    assert r30_data["summary"]["unresolved_p0_contradictions"] == 0


def test_temporal_governance(cert_data):
    """14. Verify temporal governance: dev 2016-2022, selection 2023, holdout 2024."""
    tg = cert_data["temporal_governance"]
    assert tg["development_period"] == "2016-2022"
    assert tg["model_selection_year"] == 2023
    assert tg["post_holdout_year"] == 2024
    assert tg["post_holdout_role"] == "POST_HOLDOUT"
    assert 2024 not in tg["outer_development_years"]


def test_no_2024_adaptation(cert_data):
    """15. Verify zero training, tuning, selection, or threshold adaptation on 2024."""
    tg = cert_data["temporal_governance"]
    assert tg["zero_2024_retraining_verified"] is True
    assert tg["zero_2024_tuning_verified"] is True
    assert tg["zero_2024_selection_verified"] is True
    assert tg["zero_2024_solver_tuning_verified"] is True
    assert tg["zero_2024_threshold_adaptation_verified"] is True
    assert tg["zero_2024_ensemble_weight_adaptation_verified"] is True
    assert cert_data["metrics_accounting"]["adaptation_2024_detected"] is False


def test_p4_p5_separation(cert_data, claim_data):
    """16. Verify P4 continuous density (not certified calibrated) vs P5 discrete quantiles."""
    c3 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_03_PROBABILISTIC_P5_CRPS"][0]
    assert "continuous density is not available" in c3["exact_current_wording"]
    assert "P5 provides a full continuous predictive density" in c3["prohibited_scope"]

    c4 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_04_PROBABILISTIC_P4_STUDENT_T"][0]
    assert "empirical calibration is not separately certified" in c4["exact_current_wording"]
    assert "P4 is an empirically certified calibrated distribution" in c4["prohibited_scope"]

    prob_guard = cert_data["epistemological_guardrails"]["probabilistic_capabilities"]
    assert prob_guard["P4_student_t"]["calibration_status"] == "NOT_SEPARATELY_CERTIFIED"
    assert prob_guard["P5_quantile"]["continuous_density"] is False


def test_downstream_scalar_semantics(cert_data, claim_data):
    """17. Verify downstream pipeline strictly honors SCALAR_FORECAST_IMPACT."""
    c10 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_10_DOWNSTREAM_SEMANTICS"][0]
    assert "SCALAR_FORECAST_IMPACT" in c10["exact_current_wording"]
    assert "Full uncertainty-aware downstream optimization" in c10["prohibited_scope"]
    assert cert_data["epistemological_guardrails"]["downstream_semantics"] == "SCALAR_FORECAST_IMPACT"


def test_synthetic_environment_boundary(claim_data):
    """18. Verify gate optimization is bounded to synthetic scenarios without real airfield claims."""
    c8 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_08_REAL_WORLD_GATE_OPERATIONS"][0]
    assert "simulated synthetic research environment" in c8["exact_current_wording"]
    assert "Real airfield deployment at ATL" in c8["prohibited_scope"]
    assert "Operational savings for Delta Air Lines" in c8["prohibited_scope"]


def test_oracle_boundary(claim_data):
    """19. Verify Oracle is non-deployable analytical reference; no predictive equivalence."""
    c9 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_09_ORACLE_EQUIVALENCE"][0]
    assert "Oracle remains an acausal, non-deployable theoretical reference" in c9["exact_current_wording"]
    assert "Equivalent to Oracle" in c9["prohibited_scope"]
    assert "Predictive equivalence to Oracle" in c9["prohibited_scope"]


def test_mc_claim_boundary(cert_data, claim_data):
    """20. Verify CRN marked NOT_ESTABLISHED and N=500 marked OPERATIONAL_CHOICE_ONLY."""
    c6 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_06_CRN_VARIANCE_REDUCTION"][0]
    assert c6["status"] == "NOT_SUPPORTED"
    assert "NOT_ESTABLISHED" in c6["exact_current_wording"]

    c7 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_07_MC_N500_OPTIMALITY"][0]
    assert c7["status"] == "NOT_SUPPORTED"
    assert "operational choice, not an optimal sample size" in c7["exact_current_wording"]

    mc_guard = cert_data["epistemological_guardrails"]
    assert mc_guard["monte_carlo_crn"] == "NOT_ESTABLISHED"
    assert mc_guard["monte_carlo_optimal_n"] == "OPERATIONAL_CHOICE_ONLY"


def test_reproducibility_boundary(cert_data, repro_data):
    """21. Verify final certification verdict is CERTIFIED_WITH_LIMITATIONS under contained spec."""
    assert cert_data["certification_status"] == "CERTIFIED_WITH_LIMITATIONS"
    assert repro_data["certification_level"] == "CERTIFIED_WITH_LIMITATIONS"
    assert repro_data["reproducibility_verdict"] == "REPRODUCIBILITY_VERIFIED_UNDER_CONTAINED_SPECIFICATION"
    prohibited = repro_data["prohibited_claims"]
    assert "100% reproducible" in prohibited
    assert "perfect reproducibility" in prohibited
    assert "top-tier" in prohibited
