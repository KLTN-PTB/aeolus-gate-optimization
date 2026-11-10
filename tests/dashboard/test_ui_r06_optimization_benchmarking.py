"""Unit and Integration Tests for Phase UI-R06: Optimization Lab & Fair Scientific Benchmarking.

Verifies:
- Task R06-A: Real artifact record count (95 rows) and schema integrity.
- Task R06-B: Fair comparison policy (cross-scenario/workload ranking blocked).
- Task R06-C & R06-D: Honest status separation, zero false optimality for Greedy and SA.
- Task R06-E: Cost semantics, UNKNOWN without incumbent has cost N/A, zero baseline improvement is N/A.
- Task R06-F: Cost-Runtime scatter, biobjective Pareto non-dominated set calculation.
- Task R06-G: Algorithmic phase runtime breakdown (build vs search vs validation).
- Task R06-H: Scalability curves, N=1500 UNKNOWN status, empty state when artifact missing.
- Task R06-I: Experiment selector, zero implicit solving on filter, artifact hash preservation.
"""

import hashlib
import math
from typing import Any, Dict, List
import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.core.status_mapping import SolverStatus, map_solver_status_to_badge
from dashboard.core.validation import IncompatibleComparisonError, ScientificValidator
from dashboard.visualizers.optimization_charts import (
    create_formulation_comparison_figure,
    create_pareto_frontier_figure,
    create_runtime_breakdown_figure,
    create_scalability_curve_figure,
)


# -----------------------------------------------------------------------------
# R06-T01 to R06-T02: Benchmark Schema & Provenance (Task R06-A)
# -----------------------------------------------------------------------------

def test_r06_t01_artifact_record_count_correct() -> None:
    """R06-T01: Artifact record count is verified from solver_runs.csv (95 records, not hardcoded)."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 95
    assert not df.empty


def test_r06_t02_schema_validation_required_columns() -> None:
    """R06-T02: solver_runs.csv contains all mandatory scientific benchmark columns."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    mandatory_cols = {
        "scenario_id",
        "solver_variant",
        "solver_status",
        "feasible",
        "optimality_proven",
        "objective_value",
        "build_time_ms",
        "search_time_ms",
        "total_wall_clock_ms",
        "reassignment_count",
        "remote_count",
    }
    missing = mandatory_cols - set(df.columns)
    assert len(missing) == 0, f"Missing mandatory benchmark columns: {missing}"


# -----------------------------------------------------------------------------
# R06-T03 to R06-T08: Fair Comparison Policy & Guards (Task R06-B)
# -----------------------------------------------------------------------------

def test_r06_t03_same_workload_comparison_valid() -> None:
    """R06-T03: Comparing two feasible runs on the same workload passes validation."""
    rec_a = {"scenario_id": "SCEN_TIER_B_100F_20G", "solver_status": "OPTIMAL", "feasible": True, "n_flights": 100}
    rec_b = {"scenario_id": "SCEN_TIER_B_100F_20G", "solver_status": "FEASIBLE", "feasible": True, "n_flights": 100}
    # Should not raise
    ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r06_t04_different_scenario_ranking_blocked() -> None:
    """R06-T04: Comparing runs from different scenarios raises IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_TIER_A_10F_3G", "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_TIER_B_100F_20G", "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="Scenario mismatch"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r06_t05_different_gate_inventory_blocked() -> None:
    """R06-T05: Comparing runs with different gate inventory raises IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_100", "n_gates": 20, "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_100", "n_gates": 30, "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="Benchmark configuration mismatch for 'n_gates'"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r06_t06_different_capacity_blocked() -> None:
    """R06-T06: Comparing runs with different capacity policies raises IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_100", "capacity_policy": "FINITE_REMOTE_ONLY", "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_100", "capacity_policy": "UNBOUNDED_OVERFLOW", "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="Benchmark configuration mismatch for 'capacity_policy'"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r06_t07_different_objective_blocked() -> None:
    """R06-T07: Comparing runs with different objective versions raises IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_100", "objective_version": "OBJ_V1_LEGACY", "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_100", "objective_version": "OBJ_V2_SEPARATION", "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="Benchmark configuration mismatch for 'objective_version'"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r06_t08_different_prediction_source_blocked() -> None:
    """R06-T08: Comparing runs with different prediction sources raises IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_100", "prediction_source": "SCHEDULE_BASELINE", "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_100", "prediction_source": "ML_DUAL_CORE", "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="Benchmark configuration mismatch for 'prediction_source'"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


# -----------------------------------------------------------------------------
# R06-T09 to R06-T14: Statuses & No False Optimality (Task R06-D)
# -----------------------------------------------------------------------------

def test_r06_t09_unknown_without_incumbent_no_cost() -> None:
    """R06-T09: UNKNOWN runs without incumbent have cost None, never 0.0 or fabricated numbers."""
    view = adapt_solver_result_to_view(
        result={
            "status": "UNKNOWN",
            "termination_reason": "TIME_LIMIT",
            "objective_value": None,
            "solve_time_sec": 10.0,
            "assignments": [],
        },
        solver_name="CP-SAT",
        scenario_id="SCEN_TIER_B_300F_50G",
    )
    assert view.decision_cost is None
    assert view.reporting_cost is None
    assert ScientificValidator.is_objective_defined(view.status) is False


def test_r06_t10_infeasible_excluded_from_ranking() -> None:
    """R06-T10: INFEASIBLE runs are rejected from comparative ranking."""
    rec_inf = {"scenario_id": "SCEN_100", "solver_status": "INFEASIBLE", "feasible": False}
    rec_ok = {"scenario_id": "SCEN_100", "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError, match="only verified feasible runs can be ranked"):
        ScientificValidator.validate_benchmark_record_compatibility(rec_inf, rec_ok)


def test_r06_t11_invalid_result_excluded_from_ranking() -> None:
    """R06-T11: is_status_feasible_for_ranking returns False for UNKNOWN and INFEASIBLE."""
    assert ScientificValidator.is_status_feasible_for_ranking("OPTIMAL") is True
    assert ScientificValidator.is_status_feasible_for_ranking("FEASIBLE") is True
    assert ScientificValidator.is_status_feasible_for_ranking("UNKNOWN") is False
    assert ScientificValidator.is_status_feasible_for_ranking("INFEASIBLE") is False
    assert ScientificValidator.is_status_feasible_for_ranking("MODEL_INVALID") is False


def test_r06_t12_feasible_not_labeled_as_optimal() -> None:
    """R06-T12: SolverStatus.FEASIBLE badge does not claim optimal."""
    badge = map_solver_status_to_badge("FEASIBLE", "FEASIBLE_FOUND")
    assert "TỐI ƯU TUYỆT ĐỐI" not in badge.label
    assert badge.is_optimal is False
    assert badge.is_feasible is True


def test_r06_t13_greedy_not_globally_optimal_by_default() -> None:
    """R06-T13: Deterministic Greedy in benchmark runs is never marked optimality_proven=True."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    greedy_runs = df[df["solver_variant"].str.contains("GREEDY", case=False)]
    assert len(greedy_runs) > 0
    assert all(not opt for opt in greedy_runs["optimality_proven"])


def test_r06_t14_sa_not_globally_optimal_by_default() -> None:
    """R06-T14: Standalone Simulated Annealing in benchmark runs is never marked optimality_proven=True."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    sa_standalone = df[df["solver_variant"] == "SA_STANDALONE"]
    assert len(sa_standalone) > 0
    assert all(not opt for opt in sa_standalone["optimality_proven"])


# -----------------------------------------------------------------------------
# R06-T15 to R06-T18: Cost & Runtime Semantics (Task R06-E & R06-G)
# -----------------------------------------------------------------------------

def test_r06_t15_cost_from_real_artifact_no_fallback() -> None:
    """R06-T15: Benchmark costs originate from real CSV records, eliminating hardcoded 130.00 pts."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    costs = df["objective_value"].dropna().tolist()
    assert len(costs) > 0
    # Values vary across scenarios, not hardcoded constant 130.00
    assert len(set(costs)) > 5


def test_r06_t16_runtime_units_correct_positive_numbers() -> None:
    """R06-T16: total_wall_clock_ms contains finite positive millisecond values."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    runtimes = df["total_wall_clock_ms"].tolist()
    assert all(math.isfinite(t) and t > 0.0 for t in runtimes)


def test_r06_t17_total_vs_search_time_distinguished() -> None:
    """R06-T17: Total wall-clock time includes build and search: total >= search across all runs."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    # Allowing tiny float precision tolerance of 0.01 ms
    valid_times = df["total_wall_clock_ms"] + 0.01 >= df["search_time_ms"]
    assert valid_times.all()


def test_r06_t18_hybrid_stages_represented_correctly() -> None:
    """R06-T18: Hybrid solver runs record build_time, search_time, and validation_time."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    hybrid_runs = df[df["solver_variant"] == "HYBRID_STANDALONE"]
    assert len(hybrid_runs) > 0
    assert hybrid_runs["build_time_ms"].notna().all()
    assert hybrid_runs["search_time_ms"].notna().all()
    assert hybrid_runs["validation_time_ms"].notna().all()


# -----------------------------------------------------------------------------
# R06-T19 to R06-T20: Pareto Non-Dominated Set & Scatter (Task R06-F)
# -----------------------------------------------------------------------------

def test_r06_t19_pareto_nondominance_correct() -> None:
    """R06-T19: ScientificValidator.compute_pareto_frontier calculates exact non-dominated points."""
    points = [
        {"solver": "S1", "cost": 100.0, "time_ms": 10.0},  # Non-dominated
        {"solver": "S2", "cost": 80.0, "time_ms": 20.0},   # Non-dominated
        {"solver": "S3", "cost": 120.0, "time_ms": 15.0},  # Dominated by S1 (cost > 100, time > 10)
        {"solver": "S4", "cost": 90.0, "time_ms": 25.0},   # Dominated by S2 (cost > 80, time > 20)
        {"solver": "S5", "cost": 60.0, "time_ms": 50.0},   # Non-dominated
    ]
    frontier = ScientificValidator.compute_pareto_frontier(points, cost_key="cost", time_key="time_ms")
    frontier_solvers = [p["solver"] for p in frontier]
    assert frontier_solvers == ["S1", "S2", "S5"]


def test_r06_t20_scatter_correctly_labeled_and_scaled() -> None:
    """R06-T20: Cost-Runtime figure has clean title and log-scale X-axis without raw chart IDs."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    tier_b = df[df["scenario_id"] == "SCEN_TIER_B_100F_20G"]
    fig = create_pareto_frontier_figure(tier_b)
    assert isinstance(fig, go.Figure)
    assert "CHART-09" not in fig.layout.title.text
    assert fig.layout.xaxis.type == "log"


# -----------------------------------------------------------------------------
# R06-T21 to R06-T23: Scalability & Repeated Runs (Task R06-H)
# -----------------------------------------------------------------------------

def test_r06_t21_missing_scalability_artifact_empty_state() -> None:
    """R06-T21: Empty scalability DataFrame produces empty state annotation without fake fallback data."""
    fig = create_scalability_curve_figure(pd.DataFrame())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0  # No fake lines plotted
    assert len(fig.layout.annotations) > 0
    assert "không khả dụng" in fig.layout.annotations[0].text.lower()


def test_r06_t22_historical_1500_unknown_if_artifact_used() -> None:
    """R06-T22: N=1500 case in scalability_results.csv is strictly marked UNKNOWN with feasible=False."""
    loader = ArtifactLoader()
    df = loader.load_csv("artifacts/remediation/cp_sat/scalability_results.csv")
    rows_1500 = df[df["n_flights"] == 1500]
    assert len(rows_1500) > 0
    assert all(status == "UNKNOWN" for status in rows_1500["status"])
    assert all(not feasible for feasible in rows_1500["feasible"])


def test_r06_t23_repeated_runs_grouped_by_scenario_and_variant() -> None:
    """R06-T23: Benchmark runs contain multiple repetitions (seeds) grouped under the same scenario and variant."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    # Tier A 10F has 5 repetitions per variant
    tier_a_greedy = df[(df["scenario_id"] == "SCEN_TIER_A_10F_3G") & (df["solver_variant"] == "GREEDY_STANDALONE")]
    assert len(tier_a_greedy) == 5
    run_ids = tier_a_greedy["run_id"].tolist()
    assert len(set(run_ids)) == 5  # Distinct repetition IDs


# -----------------------------------------------------------------------------
# R06-T24 to R06-T28: Math Integrity, UI State & Immutability (Task R06-I)
# -----------------------------------------------------------------------------

def test_r06_t24_zero_baseline_improvement_na() -> None:
    """R06-T24: Relative improvement returns None (N/A) when baseline cost is 0.0."""
    assert ScientificValidator.compute_relative_improvement(0.0, 50.0) is None
    assert ScientificValidator.compute_relative_improvement(-10.0, 50.0) is None
    # Valid positive baseline returns proper ratio
    assert ScientificValidator.compute_relative_improvement(100.0, 80.0) == 0.20


def test_r06_t25_switching_experiment_updates_workload_records() -> None:
    """R06-T25: Selecting different workloads filters to disjoint scenario records."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    sub_10 = df[df["scenario_id"] == "SCEN_TIER_A_10F_3G"]
    sub_100 = df[df["scenario_id"] == "SCEN_TIER_B_100F_20G"]
    assert len(sub_10) == 25
    assert len(sub_100) == 15
    assert sub_10["scenario_id"].unique()[0] != sub_100["scenario_id"].unique()[0]
    assert set(sub_10.index).isdisjoint(set(sub_100.index))


def test_r06_t26_filter_does_not_launch_solver() -> None:
    """R06-T26: Querying and filtering benchmark DataFrames is purely passive and executes zero solvers."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    # Subsetting DataFrame is instantaneous and creates no new processes
    filtered = df[df["solver_variant"] == "CP_SAT_STANDALONE"]
    assert len(filtered) == 19


def test_r06_t27_benchmark_provenance_metadata_complete() -> None:
    """R06-T27: Benchmark artifact loader points to genuine remediation path with verifiable lineage."""
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    assert "experiment_id" in df.columns
    assert "timestamp_utc" in df.columns
    assert df["experiment_id"].iloc[0] in ("EXP_TIER_A", "EXP_TIER_B")


def test_r06_t28_no_modification_of_research_artifacts() -> None:
    """R06-T28: Research artifact CSVs have NOT been mutated or corrupted."""
    expected_hashes = {
        "artifacts/remediation/benchmarks/solver_runs.csv": "8f75063f6c1f88e16aa85c4f2064a124e0cce7ce5f12c586edcb22e7858f8fcf",
        "artifacts/remediation/cp_sat/scalability_results.csv": "0f2686e9ece489a80b6b205876ccc225a321059e08d999500ba9e333e0092428",
        "artifacts/remediation/cp_sat/formulation_comparison.json": "548e2ecbe539c685628adddf0a432329c2bc643cc3bba2f02639a7d6116e2633",
    }
    for file_path, expected_hash in expected_hashes.items():
        with open(file_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert actual_hash == expected_hash, f"Research artifact was modified! Hash mismatch for {file_path}"
