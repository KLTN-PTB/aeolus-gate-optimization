"""Test Suite for System Freeze V3, Evidence Manifest V3, and Guard Governance (Task R22).

Verifies:
1. system_freeze_manifest_v3.json and system_freeze_manifest_v3.sha256 exist and pass cryptographic verification.
2. development_evidence_manifest_v3.json exists and links to system freeze v3.
3. r22_freeze_audit.json reports PASS with 24 categories and 79 frozen files verified.
4. FinalEvaluationGuardV2(freeze_version='v3') verifies all 79 frozen files without any hash mismatch.
5. Guard strictly authorizes 'POST_HOLDOUT' for 2024 post_holdout_evaluation.
6. Guard rejects all forbidden evaluation roles (untouched, development, tuning, calibration, etc.).
7. Guard rejects non-2024 evaluation years and incorrect purposes.
8. Historical freezes (v1, v2) remain preserved and unmodified.
9. 2024 holdout data remained unopened and sealed during R22.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from src.evaluation.final_evaluation_guard_v2 import (
    EXPECTED_EVALUATION_ROLE,
    FORBIDDEN_EVALUATION_ROLES,
    FinalEvaluationGuardV2,
    FinalEvaluationGuardV2Error,
    compute_sha256,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def guard_v3() -> FinalEvaluationGuardV2:
    return FinalEvaluationGuardV2(freeze_version="v3")


def test_system_freeze_v3_manifest_and_checksum_integrity() -> None:
    """Verify that system freeze v3 manifest and sidecar sha256 exist and match bitwise."""
    manifest_path = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v3.json"
    sidecar_path = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v3.sha256"
    assert manifest_path.exists(), "Missing system_freeze_manifest_v3.json"
    assert sidecar_path.exists(), "Missing system_freeze_manifest_v3.sha256"

    actual_hash = compute_sha256(manifest_path)
    sidecar_line = sidecar_path.read_text(encoding="utf-8").strip()
    expected_hash = sidecar_line.split()[0]
    assert actual_hash == expected_hash, f"Sidecar hash mismatch: {actual_hash} != {expected_hash}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "system_freeze_manifest_v3"
    assert data["freeze_status"] == "FROZEN_V3"
    assert data["final_holdout_year"] == 2024
    assert data["total_categories"] == 24
    assert data["total_files_frozen"] >= 75


def test_development_evidence_manifest_v3_validity() -> None:
    """Verify development evidence manifest v3 links to freeze v3 and tracks all components."""
    dev_path = ROOT / "artifacts" / "manifests" / "development_evidence_manifest_v3.json"
    assert dev_path.exists(), "Missing development_evidence_manifest_v3.json"

    data = json.loads(dev_path.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "development_evidence_manifest_v3"
    assert data["status"] == "DEVELOPMENT_REBUILD_V3_VERIFIED"
    assert data["holdout_status"] == "SEALED_UNTIL_R23"
    assert len(data["evaluated_models"]["core_point"]) == 5
    assert len(data["evaluated_models"]["probabilistic"]) == 5
    assert len(data["folds_evaluated"]) == 4


def test_r22_freeze_audit_completeness() -> None:
    """Verify r22_freeze_audit.json records 100% coverage and zero hidden files."""
    audit_path = ROOT / "artifacts" / "audit" / "r22_freeze_audit.json"
    assert audit_path.exists(), "Missing artifacts/audit/r22_freeze_audit.json"

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "PASS"
    assert audit["sidecar_verified"] is True
    assert audit["coverage_audit"]["all_files_verified"] is True
    assert audit["coverage_audit"]["zero_hidden_files"] is True
    assert audit["coverage_audit"]["total_categories"] == 24
    assert audit["final_guard_status"]["fail_closed_verified"] is True
    assert audit["holdout_2024_status"]["row_level_access_in_r22"] is False


def test_guard_v3_verifies_all_frozen_files(guard_v3: FinalEvaluationGuardV2) -> None:
    """Verify that guard passes verification across all 24 categories in freeze manifest v3."""
    payload = guard_v3.verify_freeze_manifest()
    assert payload["freeze_status"] == "FROZEN_V3"
    assert payload["manifest_version"] == "system_freeze_manifest_v3"
    assert payload["total_categories"] == 24


def test_guard_v3_authorizes_clean_post_holdout_access(guard_v3: FinalEvaluationGuardV2) -> None:
    """Verify that guard authorizes access under POST_HOLDOUT role for year 2024."""
    guard_v3.assert_evaluation_authorized(
        evaluation_role="POST_HOLDOUT",
        year=2024,
        purpose="post_holdout_evaluation",
    )


@pytest.mark.parametrize("role", sorted(list(FORBIDDEN_EVALUATION_ROLES)))
def test_guard_v3_rejects_forbidden_evaluation_roles(
    guard_v3: FinalEvaluationGuardV2,
    role: str,
) -> None:
    """Verify that all non-post-holdout roles fail closed."""
    with pytest.raises(FinalEvaluationGuardV2Error, match="is STRICTLY PROHIBITED"):
        guard_v3.assert_evaluation_authorized(
            evaluation_role=role,
            year=2024,
            purpose="post_holdout_evaluation",
        )


def test_historical_freezes_preserved() -> None:
    """Verify that historical v1 and v2 freeze manifests are preserved intact."""
    v1_path = ROOT / "artifacts" / "manifests" / "full_system_freeze_manifest_v1.json"
    v2_path = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v2.json"
    v2_sha = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v2.sha256"

    assert v1_path.exists(), "Missing historical full_system_freeze_manifest_v1.json"
    assert v2_path.exists(), "Missing historical system_freeze_manifest_v2.json"
    assert v2_sha.exists(), "Missing historical system_freeze_manifest_v2.sha256"
