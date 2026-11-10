"""Saved stress scenarios must load and execute through the dashboard workflow."""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from dashboard.adapters.artifact_loader import ArtifactValidationError
from dashboard.core.config import DashboardConfig
from dashboard.core.contracts import ProvenanceType
from dashboard.services.optimization_service import OptimizationService, ScenarioSizeLimitExceeded
from dashboard.services.scenario_service import ScenarioService


SCENARIO_ID = "SCEN_2023_STRESS_1500_50"
ARTIFACT_PATH = f"data/simulation/{SCENARIO_ID}.parquet"


def test_saved_stress_flights_preserve_parquet_values(test_config: DashboardConfig) -> None:
    service = ScenarioService(test_config)
    flights, gates = service.load_scenario(SCENARIO_ID)
    saved = pd.read_parquet(test_config.project_root / ARTIFACT_PATH)
    records = saved.astype(object).where(saved.notna(), None).to_dict("records")

    assert len(flights) == 1500
    assert len(gates) == 51
    assert sum(not gate.is_overflow for gate in gates) == 50
    assert {flight.nominal_gate_id for flight in flights} == {f"G_{i:02d}" for i in range(1, 51)}
    for flight, row in zip(flights, records):
        assert {column: getattr(flight, column) for column in saved.columns} == row

    context = service.get_scenario_context(SCENARIO_ID)
    identity = service.get_scenario_identity(SCENARIO_ID)
    assert context.flight_count == 1500
    assert context.gate_count == 50
    assert context.prediction_source == "PRECOMPUTED"
    assert identity.flight_count == 1500
    assert identity.gate_count == 51
    assert identity.generator_seed is None
    assert identity.dataset_version == "PARQUET_FLIGHTS_V1"
    assert context.scenario_digest == identity.scenario_digest
    predictions = service.load_scenario_predictions(SCENARIO_ID)
    assert len(predictions) == 1500
    assert predictions[0].predicted_arr_delay_min == flights[0].arrival_delay_min
    assert predictions[0].provenance == ProvenanceType.PRECOMPUTED_PREDICTION


def test_stress_greedy_solves_all_1500_flights(test_config: DashboardConfig) -> None:
    flights, gates = ScenarioService(test_config).load_scenario(SCENARIO_ID)
    run, valid, violations = OptimizationService(test_config).solve(
        flights, gates, solver_name="greedy", scenario_id=SCENARIO_ID,
        provenance=ProvenanceType.SYNTHETIC_SIMULATION,
    )
    assert valid, violations
    assert len(run.assignments) == 1500
    assert run.conflict_count == 0
    assert run.scenario_id == SCENARIO_ID
    assert not run.is_optimal_proven

    with pytest.raises(ScenarioSizeLimitExceeded):
        OptimizationService(test_config).solve(flights, gates, solver_name="greedy")
    with pytest.raises(ScenarioSizeLimitExceeded):
        OptimizationService(test_config).solve(flights + flights[:1], gates, scenario_id=SCENARIO_ID)


def test_missing_stress_file_never_uses_cached_or_generated_data(
    tmp_path: Path, test_config: DashboardConfig,
) -> None:
    # Populate the shared service cache from the real project first.
    ScenarioService(test_config).load_scenario(SCENARIO_ID)
    service = ScenarioService(replace(test_config, project_root=tmp_path))
    with pytest.raises(FileNotFoundError):
        service.load_scenario(SCENARIO_ID)


def test_replaced_parquet_refreshes_flights_and_digest(
    tmp_path: Path, test_config: DashboardConfig,
) -> None:
    metadata = next(s for s in test_config.registered_scenarios if s["id"] == SCENARIO_ID)
    config = replace(
        test_config, project_root=tmp_path,
        registered_scenarios=({**metadata, "flights": "2"},),
    )
    frame = pd.read_parquet(test_config.project_root / ARTIFACT_PATH).head(2)
    path = tmp_path / ARTIFACT_PATH
    path.parent.mkdir(parents=True)
    frame.to_parquet(path, index=False)
    service = ScenarioService(config)
    original_hash = service.compute_scenario_hash(SCENARIO_ID)
    frame.loc[0, "predicted_arrival_min"] += 500
    frame.to_parquet(path, index=False)
    assert service.compute_scenario_hash(SCENARIO_ID) != original_hash
    flights, _ = service.load_scenario(SCENARIO_ID)
    assert flights[0].predicted_arrival_min == frame.iloc[0].predicted_arrival_min


@pytest.mark.parametrize("invalid", ["missing_column", "duplicate_id", "unknown_gate", "wrong_count"])
def test_invalid_saved_scenario_fails_before_solving(
    invalid: str, tmp_path: Path, test_config: DashboardConfig,
) -> None:
    frame = pd.read_parquet(test_config.project_root / ARTIFACT_PATH)
    if invalid == "missing_column":
        frame = frame.drop(columns="predicted_arrival_min")
    elif invalid == "duplicate_id":
        frame.loc[1, "flight_id"] = frame.loc[0, "flight_id"]
    elif invalid == "unknown_gate":
        frame.loc[0, "nominal_gate_id"] = "G_99"
    else:
        frame = frame.head(10)
    path = tmp_path / ARTIFACT_PATH
    path.parent.mkdir(parents=True)
    frame.to_parquet(path, index=False)
    with pytest.raises((ArtifactValidationError, ValueError)):
        ScenarioService(replace(test_config, project_root=tmp_path)).load_scenario(SCENARIO_ID)


def test_dashboard_selects_stress_and_runs_greedy() -> None:
    from streamlit.testing.v1 import AppTest
    from dashboard.core.state import PageKeys, SessionStateKeys

    app_path = Path(__file__).resolve().parents[2] / "dashboard" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60).run()
    assert not app.exception
    scenario_select = next(widget for widget in app.selectbox if widget.label == "Kịch bản:")
    assert "Atlanta Stress (1.500 Chuyến, 50 Cổng)" in scenario_select.options
    scenario_select.set_value(SCENARIO_ID).run()
    assert not app.exception
    assert not app.error
    app.radio[0].set_value(PageKeys.GATE_OPERATIONS.value).run()
    assert not app.exception
    assert not app.error
    app.selectbox(key="solver_choice_select").select("Hybrid (Greedy+CP-SAT)").run()
    assert app.session_state[SessionStateKeys.DRAFT_CONFIGURATION]["solver_name"] == "hybrid"
    app.selectbox(key="solver_choice_select").select("Deterministic Greedy").run()
    app.button(key="btn_run_solver").click().run()
    assert not app.exception
    assert not app.error
    run = app.session_state[SessionStateKeys.ACTIVE_RESULT]
    assert run.scenario_id == SCENARIO_ID
    assert len(run.assignments) == 1500
    assert run.conflict_count == 0
    scenario_select = next(widget for widget in app.selectbox if widget.label == "Kịch bản:")
    scenario_select.set_value("SCEN_P09_CANONICAL_120").run()
    assert not app.exception
    assert not app.error
    assert app.session_state[SessionStateKeys.ACTIVE_RESULT] is None
