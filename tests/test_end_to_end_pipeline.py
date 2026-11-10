"""End-to-End Pipeline Integration Test for Phase G.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. Complete system flow:
   flight features
   → marginal predictive distribution
   → dependence layer
   → joint delay sample
   → synthetic operational timeline
   → gate occupancy
   → assignment solvers (Greedy, CP-SAT, CP-SAT+SA)
2. All exported artifacts exist and are readable:
   - run_manifest.json
   - scenario_summary.parquet
   - greedy_results.parquet
   - cp_sat_results.parquet
   - sa_results.parquet
   - aggregate_metrics.json
3. Zero contact conflicts across all solvers under synthetic scenario assignments.
4. Identical sampled scenarios used across all compared solvers.
5. All returned solutions are strictly hard-feasible.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts
from src.simulation.scenario_runner import MonteCarloScenarioRunner


def test_end_to_end_artifacts_integrity() -> None:
    """Check that all required Phase G artifacts were exported and contain required columns."""
    artifacts_dir = Path("artifacts/end_to_end")
    assert artifacts_dir.exists()

    required_files = [
        "run_manifest.json",
        "scenario_summary.parquet",
        "greedy_results.parquet",
        "cp_sat_results.parquet",
        "sa_results.parquet",
        "aggregate_metrics.json",
    ]
    for fname in required_files:
        p = artifacts_dir / fname
        assert p.exists(), f"Missing artifact: {p}"

    # Verify manifest
    with open(artifacts_dir / "run_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["phase"] == "PHASE_G"
    assert manifest["status"] == "PASS"
    assert manifest["all_hard_feasibility_satisfied"] is True
    assert manifest["zero_contact_conflicts_across_all_solvers"] is True

    # Verify Parquet tables
    df_scen = pd.read_parquet(artifacts_dir / "scenario_summary.parquet")
    df_greedy = pd.read_parquet(artifacts_dir / "greedy_results.parquet")
    df_cpsat = pd.read_parquet(artifacts_dir / "cp_sat_results.parquet")
    df_sa = pd.read_parquet(artifacts_dir / "sa_results.parquet")

    assert len(df_scen) == len(df_greedy) == len(df_cpsat) == len(df_sa)
    assert (df_greedy["conflicts"] == 0).all()
    assert (df_cpsat["conflicts"] == 0).all()
    assert (df_sa["conflicts"] == 0).all()

    # CP-SAT objective must be <= Greedy objective for all scenarios
    assert (df_cpsat["objective"] <= df_greedy["objective"] + 1e-9).all()

    # CP-SAT + SA objective must be <= CP-SAT objective for all scenarios
    assert (df_sa["objective"] <= df_cpsat["objective"] + 1e-9).all()


def test_end_to_end_single_scenario_flow() -> None:
    """Execute a single scenario end-to-end to verify flow without disk dependence."""
    from src.models.probabilistic.dependence import (
        GaussianCopulaDependenceModel,
        StudentTMarginalDistribution,
    )

    n_flights = 15
    n_contact_gates = 5

    marginals = [
        StudentTMarginalDistribution(mu=15.0, sigma=12.0, df=4.0)
        for _ in range(n_flights)
    ]
    flight_df = pd.DataFrame(
        {
            "scheduled_departure_hour": [8 + (i % 8) for i in range(n_flights)],
            "scheduled_departure_minute": [(i * 10) % 60 for i in range(n_flights)],
            "CRS_ELAPSED_TIME": [120.0] * n_flights,
            "OP_CARRIER": ["DL" if i % 2 == 0 else "AA" for i in range(n_flights)],
            "OP_CARRIER_FL_NUM": [str(100 + i) for i in range(n_flights)],
            "flight_key": [f"FL_{i:03d}" for i in range(n_flights)],
        }
    )

    dep_model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0)
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    # 1. Sample scenario delays
    sampled_delays = runner.run_scenarios(marginals, flight_df, n_scenarios=1, rng=42)[0]

    # 2. Synthesize turns
    turn_model = AircraftTurnModel()
    turns = turn_model.synthesize_batch(flight_df, sampled_delays)
    flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(turns)]

    # 3. Define gates
    gates = [Gate(gate_id=f"G_{i}", gate_index=i, is_overflow=False) for i in range(n_contact_gates)]
    gates.append(Gate(gate_id="OVERFLOW", gate_index=n_contact_gates, is_overflow=True))

    # 4. Solvers comparison
    cfg = GateOptimizationConfig()
    greedy = DeterministicGreedyGateSolver(config=cfg)
    cpsat = CPSatGateSolver(config=cfg)
    sa = SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=100, seed=42))

    res_g = greedy.solve(flights, gates)
    res_cp = cpsat.solve(flights, gates)
    res_sa = sa.solve(flights, gates, initial_assignments=res_cp.assignments)

    # All must be feasible with 0 conflicts
    assert res_g.feasible and res_cp.feasible and res_sa.feasible
    assert res_g.constraint_diagnostics.conflict_count == 0
    assert res_cp.constraint_diagnostics.conflict_count == 0
    assert res_sa.constraint_diagnostics.conflict_count == 0

    # Monotonicity
    assert res_cp.objective_value <= res_g.objective_value + 1e-9
    assert res_sa.objective_value <= res_cp.objective_value + 1e-9
