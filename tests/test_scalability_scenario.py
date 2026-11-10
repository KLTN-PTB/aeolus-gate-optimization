"""Tests for Synthetic Scalability Scenario Generator (Phase 1).

Validates:
1. Determinism under fixed seed.
2. Primary scenario dimensions (1500 inbound flights x 50 gates).
3. Leakage safety and complete absence of forbidden columns.
4. Strict prohibition of 2024 data.
5. Chronological ordering and diurnal profile validity.
6. Scaling ladder nestedness and monotonic stress progression.
7. End-to-end compatibility with AircraftTurnModel, Flight domain entities, and solver evaluators.
8. Artifact persistence and integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest
import pandas as pd
import numpy as np

from src.evaluation.downstream_comparison_v2 import validate_downstream_input_boundary
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.scalability_scenario import (
    DEFAULT_CONTACT_GATES,
    DEFAULT_LADDER_COUNTS,
    DEFAULT_PRIMARY_FLIGHT_COUNT,
    DEFAULT_SCALABILITY_SEED,
    compute_scenario_occupancy_metrics,
    generate_scalability_scenario,
    generate_scaling_ladder,
    load_canonical_source_data,
    save_scalability_scenario_artifacts,
    scenario_to_flights,
    scenario_to_gates,
    scenario_to_turns,
)


@pytest.fixture(scope="module")
def source_data() -> pd.DataFrame:
    """Fixture providing July 2023 development inbound data."""
    return load_canonical_source_data(date_prefix="2023-07")


@pytest.fixture(scope="module")
def primary_scenario(source_data: pd.DataFrame):
    """Fixture providing primary 1500x50 scalability scenario."""
    return generate_scalability_scenario(
        source_df=source_data,
        n_flights=DEFAULT_PRIMARY_FLIGHT_COUNT,
        n_contact_gates=DEFAULT_CONTACT_GATES,
        seed=DEFAULT_SCALABILITY_SEED,
    )


def test_determinism_under_fixed_seed(source_data: pd.DataFrame) -> None:
    """Calling generator twice with identical seed produces identical hash and rows."""
    scen_a = generate_scalability_scenario(
        source_df=source_data, n_flights=300, n_contact_gates=50, seed=202601
    )
    scen_b = generate_scalability_scenario(
        source_df=source_data, n_flights=300, n_contact_gates=50, seed=202601
    )

    assert scen_a.scenario_hash == scen_b.scenario_hash
    assert scen_a.flights_df["flight_key"].tolist() == scen_b.flights_df["flight_key"].tolist()
    assert scen_a.flights_df["nominal_gate_id"].tolist() == scen_b.flights_df["nominal_gate_id"].tolist()
    pd.testing.assert_frame_equal(scen_a.flights_df, scen_b.flights_df)


def test_primary_scenario_dimensions_and_population(primary_scenario) -> None:
    """Primary scenario has exactly 1500 inbound flights and 50 contact gates."""
    assert primary_scenario.n_flights == 1500
    assert primary_scenario.n_contact_gates == 50
    assert len(primary_scenario.flights_df) == 1500

    df = primary_scenario.flights_df
    # Inbound population
    assert (df["DEST"] == "ATL").all()
    # Stable synthetic identifiers
    assert df["flight_key"].iloc[0] == "S1500-0001"
    assert df["flight_key"].iloc[-1] == "S1500-1500"
    assert df["flight_key"].nunique() == 1500

    # Contact gates cycle round-robin across 50 gates
    assert df["nominal_gate_id"].iloc[0] == "G_01"
    assert df["nominal_gate_id"].iloc[49] == "G_50"
    assert df["nominal_gate_id"].iloc[50] == "G_01"
    assert set(df["nominal_gate_id"].unique()) == {f"G_{i+1:02d}" for i in range(50)}


def test_leakage_and_forbidden_columns_absence(primary_scenario) -> None:
    """Scenario dataframe strictly contains zero realized delay or leakage fields."""
    df = primary_scenario.flights_df
    forbidden = [
        "ARR_DELAY",
        "DEP_DELAY",
        "DEP_TIME",
        "ARR_TIME",
        "TAXI_IN",
        "TAXI_OUT",
        "WHEELS_ON",
        "WHEELS_OFF",
        "ACTUAL_ELAPSED_TIME",
        "AIR_TIME",
        "chain_id",
        "tail_number",
    ]
    for col in forbidden:
        assert col not in df.columns, f"Forbidden column '{col}' present in scenario dataframe!"

    # Must pass standard downstream validator
    validate_downstream_input_boundary(df)


def test_access_guard_prohibits_2024(source_data: pd.DataFrame) -> None:
    """Attempting to construct scenario from 2024 data raises ValueError."""
    with pytest.raises(ValueError, match="strictly forbidden"):
        load_canonical_source_data(date_prefix="2024-01")

    # Contaminating dataframe with a 2024 record
    contaminated_df = source_data.head(10).copy()
    contaminated_df.loc[0, "FL_DATE"] = "2024-01-01 00:00:00"
    with pytest.raises(ValueError, match="2024 records"):
        generate_scalability_scenario(source_df=contaminated_df, n_flights=5)


def test_diurnal_profile_and_temporal_validity(primary_scenario) -> None:
    """Flights are sorted chronologically and span realistic 24-hour diurnal profile."""
    df = primary_scenario.flights_df

    # Arrival and departure minutes within 0..1439
    assert (df["_sched_arr_min"] >= 0).all()
    assert (df["_sched_arr_min"] < 1440).all()
    assert (df["_sched_dep_min"] >= 0).all()
    assert (df["_sched_dep_min"] < 1440).all()

    # Chronologically sorted by arrival minute
    arr_mins = df["_sched_arr_min"].tolist()
    assert arr_mins == sorted(arr_mins)

    # Hourly distribution covers daytime and evening banks
    hours = df["scheduled_arrival_hour"].unique()
    assert len(hours) >= 20, "Scenario should span almost all 24 clock hours"


def test_scaling_ladder_nestedness_and_stress_metrics(source_data: pd.DataFrame) -> None:
    """Ladder rungs are strictly nested and exhibit monotonic demand escalation."""
    ladder = generate_scaling_ladder(
        source_df=source_data,
        counts=DEFAULT_LADDER_COUNTS,
        n_contact_gates=50,
        seed=202601,
    )
    assert set(ladder.keys()) == set(DEFAULT_LADDER_COUNTS)

    # Verify strict nested subset property
    def row_signatures(scen):
        return {
            (row["FL_DATE"], row["OP_CARRIER"], row["OP_CARRIER_FL_NUM"], row["_sched_arr_min"], row["ORIGIN"])
            for _, row in scen.flights_df.iterrows()
        }

    counts = sorted(DEFAULT_LADDER_COUNTS)
    sigs = {c: row_signatures(ladder[c]) for c in counts}

    for i in range(len(counts) - 1):
        c_low = counts[i]
        c_high = counts[i + 1]
        assert sigs[c_low].issubset(sigs[c_high]), f"Rung {c_low} is not a strict subset of Rung {c_high}!"
        assert len(sigs[c_low]) == c_low

    # Verify monotonic peak demand growth
    tm = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    metrics = {c: compute_scenario_occupancy_metrics(ladder[c], tm) for c in counts}

    prev_peak = 0
    for c in counts:
        m = metrics[c]
        assert m["peak_concurrent_demand"] >= prev_peak, f"Peak demand should not decrease with N for {c}"
        prev_peak = m["peak_concurrent_demand"]

    # At N=250: peak demand should fit in 50 gates (over-capacity = 0)
    assert metrics[250]["over_capacity_flights"] == 0
    assert metrics[250]["peak_concurrent_demand"] <= 50

    # At N=1500: massive over-capacity stress (> 100 overflow flights)
    assert metrics[1500]["over_capacity_flights"] > 100
    assert metrics[1500]["capacity_ratio"] > 3.0


def test_domain_integration_and_solver_compatibility(primary_scenario) -> None:
    """Scenario converts to domain entities and executes cleanly on baseline solver."""
    turns = scenario_to_turns(primary_scenario)
    assert len(turns) == 1500
    # Every turn has nominal 75-minute occupancy window (60 dwell + 15 buffer)
    for t in turns[:50]:
        assert t.occupancy_duration_min == 75
        assert t.min_turnaround_min == 45
        assert t.default_dwell_min == 60
        assert t.separation_buffer_min == 15

    flights = scenario_to_flights(primary_scenario)
    assert len(flights) == 1500
    assert flights[0].flight_id == "S1500-0001"

    contact_gates, overflow = scenario_to_gates(primary_scenario)
    assert len(contact_gates) == 50
    assert overflow.is_overflow is True

    # Test solver feasibility on a 50-flight bank subset
    test_flights = flights[:50]
    all_gates = contact_gates + [overflow]
    solver = DeterministicGreedyGateSolver()
    result = solver.solve(test_flights, all_gates, allow_overflow=True)
    assert result.feasible is True

    eval_result = evaluate_gate_assignment(result.assignments, test_flights, all_gates)
    assert eval_result.feasible is True
    assert eval_result.constraint_diagnostics.is_valid is True


def test_artifact_persistence_integrity(primary_scenario, source_data: pd.DataFrame) -> None:
    """Artifact publisher generates all 6 expected files with valid syntax and schema."""
    ladder = generate_scaling_ladder(
        source_df=source_data,
        counts=(250, 500),
        n_contact_gates=50,
        seed=202601,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        created = save_scalability_scenario_artifacts(
            scenario_1500=primary_scenario,
            ladder=ladder,
            output_dir=tmp_dir,
            git_commit="7ba0aba92d366f712977faaaa5a73cba65a32a55",
        )
        assert len(created) == 6

        # Check JSON files are valid
        for json_key in ("input_manifest", "gate_inventory", "scenario_metadata", "scenario_summary"):
            file_path = created[json_key]
            assert file_path.exists()
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert isinstance(data, dict)

        # Check Parquet is valid
        pq_path = created["scenario_parquet"]
        assert pq_path.exists()
        loaded_df = pd.read_parquet(pq_path)
        assert len(loaded_df) == 1500
        assert "ARR_DELAY" not in loaded_df.columns

        # Check Report
        rep_path = created["generation_report"]
        assert rep_path.exists()
        content = rep_path.read_text(encoding="utf-8")
        assert "Aeolus Scalability Scenario Generation Report" in content
        assert "1500 Inbound Flights x 50 Gates" in content
