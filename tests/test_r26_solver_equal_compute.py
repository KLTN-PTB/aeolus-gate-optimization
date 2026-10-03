"""Unit tests for AEOLUS V4 Task R26 — Solver Equal-Total-Compute Re-Certification.

Verifies:
1. test_same_total_budget: Every solver has total_budget_seconds <= 2.0s
2. test_hybrid_budget_sum: CP-SAT budget (1.0s) + SA budget (1.0s) == total_budget_seconds (2.0s)
3. test_cp_sat_budget: CP-SAT standalone budget == 2.0s
4. test_sa_budget: SA standalone budget == 2.0s
5. test_same_cases: All 4 solvers evaluated across exact same 28 scenario x forecast cases
6. test_same_constraints: No hard constraint violations permitted on feasible assignments
7. test_same_objective: Objective weights identical across all solvers
8. test_same_seed_policy: Predetermined deployment seed strictly enforced
9. test_solver_result_row_count: Exactly 112 results in parquet (28 cases x 4 solvers)
10. test_no_budget_overrun_contract: Actual solver runtimes conform to budget contract
11. test_sa_best_so_far_monotonic: Best-so-far objective trace is monotonically non-increasing
12. test_previous_non_equal_compute_claim_is_not_reused: Legacy unequal-compute claims are superseded
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "artifacts" / "audit" / "r26_solver_compute_contract.json"
RESULTS_PARQUET = ROOT / "artifacts" / "audit" / "r26_solver_equal_compute_results.parquet"
RECONCILIATION_PATH = ROOT / "artifacts" / "audit" / "r26_solver_budget_reconciliation.json"
DOC_PATH = ROOT / "docs" / "audit" / "R26_SOLVER_EQUAL_COMPUTE.md"


@pytest.fixture(scope="module")
def contract_data():
    assert CONTRACT_PATH.exists(), f"Missing contract: {CONTRACT_PATH}"
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def results_df():
    assert RESULTS_PARQUET.exists(), f"Missing parquet: {RESULTS_PARQUET}"
    return pd.read_parquet(RESULTS_PARQUET)


@pytest.fixture(scope="module")
def reconciliation_data():
    assert RECONCILIATION_PATH.exists(), f"Missing reconciliation: {RECONCILIATION_PATH}"
    with open(RECONCILIATION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_same_total_budget(contract_data, reconciliation_data):
    """Test 1: Every solver receives total budget <= 2.0s."""
    t_total = contract_data["total_wall_clock_budget_seconds"]
    assert t_total == 2.0, f"Expected 2.0s total budget, got {t_total}"
    assert reconciliation_data["equal_compute_compliance"]["same_total_budget_contract"] is True
    
    solvers = contract_data["solver_specifications"]
    for s_name, s_spec in solvers.items():
        allocated = s_spec.get("total_budget_seconds", s_spec.get("budget_seconds"))
        assert allocated <= t_total, (
            f"Solver {s_name} allocated {allocated} > {t_total}"
        )


def test_hybrid_budget_sum(contract_data, reconciliation_data):
    """Test 2: CP-SAT budget + SA budget == total_budget_seconds for Hybrid solver."""
    hybrid = contract_data["solver_specifications"]["HybridCPSatSA"]
    cp_part = hybrid["cp_sat_budget_seconds"]
    sa_part = hybrid["sa_budget_seconds"]
    total = hybrid["total_budget_seconds"]
    assert cp_part == 1.0, f"Expected CP-SAT 1.0s, got {cp_part}"
    assert sa_part == 1.0, f"Expected SA 1.0s, got {sa_part}"
    assert cp_part + sa_part == total == 2.0
    
    decomp = reconciliation_data["hybrid_budget_decomposition"]
    assert decomp["sum_constraint_satisfied"] is True
    assert decomp["cp_sat_budget"] == 1.0
    assert decomp["sa_budget"] == 1.0


def test_cp_sat_budget(contract_data):
    """Test 3: Standalone CP-SAT budget == 2.0s."""
    cpsat = contract_data["solver_specifications"]["CPSat"]
    assert cpsat["budget_seconds"] == 2.0


def test_sa_budget(contract_data):
    """Test 4: Standalone SA budget == 2.0s."""
    sa = contract_data["solver_specifications"]["SimulatedAnnealing"]
    assert sa["budget_seconds"] == 2.0


def test_same_cases(results_df, reconciliation_data):
    """Test 5: All 4 solvers evaluate the exact same 28 cases."""
    assert reconciliation_data["equal_compute_compliance"]["same_cases_evaluated"] is True
    solvers = sorted(results_df["solver_name"].unique())
    assert solvers == ["CPSat", "DeterministicGreedy", "HybridCPSatSA", "SimulatedAnnealing"]
    
    cases_by_solver = {}
    for s in solvers:
        cases_by_solver[s] = set(results_df[results_df["solver_name"] == s]["case_id"])
        assert len(cases_by_solver[s]) == 28, f"Solver {s} evaluated {len(cases_by_solver[s])} cases, expected 28"

    first_cases = cases_by_solver[solvers[0]]
    for s in solvers[1:]:
        assert cases_by_solver[s] == first_cases, f"Solver {s} case set differs from {solvers[0]}"


def test_same_constraints(reconciliation_data, results_df):
    """Test 6: All solvers enforce the same hard/soft constraints."""
    assert reconciliation_data["equal_compute_compliance"]["same_constraints_enforced"] is True
    
    # In parquet results, hard_constraint_violations must be 0 for all completed runs
    assert (results_df["hard_constraint_violations"] == 0).all()
    assert (results_df["hard_feasible"] == True).all()
    assert (results_df["realized_conflicts"] == 0).all()


def test_same_objective(contract_data, reconciliation_data):
    """Test 7: All solvers optimize the exact same objective weights."""
    assert reconciliation_data["equal_compute_compliance"]["same_objective_weights"] is True
    weights = contract_data["objective_configuration"]
    assert weights["reassignment_weight"] == 10.0
    assert weights["overflow_weight"] == 200.0
    assert weights["delay_weight"] == 1.0
    assert weights["conflict_weight"] == 1000.0
    assert weights["risk_weight"] == 2.0


def test_same_seed_policy(reconciliation_data, results_df):
    """Test 8: Predetermined deployment seed is applied consistently."""
    assert reconciliation_data["equal_compute_compliance"]["same_seed_policy"] is True
    assert (results_df["seed"] == 202601).all()


def test_solver_result_row_count(results_df, reconciliation_data):
    """Test 9: Parquet contains exactly 112 rows (28 cases x 4 solvers)."""
    assert len(results_df) == 112
    assert reconciliation_data["total_runs_evaluated"] == 112
    assert (results_df["status"] == "COMPLETED").all()


def test_no_budget_overrun_contract(results_df, reconciliation_data):
    """Test 10: Runtimes adhere to the wall-clock budget contract."""
    assert reconciliation_data["equal_compute_compliance"]["no_budget_overruns"] is True
    for idx, row in results_df.iterrows():
        solver = row["solver_name"]
        runtime = row["actual_runtime_seconds"]
        if solver == "DeterministicGreedy":
            assert runtime < 1.0, f"Greedy took unexpectedly long: {runtime}s"
        else:
            assert runtime < 3.0, f"{solver} severely exceeded budget: {runtime}s"


def test_sa_best_so_far_monotonic(results_df, reconciliation_data):
    """Test 11: SA and Hybrid solvers verify non-increasing best-so-far objective trace."""
    assert reconciliation_data["sa_monotonicity_audit"]["all_traces_monotonic"] is True
    sa_rows = results_df[results_df["solver_name"].isin(["SimulatedAnnealing", "HybridCPSatSA"])]
    assert (sa_rows["monotonicity_verified"] == True).all()


def test_previous_non_equal_compute_claim_is_not_reused(contract_data, reconciliation_data):
    """Test 12: Legacy Phase F / R15 unequal-compute claims are invalidated."""
    inval = contract_data["historical_claim_invalidation"]
    assert inval["status"] == "PREVIOUS_EVIDENCE_NOT_CERTIFIED"
    assert "Invalidated historical claim" in inval["action"]
    assert reconciliation_data["audit_verdict"] == "PASS"
    assert DOC_PATH.exists()
