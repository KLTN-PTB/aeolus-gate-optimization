"""Real HTTP acceptance: upload -> ML -> four solvers -> shared-sample Monte Carlo."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import sys

import httpx


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8000')
    p.add_argument('--file', type=Path)
    p.add_argument('--date', default='2026-07-01')
    p.add_argument('--scenarios', type=int, default=20)
    p.add_argument('--budget', type=float, default=5)
    p.add_argument('--gates', type=int, default=150)
    p.add_argument('--remote', type=int, default=30)
    p.add_argument('--research', action='store_true')
    p.add_argument('--benchmark-research', action='store_true')
    args = p.parse_args()
    with httpx.Client(base_url=args.url, timeout=60) as client:
        def call(method, url, **kwargs):
            response = client.request(method, '/api'+url, **kwargs)
            response.raise_for_status()
            return response.json()
        def wait(url, experiment=False):
            previous = None
            while True:
                data = call('GET', url)
                state = (data['status'], data.get('completed'))
                if state != previous:
                    print(url, state, data.get('stage'), flush=True)
                    previous = state
                if data['status'] not in ('queued', 'running'):
                    if data['status'] != 'completed':
                        raise RuntimeError(data)
                    return data
                time.sleep(.8)
        raw = args.file.read_bytes() if args.file else client.get('/api/example.parquet').content
        dataset = call('POST', '/datasets', files={'files': (args.file.name if args.file else 'ILLUSTRATIVE_ONLY.parquet', raw)})
        assert dataset['can_run'], dataset['errors']
        run = call('POST', '/runs', json={'dataset_id': dataset['id'], 'service_date': args.date,
            'solver': 'greedy', 'preset': 'custom', 'contact_gates': args.gates, 'remote_gates': args.remote})
        rid = run['id']
        wait('/runs/'+rid)
        result = call('GET', f'/runs/{rid}/results')
        assert result['summary']['feasible'] and result['summary']['independent_verifier_valid']
        bench = call('POST', f'/runs/{rid}/experiments', json={'kind': 'benchmark',
            'mode': 'research' if args.benchmark_research else 'quick', 'time_limit_sec': args.budget})
        wait('/experiments/'+bench['id'], True)
        b = call('GET', f"/experiments/{bench['id']}/results")
        assert len(b['cases']) == (20 if args.benchmark_research else 4)
        assert len({c['snapshot_hash'] for c in b['cases']}) == 1
        available = call('GET', f'/runs/{rid}/plans')['plans']
        plans = [next((p for p in available if p['algorithm'] == alg and p['id'].startswith(bench['id'])), None)
                 for alg in ('greedy', 'cpsat', 'sa', 'hybrid')]
        plans = [p['id'] for p in plans if p]
        assert plans
        mc = call('POST', f'/runs/{rid}/experiments', json={'kind': 'montecarlo',
            'mode': 'research' if args.research else 'quick', 'scenarios': args.scenarios,
            'time_limit_sec': args.budget, 'plan_ids': plans})
        wait('/experiments/'+mc['id'], True)
        m = call('GET', f"/experiments/{mc['id']}/results")
        assert len(m['cases']) == args.scenarios*len(plans)*2
        for scenario in range(args.scenarios):
            assert len({c['realization_hash'] for c in m['cases'] if c['scenario'] == scenario}) == 1
        replay = call('GET', f"/experiments/{mc['id']}/plans/{m['cases'][0]['case_id']}")
        assert len(replay['turns']) == result['summary']['occupancy_count']
        bundle = client.get(f"/api/experiments/{mc['id']}/exports/bundle")
        bundle.raise_for_status()
        assert bundle.content[:2] == b'PK'
        print(json.dumps({'run_id': rid, 'benchmark_id': bench['id'], 'montecarlo_id': mc['id'],
            'movement_count': result['summary']['movement_count'], 'plans': len(plans),
            'cases': len(m['cases']), 'matrix': {k: v for k,v in m['sampling'].items() if k != 'arrival_ids'},
            'zip_bytes': len(bundle.content)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
