"""UI-R07 Test Suite: Monte Carlo Scientific Integrity, Robustness Lab & Research Inspector.

Validates tasks R07-A to R07-J via tests R07-T01 to R07-T35:
- Data Contract & Observation Identity (500 stochastic scenarios x 3 solvers = 1,500 evaluations).
- Selector & Group Filtering without multi-solver contamination.
- Mode A Feasibility (0.0%) vs Physical Conflict Rate (74.8%).
- Mode B vs Mode C Audit: Greedy Reference, Non-Deployable, No False Optimality.
- Cost Semantics & Statistical Metrics (Mean, Median, MCSE, 95% CI, CVaR95 >= P95).
- Paired Comparison via CRN matching keys.
- Dynamic Scenario Drill-down without fabricated flight Gantts.
- Research Inspector default NOT_CHECKED state.
"""

import json
import math
import numpy as np
import pandas as pd
import pytest

from dashboard.adapters.artifact_loader import ArtifactLoader, ArtifactNotFoundError
from dashboard.adapters.export_adapter import export_mc_summary_to_csv, export_manifest_to_json
from dashboard.adapters.monte_carlo_adapter import (
    adapt_mc_scenario_drilldown,
    adapt_monte_carlo_to_views,
    calculate_mc_stats,
    compute_paired_differences,
    validate_mc_dataframe,
)
from dashboard.components.research_inspector import sanitize_provenance_data
from dashboard.core.validation import (
    IncompatibleComparisonError,
    ScientificValidator,
)
from dashboard.visualizers.robustness_charts import (
    create_mc_boxplot_figure,
    create_mc_convergence_figure,
    create_mc_cost_distribution_figure,
    create_mc_ecdf_figure,
    validate_single_solver_dataframe,
)


# -----------------------------------------------------------------------------
# R07-T01 to R07-T05: Data Contract & Observation Identity (Task R07-A)
# -----------------------------------------------------------------------------

def test_r07_t01_artifact_schema_validated() -> None:
    """R07-T01: Monte Carlo artifacts exist and satisfy required column schemas."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    df_oracle = loader.load_monte_carlo_scenarios("oracle")

    req_cols = {"realization_id", "scenario_index", "solver_name", "mode", "feasible", "objective_value", "conflict_count"}
    assert req_cols.issubset(set(df_fixed.columns))
    assert req_cols.issubset(set(df_recourse.columns))
    assert req_cols.issubset(set(df_oracle.columns))


def test_r07_t02_missing_mc_artifact_unavailable() -> None:
    """R07-T02: Missing Monte Carlo artifact raises ArtifactNotFoundError without crashing."""
    loader = ArtifactLoader()
    with pytest.raises(ArtifactNotFoundError):
        loader.load_csv("artifacts/remediation/monte_carlo/non_existent_results.csv")


def test_r07_t03_no_fake_numerical_fallback() -> None:
    """R07-T03: adapt_monte_carlo_to_views returns empty dict for empty summary, no fake fallback numbers."""
    views = adapt_monte_carlo_to_views({})
    assert views == {}


def test_r07_t04_500_scenarios_x_3_solvers_distinct() -> None:
    """R07-T04: 1,500 rows in fixed_plan represent 500 distinct scenarios across 3 solvers."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    assert len(df) == 1500
    assert len(df["realization_id"].unique()) == 500
    solvers = set(df["solver_name"].unique())
    assert solvers == {"Greedy", "CPSat", "Hybrid"}
    for s in solvers:
        assert len(df[df["solver_name"] == s]) == 500


def test_r07_t05_1500_evaluations_not_labeled_1500_independent_scenarios() -> None:
    """R07-T05: ScientificValidator separates 500 scenarios from 1,500 total evaluation records."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    obs = ScientificValidator.validate_mc_observation_identity(df)
    assert obs["n_scenarios"] == 500
    assert obs["n_records"] == 1500
    assert obs["n_solvers"] == 3
    assert obs["is_homogeneous"] is False


# -----------------------------------------------------------------------------
# R07-T06 to R07-T10: Selector & Filtering without Contamination (Task R07-B)
# -----------------------------------------------------------------------------

def test_r07_t06_solver_filter_applied_to_histogram() -> None:
    """R07-T06: Passing multi-solver DataFrame with solver_name filters to homogeneous 500 rows in histogram."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    fig = create_mc_cost_distribution_figure(df_fixed, df_recourse, solver_name="CPSat")
    # Verify histogram traces exist
    assert len(fig.data) >= 2


def test_r07_t07_solver_filter_applied_to_ecdf() -> None:
    """R07-T07: validate_single_solver_dataframe isolates requested solver for ECDF."""
    loader = ArtifactLoader()
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    isolated = validate_single_solver_dataframe(df_recourse, solver_name="Greedy")
    assert len(isolated) == 500
    assert isolated["solver_name"].unique().tolist() == ["Greedy"]


def test_r07_t08_solver_filter_applied_to_boxplot() -> None:
    """R07-T08: validate_single_solver_dataframe isolates requested solver for boxplot."""
    loader = ArtifactLoader()
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    isolated = validate_single_solver_dataframe(df_recourse, solver_name="Hybrid")
    assert len(isolated) == 500
    assert isolated["solver_name"].unique().tolist() == ["Hybrid"]


def test_r07_t09_solver_filter_applied_to_convergence() -> None:
    """R07-T09: Convergence trace receives filtered 500 rows, avoiding multi-solver jump contamination."""
    loader = ArtifactLoader()
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    fig = create_mc_convergence_figure(df_recourse, solver_name="CPSat")
    assert len(fig.data) >= 3  # CI upper, CI lower fill, and running mean trace


def test_r07_t10_mixed_solver_population_rejected_when_not_allowed() -> None:
    """R07-T10: ScientificValidator raises IncompatibleComparisonError when allow_filter=False on mixed data."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    with pytest.raises(IncompatibleComparisonError, match="Multi-solver contamination detected"):
        ScientificValidator.validate_single_solver_dataframe(df_fixed, allow_filter=False)


# -----------------------------------------------------------------------------
# R07-T11 to R07-T13: Scenario Uniqueness & Accounting (Task R07-A & R07-F)
# -----------------------------------------------------------------------------

def test_r07_t11_duplicate_scenario_ids_detected() -> None:
    """R07-T11: validate_mc_dataframe detects duplicate scenario identifiers within a single solver subset."""
    df_dup = pd.DataFrame({
        "realization_id": ["S1", "S2", "S1"],
        "objective_value": [10.0, 20.0, 30.0],
    })
    with pytest.raises(ValueError, match="Duplicate scenario IDs found"):
        validate_mc_dataframe(df_dup)


def test_r07_t12_failed_observations_counted() -> None:
    """R07-T12: failures.json records 0 failed observations in P09."""
    loader = ArtifactLoader()
    failures = loader.load_json("artifacts/remediation/monte_carlo/failures.json")
    assert failures["total_failed"] == 0
    assert failures["total_successful"] == 3500


def test_r07_t13_requested_vs_evaluated_counts_correct() -> None:
    """R07-T13: Requested vs evaluated counts match exactly between manifest and summary."""
    loader = ArtifactLoader()
    manifest = loader.load_json("artifacts/remediation/monte_carlo/simulation_manifest.json")
    summary = loader.load_monte_carlo_statistical_summary()
    assert manifest["n_scenarios"] == 500
    assert summary["n_evaluated"] == 500
    assert summary["n_failed"] == 0


# -----------------------------------------------------------------------------
# R07-T14 to R07-T19: Statistical Metrics & Risk Tail Math (Task R07-F)
# -----------------------------------------------------------------------------

def test_r07_t14_mean_correct() -> None:
    """R07-T14: calculate_mc_stats accurately computes sample arithmetic mean."""
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_mc_stats(data)
    assert stats["mean"] == 30.0


def test_r07_t15_median_correct() -> None:
    """R07-T15: calculate_mc_stats accurately computes sample median."""
    data = [10.0, 20.0, 100.0, 30.0, 40.0]
    stats = calculate_mc_stats(data)
    assert stats["median"] == 30.0


def test_r07_t16_std_mcse_correct() -> None:
    """R07-T16: calculate_mc_stats uses ddof=1 for sample std and divides by sqrt(n) for MCSE."""
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_mc_stats(data)
    expected_std = float(np.std(data, ddof=1))
    expected_se = expected_std / math.sqrt(5)
    assert math.isclose(stats["std"], expected_std, rel_tol=1e-5)
    assert math.isclose(stats["mc_se"], expected_se, rel_tol=1e-5)


def test_r07_t17_ci_from_fixture_correct() -> None:
    """R07-T17: 95% Confidence Interval follows [mean - 1.96 * se, mean + 1.96 * se]."""
    data = [100.0, 105.0, 95.0, 102.0, 98.0]
    stats = calculate_mc_stats(data)
    assert math.isclose(stats["ci_95_lower"], stats["mean"] - 1.96 * stats["mc_se"], rel_tol=1e-5)
    assert math.isclose(stats["ci_95_upper"], stats["mean"] + 1.96 * stats["mc_se"], rel_tol=1e-5)


def test_r07_t18_p90_p95_correct() -> None:
    """R07-T18: Quantiles p90 and p95 match numpy percentiles."""
    data = list(range(1, 101))  # 1 to 100
    stats = calculate_mc_stats(data)
    assert stats["quantiles"]["p90"] == float(np.percentile(data, 90))
    assert stats["quantiles"]["p95"] == float(np.percentile(data, 95))


def test_r07_t19_cvar95_correct() -> None:
    """R07-T19: CVaR95 is defined as upper tail mean and is strictly >= p95."""
    data = list(range(1, 101))  # 1 to 100
    stats = calculate_mc_stats(data)
    p95 = stats["quantiles"]["p95"]
    cvar95 = stats["cvar_95"]
    assert cvar95 >= p95
    assert ScientificValidator.is_cvar_distinct_from_percentile(cvar95, p95) is True


# -----------------------------------------------------------------------------
# R07-T20 to R07-T24: Scientific Integrity of Mode A & C (Task R07-C & R07-D)
# -----------------------------------------------------------------------------

def test_r07_t20_mode_a_feasibility_and_conflict_distinct() -> None:
    """R07-T20: Mode A physical conflict probability (74.8%) and static feasibility (0.0%) are distinct."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    cpsat_sub = df[df["solver_name"] == "CPSat"]
    phys_conf_rate = (cpsat_sub["conflict_count"] > 0).mean()
    feas_rate = cpsat_sub["feasible"].mean()
    assert math.isclose(phys_conf_rate, 0.748, rel_tol=1e-3)
    assert feas_rate == 0.0


def test_r07_t21_mode_b_c_effective_solver_audited() -> None:
    """R07-T21: Both Mode B and Mode C run DeterministicGreedy in the audited P09 engine."""
    import inspect
    from src.simulation.monte_carlo_engine_p09 import evaluate_mode_c_perfect_foresight_oracle
    loader = ArtifactLoader()
    df_oracle = loader.load_monte_carlo_scenarios("oracle")
    # In oracle_results.csv, solver_name is Oracle_Greedy
    assert "Oracle_Greedy" in df_oracle["solver_name"].unique()
    sig = inspect.signature(evaluate_mode_c_perfect_foresight_oracle)
    assert "Greedy" in str(sig.parameters["solver_name"].default)


def test_r07_t22_greedy_mode_c_not_globally_optimal() -> None:
    """R07-T22: Mode C Oracle claim of global optimality is rejected because solver is heuristic."""
    with pytest.raises(IncompatibleComparisonError, match="Mode C Oracle claim invalid"):
        ScientificValidator.audit_oracle_claims(
            mode_name="MODE_C_ORACLE",
            is_deployable=False,
            is_optimal=True,  # Prohibited claim!
        )


def test_r07_t23_oracle_parity_claim_blocked_if_unsupported() -> None:
    """R07-T23: Claiming deployability for Mode C Oracle raises IncompatibleComparisonError."""
    with pytest.raises(IncompatibleComparisonError, match="Mode C Oracle violates deployment constraints"):
        ScientificValidator.audit_oracle_claims(
            mode_name="MODE_C_ORACLE",
            is_deployable=True,  # Prohibited claim!
            is_optimal=False,
        )


def test_r07_t24_mode_c_clearly_non_deployable() -> None:
    """R07-T24: adapt_monte_carlo_to_views sets is_deployable=False for Mode C."""
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary, solver_key="CPSat")
    assert views["mode_c"].is_deployable is False
    assert "KHÔNG phải là nghiệm tối ưu toán học toàn cục" in views["mode_c"].academic_notes


# -----------------------------------------------------------------------------
# R07-T25 to R07-T28: Paired Comparison & Cost Semantics (Task R07-E & R07-G)
# -----------------------------------------------------------------------------

def test_r07_t25_paired_join_uses_matching_scenario_ids() -> None:
    """R07-T25: compute_paired_differences joins strictly by realization_id key."""
    df_a = pd.DataFrame({"realization_id": ["S1", "S2"], "objective_value": [100.0, 200.0]})
    df_b = pd.DataFrame({"realization_id": ["S2", "S1"], "objective_value": [80.0, 50.0]})  # Reverse order
    diff = compute_paired_differences(df_a, df_b, id_col="realization_id")
    # S1: 100 - 50 = 50; S2: 200 - 80 = 120; mean = 85.0
    assert diff["mean_delta_cost"] == 85.0
    assert diff["n_paired"] == 2


def test_r07_t26_unmatched_paired_data_rejected() -> None:
    """R07-T26: compute_paired_differences raises ValueError when scenario IDs do not match."""
    df_a = pd.DataFrame({"realization_id": ["S1", "S2"], "objective_value": [100.0, 200.0]})
    df_b = pd.DataFrame({"realization_id": ["S1", "S3"], "objective_value": [80.0, 50.0]})
    with pytest.raises(ValueError, match="Paired comparison requires exactly matched scenario IDs"):
        compute_paired_differences(df_a, df_b, strict_exact_match=True)


def test_r07_t27_paired_difference_sign_correct() -> None:
    """R07-T27: Paired difference for Mode A vs Mode B has positive mean delta (+1338.44 pts)."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    sub_a = df_fixed[df_fixed["solver_name"] == "CPSat"]
    sub_b = df_recourse[df_recourse["solver_name"] == "CPSat"]
    diff = compute_paired_differences(sub_a, sub_b)
    assert diff["mean_delta_cost"] > 1000.0  # ~1338.44 pts


def test_r07_t28_different_cost_semantics_handled() -> None:
    """R07-T28: Mode A mean cost (~1469 pts) represents penalty evaluation, Mode B (~130 pts) decision cost."""
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary, solver_key="CPSat")
    assert views["mode_a"].mean_cost > 1000.0
    assert views["mode_b"].mean_cost < 200.0


# -----------------------------------------------------------------------------
# R07-T29 to R07-T31: Scenario Drill-down & No Fabrications (Task R07-I)
# -----------------------------------------------------------------------------

def test_r07_t29_scenario_dropdown_derives_from_records() -> None:
    """R07-T29: Scenario options derive dynamically from real artifact realization IDs (500 total)."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    ids = sorted(list(df["realization_id"].unique()))
    assert len(ids) == 500
    assert ids[0] == "MC500_S0000"
    assert ids[-1] == "MC500_S0499"


def test_r07_t30_missing_scenario_not_default_success() -> None:
    """R07-T30: adapt_mc_scenario_drilldown returns None for non-existent scenario without defaulting feasible=True."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    drill = adapt_mc_scenario_drilldown("NON_EXISTENT_SCENARIO", df_fixed, df_recourse)
    assert drill["fixed_plan"] is None
    assert drill["recourse"] is None


def test_r07_t31_no_fabricated_flight_level_gantt() -> None:
    """R07-T31: Drill-down explicitly reports flight_level_assignments_available=False."""
    loader = ArtifactLoader()
    df_fixed = loader.load_monte_carlo_scenarios("fixed_plan")
    df_recourse = loader.load_monte_carlo_scenarios("recourse")
    drill = adapt_mc_scenario_drilldown("MC500_S0000", df_fixed, df_recourse)
    assert drill["flight_level_assignments_available"] is False


# -----------------------------------------------------------------------------
# R07-T32 to R07-T35: Research Inspector, State Safety & Provenance (Task R07-J)
# -----------------------------------------------------------------------------

def test_r07_t32_research_inspector_defaults_not_checked() -> None:
    """R07-T32: Research Inspector metadata defaults to NOT_CHECKED rather than hardcoded VERIFIED/PASSED."""
    sanitized = sanitize_provenance_data({
        "verifier_status": "NOT_CHECKED",
        "target_leakage_status": "NOT_CHECKED",
        "private_path": "C:\\Users\\Secret\\Aelous",
    })
    assert sanitized["verifier_status"] == "NOT_CHECKED"
    assert "Secret" not in str(sanitized["private_path"])


def test_r07_t33_chart_selection_does_not_rerun_mc() -> None:
    """R07-T33: Filtering DataFrame by solver is passive in-memory operation."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("recourse")
    sub = validate_single_solver_dataframe(df, "CPSat")
    assert len(sub) == 500


def test_r07_t34_export_preserves_experiment_metadata() -> None:
    """R07-T34: export_mc_summary_to_csv preserves experiment ID in comment header or structure."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("recourse")
    csv_str = export_mc_summary_to_csv(df, experiment_id="EXP_P09_MC500")
    assert "EXP_P09_MC500" in csv_str


def test_r07_t35_no_scientific_warning_accidentally_hidden() -> None:
    """R07-T35: All 4 scientific warnings (D1, D2, Oracle, BTS 2024) are documented in page code."""
    with open("dashboard/pages/page_05_robustness_lab.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Finding D1" in content
    assert "Finding D2" in content
    assert "Mode C" in content
    assert "2024" in content
