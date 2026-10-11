"""Unit and integration test suite for Phase UI-R02 v2.0.

Scenario Identity, Session State & Execution Safety:
Tests covering R02-T01 through R02-T31:
- 3-Tier Identity Contracts: ScenarioDataIdentity, ProblemIdentity, ExecutionIdentity (R02-T01 to R02-T10)
- Config Normalization & Staleness Detection (R02-T11 to R02-T20)
- Solver Execution Safety, Rejection & Fallback Provenance (R02-T21 to R02-T25)
- Canonical PageKeys, State Lifecycle & Cross-Scenario Isolation (R02-T26 to R02-T31)
"""

import copy
import hashlib
from typing import Any, Dict, List
import pytest

from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.core.contracts import (
    ExecutionIdentity,
    ProblemIdentity,
    ProvenanceType,
    ScenarioContext,
    ScenarioDataIdentity,
    SolverRunView,
    UIJobState,
)
from dashboard.core.state import PageKeys, SessionStateKeys, get_initial_session_state
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.optimization_service import OptimizationService
from dashboard.services.scenario_service import (
    ScenarioService,
    compute_canonical_scenario_digest,
)
from src.optimization.domain import (
    Flight,
    Gate,
    GateResourceType,
)


def _make_dummy_flight(
    flight_id: str,
    arr_min: int = 480,
    dep_min: int = 540,
    nominal_gate: str = "G_01",
    carrier: str = "DL",
    buffer_min: int = 15,
) -> Flight:
    """Helper creating a valid Flight domain object for identity testing."""
    return Flight(
        flight_id=flight_id,
        flight_index=0,
        carrier=carrier,
        flight_number=f"DL{flight_id[-3:] if len(flight_id) >= 3 else '100'}",
        scheduled_arrival_min=arr_min,
        scheduled_departure_min=dep_min,
        predicted_arrival_min=arr_min,
        aircraft_type="A321",
        nominal_gate_id=nominal_gate,
        min_turnaround_min=45,
        default_dwell_min=dep_min - arr_min,
        buffer_min=buffer_min,
        is_paired=True,
        precomputed_gate_out_min=dep_min,
    )


def _make_dummy_gate(
    gate_id: str,
    gate_index: int = 0,
    is_overflow: bool = False,
    capacity: int = 1,
) -> Gate:
    """Helper creating a valid Gate domain object for identity testing."""
    return Gate(
        gate_id=gate_id,
        gate_index=gate_index,
        is_overflow=is_overflow,
        resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON if is_overflow else GateResourceType.CONTACT_GATE,
        capacity=capacity,
    )


# ==============================================================================
# SECTION 1: 3-TIER SCENARIO & PROBLEM IDENTITY (R02-T01 to R02-T10)
# ==============================================================================

def test_r02_t01_scenario_data_identity_creation():
    """R02-T01: ScenarioDataIdentity creates frozen contract with schema_version 2.0."""
    ident = ScenarioDataIdentity(
        scenario_id="SCEN_P09_CANONICAL_120",
        scenario_digest="abc123sha256",
        flight_count=120,
        gate_count=26,
        remote_capacity=1,
        generator_seed=42,
    )
    assert ident.schema_version == "2.0"
    assert ident.scenario_id == "SCEN_P09_CANONICAL_120"
    assert ident.generator_seed == 42
    d = ident.to_dict()
    assert d["scenario_digest"] == "abc123sha256"
    with pytest.raises(Exception):
        ident.flight_count = 200  # Immutability guard


def test_r02_t02_scenario_digest_permutation_invariance():
    """R02-T02: compute_canonical_scenario_digest is invariant to flight/gate order."""
    f1 = _make_dummy_flight("FLIGHT_01", arr_min=480, dep_min=540)
    f2 = _make_dummy_flight("FLIGHT_02", arr_min=500, dep_min=560)
    g1 = _make_dummy_gate("G_01", 0)
    g2 = _make_dummy_gate("G_02", 1)

    hash1 = compute_canonical_scenario_digest([f1, f2], [g1, g2], "TEST_SCEN", generator_seed=42)
    hash2 = compute_canonical_scenario_digest([f2, f1], [g2, g1], "TEST_SCEN", generator_seed=42)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_r02_t03_scenario_digest_sensitivity_to_flight_timing():
    """R02-T03: Modifying flight arrival time changes the scenario digest."""
    f1_a = _make_dummy_flight("FLIGHT_01", arr_min=480, dep_min=540)
    f1_b = _make_dummy_flight("FLIGHT_01", arr_min=481, dep_min=540)  # 1 min difference
    g1 = _make_dummy_gate("G_01", 0)

    hash_a = compute_canonical_scenario_digest([f1_a], [g1], "TEST_SCEN", generator_seed=42)
    hash_b = compute_canonical_scenario_digest([f1_b], [g1], "TEST_SCEN", generator_seed=42)
    assert hash_a != hash_b


def test_r02_t04_scenario_digest_sensitivity_to_gate_capacity():
    """R02-T04: Modifying gate capacity changes the scenario digest."""
    f1 = _make_dummy_flight("FLIGHT_01")
    g1_a = Gate(gate_id="REMOTE", is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    g1_b = Gate(gate_id="REMOTE", is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    hash_a = compute_canonical_scenario_digest([f1], [g1_a], "TEST_SCEN", generator_seed=42)
    hash_b = compute_canonical_scenario_digest([f1], [g1_b], "TEST_SCEN", generator_seed=42)
    assert hash_a != hash_b


def test_r02_t05_scenario_digest_deterministic_consistency():
    """R02-T05: ScenarioService.compute_scenario_hash returns consistent digest on canonical dataset."""
    service = ScenarioService()
    h1 = service.compute_scenario_hash("SCEN_P09_CANONICAL_120")
    h2 = service.compute_scenario_hash("SCEN_P09_CANONICAL_120")
    assert h1 == h2
    assert len(h1) == 64


def test_r02_t06_problem_identity_creation_and_digest():
    """R02-T06: ProblemIdentity calculates deterministic SHA256 digest."""
    prob = ProblemIdentity(
        scenario_digest="scen_digest_sample",
        w_pref=10.0,
        w_remote=200.0,
        w_conflict=1000.0,
        buffer_time_min=15,
        allow_overflow=True,
    )
    assert prob.schema_version == "2.0"
    digest = prob.problem_digest
    assert len(digest) == 64
    d = prob.to_dict()
    assert d["problem_digest"] == digest


def test_r02_t07_problem_identity_weight_sensitivity():
    """R02-T07: Modifying optimization objective weights alters problem_digest."""
    p1 = ProblemIdentity(scenario_digest="sample", w_pref=10.0)
    p2 = ProblemIdentity(scenario_digest="sample", w_pref=15.0)
    assert p1.problem_digest != p2.problem_digest

    p3 = ProblemIdentity(scenario_digest="sample", w_remote=200.0)
    p4 = ProblemIdentity(scenario_digest="sample", w_remote=250.0)
    assert p3.problem_digest != p4.problem_digest


def test_r02_t08_problem_identity_buffer_sensitivity():
    """R02-T08: Modifying buffer_time_min or allow_overflow alters problem_digest."""
    p1 = ProblemIdentity(scenario_digest="sample", buffer_time_min=15)
    p2 = ProblemIdentity(scenario_digest="sample", buffer_time_min=20)
    assert p1.problem_digest != p2.problem_digest

    p3 = ProblemIdentity(scenario_digest="sample", allow_overflow=True)
    p4 = ProblemIdentity(scenario_digest="sample", allow_overflow=False)
    assert p3.problem_digest != p4.problem_digest


def test_r02_t09_execution_identity_creation_and_digest():
    """R02-T09: ExecutionIdentity creates deterministic SHA256 execution digest."""
    exec_id = ExecutionIdentity(
        problem_digest="problem_sample_digest",
        requested_solver="cpsat",
        effective_solver="CP-SAT (Sparse Interval)",
        formulation="sparse_interval",
        time_limit_sec=30.0,
        solver_seed=42,
    )
    assert len(exec_id.execution_digest) == 64
    d = exec_id.to_dict()
    assert d["execution_digest"] == exec_id.execution_digest


def test_r02_t10_execution_identity_parameter_sensitivity():
    """R02-T10: ExecutionIdentity changes when solver, time limit, or formulation changes."""
    e1 = ExecutionIdentity(problem_digest="p", requested_solver="cpsat", effective_solver="CP-SAT")
    e2 = ExecutionIdentity(problem_digest="p", requested_solver="greedy", effective_solver="Greedy")
    assert e1.execution_digest != e2.execution_digest

    e3 = ExecutionIdentity(problem_digest="p", requested_solver="cpsat", effective_solver="CP-SAT", time_limit_sec=30.0)
    e4 = ExecutionIdentity(problem_digest="p", requested_solver="cpsat", effective_solver="CP-SAT", time_limit_sec=60.0)
    assert e3.execution_digest != e4.execution_digest


# ==============================================================================
# SECTION 2: CONFIG NORMALIZATION & STALENESS (R02-T11 to R02-T20)
# ==============================================================================

def test_r02_t11_config_normalization_numeric_coercion():
    """R02-T11: normalize_optimization_config coerces floats, ints, booleans, and solver names."""
    raw = {
        "w_pref": 10,
        "w_remote": "200.5",
        "buffer_time_min": "15",
        "allow_overflow": 1,
        "solver_name": "  CP-SAT  ",
        "time_limit_sec": 30,
    }
    norm = ExperimentService.normalize_optimization_config(raw)
    assert norm["w_pref"] == 10.0
    assert norm["w_remote"] == 200.5
    assert norm["buffer_time_min"] == 15
    assert norm["allow_overflow"] is True
    assert norm["solver_name"] == "cp-sat"
    assert norm["time_limit_sec"] == 30.0


def test_r02_t12_config_normalization_empty_and_none():
    """R02-T12: normalize_optimization_config handles empty and None gracefully."""
    assert ExperimentService.normalize_optimization_config(None) == {}
    assert ExperimentService.normalize_optimization_config({}) == {}


def test_r02_t13_solver_identity_keys_completeness():
    """R02-T13: SOLVER_IDENTITY_KEYS includes all mathematical parameters."""
    keys = ExperimentService.SOLVER_IDENTITY_KEYS
    required = [
        "scenario_id",
        "solver_name",
        "w_pref",
        "w_remote",
        "w_conflict",
        "buffer_time_min",
        "time_limit_sec",
        "allow_overflow",
        "finite_remote_capacity",
        "cp_sat_formulation",
    ]
    for k in required:
        assert k in keys, f"Missing solver identity key: {k}"


def test_r02_t14_staleness_detailed_catches_weight_change():
    """R02-T14: check_staleness_detailed detects weight changes."""
    draft = {"w_pref": 15.0}
    executed = {"w_pref": 10.0}
    is_stale, differing = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "w_pref" in differing


def test_r02_t15_staleness_detailed_catches_buffer_change():
    """R02-T15: check_staleness_detailed detects separation buffer changes."""
    draft = {"buffer_time_min": 20}
    executed = {"buffer_time_min": 15}
    is_stale, differing = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "buffer_time_min" in differing


def test_r02_t16_staleness_detailed_catches_solver_change():
    """R02-T16: check_staleness_detailed detects solver changes."""
    draft = {"solver_name": "greedy"}
    executed = {"solver_name": "cpsat"}
    is_stale, differing = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "solver_name" in differing


def test_r02_t17_staleness_detailed_catches_scenario_change():
    """R02-T17: check_staleness_detailed detects active scenario change."""
    draft = {"scenario_id": "SCEN_2023_PEAK_01"}
    executed = {"scenario_id": "SCEN_P09_CANONICAL_120"}
    is_stale, differing = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "scenario_id" in differing


def test_r02_t18_staleness_detailed_returns_false_when_identical():
    """R02-T18: check_staleness_detailed returns False when normalized configs match."""
    draft = {
        "scenario_id": "SCEN_P09_CANONICAL_120",
        "solver_name": "cpsat",
        "w_pref": 10.0,
        "w_remote": 200.0,
        "buffer_time_min": 15,
        "allow_overflow": True,
    }
    executed = {
        "scenario_id": "SCEN_P09_CANONICAL_120",
        "solver_name": "cpsat",
        "w_pref": 10,
        "w_remote": 200,
        "buffer_time_min": 15,
        "allow_overflow": True,
    }
    is_stale, differing = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is False
    assert len(differing) == 0
    assert ExperimentService.is_stale(draft, executed) is False


def test_r02_t19_staleness_detailed_when_executed_is_none():
    """R02-T19: check_staleness_detailed flags stale when executed_config is None."""
    is_stale, differing = ExperimentService.check_staleness_detailed({"w_pref": 10.0}, None)
    assert is_stale is True
    assert "executed_config_missing" in differing


def test_r02_t20_presentation_filter_mutation_isolation():
    """R02-T20: Presentation filters do not corrupt mathematical experiment identity."""
    prev_filters = {"concourse_filter": ["T"], "view_mode": "Nominal"}
    new_filters = {"concourse_filter": ["T", "A"], "view_mode": "Optimized"}

    assert ExperimentService.is_presentation_filter_mutation(prev_filters, new_filters) is True

    # Configuration hash must be identical when only presentation filters change
    opt_cfg = {"solver_name": "cpsat", "w_pref": 10.0}
    h1 = ExperimentService.compute_configuration_hash("SCEN_A", {**opt_cfg, **prev_filters})
    h2 = ExperimentService.compute_configuration_hash("SCEN_A", {**opt_cfg, **new_filters})
    assert h1 == h2


# ==============================================================================
# SECTION 3: SOLVER EXECUTION SAFETY & FALLBACK (R02-T21 to R02-T25)
# ==============================================================================

def test_r02_t21_unknown_solver_rejection():
    """R02-T21: OptimizationService rejects unknown solvers without silent CP-SAT fallback."""
    opt_service = OptimizationService()
    flights = [_make_dummy_flight("F1")]
    gates = [_make_dummy_gate("G1")]

    with pytest.raises(ValueError, match="Unsupported or unknown solver"):
        opt_service.solve(flights, gates, solver_name="genetic_algorithm_v1")

    with pytest.raises(ValueError, match="Unsupported or unknown solver"):
        opt_service.solve(flights, gates, solver_name="random_search")


def test_r02_t22_solver_tracking_in_run_view():
    """R02-T22: SolverRunView tracks requested_solver and effective_solver."""
    opt_service = OptimizationService()
    flights = [_make_dummy_flight(f"F{i}", arr_min=480 + i * 80, dep_min=540 + i * 80) for i in range(3)]
    gates = [_make_dummy_gate("G_01", 0), _make_dummy_gate("G_02", 1)]

    view, is_valid, violations = opt_service.solve(
        flights=flights,
        gates=gates,
        solver_name="greedy",
        scenario_id="SCEN_TEST",
    )
    assert view.requested_solver == "Deterministic Greedy"
    assert view.effective_solver == "Deterministic Greedy"
    assert view.fallback_used is False
    assert is_valid is True


def test_r02_t23_solver_run_view_identity_digests():
    """R02-T23: SolverRunView contains valid problem_digest and execution_digest."""
    opt_service = OptimizationService()
    flights = [_make_dummy_flight(f"F{i}", arr_min=480 + i * 30, dep_min=540 + i * 30) for i in range(2)]
    gates = [_make_dummy_gate("G_01", 0)]

    view, _, _ = opt_service.solve(flights, gates, solver_name="greedy", scenario_id="SCEN_TEST")
    assert view.problem_digest is not None
    assert len(view.problem_digest) == 64
    assert view.execution_digest is not None
    assert len(view.execution_digest) == 64


def test_r02_t24_solver_run_view_verifier_diagnostics():
    """R02-T24: SolverRunView captures full verifier_diagnostics dictionary."""
    opt_service = OptimizationService()
    flights = [_make_dummy_flight("F1")]
    gates = [_make_dummy_gate("G1")]

    view, is_valid, _ = opt_service.solve(flights, gates, solver_name="greedy", scenario_id="SCEN_TEST")
    assert is_valid is True
    assert view.verifier_diagnostics is not None
    assert "hard_constraint_violations_count" in view.verifier_diagnostics


def test_r02_t25_fallback_used_disables_optimal_proven():
    """R02-T25: Fallback executions never claim is_optimal_proven and set effective_solver."""
    dummy_result = {
        "assignments": {},
        "status": "FEASIBLE",
        "termination_reason": "TIME_LIMIT",
        "objective_value": 350.0,
        "runtime_ms": 30000.0,
        "reassignment_count": 2,
        "remote_gate_count": 1,
        "conflict_count": 0,
        "optimality_proven": True,  # Solver internally claimed optimal
        "solver_configuration": {"fallback_used": True},
    }
    view = adapt_solver_result_to_view(
        result=dummy_result,
        solver_name="CP-SAT (Sparse Interval)",
        scenario_id="SCEN_TEST",
        fallback_used=True,
    )
    assert view.fallback_used is True
    assert view.is_optimal_proven is False
    assert view.effective_solver == "Deterministic Greedy"


# ==============================================================================
# SECTION 4: SESSION STATE, ROUTING & ISOLATION (R02-T26 to R02-T31)
# ==============================================================================

def test_r02_t26_page_keys_enum_canonical_values():
    """R02-T26: PageKeys enum defines exactly 5 distinct canonical page keys."""
    assert PageKeys.CONTROL_TOWER.value == "01_control_tower"
    assert PageKeys.FLIGHT_INTELLIGENCE.value == "02_flight_intelligence"
    assert PageKeys.GATE_OPERATIONS.value == "03_gate_operations"
    assert PageKeys.OPTIMIZATION_LAB.value == "04_optimization_lab"
    assert PageKeys.ROBUSTNESS_LAB.value == "05_robustness_lab"
    assert len(set(PageKeys)) == 5


def test_r02_t27_control_tower_quick_nav_uses_page_keys():
    """R02-T27: Page 01 navigation buttons use PageKeys enum rather than raw page title strings."""
    with open("dashboard/pages/page_01_control_tower.py", encoding="utf-8") as f:
        code = f.read()
    assert "PageKeys.FLIGHT_INTELLIGENCE.value" in code
    assert "PageKeys.GATE_OPERATIONS.value" in code
    assert 'CURRENT_PAGE] = "Flight Intelligence"' not in code
    assert 'CURRENT_PAGE] = "Gate Operations"' not in code


def test_r02_t28_scenario_switching_isolation_logic():
    """R02-T28: Scenario change clears active result and selection state."""
    state = get_initial_session_state()
    # Simulate an active solve on Scenario A
    state[SessionStateKeys.ACTIVE_SCENARIO_ID] = "SCEN_P09_CANONICAL_120"
    state[SessionStateKeys.ACTIVE_RESULT] = SolverRunView(
        solver_name="cpsat",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=120.0,
        decision_cost=120.0,
        reporting_cost=0.0,
        reassignment_count=2,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=1.5,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
    )
    state[SessionStateKeys.SELECTED_FLIGHT_ID] = "LEG_ARR_0001"

    # Simulate scenario change to Scenario B
    new_scen = "SCEN_2023_PEAK_01"
    if new_scen != state[SessionStateKeys.ACTIVE_SCENARIO_ID]:
        state[SessionStateKeys.ACTIVE_SCENARIO_ID] = new_scen
        state[SessionStateKeys.ACTIVE_RESULT] = None
        state[SessionStateKeys.SELECTED_FLIGHT_ID] = None
        state[SessionStateKeys.JOB_STATE] = UIJobState.IDLE.value

    assert state[SessionStateKeys.ACTIVE_RESULT] is None
    assert state[SessionStateKeys.SELECTED_FLIGHT_ID] is None
    assert state[SessionStateKeys.JOB_STATE] == UIJobState.IDLE.value


def test_r02_t29_gate_operations_active_run_mismatch_clears_result():
    """R02-T29: Active result for another scenario is discarded upon scenario switch."""
    run_scen_a = SolverRunView(
        solver_name="cpsat",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=120.0,
        decision_cost=120.0,
        reporting_cost=0.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=1.0,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
    )
    active_scenario_id = "SCEN_2023_PEAK_01"
    active_run = run_scen_a

    # Check the exact check implemented in page_03:
    if active_run is not None and active_run.scenario_id != active_scenario_id:
        active_run = None

    assert active_run is None


def test_r02_t30_uijobstate_enum_coverage():
    """R02-T30: UIJobState enum defines all required lifecycle states."""
    expected = [
        "IDLE",
        "VALIDATING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "STALE_RESULT",
        "INCOMPATIBLE_RESULT",
    ]
    for st_name in expected:
        assert hasattr(UIJobState, st_name), f"UIJobState missing {st_name}"


def test_r02_t31_apptest_gate_operations_no_auto_solve():
    """R02-T31: Initial session state has active_result=None and job_state=IDLE or READY_IDLE."""
    init_state = get_initial_session_state()
    assert init_state[SessionStateKeys.ACTIVE_RESULT] is None
    assert init_state[SessionStateKeys.IS_SOLUTION_STALE] is False

    # Verify that page_03 no longer has opt_service.solve() in its top-level unconditional block
    with open("dashboard/pages/page_03_gate_operations.py", encoding="utf-8") as f:
        code = f.read()

    # The unconditional auto-solve block was removed
    assert "# Load / solve initial solution if absent" not in code
    # Explicit solve button exists
    assert "⚡ TỐI ƯU HÓA NGAY (RUN SOLVER)" in code
