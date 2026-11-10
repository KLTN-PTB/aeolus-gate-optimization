"""Unit tests for Provenance Tracker, Audit Table, and Claim Semantics."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.claim_auditor import ClaimSemanticsAuditor
from src.audit.provenance import ProvenanceTracker

ROOT = Path(__file__).resolve().parents[1]


def test_audit_table_generation():
    """Verify that provenance tracker generates a valid audit table."""
    tracker = ProvenanceTracker(ROOT)
    table = tracker.build_audit_table()
    assert len(table) >= 5

    # Check required fields on each record
    required_fields = {
        "artifact_id",
        "stage",
        "year",
        "role",
        "input_dataset",
        "candidate_id",
        "model_hash",
        "config_hash",
        "seed",
        "selection_dependency",
        "holdout_dependency",
        "status",
    }
    for rec in table:
        rec_dict = rec.to_dict()
        assert required_fields.issubset(rec_dict.keys())


def test_metric_lineage_traces():
    """Verify that metric traces are properly generated and categorized."""
    tracker = ProvenanceTracker(ROOT)
    traces = tracker.build_metric_provenance_traces()
    assert len(traces) >= 4

    types = set(tr.metric_type for tr in traces)
    assert "forecast_evaluation" in types
    assert "downstream_simulation" in types


def test_claim_semantics_auditor():
    """Verify that claim semantics auditor flags unsupported claims."""
    auditor = ClaimSemanticsAuditor(ROOT)
    flagged = auditor.audit_all_claims()
    assert len(flagged) >= 5

    flagged_terms = set(c.claim_term for c in flagged)
    assert "real-world gate conflict" in flagged_terms
    assert "ground truth gate assignment" in flagged_terms
    assert "unnecessary gate changes" in flagged_terms
    assert "real-world optimality" in flagged_terms
    assert "83.7% error reduction" in flagged_terms
