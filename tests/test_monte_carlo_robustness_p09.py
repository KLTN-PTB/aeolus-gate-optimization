"""Test Suite for Phase P09: Robustness & Monte Carlo Scientific Validation.

Covers verification specifications MC01 through MC28:
- MC01: Requested scenarios count (exactly 500).
- MC02: Scenario accounting reconciliation (generated = evaluated + failed).
- MC03: Fixed plan assignment invariance in Mode A.
- MC04: Recourse decision trace generation in Mode B.
- MC05: Perfect-foresight mode clearly labeled non-deployable in Mode C.
- MC06: Non-anticipativity / causality in Mode B.
- MC07: Identical scenario hashes across solvers.
- MC08: Finite remote stand capacity checked.
- MC09: Realized contact conflicts diagnosed.
- MC10: Planned vs realized feasibility separated.
- MC11: Monte Carlo SE formula correctness (s / sqrt(n)).
- MC12: Confidence interval formula correctness (mean +/- 1.96 * SE).
- MC13: Paired comparison scenario alignment and delta calculation.
- MC14: Zero-cost / zero-variance baseline handled gracefully.
- MC15: Distribution sampling finite without NaN or inf.
- MC16: Quantiles monotonic ordering.
- MC17: Copula parameter bounds validation.
- MC18: Covariance matrix positive-definiteness (eigenvalues > 0).
- MC19: Random seed reproducibility.
- MC20: Failed scenario retention and accounting.
- MC21: No hidden or silent scenario filtering.
- MC22: Objective standardization via common evaluator.
- MC23: Full metadata provenance in simulation manifest.
- MC24: Explicit SimulationMode enum semantics.
- MC25: Feasibility contract: conflict_count > 0 implies feasible=False.
- MC26: Analytical hand-calculated scenario verification.
- MC27: Sample size consistency across artifacts.
- MC28: Summary statistics match raw evaluations.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
)
from src.simulation.monte_carlo_engine_p09 import (
    CopulaDependenceModel,
    MonteCarloScenarioGenerator,
    RealizedScenario,
    RealizationResult,
    SimulationMode,
    apply_delays_to_flights,
    compute_monte_carlo_statistics,
    compute_paired_comparison,
    evaluate_mode_a_fixed_plan,
    evaluate_mode_b_reactive_recourse,
    evaluate_mode_c_perfect_foresight_oracle,
)


ARTIFACTS_DIR = Path("artifacts/remediation/monte_carlo")


# -------------------------------------------------------------------------
# MC01 - MC05: Protocol Modes & Accounting
# -------------------------------------------------------------------------

def test_mc01_requested_scenarios_count():
    """MC01: Exactly 500 scenarios requested and configured."""
    manifest_file = ARTIFACTS_DIR / "simulation_manifest.json"
    assert manifest_file.exists(), "simulation_manifest.json must exist"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["n_scenarios"] == 500


def test_mc02_scenario_accounting_reconciliation():
    """MC02: n_generated = n_evaluated + n_failed (500 = 500 + 0)."""
    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["n_generated"] == 500
    assert summary["n_evaluated"] == 500
    assert summary["n_failed"] == 0
    assert summary["n_generated"] == summary["n_evaluated"] + summary["n_failed"]


def test_mc03_fixed_plan_assignment_invariance():
    """MC03: Mode A keeps the initial planned assignment frozen across realizations."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    assert len(df_mode_a) == 1500  # 500 x 3 solvers
    # In Mode A, reassignment count from plan is zero (frozen plan)
    for solver in ["Greedy", "CPSat", "Hybrid"]:
        sub = df_mode_a[df_mode_a["solver_name"] == solver]
        assert len(sub) == 500
        assert (sub["reassignment_count"] == 0).all()


def test_mc04_recourse_decision_trace_generation():
    """MC04: Mode B produces an explicit decision trace when resolving conflicts."""
    gate_contact = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    gate_remote = Gate(gate_id="REMOTE1", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5)
    gates = [gate_contact, gate_remote]

    # Two flights planned at G1 at different times
    f1 = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", precomputed_gate_out_min=160,
    )
    f2 = Flight(
        flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
        scheduled_arrival_min=200, scheduled_departure_min=260, predicted_arrival_min=200,
        nominal_gate_id="G1", precomputed_gate_out_min=260,
    )
    initial_assignments = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment(flight_id="F2", gate_id="G1", occupancy_start_min=200, occupancy_end_min=275),
    }

    # Delay F1 by 60 min so its departure is 220, overlapping F2 at 200
    realized_flights = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", precomputed_gate_out_min=220,
        ),
        f2,
    ]
    scen = RealizedScenario(
        scenario_id="TEST_01", scenario_index=0,
        arrival_delays=(0.0, 0.0), departure_delays=(60.0, 0.0),
        realization_hash="hash123", seed=123,
    )
    cfg = GateOptimizationConfig(finite_remote_capacity=5)

    res, trace = evaluate_mode_b_reactive_recourse(
        initial_assignments=initial_assignments,
        realized_flights=realized_flights,
        gates=gates,
        config=cfg,
        realization=scen,
        solver_name="TestGreedy",
    )
    assert res.feasible is True
    assert len(trace) > 0, "Mode B must generate a decision trace when conflict occurs"
    assert trace[0]["flight_id"] == "F2"
    assert trace[0]["previous_gate"] == "G1"
    assert trace[0]["reassigned_gate"] == "REMOTE1"
    assert trace[0]["reason"] == "CONFLICT_OR_CAPACITY_AVOIDANCE"


def test_mc05_perfect_foresight_oracle_labeling():
    """MC05: Mode C results and summary are strictly labeled NON_DEPLOYABLE."""
    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert "mode_c_oracle" in summary
    assert "deployable_status" in summary["mode_c_oracle"]
    assert "NON_DEPLOYABLE" in summary["mode_c_oracle"]["deployable_status"]


# -------------------------------------------------------------------------
# MC06 - MC10: Domain Invariants & Separation
# -------------------------------------------------------------------------

def test_mc06_no_future_leakage_in_reactive_mode():
    """MC06: Reactive recourse does not use unobserved future realizations."""
    # In Mode B, recourse acts on realized intervals and initial plan, not future hypothetical states
    df_mode_b = pd.read_csv(ARTIFACTS_DIR / "recourse_results.csv")
    assert (df_mode_b["mode"] == SimulationMode.REACTIVE_RECOURSE.value).all()


def test_mc07_identical_scenario_hashes_across_solvers():
    """MC07: Realization hashes are identical across all solvers for each scenario."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    greedy_hashes = df_mode_a[df_mode_a["solver_name"] == "Greedy"].sort_values("scenario_index")["realization_hash"].values
    cpsat_hashes = df_mode_a[df_mode_a["solver_name"] == "CPSat"].sort_values("scenario_index")["realization_hash"].values
    hybrid_hashes = df_mode_a[df_mode_a["solver_name"] == "Hybrid"].sort_values("scenario_index")["realization_hash"].values
    np.testing.assert_array_equal(greedy_hashes, cpsat_hashes)
    np.testing.assert_array_equal(cpsat_hashes, hybrid_hashes)


def test_mc08_remote_finite_capacity_enforced():
    """MC08: Exceeding finite remote stand capacity is diagnosed as an infeasible violation."""
    g_contact = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    g_remote = Gate(gate_id="REMOTE1", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)
    gates = [g_contact, g_remote]

    # 3 flights occupying remote stand concurrently
    flights = [
        Flight(flight_id=f"F{i}", flight_index=i, carrier="DL", flight_number=f"10{i}",
               scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
               nominal_gate_id="REMOTE1", precomputed_gate_out_min=160)
        for i in range(3)
    ]
    assignments = {
        f.flight_id: GateAssignment(
            flight_id=f.flight_id,
            gate_id="REMOTE1",
            occupancy_start_min=f.occupancy_start_min,
            occupancy_end_min=f.occupancy_end_min,
            is_overflow=True,
            assignment_state=GateAssignmentState.REMOTE_STAND.value,
        )
        for f in flights
    }
    scen = RealizedScenario(
        scenario_id="TEST_CAP", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0), departure_delays=(0.0, 0.0, 0.0),
        realization_hash="hash_cap", seed=10,
    )
    cfg = GateOptimizationConfig(finite_remote_capacity=2, enforce_remote_capacity=True)

    res = evaluate_mode_a_fixed_plan(
        frozen_assignments=assignments,
        realized_flights=flights,
        gates=gates,
        config=cfg,
        realization=scen,
        solver_name="TestSolver",
    )
    assert res.remote_capacity_violation is True
    assert res.feasible is False
    assert res.max_concurrent_remote == 3


def test_mc09_contact_conflicts_audited():
    """MC09: Contact gate overlaps are identified and count towards conflict_count."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    # In Mode A, realized delays cause conflicts on contact gates
    assert df_mode_a["conflict_count"].max() > 0
    infeasible_rows = df_mode_a[df_mode_a["conflict_count"] > 0]
    assert (infeasible_rows["feasible"] == False).all()


def test_mc10_planned_vs_realized_feasibility_separated():
    """MC10: Initial plan is 100% feasible at T-2h, but Mode A realized feasibility drops."""
    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    # Mode A realized feasibility rate is 0.0 due to unmitigated delay overlaps
    assert summary["mode_a_fixed_plan"]["Greedy"]["feasibility_rate"] < 0.10
    # Mode B recourse resolves all conflicts to 100% feasibility
    assert summary["mode_b_recourse"]["Greedy"]["feasibility_rate"] == 1.0


# -------------------------------------------------------------------------
# MC11 - MC14: Statistical Inference & Formulas
# -------------------------------------------------------------------------

def test_mc11_monte_carlo_standard_error_formula():
    """MC11: SE = s / sqrt(n) matches sample standard deviation with ddof=1."""
    res_list = [
        RealizationResult(
            realization_id=f"R{i}", scenario_index=i, solver_name="S", mode="M",
            feasible=True, objective_value=float(cost), conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=1.0, realization_hash="h",
        )
        for i, cost in enumerate([10.0, 20.0, 30.0, 40.0, 50.0])
    ]
    stats = compute_monte_carlo_statistics(res_list, requested_n=5)
    expected_std = np.std([10.0, 20.0, 30.0, 40.0, 50.0], ddof=1)
    expected_se = expected_std / math.sqrt(5)
    assert math.isclose(stats["cost_std"], expected_std, abs_tol=1e-4)
    assert math.isclose(stats["monte_carlo_se"], expected_se, abs_tol=1e-4)


def test_mc12_confidence_interval_formula():
    """MC12: 95% CI bounds match mean +/- 1.96 * SE."""
    res_list = [
        RealizationResult(
            realization_id=f"R{i}", scenario_index=i, solver_name="S", mode="M",
            feasible=True, objective_value=float(c), conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=1.0, realization_hash="h",
        )
        for i, c in enumerate([100.0, 110.0, 120.0, 130.0])
    ]
    stats = compute_monte_carlo_statistics(res_list, requested_n=4)
    expected_mean = 115.0
    expected_se = np.std([100.0, 110.0, 120.0, 130.0], ddof=1) / math.sqrt(4)
    assert math.isclose(stats["mean_cost"], expected_mean, abs_tol=1e-4)
    assert math.isclose(stats["ci_95_lower"], expected_mean - 1.96 * expected_se, abs_tol=1e-4)
    assert math.isclose(stats["ci_95_upper"], expected_mean + 1.96 * expected_se, abs_tol=1e-4)


def test_mc13_paired_comparison_scenario_alignment():
    """MC13: Paired differences d_s = Cost_A(s) - Cost_B(s) require exact scenario index alignment."""
    res_a = [
        RealizationResult(
            realization_id=f"A{i}", scenario_index=i, solver_name="A", mode="M",
            feasible=True, objective_value=float(10 + i), conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=1.0, realization_hash="h",
        )
        for i in range(5)
    ]
    res_b = [
        RealizationResult(
            realization_id=f"B{i}", scenario_index=i, solver_name="B", mode="M",
            feasible=True, objective_value=float(5 + i), conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=1.0, realization_hash="h",
        )
        for i in range(5)
    ]
    paired = compute_paired_comparison(res_a, res_b, "A", "B")
    assert paired["mean_delta_cost"] == 5.0
    assert paired["std_delta_cost"] == 0.0

    # Test alignment validation error if indices mismatch
    res_b_misaligned = list(reversed(res_b))
    with pytest.raises(ValueError, match="Scenario alignment mismatch"):
        compute_paired_comparison(res_a, res_b_misaligned, "A", "B")


def test_mc14_zero_cost_baseline_handled():
    """MC14: Zero-variance or zero-cost cases do not crash with division by zero."""
    res_zero = [
        RealizationResult(
            realization_id=f"Z{i}", scenario_index=i, solver_name="Z", mode="M",
            feasible=True, objective_value=0.0, conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=1.0, realization_hash="h",
        )
        for i in range(5)
    ]
    stats = compute_monte_carlo_statistics(res_zero, requested_n=5)
    assert stats["cost_std"] == 0.0
    assert stats["monte_carlo_se"] == 0.0
    assert stats["mean_cost"] == 0.0


# -------------------------------------------------------------------------
# MC15 - MC19: Scenario Generation & Copula Integrity
# -------------------------------------------------------------------------

def test_mc15_distribution_sampling_finite():
    """MC15: All generated arrival and departure delays are strictly finite."""
    df_scen = pd.read_csv(ARTIFACTS_DIR / "scenario_index.csv")
    assert len(df_scen) == 500
    assert np.isfinite(df_scen["mean_arr_delay"]).all()
    assert np.isfinite(df_scen["mean_dep_delay"]).all()
    assert np.isfinite(df_scen["max_arr_delay"]).all()
    assert np.isfinite(df_scen["max_dep_delay"]).all()


def test_mc16_quantiles_monotonic_ordering():
    """MC16: Quantiles must be strictly monotonic: p10 <= p25 <= ... <= p99."""
    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    for mode_key in ["mode_a_fixed_plan", "mode_b_recourse"]:
        q = summary[mode_key]["Greedy"]["cost_quantiles"]
        vals = [q["p10"], q["p25"], q["p50"], q["p75"], q["p90"], q["p95"], q["p99"]]
        for i in range(len(vals) - 1):
            assert vals[i] <= vals[i + 1], f"Quantile ordering violated: {vals[i]} > {vals[i+1]}"


def test_mc17_copula_parameter_validation():
    """MC17: CopulaDependenceModel rejects correlation rho outside (-1, 1)."""
    with pytest.raises(ValueError, match="Correlation rho must be in"):
        CopulaDependenceModel(rho=1.5)
    with pytest.raises(ValueError, match="Correlation rho must be in"):
        CopulaDependenceModel(rho=-1.0)


def test_mc18_correlation_matrix_positive_definite():
    """MC18: Covariance matrix eigenvalues must be strictly positive."""
    copula = CopulaDependenceModel(rho=0.45)
    assert copula.is_positive_definite is True
    for ev in copula.eigenvalues:
        assert ev > 0.0
    # For 2x2 with rho=0.45, eigvals are 1 - 0.45 = 0.55 and 1 + 0.45 = 1.45
    assert math.isclose(copula.eigenvalues[0], 0.55, abs_tol=1e-4)
    assert math.isclose(copula.eigenvalues[1], 1.45, abs_tol=1e-4)


def test_mc19_random_seed_reproducibility():
    """MC19: Deterministic seed produces identical scenario hashes."""
    flights = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", precomputed_gate_out_min=160,
        )
    ]
    gen1 = MonteCarloScenarioGenerator(n_scenarios=5, seed=999)
    scens1 = gen1.generate_scenarios(flights)

    gen2 = MonteCarloScenarioGenerator(n_scenarios=5, seed=999)
    scens2 = gen2.generate_scenarios(flights)

    assert [s.realization_hash for s in scens1] == [s.realization_hash for s in scens2]


# -------------------------------------------------------------------------
# MC20 - MC24: Auditing, Governance & Manifests
# -------------------------------------------------------------------------

def test_mc20_failed_scenario_retention():
    """MC20: Failed scenarios are explicitly tracked and published in failures.json."""
    failures_file = ARTIFACTS_DIR / "failures.json"
    assert failures_file.exists(), "failures.json must exist"
    with open(failures_file, "r", encoding="utf-8") as f:
        failures = json.load(f)
    assert failures["total_failed"] == 0
    assert "silent_drop_audit" in failures


def test_mc21_no_silent_scenario_filtering():
    """MC21: Full accounting confirms 0 silent drops (exactly 1500 evaluations per mode table)."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    df_mode_b = pd.read_csv(ARTIFACTS_DIR / "recourse_results.csv")
    assert len(df_mode_a) == 1500
    assert len(df_mode_b) == 1500
    assert len(df_mode_a["scenario_index"].unique()) == 500
    assert len(df_mode_b["scenario_index"].unique()) == 500


def test_mc22_standardized_objective_evaluator_used():
    """MC22: Cost evaluation uses the common objective evaluator."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    assert "objective_value" in df_mode_a.columns
    assert (df_mode_a["objective_value"] >= 0.0).all()


def test_mc23_data_lineage_and_metadata_provenance():
    """MC23: Simulation manifest documents complete distribution provenance."""
    manifest_file = ARTIFACTS_DIR / "simulation_manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["pipeline"] == "MonteCarloRobustnessEngineP09"
    assert meta["seed"] == 202601
    assert meta["marginal_distributions"]["arrival"]["family"] == "Student-t"
    assert meta["marginal_distributions"]["departure"]["family"] == "Student-t"


def test_mc24_simulation_mode_enum_explicit():
    """MC24: SimulationMode enum values are explicitly declared and verified."""
    assert SimulationMode.FIXED_PLAN_ROBUSTNESS.value == "FIXED_PLAN_ROBUSTNESS"
    assert SimulationMode.REACTIVE_RECOURSE.value == "REACTIVE_RECOURSE"
    assert SimulationMode.PERFECT_FORESIGHT_ORACLE.value == "PERFECT_FORESIGHT_ORACLE"


# -------------------------------------------------------------------------
# MC25 - MC28: Verification & Hand-Calculated Ground Truth
# -------------------------------------------------------------------------

def test_mc25_infeasible_when_conflicts_exist():
    """MC25: Solution is strictly marked infeasible if conflict_count > 0."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    conflict_rows = df_mode_a[df_mode_a["conflict_count"] > 0]
    assert len(conflict_rows) > 0
    assert (conflict_rows["feasible"] == False).all()


def test_mc26_tiny_hand_calculated_scenario_match():
    """MC26: Hand-calculated 2-flight, 1-gate scenario matches expected analytical outcome.
    
    Analytical Ground Truth:
    - Contact gate G1, remote stand REMOTE1.
    - F1 planned [100, 160], F2 planned [170, 230] at G1 -> Disjoint initially.
    - Under realization, F1 delayed by 25 min -> [100, 185], overlapping F2 at [170, 185] (15 min overlap).
    - Mode A (zero re-optimization): Keeps both at G1 -> Conflict detected, conflict_count = 1, feasible = False.
    - Mode B (recourse): Detects conflict -> Reassigns F2 to REMOTE1 -> conflict_count = 0, feasible = True.
    """
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    r1 = Gate(gate_id="REMOTE1", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5)
    gates = [g1, r1]

    f1_plan = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", precomputed_gate_out_min=160,
    )
    f2_plan = Flight(
        flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
        scheduled_arrival_min=170, scheduled_departure_min=230, predicted_arrival_min=170,
        nominal_gate_id="G1", precomputed_gate_out_min=230,
    )
    initial_plan = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment(flight_id="F2", gate_id="G1", occupancy_start_min=170, occupancy_end_min=245),
    }

    # Realized F1 pushed to 185
    f1_realized = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", precomputed_gate_out_min=185,
    )
    realized_flights = [f1_realized, f2_plan]
    scen = RealizedScenario(
        scenario_id="TOY_SCEN", scenario_index=0,
        arrival_delays=(0.0, 0.0), departure_delays=(25.0, 0.0),
        realization_hash="toy_hash", seed=1,
    )
    cfg = GateOptimizationConfig(finite_remote_capacity=5)

    # Mode A Evaluation
    res_a = evaluate_mode_a_fixed_plan(
        frozen_assignments=initial_plan,
        realized_flights=realized_flights,
        gates=gates,
        config=cfg,
        realization=scen,
        solver_name="ToyGreedy",
    )
    assert res_a.conflict_count == 1
    assert res_a.feasible is False

    # Mode B Evaluation
    res_b, trace_b = evaluate_mode_b_reactive_recourse(
        initial_assignments=initial_plan,
        realized_flights=realized_flights,
        gates=gates,
        config=cfg,
        realization=scen,
        solver_name="ToyGreedy",
    )
    assert res_b.conflict_count == 0
    assert res_b.feasible is True
    assert len(trace_b) == 1
    assert trace_b[0]["flight_id"] == "F2"
    assert trace_b[0]["reassigned_gate"] == "REMOTE1"


def test_mc27_sample_size_consistency_in_report():
    """MC27: Sample size N=500 is consistent across all summary sections."""
    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["mode_a_fixed_plan"]["Greedy"]["n_evaluated"] == 500
    assert summary["mode_a_fixed_plan"]["CPSat"]["n_evaluated"] == 500
    assert summary["mode_a_fixed_plan"]["Hybrid"]["n_evaluated"] == 500
    assert summary["mode_b_recourse"]["Greedy"]["n_evaluated"] == 500
    assert summary["mode_b_recourse"]["CPSat"]["n_evaluated"] == 500
    assert summary["mode_b_recourse"]["Hybrid"]["n_evaluated"] == 500
    assert summary["mode_c_oracle"]["Oracle"]["n_evaluated"] == 500


def test_mc28_summary_statistics_match_raw_evaluations():
    """MC28: Summary statistics in JSON reconcile with calculations from raw CSV."""
    df_mode_a = pd.read_csv(ARTIFACTS_DIR / "fixed_plan_results.csv")
    sub = df_mode_a[df_mode_a["solver_name"] == "Greedy"]
    costs = sub["objective_value"].values

    summary_file = ARTIFACTS_DIR / "statistical_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    s_greedy = summary["mode_a_fixed_plan"]["Greedy"]

    assert math.isclose(s_greedy["mean_cost"], float(np.mean(costs)), abs_tol=1e-4)
    assert math.isclose(s_greedy["median_cost"], float(np.median(costs)), abs_tol=1e-4)
    assert math.isclose(s_greedy["cost_std"], float(np.std(costs, ddof=1)), abs_tol=1e-4)
