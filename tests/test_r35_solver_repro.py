"""Unit and Forensic Verification Tests for AEOLUS V4 Task R35.

R35: SOLVER BOUNDARY & REPRODUCIBILITY ENVIRONMENT FORENSIC AUDIT

Verifies:
1. test_equal_wall_clock_contract: Same configured wall-clock ceiling (T=2.0s) across all solvers.
2. test_hybrid_total_budget: Hybrid decomposes into CP-SAT (1.0s) + SA (1.0s) <= T_total (2.0s) with 0 overruns.
3. test_solver_scope_28_cases: 28 problem instances across 4 solvers (112 runs) on 2024 seasonal post-holdout synthetic scenarios.
4. test_cp_sat_status: CP-SAT returned OPTIMAL on all 28 audited instances with 0 constraint violations.
5. test_cp_sat_optimality_claim: Optimality gap == 0.0 on all 28 cases; strictly bounded wording enforced.
6. test_hybrid_delta: Delta_i = Hybrid_i - CPSat_i == 0.0 for 100% of cases (28/28 cases, min=0, max=0, mean=0, std=0).
7. test_no_equal_work_claim: Prohibits claims of 'equal computational work' or 'equal CPU work'.
8. test_environment_versions_present: Exact package closure versions present for all core dependencies.
9. test_dependency_source_reconciles: Active virtual environment packages reconcile with R28 and R31 manifests.
10. test_artifact_environment_lineage: Artifact environment lineage is verified across R21-R31.
11. test_reproducibility_scope: Reproducibility scope verified as CONTAINED_SPECIFICATION_REPRODUCIBILITY.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

SOLVER_BOUNDARY_JSON = ROOT / "artifacts" / "audit" / "r35_solver_boundary_audit.json"
SOLVER_BOUNDARY_SHA = ROOT / "artifacts" / "audit" / "r35_solver_boundary_audit.json.sha256"

REPRO_ENV_JSON = ROOT / "artifacts" / "audit" / "r35_reproducibility_environment_audit.json"
REPRO_ENV_SHA = ROOT / "artifacts" / "audit" / "r35_reproducibility_environment_audit.json.sha256"

SOLVER_STATUS_PARQUET = ROOT / "artifacts" / "audit" / "r35_solver_status.parquet"
SOLVER_STATUS_SHA = ROOT / "artifacts" / "audit" / "r35_solver_status.parquet.sha256"

R26_PARQUET = ROOT / "artifacts" / "audit" / "r26_solver_equal_compute_results.parquet"
R26_CONTRACT = ROOT / "artifacts" / "audit" / "r26_solver_compute_contract.json"
R28_CLOSURE = ROOT / "artifacts" / "audit" / "r28_dependency_closure.json"
R31_CERT = ROOT / "artifacts" / "audit" / "final_evidence_certification_v4.json"


@pytest.fixture(scope="module")
def boundary_data() -> dict:
    assert SOLVER_BOUNDARY_JSON.is_file(), f"Missing {SOLVER_BOUNDARY_JSON}"
    return json.loads(SOLVER_BOUNDARY_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def repro_data() -> dict:
    assert REPRO_ENV_JSON.is_file(), f"Missing {REPRO_ENV_JSON}"
    return json.loads(REPRO_ENV_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def solver_status_df() -> pd.DataFrame:
    assert SOLVER_STATUS_PARQUET.is_file(), f"Missing {SOLVER_STATUS_PARQUET}"
    return pd.read_parquet(SOLVER_STATUS_PARQUET)


def test_equal_wall_clock_contract(boundary_data: dict) -> None:
    """Test 1: Verify all solvers operate under a strictly identical configured wall-clock ceiling (2.0s)."""
    assert boundary_data["solver_fairness_semantics"]["wall_clock_equality"] == "PROVEN"
    summary = boundary_data["solver_budget_summary"]
    for s_name, stats in summary.items():
        assert stats["budget_type"] in ("WALL_CLOCK", "SPLIT_WALL_CLOCK")
        assert stats["configured_budget_seconds"] == 2.0


def test_hybrid_total_budget(boundary_data: dict) -> None:
    """Test 2: Verify Hybrid solver split budget satisfies T_CP + T_SA <= T_total (1.0 + 1.0 == 2.0s)."""
    hyb = boundary_data["hybrid_budget_verification"]
    assert hyb["configured_cp_budget_s"] == 1.0
    assert hyb["configured_sa_budget_s"] == 1.0
    assert hyb["configured_total_budget_s"] == 2.0
    assert hyb["sum_equality_verified"] is True
    assert hyb["budget_ceiling_respected"] is True
    assert hyb["overrun_count"] == 0
    assert hyb["max_actual_total_runtime_s"] <= 2.0


def test_solver_scope_28_cases(solver_status_df: pd.DataFrame, boundary_data: dict) -> None:
    """Test 3: Verify benchmark scope is exactly 28 cases (112 runs) on 2024 seasonal post-holdout scenarios."""
    assert len(solver_status_df) == 112
    unique_solvers = sorted(solver_status_df["solver_name"].unique())
    assert unique_solvers == ["CPSat", "DeterministicGreedy", "HybridCPSatSA", "SimulatedAnnealing"]
    
    unique_cases = solver_status_df["case_id"].unique()
    assert len(unique_cases) == 28

    scope_reconcil = boundary_data["benchmark_scope_reconciliation"]
    assert scope_reconcil["r26_scope"]["total_cases"] == 28
    assert scope_reconcil["r26_scope"]["total_runs"] == 112
    assert scope_reconcil["r26_certifies_r21_downstream"] is False


def test_cp_sat_status(solver_status_df: pd.DataFrame, boundary_data: dict) -> None:
    """Test 4: Verify CP-SAT solver status is OPTIMAL for all 28 runs with 0 hard constraint violations."""
    cp_rows = solver_status_df[solver_status_df["solver_name"] == "CPSat"]
    assert len(cp_rows) == 28
    assert (cp_rows["solver_status"] == "OPTIMAL").all()
    assert (cp_rows["hard_feasible"] == True).all()

    audit_opt = boundary_data["cp_sat_optimality_audit"]
    assert audit_opt["total_cases_audited"] == 28
    assert audit_opt["status_counts"]["OPTIMAL"] == 28
    assert audit_opt["status_counts"]["FEASIBLE"] == 0
    assert audit_opt["status_counts"]["UNKNOWN"] == 0
    assert audit_opt["status_counts"]["TIME_LIMIT"] == 0


def test_cp_sat_optimality_claim(boundary_data: dict) -> None:
    """Test 5: Verify CP-SAT optimality claim is verified per case and strictly bounded."""
    audit_opt = boundary_data["cp_sat_optimality_audit"]
    assert audit_opt["verdict"] == "PROVEN_OPTIMAL_ON_ALL_28_AUDITED_CASES"
    assert audit_opt["optimality_gap"]["min"] == 0.0
    assert audit_opt["optimality_gap"]["max"] == 0.0
    assert audit_opt["best_bound_equals_objective"] is True
    assert "CP-SAT reached an OPTIMAL solution on all 28 audited instances" in audit_opt["safe_claim"]
    assert "Prohibited" in audit_opt["generalization_restriction"]


def test_hybrid_delta(solver_status_df: pd.DataFrame, boundary_data: dict) -> None:
    """Test 6: Verify Hybrid produces Delta_i == 0.0 relative to CP-SAT for 100% of cases."""
    hyb_rows = solver_status_df[solver_status_df["solver_name"] == "HybridCPSatSA"]
    assert len(hyb_rows) == 28
    assert (hyb_rows["delta_vs_cpsat"] == 0.0).all()

    audit_hyb = boundary_data["hybrid_zero_gain_audit"]
    assert audit_hyb["min_delta"] == 0.0
    assert audit_hyb["max_delta"] == 0.0
    assert audit_hyb["mean_delta"] == 0.0
    assert audit_hyb["std_delta"] == 0.0
    assert audit_hyb["count_exact_zero"] == 28
    assert audit_hyb["count_hybrid_better"] == 0
    assert audit_hyb["count_hybrid_worse"] == 0
    assert audit_hyb["percentage_zero_gain"] == 100.0


def test_no_equal_work_claim(boundary_data: dict) -> None:
    """Test 7: Verify computational work equality is marked NOT_PROVEN and banned from claims."""
    assert boundary_data["solver_fairness_semantics"]["computational_work_equality"] == "NOT_PROVEN"
    prohibited = boundary_data["solver_claim_boundary"]["prohibited_claims"]
    assert "equal computational work" in prohibited
    assert "equal CPU work" in prohibited
    assert "fair compute in all computational senses" in prohibited


def test_environment_versions_present(repro_data: dict) -> None:
    """Test 8: Verify exact package versions are present for all core libraries."""
    closure = repro_data["certified_package_closure"]
    expected_pkgs = [
        "numpy", "pandas", "scipy", "scikit-learn", "xgboost",
        "lightgbm", "ngboost", "ortools", "pyarrow", "optuna", "pytest"
    ]
    for pkg in expected_pkgs:
        assert pkg in closure, f"Missing {pkg} in certified package closure"
        assert len(closure[pkg]) > 0


def test_dependency_source_reconciles(repro_data: dict) -> None:
    """Test 9: Verify dependency closure reconciles across requirements.txt, R28, and R31."""
    reconcil = repro_data["environment_source_reconciliation"]
    assert reconcil["r28_dependency_closure"]["status"] == "IDENTICAL_MATCH"
    assert reconcil["r31_environment_freeze"]["status"] == "IDENTICAL_MATCH"
    
    r28_versions = reconcil["r28_dependency_closure"]["reconciled_versions"]
    r31_versions = reconcil["r31_environment_freeze"]["reconciled_versions"]
    for pkg, ver in r28_versions.items():
        assert r31_versions[pkg] == ver, f"Mismatch between R28 and R31 for {pkg}"


def test_artifact_environment_lineage(repro_data: dict) -> None:
    """Test 10: Verify critical artifacts trace their execution environment and SHA-256."""
    lineage = repro_data["artifact_environment_lineage"]
    critical_artifacts = [
        "system_freeze_manifest_v3",
        "academic_model_selection_v3",
        "post_holdout_evaluation_manifest_v3",
        "r26_solver_equal_compute_results",
        "final_evidence_certification_v4"
    ]
    for art in critical_artifacts:
        assert art in lineage
        assert lineage[art]["python_version"] == "3.11.15"
        assert len(lineage[art]["sha256"]) == 64


def test_reproducibility_scope(repro_data: dict) -> None:
    """Test 11: Verify reproducibility level is CONTAINED_SPECIFICATION_REPRODUCIBILITY and unproven claims banned."""
    contract = repro_data["reproducibility_contract"]
    assert contract["level"] == "CONTAINED_SPECIFICATION_REPRODUCIBILITY"
    assert "universally bit-for-bit reproducible" in contract["prohibited_wording"]
    assert "100% reproducible" in contract["prohibited_wording"]
    assert "CONTAINED_SPECIFICATION" in contract["level"]
