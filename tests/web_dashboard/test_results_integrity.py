import copy
import json

import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, GateAssignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from web_dashboard.experiments import summarize, experiment_results
from web_dashboard.solver_execution import solve_case_v2, verify_artifact, recover_artifact
from web_dashboard.storage import Store


def payload(waiting=False, fixed=False):
    flights = [Flight('a', 0, 'DL', '1', 0, 3, 0, min_turnaround_min=1, buffer_min=0,
                      precomputed_gate_out_min=3, nominal_gate_id='H')]
    value = dict(flights=[f.to_dict() for f in flights], gates=[Gate('G').to_dict(), Gate('H', 1).to_dict()],
        solver_config=GateOptimizationConfig(reassignment_weight=.001, overflow_weight=.002, delay_weight=0, risk_weight=0).to_dict(),
        algorithm='cpsat', mode='fixed' if fixed else 'benchmark', seed=202601, budget=1,
        solver_protocol_version=2, solver_profile='optimized')
    if waiting:
        value['waiting_config'] = dict(max_gate_wait_min=2, wait_weight=1, reassignment_weight=10, remote_weight=200)
    if fixed:
        value['initial'] = [{**GateAssignment('a', 'H', occupancy_start_min=0, occupancy_end_min=3).to_dict(), 'gate_wait_min': 0}]
    return value


@pytest.mark.parametrize('formulation', ['sparse_interval', 'sparse_pairwise', 'dense_pairwise'])
def test_subcent_objective_proves_the_true_optimum(formulation):
    p = payload()
    cfg = GateOptimizationConfig(**{**p['solver_config'], 'cp_sat_formulation': formulation, 'cp_sat_use_warm_start': False})
    result = CPSatGateSolver(cfg).solve([Flight.from_dict(f) for f in p['flights']], [Gate.from_dict(g) for g in p['gates']], allow_overflow=False)
    assert result.optimality_proven and result.assignments['a'].gate_id == 'H'
    assert result.objective_breakdown.decision_cost == 0 and result.best_bound == 0
    assert result.solver_configuration['scale_factor'] == 1000
    assert result.solver_configuration['objective_encoding'] == 'exact_decimal_v1'


def test_unsafe_objective_scale_is_rejected():
    with pytest.raises(ValueError, match='unsafe integer scale'):
        GateOptimizationConfig(reassignment_weight=1e-30)


@pytest.mark.parametrize('waiting', [False, True])
def test_fixed_risk_and_nonfinite_costs_cannot_be_forged(waiting):
    p = payload(waiting, True)
    result = solve_case_v2(p)
    verify_artifact(p, result)
    assert summarize([result])[0]['on_time_feasible_count'] == 1
    with pytest.raises(ValueError):
        verify_artifact(p, {**result, 'risk_cost': result['risk_cost']+5})
    with pytest.raises(ValueError, match='Non-finite'):
        verify_artifact(p, {**result, 'decision_cost': float('nan')})


def test_proof_and_runtime_must_agree():
    p = payload()
    result = solve_case_v2(p)
    assert result['optimality_proven']
    verify_artifact(p, result)
    for update in ({'solution_source': 'GREEDY_INITIALIZER'}, {'gap': 1}, {'best_bound': 99},
                   {'budget_compliant': False}, {'runtime_sec': 2}):
        with pytest.raises(ValueError):
            verify_artifact(p, {**result, **update})
    recovered = recover_artifact(p, result, 2, 'TIME_LIMIT')
    assert not recovered['optimality_proven'] and recovered['gap'] is None and recovered['best_bound'] is None
    legacy = {**result, 'artifact_schema_version': 0}
    verified = verify_artifact(p, legacy)
    assert not verified['optimality_proven'] and result['optimality_proven']
    bad = copy.deepcopy(result)
    bad['assignments'][0]['occupancy_start_min'] += .5
    with pytest.raises(ValueError, match='integer minutes'):
        verify_artifact(p, bad)
    bad = copy.deepcopy(result)
    bad['breakdown']['reassignment_cost'] = 123
    with pytest.raises(ValueError, match='cost component'):
        verify_artifact(p, bad)


def test_cvar_accounts_for_fractional_tail_mass():
    rows = [dict(algorithm='greedy', mode='recourse', status='FEASIBLE', feasible=True,
                 decision_cost=float(v), risk_cost=None, runtime_sec=0, conflicts=0) for v in range(1, 22)]
    result = summarize(rows)[0]
    assert result['cvar95'] == pytest.approx((21+.05*20)/1.05)


def test_paired_statistics_require_same_realization(tmp_path):
    store = Store(tmp_path)
    eid = store.create_experiment('r', dict(kind='montecarlo', seed=42, solver_protocol_version=2), 2)
    store.experiment_update(eid, status='completed')
    for index, plan in enumerate(('p1', 'p2')):
        store.put_case(eid, dict(case_id=plan, algorithm='greedy', mode='recourse', scenario=0,
            source_plan_id=plan, snapshot_hash='s', realization_hash=f'different_{index}',
            status='FEASIBLE', feasible=True, decision_cost=10., risk_cost=None, runtime_sec=.01, conflicts=0,
            solver_protocol_version=2, solver_profile='optimized', budget_compliant=True, solution_source='SOLVER'))
    result = experiment_results(store, eid)
    assert result['paired'][0]['pairs'] == 0
    assert result['paired'][0]['excluded_unmatched'] == 1
    assert result['completion']['completed'] == result['completion']['requested'] == 2


def test_export_checksums_and_interrupted_publication(tmp_path, monkeypatch):
    import zipfile
    from web_dashboard.exports import write_bundle, verify_exports
    import web_dashboard.exports as exports
    (tmp_path / 'result.json').write_text('{"cost":0}')
    write_bundle(tmp_path, ['result.json'])
    verify_exports(tmp_path)
    original = (tmp_path / 'bundle.zip').read_bytes()
    with zipfile.ZipFile(tmp_path / 'bundle.zip') as archive:
        assert set(archive.namelist()) == {'result.json', 'checksums.json'}
    replace = exports.replace_retry
    def interrupt(source, target):
        if target.name == 'bundle.zip':
            raise OSError('fixture interruption')
        return replace(source, target)
    monkeypatch.setattr(exports, 'replace_retry', interrupt)
    with pytest.raises(OSError):
        write_bundle(tmp_path, ['result.json'])
    assert (tmp_path / 'bundle.zip').read_bytes() == original
    assert not list(tmp_path.glob('*.tmp'))
    (tmp_path / 'result.json').write_text('{"cost":999}')
    with pytest.raises(ValueError, match='checksum mismatch'):
        verify_exports(tmp_path)


def test_publication_snapshot_integrity_and_failed_activation(tmp_path, monkeypatch):
    from src.pipeline import thesis_release as release
    import hashlib
    monkeypatch.setattr(release, 'ROOT', tmp_path)
    source = tmp_path / 'src/model.py'
    source.parent.mkdir()
    source.write_bytes(b'updated code')
    output = tmp_path / 'run'
    snapshot = output / 'source_snapshot/src/model.py'
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b'published code')
    (output / 'source_hashes.json').write_text(json.dumps({'src/model.py': hashlib.sha256(snapshot.read_bytes()).hexdigest()}))
    assert release.inspect_source_lineage(output) == {'snapshot_integrity': True, 'matches_current_code': False}
    with pytest.raises(ValueError, match='current publication code'):
        release.inspect_source_lineage(output, require_current=True)
    active = tmp_path / 'artifacts/thesis_completion/active_profile.json'
    active.parent.mkdir(parents=True)
    active.write_text('{"published":"unchanged"}')
    before = active.read_bytes()
    with pytest.raises(ValueError, match='Legacy run'):
        release.validate_lineage(output)
    monkeypatch.setattr(release, 'validate', lambda _: (_ for _ in ()).throw(ValueError('qualification failed')))
    with pytest.raises(ValueError, match='qualification failed'):
        release.activate(output)
    assert active.read_bytes() == before
    snapshot.write_bytes(b'corrupted snapshot')
    with pytest.raises(ValueError, match='snapshot integrity'):
        release.inspect_source_lineage(output)


def test_evaluated_model_must_match_the_model_activated():
    from src.pipeline.thesis_release import verify_freeze_records
    frozen = {'models': {'arrival': {'path':'models/a.joblib', 'sha256':'old', 'threshold':.25}}}
    records = {'arrival': {**frozen['models']['arrival'], 'historical_2023': {'mae':1}}}
    verify_freeze_records(frozen, records)
    records['arrival']['sha256'] = 'different_model'
    with pytest.raises(ValueError, match='provenance differs'):
        verify_freeze_records(frozen, records)
