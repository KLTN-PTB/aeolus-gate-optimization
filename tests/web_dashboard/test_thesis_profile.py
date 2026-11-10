import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.binary_improvement_execution import digest
from src.optimization.domain import Flight, Gate, GateAssignment
from web_dashboard.contracts import RunRequest
from web_dashboard.normalization import normalize_files
from web_dashboard.pipeline import ROOT, run_pipeline
from web_dashboard.solver_execution import solve_case_v2, verify_artifact
import web_dashboard.thesis_profile as profiles


@pytest.fixture
def smoke_profile(monkeypatch):
    folder = ROOT / 'artifacts/thesis_completion/smoke_verified_20261022'
    if (folder / 'model_results.json').exists():
        records = json.loads((folder / 'model_results.json').read_text())
        for rec in records.values():
            rec['path'] = (folder / rec['path']).relative_to(ROOT).as_posix()
        value = {'version': folder.name, 'models': records, 'model_run':folder.relative_to(ROOT).as_posix(),
                 'evaluation_scope':'historical_2023_already_seen','comparison':{}, 'residuals': {
            t: {'path': (folder / 'models' / f'{t}_residuals.joblib').relative_to(ROOT).as_posix(),
                'sha256': digest(folder / 'models' / f'{t}_residuals.joblib')} for t in ('arrival', 'departure')}}
    elif profiles.ACTIVE.exists():
        value = json.loads(profiles.ACTIVE.read_text(encoding='utf-8'))
    else:
        pytest.skip('Neither local smoke artifacts nor shipped proposal bundles are installed')
    monkeypatch.setattr(profiles, 'profile', lambda: value)
    return value


def test_proposal_inference_waiting_and_outcome_isolation(tmp_path, raw_table, smoke_profile):
    source = tmp_path / 'input.parquet'
    raw_table.to_parquet(source, index=False)
    frame, report = normalize_files([source])
    request = RunRequest(dataset_id='a'*32, service_date='2026-07-01', solver='cpsat',
                         model_profile='thesis_xgboost', gate_time_mode='bounded_wait', time_limit_sec=2)
    first = run_pipeline(frame, request, tmp_path / 'first', report)
    frame[['ARR_DELAY', 'DEP_DELAY']] = -9999
    second = run_pipeline(frame, request, tmp_path / 'second', report)
    assert first['summary']['feasible'] and first['summary']['independent_verifier_valid']
    assert first['summary']['objective_version'] == 'gate_wait_v1'
    assert len(first['predictions']) == 4
    for a, b in zip(first['predictions'], second['predictions']):
        assert a['predicted_delay_min'] == b['predicted_delay_min']
        assert a['probability_delay_15'] == b['probability_delay_15']
        assert 0 <= a['probability_delay_15'] <= 1
        assert isinstance(a['predicted_delayed'], bool)
        assert a['predicted_delayed'] == (a['probability_delay_15'] >= a['decision_threshold'])
        assert a['classification_model_sha256'] == smoke_profile['models'][
            f"{'arrival' if a['flight_direction'] == 'ARR' else 'departure'}_classification_xgboost"]['sha256']
    assert first['assignments'] == second['assignments']
    snapshot = json.loads((tmp_path / 'first/snapshot.json').read_text())
    ids, sample = profiles.sample_residual_delays(snapshot, 500, 123)
    assert sample.shape == (500, 4) and len(ids) == 4
    np.testing.assert_array_equal(sample, profiles.sample_residual_delays(snapshot, 500, 123)[1])
    for task, direction in (('arrival', 'ARR'), ('departure', 'DEP')):
        for kind in ('classification', 'regression'):
            minimal_schedule = frame.loc[frame.direction.eq(direction)].iloc[:1].drop(columns=['MONTH','DAY_OF_MONTH','DAY_OF_WEEK'])
            explanation = profiles.explain(minimal_schedule, task, kind)
            assert len(explanation['values'][0]) == len(explanation['features'])


def test_waiting_supervision_rejects_modified_cost_and_wait():
    flights = [Flight('a', 0, 'DL', '1', 0, 60, 0, nominal_gate_id='G', precomputed_gate_out_min=60),
               Flight('b', 1, 'DL', '2', 55, 115, 55, nominal_gate_id='G', precomputed_gate_out_min=115)]
    payload = {'flights': [f.to_dict() for f in flights], 'gates': [Gate('G').to_dict()],
               'waiting_config': {'max_gate_wait_min': 30}, 'algorithm': 'hybrid', 'mode': 'benchmark',
               'seed': 202601, 'budget': 1, 'solver_protocol_version': 2}
    checkpoints = []
    result = solve_case_v2(payload, publish=checkpoints.append)
    assert verify_artifact(payload, result)['feasible'] and checkpoints
    forged = json.loads(json.dumps(result))
    forged['decision_cost'] += 1
    with pytest.raises(ValueError, match='cost'):
        verify_artifact(payload, forged)
    forged = json.loads(json.dumps(result))
    forged['assignments'][0]['gate_wait_min'] += 1
    with pytest.raises(ValueError, match='waiting'):
        verify_artifact(payload, forged)


def test_proposal_api_explanation_uses_run_checkpoint(tmp_path, raw_table, smoke_profile):
    import io
    from fastapi.testclient import TestClient
    from web_dashboard.app import create_app
    from web_dashboard.worker import execute
    with TestClient(create_app(tmp_path, launch_jobs=False)) as client:
        assert client.get('/api/model-profiles').json()[1]['ready']
        raw = io.BytesIO()
        raw_table.to_parquet(raw, index=False)
        dataset = client.post('/api/datasets', files={'files':('raw.parquet',raw.getvalue())}).json()
        response = client.post('/api/runs', json={'dataset_id':dataset['id'], 'service_date':'2026-07-01',
            'solver':'greedy','model_profile':'thesis_xgboost','gate_time_mode':'bounded_wait'})
        assert response.status_code == 202, response.text
        rid = response.json()['id']
        execute(tmp_path, rid)
        result = client.get(f'/api/runs/{rid}/results').json()
        fid = result['predictions'][0]['flight_id']
        explanation = client.get(f'/api/runs/{rid}/explanation/{fid}?kind=classification')
        assert explanation.status_code == 200, explanation.text
        task = 'arrival' if result['predictions'][0]['flight_direction']=='ARR' else 'departure'
        assert explanation.json()['model_sha256'] == smoke_profile['models'][f'{task}_classification_xgboost']['sha256']
        assert client.get(f'/api/runs/{rid}/explanation/{fid}?kind=bad').status_code == 422
        assert client.get(f'/api/runs/{rid}/explanation/unknown').status_code == 404
        assert client.get('/api/model-comparison').status_code == 200
        assert client.get(f'/api/runs/{rid}/plans').json()['has_uncertainty']
        response = client.post(f'/api/runs/{rid}/experiments', json={'kind':'montecarlo','scenarios':10,
            'time_limit_sec':1,'plan_ids':['pipeline']})
        assert response.status_code == 202, response.text
        eid = response.json()['id']
        from web_dashboard.experiment_worker import execute as execute_experiment
        store = client.app.state.store
        store.experiment_update(eid,cancel_requested=1)
        execute_experiment(tmp_path,eid)
        before = np.load(tmp_path / 'experiments' / eid / 'samples.npy')
        assert before.shape == (10,4)
        assert client.post(f'/api/experiments/{eid}/resume').status_code == 202
        execute_experiment(tmp_path,eid)
        assert store.experiment(eid)['status'] == 'completed'
        np.testing.assert_array_equal(before,np.load(tmp_path / 'experiments' / eid / 'samples.npy'))
        cases = store.cases(eid)
        assert len(cases)==20 and not any(c['status']=='ERROR' for c in cases)
        assert client.get(f'/api/experiments/{eid}/plans/{cases[0]["case_id"]}').status_code == 200


def test_frozen_waits_and_dual_realizations_survive_resampling():
    from web_dashboard.experiments import adjusted_assignments, realized_flights
    from src.optimization.waiting import solve_waiting
    flights = [Flight('turn',0,'DL','1',60,180,60,precomputed_gate_out_min=180)]
    snapshot = {'flights':[f.to_dict() for f in flights], 'pairing':[{'pair_id':'turn','arrival_leg_id':'a','departure_leg_id':'d'}],
                'predictions':{'a':0.,'d':0.}}
    realized = realized_flights(snapshot,['a','d'],[20,50])
    assert realized[0].occupancy_start_min == 80 and realized[0].simulated_departure_min == 230
    initial = [{**GateAssignment('turn','G',occupancy_start_min=70,occupancy_end_min=205).to_dict(), 'gate_wait_min':10}]
    fixed = adjusted_assignments(initial,realized)
    assert fixed['turn'].occupancy_start_min == 90 and fixed['turn'].occupancy_end_min == 255


def test_streamlit_proposal_workflow_does_not_launch_browser(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from dashboard.pages import page_06_thesis_profile
    monkeypatch.setattr(page_06_thesis_profile,'profiles',lambda:[{'id':'thesis_xgboost','ready':False,'reason':'Training in progress'}])
    at = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30)
    at.session_state['current_page'] = '02_flight_intelligence'
    at.session_state['proposal_workflow'] = True
    at.run()
    assert not at.exception
    assert any('Training in progress' in x.value for x in at.info)


def test_atomic_metadata_survives_transient_windows_reader_lock(tmp_path, monkeypatch):
    from web_dashboard.pipeline import json_write
    original = Path.replace
    attempts = []
    def locked_then_released(source, target):
        if Path(target).name == 'progress.json':
            attempts.append(1)
            if len(attempts) <= 2:
                raise PermissionError('Windows reader still holds the old metadata file')
        return original(source, target)
    monkeypatch.setattr(Path,'replace',locked_then_released)
    target = tmp_path / 'progress.json'
    target.write_text('{"completed": 499}')
    json_write(target,{'completed':500,'cost':1.25})
    assert json.loads(target.read_text()) == {'completed':500,'cost':1.25}
    assert not target.with_suffix('.json.tmp').exists()
    with pytest.raises(ValueError):
        json_write(target,{'cost':float('nan')})
