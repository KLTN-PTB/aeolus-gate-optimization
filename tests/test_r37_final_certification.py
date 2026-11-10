"""Final Forensic Certification Verification Test Suite for AEOLUS V4 Task R37.

Task: R37 — FINAL CERTIFICATION V5

Verifies:
1. test_final_manifest_actual_sha: Actual byte SHA256 of final_evidence_certification_v5.json matches sidecar.
2. test_freeze_manifest_actual_sha: Actual byte SHA256 of final_freeze_manifest_v5.json matches sidecar & cert lineage.
3. test_claim_audit_actual_sha: Actual byte SHA256 of final_claim_boundary_audit_v5.json matches sidecar & cert lineage.
4. test_repro_audit_actual_sha: Actual byte SHA256 of final_reproducibility_audit_v5.json matches sidecar & cert lineage.
5. test_execution_summary_actual_sha: Actual byte SHA256 of final_execution_summary_v5.json matches sidecar & cert lineage.
6. test_exact_13_claims: Exact 13 claims matching approved taxonomy.
7. test_no_duplicate_claims: Zero duplicate claim IDs.
8. test_no_unclassified_claims: All 13 claims belong to approved status set.
9. test_all_prior_phases_pass: R25, R26, R27, R28, R29, R30, R31, R33, R34, R35, R36 all marked PASS.
10. test_r33_p4_lineage_certified: Authoritative P4 holdout metrics (CRPS=17.6532, NLL=4.6307) and dev metrics (18.484, 4.5805); calibration NOT_SEPARATELY_CERTIFIED.
11. test_r34_p5_configuration_certified: P5 9-quantile estimator [0.025..0.975]; 16.85 is CRPS_QUANTILE_APPROXIMATION; continuous density NOT_AVAILABLE.
12. test_r35_solver_semantics_certified: Equal wall-clock budget (2.0s) PROVEN; equal computational work NOT_PROVEN; CP-SAT OPTIMAL on 28/28; Hybrid Delta=0 on 28/28.
13. test_r35_r21_scope_separation: R26 (28 cases / 112 runs) separate from R21 downstream (84 runs); R26 does not certify R21.
14. test_r36_reconciliation_gate_passed: R36 reconciliation manifest matches hash in cert lineage.
15. test_temporal_governance_no_2024_adaptation: Zero 2024 retraining, tuning, selection, or threshold adaptation.
16. test_reproducibility_contained_specification: Certified level is CONTAINED_SPECIFICATION_REPRODUCIBILITY.
17. test_all_critical_artifacts_verified: All 42 critical artifacts in freeze manifest exist and match sidecars.
18. test_zero_p0_blockers: p0_blockers_count == 0, unverified_executions == 0, unclassified_claims == 0, hash_mismatches == 0.
19. test_final_action_certified_with_limitations: Final action and status is CERTIFIED_WITH_LIMITATIONS.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
from typing import Final

ROOT = Path(__file__).resolve().parents[1]

CERT_V5_PATH: Final = ROOT / "artifacts" / "audit" / "final_evidence_certification_v5.json"
CERT_V5_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_evidence_certification_v5.json.sha256"

FREEZE_V5_PATH: Final = ROOT / "artifacts" / "audit" / "final_freeze_manifest_v5.json"
FREEZE_V5_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_freeze_manifest_v5.json.sha256"

CLAIM_V5_PATH: Final = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v5.json"
CLAIM_V5_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v5.json.sha256"

REPRO_V5_PATH: Final = ROOT / "artifacts" / "audit" / "final_reproducibility_audit_v5.json"
REPRO_V5_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_reproducibility_audit_v5.json.sha256"

EXEC_V5_PATH: Final = ROOT / "artifacts" / "audit" / "final_execution_summary_v5.json"
EXEC_V5_SIDECAR: Final = ROOT / "artifacts" / "audit" / "final_execution_summary_v5.json.sha256"

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
    assert CERT_V5_PATH.is_file(), f"Missing {CERT_V5_PATH}"
    return json.loads(CERT_V5_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def freeze_data() -> dict:
    assert FREEZE_V5_PATH.is_file(), f"Missing {FREEZE_V5_PATH}"
    return json.loads(FREEZE_V5_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def claim_data() -> dict:
    assert CLAIM_V5_PATH.is_file(), f"Missing {CLAIM_V5_PATH}"
    return json.loads(CLAIM_V5_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def repro_data() -> dict:
    assert REPRO_V5_PATH.is_file(), f"Missing {REPRO_V5_PATH}"
    return json.loads(REPRO_V5_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def exec_data() -> dict:
    assert EXEC_V5_PATH.is_file(), f"Missing {EXEC_V5_PATH}"
    return json.loads(EXEC_V5_PATH.read_text(encoding="utf-8"))


def test_final_manifest_actual_sha():
    """1. Verify actual byte SHA256 of final_evidence_certification_v5.json matches sidecar."""
    actual_sha = compute_sha256(CERT_V5_PATH)
    sidecar_sha = CERT_V5_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha, f"Cert manifest mismatch: {actual_sha} != {sidecar_sha}"


def test_freeze_manifest_actual_sha(cert_data):
    """2. Verify actual byte SHA256 of final_freeze_manifest_v5.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(FREEZE_V5_PATH)
    sidecar_sha = FREEZE_V5_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha
    assert actual_sha == cert_data["cryptographic_lineage"]["final_freeze_manifest_v5_sha256"]


def test_claim_audit_actual_sha(cert_data):
    """3. Verify actual byte SHA256 of final_claim_boundary_audit_v5.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(CLAIM_V5_PATH)
    sidecar_sha = CLAIM_V5_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha
    assert actual_sha == cert_data["cryptographic_lineage"]["final_claim_boundary_audit_v5_sha256"]


def test_repro_audit_actual_sha(cert_data):
    """4. Verify actual byte SHA256 of final_reproducibility_audit_v5.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(REPRO_V5_PATH)
    sidecar_sha = REPRO_V5_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha
    assert actual_sha == cert_data["cryptographic_lineage"]["final_reproducibility_audit_v5_sha256"]


def test_execution_summary_actual_sha(cert_data):
    """5. Verify actual byte SHA256 of final_execution_summary_v5.json matches sidecar & cert lineage."""
    actual_sha = compute_sha256(EXEC_V5_PATH)
    sidecar_sha = EXEC_V5_SIDECAR.read_text(encoding="utf-8").strip().split()[0]
    assert actual_sha == sidecar_sha
    assert actual_sha == cert_data["cryptographic_lineage"]["final_execution_summary_v5_sha256"]


def test_exact_13_claims(claim_data):
    """6. Verify exact 13 claims exist matching approved taxonomy."""
    claims = claim_data["claims"]
    assert len(claims) == 13
    actual_ids = tuple(c["claim_id"] for c in claims)
    assert actual_ids == EXPECTED_13_CLAIM_IDS


def test_no_duplicate_claims(claim_data):
    """7. Verify zero duplicate claim IDs exist."""
    claims = claim_data["claims"]
    claim_ids = [c["claim_id"] for c in claims]
    assert len(claim_ids) == len(set(claim_ids))
    assert claim_data["zero_duplicate_claims"] is True


def test_no_unclassified_claims(claim_data):
    """8. Verify all 13 claims belong to approved status set."""
    assert claim_data["zero_unclassified_claims"] is True
    for c in claim_data["claims"]:
        assert c["status"] in VALID_STATUSES


def test_all_prior_phases_pass(cert_data):
    """9. Verify R25 through R36 all recorded PASS."""
    expected_phases = ["R25", "R26", "R27", "R28", "R29", "R30", "R31", "R33", "R34", "R35", "R36"]
    for ph in expected_phases:
        assert cert_data["phase_statuses"][ph] == "PASS", f"Phase {ph} is not PASS"


def test_r33_p4_lineage_certified(cert_data):
    """10. Verify P4 authoritative metrics (CRPS=17.6532, NLL=4.6307) and calibration status."""
    p4 = cert_data["epistemological_guardrails"]["probabilistic_capabilities"]["P4_student_t"]
    assert p4["authoritative_crps_holdout"] == 17.6532
    assert p4["authoritative_nll_holdout"] == 4.6307
    assert p4["calibration_status"] == "NOT_SEPARATELY_CERTIFIED"
    assert p4["density_type"] == "parametric_continuous"
    assert p4["continuous_sampling"] is True


def test_r34_p5_configuration_certified(cert_data):
    """11. Verify P5 is 9-quantile estimator [0.025..0.975] and metric is CRPS quantile approx."""
    p5 = cert_data["epistemological_guardrails"]["probabilistic_capabilities"]["P5_quantile"]
    assert p5["quantile_count"] == 9
    assert p5["quantile_levels"] == [0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]
    assert p5["crps_quantile_approximation_dev"] == 16.85
    assert p5["pinball_loss_dev"] == 6.88
    assert p5["continuous_density"] is False
    assert p5["exact_continuous_nll"] is False


def test_r35_solver_semantics_certified(cert_data):
    """12. Verify wall-clock equality PROVEN; computational work NOT_PROVEN; CP-SAT OPTIMAL; Hybrid Delta=0."""
    sf = cert_data["epistemological_guardrails"]["solver_fairness"]
    assert sf["wall_clock_equality"] == "PROVEN"
    assert sf["computational_work_equality"] == "NOT_PROVEN"
    assert sf["cp_sat_optimality"] == "PROVEN_ON_ALL_28_AUDITED_CASES"
    assert sf["hybrid_zero_marginal_gain"] == "PROVEN_ON_ALL_28_AUDITED_CASES"


def test_r35_r21_scope_separation(cert_data):
    """13. Verify R26 (28 cases/112 runs) separate from R21 downstream (84 runs)."""
    sf = cert_data["epistemological_guardrails"]["solver_fairness"]
    assert sf["r26_scope"] == "28_CASES_112_RUNS_2024_SEASONAL"
    assert sf["r21_scope"] == "28_CASES_84_RUNS_2023_DEV"


def test_r36_reconciliation_gate_passed(cert_data):
    """14. Verify R36 reconciliation manifest matches recorded SHA in cert lineage."""
    r36_path = ROOT / "artifacts" / "audit" / "r36_final_evidence_reconciliation_v2.json"
    actual_sha = compute_sha256(r36_path)
    recorded_sha = cert_data["cryptographic_lineage"]["r36_final_evidence_reconciliation_v2_sha256"]
    assert actual_sha == recorded_sha


def test_temporal_governance_no_2024_adaptation(cert_data):
    """15. Verify zero 2024 training, tuning, selection, or threshold adaptation."""
    tg = cert_data["temporal_governance"]
    assert tg["development_period"] == "2016-2022"
    assert tg["model_selection_year"] == 2023
    assert tg["post_holdout_year"] == 2024
    assert tg["zero_2024_retraining_verified"] is True
    assert tg["zero_2024_tuning_verified"] is True
    assert tg["zero_2024_selection_verified"] is True
    assert cert_data["metrics_accounting"]["adaptation_2024_detected"] is False


def test_reproducibility_contained_specification(repro_data, cert_data):
    """16. Verify reproducibility is CONTAINED_SPECIFICATION_REPRODUCIBILITY and unproven claims banned."""
    assert repro_data["certification_level"] == "CERTIFIED_WITH_LIMITATIONS"
    assert repro_data["reproducibility_verdict"] == "REPRODUCIBILITY_VERIFIED_UNDER_CONTAINED_SPECIFICATION"
    prohibited = repro_data["prohibited_claims"]
    assert "100% reproducible" in prohibited
    assert "universally bit-for-bit reproducible" in prohibited


def test_all_critical_artifacts_verified(freeze_data):
    """17. Verify all 42 critical artifacts exist on disk and match actual bytes."""
    artifacts = freeze_data["artifacts"]
    assert len(artifacts) >= 42
    assert freeze_data["zero_missing_artifacts"] is True
    assert freeze_data["zero_hash_mismatches"] is True
    for a in artifacts:
        p = ROOT / a["path"]
        assert p.is_file(), f"Missing critical artifact: {p}"
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha == a["sha256_actual"], f"SHA mismatch on {a['path']}"


def test_zero_p0_blockers(cert_data):
    """18. Verify 0 P0 blockers, 0 hash mismatches, 0 unclassified claims."""
    ma = cert_data["metrics_accounting"]
    assert ma["p0_blockers_count"] == 0
    assert ma["hash_mismatches_count"] == 0
    assert ma["unclassified_claims_count"] == 0
    assert ma["unverified_executions_count"] == 0
    assert ma["unsupported_claims_remaining"] == 0


def test_final_action_certified_with_limitations(cert_data):
    """19. Verify final action and certification status is CERTIFIED_WITH_LIMITATIONS."""
    assert cert_data["certification_status"] == "CERTIFIED_WITH_LIMITATIONS"
    assert cert_data["final_action"] == "CERTIFIED_WITH_LIMITATIONS"
