"""Test Suite for FinalEvaluationGuardV2 and System Freeze V2 Integrity (Task R11)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.evaluation.final_evaluation_guard_v2 import (
    EXPECTED_EVALUATION_ROLE,
    FORBIDDEN_EVALUATION_ROLES,
    FinalEvaluationGuardV2,
    FinalEvaluationGuardV2Error,
)


@pytest.fixture
def guard() -> FinalEvaluationGuardV2:
    return FinalEvaluationGuardV2()


def test_guard_v2_authorizes_clean_post_holdout_access(guard: FinalEvaluationGuardV2) -> None:
    """Verifies that FinalEvaluationGuardV2 permits access under clean POST_HOLDOUT conditions."""
    guard.assert_evaluation_authorized(
        evaluation_role="POST_HOLDOUT",
        year=2024,
        purpose="post_holdout_evaluation",
    )


@pytest.mark.parametrize("role", sorted(list(FORBIDDEN_EVALUATION_ROLES)))
def test_guard_v2_rejects_forbidden_evaluation_roles(
    guard: FinalEvaluationGuardV2,
    role: str,
) -> None:
    """Verifies that all non-post-holdout roles fail closed."""
    with pytest.raises(FinalEvaluationGuardV2Error, match="is STRICTLY PROHIBITED"):
        guard.assert_evaluation_authorized(
            evaluation_role=role,
            year=2024,
            purpose="post_holdout_evaluation",
        )


def test_guard_v2_rejects_non_2024_year(guard: FinalEvaluationGuardV2) -> None:
    """Verifies that guard only authorizes for year 2024."""
    with pytest.raises(FinalEvaluationGuardV2Error, match="only authorized for year 2024"):
        guard.assert_evaluation_authorized(
            evaluation_role="POST_HOLDOUT",
            year=2023,
            purpose="post_holdout_evaluation",
        )


def test_guard_v2_rejects_non_post_holdout_purpose(guard: FinalEvaluationGuardV2) -> None:
    """Verifies that guard fails closed if purpose is not post_holdout_evaluation."""
    with pytest.raises(FinalEvaluationGuardV2Error, match="purpose must be 'post_holdout_evaluation'"):
        guard.assert_evaluation_authorized(
            evaluation_role="POST_HOLDOUT",
            year=2024,
            purpose="model_tuning",
        )


def test_guard_v2_fails_if_manifest_missing(tmp_path: Path) -> None:
    """Verifies that guard fails closed if freeze manifest v2 is missing."""
    empty_guard = FinalEvaluationGuardV2(project_root=tmp_path)
    with pytest.raises(FinalEvaluationGuardV2Error, match="manifest v2 does not exist"):
        empty_guard.verify_freeze_manifest()


def test_guard_v2_fails_if_checksum_mismatch(tmp_path: Path) -> None:
    """Verifies that guard detects tampering of the freeze manifest v2."""
    manifest_dir = tmp_path / "artifacts" / "manifests"
    manifest_dir.mkdir(parents=True)
    manifest_file = manifest_dir / "system_freeze_manifest_v2.json"
    sidecar_file = manifest_dir / "system_freeze_manifest_v2.sha256"

    manifest_file.write_text('{"freeze_status": "FROZEN_V2"}', encoding="utf-8")
    sidecar_file.write_text("badhash12345  system_freeze_manifest_v2.json\n", encoding="utf-8")

    tampered_guard = FinalEvaluationGuardV2(project_root=tmp_path)
    with pytest.raises(FinalEvaluationGuardV2Error, match="Freeze manifest checksum mismatch"):
        tampered_guard.verify_freeze_manifest()


def test_freeze_v2_manifest_and_audit_completeness(guard: FinalEvaluationGuardV2) -> None:
    """Verifies that freeze manifest v2 covers all 23 categories and audit v2 is passed."""
    payload = guard.verify_freeze_manifest()
    assert payload["freeze_status"] == "FROZEN_V2"
    assert payload["final_holdout_year"] == 2024

    categories = payload["freeze_categories"]
    assert len(categories) == 23

    # Check key categories exist
    assert "A_data_contracts" in categories
    assert "B_feature_code" in categories
    assert "D_model_code" in categories
    assert "O_monte_carlo" in categories
    assert "W_final_guard" in categories

    audit_path = Path("artifacts/audit/final_development_freeze_audit_v2.json")
    assert audit_path.exists()
    audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit_data["overall_audit_status"] == "PASSED"
    assert audit_data["next_step_allowed"] == "YES"

    dev_manifest_path = Path("artifacts/manifests/development_evidence_manifest_v2.json")
    assert dev_manifest_path.exists()
    dev_data = json.loads(dev_manifest_path.read_text(encoding="utf-8"))
    assert dev_data["status"] == "DEVELOPMENT_REBUILD_VERIFIED"
    assert dev_data["failures_encountered"] == 0
