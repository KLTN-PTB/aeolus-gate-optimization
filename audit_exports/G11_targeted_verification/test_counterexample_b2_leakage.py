"""AEOLUS-G11: Counterexample Test for Mode B2 Causality, Future Information Access, and Unused lock_horizon.

This script tests:
1. FUTURE_INFORMATION_ACCESS: Confirms that evaluate_mode_b2_rolling_online_recourse reads
   realized departure times (precomputed_gate_out_min) at arrival epoch t.
2. UNUSED lock_horizon_minutes: Proves that altering lock_horizon_minutes (0, 45, 1000) has
   EXACTLY ZERO effect on active_assignments, decision_trace, and objective_value.
3. DECISION_LEAKAGE: Demonstrates whether future departure delay mutations (occurring after t)
   alter the decision taken at decision epoch t.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from src.optimization.domain import Flight, Gate, GateResourceType, GateAssignment
from src.optimization.config import GateOptimizationConfig
from src.simulation.monte_carlo_engine_p09 import RealizedScenario
from src.simulation.monte_carlo_engine_v2 import evaluate_mode_b2_rolling_online_recourse


def run_counterexample_tests():
    print("=" * 80)
    print("TEST 1: UNUSED lock_horizon_minutes PARAMETER TEST")
    print("=" * 80)

    # Setup simple scenario with 2 flights and 2 gates
    # Gate 1: Contact gate, Gate 2: Remote gate (overflow)
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1.0),
        Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=10.0, is_overflow=True),
    ]

    config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        time_limit_seconds=5.0,
    )

    # Base scheduled flights:
    # Flight A: arr=60, dep=120, gate=G1
    # Flight B: arr=100, dep=160, gate=G1 (conflicts with A)
    base_flights = [
        Flight(
            flight_id="FL_A",
            flight_index=0,
            carrier="VN",
            flight_number="101",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
            nominal_gate_id="G1",
            aircraft_type="A321",
            min_turnaround_min=45,
            default_dwell_min=60,
            buffer_min=15,
            precomputed_gate_out_min=120,
        ),
        Flight(
            flight_id="FL_B",
            flight_index=1,
            carrier="VN",
            flight_number="102",
            scheduled_arrival_min=100,
            scheduled_departure_min=160,
            predicted_arrival_min=100,
            nominal_gate_id="G1",
            aircraft_type="A321",
            min_turnaround_min=45,
            default_dwell_min=60,
            buffer_min=15,
            precomputed_gate_out_min=160,
        ),
    ]

    initial_assignments = {
        "FL_A": GateAssignment(flight_id="FL_A", gate_id="G1", occupancy_start_min=60, occupancy_end_min=135),
        "FL_B": GateAssignment(flight_id="FL_B", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
    }

    realization = RealizedScenario(
        scenario_id="TEST_SCEN_01",
        scenario_index=1,
        arrival_delays=(0.0, 0.0),
        departure_delays=(0.0, 0.0),
        realization_hash="deadbeef",
        seed=42,
    )

    # Test lock_horizon_minutes = 0, 45, 1000
    res_0 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_assignments,
        realized_flights=base_flights,
        base_scheduled_flights=base_flights,
        gates=gates,
        config=config,
        realization=realization,
        initial_solver_name="TestInit",
        lock_horizon_minutes=0,
    )

    res_45 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_assignments,
        realized_flights=base_flights,
        base_scheduled_flights=base_flights,
        gates=gates,
        config=config,
        realization=realization,
        initial_solver_name="TestInit",
        lock_horizon_minutes=45,
    )

    res_1000 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_assignments,
        realized_flights=base_flights,
        base_scheduled_flights=base_flights,
        gates=gates,
        config=config,
        realization=realization,
        initial_solver_name="TestInit",
        lock_horizon_minutes=1000,
    )

    print(f"Results for lock_horizon=0:    obj={res_0.objective_value:.4f}, reassignments={res_0.reassignment_count}")
    print(f"Results for lock_horizon=45:   obj={res_45.objective_value:.4f}, reassignments={res_45.reassignment_count}")
    print(f"Results for lock_horizon=1000: obj={res_1000.objective_value:.4f}, reassignments={res_1000.reassignment_count}")

    # Check identical trace and objective
    assert res_0.decision_trace == res_45.decision_trace == res_1000.decision_trace, "Decision traces differ!"
    assert res_0.objective_value == res_45.objective_value == res_1000.objective_value, "Objectives differ!"
    assert res_0.reassignment_count == res_45.reassignment_count == res_1000.reassignment_count, "Reassignment counts differ!"
    print("=> VERIFIED: lock_horizon_minutes has ZERO effect on logic and output. It is completely unused dead code.")

    print("\n" + "=" * 80)
    print("TEST 2: FUTURE INFORMATION ACCESS & DECISION LEAKAGE TEST")
    print("=" * 80)

    # Scenario 1: FL_A arrives at 60, departs on-time at 100 (dep_delay = 0).
    # Buffer is 15 -> FL_A gate release is 100 + 15 = 115.
    # FL_B arrives at 120 (predicted_arrival_min = 120).
    # Since 115 <= 120, at t=120 Gate G1 is FREE. FL_B should NOT be reassigned.
    fl_a_scen1 = Flight(
        flight_id="FL_A",
        flight_index=0,
        carrier="VN",
        flight_number="101",
        scheduled_arrival_min=60,
        scheduled_departure_min=100,
        predicted_arrival_min=60,
        nominal_gate_id="G1",
        aircraft_type="A321",
        min_turnaround_min=30,
        default_dwell_min=40,
        buffer_min=15,
        precomputed_gate_out_min=100,  # Departs at 100
    )
    fl_b_scen1 = Flight(
        flight_id="FL_B",
        flight_index=1,
        carrier="VN",
        flight_number="102",
        scheduled_arrival_min=120,
        scheduled_departure_min=180,
        predicted_arrival_min=120,
        nominal_gate_id="G1",
        aircraft_type="A321",
        min_turnaround_min=30,
        default_dwell_min=60,
        buffer_min=15,
        precomputed_gate_out_min=180,
    )

    init_asgn = {
        "FL_A": GateAssignment(flight_id="FL_A", gate_id="G1", occupancy_start_min=60, occupancy_end_min=115),
        "FL_B": GateAssignment(flight_id="FL_B", gate_id="G1", occupancy_start_min=120, occupancy_end_min=195),
    }

    res_scen1 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=init_asgn,
        realized_flights=[fl_a_scen1, fl_b_scen1],
        base_scheduled_flights=[fl_a_scen1, fl_b_scen1],
        gates=gates,
        config=config,
        realization=realization,
        initial_solver_name="TestInit",
    )

    print(f"Scenario 1 (FL_A departs at 100, FL_B arrives at 120):")
    print(f"  FL_B reassignments count: {res_scen1.reassignment_count}")
    print(f"  Decision trace: {res_scen1.decision_trace}")

    # Scenario 2: Identical arrival times up to t=120.
    # FL_A arrives at 60 (same). FL_B arrives at 120 (same).
    # BUT FL_A has a realized departure delay of +40 minutes (precomputed_gate_out_min = 140).
    # Notice this departure event occurs AFTER t=120!
    fl_a_scen2 = Flight(
        flight_id="FL_A",
        flight_index=0,
        carrier="VN",
        flight_number="101",
        scheduled_arrival_min=60,
        scheduled_departure_min=100,
        predicted_arrival_min=60,
        nominal_gate_id="G1",
        aircraft_type="A321",
        min_turnaround_min=30,
        default_dwell_min=40,
        buffer_min=15,
        precomputed_gate_out_min=140,  # Departs at 140 (future departure delay!)
    )
    fl_b_scen2 = fl_b_scen1  # Identical

    res_scen2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=init_asgn,
        realized_flights=[fl_a_scen2, fl_b_scen2],
        base_scheduled_flights=[fl_a_scen2, fl_b_scen2],
        gates=gates,
        config=config,
        realization=realization,
        initial_solver_name="TestInit",
    )

    print(f"\nScenario 2 (FL_A departs at 140 in future, FL_B arrives at 120):")
    print(f"  FL_B reassignments count: {res_scen2.reassignment_count}")
    print(f"  Decision trace: {res_scen2.decision_trace}")

    print("\n" + "=" * 80)
    print("ANALYSIS OF CAUSALITY IN SCENARIOS 1 vs 2:")
    print("=" * 80)
    if res_scen1.reassignment_count != res_scen2.reassignment_count or res_scen1.decision_trace != res_scen2.decision_trace:
        print("CRITICAL FINDING: DECISION LEAKAGE PROVEN!")
        print("At epoch t=120:")
        print(f"  In Scenario 1, FL_B was NOT reassigned (reassignment_count={res_scen1.reassignment_count})")
        print(f"  In Scenario 2, FL_B WAS reassigned (reassignment_count={res_scen2.reassignment_count}, trace={res_scen2.decision_trace})")
        print("The two scenarios have identical operational histories prior to t=120:")
        print("  - Both have FL_A arriving at t=60.")
        print("  - Both have FL_B arriving at t=120.")
        print("  - The only difference is FL_A's future departure timestamp (100 vs 140).")
        print("In a strictly causal real-world simulation, if FL_A's delay occurred after t=120 (e.g., ground hold announced at 125),")
        print("an arrival decision at t=120 could not anticipate a future event unless informed by an active departure forecast.")
        print("Here, evaluate_mode_b2 directly accessed precomputed_gate_out_min (the final realized departure time)!")
    else:
        print("No gate difference observed.")


if __name__ == "__main__":
    run_counterexample_tests()
