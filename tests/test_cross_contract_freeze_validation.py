"""Cross-Contract End-to-End Validation for Phase 10 System Freeze.

Validates the full operational pipeline without schema mismatch:
Prediction
  -> Distribution
  -> Dependence / Common Latent
  -> Monte Carlo
  -> AircraftTurn
  -> Gate Assignment
  -> Solvers (Greedy / CP-SAT / SA)
  -> Independent Verification
  -> Evaluator
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.contracts.distribution import NGBoostStudentTDistribution
from src.evaluation.downstream_comparison import build_scenario_gates
from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    MonteCarloScenarioSpec,
    generate_common_latent_variables,
    run_monte_carlo_evaluation,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import verify_hard_constraints_independently
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts


def test_cross_contract_pipeline_end_to_end() -> None:
    """Validate seamless data flow across all 9 protocol stages."""
    n_flights = 12
    n_contact_gates = 4
    seed = PREDETERMINED_DEPLOYMENT_SEED

    # 1. Feature & Schedule Representation
    df = pd.DataFrame({
        "flight_key": [f"FL_{i:03d}" for i in range(n_flights)],
        "OP_CARRIER": ["DL", "AA", "UA"] * (n_flights // 3),
        "OP_CARRIER_FL_NUM": [1000 + i for i in range(n_flights)],
        "_sched_arr_min": [720 + i * 20 for i in range(n_flights)],
        "nominal_gate_id": [f"G_{(i % n_contact_gates) + 1:02d}" for i in range(n_flights)],
        "ARR_DELAY": [12.0] * n_flights,
    })

    spec = MonteCarloScenarioSpec(
        scenario_id="FREEZE_VALIDATION_SCENARIO",
        date_str="2023-07-03",
        n_flights=n_flights,
        n_contact_gates=n_contact_gates,
        flights_df=df,
        spec_hash="freeze_hash_001",
    )

    # 2. Predictive Distribution Contract
    mu = np.array([10.0 + i for i in range(n_flights)])
    sigma = np.full(n_flights, 15.0)
    df_param = np.full(n_flights, 4.0)

    dist = NGBoostStudentTDistribution(
        mu=mu,
        sigma=sigma,
        df=df_param,
    )
    dist.validate()
    assert len(dist.mean) == n_flights
    assert len(dist.median) == n_flights

    # 3. Dependence & Latent Scenario Sampling (Monte Carlo)
    n_scen = 50
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=seed)
    assert latent_u.shape == (n_scen, n_flights)

    delay_matrix = MonteCarloDelayTransformer.transform(
        model_id="P4_ngboost_student_t",
        latent_u=latent_u,
        base_delays=dist.mean,
        residual_sigma=15.0,
        student_t_df=4.0,
    )
    assert delay_matrix.shape == (n_scen, n_flights)

    # 4. AircraftTurn Synthesis & Gate Occupancy Intervals
    turn_model = AircraftTurnModel(
        min_turnaround_min=45,
        default_dwell_min=60,
        separation_buffer_min=15,
    )

    contact_gates, overflow_gate = build_scenario_gates(n_contact_gates)
    all_gates = contact_gates + [overflow_gate]

    sample_delays = delay_matrix[0]
    turns = [
        turn_model.synthesize_turn(
            flight_id=str(df.loc[i, "flight_key"]),
            carrier=str(df.loc[i, "OP_CARRIER"]),
            flight_number=str(df.loc[i, "OP_CARRIER_FL_NUM"]),
            scheduled_arrival_min=int(df.loc[i, "_sched_arr_min"]),
            sampled_delay_min=float(sample_delays[i]),
            nominal_gate_id=str(df.loc[i, "nominal_gate_id"]),
        )
        for i in range(n_flights)
    ]
    flights_domain = [t.to_flight(i) for i, t in enumerate(turns)]
    assert len(flights_domain) == n_flights

    # 5. Solver Execution: Greedy, CP-SAT, and SA
    opt_config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        time_limit_seconds=2.0,
        random_seed=seed,
    )
    sa_config = SAConfig(iterations=100, seed=seed)

    greedy_solver = DeterministicGreedyGateSolver(config=opt_config)
    cpsat_solver = CPSatGateSolver(config=opt_config)
    sa_solver = SimulatedAnnealingGateSolver(config=opt_config, sa_config=sa_config)

    res_greedy = greedy_solver.solve(flights_domain, all_gates, allow_overflow=True)
    res_cpsat = cpsat_solver.solve(flights_domain, all_gates, allow_overflow=True)
    res_sa = sa_solver.solve(flights_domain, all_gates, allow_overflow=True)

    # 6. Independent Verification & Evaluator for Each Solution
    for solver_name, res in [("Greedy", res_greedy), ("CPSat", res_cpsat), ("SA", res_sa)]:
        assert res.assignments is not None
        assert len(res.assignments) == n_flights

        # Independent verification
        diagnostics = verify_hard_constraints_independently(
            flights=flights_domain,
            gates=all_gates,
            assignments=res.assignments,
        )
        assert diagnostics.is_valid is True
        assert diagnostics.conflict_count == 0

        # Conflict detector
        conflict_res = detect_conflicts(
            assignments=res.assignments,
            turns=turns,
            gates=all_gates,
        )
        assert conflict_res.conflict_count == 0

        # Evaluator
        eval_res = evaluate_gate_assignment(
            assignments=res.assignments,
            flights=flights_domain,
            gates=all_gates,
            config=opt_config,
            solver_name=solver_name,
        )
        assert eval_res.feasible is True
        assert np.isfinite(eval_res.objective_value)
        assert eval_res.objective_breakdown.conflict_cost == 0.0

    # 7. Full Monte Carlo Execution without Truncation
    records = run_monte_carlo_evaluation(
        model_id="P4_ngboost_student_t",
        spec=spec,
        delay_matrix=delay_matrix,
        requested_n=n_scen,
        seed=seed,
        config=opt_config,
    )
    assert len(records) == n_scen
    assert all(r.status == "COMPLETED" for r in records)
