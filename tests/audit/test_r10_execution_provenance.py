"""Test suite for R10 execution provenance and audit invariants (Task R13)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_r13_audit_artifacts_exist() -> None:
    """Audit artifacts for R13 must exist on disk."""
    trace_path = ROOT / "artifacts/audit/r13_r10_execution_trace.json"
    audit_path = ROOT / "artifacts/audit/r13_r10_rebuild_audit.json"
    doc_path = ROOT / "docs/audit/R13_R10_EXECUTION_AUDIT.md"

    assert trace_path.exists(), f"Missing trace artifact: {trace_path}"
    assert audit_path.exists(), f"Missing audit artifact: {audit_path}"
    assert doc_path.exists(), f"Missing audit report: {doc_path}"


def test_r13_trace_schema() -> None:
    """Execution trace must contain canonical audit fields."""
    trace_path = ROOT / "artifacts/audit/r13_r10_execution_trace.json"
    with open(trace_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_version"] == "r13_r10_execution_trace_v1"
    assert data["task_id"] == "R13_FORENSIC_R10_EXECUTION_AUDIT"
    traces = data["traces"]
    assert len(traces) > 0

    required_keys = {
        "experiment_id",
        "model_id",
        "fold_id",
        "seed",
        "temporal_role",
        "input_artifact",
        "output_artifact",
        "cache_hit",
        "cache_source",
        "fit_executed",
        "predict_executed",
        "metric_executed",
        "started_at",
        "finished_at",
        "runtime_seconds",
        "execution_classification",
        "code_hash",
        "config_hash",
    }
    for tr in traces[:20]:
        missing = required_keys - set(tr.keys())
        assert not missing, f"Trace entry missing keys: {missing}"


def test_r13_rebuild_classification_is_partial_and_blocked() -> None:
    """Forensic audit must fail-closed when artifact reuse is detected."""
    audit_path = ROOT / "artifacts/audit/r13_r10_rebuild_audit.json"
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "BLOCKED_REBUILD_REQUIRED"
    assert data["r10_rebuild_classification"] == "PARTIAL_REBUILD"
    assert data["acceptance_gate"]["gate_status"] == "BLOCKED_REBUILD_REQUIRED"
    assert data["acceptance_gate"]["next_step_allowed"] == "NO"
    assert data["data_safety_2024"]["status"] == "NOT_ACCESSED"


def test_r13_detects_stability_and_downstream_artifact_reuse() -> None:
    """Audit must correctly flag stability and downstream comparison as artifact reuse."""
    audit_path = ROOT / "artifacts/audit/r13_r10_rebuild_audit.json"
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    experiments = data["experiment_audit"]
    assert experiments["algorithmic_stability"]["classification"] == "ARTIFACT_REUSE"
    assert experiments["downstream_model_comparison"]["classification"] == "ARTIFACT_REUSE"
    assert experiments["monte_carlo_model_comparison"]["classification"] == "ARTIFACT_REUSE"
    assert experiments["model_selection_2023"]["classification"] == "ARTIFACT_ASSEMBLY_ONLY"
