"""Version-2 dashboard supervision bridge for the gate-wait objective."""
from dataclasses import replace
import time

from src.optimization.domain import Flight, Gate, GateAssignment
from src.optimization.waiting import WaitingConfig, check, solve_waiting


def problem(payload):
    flights = [Flight.from_dict(row) for row in payload["flights"]]
    gates = [Gate.from_dict(row) for row in payload["gates"]]
    cfg = WaitingConfig(**payload["waiting_config"])
    if payload.get("initial"):
        nominal = {row["flight_id"]: row["gate_id"] for row in payload["initial"]}
        flights = [replace(f, nominal_gate_id=nominal.get(f.flight_id, f.nominal_gate_id)) for f in flights]
    return flights, gates, cfg


def frozen_assignments(rows, flights):
    by_id = {f.flight_id: f for f in flights}
    result = {}
    for row in rows or []:
        f = by_id[row["flight_id"]]
        raw_wait = row.get('gate_wait_min',0)
        wait = int(raw_wait)
        if wait != raw_wait:
            raise ValueError('Frozen waiting decisions must be integer minutes')
        result[f.flight_id] = replace(GateAssignment.from_dict(row),
            occupancy_start_min=f.occupancy_start_min + wait, occupancy_end_min=f.occupancy_end_min + wait,
            is_reassignment=False)
    return result


def solve(payload, *, started=None, publish=None):
    from web_dashboard.solver_execution import fingerprint
    started = time.perf_counter() if started is None else started
    flights, gates, cfg = problem(payload)
    initial = frozen_assignments(payload.get("initial"), flights)
    def checkpoint(assignments, meta):
        if not publish:
            return
        d, waits, cost, _ = check(assignments, flights, gates, cfg)
        if not d.is_valid:
            return
        runtime = time.perf_counter()-started
        publish({"status": "FEASIBLE", "feasible": True, "algorithm": payload["algorithm"], "mode": payload["mode"],
            "seed": payload["seed"], "case_fingerprint": fingerprint(payload), "solver_protocol_version": 2,
            "solver_profile": payload.get("solver_profile", "optimized"), "objective_version": "gate_wait_v1",
            "solution_source": meta["solution_source"], "termination_reason": "FEASIBLE_FOUND", "optimality_proven": False,
            "runtime_sec": runtime, "budget_compliant": runtime <= payload["budget"], "decision_cost": cost["decision_cost"],
            "risk_cost": None, "assigned_count": len(assignments), "conflicts": d.conflict_count,
            "diagnostic": d.to_dict(), "breakdown": cost, "trace": {},
            "remote_count": sum(a.is_overflow for a in assignments.values()),
            "reassignments": sum(f.nominal_gate_id is not None and assignments[f.flight_id].gate_id != f.nominal_gate_id for f in flights),
            "total_gate_wait_min": sum(waits.values()),
            "assignments": [{**a.to_dict(), "gate_wait_min": waits[a.flight_id]} for a in assignments.values()]})
    result = solve_waiting(flights, gates, cfg, algorithm=payload["algorithm"], budget=payload["budget"],
        seed=payload["seed"], initial=initial, fixed=payload["mode"] == "fixed", started=started, publish=checkpoint,
        warm_start=payload.get('solver_profile','optimized') == 'optimized')
    result.pop("shifted_flights", None)
    result.update(mode=payload["mode"], seed=payload["seed"], case_fingerprint=fingerprint(payload),
                  solver_protocol_version=2, solver_profile=payload.get("solver_profile", "optimized"))
    return result


def verify(payload, result):
    from web_dashboard.solver_execution import fingerprint
    if result.get("case_fingerprint") != fingerprint(payload):
        raise ValueError("Waiting artifact fingerprint changed")
    if not result.get('assignments') and result.get('solution_source') == 'NONE' and result.get('termination_reason') in ('ERROR','TIME_LIMIT','CANCELLED'):
        if result.get('feasible') or result.get('decision_cost') is not None or result.get('optimality_proven'):
            raise ValueError('Invalid empty waiting result')
        return result
    flights, gates, cfg = problem(payload)
    rows = result.get("assignments", [])
    assignments = {row["flight_id"]: GateAssignment.from_dict(row) for row in rows}
    if len(rows) != len(assignments):
        raise ValueError("Duplicate waiting assignment")
    d, waits, cost, _ = check(assignments, flights, gates, cfg)
    if bool(result["feasible"]) != d.is_valid:
        raise ValueError("Waiting artifact feasibility disagrees with independent checker")
    if result.get("assigned_count", 0) != len(rows) or result.get("conflicts") != d.conflict_count:
        raise ValueError("Waiting artifact diagnostic mismatch")
    for row in rows:
        if row.get("gate_wait_min") != waits[row["flight_id"]]:
            raise ValueError("Waiting artifact reports a forged waiting time")
    if d.is_valid and abs(cost["decision_cost"] - result["decision_cost"]) > 1e-6:
        raise ValueError("Waiting artifact cost mismatch")
    if d.is_valid and result.get('breakdown'):
        for key in ('waiting_cost','reassignment_cost','remote_cost','decision_cost'):
            if abs(cost[key] - result['breakdown'][key]) > 1e-6:
                raise ValueError('Waiting artifact cost component mismatch')
    return result
