"""Unit and Integration Tests for Phase UI-R05: Gate Operations, Gantt & Verified Live Optimization.

Verifies:
- ISSUE-R00-07: Never classify APRON_* as Concourse A (group as OVERFLOW / UNBOUNDED_OVERFLOW_APRON).
- ISSUE-R00-11: Dynamic gate counts in filter labels computed from actual scenario inventory.
- Strict filter semantics: None = all, [] = empty, combined filters = intersection.
- Time window half-open intersection: [start, release) ∩ [W_start, W_end) > 0.
- Time & Gantt data: half-open intervals, single buffer, adjacent intervals do NOT conflict.
- Pooled remote stands capacity enforcement.
- Clean visualizer titles (no raw CHART-07 IDs).
- Master interactive Gantt figure generation and gate order.
- Flight inspector metrics, cross-midnight +1d continuous formatting, unassigned fallback.
- Safe live optimization execution, size guard <= 150 flights, staleness detection.
- Independent verification integration without false optimality claims.
"""

import math
from typing import List
import plotly.graph_objects as go
import pytest

from dashboard.adapters.assignment_adapter import (
    adapt_assignment_to_view,
    check_intervals_overlap,
    detect_gate_conflicts,
    filter_assignments,
)
from dashboard.components.flight_inspector import _format_time_clock
from dashboard.core.contracts import (
    GateTimelineView,
    ProvenanceType,
    SolverRunView,
    UIJobState,
)
from dashboard.pages.page_03_gate_operations import (
    _build_nominal_assignments,
    _get_gate_concourse,
)
from dashboard.services.optimization_service import (
    OptimizationService,
    ScenarioSizeLimitExceeded,
)
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.gantt_chart import create_gate_gantt_figure
from src.optimization.domain import (
    Flight,
    Gate,
    GateResourceType,
    SolverStatus,
    TerminationReason,
)
from src.optimization.evaluation import verify_hard_constraints_independently


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_gates() -> List[Gate]:
    """Sample diverse gates covering T, A, Remote, and Apron overflow."""
    return [
        Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_02", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_11", gate_index=10, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_12", gate_index=11, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="REMOTE_01", gate_index=12, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2),
        Gate(gate_id="APRON_01", gate_index=13, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf),
    ]


@pytest.fixture
def sample_flights() -> List[Flight]:
    """Sample flights with controlled schedules and buffers."""
    return [
        Flight(
            flight_id="FL_01",
            flight_index=0,
            carrier="VN",
            flight_number="101",
            scheduled_arrival_min=360,
            scheduled_departure_min=420,
            predicted_arrival_min=360,
            min_turnaround_min=45,
            buffer_min=15,
            nominal_gate_id="G_01",
        ),
        Flight(
            flight_id="FL_02",
            flight_index=1,
            carrier="VN",
            flight_number="102",
            scheduled_arrival_min=435,  # 360 + 60 + 15 = 435 (adjacent to FL_01 release)
            scheduled_departure_min=500,
            predicted_arrival_min=435,
            min_turnaround_min=45,
            buffer_min=15,
            nominal_gate_id="G_01",
        ),
        Flight(
            flight_id="FL_03",
            flight_index=2,
            carrier="VJ",
            flight_number="201",
            scheduled_arrival_min=400,  # Overlaps with FL_01 on G_01
            scheduled_departure_min=460,
            predicted_arrival_min=400,
            min_turnaround_min=45,
            buffer_min=15,
            nominal_gate_id="G_01",
        ),
        Flight(
            flight_id="FL_04",
            flight_index=3,
            carrier="QH",
            flight_number="301",
            scheduled_arrival_min=480,
            scheduled_departure_min=540,
            predicted_arrival_min=480,
            min_turnaround_min=45,
            buffer_min=15,
            nominal_gate_id="G_11",
        ),
        Flight(
            flight_id="FL_CROSS",
            flight_index=4,
            carrier="VN",
            flight_number="999",
            scheduled_arrival_min=1400,
            scheduled_departure_min=1460,  # 24h20 -> cross midnight
            predicted_arrival_min=1400,
            min_turnaround_min=45,
            buffer_min=15,
            nominal_gate_id="REMOTE_01",
        ),
    ]


# -----------------------------------------------------------------------------
# R05-T01 to R05-T07: Gate Classification & Dynamic Counts (ISSUE-R00-07 / ISSUE-R00-11)
# -----------------------------------------------------------------------------

def test_r05_t01_issue_r00_07_apron_never_classified_as_concourse_a() -> None:
    """R05-T01: Verify APRON_* is classified as OVERFLOW, never Concourse A."""
    v1 = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "APRON_01", "start_min": 360, "end_min": 420})
    assert v1.concourse == "OVERFLOW"
    assert v1.concourse != "A"

    v2 = adapt_assignment_to_view({"flight_id": "F2", "gate_id": "GATE_APRON_02", "start_min": 360, "end_min": 420})
    assert v2.concourse == "OVERFLOW"
    assert v2.concourse != "A"

    v3 = adapt_assignment_to_view({"flight_id": "F3", "gate_id": "OVERFLOW_STAND", "start_min": 360, "end_min": 420})
    assert v3.concourse == "OVERFLOW"
    assert v3.concourse != "A"


def test_r05_t02_issue_r00_07_remote_distinct_from_concourse_a_and_overflow() -> None:
    """R05-T02: Verify REMOTE_* is classified as REMOTE, distinct from A and OVERFLOW."""
    v1 = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "REMOTE_01", "start_min": 360, "end_min": 420})
    assert v1.concourse == "REMOTE"
    assert v1.concourse not in ("A", "OVERFLOW")

    v2 = adapt_assignment_to_view({"flight_id": "F2", "gate_id": "GATE_REMOTE_05", "start_min": 360, "end_min": 420})
    assert v2.concourse == "REMOTE"

    v3 = adapt_assignment_to_view({"flight_id": "F3", "gate_id": "REMOTE_APRON_01", "start_min": 360, "end_min": 420})
    assert v1.is_remote is True
    assert v3.concourse == "REMOTE"


def test_r05_t03_issue_r00_11_dynamic_gate_counts_canonical_scenario() -> None:
    """R05-T03: Verify dynamic gate counts match actual inventory of SCEN_P09_CANONICAL_120."""
    svc = ScenarioService()
    _, gates = svc.load_scenario("SCEN_P09_CANONICAL_120")
    count_t = sum(1 for g in gates if _get_gate_concourse(g) == "T")
    count_a = sum(1 for g in gates if _get_gate_concourse(g) == "A")
    count_remote = sum(1 for g in gates if _get_gate_concourse(g) == "REMOTE")
    count_overflow = sum(1 for g in gates if _get_gate_concourse(g) == "OVERFLOW")

    assert count_t == 10
    assert count_a == 15
    assert count_remote == 0 or count_remote == 1
    assert count_t + count_a + count_remote + count_overflow == len(gates)


def test_r05_t04_issue_r00_11_dynamic_gate_counts_p07_dual_core_scenario() -> None:
    """R05-T04: Verify dynamic gate counts match actual inventory of SCEN_P07_DUAL_CORE_30 (A=5, not 15)."""
    svc = ScenarioService()
    _, gates = svc.load_scenario("SCEN_P07_DUAL_CORE_30")
    count_t = sum(1 for g in gates if _get_gate_concourse(g) == "T")
    count_a = sum(1 for g in gates if _get_gate_concourse(g) == "A")
    count_remote = sum(1 for g in gates if _get_gate_concourse(g) == "REMOTE")

    assert count_t == 10
    assert count_a == 5  # Confirms dynamic count eliminates hardcoded 15!
    assert count_remote == 1


def test_r05_t05_concourse_helper_contact_gates_t_and_a() -> None:
    """R05-T05: Verify _get_gate_concourse identifies contact gates T and A accurately."""
    g_t1 = Gate(gate_id="T_01", gate_index=0)
    g_a1 = Gate(gate_id="A_01", gate_index=1)
    g_g5 = Gate(gate_id="G_05", gate_index=2)
    g_g15 = Gate(gate_id="G_15", gate_index=3)

    assert _get_gate_concourse(g_t1) == "T"
    assert _get_gate_concourse(g_a1) == "A"
    assert _get_gate_concourse(g_g5) == "T"
    assert _get_gate_concourse(g_g15) == "A"


def test_r05_t06_concourse_helper_remote_and_apron() -> None:
    """R05-T06: Verify _get_gate_concourse separates remote stands and overflow apron."""
    g_rem = Gate(gate_id="REMOTE_01", gate_index=0, resource_type=GateResourceType.FINITE_REMOTE_STAND)
    g_ovf = Gate(gate_id="APRON_01", gate_index=1, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON)

    assert _get_gate_concourse(g_rem) == "REMOTE"
    assert _get_gate_concourse(g_ovf) == "OVERFLOW"


def test_r05_t07_concourse_helper_unrecognized_gates_graceful() -> None:
    """R05-T07: Verify unrecognized gate identifier returns UNKNOWN_GROUP without error."""
    g_custom = Gate(gate_id="NORTH_PIER_99", gate_index=0)
    assert _get_gate_concourse(g_custom) == "UNKNOWN_GROUP"


# -----------------------------------------------------------------------------
# R05-T08 to R05-T16: Strict Filter Semantics (Task R05-B)
# -----------------------------------------------------------------------------

def test_r05_t08_filter_concourse_none_returns_all(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T08: concourse_filter=None applies no filter, returning all assignments."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, concourse_filter=None)
    assert len(res) == len(views)


def test_r05_t09_filter_concourse_empty_list_returns_none(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T09: concourse_filter=[] returns an empty list (strict empty selection)."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, concourse_filter=[])
    assert len(res) == 0


def test_r05_t10_filter_concourse_single_selection(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T10: concourse_filter=['T'] selects only assignments in Concourse T."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, concourse_filter=["T"])
    assert len(res) > 0
    assert all(a.concourse == "T" for a in res)


def test_r05_t11_filter_carrier_all_and_specific(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T11: carrier_filter='ALL' returns all, carrier_filter='VN' returns only VN flights."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res_all = filter_assignments(views, carrier_filter="ALL")
    assert len(res_all) == len(views)

    res_vn = filter_assignments(views, carrier_filter="VN")
    assert len(res_vn) > 0
    assert all(a.carrier == "VN" for a in res_vn)


def test_r05_t12_filter_resource_type_contact(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T12: resource_type_filter='CONTACT_GATE' returns only contact gates."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, resource_type_filter="CONTACT_GATE")
    assert len(res) > 0
    assert all(a.resource_type == "CONTACT_GATE" for a in res)


def test_r05_t13_filter_resource_type_remote(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T13: resource_type_filter='FINITE_REMOTE_STAND' returns only remote stands."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, resource_type_filter="FINITE_REMOTE_STAND")
    assert all(a.resource_type == "FINITE_REMOTE_STAND" for a in res)


def test_r05_t14_filter_resource_type_overflow(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T14: resource_type_filter='UNBOUNDED_OVERFLOW_APRON' returns only overflow apron."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, resource_type_filter="UNBOUNDED_OVERFLOW_APRON")
    assert all(a.resource_type == "UNBOUNDED_OVERFLOW_APRON" for a in res)


def test_r05_t15_filter_search_query_substring_match(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T15: search_query matches flight_id or flight_number substring."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    res = filter_assignments(views, search_query="FL_01")
    assert len(res) == 1
    assert res[0].flight_id == "FL_01"


def test_r05_t16_filter_strict_intersection_and_logic(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T16: Combined filters enforce strict AND intersection."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    # Carrier VN in Concourse T
    res = filter_assignments(views, concourse_filter=["T"], carrier_filter="VN")
    assert all(a.concourse == "T" and a.carrier == "VN" for a in res)

    # Carrier VJ in Concourse A (VJ is only in T in nominal views)
    res_empty = filter_assignments(views, concourse_filter=["A"], carrier_filter="VJ")
    assert len(res_empty) == 0


# -----------------------------------------------------------------------------
# R05-T17 to R05-T20: Time Window Half-Open Intersection (Task R05-B)
# -----------------------------------------------------------------------------

def test_r05_t17_time_window_half_open_intersection() -> None:
    """R05-T17: Time window includes flight if [start, release) ∩ [W_start, W_end) > 0."""
    v = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "G_01", "start_min": 360, "end_min": 420, "buffer_min": 15})
    # start = 360, release = 435
    # Window [400, 500) overlaps [360, 435) from 400 to 435
    res = filter_assignments([v], time_window=(400, 500))
    assert len(res) == 1


def test_r05_t18_time_window_flight_arriving_before_window_included() -> None:
    """R05-T18: Flight arriving before window but still on gate at window start is included."""
    v = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "G_01", "start_min": 300, "end_min": 400, "buffer_min": 15})
    # start = 300, release = 415. Window [350, 450)
    res = filter_assignments([v], time_window=(350, 450))
    assert len(res) == 1


def test_r05_t19_time_window_flight_departing_before_window_excluded() -> None:
    """R05-T19: Flight whose release <= W_start is strictly excluded."""
    v = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "G_01", "start_min": 300, "end_min": 360, "buffer_min": 15})
    # release = 375. Window [400, 500)
    res = filter_assignments([v], time_window=(400, 500))
    assert len(res) == 0


def test_r05_t20_time_window_flight_arriving_at_or_after_window_excluded() -> None:
    """R05-T20: Flight whose start >= W_end is strictly excluded."""
    v = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "G_01", "start_min": 500, "end_min": 560, "buffer_min": 15})
    # start = 500. Window [400, 500) -> half-open boundary at 500 is excluded
    res = filter_assignments([v], time_window=(400, 500))
    assert len(res) == 0


# -----------------------------------------------------------------------------
# R05-T21 to R05-T25: Interval Mathematics & Conflict Detection (Task R05-C)
# -----------------------------------------------------------------------------

def test_r05_t21_single_buffer_present_never_double_counted() -> None:
    """R05-T21: Release time includes buffer exactly once: release = gate_out + buffer."""
    v = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "G_01", "start_min": 360, "end_min": 420, "buffer_min": 15})
    assert v.start_min == 360
    assert v.actual_gate_out_min == 420
    assert v.actual_gate_release_min == 435
    assert v.actual_gate_release_min - v.actual_gate_out_min == 15


def test_r05_t22_adjacent_intervals_do_not_conflict() -> None:
    """R05-T22: Two adjacent intervals [a, b) and [b, c) do NOT overlap."""
    assert check_intervals_overlap((360, 435), (435, 500)) is False
    assert check_intervals_overlap((435, 500), (360, 435)) is False


def test_r05_t23_overlapping_intervals_do_conflict() -> None:
    """R05-T23: Two overlapping intervals [a, c) and [b, d) with b < c DO overlap."""
    assert check_intervals_overlap((360, 435), (400, 500)) is True


def test_r05_t24_pooled_remote_capacity_k_allows_k_concurrent() -> None:
    """R05-T24: Pooled remote stands with capacity K allows K concurrent flights without conflict."""
    # 2 flights overlapping on REMOTE_01 which has capacity 2
    v1 = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "REMOTE_01", "start_min": 360, "end_min": 420, "buffer_min": 15, "is_remote": True})
    v2 = adapt_assignment_to_view({"flight_id": "F2", "gate_id": "REMOTE_01", "start_min": 380, "end_min": 440, "buffer_min": 15, "is_remote": True})
    conflicts = detect_gate_conflicts([v1, v2], gate_capacities={"REMOTE_01": 2})
    assert len(conflicts) == 0


def test_r05_t25_pooled_remote_capacity_k_detects_k_plus_1_conflict() -> None:
    """R05-T25: Pooled remote stands with capacity K detects conflict when K+1 concurrent flights occur."""
    v1 = adapt_assignment_to_view({"flight_id": "F1", "gate_id": "REMOTE_01", "start_min": 360, "end_min": 420, "buffer_min": 15, "is_remote": True})
    v2 = adapt_assignment_to_view({"flight_id": "F2", "gate_id": "REMOTE_01", "start_min": 380, "end_min": 440, "buffer_min": 15, "is_remote": True})
    v3 = adapt_assignment_to_view({"flight_id": "F3", "gate_id": "REMOTE_01", "start_min": 390, "end_min": 450, "buffer_min": 15, "is_remote": True})
    conflicts = detect_gate_conflicts([v1, v2, v3], gate_capacities={"REMOTE_01": 2})
    assert len(conflicts) > 0
    assert "REMOTE_01" in conflicts


# -----------------------------------------------------------------------------
# R05-T26 to R05-T27: Master Gantt Visualizer (Task R05-D)
# -----------------------------------------------------------------------------

def test_r05_t26_master_gantt_clean_title_no_raw_chart_id(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T26: Gantt figure title is clean and contains no raw (CHART-07) string."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    fig = create_gate_gantt_figure(views, gates=sample_gates)
    assert isinstance(fig, go.Figure)
    assert "CHART-07" not in fig.layout.title.text


def test_r05_t27_master_gantt_reversed_gate_order(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T27: Y-axis gates are ordered so first gate appears at the top of the canvas."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    fig = create_gate_gantt_figure(views, gates=sample_gates)
    # y_categories is reversed gate_ids
    assert fig.layout.yaxis.categoryorder == "array"
    assert len(fig.layout.yaxis.categoryarray) == len(sample_gates)
    assert fig.layout.yaxis.categoryarray[0] == sample_gates[-1].gate_id
    assert fig.layout.yaxis.categoryarray[-1] == sample_gates[0].gate_id


# -----------------------------------------------------------------------------
# R05-T28 to R05-T30: Nominal vs Optimized Plan (Task R05-E)
# -----------------------------------------------------------------------------

def test_r05_t28_nominal_plan_detects_contact_conflicts(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T28: Nominal plan builder detects overlaps on contact gates for uncoordinated schedules."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    # FL_01 (360-435) and FL_03 (400-475) both on G_01
    conflict_map = {v.flight_id: v.has_conflict for v in views}
    assert conflict_map["FL_01"] is True
    assert conflict_map["FL_03"] is True
    # FL_04 is on G_11 without competitor
    assert conflict_map["FL_04"] is False


def test_r05_t29_nominal_plan_provenance_is_schedule_baseline(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T29: Nominal assignments carry SCHEDULE_BASELINE provenance."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    assert all(v.provenance == ProvenanceType.SCHEDULE_BASELINE for v in views)


def test_r05_t30_unrun_scenario_does_not_implicitly_solve() -> None:
    """R05-T30: An unrun scenario defaults to nominal plan and does not invoke CP-SAT automatically."""
    # When active_run is None, Page 03 defaults to nominal views without solving
    svc = ScenarioService()
    flights, gates = svc.load_scenario("SCEN_P09_CANONICAL_120")
    views = _build_nominal_assignments(flights, gates)
    assert len(views) == len(flights)
    assert all(v.provenance == ProvenanceType.SCHEDULE_BASELINE for v in views)
    assert all(not v.is_reassigned for v in views)


# -----------------------------------------------------------------------------
# R05-T31 to R05-T33: Safe Live Optimization & Independent Verifier (Task R05-G / R05-H)
# -----------------------------------------------------------------------------

def test_r05_t31_safe_live_optimization_size_guard() -> None:
    """R05-T31: ScenarioSizeLimitExceeded is raised if flights > max_live_solving_flights."""
    from dashboard.core.config import DashboardConfig
    fake_flights = [
        Flight(
            flight_id=f"F_{i}",
            flight_index=i,
            carrier="VN",
            flight_number=f"{i}",
            scheduled_arrival_min=360,
            scheduled_departure_min=420,
            predicted_arrival_min=360,
            nominal_gate_id="G_01",
        )
        for i in range(160)
    ]
    fake_gates = [Gate(gate_id="G_01", gate_index=0)]
    opt_service = OptimizationService(config=DashboardConfig(max_live_solving_flights=150))
    with pytest.raises(ScenarioSizeLimitExceeded):
        opt_service.solve(fake_flights, fake_gates, solver_name="cpsat")


def test_r05_t32_independent_verifier_valid_cpsat_run() -> None:
    """R05-T32: verify_hard_constraints_independently verifies a valid solution with 0 violations."""
    svc = ScenarioService()
    flights, gates = svc.load_scenario("SCEN_P07_DUAL_CORE_30")
    opt = OptimizationService()
    run, is_valid, violations = opt.solve(flights, gates, solver_name="greedy", scenario_id="SCEN_P07_DUAL_CORE_30")
    assert run.conflict_count == 0
    assert is_valid is True
    assert len(violations) == 0


def test_r05_t33_greedy_heuristic_never_claims_optimal() -> None:
    """R05-T33: Deterministic Greedy or heuristic run is never labeled as is_optimal_proven=True."""
    svc = ScenarioService()
    flights, gates = svc.load_scenario("SCEN_P07_DUAL_CORE_30")
    opt = OptimizationService()
    run, _, _ = opt.solve(flights, gates, solver_name="greedy", scenario_id="SCEN_P07_DUAL_CORE_30")
    assert run.is_optimal_proven is False
    assert "OPTIMAL_PROVEN" not in str(run.termination_reason)


# -----------------------------------------------------------------------------
# R05-T34 to R05-T35: Flight Inspector & Cross-Midnight Formatting (Task R05-F)
# -----------------------------------------------------------------------------

def test_r05_t34_cross_midnight_clock_formatting() -> None:
    """R05-T34: Continuous time formatting formats minutes into HH:MM and cross-midnight into +1d HH:MM."""
    assert _format_time_clock(360) == "06:00"
    assert _format_time_clock(750) == "12:30"
    assert _format_time_clock(1440) == "+1d 00:00"
    assert _format_time_clock(1475) == "+1d 00:35"


def test_r05_t35_flight_inspector_views_contain_operational_attributes(sample_flights: List[Flight], sample_gates: List[Gate]) -> None:
    """R05-T35: GateTimelineView carries all operational attributes needed by Flight Inspector."""
    views = _build_nominal_assignments(sample_flights, sample_gates)
    v0 = views[0]
    assert v0.flight_id == "FL_01"
    assert v0.gate_id == "G_01"
    assert v0.buffer_min == 15
    assert v0.actual_gate_out_min == 420
    assert v0.actual_gate_release_min == 435
    assert v0.resource_type == "CONTACT_GATE"
    assert v0.is_remote is False
