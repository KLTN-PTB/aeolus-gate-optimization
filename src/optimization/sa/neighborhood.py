"""Neighborhood Operators and Explicit Repair for Simulated Annealing.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Move operator: moves a flight to another feasible gate.
- Swap operator: swaps gate assignments between two distinct flights.
- Direct feasibility preservation: validates hard constraints before applying moves.
- Explicit repair operator: resolves secondary conflicts by reassigning conflicting flights.
- Fail-closed: Never returns an infeasible state.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

from src.optimization.domain import Flight, Gate, GateResourceType
from src.optimization.sa.state import SAState


def is_gate_feasible_for_flight(
    gate: Gate,
    flight: Flight,
    existing_flights_on_gate: Sequence[Flight],
) -> bool:
    """Check if gate can accommodate flight without violating hard constraints."""
    if not gate.is_compatible_carrier(flight.carrier):
        return False
    if not gate.is_compatible_aircraft(flight.aircraft_type):
        return False
    if not gate.is_available_during(flight.time_window):
        return False

    # Check capacity & overlap
    if gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or gate.is_unbounded:
        return True

    w_fl = flight.time_window
    other_flights = [f for f in existing_flights_on_gate if f.flight_id != flight.flight_id]

    if gate.capacity == 1:
        for other in other_flights:
            if w_fl.overlaps(other.time_window):
                return False
        return True
    elif math.isfinite(gate.capacity) and gate.capacity > 1:
        cap = int(gate.capacity)
        crit_times = [w_fl.start_min] + [
            o.time_window.start_min for o in other_flights
            if w_fl.start_min <= o.time_window.start_min < w_fl.end_min
        ]
        for t in crit_times:
            concurrent = sum(1 for o in other_flights if o.time_window.start_min <= t < o.time_window.end_min)
            if concurrent + 1 > cap:
                return False
        return True

    return True


def repair_state(state: SAState) -> SAState | None:
    """Explicit repair operator resolving gate conflicts across finite resources.

    Attempts to relocate conflicting flights on finite gates (contact gates and
    finite remote stands) to either:
    1. A conflict-free compatible gate, or
    2. An overflow stand/apron that can accommodate them.

    Returns:
        Repaired feasible SAState, or None if repair fails.
    """
    repaired = state.copy()
    finite_gates = [g for g in repaired.gates if g.is_finite]
    overflow_gates = [g for g in repaired.gates if g.is_overflow]

    # Iterative conflict resolution
    max_steps = 10
    step = 0
    while step < max_steps:
        step += 1
        conflicts_found = False

        for g in finite_gates:
            assigned = list(repaired.gate_to_flights.get(g.gate_id, []))
            n = len(assigned)
            cap = int(g.capacity) if (g.capacity is not None and math.isfinite(g.capacity)) else 1
            if n <= cap:
                continue

            # Sort by arrival
            sorted_fl = sorted(assigned, key=lambda f: f.time_window.start_min)
            if cap == 1:
                for i in range(n - 1):
                    f1 = sorted_fl[i]
                    for j in range(i + 1, n):
                        f2 = sorted_fl[j]
                        if f1.time_window.overlaps(f2.time_window):
                            conflicts_found = True
                            # Conflict detected: attempt to evict f2
                            evicted = False

                            # Try other finite gates first
                            for alt_g in finite_gates:
                                if alt_g.gate_id == g.gate_id:
                                    continue
                                existing = repaired.gate_to_flights.get(alt_g.gate_id, [])
                                if is_gate_feasible_for_flight(alt_g, f2, existing):
                                    repaired.assign(f2.flight_id, alt_g.gate_id)
                                    evicted = True
                                    break

                            # Fallback to overflow stand
                            if not evicted and overflow_gates:
                                for ovf in overflow_gates:
                                    if ovf.gate_id == g.gate_id:
                                        continue
                                    existing_ovf = repaired.gate_to_flights.get(ovf.gate_id, [])
                                    if is_gate_feasible_for_flight(ovf, f2, existing_ovf):
                                        repaired.assign(f2.flight_id, ovf.gate_id)
                                        evicted = True
                                        break

                            if not evicted:
                                # Cannot repair this conflict
                                return None

                            break  # Break inner loop to re-scan
                    if conflicts_found:
                        break
            else:
                for fl in sorted_fl:
                    t = fl.time_window.start_min
                    active = [f for f in sorted_fl if f.time_window.start_min <= t < f.time_window.end_min]
                    if len(active) > cap:
                        conflicts_found = True
                        f2 = active[-1]
                        evicted = False

                        for alt_g in finite_gates:
                            if alt_g.gate_id == g.gate_id:
                                continue
                            existing = repaired.gate_to_flights.get(alt_g.gate_id, [])
                            if is_gate_feasible_for_flight(alt_g, f2, existing):
                                repaired.assign(f2.flight_id, alt_g.gate_id)
                                evicted = True
                                break

                        if not evicted and overflow_gates:
                            for ovf in overflow_gates:
                                if ovf.gate_id == g.gate_id:
                                    continue
                                existing_ovf = repaired.gate_to_flights.get(ovf.gate_id, [])
                                if is_gate_feasible_for_flight(ovf, f2, existing_ovf):
                                    repaired.assign(f2.flight_id, ovf.gate_id)
                                    evicted = True
                                    break

                        if not evicted:
                            return None
                        break

            if conflicts_found:
                break

        if not conflicts_found:
            break

    if repaired.is_feasible():
        return repaired
    return None


def try_move_flight(
    state: SAState,
    flight: Flight,
    target_gate: Gate,
    *,
    use_repair: bool = True,
) -> SAState | None:
    """Attempt moving flight to target_gate.

    Either:
    A. Directly preserves hard feasibility, or
    B. Uses explicit repair operator if minor conflict occurs.
    """
    curr_gate_id = state.get_gate_id(flight.flight_id)
    if curr_gate_id == target_gate.gate_id:
        return None

    existing = state.gate_to_flights.get(target_gate.gate_id, [])
    if is_gate_feasible_for_flight(target_gate, flight, existing):
        # Option A: Directly feasible
        new_state = state.copy()
        new_state.assign(flight.flight_id, target_gate.gate_id)
        if new_state.is_feasible():
            return new_state

    # Option B: Use repair operator
    if use_repair:
        new_state = state.copy()
        new_state.assign(flight.flight_id, target_gate.gate_id)
        repaired = repair_state(new_state)
        if repaired is not None and repaired.is_feasible():
            return repaired

    return None


def try_swap_flights(
    state: SAState,
    flight_1: Flight,
    flight_2: Flight,
    *,
    use_repair: bool = True,
) -> SAState | None:
    """Attempt swapping gates between flight_1 and flight_2.

    Either:
    A. Directly preserves hard feasibility, or
    B. Uses explicit repair operator.
    """
    g1_id = state.get_gate_id(flight_1.flight_id)
    g2_id = state.get_gate_id(flight_2.flight_id)
    if g1_id == g2_id:
        return None

    gate_1 = state.gate_map[g1_id]
    gate_2 = state.gate_map[g2_id]

    existing_g2 = [f for f in state.gate_to_flights.get(g2_id, []) if f.flight_id != flight_2.flight_id]
    existing_g1 = [f for f in state.gate_to_flights.get(g1_id, []) if f.flight_id != flight_1.flight_id]

    feasible_1_on_2 = is_gate_feasible_for_flight(gate_2, flight_1, existing_g2)
    feasible_2_on_1 = is_gate_feasible_for_flight(gate_1, flight_2, existing_g1)

    if feasible_1_on_2 and feasible_2_on_1:
        # Option A: Directly feasible swap
        new_state = state.copy()
        new_state.swap(flight_1.flight_id, flight_2.flight_id)
        if new_state.is_feasible():
            return new_state

    # Option B: Use repair operator
    if use_repair:
        new_state = state.copy()
        new_state.swap(flight_1.flight_id, flight_2.flight_id)
        repaired = repair_state(new_state)
        if repaired is not None and repaired.is_feasible():
            return repaired

    return None


def generate_neighbor(
    state: SAState,
    rng: random.Random,
    *,
    move_prob: float = 0.6,
    max_attempts: int = 50,
) -> SAState | None:
    """Generate a random hard-feasible neighbor state via Move or Swap.

    Args:
        state: Current hard-feasible SAState.
        rng: Deterministic random.Random instance.
        move_prob: Probability of choosing Move over Swap (0.0 to 1.0).
        max_attempts: Maximum random sampling attempts before giving up.

    Returns:
        New feasible SAState, or None if no feasible neighbor exists.
    """
    n_flights = len(state.flights)
    n_gates = len(state.gates)
    if n_flights == 0 or n_gates <= 1:
        return None

    flights_list = list(state.flights)
    gates_list = list(state.gates)

    # Identify candidates that could benefit from move/swap (reassigned or overflow flights)
    reassigned_or_ovf = [
        f for f in flights_list
        if state.get_gate_id(f.flight_id) != f.nominal_gate_id
        or state.gate_map[state.get_gate_id(f.flight_id)].is_overflow
    ]

    for _ in range(max_attempts):
        choose_move = (n_flights < 2) or (rng.random() < move_prob)

        if choose_move:
            # 50% bias to select a reassigned/overflow flight if available
            if reassigned_or_ovf and rng.random() < 0.5:
                fl = rng.choice(reassigned_or_ovf)
            else:
                fl = rng.choice(flights_list)

            # If flight is not at nominal gate, 40% bias to try its nominal gate
            if (
                fl.nominal_gate_id is not None
                and state.get_gate_id(fl.flight_id) != fl.nominal_gate_id
                and fl.nominal_gate_id in state.gate_map
                and rng.random() < 0.4
            ):
                target_g = state.gate_map[fl.nominal_gate_id]
            else:
                target_g = rng.choice(gates_list)

            cand = try_move_flight(state, fl, target_g, use_repair=True)
            if cand is not None:
                assert cand.is_feasible(), "Fail-closed: Generated neighbor must be hard-feasible"
                return cand
        else:
            if reassigned_or_ovf and rng.random() < 0.5:
                f1 = rng.choice(reassigned_or_ovf)
                other_flights = [f for f in flights_list if f.flight_id != f1.flight_id]
                f2 = rng.choice(other_flights) if other_flights else f1
            else:
                f1, f2 = rng.sample(flights_list, 2)

            cand = try_swap_flights(state, f1, f2, use_repair=True)
            if cand is not None:
                assert cand.is_feasible(), "Fail-closed: Generated neighbor must be hard-feasible"
                return cand

    return None
