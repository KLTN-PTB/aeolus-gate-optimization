"""Tests for Targeted Development Evidence Rebuild V3 (Task R21).

Verifies:
1. r21_rebuild_scope.json exists and strictly classifies all experiments.
2. All MUST_REBUILD experiments were actually recomputed with clean execution trace.
3. Academic Model Selection V3 decouples the 3 operational roles without claiming a single overall champion.
4. Downstream comparison evaluates exactly 84 runs (7 candidates x 4 scenarios x 3 solvers) under locked SCALAR_FORECAST_IMPACT semantics.
5. Monte Carlo convergence evaluates exact N in (100, 250, 500, 1000, 2500) under CRN with zero truncation, and marks variance reduction as NOT_ESTABLISHED.
6. Execution trace records cache_hit=False and fit/prediction/metric execution across all rebuilt experiments.
7. Temporal governance: 2024 holdout data remained unopened and sealed during R21.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_r21_rebuild_scope_manifest_validity() -> None:
    """Verify that rebuild scope manifest exists and classifies all experimental branches."""
    scope_path = ROOT / "artifacts" / "manifests" / "r21_rebuild_scope.json"
    assert scope_path.exists(), "Missing artifacts/manifests/r21_rebuild_scope.json"

    data = json.loads(scope_path.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "r21_rebuild_scope_v3"
    assert data["task_id"] == "R21_TARGETED_DEVELOPMENT_REBUILD_V3"
    assert data["temporal_scope"]["row_level_2024_access_permitted"] is False

    valid_statuses = {"VALID_TO_REUSE", "MUST_REBUILD", "INVALIDATED", "BLOCKED"}
    experiments = data["experiments"]
    assert len(experiments) >= 10

    for exp in experiments:
        assert exp["classification"] in valid_statuses
        assert "experiment_id" in exp
        assert "name" in exp
        assert "rationale" in exp

    # Check key classifications
    classifications = {e["experiment_id"]: e["classification"] for e in experiments}
    assert classifications["academic_model_selection_2023"] == "MUST_REBUILD"
    assert classifications["downstream_operational_comparison_2023"] == "MUST_REBUILD"
    assert classifications["monte_carlo_convergence_2023"] == "MUST_REBUILD"
    assert classifications["core_point_benchmark_folds_1_to_4"] == "VALID_TO_REUSE"
    assert classifications["holdout_evaluation_2024"] == "BLOCKED"


def test_academic_model_selection_v3_rebuilt_and_decoupled() -> None:
    """Verify that Academic Model Selection V3 exists and enforces 3 decoupled operational roles."""
    sel_path = ROOT / "artifacts" / "manifests" / "academic_model_selection_v3.json"
    sha_path = ROOT / "artifacts" / "manifests" / "academic_model_selection_v3.sha256"
    assert sel_path.exists(), "Missing academic_model_selection_v3.json"
    assert sha_path.exists(), "Missing academic_model_selection_v3.sha256"

    data = json.loads(sel_path.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "academic_model_selection_v3"
    assert "decoupled_operational_roles" in data

    roles = data["decoupled_operational_roles"]
    assert "role_a_point_prediction" in roles
    assert "role_b_probabilistic_forecasting" in roles
    assert "role_c_downstream_simulation" in roles

    # Verify no single overall champion claim
    assert roles["role_b_probabilistic_forecasting"]["role_status"] == "DECOUPLED_DUAL_ROLES_NO_SINGLE_OVERALL_CHAMPION"
    assert len(roles["role_c_downstream_simulation"]["candidates"]) == 7


def test_downstream_comparison_v3_execution_and_semantics() -> None:
    """Verify downstream comparison V3 completed 84 runs under locked semantics."""
    summary_path = ROOT / "artifacts" / "downstream_model_comparison_v3" / "downstream_summary.json"
    evals_path = ROOT / "artifacts" / "downstream_model_comparison_v3" / "evaluations.json"
    assert summary_path.exists(), "Missing downstream_summary.json in v3 directory"
    assert evals_path.exists(), "Missing evaluations.json in v3 directory"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_evaluations"] == 84
    assert summary["total_completed"] == 84
    assert len(summary["models_evaluated"]) == 7
    assert len(summary["scenarios_evaluated"]) == 4
    assert len(summary["solvers_evaluated"]) == 3

    # Check that individual evaluation records track distinct gate types
    records = json.loads(evals_path.read_text(encoding="utf-8"))
    assert len(records) == 84
    for r in records:
        assert "contact_count" in r
        assert "remote_count" in r
        assert "unassigned_count" in r
        assert "conflict_count" in r
        assert "runtime_ms" in r
        assert "hard_feasible" in r
        assert r["status"] == "COMPLETED"


def test_monte_carlo_v2_exact_counts_and_variance_reduction() -> None:
    """Verify Monte Carlo V2 evaluates exact counts and marks variance reduction as NOT_ESTABLISHED."""
    estimates_path = ROOT / "artifacts" / "monte_carlo_model_comparison_v2" / "convergence_estimates.json"
    vr_path = ROOT / "artifacts" / "monte_carlo_model_comparison_v2" / "crn_variance_reduction.json"
    assert estimates_path.exists(), "Missing convergence_estimates.json"
    assert vr_path.exists(), "Missing crn_variance_reduction.json"

    estimates = json.loads(estimates_path.read_text(encoding="utf-8"))
    assert len(estimates) == 30  # 6 models x 5 counts

    # Check zero truncation
    for est in estimates:
        assert est["n_requested"] == est["n_actual"]
        assert est["n_requested"] in [100, 250, 500, 1000, 2500]
        assert est["mc_se_objective"] >= 0.0

    # Check variance reduction report
    vr_reports = json.loads(vr_path.read_text(encoding="utf-8"))
    assert len(vr_reports) >= 1
    assert vr_reports[0]["status"] == "NOT_ESTABLISHED"


def test_r21_execution_trace_integrity() -> None:
    """Verify that execution trace records cache_hit=False and zero failures."""
    trace_path = ROOT / "artifacts" / "audit" / "r21_execution_trace.json"
    assert trace_path.exists(), "Missing artifacts/audit/r21_execution_trace.json"

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["status"] == "PASS"
    assert trace["summary"]["experiments_rebuilt"] == 3
    assert trace["summary"]["cache_hits"] == 0
    assert trace["summary"]["failures"] == 0
    assert trace["temporal_governance"]["holdout_2024_access_detected"] is False

    for exp in trace["rebuilt_experiments"]:
        assert exp["cache_hit"] is False
        assert exp["fit_executed"] is True
        assert exp["prediction_executed"] is True
        assert exp["metric_executed"] is True
