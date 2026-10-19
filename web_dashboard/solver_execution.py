"""Versioned dashboard execution: deadlines, verified incumbents and honest provenance."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
import time

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, GateAssignment
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.execution import SolverDeadlineExceeded
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from web_dashboard.pipeline import finite_metadata

PROTOCOL_VERSION = 2
ANALYSIS_VERSION = 3


def fingerprint(payload):
    return hashlib.sha256(json.dumps({k:v for k,v in payload.items() if not k.startswith('_')},
        sort_keys=True, allow_nan=False).encode()).hexdigest()


def version_for(experiment):
    return ANALYSIS_VERSION if experiment['config'].get('solver_protocol_version') == PROTOCOL_VERSION else 2


def cost_eligible(case):
    if case.get('solver_protocol_version') != PROTOCOL_VERSION:
        return bool(case.get('feasible'))
    return bool(case.get('feasible') and case.get('budget_compliant') and case.get('solution_source') == 'SOLVER' and case.get('termination_reason') not in ('ERROR','CANCELLED'))


def actual_algorithm(case):
    return 'greedy' if case.get('solution_source') in ('GREEDY_INITIALIZER', 'GREEDY_FALLBACK') else case['algorithm']


def problem(payload):
    flights = [Flight.from_dict(f) for f in payload['flights']]
    gates = [Gate.from_dict(g) for g in payload['gates']]
    if payload.get('initial'):
        nominal = {a['flight_id']:a['gate_id'] for a in payload['initial']}
        flights = [replace(f, nominal_gate_id=nominal[f.flight_id]) for f in flights]
    cfg = GateOptimizationConfig(**{**payload['solver_config'], 'num_search_workers':1,
        'random_seed':payload['seed'], 'cp_sat_use_warm_start':False, 'cp_sat_fallback_to_greedy':False,
        'time_limit_seconds':payload['budget'], 'total_wall_clock_budget_seconds':payload['budget'],
        'allow_unbounded_overflow':False, 'enforce_remote_capacity':True})
    return flights, gates, cfg


def empty_result(payload, runtime, reason='TIME_LIMIT', error=None):
    return {'status':'TIMEOUT' if reason=='TIME_LIMIT' else 'ERROR', 'feasible':False,
        'algorithm':payload['algorithm'], 'mode':payload['mode'], 'seed':payload['seed'],
        'solver_protocol_version':PROTOCOL_VERSION, 'solver_profile':payload.get('solver_profile','optimized'),
        'case_fingerprint':fingerprint(payload), 'termination_reason':reason, 'solution_source':'NONE',
        'runtime_sec':runtime, 'budget_compliant':runtime<=payload['budget'],
        'decision_cost':None, 'risk_cost':None, 'conflicts':None, 'assigned_count':0,
        'assignments':[], 'optimality_proven':False, 'best_bound':None, 'gap':None, 'error':error}


def verify_artifact(payload, result):
    if result.get('case_fingerprint') != fingerprint(payload):
        raise ValueError('Case artifact does not match input/configuration/protocol')
    if result.get('assignments'):
        flights,gates,cfg=problem(payload)
        assignments={a['flight_id']:GateAssignment.from_dict(a) for a in result['assignments']}
        if len(assignments)!=len(result['assignments']):
            raise ValueError('Duplicate assignment in case artifact')
        checked=evaluate_gate_assignment(assignments,flights,gates,cfg)
        if bool(result.get('feasible')) != bool(checked.feasible and checked.constraint_diagnostics.is_valid):
            raise ValueError('Case artifact failed independent verification')
        if result.get('assigned_count') != len(assignments) or result.get('conflicts') != checked.constraint_diagnostics.conflict_count:
            raise ValueError('Case artifact diagnostics differ from independent evaluation')
        if payload['mode']=='fixed' and abs(checked.objective_value-result['risk_cost'])>1e-6:
            raise ValueError('Fixed-plan risk differs from independent evaluation')
        if payload['mode']!='fixed' and not checked.feasible:
            raise ValueError('Invalid optimization incumbent')
        cost=checked.objective_breakdown.decision_cost if checked.feasible else None
        if cost is not None and abs(cost-result['decision_cost'])>1e-6:
            raise ValueError('Case artifact cost differs from independent evaluation')
    elif result.get('feasible'):
        flights,_,_=problem(payload)
        if flights:
            raise ValueError('Feasible artifact is missing assignments')
    return result


def recover_artifact(payload, result, runtime, reason, error=None):
    verify_artifact(payload,result)
    # Recovery never upgrades a checkpoint into an optimality proof.
    return {**result, 'runtime_sec':runtime, 'budget_compliant':runtime<=payload['budget'],
        'status':'FEASIBLE' if result.get('feasible') else 'TIMEOUT' if reason=='TIME_LIMIT' else 'ERROR',
        'termination_reason':reason, 'optimality_proven':False, 'gap':None, 'error':error}


def solve_case_v2(payload, *, started=None, publish=None):
    from web_dashboard.experiments import peak_demand, adjusted_assignments
    started=time.perf_counter() if started is None else started
    budget=payload['budget']
    reserve=min(.25*budget,max(.25,.1*budget))
    hard_deadline=started+budget
    soft_deadline=hard_deadline-reserve
    flights,gates,cfg=problem(payload)
    optimized=payload.get('solver_profile','optimized')=='optimized'
    best=None
    verified_at=None
    timings={'initialization_sec':0.0,'model_build_sec':None,'search_sec':None,
             'validation_sec':0.0,'persistence_sec':0.0}
    peak=peak_demand(flights)
    allow_remote=any(g.is_overflow for g in gates)

    def pack(assignments, meta=None, *, solved=None, fixed=False):
        nonlocal verified_at
        meta=meta or {}
        before=time.perf_counter()
        checked=evaluate_gate_assignment(assignments,flights,gates,cfg)
        timings['validation_sec']+=time.perf_counter()-before
        valid=bool(checked.feasible and checked.constraint_diagnostics.is_valid)
        if not valid and not fixed:
            return None
        if verified_at is None and valid:
            verified_at=time.perf_counter()-started
        trace={**(solved.solver_configuration if solved is not None else {}),**meta}
        reason=solved.termination_reason if solved is not None else 'FEASIBLE_FOUND'
        reason=getattr(reason,'value',reason)
        proven=bool(solved is not None and solved.optimality_proven and valid)
        return finite_metadata({'status': 'FIXED_PLAN' if fixed else 'OPTIMAL' if proven else 'FEASIBLE',
            'feasible':valid, 'algorithm':payload['algorithm'],'mode':payload['mode'],'seed':payload['seed'],
            'solver_protocol_version':PROTOCOL_VERSION,'solver_profile':payload.get('solver_profile','optimized'),
            'case_fingerprint':fingerprint(payload),'solution_source':meta.get('solution_source','SOLVER'),
            'termination_reason':reason,'time_to_verified_incumbent_sec':verified_at,
            'runtime_sec':time.perf_counter()-started,'budget_compliant':False,'timings':dict(timings),
            'assigned_count':len(assignments),'assignments':[a.to_dict() for a in assignments.values()],
            'decision_cost':checked.objective_breakdown.decision_cost if valid else None,
            'risk_cost':checked.objective_value if fixed else None,
            'breakdown':checked.objective_breakdown.to_dict(), 'conflicts':checked.constraint_diagnostics.conflict_count,
            'diagnostic':checked.constraint_diagnostics.to_dict(),'peak':peak,
            'remote_count':sum(a.is_overflow for a in assignments.values()),
            'reassignments':sum(f.nominal_gate_id is not None and f.flight_id in assignments
                and assignments[f.flight_id].gate_id!=f.nominal_gate_id for f in flights),
            'optimality_proven':proven,'best_bound':solved.best_bound if solved is not None else meta.get('best_bound'),
            'gap':solved.optimality_gap if solved is not None else None,'trace':trace})

    def incumbent(assignments, meta):
        nonlocal best,soft_deadline,reserve
        candidate=pack(assignments,meta)
        if candidate is None:
            return
        rank={'GREEDY_INITIALIZER':0,'GREEDY_FALLBACK':1,'SOLVER':2}
        if best is not None:
            if candidate['decision_cost']>best['decision_cost']+1e-9:
                return
            if abs(candidate['decision_cost']-best['decision_cost'])<1e-9 and rank[candidate['solution_source']]<rank[best['solution_source']]:
                return
        best=candidate
        if publish:
            before=time.perf_counter();publish(candidate)
            timings['persistence_sec']+=time.perf_counter()-before
        overhead=timings['validation_sec']+timings['persistence_sec']
        reserve=min(.9*budget,max(reserve,2*overhead))
        soft_deadline=hard_deadline-reserve

    try:
        if payload['mode']=='fixed':
            best=pack(adjusted_assignments(payload['initial'],flights),fixed=True)
        else:
            alg=payload['algorithm'];initial=None
            if optimized and alg in ('cpsat','hybrid'):
                before=time.perf_counter()
                greedy=DeterministicGreedyGateSolver(cfg).solve(flights,gates,allow_overflow=allow_remote)
                timings['initialization_sec']=time.perf_counter()-before
                if greedy.feasible:
                    initial=greedy.assignments
                    incumbent(initial,{'solution_source':'GREEDY_INITIALIZER','stage':'initialization',
                        'initial_solution_source':'GREEDY'})
            remaining=max(.001,soft_deadline-time.perf_counter())
            run_cfg=replace(cfg,time_limit_seconds=remaining,total_wall_clock_budget_seconds=remaining,
                            cp_sat_use_warm_start=optimized and initial is not None)
            if time.perf_counter()>=soft_deadline:
                raise SolverDeadlineExceeded()
            if alg=='cpsat':
                solved=CPSatGateSolver(run_cfg).solve(flights,gates,allow_overflow=allow_remote,
                    initial_assignments=initial,deadline_perf_counter=soft_deadline,
                    progress_callback=incumbent,complete_hints=optimized)
            elif alg=='hybrid':
                solved=HybridGateSolver(run_cfg,SAConfig(seed=payload['seed'],iterations=1000)).solve(
                    flights,gates,allow_overflow=allow_remote,initial_assignments=initial,
                    deadline_perf_counter=soft_deadline,progress_callback=incumbent,complete_hints=optimized)
            elif alg=='sa':
                solved=SimulatedAnnealingGateSolver(run_cfg,SAConfig(seed=payload['seed'],iterations=1000)).solve(
                    flights,gates,allow_overflow=allow_remote,deadline_perf_counter=soft_deadline,progress_callback=incumbent)
            else:
                solved=DeterministicGreedyGateSolver(run_cfg).solve(flights,gates,allow_overflow=allow_remote)
            trace=solved.solver_configuration
            model_ms=trace.get('model_construction_ms')
            timings['model_build_sec']=model_ms/1000 if model_ms is not None else None
            timings['search_sec']=trace.get('search_time_ms',solved.runtime_ms)/1000
            if solved.feasible:
                source='SOLVER'
                if alg=='hybrid' and trace.get('initial_solution_source')=='GREEDY_FALLBACK' and not trace.get('sa_executed'):
                    source='GREEDY_FALLBACK'
                candidate=pack(solved.assignments,{'solution_source':source},solved=solved)
                if candidate and (best is None or candidate['decision_cost']<=best['decision_cost']+1e-9):
                    best=candidate
            elif solved.status=='INFEASIBLE' and alg in ('cpsat','hybrid'):
                best={**empty_result(payload,time.perf_counter()-started,'PROVEN_INFEASIBLE'),
                      'status':'INFEASIBLE','termination_reason':'PROVEN_INFEASIBLE','trace':trace}
            elif best is None:
                reason='TIME_LIMIT' if time.perf_counter()>=soft_deadline or str(solved.status) in ('UNKNOWN','TIMEOUT_NO_SOLUTION') else 'NO_FEASIBLE_SOLUTION'
                best=empty_result(payload,time.perf_counter()-started,reason)
                best['status']='TIMEOUT' if reason=='TIME_LIMIT' else 'UNKNOWN'
    except SolverDeadlineExceeded:
        if best is None:
            best=empty_result(payload,time.perf_counter()-started)
        best.update(termination_reason='TIME_LIMIT',optimality_proven=False,gap=None)
    if best is None:
        best=empty_result(payload,time.perf_counter()-started)
    elapsed=time.perf_counter()-started
    if elapsed>=soft_deadline-started and not best.get('optimality_proven') and payload['mode']!='fixed':
        best['termination_reason']='TIME_LIMIT'
    best.update(runtime_sec=elapsed,budget_compliant=elapsed<=budget,timings=dict(timings))
    return finite_metadata(best)
