"""Unit tests for Stage 8 selection audit."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.stage8_auditor import audit_stage8_selection

ROOT = Path(__file__).resolve().parents[1]


def test_stage8_audit_execution():
    """Verify that Stage 8 audit runs cleanly and returns structured results."""
    result = audit_stage8_selection(ROOT)
    assert result.stage_id == "STAGE_8_SYSTEM_SELECTION"
    assert result.is_one_time_selection is True
    assert result.exactly_one_system_selected is True
    assert result.selected_system_id == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"
    assert result.candidate_pool_pre_frozen is True


def test_stage8_missing_manifest(tmp_path: Path):
    """Verify that missing manifest triggers FAIL status."""
    res = audit_stage8_selection(tmp_path)
    assert res.audit_status == "FAIL"
    assert res.is_one_time_selection is False
