"""Unit and integration tests for Dual Prediction Turn Engine and Legacy Parity.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P7 Dual Prediction Turn Engine with Legacy Parity
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import numpy as np
import pytest

from src.contracts.distribution import GaussianResidualDistribution
from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    PairType,
    TurnPair,
)
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.dual_prediction_turn import (
    CouplingAssumption,
    DualAircraftTurn,
    DualTurnEngine,
    LegPrediction,
    SimulationMode,
)


@pytest.fixture
def base_legs() -> dict[str, FlightLeg]:
    arr_leg = FlightLeg(
        flight_id="LEG_ARR_1",
        direction=LegDirection.ARR,
        carrier="DL",
        flight_number="100",
        origin="MIA",
        destination="ATL",
        scheduled_event_local=datetime(2024, 1, 1, 10, 0),
        normalized_timeline_min=600,
    )
    dep_leg = FlightLeg(
        flight_id="LEG_DEP_1",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="101",
        origin="ATL",
        destination="ORD",
        scheduled_event_local=datetime(2024, 1, 1, 11, 30),
        normalized_timeline_min=690,
    )
    return {"LEG_ARR_1": arr_leg, "LEG_DEP_1": dep_leg}


@pytest.fixture
def paired_turn() -> TurnPair:
    return TurnPair(
        pair_id="PAIR_001",
        arrival_leg_id="LEG_ARR_1",
        departure_leg_id="LEG_DEP_1",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="scen_p7",
    )


class TestDeterministicTurnFixtures:
    """Verifies deterministic calculation and exact fixture 7A."""

    def test_deterministic_fixture_7a(self, base_legs, paired_turn):
        """Specification from P7 Section 7A:
        A_sched=10:00 (600), D_sched=11:30 (690)
        Delta_arr=+20, Delta_dep=+30
        T_min=45, B_buffer=15
        Expected: A_pred=10:20 (620), D_ml=12:00 (720), D_gate_out=12:00 (720), Gate_release=12:15 (735).
        """
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=20.0,
            departure_prediction=30.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.simulated_arrival_min == 620
        assert turn.departure_ml_min == 720
        assert turn.earliest_physical_departure_min == 665  # 620 + 45
        assert turn.simulated_departure_min == 720  # max(720, 665)
        assert turn.gate_release_min == 735  # 720 + 15
        assert turn.occupancy_duration_min == 115  # 735 - 620
        assert turn.occupancy_interval == (620, 735)

    def test_severe_arrival_delay_dominates_turnaround(self, base_legs, paired_turn):
        """Arrival delayed by 120m (arrives at 720), departure ML predicts +10m (700m).
        Physical turnaround must force departure to at least 720 + 45 = 765m.
        """
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=120.0,
            departure_prediction=10.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.simulated_arrival_min == 720
        assert turn.departure_ml_min == 700
        assert turn.earliest_physical_departure_min == 765
        assert turn.simulated_departure_min == 765  # max(700, 765) = 765
        assert turn.gate_release_min == 780  # 765 + 15

    def test_negative_signed_delay_early_departure(self, base_legs, paired_turn):
        """Departure ML predicts early departure (-20m). Signed negative delay is preserved."""
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=0.0,
            departure_prediction=-20.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.simulated_arrival_min == 600
        assert turn.departure_ml_min == 670  # 690 - 20
        assert turn.earliest_physical_departure_min == 645  # 600 + 45
        assert turn.simulated_departure_min == 670  # max(670, 645) = 670
        assert turn.gate_release_min == 685  # 670 + 15

    def test_departure_ml_before_minimum_turnaround(self, base_legs, paired_turn):
        """Departure ML predicts pushback earlier than physical servicing minimum."""
        # A_sched=600, Delta_arr=+10 -> A_pred=610 -> D_min=655
        # D_sched=690, Delta_dep=-40 -> D_ml=650
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=10.0,
            departure_prediction=-40.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.simulated_arrival_min == 610
        assert turn.departure_ml_min == 650
        assert turn.earliest_physical_departure_min == 655
        assert turn.simulated_departure_min == 655  # max(650, 655) = 655
        assert turn.gate_release_min == 670

    def test_overnight_turn(self):
        """Arrival at 23:30 (1410), Departure at 06:30 next morning (1830)."""
        legs = {
            "ARR_NIGHT": FlightLeg(
                flight_id="ARR_NIGHT",
                direction=LegDirection.ARR,
                carrier="DL",
                flight_number="500",
                origin="LAX",
                destination="ATL",
                scheduled_event_local=datetime(2024, 1, 1, 23, 30),
                normalized_timeline_min=1410,
            ),
            "DEP_MORNING": FlightLeg(
                flight_id="DEP_MORNING",
                direction=LegDirection.DEP,
                carrier="DL",
                flight_number="501",
                origin="ATL",
                destination="BOS",
                scheduled_event_local=datetime(2024, 1, 2, 6, 30),
                normalized_timeline_min=1830,
            ),
        }
        pair = TurnPair(
            pair_id="PAIR_OVERNIGHT",
            arrival_leg_id="ARR_NIGHT",
            departure_leg_id="DEP_MORNING",
            pair_type=PairType.SYNTHETIC_PAIR,
        )
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=pair,
            legs=legs,
            arrival_prediction=15.0,
            departure_prediction=-10.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.simulated_arrival_min == 1425  # 1410 + 15
        assert turn.departure_ml_min == 1820  # 1830 - 10
        assert turn.simulated_departure_min == 1820
        assert turn.gate_release_min == 1835
        assert turn.occupancy_duration_min == 410

    def test_buffer_zero_and_positive(self, base_legs, paired_turn):
        # Buffer 0
        engine_0 = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=0)
        t0 = engine_0.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=20.0,
            departure_prediction=30.0,
            mode=SimulationMode.DUAL_POINT,
        )
        assert t0.gate_release_min == t0.simulated_departure_min == 720

        # Buffer 30
        engine_30 = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=30)
        t30 = engine_30.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=20.0,
            departure_prediction=30.0,
            mode=SimulationMode.DUAL_POINT,
        )
        assert t30.gate_release_min == 750  # 720 + 30


class TestUnmatchedHandling:
    """Verifies unmatched arrival and departure synthesis policies."""

    def test_unmatched_arrival_synthetic_dwell(self, base_legs):
        pair = TurnPair(
            pair_id="PAIR_UNMATCHED_ARR",
            arrival_leg_id="LEG_ARR_1",
            departure_leg_id=None,
            pair_type=PairType.UNMATCHED_ARR,
        )
        engine = DualTurnEngine(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=pair,
            legs=base_legs,
            arrival_prediction=10.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.unmatched_status == "SYNTHETIC_DWELL"
        assert turn.simulated_arrival_min == 610
        assert turn.scheduled_departure_min == 660  # 600 + 60
        assert turn.simulated_departure_min == 660  # max(660, 610+45=655)
        assert turn.gate_release_min == 675  # 660 + 15

    def test_unmatched_departure_handling(self, base_legs):
        pair = TurnPair(
            pair_id="PAIR_UNMATCHED_DEP",
            arrival_leg_id=None,
            departure_leg_id="LEG_DEP_1",
            pair_type=PairType.UNMATCHED_DEP,
        )
        engine = DualTurnEngine(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=pair,
            legs=base_legs,
            arrival_prediction=0.0,
            departure_prediction=15.0,
            mode=SimulationMode.DUAL_POINT,
        )

        assert turn.unmatched_status == "UNSCHEDULABLE_WITH_CURRENT_INPUT"
        assert turn.simulated_departure_min == 705  # 690 + 15
        assert turn.gate_release_min == 720  # 705 + 15


class TestPredictionValidationAndCausality:
    """Verifies validation on LegPrediction objects and operational causality checks."""

    def test_prediction_postdates_planning_snapshot_rejected(self):
        snapshot_time = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        pred_future = LegPrediction(
            leg_id="LEG_ARR_1",
            direction=LegDirection.ARR,
            task="core_arrival",
            predicted_delay_min=15.0,
            model_id="core_arrival_p4_student_t",
            prediction_generated_at_utc=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),  # Postdates snapshot!
        )
        errors = pred_future.validate(planning_snapshot_at_utc=snapshot_time)
        assert any("PREDICTION_POSTDATES_PLANNING_SNAPSHOT" in e for e in errors)

    def test_invalid_unit_or_nan_rejected(self):
        pred_nan = LegPrediction(
            leg_id="LEG_1",
            direction=LegDirection.ARR,
            task="core_arrival",
            predicted_delay_min=float("nan"),
            model_id="model_v1",
        )
        errs = pred_nan.validate()
        assert any("NON_FINITE_DELAY" in e for e in errs)

        pred_unit = LegPrediction(
            leg_id="LEG_1",
            direction=LegDirection.ARR,
            task="core_arrival",
            predicted_delay_min=15.0,
            unit="seconds",  # Invalid unit
            model_id="model_v1",
        )
        errs = pred_unit.validate()
        assert any("INVALID_UNIT" in e for e in errs)


class TestLegacyBitForBitParity:
    """Verifies that ARRIVAL_ONLY_LEGACY mode is bit-for-bit identical to legacy AircraftTurnModel."""

    def test_legacy_parity_random_sweep(self, base_legs, paired_turn):
        legacy_model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
        dual_engine = DualTurnEngine(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)

        rng = np.random.RandomState(42)
        delays = rng.uniform(-30, 150, size=50)

        for delay in delays:
            legacy_turn = legacy_model.synthesize_turn(
                flight_id="PAIR_001",
                carrier="DL",
                flight_number="100",
                scheduled_arrival_min=600,
                sampled_delay_min=float(delay),
                scheduled_departure_min=690,
            )
            dual_turn = dual_engine.synthesize_turn(
                pair=paired_turn,
                legs=base_legs,
                arrival_prediction=float(delay),
                mode=SimulationMode.ARRIVAL_ONLY_LEGACY,
            )

            assert legacy_turn.simulated_arrival_min == dual_turn.simulated_arrival_min
            assert legacy_turn.scheduled_departure_min == dual_turn.scheduled_departure_min
            assert legacy_turn.simulated_departure_min == dual_turn.simulated_departure_min
            assert legacy_turn.gate_release_min == dual_turn.gate_release_min
            assert legacy_turn.occupancy_duration_min == dual_turn.occupancy_duration_min
            assert legacy_turn.occupancy_interval == dual_turn.occupancy_interval


class TestProbabilisticCouplingAndMonteCarlo:
    """Verifies Monte Carlo sampling and sensitivity coupling assumptions."""

    def test_probabilistic_scenarios_deterministic_reproducibility(self, base_legs, paired_turn):
        arr_dist = GaussianResidualDistribution(
            mu=np.array([10.0]), sigma=np.array([15.0]), candidate_id="arrival_gauss"
        )
        dep_dist = GaussianResidualDistribution(
            mu=np.array([5.0]), sigma=np.array([20.0]), candidate_id="departure_gauss"
        )

        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        scenarios_1 = engine.synthesize_probabilistic_scenarios(
            pair=paired_turn,
            legs=base_legs,
            arr_dist=arr_dist,
            dep_dist=dep_dist,
            n_scenarios=20,
            seed=42,
            coupling_assumption=CouplingAssumption.INDEPENDENT,
        )
        scenarios_2 = engine.synthesize_probabilistic_scenarios(
            pair=paired_turn,
            legs=base_legs,
            arr_dist=arr_dist,
            dep_dist=dep_dist,
            n_scenarios=20,
            seed=42,
            coupling_assumption=CouplingAssumption.INDEPENDENT,
        )

        assert len(scenarios_1) == 20
        for s in range(20):
            assert scenarios_1[s].simulated_arrival_min == scenarios_2[s].simulated_arrival_min
            assert scenarios_1[s].simulated_departure_min == scenarios_2[s].simulated_departure_min
            assert scenarios_1[s].gate_release_min == scenarios_2[s].gate_release_min

    def test_comonotonic_coupling_assumption(self, base_legs, paired_turn):
        arr_dist = GaussianResidualDistribution(
            mu=np.array([10.0]), sigma=np.array([15.0]), candidate_id="arr"
        )
        dep_dist = GaussianResidualDistribution(
            mu=np.array([10.0]), sigma=np.array([15.0]), candidate_id="dep"
        )
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        scenarios = engine.synthesize_probabilistic_scenarios(
            pair=paired_turn,
            legs=base_legs,
            arr_dist=arr_dist,
            dep_dist=dep_dist,
            n_scenarios=50,
            seed=42,
            coupling_assumption=CouplingAssumption.COMONOTONIC,
        )
        delays_arr = [s.predicted_arrival_delay_min for s in scenarios]
        delays_dep = [s.predicted_departure_delay_min for s in scenarios]

        # Comonotonic rank correlation should be exactly 1.0
        corr = float(np.corrcoef(delays_arr, delays_dep)[0, 1])
        assert corr > 0.999


class TestInvariantsExhaustiveSweep:
    """Verifies that under no circumstances can an operational turn violate physical constraints."""

    def test_zero_negative_occupancy_and_turnaround_violations(self, base_legs, paired_turn):
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        rng = np.random.RandomState(99)

        # 200 random combinations of arrival and departure delays
        arr_delays = rng.uniform(-60, 240, size=200)
        dep_delays = rng.uniform(-60, 240, size=200)

        for d_arr, d_dep in zip(arr_delays, dep_delays):
            turn = engine.synthesize_turn(
                pair=paired_turn,
                legs=base_legs,
                arrival_prediction=float(d_arr),
                departure_prediction=float(d_dep),
                mode=SimulationMode.DUAL_POINT,
            )

            # Invariant 1: Gate-out must respect physical turnaround
            assert turn.simulated_departure_min >= turn.simulated_arrival_min + turn.min_turnaround_min

            # Invariant 2: Gate-out must respect ML prediction
            assert turn.simulated_departure_min >= turn.departure_ml_min

            # Invariant 3: Gate release must be departure + separation buffer
            assert turn.gate_release_min == turn.simulated_departure_min + turn.separation_buffer_min

            # Invariant 4: Occupancy duration must be strictly positive
            assert turn.occupancy_duration_min > 0

    def test_domain_flight_conversion(self, base_legs, paired_turn):
        engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
        turn = engine.synthesize_turn(
            pair=paired_turn,
            legs=base_legs,
            arrival_prediction=20.0,
            departure_prediction=30.0,
            mode=SimulationMode.DUAL_POINT,
        )
        flight = turn.to_flight(flight_index=7)
        assert flight.flight_id == "PAIR_001"
        assert flight.flight_index == 7
        assert flight.predicted_arrival_min == 620
        assert flight.scheduled_departure_min == 690
        assert flight.min_turnaround_min == 45
        assert flight.buffer_min == 15
        assert flight.is_paired is True
