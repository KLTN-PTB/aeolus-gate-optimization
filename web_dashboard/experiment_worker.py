"""Long-lived experiment supervisor, with a separate killable solver per case."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import psutil

from web_dashboard.experiments import (ALGORITHMS, export_experiment, load_plan, read_json,
    realized_flights, snapshot_for, solve_case)
from web_dashboard.pipeline import ROOT, json_write
from web_dashboard.storage import Store

CASE_HOST = None


def stop_owned(process):
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for p in reversed(children):
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    process.wait()
    psutil.wait_procs(children, timeout=3)


def case_process(input_path, output_path, ready_path):
    payload = read_json(input_path)
    ready_path.write_text(str(time.perf_counter()), encoding='ascii')
    json_write(output_path, solve_case(payload))


def supervised_case(store, eid, directory, cid, payload):
    global CASE_HOST
    input_path, output_path, ready = [directory / f'{prefix}{cid}{ext}' for prefix, ext in
                                    [('input_', '.json'), ('', '.json'), ('ready_', '.txt')]]
    # A crash after atomic output but before the SQLite commit can be recovered.
    if output_path.exists():
        cached = read_json(output_path)
        if cached.get('runtime_sec', 0) <= payload['budget'] + .1:
            return cached
        return {'status': 'TIMEOUT', 'feasible': False, 'decision_cost': None,
                'risk_cost': None, 'conflicts': None, 'runtime_sec': cached['runtime_sec'], 'error': 'Kết quả trước gián đoạn vượt ngân sách.'}
    ready.unlink(missing_ok=True)
    json_write(input_path, payload)
    started = time.perf_counter()
    with (directory / 'cases.log').open('a', encoding='utf-8') as log:
        if CASE_HOST is None or CASE_HOST.poll() is not None:
            CASE_HOST = subprocess.Popen([sys.executable, '-m', 'web_dashboard.experiment_worker', 'host'], cwd=ROOT,
                stdin=subprocess.PIPE, stdout=log, stderr=log, text=True, encoding='utf-8',
                env={**os.environ, 'PYTHONUTF8': '1'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        process = CASE_HOST
        process.stdin.write(json.dumps([str(input_path), str(output_path), str(ready)]) + '\n')
        process.stdin.flush()
        try:
            while process.poll() is None and not output_path.exists():
                current = store.experiment(eid)
                if current['cancel_requested']:
                    stop_owned(process)
                    return None
                if ready.exists():
                    try:
                        case_start = float(ready.read_text(encoding='ascii'))
                    except ValueError:
                        time.sleep(.03)
                        continue
                    if time.perf_counter()-case_start > payload['budget'] + .1:
                        stop_owned(process)
                        return {'status': 'TIMEOUT', 'feasible': False, 'decision_cost': None,
                            'risk_cost': None, 'conflicts': None, 'runtime_sec': payload['budget'],
                            'error': 'Vượt ngân sách toàn lượt giải; không có nghiệm được công bố.'}
                elif time.perf_counter()-started > 60:
                    stop_owned(process)
                    return {'status': 'ERROR', 'feasible': False, 'decision_cost': None,
                        'risk_cost': None, 'conflicts': None, 'runtime_sec': 0, 'error': 'Không khởi động được solver trong 60 giây.'}
                time.sleep(.04)
            if output_path.exists():
                output = read_json(output_path)
                if output['runtime_sec'] > payload['budget'] + .1:
                    return {'status': 'TIMEOUT', 'feasible': False, 'decision_cost': None,
                        'risk_cost': None, 'conflicts': None, 'runtime_sec': output['runtime_sec'], 'error': 'Solver trả kết quả vượt ngân sách.'}
                return output
            return {'status': 'ERROR', 'feasible': False, 'decision_cost': None,
                'risk_cost': None, 'conflicts': None, 'runtime_sec': 0,
                'error': f'Worker kết thúc mã {process.returncode}; xem cases.log.'}
        finally:
            input_path.unlink(missing_ok=True)
            ready.unlink(missing_ok=True)


def execute(root, eid):
    store = Store(root)
    exp = store.experiment(eid)
    directory = root / 'experiments' / eid
    directory.mkdir(parents=True, exist_ok=True)
    config = exp['config']
    try:
        snapshot = snapshot_for(store, exp['run_id'])
        if snapshot['hash'] != config['snapshot_hash']:
            raise ValueError('Snapshot không còn khớp cấu hình thí nghiệm.')
        store.experiment_update(eid, status='running', stage='preparation')
        done = {c['case_id'] for c in store.cases(eid)}

        def evaluate(cid, flights, algorithm, mode, seed, initial=None, **meta):
            if cid in done:
                return True
            if store.experiment(eid)['cancel_requested']:
                return False
            store.experiment_update(eid, stage=f'{mode} · {ALGORITHMS[algorithm]} · {meta.get("scenario", seed)}')
            payload = {'flights': flights, 'gates': snapshot['gates'], 'solver_config': snapshot['solver_config'],
                       'algorithm': algorithm, 'mode': mode, 'seed': seed, 'initial': initial,
                       'budget': config['time_limit_sec']}
            result = supervised_case(store, eid, directory, cid, payload)
            if result is None:
                return False
            # Large assignment/trace arrays live in atomic per-case artifacts.
            brief = {k: v for k, v in result.items() if k not in ('assignments', 'trace', 'diagnostic')}
            trace = result.get('trace', {})
            brief.update(initializer=trace.get('initial_solution_source', 'GREEDY' if algorithm == 'sa' else None),
                         cp_status=trace.get('cp_solver_status'), sa_iterations=trace.get('sa_iterations'),
                         stage1_ms=trace.get('stage1_wall_clock_ms'), stage2_ms=trace.get('stage2_wall_clock_ms'))
            diagnostic = result.get('diagnostic', {})
            brief['gate_conflicts'] = {}
            for conflict in diagnostic.get('conflict_pairs', []):
                gate = conflict.get('gate_id', 'unknown')
                brief['gate_conflicts'][gate] = brief['gate_conflicts'].get(gate, 0)+1
            store.put_case(eid, {**brief, 'case_id': cid, 'algorithm': algorithm, 'mode': mode,
                'seed': seed, 'snapshot_hash': snapshot['hash'], **meta})
            return True

        keep_running = True
        if config['kind'] == 'benchmark':
            for seed in range(config['seed'], config['seed'] + (5 if config['mode'] == 'research' else 1)):
                for alg in config['algorithms']:
                    keep_running = evaluate(f'b_{alg}_{seed}', snapshot['flights'], alg, 'benchmark', seed)
                    if not keep_running:
                        break
                if not keep_running:
                    break
        else:
            arrival_ids = sorted(snapshot['marginals'])
            matrix_path = directory / 'samples.npy'
            if matrix_path.exists():
                samples = np.load(matrix_path)
            else:
                rng = np.random.default_rng(config['seed'])
                samples = np.column_stack([snapshot['marginals'][fid]['mu'] + snapshot['marginals'][fid]['sigma'] *
                    rng.standard_t(snapshot['marginals'][fid]['df'], size=config['scenarios']) for fid in arrival_ids])
                if not np.isfinite(samples).all():
                    raise ValueError('Mẫu Student-t không hữu hạn; dừng thay vì cắt độ trễ.')
                temporary = directory / 'samples.tmp'
                with temporary.open('wb') as stream:
                    np.save(stream, samples)
                temporary.replace(matrix_path)
            digest = hashlib.sha256(samples.tobytes()).hexdigest()
            sampling = {'seed': config['seed'], 'arrival_ids': arrival_ids, 'shape': list(samples.shape),
                'hash': digest, 'dependence': 'INDEPENDENT_ARRIVALS', 'departure': 'FIXED_POINT_WITH_TURNAROUND',
                'unique_scenarios': int(np.unique(samples, axis=0).shape[0])}
            if (directory / 'sampling.json').exists() and read_json(directory / 'sampling.json')['hash'] != digest:
                raise ValueError('Ma trận mẫu đã thay đổi; không thể tiếp tục.')
            json_write(directory / 'sampling.json', sampling)
            initial_plans = [(p, load_plan(store, exp['run_id'], p['id'])) for p in config['plans']]
            for index, sample in enumerate(samples):
                if store.experiment(eid)['cancel_requested']:
                    keep_running = False
                    break
                try:
                    flights = [f.to_dict() for f in realized_flights(snapshot, arrival_ids, sample)]
                except Exception as exc:
                    # Every requested slot is accounted for, including a failed
                    # realization; never reduce the denominator by dropping it.
                    for pindex, (plan, _) in enumerate(initial_plans):
                        for mode in ('fixed', 'recourse'):
                            store.put_case(eid, {'case_id': f'm_{index:04d}_{pindex}_{mode}',
                                'algorithm': plan['algorithm'], 'mode': mode, 'scenario': index,
                                'source_plan_id': plan['id'], 'seed': config['seed']+index,
                                'status': 'GENERATION_ERROR', 'feasible': False, 'decision_cost': None,
                                'risk_cost': None, 'conflicts': None, 'runtime_sec': 0, 'error': str(exc),
                                'snapshot_hash': snapshot['hash'], 'realization_hash': hashlib.sha256(sample.tobytes()).hexdigest()})
                    continue
                for pindex, (plan, initial) in enumerate(initial_plans):
                    for mode in ('fixed', 'recourse'):
                        cid = f'm_{index:04d}_{pindex}_{mode}'
                        keep_running = evaluate(cid, flights, plan['algorithm'], mode, config['seed']+index,
                            initial=initial, scenario=index, source_plan_id=plan['id'], realization_hash=hashlib.sha256(sample.tobytes()).hexdigest())
                        if not keep_running:
                            break
                    if not keep_running:
                        break
                if not keep_running:
                    break
        completed = store.experiment(eid)['completed']
        final_status = 'completed' if completed == exp['total'] else 'cancelled'
        store.experiment_update(eid, status='running', stage='export')
        export_experiment(store, eid, final_status=final_status)
        store.experiment_update(eid, status=final_status, stage='done')
    except Exception as exc:
        logging.exception('Experiment failed')
        store.experiment_update(eid, status='failed', error=str(exc), stage='error')
    finally:
        if CASE_HOST is not None and CASE_HOST.poll() is None:
            stop_owned(CASE_HOST)


if __name__ == '__main__':
    if sys.argv[1] == 'host':
        for line in sys.stdin:
            paths = list(map(Path, json.loads(line)))
            try:
                case_process(*paths)
            except Exception as exc:
                logging.exception('Solver case failed')
                json_write(paths[1], {'status': 'ERROR', 'feasible': False, 'decision_cost': None,
                    'risk_cost': None, 'conflicts': None, 'runtime_sec': 0, 'error': str(exc)})
    elif sys.argv[1] == 'case':
        case_process(*map(Path, sys.argv[2:5]))
    else:
        execute(Path(sys.argv[1]), sys.argv[2])
