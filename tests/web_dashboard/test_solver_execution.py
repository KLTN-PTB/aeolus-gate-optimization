"""Behavioral checks for deadline recovery, provenance and immutable caches."""
from dataclasses import replace
from types import SimpleNamespace
import json
import time

import pytest
from ortools.sat.python import cp_model

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.execution import SolverDeadlineExceeded
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from web_dashboard import experiment_worker as worker
from web_dashboard.experiments import solve_case, summarize
from web_dashboard.pipeline import json_write
from web_dashboard.solver_execution import cost_eligible, verify_artifact, recover_artifact


def payload(algorithm='greedy', profile='optimized'):
    fs=[Flight('a',7,'DL','1',100,160,100,nominal_gate_id='G1'),
        Flight('b',99,'DL','2',200,260,200,nominal_gate_id='G1')]
    return {'flights':[f.to_dict() for f in fs], 'gates':[Gate('G1',0).to_dict(),Gate('G2',1).to_dict()],
            'solver_config':GateOptimizationConfig().to_dict(),'algorithm':algorithm,'mode':'benchmark',
            'seed':202601,'budget':1,'solver_protocol_version':2,'solver_profile':profile,'snapshot_hash':'test','case_id':'test'}


def test_frozen_window_cache_and_replace_have_independent_lifetimes():
    f=Flight.from_dict(payload()['flights'][0])
    assert f.time_window is f.time_window
    fresh=replace(f,predicted_arrival_min=120)
    assert fresh.time_window is not f.time_window
    assert fresh.time_window.start_min==120 and f.time_window.start_min==100
    assert Flight.from_dict(f.to_dict()).time_window==f.time_window


@pytest.mark.parametrize('profile',['optimized','baseline'])
@pytest.mark.parametrize('algorithm',['greedy','cpsat','sa','hybrid'])
def test_profiles_return_verified_solutions_with_actual_iterations(algorithm,profile):
    case=solve_case(payload(algorithm,profile))
    assert case['feasible'] and case['budget_compliant'] and case['conflicts']==0
    assert case['solution_source']=='SOLVER'
    assert cost_eligible(case)
    if algorithm in ('sa','hybrid'):
        assert 0<=case['trace']['sa_iterations']<=1000
    verify_artifact(payload(algorithm,profile),case)


@pytest.mark.parametrize('formulation',['sparse_interval','sparse_pairwise','dense_pairwise'])
def test_cp_complete_hint_and_callback_do_not_depend_on_flight_indices(monkeypatch,formulation):
    request=payload('cpsat');fs=[Flight.from_dict(f) for f in request['flights']];gs=[Gate.from_dict(g) for g in request['gates']]
    cfg=GateOptimizationConfig(cp_sat_use_warm_start=True,cp_sat_formulation=formulation)
    initial=DeterministicGreedyGateSolver(cfg).solve(fs,gs).assignments
    original=cp_model.CpSolver.Solve
    seen=[]
    def capture(solver,model,*args):
        proto=model.Proto()
        assert len(proto.solution_hint.vars)==len(proto.variables)==4
        assert sorted(proto.solution_hint.values)==[0,0,1,1]
        return original(solver,model,*args)
    monkeypatch.setattr(cp_model.CpSolver,'Solve',capture)
    result=CPSatGateSolver(cfg).solve(fs,gs,allow_overflow=False,initial_assignments=initial,complete_hints=True,
        deadline_perf_counter=time.perf_counter()+2,progress_callback=lambda a,m:seen.append((a,m)))
    assert result.feasible and seen
    assert all(evaluate_gate_assignment(a,fs,gs,cfg).feasible for a,_ in seen)


def test_cp_deadline_can_interrupt_preparation_before_search():
    p=payload('cpsat')
    with pytest.raises(SolverDeadlineExceeded):
        CPSatGateSolver().solve([Flight.from_dict(f) for f in p['flights']],
            [Gate.from_dict(g) for g in p['gates']],deadline_perf_counter=time.perf_counter()-1)


def test_slow_initializer_is_kept_but_never_ranked_as_cpsat(monkeypatch):
    import web_dashboard.solver_execution as execution
    clock=SimpleNamespace(now=10.)
    fs,gs,cfg=execution.problem(payload('cpsat'))
    initial=DeterministicGreedyGateSolver(cfg).solve(fs,gs)
    def slow(*a,**k):
        clock.now+=1.5
        return initial
    monkeypatch.setattr(execution,'time',SimpleNamespace(perf_counter=lambda:clock.now))
    monkeypatch.setattr(DeterministicGreedyGateSolver,'solve',slow)
    published=[]
    result=solve_case(payload('cpsat'),publish=published.append)
    assert result['feasible'] and published
    assert result['runtime_sec']==1.5 and not result['budget_compliant']
    assert result['termination_reason']=='TIME_LIMIT' and result['solution_source']=='GREEDY_INITIALIZER'
    assert not cost_eligible(result)


def test_recovery_reverifies_inputs_assignment_and_cost():
    p=payload();result=solve_case(p)
    for tampered in ({**p,'seed':9},{**p,'solver_profile':'baseline'},{**p,'budget':2}):
        with pytest.raises(ValueError,match='does not match'):
            verify_artifact(tampered,result)
    bad={**result,'assignments':[dict(a,gate_id='unknown') for a in result['assignments']]}
    with pytest.raises(ValueError):verify_artifact(p,bad)
    with pytest.raises(ValueError):verify_artifact(p,{**result,'decision_cost':99})
    with pytest.raises(ValueError):verify_artifact(p,{**result,'conflicts':99})
    fixed_payload={**p,'mode':'fixed','initial':result['assignments']}
    fixed=solve_case(fixed_payload)
    with pytest.raises(ValueError):verify_artifact(fixed_payload,{**fixed,'risk_cost':99})
    recovered=recover_artifact(p,result,1.1,'TIME_LIMIT')
    assert recovered['feasible'] and not recovered['budget_compliant']
    assert not recovered['optimality_proven'] and recovered['gap'] is None


def test_statistics_keep_late_and_initializer_in_denominator_but_out_of_costs():
    base=solve_case(payload('cpsat'))
    cases=[base,{**base,'runtime_sec':1.2,'budget_compliant':False,'decision_cost':-1,'termination_reason':'TIME_LIMIT'},
           {**base,'solution_source':'GREEDY_INITIALIZER','decision_cost':-2}]
    g=summarize(cases)[0]
    assert g['count']==g['feasible_count']==3
    assert g['on_time_feasible_count']==1 and g['cost_sample_count']==1
    assert g['mean']==base['decision_cost'] and g['timeouts']==1 and g['initializer_only_count']==1


def fake_supervisor(monkeypatch,tmp_path, *, invalid=False,cancel=False,start=True):
    p=payload();initial=solve_case(p);clock=SimpleNamespace(now=100.)
    class Host:
        killed=False
        returncode=-9
        def poll(self):return -1 if self.killed else None
        def write(self,line):
            inp,out,ready=map(__import__('pathlib').Path,json.loads(line))
            if start:ready.write_text('100',encoding='ascii')
            json_write(out.with_suffix('.incumbent.json'),{**initial,'case_fingerprint':'wrong'} if invalid else initial)
        def flush(self):pass
    host=Host();host.stdin=host
    def stop(proc):
        proc.killed=True;clock.now+=.005
    monkeypatch.setattr(worker,'CASE_HOST',host)
    monkeypatch.setattr(worker,'stop_owned',stop)
    monkeypatch.setattr(worker,'time',SimpleNamespace(perf_counter=lambda:clock.now,sleep=lambda sec:setattr(clock,'now',clock.now+sec)))
    store=SimpleNamespace(experiment=lambda eid:{'cancel_requested':int(cancel)})
    return p,host,store


def test_watchdog_keeps_verified_incumbent_and_cached_retry_is_identical(monkeypatch,tmp_path):
    p,host,store=fake_supervisor(monkeypatch,tmp_path)
    result=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert host.killed and result['feasible'] and not result['budget_compliant']
    assert result['runtime_sec']>1 and result['termination_reason']=='TIME_LIMIT'
    cached=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert cached['assignments']==result['assignments'] and cached['runtime_sec']==result['runtime_sec']


def test_watchdog_rejects_invalid_checkpoint(monkeypatch,tmp_path):
    p,host,store=fake_supervisor(monkeypatch,tmp_path,invalid=True)
    result=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert host.killed and not result['feasible'] and not result['assignments']


def test_cancel_discards_uncommitted_partial_case_for_paid_recomputation(monkeypatch,tmp_path):
    p,host,store=fake_supervisor(monkeypatch,tmp_path,cancel=True)
    assert worker.supervised_case(store,'eid',tmp_path,'test',p) is None
    assert host.killed and not (tmp_path/'test.incumbent.json').exists()


def test_startup_failure_is_separate_from_solver_timeout(monkeypatch,tmp_path):
    p,host,store=fake_supervisor(monkeypatch,tmp_path,start=False)
    result=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert host.killed and result['status']=='ERROR' and result['termination_reason']=='ERROR'


def test_hybrid_cp_stage_includes_build_and_does_not_claim_requested_sa_iterations(monkeypatch):
    import src.optimization.solvers.budgeted_hybrid as hybrid
    p=payload('hybrid');fs=[Flight.from_dict(f) for f in p['flights']];gs=[Gate.from_dict(g) for g in p['gates']]
    cfg=GateOptimizationConfig(time_limit_seconds=4,total_wall_clock_budget_seconds=4)
    def no_cp(self,*args,**kw):
        assert 0<self.config.total_wall_clock_budget_seconds<=2
        assert self.config.time_limit_seconds==self.config.total_wall_clock_budget_seconds
        return evaluate_gate_assignment({},fs,gs,cfg,solver_status='UNKNOWN')
    monkeypatch.setattr(hybrid.CPSatGateSolver,'solve',no_cp)
    result=HybridGateSolver(cfg,SAConfig(iterations=0)).solve(fs,gs,deadline_perf_counter=time.perf_counter()+4)
    assert result.feasible and result.solver_configuration['sa_iterations']==0
    assert result.solver_configuration['initial_solution_source']=='GREEDY_FALLBACK'


def test_atomic_output_without_done_marker_is_preserved_without_fabricated_runtime(tmp_path):
    p=payload();case=solve_case(p)
    json_write(tmp_path/'test.json',case)
    store=SimpleNamespace(experiment=lambda eid:{'cancel_requested':0})
    recovered=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert recovered['feasible'] and recovered['assignments']==case['assignments']
    assert not recovered['budget_compliant'] and recovered['timing_complete'] is False
    assert recovered['runtime_sec']==case['runtime_sec']
    assert recovered['termination_reason']=='ERROR' and not cost_eligible(recovered)


def test_worker_crash_preserves_incumbent_but_excludes_error_from_costs(monkeypatch,tmp_path):
    p,host,store=fake_supervisor(monkeypatch,tmp_path)
    original_write=host.write
    def crash(line):
        original_write(line)
        host.killed=True
    host.stdin=SimpleNamespace(write=crash,flush=lambda:None)
    result=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert result['feasible'] and result['termination_reason']=='ERROR'
    assert not cost_eligible(result)
    cached=worker.supervised_case(store,'eid',tmp_path,'test',p)
    assert cached['assignments']==result['assignments']
