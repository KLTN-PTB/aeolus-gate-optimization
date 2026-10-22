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
    started = time.perf_counter()
    payload = read_json(input_path)
    ready_path.write_text(str(started), encoding='ascii')
    modern = payload.get('solver_protocol_version') == 2
    checkpoint = output_path.with_suffix('.incumbent.json')
    try:
        result = solve_case(payload, started=started,
                            publish=(lambda result: json_write(checkpoint, result)) if modern else None)
    except Exception as exc:
        if not modern:
            raise
        logging.exception('Versioned solver case failed')
        from web_dashboard.solver_execution import empty_result, recover_artifact
        result = empty_result(payload, time.perf_counter()-started, 'ERROR', str(exc))
        if checkpoint.exists():
            try:
                result = recover_artifact(payload, read_json(checkpoint), time.perf_counter()-started, 'ERROR', str(exc))
            except (ValueError, KeyError, TypeError):
                logging.exception('Rejected checkpoint after worker exception')
    if modern:
        result['_case_started_perf'] = started
    json_write(output_path, result)
    if modern:
        output_path.with_suffix('.done').write_text(str(time.perf_counter()), encoding='ascii')


def supervised_case(store, eid, directory, cid, payload):
    global CASE_HOST
    if payload.get('solver_protocol_version') == 2:
        return supervised_case_v2(store, eid, directory, cid, payload)
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


def supervised_case_v2(store, eid, directory, cid, payload):
    from web_dashboard.solver_execution import empty_result, verify_artifact, recover_artifact
    global CASE_HOST
    input_path = directory / f'input_{cid}.json'
    output = directory / f'{cid}.json'
    checkpoint = output.with_suffix('.incumbent.json')
    ready = directory / f'ready_{cid}.txt'
    done = output.with_suffix('.done')

    def recover(runtime, reason, error=None):
        if checkpoint.exists():
            try:
                return recover_artifact(payload, read_json(checkpoint), runtime, reason, error)
            except (ValueError, KeyError, TypeError, OSError):
                logging.exception('Rejected invalid incumbent checkpoint')
        return empty_result(payload, runtime, reason, error)

    def persist_recovery(result, case_start):
        if case_start is not None:
            result['_case_started_perf'] = case_start
        json_write(output, result)
        if case_start is not None:
            finished = time.perf_counter()
            done.write_text(str(finished), encoding='ascii')
            result.update(runtime_sec=finished-case_start,
                          budget_compliant=result.get('budget_compliant', False) and finished-case_start <= payload['budget'])
            json_write(output, result)
        return result

    def completed():
        result = verify_artifact(payload, read_json(output))
        if not done.exists():
            recovered = recover_artifact(payload, result, result.get('runtime_sec', 0), 'ERROR',
                                         'Worker interrupted before completing output persistence; full runtime is unknown')
            recovered.update(budget_compliant=False, timing_complete=False)
            json_write(output, recovered)
            return recovered
        runtime = float(done.read_text(encoding='ascii')) - result['_case_started_perf']
        result.update(runtime_sec=runtime, budget_compliant=runtime <= payload['budget'])
        if runtime > payload['budget']:
            result.update(termination_reason='TIME_LIMIT')
        json_write(output, result)
        return result

    if output.exists():
        return completed()
    ready.unlink(missing_ok=True)
    done.unlink(missing_ok=True)
    checkpoint.unlink(missing_ok=True)
    # Uncommitted attempts are recomputed; never inject an unpaid old initializer.
    json_write(input_path, payload)
    launched = time.perf_counter()
    with (directory / 'cases.log').open('a', encoding='utf-8') as log:
        if CASE_HOST is None or CASE_HOST.poll() is not None:
            CASE_HOST = subprocess.Popen([sys.executable, '-m', 'web_dashboard.experiment_worker', 'host'], cwd=ROOT,
                stdin=subprocess.PIPE, stdout=log, stderr=log, text=True, encoding='utf-8',
                env={**os.environ, 'PYTHONUTF8': '1'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        process = CASE_HOST
        process.stdin.write(json.dumps([str(input_path), str(output), str(ready)]) + '\n')
        process.stdin.flush()
        case_start = None
        try:
            while True:
                if done.exists() and output.exists():
                    return completed()
                if store.experiment(eid)['cancel_requested']:
                    stop_owned(process)
                    # Cancelled cases are not committed; resume recomputes the whole case.
                    for partial in (output, done, checkpoint):
                        partial.unlink(missing_ok=True)
                    return None
                if ready.exists():
                    try:
                        case_start = float(ready.read_text(encoding='ascii'))
                    except ValueError:
                        time.sleep(.01)
                        continue
                    elapsed = time.perf_counter()-case_start
                    if elapsed >= payload['budget']:
                        stop_owned(process)
                        result = recover(time.perf_counter()-case_start, 'TIME_LIMIT')
                        result.update(budget_compliant=False)
                        return persist_recovery(result, case_start)
                elif time.perf_counter()-launched > 60:
                    stop_owned(process)
                    return empty_result(payload, 0, 'ERROR', 'Solver host did not start in 60 seconds')
                if process.poll() is not None:
                    result = recover(time.perf_counter()-case_start if case_start is not None else 0,
                                     'ERROR', f'Worker exited with code {process.returncode}')
                    return persist_recovery(result, case_start)
                time.sleep(.02)
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
                       'budget': config['time_limit_sec'],
                       'solver_protocol_version': config.get('solver_protocol_version', 1),
                       'solver_profile': config.get('solver_profile', 'baseline'),
                       'snapshot_hash': snapshot['hash'], 'case_id': cid}
            if snapshot.get('waiting_config'):
                payload['waiting_config'] = snapshot['waiting_config']
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
            empirical = snapshot.get('uncertainty', {}).get('kind') == 'EMPIRICAL_TEMPORAL_OOF_RESIDUALS'
            if empirical:
                arrival_ids = sorted(snapshot['predictions'])
            matrix_path = directory / 'samples.npy'
            if matrix_path.exists():
                samples = np.load(matrix_path)
            else:
                if empirical:
                    from web_dashboard.thesis_profile import sample_residual_delays
                    arrival_ids, samples = sample_residual_delays(snapshot, config['scenarios'], config['seed'])
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
            if empirical:
                sampling.update(dependence='INDEPENDENT_DUAL_OOF_RESIDUALS', departure='SAMPLED_WITH_TURNAROUND',
                                uncertainty=snapshot['uncertainty'])
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
                                'solver_protocol_version': config.get('solver_protocol_version', 1),
                                'solver_profile': config.get('solver_profile', 'baseline'), 'budget_compliant': False,
                                'termination_reason': 'GENERATION_ERROR', 'solution_source': 'NONE',
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
