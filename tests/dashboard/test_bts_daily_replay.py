"""Real movements, inferred rotations and finite resources in the 2026 replay."""

from collections import Counter
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.state import PageKeys, SessionStateKeys
from dashboard.services.optimization_service import OptimizationService
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.concourse_chart import create_concourse_utilization_figure
from dashboard.visualizers.timeline_chart import create_activity_timeline_figure
from src.simulation.bts_daily_replay import (
    SCENARIO_ID, build_replay, infer_complete_turns, load_atl_events, peak_occupancy, select_turns,
)


@pytest.fixture(scope="module")
def replay():
    service = ScenarioService()
    flights, gates = service.load_scenario(SCENARIO_ID)
    return service, flights, gates


def test_1500_distinct_movements_are_750_occupancies(replay):
    service, flights, gates = replay
    movements = service.load_scenario_movements(SCENARIO_ID)
    frame = pd.DataFrame(movements)
    assert len(frame) == frame.movement_id.nunique() == 1500
    assert frame.direction.value_counts().to_dict() == {"ARR": 750, "DEP": 750}
    assert len(flights) == len(service.load_scenario_turns(SCENARIO_ID)) == 750
    assert set(frame.turn_id) == {flight.flight_id for flight in flights}
    assert frame.actual_event_min.between(0, 1439).all()
    for flight in flights:
        group = frame[frame.turn_id == flight.flight_id].set_index("direction")
        assert len(group) == 2
        assert group.loc["ARR", "tail_number"] == group.loc["DEP", "tail_number"]
        assert flight.occupancy_start_min == group.loc["ARR", "actual_event_min"]
        assert flight.precomputed_gate_out_min == group.loc["DEP", "actual_event_min"]
        assert 30 <= flight.precomputed_gate_out_min - flight.occupancy_start_min <= 720
    context = service.get_scenario_context(SCENARIO_ID)
    assert context.flight_count == 1500 and context.optimization_count == 750
    assert context.arrival_count == context.departure_count == 750
    assert context.service_date == "2026-07-01"
    assert context.evidence_provenance.information_regime.value == "RETROSPECTIVE"
    assert context.pairing_source == "INFERRED"
    assert context.prediction_source == "NONE"
    assert service.load_scenario_predictions(SCENARIO_ID) == []


def test_finite_150_gates_and_verified_greedy_solution(replay):
    service, flights, gates = replay
    assert len(gates) == len({g.gate_id for g in gates}) == 150
    assert all(g.capacity == 1 and not g.is_overflow and not g.is_unbounded for g in gates)
    assert Counter(g.gate_id[0] for g in gates) == {"T": 21, "A": 29, "B": 32, "C": 34, "D": 34}
    assert peak_occupancy(flights) == 115
    inventory = service.get_scenario_gate_inventory(SCENARIO_ID)
    assert inventory["remote_count"] == inventory["remote_capacity"] == 0
    assert not inventory["overflow_allowed"]
    run, valid, errors = OptimizationService().solve(flights, gates, "greedy", SCENARIO_ID)
    assert valid, errors
    assert len(run.assignments) == 750 and run.conflict_count == 0 and run.remote_gate_count == 0
    assert {a.gate_id for a in run.assignments} <= {g.gate_id for g in gates}
    with pytest.raises(ValueError, match="150"):
        OptimizationService().solve(flights, gates, "greedy", SCENARIO_ID, params={"allow_overflow": True})
    # Returning from the solver page to Control Tower must accept view-model lists.
    figure = create_concourse_utilization_figure(gates=gates, assignments=run.assignments)
    assert list(figure.data[0].y) == ["Concourse T", "Concourse A", "Concourse B", "Concourse C", "Concourse D"]
    assert all(occupied <= capacity for occupied, capacity in zip(figure.data[1].x, figure.data[0].x))


def test_timeline_counts_each_movement_once(replay):
    service, flights, _ = replay
    figure = create_activity_timeline_figure(flights, movements=service.load_scenario_movements(SCENARIO_ID))
    assert sum(figure.data[0].y) == 750
    assert sum(figure.data[1].y) == 750


def test_bundled_replay_artifact_hashes(replay):
    service, _, _ = replay
    manifest = service.load_scenario_manifest(SCENARIO_ID)
    metadata = DEFAULT_CONFIG.scenario_metadata(SCENARIO_ID)
    for key, path_key in (("occupancy", "artifact_path"), ("movements", "movements_path"), ("gates", "gates_path")):
        data = (DEFAULT_CONFIG.project_root / metadata[path_key]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == manifest["artifact_sha256"][key]


def test_saved_artifacts_reproduce_without_raw_mutation(replay):
    service, _, _ = replay
    manifest = service.load_scenario_manifest(SCENARIO_ID)
    source = DEFAULT_CONFIG.project_root / manifest["source_path"]
    if not source.is_file():
        pytest.skip("Optional full-month BTS raw source is not bundled; replay artifact hashes are checked separately.")
    with source.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest["source_sha256"]
    first, movements, _, rebuilt = build_replay(source)
    metadata = DEFAULT_CONFIG.scenario_metadata(SCENARIO_ID)
    saved = pd.read_parquet(DEFAULT_CONFIG.project_root / metadata["artifact_path"])
    pd.testing.assert_frame_equal(first, saved)
    pd.testing.assert_frame_equal(movements, pd.read_parquet(DEFAULT_CONFIG.project_root / metadata["movements_path"]))
    assert rebuilt["eligible_complete_turns"] == 769
    assert rebuilt["peak_concurrent_occupancy_with_buffer"] == 115
    for key, path_key in (("occupancy", "artifact_path"), ("movements", "movements_path"), ("gates", "gates_path")):
        data = (DEFAULT_CONFIG.project_root / metadata[path_key]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == manifest["artifact_sha256"][key]


def test_origin_timezone_and_midnight_are_normalized(tmp_path: Path):
    row = [""] * 71
    for i, value in {0: "DL", 1: "1", 4: "DL", 5: "1", 6: "SFO", 7: "ATL",
                     8: "20260701", 11: "2330", 15: "0720", 18: "300", 21: "-10",
                     25: "N123", 38: "0"}.items():
        row[i] = value
    source = tmp_path / "sample.asc"
    source.write_text("|".join(row) + "\n", encoding="ascii")
    events, _ = load_atl_events(source)
    assert events[0]["scheduled_event_local"] == "2026-07-02T07:30:00-04:00"
    assert events[0]["actual_event_local"] == "2026-07-02T07:20:00-04:00"
    assert events[0]["actual_event_min"] == 1880
    assert infer_complete_turns(events) == []


def test_turn_selection_is_permutation_invariant_and_preserves_real_legs():
    def event(identity, direction, minute, tail):
        return {"movement_id": identity, "direction": direction, "actual_event_min": minute,
                "tail_number": tail, "carrier": "DL"}
    events = [event("A1", "ARR", 100, "N1"), event("A2", "ARR", 110, "N1"),
              event("D1", "DEP", 150, "N1"), event("D2", "DEP", 160, "N2")]
    turns = infer_complete_turns(events)
    assert len(turns) == 1 and turns[0]["arrival"]["movement_id"] == "A2"
    assert infer_complete_turns(list(reversed(events))) == turns
    assert select_turns(turns, 1) == select_turns(list(reversed(turns)), 1)
    with pytest.raises(ValueError):
        select_turns(turns, 2)


def test_dashboard_uses_movement_counts_and_finite_replay_gates():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(DEFAULT_CONFIG.project_root / "dashboard/app.py"), default_timeout=60).run()
    selector = next(w for w in app.selectbox if w.label == "Kịch bản:")
    assert "ATL 01/07/2026 — 750 đến + 750 đi, 150 cổng" in selector.options
    selector.set_value(SCENARIO_ID).run()
    assert not app.exception and not app.error
    assert any(SCENARIO_ID in caption.value for caption in app.caption)
    assert any("1500" in markdown.value and "Lượt bay" in markdown.value for markdown in app.markdown)
    assert any("2026-07-01" in markdown.value for markdown in app.markdown)
    app.radio(key="sidebar_page_navigation").set_value(PageKeys.FLIGHT_INTELLIGENCE.value).run()
    assert not app.exception and not app.error
    assert len(app.dataframe[0].value) == 1500
    app.radio(key="sidebar_page_navigation").set_value(PageKeys.GATE_OPERATIONS.value).run()
    assert not app.exception and not app.error
    for label in ("Concourse T (21)", "Concourse A (29)", "Concourse B (32)", "Concourse C (34)", "Concourse D (34)"):
        assert any(widget.label == label for widget in app.checkbox)
    app.selectbox(key="solver_choice_select").select("Deterministic Greedy").run()
    app.button(key="btn_run_solver").click().run()
    assert not app.exception and not app.error
    run = app.session_state[SessionStateKeys.ACTIVE_RESULT]
    assert len(run.assignments) == 750 and run.remote_gate_count == 0 and run.conflict_count == 0
    app.radio(key="sidebar_page_navigation").set_value(PageKeys.CONTROL_TOWER.value).run()
    assert not app.exception and not app.error
    app.radio(key="sidebar_page_navigation").set_value(PageKeys.ROBUSTNESS_LAB.value).run()
    assert not app.exception and not app.error
    assert any("Chưa có kết quả Monte Carlo" in message.value for message in app.info)
