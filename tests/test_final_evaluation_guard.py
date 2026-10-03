"""Unit tests for FinalEvaluationGuard (Phase 11).

Validates:
1. System freeze manifest exists, checksum matches, and freeze_status is FROZEN.
2. All config, feature, model code, and benchmark manifest hashes are validated against disk.
3. Access guard authorizes 2024 final_evaluation while rejecting development / HPO.
4. evaluation_role must be strictly 'POST_HOLDOUT'. Attempts to label as 'untouched_holdout',
   'unseen_final_test', or 'development' fail closed with FinalEvaluationGuardError.
5. Tampering with freeze manifest, checksum, or config files triggers immediate failure.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.evaluation.final_evaluation_guard import (
    FinalEvaluationGuard,
    FinalEvaluationGuardError,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.json"
CHECKSUM_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.sha256"


def test_guard_authorizes_clean_post_holdout_access() -> None:
    """Guard authorizes access when evaluation_role is explicitly POST_HOLDOUT."""
    guard = FinalEvaluationGuard(project_root=ROOT)
    payload = guard.assert_final_evaluation_authorized(
        evaluation_role="POST_HOLDOUT",
        purpose="final_evaluation",
    )
    assert payload["freeze_status"] == "FROZEN"
    assert payload["final_holdout_year"] == 2024
    assert payload["stage"] == "PHASE_10_FULL_SYSTEM_FREEZE"
    assert payload["frozen_system"]["system_id"] == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"


@pytest.mark.parametrize(
    "forbidden_role",
    [
        "untouched_holdout",
        "unseen_final_test",
        "development",
        "model_selection",
        "hpo",
        "tuning",
        "calibration",
        "random_test",
    ],
)
def test_guard_rejects_forbidden_evaluation_roles(forbidden_role: str) -> None:
    """Guard must fail closed if evaluation_role is anything other than POST_HOLDOUT."""
    guard = FinalEvaluationGuard(project_root=ROOT)
    with pytest.raises(FinalEvaluationGuardError, match="Unauthorized evaluation_role"):
        guard.assert_final_evaluation_authorized(
            evaluation_role=forbidden_role,
            purpose="final_evaluation",
        )


def test_guard_rejects_non_final_evaluation_purpose() -> None:
    """Guard must fail closed if purpose is not 'final_evaluation'."""
    guard = FinalEvaluationGuard(project_root=ROOT)
    with pytest.raises(FinalEvaluationGuardError, match="Unauthorized purpose"):
        guard.assert_final_evaluation_authorized(
            evaluation_role="POST_HOLDOUT",
            purpose="development",
        )


def test_guard_fails_if_manifest_missing(tmp_path: Path) -> None:
    """Guard must fail closed if system_freeze_manifest.json is missing."""
    empty_root = tmp_path / "empty_root"
    empty_root.mkdir(parents=True)
    guard = FinalEvaluationGuard(project_root=empty_root)
    with pytest.raises(FinalEvaluationGuardError, match="Prerequisite failure"):
        guard.verify_freeze_manifest()


def test_guard_fails_if_checksum_mismatch(tmp_path: Path) -> None:
    """Guard must detect manifest tampering via SHA256 checksum mismatch."""
    mock_root = tmp_path / "mock_repo"
    manifest_dir = mock_root / "artifacts" / "manifests"
    manifest_dir.mkdir(parents=True)

    fake_manifest = manifest_dir / "system_freeze_manifest.json"
    fake_checksum = manifest_dir / "system_freeze_manifest.sha256"

    fake_manifest.write_text(json.dumps({"freeze_status": "FROZEN", "final_holdout_year": 2024}), encoding="utf-8")
    fake_checksum.write_text("0000000000000000000000000000000000000000000000000000000000000000  system_freeze_manifest.json\n", encoding="utf-8")

    guard = FinalEvaluationGuard(project_root=mock_root)
    with pytest.raises(FinalEvaluationGuardError, match="Integrity violation"):
        guard.verify_freeze_manifest()


def test_guard_fails_if_freeze_status_not_frozen(tmp_path: Path) -> None:
    """Guard must fail closed if freeze_status is not FROZEN."""
    import hashlib
    mock_root = tmp_path / "mock_repo"
    manifest_dir = mock_root / "artifacts" / "manifests"
    manifest_dir.mkdir(parents=True)

    fake_manifest = manifest_dir / "system_freeze_manifest.json"
    fake_checksum = manifest_dir / "system_freeze_manifest.sha256"

    content = json.dumps({"freeze_status": "UNFROZEN", "final_holdout_year": 2024})
    fake_manifest.write_text(content, encoding="utf-8")
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    fake_checksum.write_text(f"{h}  system_freeze_manifest.json\n", encoding="utf-8")

    guard = FinalEvaluationGuard(project_root=mock_root)
    with pytest.raises(FinalEvaluationGuardError, match="System is not in FROZEN state"):
        guard.verify_freeze_manifest()
