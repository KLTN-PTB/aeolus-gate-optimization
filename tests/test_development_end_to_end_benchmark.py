"""Test Suite for Step 7 — Broader Development End-to-End Benchmark.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19
Verifies:
1. Prerequisites: Steps 1-6 manifests all exist with status PASS.
2. Artifact Completeness: All 7 required artifacts exist in artifacts/development_end_to_end/.
3. Scenario Registry Integrity: Covers all 4 development days across varying demand levels.
4. Solvers Hard Feasibility: Greedy, CP-SAT, and SA all achieve 100% feasibility and 0 contact conflicts.
5. Failures Traceability: failures.json exists, 0 silent drops.
6. Method-Wise Distributions: aggregate_metrics.json records statistical distributions across methods.
7. Deterministic Repetition: Certified deterministic reproducibility on identical seed/registry.
8. Protocol Compliance: Strictly development data (2016-2023), 0 access to 2024 holdout.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
import pytest

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BENCHMARK_DIR = PROJECT_ROOT / "artifacts" / "development_end_to_end"


@pytest.fixture(scope="module")
def run_manifest() -> dict:
    manifest_path = BENCHMARK_DIR / "run_manifest.json"
    assert manifest_path.exists(), f"run_manifest.json not found at {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def aggregate_metrics() -> dict:
    metrics_path = BENCHMARK_DIR / "aggregate_metrics.json"
    assert metrics_path.exists(), f"aggregate_metrics.json not found at {metrics_path}"
    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def failures_data() -> dict:
    failures_path = BENCHMARK_DIR / "failures.json"
    assert failures_path.exists(), f"failures.json not found at {failures_path}"
    with open(failures_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def scenario_registry_df() -> pd.DataFrame:
    p = BENCHMARK_DIR / "scenario_registry.parquet"
    assert p.exists(), f"scenario_registry.parquet not found at {p}"
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def greedy_results_df() -> pd.DataFrame:
    p = BENCHMARK_DIR / "greedy_results.parquet"
    assert p.exists(), f"greedy_results.parquet not found at {p}"
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def cpsat_results_df() -> pd.DataFrame:
    p = BENCHMARK_DIR / "cp_sat_results.parquet"
    assert p.exists(), f"cp_sat_results.parquet not found at {p}"
    return pd.read_parquet(p)


@pytest.fixture(scope="module")
def sa_results_df() -> pd.DataFrame:
    p = BENCHMARK_DIR / "sa_results.parquet"
    assert p.exists(), f"sa_results.parquet not found at {p}"
    return pd.read_parquet(p)


def test_prerequisites_all_pass():
    """Verify that prerequisite manifests from Steps 1-6 all exist and are PASS."""
    audit_dir = PROJECT_ROOT / "artifacts" / "audit"
    manifests_dir = PROJECT_ROOT / "artifacts" / "manifests"

    prereqs = {
        "step_1": manifests_dir / "probabilistic_stage9_gate_simulation_v1.json",
        "step_2": audit_dir / "phase_d_cp_sat_objective_audit_manifest_v1.json",
        "step_3": audit_dir / "phase_f_time_limited_sa_benchmark_manifest_v1.json",
        "step_4": audit_dir / "phase_h_holdout_fold_guard_correction_manifest_v1.json",
        "step_5": audit_dir / "phase_c_dependence_contract_consistency_manifest_v1.json",
        "step_6": audit_dir / "phase_g_timeline_semantics_audit_manifest_v1.json",
    }
    for step_name, path in prereqs.items():
        assert path.exists(), f"Prerequisite manifest for {step_name} missing: {path}"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            stat = data.get("status")
            if stat is None and "joint_sampler_validation" in data:
                stat = data["joint_sampler_validation"].get("status")
            assert stat in {"PASS", "VALIDATED_PASS"}, f"{step_name} status is {stat}, expected PASS"


def test_all_seven_artifacts_exist():
    """Verify all 7 required artifact files exist in artifacts/development_end_to_end/."""
    required_files = [
        "run_manifest.json",
        "scenario_registry.parquet",
        "greedy_results.parquet",
        "cp_sat_results.parquet",
        "sa_results.parquet",
        "aggregate_metrics.json",
        "failures.json",
    ]
    for fname in required_files:
        p = BENCHMARK_DIR / fname
        assert p.exists(), f"Required artifact {fname} missing from {BENCHMARK_DIR}"
        assert p.stat().st_size > 0, f"Artifact {fname} is empty"


def test_scenario_registry_integrity(scenario_registry_df: pd.DataFrame):
    """Verify scenario_registry.parquet schema, row count, demand levels, and hash validity."""
    df = scenario_registry_df
    assert len(df) == 40, f"Expected 40 scenarios across 4 days, got {len(df)}"

    required_cols = {
        "scenario_id",
        "day_id",
        "date_str",
        "demand_level",
        "n_flights",
        "n_contact_gates",
        "scenario_seed",
        "scenario_hash",
        "mean_delay_min",
        "p95_delay_min",
        "nominal_conflict_count",
    }
    assert required_cols.issubset(df.columns), f"Missing columns in registry: {required_cols - set(df.columns)}"

    # Check that all 4 demand levels are present
    demand_levels = set(df["demand_level"].unique())
    expected_demand_levels = {"LOW", "MEDIUM", "HIGH", "WEATHER_DISRUPTED"}
    assert demand_levels == expected_demand_levels, f"Expected {expected_demand_levels}, got {demand_levels}"

    # Check unique scenario hashes
    assert df["scenario_hash"].nunique() == len(df), "All scenario hashes must be unique"


def test_solver_results_hard_feasibility_and_zero_conflicts(
    greedy_results_df: pd.DataFrame,
    cpsat_results_df: pd.DataFrame,
    sa_results_df: pd.DataFrame,
):
    """Verify that all solvers achieve 100% hard constraint feasibility and zero contact conflicts."""
    # 1. Greedy
    assert len(greedy_results_df) == 40
    assert greedy_results_df["feasibility"].all() is True or greedy_results_df["feasibility"].all() == 1
    assert greedy_results_df["simulated_conflicts"].sum() == 0
    assert greedy_results_df["conflict_duration"].sum() == 0.0

    # 2. CP-SAT
    assert len(cpsat_results_df) == 40
    assert cpsat_results_df["feasibility"].all() is True or cpsat_results_df["feasibility"].all() == 1
    assert cpsat_results_df["simulated_conflicts"].sum() == 0
    assert cpsat_results_df["conflict_duration"].sum() == 0.0

    # 3. SA (both branches)
    assert len(sa_results_df) == 80  # 40 CP-SAT+SA and 40 Greedy+SA
    assert sa_results_df["feasibility"].all() is True or sa_results_df["feasibility"].all() == 1
    assert sa_results_df["simulated_conflicts"].sum() == 0
    assert sa_results_df["conflict_duration"].sum() == 0.0


def test_failures_json_integrity(failures_data: dict):
    """Verify failures.json properly traces errors and confirms 0 silent drops."""
    assert "failures_count" in failures_data
    assert "failed_scenarios" in failures_data
    assert "silently_dropped_scenarios_count" in failures_data
    assert failures_data["silently_dropped_scenarios_count"] == 0
    assert failures_data["failures_count"] == len(failures_data["failed_scenarios"])


def test_aggregate_metrics_method_distributions(aggregate_metrics: dict):
    """Verify aggregate_metrics.json records comprehensive statistical distributions across methods."""
    assert aggregate_metrics["all_hard_feasibility_satisfied"] is True
    assert aggregate_metrics["zero_contact_conflicts_across_all_solvers"] is True

    method_dists = aggregate_metrics["method_distributions"]
    expected_methods = ["Greedy", "CP-SAT", "SA_CPSAT_Incumbent", "SA_Greedy_WarmStart"]
    for m in expected_methods:
        assert m in method_dists, f"Missing method distribution for {m}"
        dist = method_dists[m]
        assert dist["hard_feasibility_rate"] == 100.0
        assert dist["contact_conflicts_total"] == 0
        for metric in ["objective", "decision_cost", "runtime_ms", "utilization"]:
            assert metric in dist
            stats = dist[metric]
            for s in ["mean", "std", "median", "p10", "p90", "min", "max"]:
                assert s in stats, f"Missing {s} in {m} {metric}"


def test_demand_level_breakdown_exists(aggregate_metrics: dict):
    """Verify demand level breakdown covers all 4 operational demand levels."""
    breakdown = aggregate_metrics["demand_level_breakdown"]
    for lvl in ["LOW", "MEDIUM", "HIGH", "WEATHER_DISRUPTED"]:
        assert lvl in breakdown, f"Missing demand level {lvl}"
        info = breakdown[lvl]
        assert info["scenarios"] == 10
        assert info["greedy_mean_objective"] is not None
        assert info["cpsat_mean_objective"] is not None


def test_deterministic_reproducibility_certified(run_manifest: dict):
    """Verify deterministic repetition confirmation in run_manifest.json."""
    assert run_manifest["status"] == "PASS"
    assert run_manifest["deterministic_repetition_confirmed"] is True
    assert run_manifest["all_hard_feasibility_satisfied"] is True
    assert run_manifest["zero_contact_conflicts_across_all_solvers"] is True


def test_no_2024_holdout_accessed(run_manifest: dict, scenario_registry_df: pd.DataFrame):
    """Verify strictly development data used, no 2024 dates evaluated."""
    for day in run_manifest["benchmark_days"]:
        assert not day["date_str"].startswith("2024"), f"Unauthorized 2024 date found: {day['date_str']}"

    for date_val in scenario_registry_df["date_str"].unique():
        assert not str(date_val).startswith("2024"), f"Unauthorized 2024 date in registry: {date_val}"
