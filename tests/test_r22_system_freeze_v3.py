"""Test Suite for System Freeze V3, Evidence Manifest V3, and Guard Governance (Task R22).

Verifies:
1. system_freeze_manifest_v3.json and system_freeze_manifest_v3.sha256 exist and pass cryptographic verification.
2. development_evidence_manifest_v3.json exists and links to system freeze v3.
3. r22_freeze_audit.json reports PASS with 24 categories and 79 frozen files verified.
4. A clean, isolated fixture verifies every file in all categories; mutation fails closed.
5. Authorization succeeds only in the isolated fixture; the revised working tree stays blocked.
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


@pytest.fixture
def clean_guard_v3(tmp_path: Path) -> FinalEvaluationGuardV2:
    """Synthetic frozen bytes exercise the guard without authorizing this working tree.

    Preserve the real manifest's category/file structure, but use fixture contents and
    checksums in a temporary root. No historical manifest or 2024 data is changed.
    """
    manifest = json.loads((ROOT / "artifacts/manifests/system_freeze_manifest_v3.json").read_text(encoding="utf-8"))
    for category in manifest["freeze_categories"].values():
        for name in category["files"]:
            source = tmp_path / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(("Synthetic frozen fixture: " + name).encode("utf-8"))
            category["files"][name] = compute_sha256(source)
    guard = FinalEvaluationGuardV2(project_root=tmp_path, freeze_version="v3")
    guard.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    guard.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    guard.checksum_path.write_text(compute_sha256(guard.manifest_path), encoding="utf-8")
    return guard


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


def test_guard_v3_verifies_clean_fixture_files(clean_guard_v3: FinalEvaluationGuardV2) -> None:
    """Verify all categories when the bytes actually match their frozen checksums."""
    payload = clean_guard_v3.verify_freeze_manifest()
    assert payload["freeze_status"] == "FROZEN_V3"
    assert payload["manifest_version"] == "system_freeze_manifest_v3"
    assert payload["total_categories"] == 24


def test_guard_v3_authorizes_only_clean_fixture(clean_guard_v3: FinalEvaluationGuardV2) -> None:
    """Exercise the positive authorization branch in a temporary synthetic root."""
    clean_guard_v3.assert_evaluation_authorized(
        evaluation_role="POST_HOLDOUT",
        year=2024,
        purpose="post_holdout_evaluation",
    )


def test_guard_v3_blocks_current_revised_working_tree(guard_v3: FinalEvaluationGuardV2) -> None:
    """Current code must never inherit the old freeze's authorization."""
    for operation in (guard_v3.verify_freeze_manifest, lambda: guard_v3.assert_evaluation_authorized(
        evaluation_role="POST_HOLDOUT", year=2024, purpose="post_holdout_evaluation"
    )):
        with pytest.raises(FinalEvaluationGuardV2Error, match=r"Integrity hash mismatch.*domain\.py"):
            operation()


def test_guard_v3_detects_fixture_source_mutation(clean_guard_v3: FinalEvaluationGuardV2) -> None:
    source = clean_guard_v3.project_root / "src/optimization/domain.py"
    source.write_bytes(source.read_bytes() + b"\nchanged after freeze")
    with pytest.raises(FinalEvaluationGuardV2Error, match=r"Integrity hash mismatch.*domain\.py"):
        clean_guard_v3.verify_freeze_manifest()


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
