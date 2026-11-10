"""Tests for Phase P10-E: Optimization Lab, Robustness Lab & Research Inspector.

Validates:
- P10E-01 to P10E-10: Multi-solver benchmarking, fairness guards, Pareto & Scalability curves.
- P10E-11 to P10E-20: Monte Carlo simulation protocols, risk metrics, paired differences, drill-down.
- P10E-21 to P10E-26: Research Inspector, path sanitization, data leakage isolation, and export identity.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from dashboard.adapters.artifact_loader import (
    ArtifactLoader,
    ArtifactNotFoundError,
    ArtifactValidationError,
)
from dashboard.adapters.export_adapter import (
    export_benchmark_to_csv,
    export_mc_summary_to_csv,
    export_manifest_to_json,
)
from dashboard.adapters.monte_carlo_adapter import (
    adapt_mc_scenario_drilldown,
    adapt_monte_carlo_to_views,
    calculate_mc_stats,
    compute_paired_differences,
    validate_mc_dataframe,
)
from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.components.research_inspector import sanitize_provenance_data
from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.contracts import ProvenanceType, SolverRunView
from dashboard.core.validation import (
    DataLeakageError,
    IncompatibleComparisonError,
    ScientificValidator,
)
from dashboard.services.experiment_service import ExperimentService
from dashboard.visualizers.optimization_charts import (
    create_pareto_frontier_figure,
    create_runtime_breakdown_figure,
    create_scalability_curve_figure,
)
from dashboard.visualizers.robustness_charts import (
    create_mc_boxplot_figure,
    create_mc_convergence_figure,
    create_mc_cost_distribution_figure,
    create_mc_ecdf_figure,
)


@pytest.fixture
def sample_feasible_solver_run_a() -> SolverRunView:
    return SolverRunView(
        solver_name="CP-SAT",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=130.0,
        decision_cost=130.0,
        reporting_cost=0.0,
        reassignment_count=2,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.065,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
        solver_config={"w_pref": 10.0, "w_remote": 200.0, "buffer_time_min": 15},
    )


@pytest.fixture
def sample_feasible_solver_run_b() -> SolverRunView:
    return SolverRunView(
        solver_name="DeterministicGreedy",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=150.0,
        decision_cost=150.0,
        reporting_cost=0.0,
        reassignment_count=4,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.002,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 200.0, "buffer_time_min": 15},
    )


# ------------------------------------------------------------------------------
# P10E-01: Compatible solver runs comparable
# ------------------------------------------------------------------------------
def test_p10e_01_compatible_solver_runs_comparable(
    sample_feasible_solver_run_a: SolverRunView,
    sample_feasible_solver_run_b: SolverRunView,
) -> None:
    ranked = ExperimentService.rank_solver_runs([sample_feasible_solver_run_a, sample_feasible_solver_run_b])
    assert len(ranked) == 2
    assert ranked[0].solver_name == "CP-SAT"
    assert ranked[1].solver_name == "DeterministicGreedy"


# ------------------------------------------------------------------------------
# P10E-02: Scenario mismatch blocks ranking
# ------------------------------------------------------------------------------
def test_p10e_02_scenario_mismatch_blocks_ranking(
    sample_feasible_solver_run_a: SolverRunView,
) -> None:
    mismatched_run = SolverRunView(
        solver_name="Greedy",
        scenario_id="SCEN_DIFFERENT_999",
        objective_value=120.0,
        decision_cost=120.0,
        reporting_cost=0.0,
        reassignment_count=1,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.001,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 200.0},
    )
    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([sample_feasible_solver_run_a, mismatched_run])
    assert "Scenario mismatch" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-03: Objective mismatch blocks ranking
# ------------------------------------------------------------------------------
def test_p10e_03_objective_mismatch_blocks_ranking(
    sample_feasible_solver_run_a: SolverRunView,
) -> None:
    diff_weight_run = SolverRunView(
        solver_name="Greedy",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=120.0,
        decision_cost=120.0,
        reporting_cost=0.0,
        reassignment_count=1,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.001,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 500.0},  # Mismatch w_remote!
    )
    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([sample_feasible_solver_run_a, diff_weight_run])
    assert "Objective parameter mismatch" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-04: Capacity policy mismatch blocks ranking
# ------------------------------------------------------------------------------
def test_p10e_04_capacity_policy_mismatch_blocks_ranking(
    sample_feasible_solver_run_a: SolverRunView,
) -> None:
    diff_policy_run = SolverRunView(
        solver_name="Greedy",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=120.0,
        decision_cost=120.0,
        reporting_cost=0.0,
        reassignment_count=1,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.001,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 200.0, "capacity_policy": "POLICY_B_RESTRICTED"},
    )
    # Give base run a different capacity_policy
    base_run = SolverRunView(
        solver_name="CP-SAT",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=130.0,
        decision_cost=130.0,
        reporting_cost=0.0,
        reassignment_count=2,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.065,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
        solver_config={"w_pref": 10.0, "w_remote": 200.0, "capacity_policy": "POLICY_A_STANDARD"},
    )
    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([base_run, diff_policy_run])
    assert "capacity_policy" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-05: UNKNOWN excluded from feasible ranking
# ------------------------------------------------------------------------------
def test_p10e_05_unknown_excluded_from_feasible_ranking(
    sample_feasible_solver_run_a: SolverRunView,
) -> None:
    unknown_run = SolverRunView(
        solver_name="CP-SAT-BudgetExceeded",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=None,
        decision_cost=0.0,
        reporting_cost=0.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=10.0,
        status="UNKNOWN",
        termination_reason="TIME_LIMIT_NO_INCUMBENT",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 200.0},
    )
    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([sample_feasible_solver_run_a, unknown_run])
    assert "UNKNOWN" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-06: INFEASIBLE has no fabricated cost
# ------------------------------------------------------------------------------
def test_p10e_06_infeasible_has_no_fabricated_cost() -> None:
    assert ScientificValidator.is_objective_defined("INFEASIBLE") is False
    assert ScientificValidator.is_objective_defined("UNKNOWN") is False
    assert ScientificValidator.is_objective_defined("FEASIBLE") is True
    assert ScientificValidator.is_objective_defined("OPTIMAL") is True


# ------------------------------------------------------------------------------
# P10E-07: Greedy/SA never falsely marked OPTIMAL
# ------------------------------------------------------------------------------
def test_p10e_07_greedy_sa_never_falsely_marked_optimal() -> None:
    raw_greedy = {
        "status": "OPTIMAL",
        "termination_reason": "OPTIMAL_PROVEN",
        "objective_value": 130.0,
        "runtime_ms": 2.5,
        "optimality_proven": True,  # False claim in raw dict!
    }
    view = adapt_solver_result_to_view(raw_greedy, solver_name="DeterministicGreedy", scenario_id="SCEN_01")
    assert view.is_optimal_proven is False

    raw_sa = {
        "status": "OPTIMAL",
        "termination_reason": "OPTIMAL_PROVEN",
        "objective_value": 130.0,
        "runtime_ms": 150.0,
        "optimality_proven": True,
    }
    view_sa = adapt_solver_result_to_view(raw_sa, solver_name="SimulatedAnnealing", scenario_id="SCEN_01")
    assert view_sa.is_optimal_proven is False


# ------------------------------------------------------------------------------
# P10E-08: Build/search/total timings handled correctly
# ------------------------------------------------------------------------------
def test_p10e_08_build_search_total_timings_handled_correctly() -> None:
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    assert not df.empty
    assert "build_time_ms" in df.columns
    assert "search_time_ms" in df.columns
    assert "total_wall_clock_ms" in df.columns

    # Verify search time is not confused with total wall clock
    for _, row in df.iterrows():
        assert row["total_wall_clock_ms"] >= row["search_time_ms"]

    fig = create_runtime_breakdown_figure(df)
    assert fig is not None
    assert len(fig.data) == 3  # Build, Search, Validation


# ------------------------------------------------------------------------------
# P10E-09: Hybrid timing does not omit stages
# ------------------------------------------------------------------------------
def test_p10e_09_hybrid_timing_does_not_omit_stages() -> None:
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    hybrid_rows = df[df["solver_variant"].str.contains("HYBRID", case=False)]
    assert not hybrid_rows.empty
    # Hybrid must have recorded build time, search time, and validation time
    assert hybrid_rows["build_time_ms"].mean() > 0
    assert hybrid_rows["search_time_ms"].mean() > 0
    assert hybrid_rows["validation_time_ms"].mean() >= 0


# ------------------------------------------------------------------------------
# P10E-10: P06 1500 case displays UNKNOWN
# ------------------------------------------------------------------------------
def test_p10e_10_p06_1500_case_displays_unknown() -> None:
    scalability_df = pd.DataFrame([
        {"n_flights": 100, "runtime_ms": 50.0, "solver_status": "OPTIMAL"},
        {"n_flights": 500, "runtime_ms": 1100.0, "solver_status": "OPTIMAL"},
        {"n_flights": 1500, "runtime_ms": 10000.0, "solver_status": "UNKNOWN"},
    ])
    fig = create_scalability_curve_figure(scalability_df)
    assert fig is not None
    # Annotation for 1500 must mention UNKNOWN
    annotations_text = " ".join([str(a.text) for a in fig.layout.annotations])
    assert "UNKNOWN" in annotations_text
    assert "1,500" in annotations_text


# ------------------------------------------------------------------------------
# P10E-11: Monte Carlo modes remain distinct
# ------------------------------------------------------------------------------
def test_p10e_11_monte_carlo_modes_remain_distinct() -> None:
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary)

    assert "mode_a" in views
    assert "mode_b" in views
    assert "mode_c" in views

    view_a = views["mode_a"]
    view_b = views["mode_b"]
    view_c = views["mode_c"]

    # Distinct semantics
    assert view_a.physical_conflict_rate > 0.0   # 74.8% conflicts in Mode A
    assert view_b.physical_conflict_rate == 0.0  # Absorbed in Mode B
    assert view_a.mean_cost > view_b.mean_cost   # Mode A carries penalty cost


# ------------------------------------------------------------------------------
# P10E-12: Mode C prominently labeled NON-DEPLOYABLE
# ------------------------------------------------------------------------------
def test_p10e_12_mode_c_prominently_labeled_non_deployable() -> None:
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary)
    view_c = views["mode_c"]

    assert view_c.is_deployable is False
    assert "Mode C" in view_c.academic_notes or "Oracle" in view_c.academic_notes


# ------------------------------------------------------------------------------
# P10E-13: Exactly matched scenario IDs required for paired analysis
# ------------------------------------------------------------------------------
def test_p10e_13_exactly_matched_scenario_ids_required_for_paired_analysis() -> None:
    df_a = pd.DataFrame({
        "realization_id": ["MC_01", "MC_02", "MC_03"],
        "objective_value": [100.0, 110.0, 120.0],
    })
    df_b = pd.DataFrame({
        "realization_id": ["MC_01", "MC_02", "MC_04"],  # MC_04 instead of MC_03!
        "objective_value": [90.0, 95.0, 100.0],
    })

    with pytest.raises(ValueError) as exc:
        compute_paired_differences(df_a, df_b, strict_exact_match=True)
    assert "Paired comparison requires exactly matched scenario IDs" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-14: Duplicate MC IDs rejected
# ------------------------------------------------------------------------------
def test_p10e_14_duplicate_mc_ids_rejected() -> None:
    df_dup = pd.DataFrame({
        "realization_id": ["MC_01", "MC_02", "MC_02"],  # Duplicate MC_02!
        "objective_value": [10.0, 20.0, 30.0],
    })
    with pytest.raises(ValueError) as exc:
        validate_mc_dataframe(df_dup)
    assert "Duplicate scenario IDs found" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-15: Missing MC scenarios reported
# ------------------------------------------------------------------------------
def test_p10e_15_missing_mc_scenarios_reported() -> None:
    df_a = pd.DataFrame({
        "realization_id": ["MC_01", "MC_02", "MC_03", "MC_04"],
        "objective_value": [10.0, 20.0, 30.0, 40.0],
    })
    df_b = pd.DataFrame({
        "realization_id": ["MC_01", "MC_02"],
        "objective_value": [10.0, 20.0],
    })
    with pytest.raises(ValueError) as exc:
        compute_paired_differences(df_a, df_b, strict_exact_match=True)
    assert "Missing in dataset B: 2" in str(exc.value)


# ------------------------------------------------------------------------------
# P10E-16: Correct MCSE/CI/quantile/CVaR from golden fixtures
# ------------------------------------------------------------------------------
def test_p10e_16_correct_mcse_ci_quantile_cvar_from_golden_fixtures() -> None:
    loader = ArtifactLoader()
    recourse_df = loader.load_monte_carlo_scenarios("recourse")
    cpsat_recourse = recourse_df[recourse_df["solver_name"] == "CPSat"]

    stats = calculate_mc_stats(cpsat_recourse["objective_value"])

    assert stats["n"] == 500
    assert pytest.approx(stats["mean"], rel=1e-2) == 130.73
    assert pytest.approx(stats["std"], rel=1e-2) == 25.37
    assert pytest.approx(stats["mc_se"], rel=1e-2) == 1.13
    assert pytest.approx(stats["quantiles"]["p90"], rel=1e-2) == 163.48
    assert pytest.approx(stats["quantiles"]["p95"], rel=1e-2) == 177.37
    assert pytest.approx(stats["cvar_95"], rel=1e-2) == 195.56


# ------------------------------------------------------------------------------
# P10E-17: Cost semantics displayed correctly
# ------------------------------------------------------------------------------
def test_p10e_17_cost_semantics_displayed_correctly() -> None:
    loader = ArtifactLoader()
    fixed_df = loader.load_monte_carlo_scenarios("fixed_plan")
    recourse_df = loader.load_monte_carlo_scenarios("recourse")

    # Mode A carries conflict penalties (>1000 pts average)
    mean_a = fixed_df[fixed_df["solver_name"] == "CPSat"]["objective_value"].mean()
    # Mode B carries operational decision cost (~130 pts average)
    mean_b = recourse_df[recourse_df["solver_name"] == "CPSat"]["objective_value"].mean()

    assert mean_a > 1000.0
    assert mean_b < 200.0

    fig_hist = create_mc_cost_distribution_figure(fixed_df, recourse_df)
    assert fig_hist is not None


# ------------------------------------------------------------------------------
# P10E-18: Missing oracle records handled
# ------------------------------------------------------------------------------
def test_p10e_18_missing_oracle_records_handled() -> None:
    loader = ArtifactLoader()
    fixed_df = loader.load_monte_carlo_scenarios("fixed_plan")
    recourse_df = loader.load_monte_carlo_scenarios("recourse")

    # Pass oracle_df=None, must render cleanly
    fig = create_mc_cost_distribution_figure(fixed_df, recourse_df, oracle_df=None)
    assert fig is not None

    fig_ecdf = create_mc_ecdf_figure(fixed_df, recourse_df, oracle_df=None)
    assert fig_ecdf is not None


# ------------------------------------------------------------------------------
# P10E-19: Scenario drill-down never invents missing flight assignments
# ------------------------------------------------------------------------------
def test_p10e_19_scenario_drilldown_never_invents_missing_flight_assignments() -> None:
    loader = ArtifactLoader()
    fixed_df = loader.load_monte_carlo_scenarios("fixed_plan")
    recourse_df = loader.load_monte_carlo_scenarios("recourse")

    drilldown = adapt_mc_scenario_drilldown("MC500_S0000", fixed_df, recourse_df)
    assert drilldown["scenario_id"] == "MC500_S0000"
    assert drilldown["flight_level_assignments_available"] is False
    assert "Khai báo minh bạch" in drilldown["academic_note"]


# ------------------------------------------------------------------------------
# P10E-20: Scientific issue warnings visible where required
# ------------------------------------------------------------------------------
def test_p10e_20_scientific_issue_warnings_visible_where_required() -> None:
    # Verify warning documentation strings are present in page code
    page_05_path = DEFAULT_CONFIG.project_root / "dashboard" / "pages" / "page_05_robustness_lab.py"
    content = page_05_path.read_text(encoding="utf-8")

    assert "Finding D1" in content
    assert "Finding D2" in content
    assert "NON-DEPLOYABLE" in content
    assert "Quarantined Holdout" in content


# ------------------------------------------------------------------------------
# P10E-21: Research Inspector shows provenance
# ------------------------------------------------------------------------------
def test_p10e_21_research_inspector_shows_provenance() -> None:
    inspector_path = DEFAULT_CONFIG.project_root / "dashboard" / "components" / "research_inspector.py"
    content = inspector_path.read_text(encoding="utf-8")

    assert "Experiment Provenance" in content
    assert "Validation & Diagnostics" in content
    assert "Artifact Inspector" in content
    assert "Scientific Protocol" in content
    assert "Reproducibility" in content


# ------------------------------------------------------------------------------
# P10E-22: Actual data isolated from planning
# ------------------------------------------------------------------------------
def test_p10e_22_actual_data_isolated_from_planning() -> None:
    leaked_benchmark = pd.DataFrame([{
        "solver": "CP-SAT",
        "arr_delay": 45.0,  # Prohibited actual arrival delay!
        "objective_value": 130.0,
    }])
    with pytest.raises(DataLeakageError):
        export_benchmark_to_csv(leaked_benchmark, experiment_id="EXP_TEST")


# ------------------------------------------------------------------------------
# P10E-23: Changing chart filters doesn't launch simulations
# ------------------------------------------------------------------------------
def test_p10e_23_changing_chart_filters_doesnt_launch_simulations() -> None:
    base_filters = {"view_mode": "PRESENTATION", "search_query": ""}
    new_filters = {"view_mode": "PRESENTATION", "search_query": "A1"}

    assert ExperimentService.is_presentation_filter_mutation(base_filters, new_filters) is True


# ------------------------------------------------------------------------------
# P10E-24: No local secrets/absolute paths exposed
# ------------------------------------------------------------------------------
def test_p10e_24_no_local_secrets_absolute_paths_exposed() -> None:
    raw_meta = {
        "local_file": r"D:\Study\Code\Python\Aelous\artifacts\test.csv",
        "user_dir": "/home/heikapu/.gemini/secret",
        "api_token": "secret_token_12345",
        "safe_key": "EXP_01",
    }
    sanitized = sanitize_provenance_data(raw_meta)

    assert "D:\\Study" not in str(sanitized)
    assert "/home/heikapu" not in str(sanitized)
    assert "api_token" not in sanitized
    assert sanitized["safe_key"] == "EXP_01"


# ------------------------------------------------------------------------------
# P10E-25: Exported data preserve experiment identity
# ------------------------------------------------------------------------------
def test_p10e_25_exported_data_preserve_experiment_identity() -> None:
    df = pd.DataFrame([{"solver": "CPSat", "objective_value": 130.0}])
    csv_str = export_benchmark_to_csv(df, experiment_id="EXP_P06_IDENT_999")

    assert "experiment_id" in csv_str
    assert "EXP_P06_IDENT_999" in csv_str


# ------------------------------------------------------------------------------
# P10E-26: Missing/corrupt artifact does not crash whole app
# ------------------------------------------------------------------------------
def test_p10e_26_missing_corrupt_artifact_does_not_crash_whole_app(tmp_path: Path) -> None:
    loader = ArtifactLoader(config=DEFAULT_CONFIG)

    with pytest.raises(ArtifactNotFoundError):
        loader.load_csv("artifacts/remediation/non_existent_artifact_xyz.csv")

    corrupt_file = DEFAULT_CONFIG.project_root / "artifacts" / "remediation" / "corrupt_test.json"
    corrupt_file.write_text("NOT_VALID_JSON{", encoding="utf-8")
    try:
        with pytest.raises(ArtifactValidationError):
            loader.load_json("artifacts/remediation/corrupt_test.json")
    finally:
        if corrupt_file.exists():
            corrupt_file.unlink()
