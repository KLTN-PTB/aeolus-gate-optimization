"""Opt-in Hybrid stages with one absolute deadline including model construction."""
from dataclasses import replace
import time
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.execution import SolverDeadlineExceeded
from src.optimization.sa.annealer import SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def solve_budgeted_hybrid(solver, flights, gates, *, allow_overflow, deadline,
                          initial_assignments=None, progress_callback=None, complete_hints=False):
    started = time.perf_counter()
    cfg = solver.config
    cp_deadline = started + max(0, deadline-started)*solver.cp_ratio
    cp_cfg = replace(cfg, time_limit_seconds=max(.001, cp_deadline-started),
                     total_wall_clock_budget_seconds=max(.001, cp_deadline-started))
    cp_result = None
    try:
        cp_result = CPSatGateSolver(cp_cfg).solve(flights, gates, allow_overflow=allow_overflow,
            initial_assignments=initial_assignments if cfg.cp_sat_use_warm_start else None,
            deadline_perf_counter=cp_deadline, progress_callback=progress_callback,
            complete_hints=complete_hints)
    except SolverDeadlineExceeded:
        pass
    cp_ms = (time.perf_counter()-started)*1000
    if cp_result is not None and cp_result.status == 'INFEASIBLE':
        return cp_result
    source = 'CP_SAT'
    if cp_result is not None and cp_result.feasible:
        incumbent = cp_result
    else:
        source = 'GREEDY_FALLBACK'
        if initial_assignments:
            incumbent = evaluate_gate_assignment(initial_assignments, flights, gates, cfg, solver_status='FEASIBLE')
        elif time.perf_counter() < deadline:
            incumbent = DeterministicGreedyGateSolver(cfg).solve(flights, gates, allow_overflow=allow_overflow)
        else:
            incumbent = evaluate_gate_assignment({}, flights, gates, cfg, solver_status='UNKNOWN')
    initial_cost = incumbent.objective_value
    if progress_callback and incumbent.feasible:
        progress_callback(incumbent.assignments, {'solution_source': 'GREEDY_FALLBACK' if source != 'CP_SAT' else 'SOLVER',
            'stage': 'hybrid', 'initial_solution_source': source})
    sa_started = time.perf_counter()
    sa_result = None
    if incumbent.feasible and sa_started < deadline:
        sa_result = SimulatedAnnealingGateSolver(cfg, solver.sa_config).solve(flights, gates,
            initial_assignments=incumbent.assignments, allow_overflow=allow_overflow,
            deadline_perf_counter=deadline, progress_callback=progress_callback)
        if sa_result.feasible and sa_result.objective_value <= incumbent.objective_value + 1e-9:
            incumbent = sa_result
    sa_ms = (time.perf_counter()-sa_started)*1000
    proven = bool(cp_result is not None and cp_result.optimality_proven and incumbent.feasible
                  and abs(incumbent.objective_value-cp_result.objective_value)<1e-9)
    timed_out = time.perf_counter() >= deadline
    reason = 'OPTIMAL_PROVEN' if proven else ('TIME_LIMIT' if timed_out else 'FEASIBLE_FOUND' if incumbent.feasible else 'NO_FEASIBLE_SOLUTION')
    cp_trace = cp_result.solver_configuration if cp_result is not None else {}
    trace = {**incumbent.solver_configuration, 'solver_name': 'HybridCPSatSA',
        'model_construction_ms': cp_trace.get('model_construction_ms'),
        'search_time_ms': cp_trace.get('search_time_ms', 0) + sa_ms,
        'warm_start_used': cp_trace.get('warm_start_used', False),
        'n_variables': cp_trace.get('n_variables'), 'n_constraints': cp_trace.get('n_constraints'),
        'initial_solution_source': source, 'cp_solver_status': cp_result.status if cp_result is not None else 'TIMEOUT_NO_SOLUTION',
        'stage1_wall_clock_ms': cp_ms, 'stage2_wall_clock_ms': sa_ms,
        'initial_cost': initial_cost, 'final_cost': incumbent.objective_value,
        'sa_iterations': sa_result.solver_configuration.get('sa_iterations', 0) if sa_result is not None else 0,
        'sa_executed': sa_result is not None, 'fallback_used': source == 'GREEDY_FALLBACK',
        'termination_reason': reason}
    return replace(incumbent, status='OPTIMAL' if proven else 'FEASIBLE' if incumbent.feasible else 'UNKNOWN',
        normalized_status=None, raw_solver_status=trace['cp_solver_status'],
        runtime_ms=(time.perf_counter()-started)*1000, solver_configuration=trace,
        optimality_proven=proven, optimality_gap=0.0 if proven else None,
        best_bound=cp_result.best_bound if cp_result is not None else None, termination_reason=reason)
