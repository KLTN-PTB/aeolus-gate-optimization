"""Common numerical/provenance checks for persisted experiment results."""
import math

ARTIFACT_SCHEMA_VERSION = 2


def finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite value in result artifact")
    if isinstance(value, dict):
        for item in value.values():
            finite_tree(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            finite_tree(item)


def equal_number(actual, expected, label):
    if isinstance(actual, bool) or not isinstance(actual, (float, int)) or not math.isfinite(actual):
        raise ValueError(f"Missing or invalid {label}")
    tolerance = 8 * max(math.ulp(float(actual)), math.ulp(float(expected)))
    if abs(actual - expected) > tolerance:
        raise ValueError(f"Result {label} differs from independent evaluation")


def verify_common(payload, result):
    finite_tree(result)
    result = dict(result)
    if type(result.get('feasible')) is not bool or type(result.get('budget_compliant')) is not bool:
        raise ValueError('Invalid feasibility/budget flags')
    for row in result.get('assignments', []):
        for name in ('occupancy_start_min', 'occupancy_end_min'):
            value = row.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                raise ValueError('Assignment timestamps must be integer minutes')
    if payload['mode'] == 'fixed':
        initial = payload.get('initial') or []
        ids = [a['flight_id'] for a in initial]
        if len(set(ids)) != len(ids) or set(ids) != {f['flight_id'] for f in payload['flights']}:
            raise ValueError('Fixed plan must cover every flight exactly once')
    runtime = result.get('runtime_sec')
    if isinstance(runtime, bool) or not isinstance(runtime, (float, int)) or runtime < 0:
        raise ValueError('Invalid runtime')
    if result.get('budget_compliant') and runtime > payload['budget'] + 1e-9:
        raise ValueError('Result exceeds its claimed budget')
    for key in ('algorithm', 'mode', 'seed'):
        if result.get(key) != payload[key]:
            raise ValueError(f'Result {key} does not match payload')
    if result.get('optimality_proven'):
        if result.get('artifact_schema_version', 0) < ARTIFACT_SCHEMA_VERSION:
            result.update(optimality_proven=False, gap=None, best_bound=None, proof_validation='legacy_unverified')
            if result.get('status') == 'OPTIMAL':
                result['status'] = 'FEASIBLE'
            return result
        if (not result.get('feasible') or not result.get('budget_compliant')
                or result.get('solution_source') != 'SOLVER' or payload['mode'] == 'fixed'
                or payload['algorithm'] not in ('cpsat', 'hybrid') or result.get('status') != 'OPTIMAL'
                or result.get('termination_reason') != 'OPTIMAL_PROVEN'):
            raise ValueError('Inconsistent optimality claim')
        if payload['flights'] and not payload.get('waiting_config'):
            trace = result.get('trace', {})
            if trace.get('objective_encoding', trace.get('cp_objective_encoding')) != 'exact_decimal_v1':
                raise ValueError('Optimality lacks exact objective provenance')
        equal_number(result.get('gap'), 0., 'optimality gap')
        reporting = result.get('breakdown', {}).get('reporting_cost', 0.)
        equal_number(result.get('best_bound'), result['decision_cost'] + reporting, 'optimality cost bound')
    return result


def finalized_timing(result, runtime, budget):
    result = {**result, 'runtime_sec': runtime, 'budget_compliant': runtime <= budget}
    if runtime > budget:
        result.update(optimality_proven=False, gap=None, best_bound=None, termination_reason='TIME_LIMIT')
        if result.get('status') == 'OPTIMAL':
            result['status'] = 'FEASIBLE' if result.get('feasible') else 'TIMEOUT'
    return result


def legacy_proof_view(result):
    """Keep historical artifacts immutable and distinguish unsupported proof claims."""
    result = dict(result)
    if result.get('artifact_schema_version', 0) < ARTIFACT_SCHEMA_VERSION and result.get('optimality_proven'):
        result.update(optimality_proven=False, gap=None, best_bound=None, proof_validation='legacy_unverified')
        if result.get('status') == 'OPTIMAL':
            result['status'] = 'FEASIBLE'
    return result


def read_pipeline_result(store, run_id):
    import json
    from src.optimization.config import GateOptimizationConfig
    from src.optimization.domain import Flight, Gate, GateAssignment
    from src.optimization.evaluation import evaluate_gate_assignment
    from web_dashboard.experiments import snapshot_for
    from web_dashboard.exports import verify_exports
    directory = store.root / 'runs' / run_id
    result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
    finite_tree(result)
    snapshot = snapshot_for(store, run_id)
    if result['manifest'].get('snapshot_hash') != snapshot['hash']:
        raise ValueError('Result and snapshot differ')
    if result['manifest'].get('export_schema_version') == 2:
        verify_exports(directory)
    flights = [Flight.from_dict(row) for row in snapshot['flights']]
    gates = [Gate.from_dict(row) for row in snapshot['gates']]
    rows = result['assignments']
    assignments = {row['flight_id']: GateAssignment.from_dict(row) for row in rows}
    if len(rows) != len(assignments):
        raise ValueError('Duplicate pipeline assignment')
    summary = result['summary']
    if snapshot.get('waiting_config'):
        from src.optimization.waiting import WaitingConfig, check
        diagnostic, waits, costs, _ = check(assignments, flights, gates, WaitingConfig(**snapshot['waiting_config']))
        cost = costs['decision_cost']
        for row in rows:
            equal_number(row.get('gate_wait_min'), waits[row['flight_id']], 'pipeline waiting')
    else:
        checked = evaluate_gate_assignment(assignments, flights, gates, GateOptimizationConfig(**snapshot['solver_config']))
        diagnostic, cost = checked.constraint_diagnostics, checked.objective_breakdown.decision_cost
    if bool(summary['feasible']) != diagnostic.is_valid or bool(summary['independent_verifier_valid']) != diagnostic.is_valid:
        raise ValueError('Pipeline feasibility differs from independent verification')
    if summary.get('conflicts') != diagnostic.conflict_count:
        raise ValueError('Pipeline conflicts disagree')
    if summary['feasible']:
        equal_number(summary.get('decision_cost'), cost, 'pipeline decision cost')
        equal_number(summary.get('assigned_count'), len(rows), 'pipeline assignment count')
    elif rows or summary.get('decision_cost') is not None:
        raise ValueError('Infeasible pipeline has assignments/decision cost')
    if summary != result['manifest']['summary']:
        raise ValueError('Pipeline summary and manifest disagree')
    if result['manifest'].get('export_schema_version') != 2:
        summary['optimality_proven'] = False
        result['manifest']['summary']['optimality_proven'] = False
        result['manifest']['warnings'].append('Artifact lịch sử: chưa xác minh chứng nhận tối ưu theo schema hiện tại.')
    return result
