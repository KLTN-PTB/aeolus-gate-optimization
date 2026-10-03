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

import random
from typing import Sequence

from src.optimization.domain import Flight, Gate
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

    if not gate.is_overflow:
        w_fl = flight.time_window
        for other in existing_flights_on_gate:
            if other.flight_id == flight.flight_id:
                continue
            if w_fl.overlaps(other.time_window):
                return False

    return True


def repair_state(state: SAState) -> SAState | None:
    """Explicit repair operator resolving contact gate conflicts.

    Attempts to relocate conflicting flights on contact gates to either:
    1. A conflict-free compatible contact gate, or
    2. An overflow apron.

    Returns:
        Repaired feasible SAState, or None if repair fails.
    """
    repaired = state.copy()
    overflow_gates = [g for g in repaired.gates if g.is_overflow]
    contact_gates = [g for g in repaired.gates if not g.is_overflow]

    # Iterative conflict resolution
    max_steps = 10
    step = 0
    while step < max_steps:
        step += 1
        conflicts_found = False

        for g in contact_gates:
            assigned = list(repaired.gate_to_flights.get(g.gate_id, []))
            n = len(assigned)
            if n <= 1:
                continue

            # Sort by arrival
            sorted_fl = sorted(assigned, key=lambda f: f.time_window.start_min)
            for i in range(n - 1):
                f1 = sorted_fl[i]
                for j in range(i + 1, n):
                    f2 = sorted_fl[j]
                    if f1.time_window.overlaps(f2.time_window):
                        conflicts_found = True
                        # Conflict detected: attempt to evict f2
                        evicted = False

                        # Try other contact gates first
                        for alt_g in contact_gates:
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
                                if is_gate_feasible_for_flight(ovf, f2, []):
                                    repaired.assign(f2.flight_id, ovf.gate_id)
                                    evicted = True
                                    break

                        if not evicted:
                            # Cannot repair this conflict
                            return None

                        break  # Break inner loop to re-scan
                if conflicts_found:
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

    # Check compatibility and operational availability
    if not target_gate.is_compatible_carrier(flight.carrier):
        return None
    if not target_gate.is_compatible_aircraft(flight.aircraft_type):
        return None
    if not target_gate.is_available_during(flight.time_window):
        return None

    # Check contact gate overlap
    existing = state.gate_to_flights.get(target_gate.gate_id, [])
    overlaps = False
    if not target_gate.is_overflow:
        w_fl = flight.time_window
        overlaps = any(w_fl.overlaps(f.time_window) for f in existing)

    if not overlaps:
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

    # Check compatibility and availability
    if not gate_2.is_compatible_carrier(flight_1.carrier):
        return None
    if not gate_2.is_compatible_aircraft(flight_1.aircraft_type):
        return None
    if not gate_2.is_available_during(flight_1.time_window):
        return None

    if not gate_1.is_compatible_carrier(flight_2.carrier):
        return None
    if not gate_1.is_compatible_aircraft(flight_2.aircraft_type):
        return None
    if not gate_1.is_available_during(flight_2.time_window):
        return None

    # Check overlaps on gate_2 (excluding flight_2)
    overlap_g2 = False
    if not gate_2.is_overflow:
        existing_g2 = [f for f in state.gate_to_flights.get(g2_id, []) if f.flight_id != flight_2.flight_id]
        overlap_g2 = any(flight_1.time_window.overlaps(f.time_window) for f in existing_g2)

    # Check overlaps on gate_1 (excluding flight_1)
    overlap_g1 = False
    if not gate_1.is_overflow:
        existing_g1 = [f for f in state.gate_to_flights.get(g1_id, []) if f.flight_id != flight_1.flight_id]
        overlap_g1 = any(flight_2.time_window.overlaps(f.time_window) for f in existing_g1)

    if not overlap_g1 and not overlap_g2:
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
