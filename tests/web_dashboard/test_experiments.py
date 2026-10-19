"""Behavioral tests: fair inputs, realized windows, accounting and resumability."""
from dataclasses import replace
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from web_dashboard.app import create_app
from web_dashboard.contracts import RunRequest
from web_dashboard.experiments import (adjusted_assignments, experiment_results, realized_flights,
    render_plan, snapshot_for, solve_case, summarize)
from web_dashboard.experiment_worker import execute
from web_dashboard.normalization import normalize_files
from web_dashboard.pipeline import json_write, run_pipeline


def payload(algorithm='greedy'):
    flights = [Flight('a', 0, 'DL', '1', 100, 160, 100, buffer_min=15, precomputed_gate_out_min=160),
               Flight('b', 1, 'DL', '2', 200, 260, 200, buffer_min=15, precomputed_gate_out_min=260)]
    return {'flights': [f.to_dict() for f in flights], 'gates': [Gate('G001',0).to_dict()],
            'solver_config': GateOptimizationConfig().to_dict(), 'algorithm': algorithm,
            'mode': 'benchmark', 'seed': 202601, 'budget': 1}


@pytest.mark.parametrize('algorithm', ['greedy', 'cpsat', 'sa', 'hybrid'])
def test_four_independent_solvers_are_verified(algorithm):
    result = solve_case(payload(algorithm))
    assert result['feasible'] and result['assigned_count'] == 2 and result['conflicts'] == 0
    assert result['algorithm'] == algorithm
    if algorithm in ('sa', 'greedy'):
        assert not result['optimality_proven']
    if algorithm == 'sa':
        assert 'sa' in str(result['trace']).lower()


def test_fixed_plan_updates_windows_and_detects_new_conflict():
    base = payload()
    plan = solve_case(base)['assignments']
    changed = [Flight.from_dict(f) for f in base['flights']]
    changed[0] = replace(changed[0], precomputed_gate_out_min=230)
    fixed = solve_case({**base, 'flights': [f.to_dict() for f in changed], 'initial': plan, 'mode': 'fixed'})
    assert not fixed['feasible'] and fixed['conflicts'] > 0
    assert fixed['risk_cost'] > 0 and fixed['decision_cost'] is None
    assignments = adjusted_assignments(plan, changed)
    assert assignments['a'].occupancy_end_min == 245


def test_realization_recomputes_departure_and_conserves_unmatched():
    base = payload()
    snap = {'flights': base['flights'], 'pairing': [
        {'pair_id': 'a', 'arrival_leg_id': 'in', 'departure_leg_id': 'out'},
        {'pair_id': 'b', 'arrival_leg_id': None, 'departure_leg_id': 'only_out'}], 'predictions': {'out': -20}}
    realized = realized_flights(snap, ['in'], [200])
    assert realized[0].predicted_arrival_min == 300
    assert realized[0].precomputed_gate_out_min == 345
    assert realized[1].to_dict() == base['flights'][1]


def test_statistics_keep_timeout_in_denominator_and_cost_null():
    rows = [{'algorithm': 'cpsat', 'mode': 'recourse', 'status': 'TIMEOUT', 'feasible': False,
             'decision_cost': None, 'risk_cost': None, 'runtime_sec': 1, 'conflicts': None},
            {'algorithm': 'cpsat', 'mode': 'recourse', 'status': 'FEASIBLE', 'feasible': True,
             'decision_cost': 10, 'risk_cost': None, 'runtime_sec': .1, 'conflicts': 0,
             'remote_count': 0, 'reassignments': 1}]
    group = summarize(rows)[0]
    assert group['feasible_rate'] == .5 and group['timeouts'] == 1
    assert group['mean'] == 10 and group['cost_sample_count'] == 1
    assert group['mean_ci95'] is None and group['rate_ci95']


@pytest.fixture
def prepared(tmp_path, raw_table):
    raw = tmp_path / 'raw.parquet'
    raw_table.to_parquet(raw)
    frame, report = normalize_files([raw])
    app = create_app(tmp_path / 'runtime', launch_jobs=False)
    store = app.state.store
    did = 'a'*32
    store.put_dataset(did, report)
    cfg = RunRequest(dataset_id=did, service_date='2026-07-01', preset='custom', contact_gates=3, solver='greedy')
    rid = store.create_run(cfg.model_dump(mode='json'))
    run_pipeline(frame, cfg, store.root / 'runs' / rid, report)
    store.update(rid, status='completed', stage='done')
    return app, store, rid


def test_api_benchmark_mc_resume_and_exports(prepared):
    app, store, rid = prepared
    with TestClient(app) as client:
        snapshot = snapshot_for(store, rid)
        arrivals = sorted(snapshot['marginals'])
        unchanged = realized_flights(snapshot, arrivals, [snapshot['predictions'][fid] for fid in arrivals])
        assert [f.to_dict() for f in unchanged] == snapshot['flights']
        plans = client.get(f'/api/runs/{rid}/plans').json()
        assert plans['ready'] and plans['plans'][0]['id'] == 'pipeline'
        request = {'kind': 'benchmark', 'time_limit_sec': 1}
        exp = client.post(f'/api/runs/{rid}/experiments', json=request).json()
        eid = exp['id']
        assert client.post('/api/runs', json=store.run(rid)['config']).status_code == 409
        assert client.post(f'/api/runs/{rid}/experiments', json=request).status_code == 409
        execute(store.root, eid)
        done = client.get(f'/api/experiments/{eid}').json()
        assert done['status'] == 'completed' and done['completed'] == 4
        output = client.get(f'/api/experiments/{eid}/results').json()
        assert len(output['groups']) == 4
        assert len({c['snapshot_hash'] for c in output['cases']}) == 1
        for c in output['cases']:
            if c['feasible']:
                plan = client.get(f"/api/experiments/{eid}/plans/{c['case_id']}").json()
                assert plan['summary']['assigned_count'] == 3
                detail = client.get(f"/api/experiments/{eid}/cases/{c['case_id']}").json()
                assert detail['diagnostic']['is_valid']
                assert 'solver_name' in detail['trace']
        assert client.get(f'/api/experiments/{eid}/exports/bundle').content[:2] == b'PK'
        mc = client.post(f'/api/runs/{rid}/experiments', json={
            'kind': 'montecarlo', 'scenarios': 10, 'time_limit_sec': 1, 'plan_ids': ['pipeline']}).json()
        mid = mc['id']
        # Cancel before first slot, resume exactly the same realization matrix.
        store.experiment_update(mid, cancel_requested=1)
        execute(store.root, mid)
        assert store.experiment(mid)['status'] == 'cancelled'
        before = np.load(store.root/'experiments'/mid/'samples.npy')
        assert client.post(f'/api/experiments/{mid}/resume').status_code == 202
        execute(store.root, mid)
        assert store.experiment(mid)['completed'] == 20
        assert np.array_equal(before, np.load(store.root/'experiments'/mid/'samples.npy'))
        cases = store.cases(mid)
        assert len({c['case_id'] for c in cases}) == 20
        for i in range(10):
            assert len({c['realization_hash'] for c in cases if c['scenario'] == i}) == 1
        replay = client.get(f"/api/experiments/{mid}/plans/{cases[0]['case_id']}")
        assert replay.status_code == 200
        assert client.get(f'/api/experiments/{mid}/exports/cases.parquet').status_code == 200
        assert client.post(f'/api/experiments/{mid}/resume').status_code == 409
        assert client.post(f'/api/runs/{rid}/experiments', json={
            'kind': 'montecarlo', 'plan_ids': ['foreign.plan']}).status_code == 422


def test_snapshot_tampering_rejected_and_restart_recovers(prepared):
    app, store, rid = prepared
    snap = snapshot_for(store, rid)
    eid = store.create_experiment(rid, {'kind': 'benchmark'}, 4)
    store.recover()
    assert store.experiment(eid)['status'] == 'interrupted'
    snap['flights'][0]['predicted_arrival_min'] += 1
    json_write(store.root/'runs'/rid/'snapshot.json', snap)
    with pytest.raises(ValueError, match='Snapshot'):
        snapshot_for(store, rid)


def test_download_blocked_until_atomic_export_finishes(prepared, monkeypatch):
    from web_dashboard import experiment_worker
    app, store, rid = prepared
    original_export = experiment_worker.export_experiment
    observations = []
    with TestClient(app) as client:
        exp = client.post(f'/api/runs/{rid}/experiments', json={'kind': 'benchmark', 'algorithms': ['greedy']}).json()
        eid = exp['id']
        def inspect_export(*args, **kwargs):
            observations.append(store.experiment(eid)['status'])
            assert client.get(f'/api/experiments/{eid}/exports/bundle').status_code == 409
            return original_export(*args, **kwargs)
        monkeypatch.setattr(experiment_worker, 'export_experiment', inspect_export)
        execute(store.root, eid)
        assert observations == ['running']
        assert store.experiment(eid)['status'] == 'completed'
        assert client.get(f'/api/experiments/{eid}/exports/bundle').content[:2] == b'PK'
