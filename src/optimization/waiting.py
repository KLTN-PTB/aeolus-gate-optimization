"""Opt-in finite-capacity gate assignment with bounded gate-entry waiting.

All costs are simulation points. Arrival predictions remain immutable. Waiting
shifts gate-in AND gate-out by the same amount, preserving service duration.
Legacy fixed-window solvers/evidence are not modified by this module.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import math
import random
import time
from decimal import Decimal

from ortools.sat.python import cp_model

from src.optimization.domain import FlightTimeWindow, GateAssignment, verify_hard_constraints_independently

VERSION = "gate_wait_v1"


@dataclass(frozen=True)
class WaitingConfig:
    max_gate_wait_min: int = 30
    wait_weight: float = 1.
    reassignment_weight: float = 10.
    remote_weight: float = 200.
    allowed_wait_ids: tuple | None = None

    def __post_init__(self):
        if isinstance(self.max_gate_wait_min, bool) or int(self.max_gate_wait_min) != self.max_gate_wait_min or not 0 <= self.max_gate_wait_min <= 120:
            raise ValueError("Maximum gate wait must be an integer in [0,120]")
        for weight in (self.wait_weight, self.reassignment_weight, self.remote_weight):
            if not math.isfinite(weight) or not 0 <= weight <= 1e6 or Decimal(str(weight)).normalize().as_tuple().exponent < -6:
                raise ValueError("Waiting weights require 0..1000000 and at most six decimal places")

    def cost_scale(self):
        return 10 ** max(0, *(-Decimal(str(w)).normalize().as_tuple().exponent
                             for w in (self.wait_weight, self.reassignment_weight, self.remote_weight)))

    def cap(self, flight):
        return self.max_gate_wait_min if self.allowed_wait_ids is None or flight.flight_id in self.allowed_wait_ids else 0


def shifted(flight, wait):
    return replace(flight, predicted_arrival_min=flight.predicted_arrival_min + wait,
                   precomputed_gate_out_min=flight.simulated_departure_min + wait)


def compatible(flight, gate):
    return gate.is_compatible_carrier(flight.carrier) and gate.is_compatible_aircraft(flight.aircraft_type)


def assignment(flight, gate, wait):
    return GateAssignment(flight.flight_id, gate.gate_id, flight.flight_index, gate.gate_index,
        is_overflow=gate.is_overflow,
        is_reassignment=flight.nominal_gate_id is not None and flight.nominal_gate_id != gate.gate_id,
        occupancy_start_min=flight.occupancy_start_min + wait,
        occupancy_end_min=flight.occupancy_end_min + wait)


def check(assignments, flights, gates, cfg):
    """Derive waiting from timestamps; never trust solver-supplied waiting/cost."""
    if len({f.flight_id for f in flights}) != len(flights) or len({g.gate_id for g in gates}) != len(gates):
        raise ValueError("Duplicate input flight or gate identifiers")
    if any(not g.is_finite for g in gates):
        raise ValueError("Bounded-wait profile requires finite resources")
    shifted_flights, waits = [], {}
    by_id = {f.flight_id: f for f in flights}
    if set(assignments) - set(by_id):
        raise ValueError("Unknown flight in waiting assignment")
    if any(key != item.flight_id for key, item in assignments.items()):
        raise ValueError("Assignment key and flight identifier disagree")
    for flight in flights:
        item = assignments.get(flight.flight_id)
        wait = item.occupancy_start_min - flight.occupancy_start_min if item else 0
        if int(wait) != wait or not 0 <= wait <= cfg.cap(flight):
            raise ValueError("Gate wait outside the admitted bound")
        if item and item.occupancy_end_min != flight.occupancy_end_min + wait:
            raise ValueError("Waiting must preserve physical service and buffer duration")
        waits[flight.flight_id] = int(wait)
        shifted_flights.append(shifted(flight, int(wait)))
    diagnostic = verify_hard_constraints_independently(shifted_flights, gates, assignments)
    by_gate = {g.gate_id: g for g in gates}
    moved = sum(f.nominal_gate_id is not None and f.flight_id in assignments
                and assignments[f.flight_id].gate_id != f.nominal_gate_id for f in flights)
    remote = sum(by_gate[item.gate_id].is_overflow for item in assignments.values() if item.gate_id in by_gate)
    waiting_cost, reassignment_cost, remote_cost = sum(waits.values()) * cfg.wait_weight, moved * cfg.reassignment_weight, remote * cfg.remote_weight
    cost = {"objective_version": VERSION, "waiting_cost": waiting_cost,
        "reassignment_cost": reassignment_cost, "remote_cost": remote_cost,
        "overflow_cost": remote_cost, "decision_cost": waiting_cost + reassignment_cost + remote_cost,
        "total_cost": waiting_cost + reassignment_cost + remote_cost, "reporting_cost": 0.,
        "exogenous_delay_minutes": sum(max(0, f.arrival_delay_min) for f in flights),
        "total_gate_wait_min": sum(waits.values()), "weights": asdict(cfg)}
    return diagnostic, waits, cost, shifted_flights


def _fits(gate, start, end, intervals):
    if not gate.is_available_during(FlightTimeWindow(start, end)):
        return False
    overlap = [(s, e) for s, e in intervals if max(start, s) < min(end, e)]
    if gate.capacity == 1:
        return not overlap
    events = [(max(start, s), 1) for s, _ in overlap] + [(min(end, e), -1) for _, e in overlap]
    active = 1
    for _, delta in sorted(events):
        active += delta
        if active > gate.capacity:
            return False
    return True


def earliest(flight, gate, intervals, cap):
    if not compatible(flight, gate):
        return None
    ready, duration = flight.occupancy_start_min, flight.occupancy_end_min - flight.occupancy_start_min
    starts = {ready, *(e for _, e in intervals)}
    if gate.available_windows:
        starts.update(s for s, _ in gate.available_windows)
    for start in sorted(s for s in starts if ready <= s <= ready + cap):
        if _fits(gate, start, start + duration, intervals):
            return start - ready
    return None


def _increment(flight, gate, wait, cfg):
    return cfg.wait_weight * wait + cfg.remote_weight * gate.is_overflow + cfg.reassignment_weight * (
        flight.nominal_gate_id is not None and flight.nominal_gate_id != gate.gate_id)


def greedy(flights, gates, cfg, deadline, forced=None, existing=None):
    output = dict(existing or {})
    busy = {g.gate_id: [] for g in gates}
    for item in output.values():
        busy[item.gate_id].append((item.occupancy_start_min, item.occupancy_end_min))
    for flight in sorted(flights, key=lambda f: (f.occupancy_start_min, f.flight_id)):
        if flight.flight_id in output:
            continue
        if time.perf_counter() >= deadline:
            return output
        options = []
        for gate in gates:
            if forced and flight.flight_id in forced and forced[flight.flight_id] != gate.gate_id:
                continue
            wait = earliest(flight, gate, busy[gate.gate_id], cfg.cap(flight))
            if wait is not None:
                options.append((_increment(flight, gate, wait, cfg), wait, gate.gate_id, gate))
        if not options:
            return output
        _, wait, _, gate = min(options, key=lambda item: item[:3])
        output[flight.flight_id] = assignment(flight, gate, wait)
        busy[gate.gate_id].append((flight.occupancy_start_min + wait, flight.occupancy_end_min + wait))
    return output


def cp_solve(flights, gates, cfg, deadline, seed, initial=None):
    model = cp_model.CpModel()
    scale = cfg.cost_scale()
    starts, waits, choices, intervals, costs = {}, {}, {}, {g.gate_id: [] for g in gates}, []
    for i, flight in enumerate(flights):
        if time.perf_counter() >= deadline:
            return None, "UNKNOWN", None, None
        ready, duration = flight.occupancy_start_min, flight.occupancy_end_min - flight.occupancy_start_min
        waits[flight.flight_id] = model.new_int_var(0, cfg.cap(flight), f"w_{i}")
        starts[flight.flight_id] = model.new_int_var(ready, ready + cfg.cap(flight), f"s_{i}")
        model.add(starts[flight.flight_id] == ready + waits[flight.flight_id])
        costs.append(round(cfg.wait_weight * scale) * waits[flight.flight_id])
        presence = []
        for j, gate in enumerate(gates):
            if not compatible(flight, gate):
                continue
            if time.perf_counter() >= deadline:
                return None, "UNKNOWN", None, None
            selected = model.new_bool_var(f"x_{i}_{j}")
            end = model.new_int_var(ready + duration, ready + cfg.cap(flight) + duration, f"e_{i}_{j}")
            interval = model.new_optional_interval_var(starts[flight.flight_id], duration, end, selected, f"iv_{i}_{j}")
            intervals[gate.gate_id].append(interval)
            choices[flight.flight_id, gate.gate_id] = selected
            presence.append(selected)
            costs.append(round(scale * _increment(flight, gate, 0, cfg)) * selected)
            if gate.available_windows is not None:
                windows = []
                for k, (lo, hi) in enumerate(gate.available_windows):
                    if hi - lo < duration:
                        continue
                    active = model.new_bool_var(f"win_{i}_{j}_{k}")
                    model.add(starts[flight.flight_id] >= lo).only_enforce_if(active)
                    model.add(starts[flight.flight_id] + duration <= hi).only_enforce_if(active)
                    model.add_implication(active, selected)
                    windows.append(active)
                model.add(sum(windows) == selected)
            if initial and flight.flight_id in initial:
                model.add_hint(selected, int(initial[flight.flight_id].gate_id == gate.gate_id))
        model.add_exactly_one(presence)
        if initial and flight.flight_id in initial:
            model.add_hint(waits[flight.flight_id], initial[flight.flight_id].occupancy_start_min - ready)
    for gate in gates:
        if gate.capacity == 1:
            model.add_no_overlap(intervals[gate.gate_id])
        else:
            model.add_cumulative(intervals[gate.gate_id], [1] * len(intervals[gate.gate_id]), int(gate.capacity))
    model.minimize(sum(costs))
    solver = cp_model.CpSolver()
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        return None, "UNKNOWN", None, None
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    status = solver.solve(model)
    label = solver.status_name(status)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return None, label, None, None
    output = {}
    for flight in flights:
        wait = solver.value(waits[flight.flight_id])
        for gate in gates:
            variable = choices.get((flight.flight_id, gate.gate_id))
            if variable is not None and solver.value(variable):
                output[flight.flight_id] = assignment(flight, gate, wait)
                break
    return output, label, solver.best_objective_bound / scale, solver.objective_value / scale


def anneal(flights, gates, cfg, deadline, seed, initial, *, iterations=1000):
    rng = random.Random(seed)
    current, best = dict(initial), dict(initial)
    d, _, costs, _ = check(current, flights, gates, cfg)
    if not d.is_valid:
        return best, {"sa_iterations": 0, "sa_accepted_moves": 0}
    current_cost = best_cost = costs["decision_cost"]
    accepted, completed = 0, 0
    ids = [f.flight_id for f in flights]
    if not ids:
        return best, {"sa_iterations": 0, "sa_accepted_moves": 0}
    for step in range(iterations):
        if time.perf_counter() >= deadline:
            break
        completed += 1
        first = rng.choice(ids)
        removed, forced = {first}, {first: rng.choice(gates).gate_id}
        if len(ids) > 1 and rng.random() < .4:
            second = rng.choice([fid for fid in ids if fid != first])
            removed.add(second)
            forced = {first: current[second].gate_id, second: current[first].gate_id}
        remaining = {fid: a for fid, a in current.items() if fid not in removed}
        neighbor = greedy([f for f in flights if f.flight_id in removed], gates, cfg, deadline,
                          forced=forced, existing=remaining)
        if len(neighbor) != len(flights):
            continue
        d, _, cost, _ = check(neighbor, flights, gates, cfg)
        if not d.is_valid:
            continue
        value = cost["decision_cost"]
        temperature = max(.01, 100. * (.995 ** step))
        if value <= current_cost or rng.random() < math.exp(max(-700, (current_cost - value) / temperature)):
            current, current_cost = neighbor, value
            accepted += 1
            if value < best_cost:
                best, best_cost = dict(neighbor), value
    return best, {"sa_iterations": completed, "sa_accepted_moves": accepted, "sa_best_cost": best_cost}


def solve_waiting(flights, gates, cfg=None, *, algorithm="cpsat", budget=10., seed=202601,
                  initial=None, fixed=False, started=None, publish=None, warm_start=True, greedy_fallback=True):
    cfg = cfg or WaitingConfig()
    started = time.perf_counter() if started is None else started
    if budget <= 0 or not math.isfinite(budget):
        raise ValueError("Solver budget must be positive and finite")
    if algorithm not in ("greedy", "cpsat", "sa", "hybrid"):
        raise ValueError("Unknown waiting solver")
    if any(not g.is_finite for g in gates):
        raise ValueError("No infinite overflow in waiting mode")
    hard_deadline = started + budget
    deadline = hard_deadline - min(.25, .1 * budget)
    trace, assignments, source, status, bound = {}, {}, "NONE", "UNKNOWN", None
    if fixed:
        assignments = dict(initial or {})
        status, source = "FIXED_PLAN", "FIXED_PLAN"
    else:
        if initial and algorithm != 'greedy':
            d, _, _, _ = check(initial, flights, gates, cfg)
            if d.is_valid:
                assignments, source = dict(initial), "GREEDY_INITIALIZER"
        if not assignments:
            candidate = greedy(flights, gates, cfg, deadline)
            d, _, _, _ = check(candidate, flights, gates, cfg)
            if d.is_valid:
                assignments, source = candidate, "SOLVER" if algorithm == "greedy" else "GREEDY_INITIALIZER"
        if publish and assignments:
            publish(assignments, {"solution_source": source})
        if algorithm in ("cpsat", "hybrid") and time.perf_counter() < deadline:
            cp_started = time.perf_counter()
            cp_deadline = cp_started + (deadline - cp_started) * (.5 if algorithm == "hybrid" else 1)
            solved, status, bound, _ = cp_solve(flights, gates, cfg, cp_deadline, seed, assignments if warm_start else None)
            trace.update(cp_solver_status=status, stage1_wall_clock_ms=(time.perf_counter() - cp_started) * 1000)
            if solved is not None:
                d, _, candidate_cost, _ = check(solved, flights, gates, cfg)
                old_cost = check(assignments, flights, gates, cfg)[2]["decision_cost"] if assignments else math.inf
                if d.is_valid and candidate_cost["decision_cost"] <= old_cost + 1e-7:
                    assignments, source = solved, "SOLVER"
            elif status == "INFEASIBLE":
                if assignments:
                    raise ValueError("CP-SAT infeasibility contradicts verified incumbent")
            elif assignments:
                source = "GREEDY_FALLBACK"
        initial_cost = check(assignments, flights, gates, cfg)[2]["decision_cost"] if assignments else None
        trace.update(initial_cost=initial_cost, initial_solution_source="CP_SAT" if source == "SOLVER" and algorithm != "greedy" else source)
        if algorithm in ("sa", "hybrid") and assignments and time.perf_counter() < deadline:
            sa_started = time.perf_counter()
            improved, sa_trace = anneal(flights, gates, cfg, deadline, seed, assignments)
            if sa_trace.get("sa_accepted_moves", 0):
                source = "SOLVER"
            assignments = improved
            trace.update(sa_trace, stage2_wall_clock_ms=(time.perf_counter() - sa_started) * 1000)
    if not fixed and algorithm == 'cpsat' and not greedy_fallback and source != 'SOLVER':
        assignments, source = {}, 'NONE'
    if not fixed and assignments and not check(assignments, flights, gates, cfg)[0].is_valid:
        assignments = {}
    diagnostic, waits, breakdown, shifted_flights = check(assignments, flights, gates, cfg)
    valid = diagnostic.is_valid
    runtime = time.perf_counter() - started
    proven = bool(status == "OPTIMAL" and valid and source == "SOLVER" and runtime <= budget)
    rows = [{**a.to_dict(), "gate_wait_min": waits[a.flight_id], "additional_departure_delay_min": waits[a.flight_id]}
            for a in assignments.values()]
    reason = "FIXED_PLAN" if fixed else "OPTIMAL_PROVEN" if proven else "PROVEN_INFEASIBLE" if status == "INFEASIBLE" else "TIME_LIMIT" if time.perf_counter() >= deadline else "FEASIBLE_FOUND" if valid else "NO_FEASIBLE_SOLUTION"
    return {"status": "FIXED_PLAN" if fixed else "OPTIMAL" if proven else "FEASIBLE" if valid else "INFEASIBLE" if status == "INFEASIBLE" else "TIMEOUT_NO_SOLUTION",
        "feasible": valid, "algorithm": algorithm, "runtime_sec": runtime, "budget_compliant": runtime <= budget,
        "solution_source": source, "termination_reason": reason, "objective_version": VERSION,
        "optimality_proven": proven, "best_bound": bound, "gap": max(0, (breakdown["decision_cost"] - bound) / max(1, abs(breakdown["decision_cost"]))) if bound is not None and valid else None,
        "decision_cost": breakdown["decision_cost"] if valid else None,
        "risk_cost": breakdown["decision_cost"] + 1000 * diagnostic.conflict_count if fixed else None,
        "breakdown": breakdown, "assigned_count": len(rows) if valid or fixed else 0,
        "assignments": rows if valid or fixed else [], "diagnostic": diagnostic.to_dict(),
        "conflicts": diagnostic.conflict_count, "remote_count": sum(a.is_overflow for a in assignments.values()),
        "reassignments": sum(f.nominal_gate_id is not None and f.flight_id in assignments and assignments[f.flight_id].gate_id != f.nominal_gate_id for f in flights),
        "total_gate_wait_min": sum(waits.values()), "mean_gate_wait_min": float(sum(waits.values()) / max(1, len(flights))),
        "p95_gate_wait_min": float(__import__('numpy').percentile(list(waits.values()), 95)) if waits else 0.,
        "trace": {**trace, "waiting_config": asdict(cfg)}, "shifted_flights": [f.to_dict() for f in shifted_flights]}
