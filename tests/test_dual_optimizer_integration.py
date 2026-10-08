"""Integration, Parity, and Role Access Control Tests for Dual Core Gate Optimization.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P8 Dual Core Gate Optimizer Integration & Solver Parity
Test Coverage:
1. Section 7A: Legacy Parity Matrix (flag OFF -> bit-for-bit / solution identical to legacy across all 4 solvers)
2. Section 7B: Dual Core Active Mode Matrix (flag ON -> D_ml replaces D_old, physical turnaround respected)
3. Section 7C: Role-Based Access Control & Fail-Closed Guard Matrix:
   - Auxiliary Departure rejection (RoleAccessViolationError)
   - Uncertified Core Departure rejection (UncertifiedModelError)
   - Unknown Model rejection (UncertifiedModelError)
   - Missing departure_model_id rejection (ValueError)
   - Physical turnaround feasibility guard rejection (ValueError)
   - Non-finite delay rejection (ValueError)
4. Section 7D: Independent Hard Constraint Verifier Audit:
   - Independent verification across Greedy, CP-SAT, SA, and Hybrid solvers.
"""

from __future__ import annotations

import math
from datetime import datetime
import pytest

from src.contracts.turn_contracts import FlightLeg, LegDirection, PairType, TurnPair
from src.models.interfaces import ModelCategory, ModelSpec, ModelStatus, ModelTask
from src.models.registry import _MODEL_CATALOG, register_model, unregister_model
from src.optimization.adapter import (
    DualCoreGateOptimizerAdapter,
    RoleAccessViolationError,
    UncertifiedModelError,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.dual_prediction_turn import (
    DualAircraftTurn,
    DualTurnEngine,
    SimulationMode,
)


# =============================================================================
# Test Fixtures & Synthetic Flight Builders
# =============================================================================

@pytest.fixture
def sample_gates() -> list[Gate]:
    """Standard 5 contact gates + 1 overflow stand."""
    return [
        Gate(gate_id="G1", gate_index=0, is_overflow=False),
        Gate(gate_id="G2", gate_index=1, is_overflow=False),
        Gate(gate_id="G3", gate_index=2, is_overflow=False),
        Gate(gate_id="G4", gate_index=3, is_overflow=False),
        Gate(gate_id="G5", gate_index=4, is_overflow=False),
        Gate(gate_id="OVERFLOW_APRON", gate_index=5, is_overflow=True),
    ]


@pytest.fixture
def synthetic_turns() -> list[DualAircraftTurn]:
    """Synthesize a reproducible schedule of 8 aircraft turns with varying delays."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    turns: list[DualAircraftTurn] = []

    # Staggered arrivals and departures across a 4-hour window
    scenarios = [
        ("T1", "DL", "101", 600, 690, 10.0, 15.0),   # Arr 610, Dep_ml 705, Phys 655 -> Pushback 705
        ("T2", "DL", "102", 610, 710, -5.0, 30.0),   # Arr 605, Dep_ml 740, Phys 650 -> Pushback 740
        ("T3", "AA", "201", 620, 720, 20.0, 45.0),   # Arr 640, Dep_ml 765, Phys 685 -> Pushback 765
        ("T4", "UA", "301", 630, 715, 0.0, -10.0),   # Arr 630, Dep_ml 705, Phys 675 -> Pushback 705
        ("T5", "DL", "103", 660, 750, 15.0, 20.0),   # Arr 675, Dep_ml 770, Phys 720 -> Pushback 770
        ("T6", "WN", "401", 680, 770, -10.0, -5.0),  # Arr 670, Dep_ml 765, Phys 715 -> Pushback 765
        ("T7", "AA", "202", 700, 790, 30.0, 50.0),   # Arr 730, Dep_ml 840, Phys 775 -> Pushback 840
        ("T8", "DL", "104", 720, 810, 5.0, 10.0),    # Arr 725, Dep_ml 820, Phys 770 -> Pushback 820
    ]

    for turn_id, carrier, fl_num, arr_sched, dep_sched, arr_delay, dep_delay in scenarios:
        arr_leg = FlightLeg(
            flight_id=f"ARR_{turn_id}",
            direction=LegDirection.ARR,
            carrier=carrier,
            flight_number=fl_num,
            origin="MIA",
            destination="ATL",
            scheduled_event_local=datetime(2024, 1, 1, arr_sched // 60, arr_sched % 60),
            normalized_timeline_min=arr_sched,
        )
        dep_leg = FlightLeg(
            flight_id=f"DEP_{turn_id}",
            direction=LegDirection.DEP,
            carrier=carrier,
            flight_number=fl_num,
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2024, 1, 1, dep_sched // 60, dep_sched % 60),
            normalized_timeline_min=dep_sched,
        )
        pair = TurnPair(
            pair_id=f"PAIR_{turn_id}",
            arrival_leg_id=f"ARR_{turn_id}",
            departure_leg_id=f"DEP_{turn_id}",
            pair_type=PairType.SYNTHETIC_PAIR,
            scenario_id="p8_parity_test",
        )
        turn = engine.synthesize_turn(
            pair=pair,
            legs={f"ARR_{turn_id}": arr_leg, f"DEP_{turn_id}": dep_leg},
            arrival_prediction=arr_delay,
            departure_prediction=dep_delay,
            mode=SimulationMode.DUAL_POINT,
        )
        turns.append(turn)

    return turns


# =============================================================================
# Section 7A: Legacy Parity Matrix (dual_core_gate_enabled = False)
# =============================================================================

class TestLegacyParityMatrix:
    """Verifies 100% legacy parity when dual_core_gate_enabled is OFF."""

    @pytest.mark.parametrize(
        "solver_name,solver_factory",
        [
            ("Greedy", lambda cfg: DeterministicGreedyGateSolver(config=cfg)),
            ("CPSat", lambda cfg: CPSatGateSolver(config=cfg)),
            ("SA", lambda cfg: SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=100))),
            ("Hybrid", lambda cfg: HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=100))),
        ],
    )
    def test_legacy_parity_across_all_four_solvers(
        self,
        solver_name: str,
        solver_factory,
        sample_gates: list[Gate],
        synthetic_turns: list[DualAircraftTurn],
    ) -> None:
        """When flag is OFF, DualCoreGateOptimizerAdapter produces identical assignments to legacy flights."""
        legacy_cfg = GateOptimizationConfig(dual_core_gate_enabled=False, random_seed=42)
        adapter = DualCoreGateOptimizerAdapter(config=legacy_cfg)

        # Baseline: convert directly to legacy flights (dual_core_enabled=False)
        baseline_flights = [t.to_flight(idx, dual_core_enabled=False) for idx, t in enumerate(synthetic_turns)]
        for f in baseline_flights:
            assert f.precomputed_gate_out_min is None

        # Adapter: convert turns under adapter with flag OFF
        adapter_flights = adapter.turns_to_flights(synthetic_turns)
        for f_base, f_adapt in zip(baseline_flights, adapter_flights):
            assert f_base.flight_id == f_adapt.flight_id
            assert f_base.precomputed_gate_out_min is None
            assert f_adapt.precomputed_gate_out_min is None
            assert f_base.simulated_departure_min == f_adapt.simulated_departure_min
            assert f_base.time_window == f_adapt.time_window

        # Run solver directly on baseline vs adapter
        solver_base = solver_factory(legacy_cfg)
        solver_adapt = solver_factory(legacy_cfg)

        res_base = solver_base.solve(baseline_flights, sample_gates, allow_overflow=True)
        res_adapt = adapter.solve(solver_adapt, synthetic_turns, sample_gates, allow_overflow=True)

        # Exact parity assertions
        assert res_base.feasible == res_adapt.feasible
        assert res_base.status == res_adapt.status
        assert pytest.approx(res_base.objective_value, rel=1e-5) == res_adapt.objective_value

        for f_id in res_base.assignments:
            assert res_base.assignments[f_id].gate_id == res_adapt.assignments[f_id].gate_id
            assert res_base.assignments[f_id].is_overflow == res_adapt.assignments[f_id].is_overflow


# =============================================================================
# Section 7B: Dual Core Active Mode Matrix (dual_core_gate_enabled = True)
# =============================================================================

class TestDualCoreActiveModeMatrix:
    """Verifies that enabling dual core incorporates Departure ML pushback."""

    def test_dual_flights_reflect_departure_ml(
        self,
        synthetic_turns: list[DualAircraftTurn],
    ) -> None:
        """When enabled, flights receive precomputed_gate_out_min matching turn pushback."""
        cfg = GateOptimizationConfig(dual_core_gate_enabled=True)
        adapter = DualCoreGateOptimizerAdapter(config=cfg)

        flights = adapter.turns_to_flights(
            synthetic_turns,
            departure_model_id="departure_certified_point_v1",
        )

        for turn, flight in zip(synthetic_turns, flights):
            assert flight.precomputed_gate_out_min == turn.simulated_departure_min
            assert flight.simulated_departure_min == turn.simulated_departure_min
            # Physical turnaround invariant: pushback >= arrival + turnaround
            assert flight.simulated_departure_min >= flight.predicted_arrival_min + flight.min_turnaround_min
            # Authoritative window matching turn release
            assert flight.time_window.end_min == turn.gate_release_min

    @pytest.mark.parametrize(
        "solver_name,solver_factory",
        [
            ("Greedy", lambda cfg: DeterministicGreedyGateSolver(config=cfg)),
            ("CPSat", lambda cfg: CPSatGateSolver(config=cfg)),
            ("SA", lambda cfg: SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=100))),
            ("Hybrid", lambda cfg: HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=100))),
        ],
    )
    def test_all_four_solvers_solve_dual_mode_with_zero_violations(
        self,
        solver_name: str,
        solver_factory,
        sample_gates: list[Gate],
        synthetic_turns: list[DualAircraftTurn],
    ) -> None:
        """All 4 solvers find feasible solutions under dual core with 0 hard constraint violations."""
        cfg = GateOptimizationConfig(dual_core_gate_enabled=True, random_seed=42)
        adapter = DualCoreGateOptimizerAdapter(config=cfg)
        solver = solver_factory(cfg)

        result = adapter.solve(
            solver=solver,
            turns=synthetic_turns,
            gates=sample_gates,
            departure_model_id="departure_certified_point_v1",
            allow_overflow=True,
        )

        assert result.feasible is True
        assert result.constraint_diagnostics.is_valid is True
        assert result.constraint_diagnostics.hard_constraint_violations_count == 0
        assert result.constraint_diagnostics.conflict_count == 0

        # Independent outside verification
        flights = adapter.turns_to_flights(synthetic_turns, departure_model_id="departure_certified_point_v1")
        diag = verify_hard_constraints_independently(
            flights=flights,
            gates=sample_gates,
            assignments=result.assignments,
        )
        assert diag.is_valid is True
        assert diag.hard_constraint_violations_count == 0
        assert diag.conflict_count == 0


# =============================================================================
# Section 7C: Role-Based Access Control & Fail-Closed Guards
# =============================================================================

class TestRoleBasedAccessControlAndGuards:
    """Verifies security firewalls, role checks, and fail-closed integrity."""

    def test_auxiliary_departure_model_strictly_rejected(self) -> None:
        """Auxiliary Departure models must be blocked with RoleAccessViolationError."""
        adapter = DualCoreGateOptimizerAdapter()
        with pytest.raises(RoleAccessViolationError, match="Auxiliary Departure"):
            adapter.validate_departure_model("departure_auxiliary_baseline_v1")

    def test_uncertified_core_departure_model_rejected(self) -> None:
        """Core Departure models without GATE_OUT_PREDICTION must be blocked with UncertifiedModelError."""
        adapter = DualCoreGateOptimizerAdapter()
        # departure_xgboost_baseline_v1 has selection_role="core_departure_xgboost_baseline", downstream_eligible=False
        with pytest.raises(UncertifiedModelError, match="Requires certified selection_role='GATE_OUT_PREDICTION'"):
            adapter.validate_departure_model("departure_xgboost_baseline_v1")

    def test_unknown_model_fails_closed(self) -> None:
        """Unknown or unregistered models fail closed with UncertifiedModelError."""
        adapter = DualCoreGateOptimizerAdapter()
        with pytest.raises(UncertifiedModelError, match="unknown or not registered"):
            adapter.validate_departure_model("nonexistent_unknown_dep_model")

    def test_arrival_model_rejected_for_departure_role(self) -> None:
        """Arrival models cannot be passed as departure models."""
        adapter = DualCoreGateOptimizerAdapter()
        with pytest.raises(RoleAccessViolationError, match="expected 'core_departure'"):
            adapter.validate_departure_model("arrival_linear_baseline_v1")

    def test_departure_model_id_mandatory_when_dual_enabled(
        self,
        synthetic_turns: list[DualAircraftTurn],
    ) -> None:
        """When dual_core_gate_enabled is True, missing departure_model_id raises ValueError."""
        cfg = GateOptimizationConfig(dual_core_gate_enabled=True)
        adapter = DualCoreGateOptimizerAdapter(config=cfg)
        with pytest.raises(ValueError, match="departure_model_id is required"):
            adapter.turns_to_flights(synthetic_turns, departure_model_id=None)

    def test_physical_turnaround_violation_in_flight_rejected(self) -> None:
        """Flight domain must fail closed if precomputed_gate_out_min violates physical turnaround."""
        with pytest.raises(ValueError, match="violates physical minimum turnaround"):
            Flight(
                flight_id="FL_INVALID_TURNAROUND",
                flight_index=0,
                carrier="DL",
                flight_number="100",
                scheduled_arrival_min=600,
                scheduled_departure_min=690,
                predicted_arrival_min=620,
                min_turnaround_min=45,  # Requires pushback >= 620 + 45 = 665
                precomputed_gate_out_min=650,  # ILLEGAL: 650 < 665
            )

    def test_non_finite_values_in_flight_rejected(self) -> None:
        """Flight domain entity must reject NaN / Inf values."""
        with pytest.raises(ValueError, match="must be finite"):
            Flight(
                flight_id="FL_NAN",
                flight_index=0,
                carrier="DL",
                flight_number="100",
                scheduled_arrival_min=600,
                scheduled_departure_min=690,
                predicted_arrival_min=620,
                min_turnaround_min=45,
                precomputed_gate_out_min=float("nan"),  # type: ignore[arg-type]
            )

        with pytest.raises(ValueError, match="must be finite"):
            Flight(
                flight_id="FL_INF",
                flight_index=0,
                carrier="DL",
                flight_number="100",
                scheduled_arrival_min=600,
                scheduled_departure_min=690,
                predicted_arrival_min=float("inf"),  # type: ignore[arg-type]
                min_turnaround_min=45,
            )


# =============================================================================
# Section 7D: Hybrid Solver Architectural Correctness
# =============================================================================

class TestHybridSolverArchitecture:
    """Verifies HybridGateSolver behavior, zero flights, and invalid configs."""

    def test_hybrid_solver_zero_flights(self, sample_gates: list[Gate]) -> None:
        """HybridGateSolver handles empty flight input cleanly."""
        solver = HybridGateSolver()
        res = solver.solve([], sample_gates)
        assert res.feasible is True
        assert res.status == "OPTIMAL"
        assert res.objective_value == 0.0
        assert len(res.assignments) == 0

    def test_hybrid_solver_invalid_cp_ratio(self) -> None:
        """cp_ratio must be strictly between 0 and 1."""
        with pytest.raises(ValueError, match="cp_ratio must be strictly between 0 and 1"):
            HybridGateSolver(cp_ratio=0.0)
        with pytest.raises(ValueError, match="cp_ratio must be strictly between 0 and 1"):
            HybridGateSolver(cp_ratio=1.0)
