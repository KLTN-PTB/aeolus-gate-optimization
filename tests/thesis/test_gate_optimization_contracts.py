"""Unit tests for gate optimization data contracts."""

import pytest

from src.optimization.contracts import (
    CostParams,
    Flight,
    Gate,
    GateOptimizationContractViolation,
    ProblemInstance,
)


def test_flight_valid_contract() -> None:
    flight = Flight(
        flight_id="FL001",
        direction="ARR",
        aircraft_type="A320",
        sched_time_min=540,
        p_delay=0.3,
        delay_est_min=25.0,
        dwell_time_min=45,
        chain_group_id="CG1",
        current_gate="G01",
    )
    assert flight.flight_id == "FL001"
    assert flight.direction == "ARR"
    assert flight.p_delay == 0.3


def test_flight_invalid_p_delay() -> None:
    with pytest.raises(GateOptimizationContractViolation, match="p_delay must be in"):
        Flight(
            flight_id="FL002",
            direction="ARR",
            aircraft_type="A320",
            sched_time_min=600,
            p_delay=1.5,  # Invalid: > 1.0
            delay_est_min=10.0,
            dwell_time_min=30,
        )


def test_gate_valid_contract() -> None:
    gate = Gate(
        gate_id="G01",
        compatible_types=["A320", "B738"],
        is_contact_gate=True,
    )
    assert gate.gate_id == "G01"
    assert "A320" in gate.compatible_types


def test_problem_instance_round_trip() -> None:
    flight = Flight(
        flight_id="FL101",
        direction="ARR",
        aircraft_type="B738",
        sched_time_min=480,
        p_delay=0.1,
        delay_est_min=0.0,
        dwell_time_min=40,
    )
    gate = Gate(
        gate_id="G01",
        compatible_types=["B738"],
        is_contact_gate=True,
    )
    params = CostParams()
    instance = ProblemInstance(
        airport="ATL",
        planning_date="2026-09-20",
        horizon_min=1440,
        flights=[flight],
        gates=[gate],
        cost_params=params,
    )

    json_data = instance.to_json()
    reconstructed = ProblemInstance.from_json(json_data)

    assert reconstructed.airport == "ATL"
    assert len(reconstructed.flights) == 1
    assert reconstructed.flights[0].flight_id == "FL101"
    assert reconstructed.gates[0].gate_id == "G01"


def test_problem_instance_duplicate_flight_id() -> None:
    f1 = Flight("FL001", "ARR", "A320", 500, 0.2, 10.0, 30)
    f2 = Flight("FL001", "DEP", "A320", 600, 0.1, 0.0, 30)
    g = Gate("G01", ["A320"])
    with pytest.raises(GateOptimizationContractViolation, match="duplicate flight_id"):
        ProblemInstance("ATL", "2026-09-20", 1440, [f1, f2], [g], CostParams())
