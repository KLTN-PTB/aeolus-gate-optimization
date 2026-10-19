"""Run one dashboard solver directly, with an optional time budget, without a web server.

Diagnostic-only config permits infinity; application validation remains unchanged.
The input snapshot and dashboard database are never modified.
"""
from __future__ import annotations

import argparse
import cProfile
from dataclasses import dataclass
from functools import cached_property
import hashlib
import json
import math
from pathlib import Path
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from web_dashboard.pipeline import finite_metadata


@dataclass(frozen=True)
class DiagnosticConfig(GateOptimizationConfig):
    """Allow an infinite search deadline ONLY in this offline diagnostic process."""

    def __post_init__(self):
        search, total = self.time_limit_seconds, self.total_wall_clock_budget_seconds
        object.__setattr__(self, 'time_limit_seconds', 120.0 if search == math.inf else search)
        object.__setattr__(self, 'total_wall_clock_budget_seconds', None if total == math.inf else total)
        try:
            super().__post_init__()
        finally:
            object.__setattr__(self, 'time_limit_seconds', search)
            object.__setattr__(self, 'total_wall_clock_budget_seconds', total)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--algorithm', choices=['greedy', 'cpsat', 'sa', 'hybrid'], required=True)
    parser.add_argument('--budget', type=float, help='Omit to remove ALL solver time limits. Ctrl+C stops the diagnostic.')
    parser.add_argument('--iterations', type=int, default=1000)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--warm-start', action='store_true')
    parser.add_argument('--complete-hints', action='store_true', help='Diagnostic-only prototype: fill unselected assignment Bool hints with zero')
    parser.add_argument('--formulation', choices=['sparse_interval', 'sparse_pairwise', 'dense_pairwise'], default='sparse_interval')
    parser.add_argument('--log-search', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--cache-windows', action='store_true', help='Diagnostic-only prototype: cache immutable Flight.time_window')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.complete_hints and not args.warm_start:
        parser.error('--complete-hints requires --warm-start')
    if args.budget is not None and (not math.isfinite(args.budget) or args.budget <= 0):
        parser.error('--budget must be positive and finite, or omitted')
    raw = args.snapshot.read_bytes()
    snapshot = json.loads(raw)
    data = {k: v for k, v in snapshot.items() if k != 'hash'}
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if digest != snapshot['hash']:
        parser.error('Snapshot content hash is invalid')
    if args.output.resolve() == args.snapshot.resolve():
        parser.error('Output must not overwrite input')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cfg = DiagnosticConfig(**{**snapshot['solver_config'],
        'time_limit_seconds': args.budget if args.budget is not None else math.inf,
        'total_wall_clock_budget_seconds': args.budget,
        'num_search_workers': args.workers, 'random_seed': 202601,
        'cp_sat_fallback_to_greedy': False, 'cp_sat_use_warm_start': args.warm_start,
        'cp_sat_formulation': args.formulation, 'log_search_progress': args.log_search,
        'allow_unbounded_overflow': False, 'enforce_remote_capacity': True})
    if args.complete_hints:
        from ortools.sat.python import cp_model
        original_solve = cp_model.CpSolver.Solve

        def solve_with_complete_hint(solver, model, *positional, **keywords):
            proto = model.Proto()
            hinted = set(proto.solution_hint.vars)
            if hinted:
                if any(list(var.domain) != [0, 1] for var in proto.variables):
                    raise ValueError('Complete-hint prototype requires Bool assignment variables only')
                for index in range(len(proto.variables)):
                    if index not in hinted:
                        model.AddHint(model.GetBoolVarFromProtoIndex(index), 0)
            return original_solve(solver, model, *positional, **keywords)

        cp_model.CpSolver.Solve = solve_with_complete_hint
    if args.cache_windows and isinstance(Flight.time_window, property):
        # Flight is frozen: its occupancy window cannot change. A replacement
        # Flight gets a new instance/cache. This patch affects only this process.
        window_cache = cached_property(Flight.time_window.fget)
        window_cache.__set_name__(Flight, 'time_window')
        Flight.time_window = window_cache
    flights = [Flight.from_dict(f) for f in snapshot['flights']]
    gates = [Gate.from_dict(g) for g in snapshot['gates']]
    sa = SAConfig(seed=202601, iterations=args.iterations)
    solvers = {'greedy': lambda: DeterministicGreedyGateSolver(cfg),
        'cpsat': lambda: CPSatGateSolver(cfg),
        'sa': lambda: SimulatedAnnealingGateSolver(cfg, sa),
        'hybrid': lambda: HybridGateSolver(cfg, sa)}
    print(json.dumps({'algorithm': args.algorithm, 'time_budget_sec': args.budget,
        'flights': len(flights), 'gates': len(gates), 'workers': args.workers,
        'warm_start': args.warm_start, 'complete_hints': args.complete_hints, 'iterations': args.iterations,
        'snapshot_hash': digest, 'profile': args.profile, 'cache_windows': args.cache_windows}), flush=True)
    profiler = cProfile.Profile() if args.profile else None
    started = time.perf_counter()
    try:
        if profiler:
            profiler.enable()
        result = solvers[args.algorithm]().solve(flights, gates, allow_overflow=any(g.is_overflow for g in gates))
        if profiler:
            profiler.disable()
        solver_sec = time.perf_counter()-started
        checked = evaluate_gate_assignment(result.assignments, flights, gates, cfg)
        out = {'algorithm': args.algorithm, 'budget_sec': args.budget, 'solver_sec': solver_sec,
            'cache_windows': args.cache_windows, 'workers': args.workers, 'warm_start': args.warm_start,
            'complete_hints': args.complete_hints,
            'end_to_end_sec': time.perf_counter()-started, 'status': result.status,
            'feasible': bool(checked.feasible and checked.constraint_diagnostics.is_valid),
            'decision_cost': checked.objective_breakdown.decision_cost if checked.feasible else None,
            'optimality_proven': result.optimality_proven, 'gap': result.optimality_gap,
            'assigned_count': len(result.assignments), 'conflicts': checked.constraint_diagnostics.conflict_count,
            'snapshot_hash': digest, 'input_file_sha256': hashlib.sha256(raw).hexdigest(),
            'trace': result.solver_configuration,
            'assignments': [a.to_dict() for a in result.assignments.values()]}
        args.output.write_text(json.dumps(finite_metadata(out), ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in finite_metadata(out).items() if k not in ('trace', 'assignments')}, ensure_ascii=True), flush=True)
    except KeyboardInterrupt:
        args.output.with_suffix('.interrupted.json').write_text(json.dumps({'status': 'MANUALLY_STOPPED',
            'algorithm': args.algorithm, 'elapsed_sec': time.perf_counter()-started, 'budget_sec': args.budget,
            'snapshot_hash': digest}), encoding='utf-8')
        raise
    finally:
        if profiler:
            profiler.disable()
            profiler.dump_stats(str(args.output.with_suffix('.prof')))
            with args.output.with_suffix('.profile.txt').open('w', encoding='utf-8') as stream:
                pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(35)
        if args.snapshot.read_bytes() != raw:
            raise RuntimeError('Input snapshot changed during the diagnostic')


if __name__ == '__main__':
    main()
