"""Unit tests for synthetic airport simulation."""

import random
from src.simulation.simulate_airport import (
    AIRCRAFT_TYPES,
    assign_aircraft_type,
    generate_gates,
)


def test_generate_gates_count_and_reproducibility() -> None:
    gates1 = generate_gates(n_gates=10, seed=123)
    gates2 = generate_gates(n_gates=10, seed=123)

    assert len(gates1) == 10
    assert len(gates2) == 10
    assert [g.gate_id for g in gates1] == [f"G{i:02d}" for i in range(1, 11)]
    assert [g.is_contact_gate for g in gates1] == [g.is_contact_gate for g in gates2]


def test_assign_aircraft_type() -> None:
    rng = random.Random(42)
    assigned = [assign_aircraft_type(rng) for _ in range(100)]

    for atype in assigned:
        assert atype in AIRCRAFT_TYPES
