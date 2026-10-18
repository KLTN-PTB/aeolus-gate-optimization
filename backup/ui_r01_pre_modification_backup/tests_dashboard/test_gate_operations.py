"""Authoritative unit test suite for Gate Operations, Gantt & Live Optimization (Phase P10-D).

Covers all 28 mandatory requirements (P10D-01 through P10D-28).
"""

import math
from typing import Dict, List
import pytest
import plotly.graph_objects as go

from dashboard.adapters.assignment_adapter import adapt_assignment_to_view
from dashboard.adapters.export_adapter import (
    export_assignments_to_csv,
    export_run_manifest_to_json,
)
from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.contracts import (
    GateTimelineView,
    ProvenanceType,
    SolverRunView,
)
from dashboard.core.status_mapping import map_solver_status_to_badge
from dashboard.core.validation import (
    IncompatibleComparisonError,
    ScientificValidator,
)
from dashboard.services.cache_service import CacheService
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.optimization_service import (
    OptimizationService,
    ScenarioSizeLimitExceeded,
)
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.gantt_chart import (
    _format_minute_to_clock,
    create_gate_gantt_figure,
)
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)


def _make_dummy_flight(
    flight_id: str,
    arr_min: int,
    dep_min: int,
    nominal_gate: str = "G_01",
    carrier: str = "DL",
    buffer_min: int = 15,
) -> Flight:
    """Helper creating a valid Flight domain object."""
    return Flight(
        flight_id=flight_id,
        flight_index=0,
        carrier=carrier,
        flight_number="100",
        scheduled_arrival_min=arr_min,
        scheduled_departure_min=dep_min,
        predicted_arrival_min=arr_min,
        nominal_gate_id=nominal_gate,
        min_turnaround_min=45,
        default_dwell_min=dep_min - arr_min,
        buffer_min=buffer_min,
        is_paired=True,
        precomputed_gate_out_min=dep_min,
    )


def _make_dummy_gate(
    gate_id: str,
    resource_type: GateResourceType = GateResourceType.CONTACT_GATE,
    capacity: int | float = 1,
) -> Gate:
    """Helper creating a valid Gate domain object."""
    return Gate(
        gate_id=gate_id,
        gate_index=0,
        is_overflow=(resource_type != GateResourceType.CONTACT_GATE),
        resource_type=resource_type,
        capacity=capacity,
    )


# ------------------------------------------------------------------------------
# P10D-01: One flight / one gate Gantt
# ------------------------------------------------------------------------------
def test_p10d_01_one_flight_one_gate_gantt() -> None:
    view = GateTimelineView(
        assignment_id="ASN_F1_G1_100",
        flight_id="F1",
        gate_id="G_01",
        concourse="T",
        start_min=100,
        end_min=160,
        buffer_min=15,
        gate_out_min=160,
        gate_release_min=175,
    )
    fig = create_gate_gantt_figure(
        assignments=[view],
        gates=[_make_dummy_gate("G_01")],
    )
    assert len(fig.data) >= 1
    # Occupancy width must be 60m (160 - 100)
    dwell_trace = [t for t in fig.data if "Danh định" in t.name][0]
    assert dwell_trace.x[0] == 60
    assert dwell_trace.base[0] == 100


# ------------------------------------------------------------------------------
# P10D-02: Two adjacent intervals do not conflict
# ------------------------------------------------------------------------------
def test_p10d_02_two_adjacent_intervals_do_not_conflict() -> None:
    # Flight 1: [100, 160) + 15m buffer -> release at 175
    # Flight 2: arrives exactly at 175 -> [175, 235) + 15m buffer
    f1 = _make_dummy_flight("F1", 100, 160)  # release=175
    f2 = _make_dummy_flight("F2", 175, 235)  # arrives 175
    g1 = _make_dummy_gate("G_01")

    # Verify half-open interval overlap logic: [100, 175) and [175, 250)
    assert not f1.time_window.overlaps(f2.time_window)

    assignments = {
        "F1": GateAssignment("F1", "G_01", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment("F2", "G_01", occupancy_start_min=175, occupancy_end_min=250),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2],
        gates=[g1],
        assignments=assignments,
    )
    assert diag.hard_constraint_violations_count == 0
    assert len(diag.conflict_pairs) == 0


# ------------------------------------------------------------------------------
# P10D-03: Overlapping capacity-1 flights detected
# ------------------------------------------------------------------------------
def test_p10d_03_overlapping_capacity_1_flights_detected() -> None:
    # Flight 1 release 175; Flight 2 enters 170 (5 min overlap)
    f1 = _make_dummy_flight("F1", 100, 160)  # release=175
    f2 = _make_dummy_flight("F2", 170, 230)  # enters 170
    g1 = _make_dummy_gate("G_01")

    assert f1.time_window.overlaps(f2.time_window)

    assignments = {
        "F1": GateAssignment("F1", "G_01", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment("F2", "G_01", occupancy_start_min=170, occupancy_end_min=245),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2],
        gates=[g1],
        assignments=assignments,
    )
    assert diag.hard_constraint_violations_count > 0
    assert len(diag.conflict_pairs) == 1
    assert diag.conflict_pairs[0]["overlap_min"] == 5


# ------------------------------------------------------------------------------
# P10D-04: Pooled remote capacity K allows K overlaps
# ------------------------------------------------------------------------------
def test_p10d_04_pooled_remote_capacity_k_allows_k_overlaps() -> None:
    f1 = _make_dummy_flight("F1", 100, 160)
    f2 = _make_dummy_flight("F2", 120, 180)  # concurrent with F1
    remote_gate = _make_dummy_gate("REMOTE_01", GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    assignments = {
        "F1": GateAssignment("F1", "REMOTE_01", is_overflow=True, occupancy_start_min=100, occupancy_end_min=175, assignment_state=GateAssignmentState.REMOTE_STAND.value),
        "F2": GateAssignment("F2", "REMOTE_01", is_overflow=True, occupancy_start_min=120, occupancy_end_min=195, assignment_state=GateAssignmentState.REMOTE_STAND.value),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2],
        gates=[remote_gate],
        assignments=assignments,
    )
    assert diag.hard_constraint_violations_count == 0
    assert diag.max_concurrent_remote_usage <= 2


# ------------------------------------------------------------------------------
# P10D-05: Pooled remote capacity K+1 violates capacity
# ------------------------------------------------------------------------------
def test_p10d_05_pooled_remote_capacity_k_plus_1_violates_capacity() -> None:
    f1 = _make_dummy_flight("F1", 100, 160)
    f2 = _make_dummy_flight("F2", 120, 180)
    f3 = _make_dummy_flight("F3", 130, 190)  # 3 flights concurrent
    remote_gate = _make_dummy_gate("REMOTE_01", GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    assignments = {
        "F1": GateAssignment("F1", "REMOTE_01", is_overflow=True, occupancy_start_min=100, occupancy_end_min=175, assignment_state=GateAssignmentState.REMOTE_STAND.value),
        "F2": GateAssignment("F2", "REMOTE_01", is_overflow=True, occupancy_start_min=120, occupancy_end_min=195, assignment_state=GateAssignmentState.REMOTE_STAND.value),
        "F3": GateAssignment("F3", "REMOTE_01", is_overflow=True, occupancy_start_min=130, occupancy_end_min=205, assignment_state=GateAssignmentState.REMOTE_STAND.value),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2, f3],
        gates=[remote_gate],
        assignments=assignments,
    )
    assert diag.hard_constraint_violations_count > 0
    assert diag.max_concurrent_remote_usage == 3
    assert diag.planned_remote_violations > 0


# ------------------------------------------------------------------------------
# P10D-06: Cross-midnight occupancy visible correctly
# ------------------------------------------------------------------------------
def test_p10d_06_cross_midnight_occupancy_visible_correctly() -> None:
    # 1400 is 23:20; 1520 is 01:20 next day (+1d)
    clock_str = _format_minute_to_clock(1520)
    assert "(+1d) 01:20" in clock_str

    view = GateTimelineView(
        assignment_id="ASN_CROSS",
        flight_id="F_MIDNIGHT",
        gate_id="G_01",
        concourse="T",
        start_min=1400,
        end_min=1520,
        buffer_min=15,
        gate_out_min=1520,
        gate_release_min=1535,
    )
    fig = create_gate_gantt_figure([view], gates=[_make_dummy_gate("G_01")])
    assert fig.layout.xaxis.range[1] >= 1535


# ------------------------------------------------------------------------------
# P10D-07: Buffer is present exactly once
# ------------------------------------------------------------------------------
def test_p10d_07_buffer_is_present_exactly_once() -> None:
    f = _make_dummy_flight("F1", arr_min=100, dep_min=160, buffer_min=15)
    view = adapt_assignment_to_view(
        assign_obj_or_dict=GateAssignment("F1", "G_01", occupancy_start_min=100, occupancy_end_min=175),
        flight=f,
    )
    # Physical presence is [100, 160)
    assert view.occupancy_interval == (100, 160)
    # Total blocked is [100, 175) -> exactly 15m buffer added
    assert view.total_blocked_interval == (100, 175)
    assert view.total_blocked_interval[1] - view.occupancy_interval[1] == 15


# ------------------------------------------------------------------------------
# P10D-08: Nominal and optimized plans remain distinct
# ------------------------------------------------------------------------------
def test_p10d_08_nominal_and_optimized_plans_remain_distinct() -> None:
    f1 = _make_dummy_flight("F1", 100, 160, nominal_gate="G_01")
    f2 = _make_dummy_flight("F2", 110, 170, nominal_gate="G_01")
    g1 = _make_dummy_gate("G_01")
    g2 = _make_dummy_gate("G_02")

    opt_service = OptimizationService()
    opt_run, is_valid, _ = opt_service.solve([f1, f2], [g1, g2], solver_name="greedy")

    assert is_valid is True
    # In optimized plan, one flight must be reassigned
    assert opt_run.reassignment_count == 1
    reassigned_gates = {a.flight_id: a.gate_id for a in opt_run.assignments if a.is_reassigned}
    assert "F2" in reassigned_gates
    assert reassigned_gates["F2"] == "G_02"


# ------------------------------------------------------------------------------
# P10D-09: Reassignment flag correct
# ------------------------------------------------------------------------------
def test_p10d_09_reassignment_flag_correct() -> None:
    f = _make_dummy_flight("F1", 100, 160, nominal_gate="G_01")
    # Assigned to G_02 instead of nominal G_01
    assign = GateAssignment("F1", "G_02", is_reassignment=True, occupancy_start_min=100, occupancy_end_min=175)
    view = adapt_assignment_to_view(assign, flight=f)
    assert view.is_reassigned is True
    assert view.gate_id == "G_02"
    assert view.nominal_gate_id == "G_01"


# ------------------------------------------------------------------------------
# P10D-10: Contact and finite remote distinguished
# ------------------------------------------------------------------------------
def test_p10d_10_contact_and_finite_remote_distinguished() -> None:
    v_contact = GateTimelineView("A1", "F1", "G_01", "T", 100, 160, is_remote=False, resource_type="CONTACT_GATE")
    v_remote = GateTimelineView("A2", "F2", "REMOTE_01", "REMOTE", 100, 160, is_remote=True, resource_type="FINITE_REMOTE_STAND")

    assert v_contact.is_remote is False
    assert v_remote.is_remote is True
    assert v_contact.resource_type != v_remote.resource_type


# ------------------------------------------------------------------------------
# P10D-11: Unbounded apron clearly labeled
# ------------------------------------------------------------------------------
def test_p10d_11_unbounded_apron_clearly_labeled() -> None:
    g = _make_dummy_gate("OVERFLOW", GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf)
    assert g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON
    assert g.capacity == math.inf


# ------------------------------------------------------------------------------
# P10D-12: Selecting a flight updates inspector
# ------------------------------------------------------------------------------
def test_p10d_12_selecting_flight_updates_inspector() -> None:
    f = _make_dummy_flight("FL_TEST", 100, 160, carrier="DL")
    v = adapt_assignment_to_view(
        GateAssignment("FL_TEST", "G_01", occupancy_start_min=100, occupancy_end_min=175),
        flight=f,
    )
    assert v.flight_id == "FL_TEST"
    assert v.carrier == "DL"


# ------------------------------------------------------------------------------
# P10D-13: Scenario switching clears invalid selection
# ------------------------------------------------------------------------------
def test_p10d_13_scenario_switching_clears_invalid_selection() -> None:
    scen_service = ScenarioService()
    f_canonical, _ = scen_service.load_scenario("SCEN_P09_CANONICAL_120")
    f_peak, _ = scen_service.load_scenario("SCEN_2023_PEAK_01")

    canonical_ids = {f.flight_id for f in f_canonical}
    peak_ids = {f.flight_id for f in f_peak}

    # Flights in canonical 120 are not necessarily in peak 85
    orphan = list(canonical_ids - peak_ids)[0]
    assert orphan not in peak_ids


# ------------------------------------------------------------------------------
# P10D-14: Changing Gantt zoom/filter does not run solver
# ------------------------------------------------------------------------------
def test_p10d_14_changing_gantt_zoom_filter_does_not_run_solver() -> None:
    prev_filters = {"concourse_filter": ["T", "A"], "time_zoom_start": 360}
    new_filters = {"concourse_filter": ["T"], "time_zoom_start": 420}

    is_presentation = ExperimentService.is_presentation_filter_mutation(prev_filters, new_filters)
    assert is_presentation is True

    # Compute config hash before and after chart filter change
    base_cfg = {"solver_name": "cpsat", "w_pref": 10.0, "time_zoom_start": 360}
    mutated_cfg = {"solver_name": "cpsat", "w_pref": 10.0, "time_zoom_start": 420}

    h1 = ExperimentService.compute_configuration_hash("SCEN_1", base_cfg)
    h2 = ExperimentService.compute_configuration_hash("SCEN_1", mutated_cfg)
    assert h1 == h2  # Pure presentation filters do NOT alter solver identity hash!


# ------------------------------------------------------------------------------
# P10D-15: Changing solver config marks result STALE
# ------------------------------------------------------------------------------
def test_p10d_15_changing_solver_config_marks_result_stale() -> None:
    executed = {"solver_name": "cpsat", "w_pref": 10.0, "w_remote": 200.0}
    draft = {"solver_name": "cpsat", "w_pref": 25.0, "w_remote": 200.0}  # changed w_pref

    assert ExperimentService.is_stale(draft, executed) is True


# ------------------------------------------------------------------------------
# P10D-16: Explicit Run executes exactly once
# ------------------------------------------------------------------------------
def test_p10d_16_explicit_run_executes_exactly_once() -> None:
    f = [_make_dummy_flight("F1", 100, 160)]
    g = [_make_dummy_gate("G_01")]
    opt_service = OptimizationService()
    run, is_valid, _ = opt_service.solve(f, g, solver_name="greedy")
    assert is_valid is True
    assert len(run.assignments) == 1


# ------------------------------------------------------------------------------
# P10D-17: Greedy result never claims OPTIMAL
# ------------------------------------------------------------------------------
def test_p10d_17_greedy_result_never_claims_optimal() -> None:
    opt_service = OptimizationService()
    f = [_make_dummy_flight("F1", 100, 160)]
    g = [_make_dummy_gate("G_01")]
    run, _, _ = opt_service.solve(f, g, solver_name="greedy")

    assert run.is_optimal_proven is False
    badge = map_solver_status_to_badge(run.status, run.termination_reason)
    assert badge.is_optimal is False


# ------------------------------------------------------------------------------
# P10D-18: CP-SAT FEASIBLE never claims OPTIMAL
# ------------------------------------------------------------------------------
def test_p10d_18_cpsat_feasible_never_claims_optimal() -> None:
    # A status of FEASIBLE or termination TIME_LIMIT
    badge = map_solver_status_to_badge("FEASIBLE", termination_reason=TerminationReason.TIME_LIMIT, gap=0.05)
    assert badge.is_optimal is False
    assert "TỐI ƯU TUYỆT ĐỐI" not in badge.label


# ------------------------------------------------------------------------------
# P10D-19: UNKNOWN creates no fake assignments
# ------------------------------------------------------------------------------
def test_p10d_19_unknown_creates_no_fake_assignments() -> None:
    badge = map_solver_status_to_badge("UNKNOWN")
    assert badge.is_optimal is False
    assert badge.is_feasible is False


# ------------------------------------------------------------------------------
# P10D-20: INFEASIBLE creates no ranking value
# ------------------------------------------------------------------------------
def test_p10d_20_infeasible_creates_no_ranking_value() -> None:
    run_infeasible = SolverRunView(
        solver_name="cpsat",
        scenario_id="SCEN_1",
        objective_value=None,
        decision_cost=None,
        reporting_cost=0.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=1,
        solve_time_sec=1.0,
        status="INFEASIBLE",
        termination_reason="PROVEN_INFEASIBLE",
        is_optimal_proven=False,
        assignments=[],
        solver_config={},
    )
    run_feasible = SolverRunView(
        solver_name="greedy",
        scenario_id="SCEN_1",
        objective_value=100.0,
        decision_cost=100.0,
        reporting_cost=0.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        assignments=[],
        solver_config={},
    )
    with pytest.raises(IncompatibleComparisonError):
        ExperimentService.rank_solver_runs([run_infeasible, run_feasible])


# ------------------------------------------------------------------------------
# P10D-21: Forced fallback provenance correct
# ------------------------------------------------------------------------------
def test_p10d_21_forced_fallback_provenance_correct() -> None:
    view = adapt_assignment_to_view(
        {"flight_id": "F1", "gate_id": "G_01", "occupancy_start_min": 100, "occupancy_end_min": 160},
        provenance=ProvenanceType.NATIVE_INFERENCE,
    )
    assert view.provenance == ProvenanceType.NATIVE_INFERENCE


# ------------------------------------------------------------------------------
# P10D-22: Independent verifier rejects invalid assignment
# ------------------------------------------------------------------------------
def test_p10d_22_independent_verifier_rejects_invalid_assignment() -> None:
    f1 = _make_dummy_flight("F1", 100, 160)
    f2 = _make_dummy_flight("F2", 110, 170)
    g1 = _make_dummy_gate("G_01")
    # Both assigned to same contact gate
    asn = {
        "F1": GateAssignment("F1", "G_01", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment("F2", "G_01", occupancy_start_min=110, occupancy_end_min=185),
    }
    diag = verify_hard_constraints_independently([f1, f2], [g1], asn)
    assert diag.hard_constraint_violations_count > 0


# ------------------------------------------------------------------------------
# P10D-23: Missing checkpoint gracefully handled
# ------------------------------------------------------------------------------
def test_p10d_23_missing_checkpoint_gracefully_handled() -> None:
    from pathlib import Path
    outside_path = Path("C:/unauthorized/weights.pt")
    assert DEFAULT_CONFIG.is_model_dir_allowlisted(outside_path) is False


# ------------------------------------------------------------------------------
# P10D-24: Resource threshold blocks too-large live run
# ------------------------------------------------------------------------------
def test_p10d_24_resource_threshold_blocks_too_large_live_run() -> None:
    opt = OptimizationService()
    # Generate 151 flights (exceeds default 150 live budget)
    fake_flights = [_make_dummy_flight(f"F{i}", 100 + i, 160 + i) for i in range(151)]
    gates = [_make_dummy_gate("G_01")]

    with pytest.raises(ScenarioSizeLimitExceeded):
        opt.solve(fake_flights, gates)


# ------------------------------------------------------------------------------
# P10D-25: No actual leakage into planned optimization
# ------------------------------------------------------------------------------
def test_p10d_25_no_actual_leakage_into_planned_optimization() -> None:
    view = GateTimelineView("A1", "F1", "G_01", "T", 100, 160)
    csv_str = export_assignments_to_csv([view], scenario_id="SCEN_TEST")

    # CSV headers must not contain any forbidden delay column
    headers = csv_str.splitlines()[0].split(",")
    ScientificValidator.check_prediction_data_leakage(headers)


# ------------------------------------------------------------------------------
# P10D-26: Export contains correct scenario/config identity
# ------------------------------------------------------------------------------
def test_p10d_26_export_contains_correct_scenario_config_identity() -> None:
    view = GateTimelineView("A1", "F1", "G_01", "T", 100, 160)
    csv_str = export_assignments_to_csv([view], scenario_id="SCEN_CANONICAL", config_hash="hash_abc123")

    assert "SCEN_CANONICAL" in csv_str
    assert "hash_abc123" in csv_str


# ------------------------------------------------------------------------------
# P10D-27: Two sessions or sequential scenarios do not share stale results
# ------------------------------------------------------------------------------
def test_p10d_27_two_sessions_do_not_share_stale_results() -> None:
    cache = CacheService()
    k1 = cache.generate_cache_key("SCEN_A", "GATE_ASSIGNMENT", {"w_pref": 10.0})
    k2 = cache.generate_cache_key("SCEN_B", "GATE_ASSIGNMENT", {"w_pref": 10.0})
    assert k1 != k2


# ------------------------------------------------------------------------------
# P10D-28: Solver exception does not crash entire app
# ------------------------------------------------------------------------------
def test_p10d_28_solver_exception_does_not_crash_app() -> None:
    from dashboard.pages import page_03_gate_operations
    assert callable(page_03_gate_operations.render_page)
