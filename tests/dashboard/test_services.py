"""Integration tests for Dashboard services (ScenarioService, OptimizationService, PreflightService)."""

import pytest

from dashboard.core.config import DashboardConfig
from dashboard.core.contracts import ProvenanceType
from dashboard.services.scenario_service import ScenarioService
from dashboard.services.optimization_service import (
    OptimizationService,
    ScenarioSizeLimitExceeded,
)
from dashboard.services.preflight_service import PreflightService


def test_scenario_service_canonical_load(test_config: DashboardConfig) -> None:
    service = ScenarioService(test_config)
    flights, gates = service.load_scenario("SCEN_P09_CANONICAL_120")
    assert len(flights) == 120
    assert len(gates) == 26  # 25 contact gates + 1 remote apron

    context = service.get_scenario_context("SCEN_P09_CANONICAL_120")
    assert context.flight_count == 120
    assert context.gate_count == 25
    assert context.remote_capacity == 1
    assert context.hub_iata == "ATL"


def test_scenario_service_quarantines_2024(test_config: DashboardConfig) -> None:
    service = ScenarioService(test_config)
    with pytest.raises(PermissionError) as exc:
        service.load_scenario("SCEN_2024_HOLD_OUT")
    assert "2024 data sealed under Protocol V4" in str(exc.value)


def test_optimization_service_greedy_solve(test_config: DashboardConfig) -> None:
    scen_service = ScenarioService(test_config)
    flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

    opt_service = OptimizationService(test_config)
    view, is_valid, violations = opt_service.solve(
        flights=flights,
        gates=gates,
        solver_name="greedy",
        scenario_id="SCEN_P09_CANONICAL_120",
    )

    assert is_valid is True
    assert len(violations) == 0
    assert view.solver_name == "Deterministic Greedy"
    assert len(view.assignments) == 120
    assert view.conflict_count == 0
    assert view.solve_time_sec >= 0.0
    assert view.provenance == ProvenanceType.NATIVE_INFERENCE


def test_optimization_service_cpsat_solve(test_config: DashboardConfig) -> None:
    scen_service = ScenarioService(test_config)
    flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

    # Test on a 30-flight slice for fast unit testing (< 100ms)
    slice_flights = flights[:30]
    opt_service = OptimizationService(test_config)
    view, is_valid, violations = opt_service.solve(
        flights=slice_flights,
        gates=gates,
        solver_name="cpsat",
        scenario_id="SCEN_SLICE_30",
    )

    assert is_valid is True
    assert len(violations) == 0
    assert view.is_optimal_proven is True
    assert view.status == "OPTIMAL"
    assert len(view.assignments) == 30


def test_optimization_service_size_limit_guard(test_config: DashboardConfig) -> None:
    scen_service = ScenarioService(test_config)
    flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

    # Exceed limit by duplicating flights
    too_many_flights = flights * 2  # 240 flights > 150 limit
    opt_service = OptimizationService(test_config)

    with pytest.raises(ScenarioSizeLimitExceeded) as exc:
        opt_service.solve(
            flights=too_many_flights,
            gates=gates,
            solver_name="cpsat",
        )
    assert "exceeds live interactive safety limit" in str(exc.value)


def test_preflight_service_full_report(test_config: DashboardConfig) -> None:
    preflight = PreflightService(test_config)
    report = preflight.run_preflight_checks()

    assert report.is_healthy is True
    assert report.ready_for_presentation is True
    summary = report.summary_dict()
    assert summary["failed_checks"] == 0
    assert summary["passed_checks"] > 0
