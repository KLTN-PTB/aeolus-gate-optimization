"""Unit tests for Stage 11 holdout audit."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.stage11_auditor import audit_stage11_holdout

ROOT = Path(__file__).resolve().parents[1]


def test_stage11_holdout_audit_execution():
    """Verify that Stage 11 audit executes and identifies contradiction & post-holdout status."""
    result = audit_stage11_holdout(ROOT)
    assert result.stage_id == "STAGE_11_FINAL_HOLDOUT"
    assert result.current_repo_status == "POST_HOLDOUT"
    # Contradiction: manifest numbers say -387.2% reduction, but finding 3 claims >75% reduction
    assert result.claim_contradiction_detected is True
    assert result.downstream_conflict_error_reduction_2024 < 0  # -3.87234
    assert result.ground_truth_claim_validity is False


def test_stage11_missing_manifest(tmp_path: Path):
    """Verify that missing manifest triggers FAIL status."""
    res = audit_stage11_holdout(tmp_path)
    assert res.audit_status == "FAIL"
