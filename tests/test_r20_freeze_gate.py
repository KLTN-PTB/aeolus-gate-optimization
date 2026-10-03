"""Test Suite for R20 Freeze Gate, Provenance, and Legacy Claim Reconciliation.

Protocol: Task R20 Freeze & Provenance Audit
Invariants:
- All 10 pre-rebuild gate checks pass
- All 17 components in freeze manifest are FROZEN
- 2024 is classified strictly as POST_HOLDOUT with zero tuning leakage
- All 9 legacy claims are reconciled against empirical evidence
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path("D:/Study/Code/Python/Aelous")


def test_r20_pre_rebuild_gate_passes():
    """Verify that r20_pre_rebuild_gate.json passes 10/10 checks and authorizes R21."""
    gate_file = REPO_ROOT / "artifacts/r20_pre_rebuild_gate.json"
    assert gate_file.exists(), f"Gate artifact missing: {gate_file}"

    with open(gate_file, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["gate"] == "R20_PRE_REBUILD"
    assert doc["status"] == "PASS"
    assert doc["rebuild_authorization"] == "AUTHORIZED"
    assert doc["total_checks"] == 10
    assert doc["passed_checks"] == 10
    assert doc["failed_checks"] == 0

    for chk in doc["checks"]:
        assert chk["status"] == "PASS", f"Check {chk['check']} failed!"


def test_r20_freeze_manifest_complete():
    """Verify that all 17 components in r20_freeze_manifest.json are verified FROZEN."""
    manifest_file = REPO_ROOT / "artifacts/r20_freeze_manifest.json"
    assert manifest_file.exists(), f"Freeze manifest missing: {manifest_file}"

    with open(manifest_file, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["freeze_status"] == "SYSTEM_FROZEN_V3"
    assert doc["total_components"] == 17
    assert doc["frozen_components"] == 17
    assert doc["blocked_components"] == 0

    expected_prefixes = [
        "1. data_split",
        "2. feature_definition",
        "3. target_definition",
        "4. cutoff_logic",
        "5. model_registry",
        "6. hyperparameter_configs",
        "7. preprocessing",
        "8. oof_generation",
        "9. model_selection_logic",
        "10. probabilistic_metric_definitions",
        "11. downstream_semantics",
        "12. optimizer_semantics",
        "13. statistical_runner",
        "14. monte_carlo_configuration",
        "15. seed_policy",
        "16. artifact_naming",
        "17. provenance_checks",
    ]

    components = doc["components"]
    comp_names = [c["component"] for c in components]

    for exp in expected_prefixes:
        assert exp in comp_names, f"Missing frozen component: {exp}"

    for c in components:
        assert c["status"] == "FROZEN", f"Component {c['component']} not FROZEN!"
        assert len(c["git_sha"]) == 40, f"Invalid git sha in {c['component']}"
        assert c["config_hash"] != "FILE_NOT_FOUND"


def test_r20_2024_provenance_audit():
    """Verify that 2024 holdout is classified strictly as POST_HOLDOUT with zero tuning leakage."""
    audit_file = REPO_ROOT / "artifacts/r20_2024_provenance_audit.json"
    assert audit_file.exists(), f"2024 audit missing: {audit_file}"

    with open(audit_file, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["status"] == "PASS"
    assert doc["classification"] == "POST_HOLDOUT"
    assert doc["dataset_2024_access"] is True
    assert doc["historical_access"] is True
    assert doc["development_use"] is False
    assert doc["tuning_use"] is False
    assert doc["final_eval_use"] is True
    assert len(doc["evidence"]) >= 5


def test_r20_claim_reconciliation():
    """Verify that all 9 legacy claims are reconciled."""
    recon_file = REPO_ROOT / "artifacts/r20_claim_reconciliation.json"
    assert recon_file.exists(), f"Claim reconciliation missing: {recon_file}"

    with open(recon_file, encoding="utf-8") as f:
        claims = json.load(f)

    expected_claims = {
        "SYSTEM_FROZEN",
        "FAIL_CLOSED_CERTIFIED",
        "POST_HOLDOUT_STABILIZED",
        "untouched 2024",
        "7 core models",
        "real-world gate optimization",
        "optimal N=500",
        "CRPS Pinball",
        "SA peer solver",
    }

    found_claims = {c["claim"] for c in claims}
    assert expected_claims.issubset(found_claims), f"Missing claims: {expected_claims - found_claims}"

    for c in claims:
        assert c["reconciled_status"] in {"OVERSTATED", "INVALID", "INVALID_AND_OVERSTATED", "VALID"}
        assert len(c["evidence"]) >= 1


def test_r20_data_provenance():
    """Verify that raw and processed data partitions are properly documented."""
    prov_file = REPO_ROOT / "artifacts/r20_data_provenance.json"
    assert prov_file.exists(), f"Data provenance missing: {prov_file}"

    with open(prov_file, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["status"] == "PASS"
    assert "partitions" in doc["processed_datasets"]
    parts = doc["processed_datasets"]["partitions"]

    for yr in range(2016, 2025):
        key = f"year={yr}"
        assert key in parts, f"Missing partition: {key}"
        assert parts[key]["file_count"] > 0
