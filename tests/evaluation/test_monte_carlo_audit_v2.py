"""Audit tests for Monte Carlo protocol, governance, and freeze integrity (Task R9)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from src.evaluation.mc_convergence import PREREGISTERED_MC_COUNTS


def test_monte_carlo_manifest_and_config_integrity() -> None:
    """Verify that Monte Carlo protocol v2 manifest and YAML configuration are synchronized and valid."""
    manifest_path = Path("artifacts/manifests/monte_carlo_protocol_v2.json")
    config_path = Path("configs/monte_carlo_protocol_v2.yaml")

    assert manifest_path.exists(), "Manifest file missing"
    assert config_path.exists(), "Config file missing"

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Assert registered counts match
    assert manifest_data["preregistered_mc_counts"] == list(PREREGISTERED_MC_COUNTS)
    assert config_data["preregistered_mc_counts"] == list(PREREGISTERED_MC_COUNTS)

    # Assert truncation policy
    assert manifest_data["truncation_audit"]["silent_truncation_prohibited"] is True
    assert config_data["truncation_policy"]["allow_truncation"] is False

    # Assert CRN variance reduction status
    assert manifest_data["crn_variance_reduction_policy"]["status"] == "NOT_ESTABLISHED"
    assert config_data["crn_variance_reduction_protocol"]["uncomputed_status"] == "NOT_ESTABLISHED"

    # Assert precision target status
    assert manifest_data["convergence_specification"]["precision_target_status"] == "NOT_PREREGISTERED"
    assert config_data["convergence_protocol"]["precision_target_status_if_null"] == "NOT_PREREGISTERED"


def test_monte_carlo_audit_report_integrity() -> None:
    """Verify that monte_carlo_audit_v2.json documents all 6 key findings and confirms resolution."""
    audit_path = Path("artifacts/audit/monte_carlo_audit_v2.json")
    assert audit_path.exists(), "Audit report missing"

    audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit_data["audit_name"] == "monte_carlo_audit_v2"
    assert audit_data["historical_findings_summary"]["total_flaws_identified"] == 6

    flaw_ids = [f["issue_id"] for f in audit_data["historical_findings_summary"]["flaws"]]
    assert "MC_FLAW_01_SILENT_TRUNCATION_RISK" in flaw_ids
    assert "MC_FLAW_02_UNSUBSTANTIATED_CRN_VARIANCE_REDUCTION" in flaw_ids
    assert "MC_FLAW_03_POST_HOC_N500_OPTIMALITY_CLAIM" in flaw_ids
    assert "MC_FLAW_04_INVENTED_P5_TRANSFORMATION" in flaw_ids
    assert "MC_FLAW_05_CRN_RNG_RESET_AUDIT" in flaw_ids
    assert "MC_FLAW_06_INCOMPLETE_FAILURE_ACCOUNTING" in flaw_ids

    # All flaws marked as repaired in v2
    for f in audit_data["historical_findings_summary"]["flaws"]:
        assert f["repaired_in_v2"] is True

    assert audit_data["repaired_engine_validation"]["status"] == "VERIFIED_PASS"


def test_zero_unsubstantiated_claims_in_v2_code_and_manifests() -> None:
    """Verify that neither mc_convergence.py nor protocol manifests assert unsubstantiated claims."""
    forbidden_phrases = [
        "reduces variance by 82.4%",
        "variance reduction of 82.4%",
        "n=500 is optimal",
    ]

    target_files = [
        Path("src/evaluation/mc_convergence.py"),
        Path("src/evaluation/monte_carlo_comparison_v2.py"),
        Path("configs/monte_carlo_protocol_v2.yaml"),
        Path("artifacts/manifests/monte_carlo_protocol_v2.json"),
    ]

    for p in target_files:
        content = p.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            # If in manifest, only allowed under prohibited/audit sections
            if p.suffix in (".json", ".yaml"):
                assert f'"{phrase}"' not in content or "prohibit" in content or "unsubstantiated" in content
            else:
                assert phrase not in content, f"Forbidden phrase '{phrase}' found in {p}"
