"""Unit tests for Stage 9 downstream audit."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.stage9_auditor import audit_stage9_downstream

ROOT = Path(__file__).resolve().parents[1]


def test_stage9_audit_identifies_post_selection_reuse():
    """Verify that Stage 9 audit correctly identifies 100% data overlap with Stage 8."""
    result = audit_stage9_downstream(ROOT)
    assert result.stage_id == "STAGE_9_GATE_SIMULATION"
    assert result.days_evaluated == 25
    assert result.flights_evaluated == 529
    assert result.were_days_preregistered_before_stage8 is False
    assert result.were_days_excluded_from_stage8 is False
    assert result.overlap_with_stage8_data_percent == 100.0
    assert result.audit_status == "POST_SELECTION_REUSE"
    assert result.data_reuse_verdict == "CIRCULAR_DOWNSTREAM_REUSE_OF_SELECTION_DATA"


def test_stage9_missing_manifest(tmp_path: Path):
    """Verify that missing manifest triggers FAIL status."""
    res = audit_stage9_downstream(tmp_path)
    assert res.audit_status == "FAIL"
