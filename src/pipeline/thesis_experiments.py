"""Resumable proposal benchmarks and common-random-number robustness evidence."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.models.binary_improvement_execution import digest
from src.optimization.domain import Flight
from web_dashboard.contracts import RunRequest
from web_dashboard.experiments import realized_flights, summarize
from web_dashboard.normalization import normalize_files, REQUIRED
from web_dashboard.pipeline import ROOT, json_write, run_pipeline
from web_dashboard.solver_execution import fingerprint, solve_case_v2, verify_artifact
from web_dashboard.thesis_profile import sample_residual_delays, explain


def candidate_schedule(day):
    """Read only known 2023 schedule fields, never weather/actual operations."""
    if not str(day).startswith('2023-'):
        raise PermissionError('Proposal experiments are restricted to historical 2023 schedules')
    pieces = []
    for task in ('inbound_atl', 'outbound_atl'):
        files = sorted((ROOT / 'data/processed' / task / 'year=2023').glob('*.parquet'))
        dataset = ds.dataset(files, format='parquet')
        columns = [c for c in (*REQUIRED, 'TAIL_NUM') if c in dataset.schema.names]
        pieces.append(dataset.to_table(columns=columns, filter=ds.field('FL_DATE') == f'{day} 00:00:00').to_pandas())
    return pd.concat(pieces, ignore_index=True)


def selected_schedule(output, day, size, seed):
    destination = output / f'{day}_{size}'
    destination.mkdir(parents=True, exist_ok=True)
    source = destination / 'candidate_schedule.parquet'
    if not source.exists():
        candidate_schedule(day).to_parquet(source, index=False)
    frame, report = normalize_files([source])
    json_write(destination / 'normalization.json', report)
    if not report['can_run']:
        json_write(destination / 'normalization.json', report)
        raise ValueError(f'Invalid benchmark schedules: {report["errors"][:2]}')
    # Same calendar/representation constraints as the frozen model contract.
    eligible = frame.service_date.eq(day) & ~pd.to_datetime(frame.CRS_DEP_TIME).dt.strftime('%H:%M:%S').eq('00:00:00')
    population = frame.loc[eligible].sort_values('flight_key').reset_index(drop=True)
    if len(population) < size:
        raise ValueError('Not enough eligible scheduled movements; no duplication or fabricated flights')
    rng = np.random.default_rng(seed)
    chosen = population.iloc[rng.permutation(len(population))[:size]].sort_values('flight_key').reset_index(drop=True)
    json_write(destination / 'selection.json', {'source_sha256': digest(source), 'candidate_rows': len(frame),
        'same_day_nonmidnight_rows': len(population), 'selected_movements': len(chosen), 'seed': seed,
        'selection_inputs': 'schedule_only_random_sample_without_replacement',
        'flight_keys': chosen.flight_key.tolist(), 'tail_available': bool(chosen.TAIL_NUM.notna().any())})
    return destination, chosen, report


class Experiments:
    def __init__(self, output, config):
        self.output, self.config = output, config
        self.folder = output / 'experiments'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.previous = json.loads((output / 'training_state.json').read_text())['active_seconds']
        checkpoint = self.folder / 'stage_state.json'
        self.stage_previous = json.loads(checkpoint.read_text()).get('active_seconds', 0) if checkpoint.exists() else 0
        self.previous += self.stage_previous
        self.code_hashes = {name:digest(ROOT / name) for name in ('src/optimization/waiting.py',
            'web_dashboard/waiting_execution.py','web_dashboard/solver_execution.py','web_dashboard/experiments.py',
            'src/pipeline/thesis_experiments.py')}

    def event(self, stage, **fields):
        elapsed = self.previous + time.monotonic() - self.started
        value = {'at': datetime.now(timezone.utc).isoformat(), 'stage': stage, 'elapsed_seconds': elapsed, **fields}
        print(json.dumps(value), flush=True)
        json_write(self.folder / 'progress.json', value)
        json_write(self.folder / 'stage_state.json', {'active_seconds': self.stage_previous+time.monotonic()-self.started})
        if elapsed >= self.config['budget']['experiment_hours'] * 3600:
            raise TimeoutError('The 20-hour experiment stage budget has expired; existing cases remain resumable')

    def case(self, name, payload):
        path = self.folder / 'cases' / f'{name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.event('case', case=name)
        if path.exists():
            result = json.loads(path.read_text())
            return verify_artifact(payload, result)
        started = time.perf_counter()
        try:
            result = solve_case_v2(payload)
            verify_artifact(payload, result)
        except Exception as exc:
            from web_dashboard.solver_execution import empty_result
            result = empty_result(payload, time.perf_counter()-started, 'ERROR', str(exc))
        json_write(path, result)
        return result

    def payload(self, snapshot, algorithm, budget, seed, *, flights=None, initial=None, mode='benchmark'):
        return {'flights': flights if flights is not None else snapshot['flights'], 'gates': snapshot['gates'],
                'solver_config': snapshot['solver_config'], 'waiting_config': snapshot['waiting_config'],
                'snapshot_hash': snapshot['hash'], 'algorithm': algorithm, 'budget': budget, 'seed': seed,
                'initial': initial, 'mode': mode, 'solver_protocol_version': 2, 'solver_profile': 'optimized',
                'implementation_hashes':self.code_hashes}

    def benchmark(self):
        cfg = self.config['benchmark']
        cases, snapshots, plans = [], {}, {}
        for day in cfg['dates']:
            for size, gate_count in zip(cfg['sizes'], cfg['contact_gates']):
                self.event('prepare_benchmark', day=day, movements=size)
                directory, frame, report = selected_schedule(self.folder, day, size, self.config['seed'])
                snapshot_path = directory / 'run/snapshot.json'
                if not snapshot_path.exists():
                    request = RunRequest(dataset_id='0'*32, service_date=day, preset='custom',
                        contact_gates=gate_count, remote_gates=5, solver='greedy', time_limit_sec=cfg['time_limit_sec'],
                        model_profile='thesis_xgboost', gate_time_mode='bounded_wait', **{
                            'max_gate_wait_min': self.config['waiting']['max_gate_wait_min']})
                    run_pipeline(frame, request, directory / 'run', report)
                snapshot = json.loads(snapshot_path.read_text())
                key = f'{day}_{size}'
                snapshots[key] = snapshot
                for seed in cfg['seeds']:
                    for algorithm in cfg['algorithms']:
                        name = f'b_{day}_{size}_{seed}_{algorithm}'
                        payload = self.payload(snapshot, algorithm, cfg['time_limit_sec'], seed)
                        result = self.case(name, payload)
                        cases.append({**{k:v for k,v in result.items() if k not in ('assignments','diagnostic','trace')},
                            'case_id': name, 'day': day, 'movement_count': len(frame), 'occupancy_count': len(snapshot['flights']),
                            'contact_gates': gate_count, 'finite_remote_stands': 5})
                        if seed == cfg['seeds'][0]:
                            plans[key, algorithm] = result
        if len(cases) != 108:
            raise ValueError('Incomplete 108-case benchmark')
        pd.DataFrame(cases).to_csv(self.folder / 'benchmark.csv', index=False)
        json_write(self.folder / 'benchmark_summary.json', {'status':'COMPLETE', 'cases':len(cases),
            'groups': summarize(cases), 'topology':'simulated finite capacities, five remote stands per case',
            'movement_and_occupancy_counts_distinct':True})
        return snapshots, plans

    def monte_carlo(self, snapshot, plans):
        cfg = self.config['monte_carlo']
        ids, samples = sample_residual_delays(snapshot, cfg['scenarios'], cfg['seed'])
        path = self.folder / 'monte_carlo_samples.npy'
        sha = hashlib.sha256(samples.tobytes()).hexdigest()
        if path.exists():
            np.testing.assert_array_equal(np.load(path), samples)
        else:
            np.save(path, samples)
        json_write(self.folder / 'sampling.json', {'hash':sha, 'flight_ids':ids, 'shape':list(samples.shape),
            'seed':cfg['seed'], 'snapshot_hash':snapshot['hash'], 'uncertainty':snapshot['uncertainty'],
            'dependence':'independent arrival/departure empirical development-OOF residuals',
            'common_samples_for_all_algorithms':True, 'recourse_information':'retrospective full scenario'})
        cases = []
        for index, sample in enumerate(samples):
            sample_hash = hashlib.sha256(sample.tobytes()).hexdigest()
            try:
                flights = [f.to_dict() for f in realized_flights(snapshot, ids, sample)]
            except Exception as exc:
                for algorithm, mode in [*( (a,'fixed') for a in plans), ('hybrid','recourse')]:
                    name = f'm_{index:04d}_{algorithm}_{mode}'
                    error = {'case_id':name,'scenario':index,'realization_hash':sample_hash,'algorithm':algorithm,'mode':mode,
                        'status':'GENERATION_ERROR','feasible':False,'decision_cost':None,'risk_cost':None,'runtime_sec':0,
                        'seed':cfg['seed']+index,'solver_protocol_version':2,'solver_profile':'optimized',
                        'solution_source':'NONE','budget_compliant':False,'error':str(exc)}
                    cases.append(error)
                    json_write(self.folder / 'cases' / f'{name}.json',error)
                continue
            for algorithm, plan in plans.items():
                name = f'm_{index:04d}_{algorithm}_fixed'
                if plan.get('feasible'):
                    payload = self.payload(snapshot, algorithm, 2, cfg['seed']+index, flights=flights,
                                           initial=plan['assignments'], mode='fixed')
                    result = self.case(name, payload)
                else:
                    result = {'status':'NO_SOURCE_PLAN','feasible':False,'decision_cost':None,'risk_cost':None,
                        'algorithm':algorithm,'mode':'fixed','seed':cfg['seed']+index,'runtime_sec':0,'budget_compliant':False,
                        'solver_protocol_version':2,'solver_profile':'optimized','solution_source':'NONE', 'termination_reason':'ERROR'}
                cases.append({**{k:v for k,v in result.items() if k not in ('assignments','diagnostic','trace')},
                              'case_id':name,'scenario':index,'realization_hash':sample_hash})
            algorithm = cfg['recourse_algorithm']
            plan = plans[algorithm]
            name = f'm_{index:04d}_hybrid_recourse'
            payload = self.payload(snapshot, algorithm, cfg['recourse_time_limit_sec'], cfg['seed']+index,
                                   flights=flights, initial=plan.get('assignments') or None, mode='recourse')
            result = self.case(name, payload)
            cases.append({**{k:v for k,v in result.items() if k not in ('assignments','diagnostic','trace')},
                          'case_id':name,'scenario':index,'realization_hash':sample_hash})
            pd.DataFrame(cases).to_csv(self.folder / 'monte_carlo.csv', index=False)
        if len(cases) != cfg['scenarios'] * 5:
            raise ValueError('Every requested scenario and failed plan must stay in denominator')
        json_write(self.folder / 'monte_carlo_summary.json', {'status':'COMPLETE','scenarios':cfg['scenarios'],
            'cases':len(cases),'sample_hash':sha,'groups':summarize(cases),'recourse_information':'retrospective full scenario',
            'fixed_decisions':'gate and bounded waiting held fixed','errors_in_denominator':True})

    def global_shap(self):
        from web_dashboard.thesis_profile import profile
        p = profile()
        evidence = {}
        for task, folder in (('arrival','inbound_atl'), ('departure','outbound_atl')):
            self.event('global_shap', task=task)
            files = sorted((ROOT / 'data/processed' / folder / 'year=2023').glob('*.parquet'))
            raw = ds.dataset(files, format='parquet').to_table(columns=[*REQUIRED, 'flight_key']).to_pandas()
            raw = raw.sample(n=1000, random_state=self.config['seed']).reset_index(drop=True)
            for kind in ('classification','regression'):
                rec = p['models'][f'{task}_{kind}_xgboost']
                values = explain(raw, task, kind, model_record=rec)
                importance = np.abs(values['values']).mean(axis=0)
                evidence[f'{task}_{kind}'] = {'sample_count':len(raw), 'model_sha256':rec['sha256'],
                    'output_space':values['output_space'], 'seed':self.config['seed'],
                    'flight_keys':raw.flight_key.tolist(),
                    'features':sorted([{'feature':name,'mean_abs_shap':float(value)} for name,value in zip(values['features'],importance)],
                                      key=lambda r:-r['mean_abs_shap'])}
        json_write(self.output / 'shap_global.json', evidence)

    def run(self):
        snapshots, plans = self.benchmark()
        key = f"{self.config['benchmark']['dates'][0]}_{self.config['benchmark']['sizes'][0]}"
        self.monte_carlo(snapshots[key], {a:plans[key,a] for a in self.config['benchmark']['algorithms']})
        self.global_shap()
        self.event('experiments_complete')
