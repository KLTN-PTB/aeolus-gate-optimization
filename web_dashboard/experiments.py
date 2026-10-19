"""Frozen-input experiments. No research artifact is used as an uploaded run's result."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time
import zipfile

import numpy as np
import pandas as pd

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, GateAssignment
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from web_dashboard.pipeline import finite_metadata, json_write

ALGORITHMS = {'greedy': 'Deterministic Greedy', 'cpsat': 'CP-SAT', 'sa': 'SA độc lập', 'hybrid': 'Hybrid (CP-SAT/Greedy → SA)'}
ANALYSIS_VERSION = 2


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def snapshot_for(store, run_id):
    run = store.run(run_id)
    if not run or run['status'] != 'completed':
        raise ValueError('Cần một lần chạy pipeline đã hoàn tất.')
    path = store.root / 'runs' / run_id / 'snapshot.json'
    if not path.is_file():
        raise ValueError('Lần chạy cũ thiếu snapshot thí nghiệm. Hãy chạy end-to-end lại với cùng dữ liệu.')
    data = read_json(path)
    digest = data.pop('hash')
    actual = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    data['hash'] = digest
    if actual != digest:
        raise ValueError('Snapshot bị thay đổi; không thể so sánh thí nghiệm.')
    return data


def peak_demand(flights):
    active = peak = 0
    for _, change in sorted([(f.occupancy_start_min, 1) for f in flights] + [(f.occupancy_end_min, -1) for f in flights]):
        active += change
        peak = max(peak, active)
    return peak


def adjusted_assignments(initial, flights):
    """Freeze gate choices, NOT the obsolete occupancy timestamps."""
    by_id = {f.flight_id: f for f in flights}
    return {a['flight_id']: replace(GateAssignment.from_dict(a),
            occupancy_start_min=by_id[a['flight_id']].occupancy_start_min,
            occupancy_end_min=by_id[a['flight_id']].occupancy_end_min, is_reassignment=False)
            for a in initial if a['flight_id'] in by_id}


def solve_case(payload):
    started = time.perf_counter()
    flights = [Flight.from_dict(f) for f in payload['flights']]
    gates = [Gate.from_dict(g) for g in payload['gates']]
    cfg = GateOptimizationConfig(**{**payload['solver_config'], 'time_limit_seconds': payload['budget'],
        'total_wall_clock_budget_seconds': payload['budget'], 'num_search_workers': 1,
        'random_seed': payload['seed'], 'cp_sat_fallback_to_greedy': False,
        'cp_sat_use_warm_start': False, 'allow_unbounded_overflow': False, 'enforce_remote_capacity': True})
    initial = payload.get('initial')
    if initial:
        nominal = {a['flight_id']: a['gate_id'] for a in initial}
        flights = [replace(f, nominal_gate_id=nominal[f.flight_id]) for f in flights]
    allow_remote = any(g.is_overflow for g in gates)
    if payload['mode'] == 'fixed':
        solved = evaluate_gate_assignment(adjusted_assignments(initial, flights), flights, gates, cfg, solver_status='FIXED_PLAN')
    else:
        alg = payload['algorithm']
        if alg == 'sa':
            solver = SimulatedAnnealingGateSolver(cfg, SAConfig(seed=payload['seed'], iterations=1000))
        elif alg == 'hybrid':
            solver = HybridGateSolver(cfg, SAConfig(seed=payload['seed'], iterations=1000))
        else:
            solver = {'greedy': DeterministicGreedyGateSolver, 'cpsat': CPSatGateSolver}[alg](cfg)
        solved = solver.solve(flights, gates, allow_overflow=allow_remote)
    # Re-evaluate using the SAME nominal reference and objective for all solvers.
    checked = evaluate_gate_assignment(solved.assignments, flights, gates, cfg)
    valid = bool(checked.feasible and checked.constraint_diagnostics.is_valid)
    diag = checked.constraint_diagnostics
    duration = time.perf_counter() - started
    assignments = [a.to_dict() for a in solved.assignments.values()]
    if payload['mode'] != 'fixed' and not valid:
        assignments = []
    return finite_metadata({'status': str(solved.status), 'feasible': valid,
        'algorithm': payload['algorithm'], 'mode': payload['mode'], 'seed': payload['seed'],
        'runtime_sec': duration, 'assigned_count': len(assignments),
        'decision_cost': checked.objective_breakdown.decision_cost if valid else None,
        'risk_cost': checked.objective_value if payload['mode'] == 'fixed' else None,
        'breakdown': checked.objective_breakdown.to_dict() if valid or payload['mode'] == 'fixed' else None,
        'remote_count': sum(a['is_overflow'] for a in assignments),
        'reassignments': sum(f.nominal_gate_id is not None and f.flight_id in solved.assignments
            and solved.assignments[f.flight_id].gate_id != f.nominal_gate_id for f in flights),
        'conflicts': diag.conflict_count, 'diagnostic': diag.to_dict(),
        'peak': peak_demand(flights), 'optimality_proven': bool(solved.optimality_proven and valid),
        'best_bound': solved.best_bound, 'gap': solved.optimality_gap,
        'trace': {**solved.solver_configuration, 'sa_iterations_limit': 1000 if payload['algorithm'] in ('sa', 'hybrid') else None}, 'assignments': assignments})


def realized_flights(snapshot, arrivals, sample):
    delay = dict(zip(arrivals, sample))
    pair_map = {p['pair_id']: p for p in snapshot['pairing']}
    result = []
    for row in snapshot['flights']:
        f = Flight.from_dict(row)
        pair = pair_map[f.flight_id]
        aid, did = pair['arrival_leg_id'], pair['departure_leg_id']
        if aid:
            start = int(round(f.scheduled_arrival_min + delay[aid]))
            if did:
                end = max(int(round(f.scheduled_departure_min + snapshot['predictions'][did])), start + f.min_turnaround_min)
            else:
                end = max(f.scheduled_arrival_min + f.default_dwell_min, start + f.min_turnaround_min)
            f = replace(f, predicted_arrival_min=start, precomputed_gate_out_min=end)
        result.append(f)
    return result


def available_plans(store, run_id):
    result = read_json(store.root / 'runs' / run_id / 'result.json')
    plans = []
    if result['summary']['feasible'] and result['summary']['independent_verifier_valid']:
        algorithm = 'greedy' if result['summary'].get('fallback_used') else result['manifest']['config']['solver']
        plans.append({'id': 'pipeline', 'algorithm': algorithm, 'seed': 202601,
                      'label': f"Pipeline · {result['summary'].get('actual_solver', ALGORITHMS[algorithm])}",
                      'snapshot_hash': result['manifest'].get('snapshot_hash')})
    for exp in store.experiments(run_id):
        if exp['config']['kind'] != 'benchmark':
            continue
        for case in store.cases(exp['id']):
            if case.get('feasible'):
                plans.append({'id': f"{exp['id']}.{case['case_id']}", 'algorithm': case['algorithm'],
                    'seed': case['seed'], 'label': f"{ALGORITHMS[case['algorithm']]} · seed {case['seed']} · #{exp['id'][:6]}",
                    'snapshot_hash': case['snapshot_hash']})
    return plans


def load_plan(store, run_id, plan_id):
    if plan_id == 'pipeline':
        data = read_json(store.root / 'runs' / run_id / 'result.json')
        if not data['summary']['feasible']:
            raise ValueError('Lịch pipeline chưa có nghiệm khả thi.')
        return data['assignments']
    if not re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9_]+', plan_id):
        raise ValueError('Mã lịch không hợp lệ.')
    eid, cid = plan_id.split('.')
    exp = store.experiment(eid)
    case = next((c for c in store.cases(eid) if c['case_id'] == cid), None)
    if not exp or exp['run_id'] != run_id or not case or not case['feasible']:
        raise ValueError('Lịch không thuộc lần chạy hoặc chưa khả thi.')
    return read_json(store.root / 'experiments' / eid / f'{cid}.json')['assignments']


def bootstrap_mean(values, seed):
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    x = np.asarray(values, dtype=float)
    means = np.mean(rng.choice(x, size=(2000, len(x))), axis=1)
    return [float(v) for v in np.quantile(means, [.025, .975])]


def wilson(success, n):
    if not n:
        return None
    p, z = success / n, 1.96
    mid = (p + z*z / (2*n)) / (1 + z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1+z*z/n)
    return [max(0, mid-half), min(1, mid+half)]


def summarize(cases, seed=202601, intervals=True):
    groups = {}
    for c in cases:
        key = f"{c['algorithm']}:{c['mode']}:{c.get('source_plan_id', '')}"
        groups.setdefault(key, []).append(c)
    output = []
    for key, rows in groups.items():
        feasible = [c for c in rows if c.get('feasible')]
        costs = [c['decision_cost'] for c in feasible if c.get('decision_cost') is not None]
        risks = [c['risk_cost'] for c in rows if c.get('risk_cost') is not None]
        values = risks if rows[0]['mode'] == 'fixed' else costs
        sorted_values = sorted(values)
        operational_rows = [c for c in rows if c.get('remote_count') is not None] if rows[0]['mode'] == 'fixed' else feasible
        metric = {'key': key, 'algorithm': rows[0]['algorithm'], 'mode': rows[0]['mode'],
            'source_plan_id': rows[0].get('source_plan_id'), 'count': len(rows), 'feasible_count': len(feasible),
            'timeouts': sum(c['status'] == 'TIMEOUT' for c in rows),
            'failures': sum(c['status'] in ('ERROR', 'GENERATION_ERROR') for c in rows),
            'feasible_rate': len(feasible)/len(rows), 'rate_ci95': wilson(len(feasible), len(rows)),
            'cost_sample_count': len(values), 'mean': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None,
            'std': statistics.stdev(values) if len(values) > 1 else None,
            'min': min(values) if values else None, 'max': max(values) if values else None,
            'p95': float(np.quantile(values, .95)) if values else None,
            'cvar95': statistics.mean(sorted_values[-max(1, math.ceil(.05*len(values))):]) if values else None,
            'mean_ci95': bootstrap_mean(values, seed) if intervals else None,
            'runtime_median': statistics.median(c.get('runtime_sec', 0) for c in rows),
            'mean_conflicts': statistics.mean(c['conflicts'] for c in rows if c.get('conflicts') is not None) if any(c.get('conflicts') is not None for c in rows) else None,
            'mean_remote': statistics.mean(c['remote_count'] for c in operational_rows) if operational_rows else None,
            'mean_reassignments': statistics.mean(c['reassignments'] for c in operational_rows) if operational_rows else None,
            'convergence': [{'n': i+1, 'feasible_rate': sum(bool(r.get('feasible')) for r in rows[:i+1])/(i+1)} for i in range(len(rows))]}
        output.append(metric)
    return output


def experiment_results(store, eid, *, finalize=False):
    exp = store.experiment(eid)
    cases = store.cases(eid)
    directory = store.root / 'experiments' / eid
    matrix_meta = read_json(directory / 'sampling.json') if (directory / 'sampling.json').exists() else None
    terminal = finalize or exp['status'] not in ('queued', 'running')
    paired = []
    # Compare recourse algorithms only on aligned, jointly feasible realizations.
    plans = sorted({c.get('source_plan_id') for c in cases if c.get('source_plan_id')})
    if terminal:
        for i, a in enumerate(plans):
            for b in plans[i+1:]:
                left = {c['scenario']: c for c in cases if c.get('source_plan_id') == a and c['mode'] == 'recourse' and c['feasible']}
                right = {c['scenario']: c for c in cases if c.get('source_plan_id') == b and c['mode'] == 'recourse' and c['feasible']}
                indices = sorted(set(left) & set(right))
                values = [left[s]['decision_cost'] - right[s]['decision_cost'] for s in indices]
                paired.append({'a': a, 'b': b, 'pairs': len(values), 'mean_delta': statistics.mean(values) if values else None,
                    'ci95': bootstrap_mean(values, exp['config']['seed'])})
    return {'analysis_version': ANALYSIS_VERSION, 'experiment': exp, 'cases': cases, 'groups': summarize(cases, exp['config']['seed'], terminal),
            'sampling': matrix_meta, 'paired': paired,
            'assumptions': ['Chi phí là điểm theo trọng số, không phải đơn vị tiền tệ.',
                'Trễ đến độc lập; chuyến đi giữ dự báo điểm, có ràng buộc turnaround.',
                'Phân cổng lại hồi cứu biết toàn bộ kịch bản, chưa phải điều hành trực tuyến.',
                'Chi phí fixed là chỉ số rủi ro có phạt xung đột; recourse là chi phí sửa lịch khả thi.',
                'Chi phí recourse chỉ trên nghiệm hợp lệ; tỷ lệ khả thi gồm cả timeout/lỗi trong mẫu số.',
                'Khoảng tin cậy chi phí: bootstrap 2000; tỷ lệ: Wilson. N nhỏ có thể cho đuôi không ổn định.']}


def render_plan(store, eid, cid):
    exp = store.experiment(eid)
    case = next((c for c in store.cases(eid) if c['case_id'] == cid), None)
    if not case:
        raise ValueError('Không có lượt thí nghiệm này.')
    snapshot = snapshot_for(store, exp['run_id'])
    result = read_json(store.root / 'runs' / exp['run_id'] / 'result.json')
    if case['mode'] == 'benchmark':
        flights = [Flight.from_dict(f) for f in snapshot['flights']]
    else:
        directory = store.root / 'experiments' / eid
        sampling = read_json(directory / 'sampling.json')
        matrix = np.load(directory / 'samples.npy', mmap_mode='r')
        flights = realized_flights(snapshot, sampling['arrival_ids'], matrix[case['scenario']])
    output = read_json(store.root / 'experiments' / eid / f'{cid}.json') if case['status'] not in ('TIMEOUT', 'ERROR', 'GENERATION_ERROR') else {'assignments': []}
    if case['mode'] == 'fixed':
        output['assignments'] = [a.to_dict() for a in adjusted_assignments(load_plan(store, exp['run_id'], case['source_plan_id']), flights).values()]
    f_map = {f.flight_id: f for f in flights}
    initial_map = {a['flight_id']: a['gate_id'] for a in load_plan(store, exp['run_id'], case['source_plan_id'])} if case['mode'] != 'benchmark' else None
    for turn in result['turns']:
        f = f_map[turn['turn_id']]
        turn.update(simulated_arrival_min=f.occupancy_start_min, simulated_departure_min=f.occupancy_end_min-f.buffer_min,
                    gate_release_min=f.occupancy_end_min)
        if initial_map is not None:
            turn['nominal_gate_id'] = initial_map.get(turn['turn_id'])
    result['assignments'] = output['assignments']
    result['summary'].update(assigned_count=len(result['assignments']), feasible=case['feasible'],
        independent_verifier_valid=case['feasible'], conflicts=case.get('conflicts'),
        solver_status=case['status'], actual_solver=ALGORITHMS[case['algorithm']],
        solver_runtime_sec=case.get('runtime_sec', 0), remote_count=case.get('remote_count', 0),
        reassignments=case.get('reassignments', 0), peak_occupancy=peak_demand(flights),
        decision_cost=case.get('decision_cost'), optimality_proven=case.get('optimality_proven', False))
    if initial_map is not None:
        result['summary']['baseline_covered'] = len(initial_map)
        result['manifest']['warnings'].append('Mốc tái phân bổ là lịch ban đầu của thí nghiệm Monte Carlo.')
    result['manifest']['plan_label'] = f"{ALGORITHMS[case['algorithm']]} · {case['mode']} · {cid}"
    result['manifest']['warnings'].append('Lịch thí nghiệm: ' + result['manifest']['plan_label'])
    return result


def export_experiment(store, eid, *, final_status=None):
    data = experiment_results(store, eid, finalize=True)
    if final_status:
        data['experiment'] = {**data['experiment'], 'status': final_status, 'stage': 'done'}
    directory = store.root / 'experiments' / eid
    json_write(directory / 'results.json', data)
    pd.json_normalize(data['cases']).to_csv(directory / 'cases.csv', index=False)
    pd.json_normalize(data['cases']).to_parquet(directory / 'cases.parquet', index=False)
    json_write(directory / 'manifest.json', {'analysis_version': ANALYSIS_VERSION, 'experiment': data['experiment'], 'sampling': data['sampling'],
        'assumptions': data['assumptions'], 'snapshot': snapshot_for(store, data['experiment']['run_id'])})
    temporary_bundle = directory / 'bundle.zip.tmp'
    with zipfile.ZipFile(temporary_bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in directory.iterdir():
            if path.suffix in ('.json', '.csv', '.parquet', '.npy') and not path.name.startswith('input_') and path.name != '.export_state.json':
                archive.write(path, path.name)
    temporary_bundle.replace(directory / 'bundle.zip')
    json_write(directory / '.export_state.json', {'analysis_version': ANALYSIS_VERSION,
        'completed': data['experiment']['completed'], 'status': data['experiment']['status']})
    return directory
