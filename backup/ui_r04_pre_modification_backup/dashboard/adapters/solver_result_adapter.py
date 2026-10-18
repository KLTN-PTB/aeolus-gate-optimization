"""Adapter transforming OptimizationResult domain objects to SolverRunView."""

from typing import Any, Dict, List, Optional

from dashboard.adapters.assignment_adapter import adapt_assignment_to_view
from dashboard.core.contracts import GateTimelineView, ProvenanceType, SolverRunView
from src.optimization.domain import OptimizationResult


def adapt_solver_result_to_view(
    result: OptimizationResult | Dict[str, Any],
    solver_name: str,
    scenario_id: str,
    solver_config: Optional[Dict[str, Any]] = None,
    conflicts: Optional[List[str]] = None,
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION,
    requested_solver: Optional[str] = None,
    effective_solver: Optional[str] = None,
    fallback_used: Optional[bool] = None,
    problem_digest: Optional[str] = None,
    execution_digest: Optional[str] = None,
    run_id: Optional[str] = None,
    verifier_diagnostics: Optional[Dict[str, Any]] = None,
) -> SolverRunView:
    """Convert an OptimizationResult domain object to a SolverRunView view model."""
    if isinstance(result, dict):
        d = result
        assignments_raw = d.get("assignments", [])
        if isinstance(assignments_raw, dict):
            assignments_raw = list(assignments_raw.values())
        status_val = str(d.get("status", "UNKNOWN"))
        term_val = str(d.get("termination_reason", "UNKNOWN"))
        obj_val = d.get("objective_value")
        solve_time = float(d.get("solve_time_sec", d.get("runtime_ms", 0.0) / 1000.0))
        n_reassign = int(d.get("reassignment_count", 0))
        n_remote = int(d.get("remote_gate_count", 0))
        n_conflict = int(d.get("conflict_count", 0))
        gap = d.get("gap", d.get("optimality_gap"))
        is_opt_proven = bool(d.get("optimality_proven", False))
        diag_raw = d.get("constraint_diagnostics")
        raw_cfg = d.get("solver_configuration", {})
    else:
        # Domain dataclass instance
        if isinstance(result.assignments, dict):
            assignments_raw = list(result.assignments.values())
        else:
            assignments_raw = result.assignments

        status_val = str(result.status)
        term_val = str(result.termination_reason or ("OPTIMAL_PROVEN" if result.optimality_proven else "HEURISTIC_STOP"))
        obj_val = result.objective_value
        solve_time = float(result.runtime_ms) / 1000.0
        n_reassign = sum(
            1 for a in assignments_raw
            if getattr(a, "is_reassignment", False) or getattr(a, "is_reassigned", False)
        )
        n_remote = sum(
            1 for a in assignments_raw
            if getattr(a, "is_overflow", False) or getattr(a, "is_remote", False) or "REMOTE" in getattr(a, "gate_id", "").upper()
        )
        n_conflict = getattr(result.constraint_diagnostics, "conflict_count", getattr(result.constraint_diagnostics, "hard_constraint_violations_count", 0))
        gap = result.optimality_gap
        is_opt_proven = (
            "OPTIMAL_PROVEN" in term_val
            or getattr(result, "optimality_proven", False)
        )
        diag_raw = getattr(result, "constraint_diagnostics", None)
        raw_cfg = getattr(result, "solver_configuration", {})

    if fallback_used is None:
        fallback_used = bool(raw_cfg.get("fallback_used", False) if isinstance(raw_cfg, dict) else False)

    if verifier_diagnostics is None and diag_raw is not None:
        if hasattr(diag_raw, "to_dict"):
            verifier_diagnostics = diag_raw.to_dict()
        elif isinstance(diag_raw, dict):
            verifier_diagnostics = diag_raw

    cfg = solver_config or {}
    w_pref = float(cfg.get("w_pref", 10.0))
    w_remote = float(cfg.get("w_remote", 200.0))
    w_conflict = float(cfg.get("w_conflict", 1000.0))

    # Deconstruct Decision Cost: w_pref * reassign + w_remote * remote + w_conflict * conflict
    decision_cost = (
        (w_pref * n_reassign) + (w_remote * n_remote) + (w_conflict * n_conflict)
    )
    # Exogenous reporting cost
    reporting_cost = max(0.0, (float(obj_val) - decision_cost)) if obj_val is not None else 0.0

    # Adapt assignments
    conflict_flights = set(conflicts or [])
    views: List[GateTimelineView] = [
        adapt_assignment_to_view(
            a,
            has_conflict=(
                (a.get("flight_id") if isinstance(a, dict) else getattr(a, "flight_id", ""))
                in conflict_flights
            ),
            buffer_min=int(cfg.get("buffer_time_min", 15)),
            provenance=provenance,
        )
        for a in assignments_raw
    ]

    # Enforce scientific rule: Only OPTIMAL_PROVEN gets is_optimal_proven = True.
    # Heuristics (Greedy, Simulated Annealing) or fallback executions can NEVER be certified as optimal proven.
    s_upper = solver_name.upper()
    if "GREEDY" in s_upper or "SIMULATED" in s_upper or s_upper.startswith("SA") or fallback_used:
        is_opt_proven = False

    eff_solver = effective_solver
    if eff_solver is None:
        eff_solver = "Deterministic Greedy" if fallback_used else solver_name

    return SolverRunView(
        solver_name=solver_name,
        scenario_id=scenario_id,
        objective_value=float(obj_val) if obj_val is not None else None,
        decision_cost=decision_cost,
        reporting_cost=reporting_cost,
        reassignment_count=n_reassign,
        remote_gate_count=n_remote,
        conflict_count=n_conflict,
        solve_time_sec=solve_time,
        status=status_val,
        termination_reason=term_val,
        is_optimal_proven=is_opt_proven,
        optimality_gap=float(gap) if gap is not None else None,
        assignments=views,
        solver_config=cfg,
        provenance=provenance,
        requested_solver=requested_solver or solver_name,
        effective_solver=eff_solver,
        fallback_used=fallback_used,
        problem_digest=problem_digest,
        execution_digest=execution_digest,
        run_id=run_id,
        verifier_diagnostics=verifier_diagnostics,
    )
