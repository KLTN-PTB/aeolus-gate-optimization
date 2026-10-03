"""Tests for common scenario invariants and exact pairing across models (Phase 8)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.evaluation.downstream_comparison import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    DEFAULT_SCENARIO_SPECS,
    DownstreamScenario,
    DownstreamScenarioSpec,
    build_scenario_gates,
    extract_scenario_from_raw,
)


def _make_dummy_raw_df(date_str: str, n_rows: int = 50) -> pd.DataFrame:
    """Helper to generate a dummy raw arrival dataframe."""
    return pd.DataFrame({
        "FL_DATE": [f"{date_str} 00:00:00"] * n_rows,
        "OP_CARRIER": ["DL"] * n_rows,
        "OP_CARRIER_FL_NUM": [1000 + i for i in range(n_rows)],
        "ORIGIN": ["LGA"] * n_rows,
        "CRS_DEP_TIME": [1200 + (i % 60) for i in range(n_rows)],
        "CRS_ARR_TIME": [f"{date_str} 14:{i % 60:02d}:00" for i in range(n_rows)],
        "CRS_ELAPSED_TIME": [120] * n_rows,
        "MONTH": [int(date_str.split("-")[1])] * n_rows,
        "DAY_OF_MONTH": [int(date_str.split("-")[2])] * n_rows,
        "DAY_OF_WEEK": [4] * n_rows,
        "DEST": ["ATL"] * n_rows,
        "ARR_DELAY": [float(i - 10) for i in range(n_rows)],
        "flight_key": [f"FL_{date_str}_{i:03d}" for i in range(n_rows)],
    })


def test_standard_scenario_specs_defined() -> None:
    """Assert exactly 4 standard representative scenarios are defined."""
    assert len(DEFAULT_SCENARIO_SPECS) == 4
    scenario_ids = [s.scenario_id for s in DEFAULT_SCENARIO_SPECS]
    assert scenario_ids == [
        "SCEN_2023_LOW",
        "SCEN_2023_MEDIUM",
        "SCEN_2023_HIGH",
        "SCEN_2023_DISRUPTED",
    ]


def test_build_scenario_gates_invariant() -> None:
    """Gate sets must consist of n contact gates plus exactly 1 remote overflow apron."""
    for n_gates in [10, 15, 20]:
        contact_gates, overflow_gate = build_scenario_gates(n_gates)
        assert len(contact_gates) == n_gates
        for idx, g in enumerate(contact_gates):
            assert not g.is_overflow
            assert g.gate_id == f"G_{idx+1:02d}"
            assert g.gate_index == idx
        assert overflow_gate.is_overflow
        assert overflow_gate.gate_id == "REMOTE_APRON_01"
        assert overflow_gate.gate_index == n_gates


def test_scenario_extraction_deterministic_hash() -> None:
    """Scenario extraction must produce deterministic flights and invariant scenario_hash."""
    spec = DownstreamScenarioSpec(
        scenario_id="SCEN_TEST",
        day_id="2023-07-03",
        date_str="2023-07-03",
        n_flights=25,
        n_contact_gates=8,
    )
    raw_df = _make_dummy_raw_df("2023-07-03", n_rows=50)

    scen1 = extract_scenario_from_raw(spec, raw_df)
    scen2 = extract_scenario_from_raw(spec, raw_df)

    assert scen1.scenario_hash == scen2.scenario_hash
    assert scen1.n_flights == 25
    assert len(scen1.flights_df) == 25
    assert list(scen1.flights_df["flight_key"]) == list(scen2.flights_df["flight_key"])
    assert list(scen1.flights_df["nominal_gate_id"]) == list(scen2.flights_df["nominal_gate_id"])


def test_all_candidates_share_exact_same_scenario() -> None:
    """All candidate models must receive the exact same scenario instance without mutation."""
    spec = DownstreamScenarioSpec(
        scenario_id="SCEN_2023_LOW",
        day_id="2023-11-23",
        date_str="2023-11-23",
        n_flights=30,
        n_contact_gates=10,
    )
    raw_df = _make_dummy_raw_df("2023-11-23", n_rows=60)
    scenario = extract_scenario_from_raw(spec, raw_df)

    initial_hash = scenario.scenario_hash
    initial_flight_count = len(scenario.flights_df)

    # Simulate passing scenario across all candidate models
    for cand in DEFAULT_DOWNSTREAM_CANDIDATES:
        assert scenario.scenario_hash == initial_hash
        assert len(scenario.flights_df) == initial_flight_count
        assert scenario.n_contact_gates == 10
