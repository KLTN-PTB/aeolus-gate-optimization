"""Unit tests for Stage 10 freeze audit."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.stage10_auditor import audit_stage10_freeze

ROOT = Path(__file__).resolve().parents[1]


def test_stage10_freeze_audit_execution():
    """Verify that Stage 10 audit executes and checks freeze completeness."""
    result = audit_stage10_freeze(ROOT)
    assert result.stage_id == "STAGE_10_FULL_SYSTEM_FREEZE"
    assert result.model_weights_sha256_verified is True
    # Git commit hash is missing from freeze manifest, so git_commit_hash_recorded should be False
    assert result.git_commit_hash_recorded is False
    # Simulation & optimization config mismatch detected
    assert result.simulation_config_alignment is False
    assert result.optimization_config_alignment is False
    assert result.audit_status == "INCOMPLETE_OR_INCONSISTENT"


def test_stage10_missing_manifest(tmp_path: Path):
    """Verify that missing manifest triggers FAIL status."""
    res = audit_stage10_freeze(tmp_path)
    assert res.audit_status == "FAIL"
