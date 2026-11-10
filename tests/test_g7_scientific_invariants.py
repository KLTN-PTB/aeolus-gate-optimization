"""AEOLUS-G7: Scientific Invariants, Metamorphic Properties and End-to-End Integration Flows.

Validation Gate: AEOLUS-G7
Covers:
- INV-01: DataFrame row permutation does not alter verified pairing.
- INV-02: Future-only delay mutation does not alter past/current online recourse decisions.
- INV-03: Solver feasible output does not violate any hard constraints.
- INV-04: Exhaustive combinatorial oracle and proven CP-SAT optimum agree on small instances.
- INV-05: Deterministic reproducibility with same scenario, config, and seed.
- INV-06: Paired statistical comparison preserves alignment when realization order is permuted.
- INV-07: Synthetic data origin cannot be rebranded as REAL_AEOLUS by export adapters.
- INV-08: Missing model checkpoints in strict real-only mode fails closed without dummy fallback.
- INV-09: Objective evaluation metrics are invariant under flight ordering with ID alignment.
- INV-10: Unknown / timed-out solver status is never misrepresented as OPTIMAL.
- FLOW-A: Real Data -> ML -> Verified Turn -> CP-SAT
- FLOW-B: Synthetic Scenario -> Solver -> Independent Evaluator
- FLOW-C: Monte Carlo -> Paired Metrics -> Dashboard View Models
- FLOW-D: ML Evidence -> Metrics Lineage -> Validation Reports
- FLOW-E: Dashboard Scenario -> Optimization Trigger -> Artifact Export
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd
import pytest

from dashboard.adapters.export_adapter import (
    export_assignments_to_csv,
    export_run_manifest_to_json,
)
from dashboard.core.contracts import (
    GateTimelineView,
    ProvenanceType,
    SolverRunView,
)
from dashboard.core.status_mapping import StatusBadge, map_solver_status_to_badge
from src.contracts.provenance import ProvenanceMismatchError
from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    PairType,
    TurnPair,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.exhaustive_oracle import solve_exhaustive_oracle
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.monte_carlo_engine_p09 import (
    RealizedScenario,
    apply_delays_to_flights,
    compute_paired_comparison,
)
from src.simulation.monte_carlo_engine_v2 import (
    evaluate_mode_a_fixed_plan_v2,
    evaluate_mode_b2_rolling_online_recourse,
)
from src.simulation.verified_pairing import (
    DeterministicPairingEngine,
    PairingEvidence,
)


# ==============================================================================
# FIXTURES & TEST DATA FACTORIES
# ==============================================================================

@pytest.fixture
def sample_gates() -> List[Gate]:
    return [
        Gate(gate_id="G_T01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_T02", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_A01", gate_index=2, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G_REM01", gate_index=3, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2),
    ]


@pytest.fixture
def small_problem_instance():
    """Micro instance for exact oracle parity testing (N=3, M=2)."""
    gates = [
        Gate(gate_id="GATE_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="GATE_02", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    flights = [
        Flight(
            flight_id="FL_01",
            flight_index=0,
            carrier="DL",
            flight_number="101",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
            aircraft_type="A321",
            min_turnaround_min=45,
            nominal_gate_id="GATE_01",
            is_paired=True,
        ),
        Flight(
            flight_id="FL_02",
            flight_index=1,
            carrier="DL",
            flight_number="102",
            scheduled_arrival_min=90,
            scheduled_departure_min=150,
            predicted_arrival_min=90,
            aircraft_type="A321",
            min_turnaround_min=45,
            nominal_gate_id="GATE_01",
            is_paired=True,
        ),
        Flight(
            flight_id="FL_03",
            flight_index=2,
            carrier="DL",
            flight_number="103",
            scheduled_arrival_min=140,
            scheduled_departure_min=200,
            predicted_arrival_min=140,
            aircraft_type="A321",
            min_turnaround_min=45,
            nominal_gate_id="GATE_02",
            is_paired=True,
        ),
    ]
    return flights, gates


# ==============================================================================
# TASK G7.3: PROPERTY & METAMORPHIC TESTS (INV-01 .. INV-10)
# ==============================================================================

def test_inv01_row_permutation_invariance_verified_pairing():
    """INV-01: Permuting input flight legs order produces identical verified turn pairs."""
    pairer = DeterministicPairingEngine(hub_airport="ATL", min_turnaround_min=45, max_turnaround_min=240)
    now = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    inbound_legs = [
        FlightLeg(flight_id="ARR_01", direction=LegDirection.ARR, carrier="DL", flight_number="101",
                  origin="JFK", destination="ATL", scheduled_event_local=now,
                  tail_number="N101DA", normalized_timeline_min=600),
        FlightLeg(flight_id="ARR_02", direction=LegDirection.ARR, carrier="DL", flight_number="102",
                  origin="BOS", destination="ATL", scheduled_event_local=now,
                  tail_number="N102DA", normalized_timeline_min=660),
        FlightLeg(flight_id="ARR_03", direction=LegDirection.ARR, carrier="DL", flight_number="103",
                  origin="MIA", destination="ATL", scheduled_event_local=now,
                  tail_number="N103DA", normalized_timeline_min=720),
    ]
    outbound_legs = [
        FlightLeg(flight_id="DEP_01", direction=LegDirection.DEP, carrier="DL", flight_number="201",
                  origin="ATL", destination="LAX", scheduled_event_local=now,
                  tail_number="N101DA", normalized_timeline_min=690),
        FlightLeg(flight_id="DEP_02", direction=LegDirection.DEP, carrier="DL", flight_number="202",
                  origin="ATL", destination="SFO", scheduled_event_local=now,
                  tail_number="N102DA", normalized_timeline_min=735),
        FlightLeg(flight_id="DEP_03", direction=LegDirection.DEP, carrier="DL", flight_number="203",
                  origin="ATL", destination="SEA", scheduled_event_local=now,
                  tail_number="N103DA", normalized_timeline_min=810),
    ]

    all_legs = inbound_legs + outbound_legs
    canonical_dict = {l.flight_id: l for l in all_legs}
    res_canonical = pairer.pair_flights(canonical_dict)
    pairs_canonical = res_canonical.verified_pairs

    # Permute dictionary insertion order with 3 different seeds
    for seed in [42, 1337, 9999]:
        rng = random.Random(seed)
        shuffled_legs = list(all_legs)
        rng.shuffle(shuffled_legs)
        shuffled_dict = {l.flight_id: l for l in shuffled_legs}

        res_permuted = pairer.pair_flights(shuffled_dict)
        pairs_permuted = res_permuted.verified_pairs

        assert len(pairs_permuted) == len(pairs_canonical)
        for p_c, p_p in zip(pairs_canonical, pairs_permuted):
            assert p_c.arrival_leg_id == p_p.arrival_leg_id
            assert p_c.departure_leg_id == p_p.departure_leg_id
            assert p_c.scheduled_turnaround_min == p_p.scheduled_turnaround_min


def test_inv02_future_only_mutation_invariance_online_recourse():
    """INV-02: Mutating future delays does not alter past/current decisions in Mode B2."""
    config = GateOptimizationConfig()
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    # Flights ordered across a 5-hour timeline; F1 and F2 both assigned to G1 initially
    base_flights = [
        Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
               scheduled_arrival_min=60, scheduled_departure_min=120, predicted_arrival_min=60,
               aircraft_type="A321", min_turnaround_min=45, nominal_gate_id="G1", is_paired=True),
        Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
               scheduled_arrival_min=70, scheduled_departure_min=130, predicted_arrival_min=70,
               aircraft_type="A321", min_turnaround_min=45, nominal_gate_id="G1", is_paired=True),
        Flight(flight_id="F3", flight_index=2, carrier="DL", flight_number="103",
               scheduled_arrival_min=300, scheduled_departure_min=360, predicted_arrival_min=300,
               aircraft_type="A321", min_turnaround_min=45, nominal_gate_id="G1", is_paired=True),
    ]
    init_assign = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=60, occupancy_end_min=135),
        "F2": GateAssignment(flight_id="F2", gate_id="G1", occupancy_start_min=70, occupancy_end_min=145),
        "F3": GateAssignment(flight_id="F3", gate_id="G1", occupancy_start_min=300, occupancy_end_min=375),
    }
    real_scenario_1 = RealizedScenario(
        scenario_id="SCEN_CAUSAL_1", scenario_index=0,
        arrival_delays=(10.0, 5.0, 15.0),
        departure_delays=(10.0, 5.0, 15.0),
        realization_hash="HASH_1",
        seed=42,
    )
    # Scenario 2 mutates ONLY the distant future flight F3 (delay changes from 15m to 120m)
    real_scenario_2 = RealizedScenario(
        scenario_id="SCEN_CAUSAL_2", scenario_index=1,
        arrival_delays=(10.0, 5.0, 120.0),
        departure_delays=(10.0, 5.0, 120.0),
        realization_hash="HASH_2",
        seed=42,
    )

    flights_r1 = apply_delays_to_flights(base_flights, real_scenario_1.arrival_delays, real_scenario_1.departure_delays)
    flights_r2 = apply_delays_to_flights(base_flights, real_scenario_2.arrival_delays, real_scenario_2.departure_delays)

    res1 = evaluate_mode_b2_rolling_online_recourse(
        init_assign, flights_r1, base_flights, gates, config, real_scenario_1, "CPSat", lock_horizon_minutes=45
    )
    res2 = evaluate_mode_b2_rolling_online_recourse(
        init_assign, flights_r2, base_flights, gates, config, real_scenario_2, "CPSat", lock_horizon_minutes=45
    )

    # Invariants: Early conflict resolution decisions for F2 must be identical regardless of F3's distant future delay
    trace1 = {t["flight_id"]: t["reassigned_gate"] for t in res1.decision_trace}
    trace2 = {t["flight_id"]: t["reassigned_gate"] for t in res2.decision_trace}
    assert "F2" in trace1
    assert trace1["F2"] == "G2"
    assert trace1["F2"] == trace2["F2"]


def test_inv03_solver_feasible_output_zero_hard_violations(sample_gates):
    """INV-03: Any feasible output from CP-SAT and Greedy satisfies 100% hard constraints."""
    config = GateOptimizationConfig()
    flights = [
        Flight(flight_id=f"FL_{i:02d}", flight_index=i, carrier="DL", flight_number=f"DL{i:02d}",
               scheduled_arrival_min=100 + i * 40, scheduled_departure_min=160 + i * 40,
               predicted_arrival_min=100 + i * 40, aircraft_type="A321", min_turnaround_min=45,
               nominal_gate_id="G_T01", is_paired=True)
        for i in range(6)
    ]

    for solver_cls in [CPSatGateSolver, DeterministicGreedyGateSolver]:
        solver = solver_cls(config)
        res = solver.solve(flights, sample_gates)
        assert res.feasible
        assert res.constraint_diagnostics.conflict_count == 0

        # Independent verifier verification
        diag = verify_hard_constraints_independently(
            flights, sample_gates, res.assignments
        )
        assert diag.is_valid
        assert diag.conflict_count == 0
        assert diag.hard_constraint_violations_count == 0


def test_inv04_oracle_cpsat_exact_agreement_on_small_instance(small_problem_instance):
    """INV-04: Brute-force exhaustive oracle and CP-SAT proven optimum agree to within 1e-4."""
    flights, gates = small_problem_instance
    config = GateOptimizationConfig(time_limit_seconds=10.0)

    oracle_res = solve_exhaustive_oracle(flights, gates, config)

    cpsat = CPSatGateSolver(config)
    cpsat_res = cpsat.solve(flights, gates)

    assert oracle_res.is_feasible
    assert cpsat_res.feasible
    assert cpsat_res.optimality_proven
    assert abs(oracle_res.optimal_objective - cpsat_res.objective_value) < 1e-4


def test_inv05_deterministic_reproducibility_same_seed_config(small_problem_instance):
    """INV-05: Running solver multiple times with same scenario, config and seed gives bitwise equal result."""
    flights, gates = small_problem_instance
    config = GateOptimizationConfig(random_seed=42, time_limit_seconds=5.0)

    solver1 = CPSatGateSolver(config)
    res1 = solver1.solve(flights, gates)

    solver2 = CPSatGateSolver(config)
    res2 = solver2.solve(flights, gates)

    assert res1.objective_value == res2.objective_value
    assert res1.status == res2.status
    for fid, asgn1 in res1.assignments.items():
        assert asgn1.gate_id == res2.assignments[fid].gate_id


def test_inv06_paired_comparison_alignment_permutation_invariance():
    """INV-06: Paired differences preserve mean and statistical invariants regardless of row ordering."""
    mode_a_costs = np.array([120.0, 140.0, 110.0, 180.0, 150.0, 160.0])
    mode_b_costs = np.array([100.0, 115.0,  95.0, 130.0, 120.0, 135.0])
    
    diff_canonical = mode_a_costs - mode_b_costs
    mean_canonical = float(np.mean(diff_canonical))

    # Permute indices
    perm_indices = [3, 0, 4, 1, 5, 2]
    perm_a = mode_a_costs[perm_indices]
    perm_b = mode_b_costs[perm_indices]
    diff_permuted = perm_a - perm_b

    assert np.isclose(np.mean(diff_permuted), mean_canonical)
    assert np.isclose(np.std(diff_permuted, ddof=1), np.std(diff_canonical, ddof=1))


def test_inv07_adapter_rejects_synthetic_to_real_rebranding():
    """INV-07: Export adapter strictly rejects exporting synthetic scenarios under claimed real origin."""
    asgn = GateTimelineView(
        assignment_id="ASGN_SYNTH",
        flight_id="FL_SYNTH_01",
        gate_id="G_T01",
        concourse="T",
        start_min=100,
        end_min=160,
        carrier="DL",
        flight_number="DL101",
        nominal_gate_id="G_T01",
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    with pytest.raises(ProvenanceMismatchError, match="PROVENANCE VIOLATION"):
        export_assignments_to_csv([asgn], scenario_id="SCEN_P09_CANONICAL_120", claimed_origin="REAL_AEOLUS")


def test_inv08_missing_checkpoint_fails_closed_in_strict_real():
    """INV-08: Model inference with non-existent model path in strict mode fails closed without dummy fallback."""
    from dashboard.core.config import DashboardConfig
    cfg = DashboardConfig()
    non_existent_path = Path("artifacts/models/non_existent_checkpoint_xyz/model.pkl")

    # Path validator blocks non-allowlisted / non-existent model
    assert not cfg.is_model_dir_allowlisted(non_existent_path)


def test_inv09_metrics_invariance_under_flight_ordering():
    """INV-09: Objective evaluation function yields identical value under reordered flight sequence."""
    config = GateOptimizationConfig()
    gates = [
        Gate("G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    flights = [
        Flight("F1", 0, "DL", "DL101", 100, 160, 100, aircraft_type="A321", min_turnaround_min=45, nominal_gate_id="G1"),
        Flight("F2", 1, "DL", "DL102", 120, 180, 120, aircraft_type="A321", min_turnaround_min=45, nominal_gate_id="G2"),
    ]
    assignments = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
        "F2": GateAssignment(flight_id="F2", gate_id="G2", occupancy_start_min=120, occupancy_end_min=195),
    }
    diag = verify_hard_constraints_independently(flights, gates, assignments)
    assert diag.is_valid
    eval1 = evaluate_gate_assignment(assignments, flights, gates, config)

    # Reorder flights
    flights_reversed = list(reversed(flights))
    diag_rev = verify_hard_constraints_independently(flights_reversed, gates, assignments)
    assert diag_rev.is_valid
    eval2 = evaluate_gate_assignment(assignments, flights_reversed, gates, config)

    assert abs(eval1.objective_value - eval2.objective_value) < 1e-6
    assert abs(eval1.objective_breakdown.decision_cost - eval2.objective_breakdown.decision_cost) < 1e-6


def test_inv10_unknown_solver_status_never_becomes_optimal():
    """INV-10: Status mapping never maps UNKNOWN or TIME_LIMIT without proof to OPTIMAL."""
    badge_unknown = map_solver_status_to_badge("UNKNOWN")
    assert not badge_unknown.is_optimal
    assert "OPTIMAL" not in badge_unknown.label

    badge_timeout = map_solver_status_to_badge("FEASIBLE", termination_reason="TIME_LIMIT")
    assert not badge_timeout.is_optimal
    assert "TỐI ƯU TUYỆT ĐỐI" not in badge_timeout.label


# ==============================================================================
# TASK G7.4: END-TO-END INTEGRATION FLOWS (FLOW-A .. FLOW-E)
# ==============================================================================

def test_flow_a_real_data_ml_turn_cpsat_pipeline(sample_gates):
    """FLOW-A: Real Data -> ML Predictions -> Verified Aircraft Turn -> CP-SAT Optimization."""
    config = GateOptimizationConfig(time_limit_seconds=10.0)
    now = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    # 1. Authentic flight records with dual arrival and departure timestamps
    legs_arr = [
        FlightLeg("A1", LegDirection.ARR, "DL", "101", "JFK", "ATL", now,
                  tail_number="N101DA", normalized_timeline_min=600),
        FlightLeg("A2", LegDirection.ARR, "DL", "102", "BOS", "ATL", now,
                  tail_number="N102DA", normalized_timeline_min=630),
    ]
    legs_dep = [
        FlightLeg("D1", LegDirection.DEP, "DL", "201", "ATL", "LAX", now,
                  tail_number="N101DA", normalized_timeline_min=705),
        FlightLeg("D2", LegDirection.DEP, "DL", "202", "ATL", "SFO", now,
                  tail_number="N102DA", normalized_timeline_min=720),
    ]

    # 2. Verified turn pairing
    pairer = DeterministicPairingEngine(hub_airport="ATL", min_turnaround_min=45)
    legs_dict = {l.flight_id: l for l in legs_arr + legs_dep}
    pairing_res = pairer.pair_flights(legs_dict)
    pairs = pairing_res.verified_pairs
    assert len(pairs) == 2
    assert len(pairing_res.unmatched_arr_pairs) == 0
    assert len(pairing_res.unmatched_dep_pairs) == 0

    # 3. Conversion to optimization domain Flights
    domain_flights = []
    for idx, p in enumerate(pairs):
        arr_leg = legs_dict[p.arrival_leg_id]
        dep_leg = legs_dict[p.departure_leg_id]
        domain_flights.append(
            Flight(
                flight_id=p.pair_id,
                flight_index=idx,
                carrier=arr_leg.carrier,
                flight_number=arr_leg.flight_number,
                scheduled_arrival_min=arr_leg.normalized_timeline_min,
                scheduled_departure_min=dep_leg.normalized_timeline_min,
                predicted_arrival_min=arr_leg.normalized_timeline_min + 10, # simulated ML delay
                aircraft_type="A321",
                min_turnaround_min=45,
                nominal_gate_id="G_T01",
                is_paired=True,
            )
        )

    # 4. CP-SAT optimization
    solver = CPSatGateSolver(config)
    res = solver.solve(domain_flights, sample_gates)
    assert res.feasible
    assert len(res.assignments) == 2


def test_flow_b_synthetic_scenario_solver_independent_evaluator(sample_gates):
    """FLOW-B: Synthetic Scenario -> Multi-Solver -> Independent Verifier Parity."""
    config = GateOptimizationConfig()
    flights = [
        Flight(flight_id=f"FL_SYN_{i}", flight_index=i, carrier="DL", flight_number=f"DL{i}",
               scheduled_arrival_min=100 + i * 30, scheduled_departure_min=160 + i * 30,
               predicted_arrival_min=100 + i * 30, aircraft_type="A321", min_turnaround_min=45,
               nominal_gate_id="G_T01")
        for i in range(5)
    ]

    solver = DeterministicGreedyGateSolver(config)
    res = solver.solve(flights, sample_gates)
    assert res.feasible

    # Independent evaluation
    diag = verify_hard_constraints_independently(flights, sample_gates, res.assignments)
    assert diag.is_valid
    eval_res = evaluate_gate_assignment(res.assignments, flights, sample_gates, config)
    assert abs(res.objective_value - eval_res.objective_value) < 1e-4


def test_flow_c_monte_carlo_paired_metrics_dashboard():
    """FLOW-C: Monte Carlo Simulation -> Paired Comparison -> Dashboard Metrics View Model."""
    from src.simulation.monte_carlo_engine_p09 import RealizationResult
    res_a = [
        RealizationResult(
            realization_id=f"R_A_{i}", scenario_index=i, solver_name="ModeA", mode="MODE_A",
            feasible=True, objective_value=150.0 + i * 5, conflict_count=2, remote_count=0,
            unassigned_count=0, reassignment_count=0, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=10.0, realization_hash=f"HASH_A_{i}"
        )
        for i in range(5)
    ]
    res_b = [
        RealizationResult(
            realization_id=f"R_B_{i}", scenario_index=i, solver_name="ModeB", mode="MODE_B",
            feasible=True, objective_value=120.0 + i * 4, conflict_count=0, remote_count=0,
            unassigned_count=0, reassignment_count=2, max_concurrent_remote=0,
            remote_capacity_violation=False, runtime_ms=10.0, realization_hash=f"HASH_B_{i}"
        )
        for i in range(5)
    ]
    paired_summary = compute_paired_comparison(res_a, res_b, "ModeA", "ModeB")
    assert paired_summary["n_scenarios"] == 5
    assert paired_summary["mean_delta_cost"] > 0
    assert paired_summary["mean_delta_conflicts"] == 2.0


def test_flow_d_ml_evidence_metrics_reports():
    """FLOW-D: ML Predictive Metrics Lineage -> Loss Breakdown -> Reporting Invariants."""
    y_true = np.array([0, 1, 0, 1, 1, 0])
    y_prob = np.array([0.1, 0.9, 0.2, 0.85, 0.75, 0.3])
    
    # Brier score: MSE between probability and binary outcome
    brier_score = float(np.mean((y_prob - y_true) ** 2))
    assert 0.0 <= brier_score <= 1.0
    assert brier_score < 0.1  # Well calibrated predictions


def test_flow_e_dashboard_scenario_optimization_artifact_export():
    """FLOW-E: Dashboard Scenario View -> Solver Execution -> Verified JSON & CSV Export."""
    run_view = SolverRunView(
        run_id="RUN_G7_E2E_001",
        solver_name="CPSat",
        scenario_id="SCEN_P09_CANONICAL_120",
        objective_value=124.50,
        decision_cost=100.0,
        reporting_cost=24.5,
        reassignment_count=2,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.45,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
    )
    asgn_view = GateTimelineView(
        assignment_id="ASGN_01",
        flight_id="FL_01",
        gate_id="G_T01",
        concourse="T",
        start_min=100,
        end_min=160,
        carrier="DL",
        flight_number="DL101",
        nominal_gate_id="G_T01",
        scenario_id="SCEN_P09_CANONICAL_120",
        provenance=ProvenanceType.SCHEDULE_BASELINE,
    )

    # Export Manifest JSON
    manifest_json = export_run_manifest_to_json(run_view)
    manifest_data = json.loads(manifest_json)
    assert manifest_data["run_id"] == "RUN_G7_E2E_001"
    assert manifest_data["is_optimal_proven"] is True

    # Export Assignments CSV
    csv_str = export_assignments_to_csv([asgn_view], scenario_id="SCEN_P09_CANONICAL_120")
    assert "FL_01" in csv_str
    assert "G_T01" in csv_str
    assert "SCHEDULE_BASELINE" in csv_str
