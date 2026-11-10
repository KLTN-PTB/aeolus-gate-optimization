"""Offline acceptance run through the real supervisor; never starts HTTP or a browser."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web_dashboard import experiment_worker as worker
from web_dashboard.pipeline import json_write
from web_dashboard.solver_execution import PROTOCOL_VERSION
from web_dashboard.storage import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget',type=float,default=120)
    parser.add_argument('--profile',choices=['optimized','baseline'],default='optimized')
    parser.add_argument('--algorithms',nargs='+',choices=['greedy','cpsat','sa','hybrid'],default=['greedy','cpsat','sa','hybrid'])
    args=parser.parse_args()
    if not 1<=args.budget<=120:parser.error('budget must be between 1 and 120')
    if args.output.exists():parser.error('output must be a new directory; prior evidence is never overwritten')
    raw=args.snapshot.read_bytes();snapshot=json.loads(raw)
    content={k:v for k,v in snapshot.items() if k!='hash'}
    assert hashlib.sha256(json.dumps(content,sort_keys=True,allow_nan=False).encode()).hexdigest()==snapshot['hash']
    store=Store(args.output)
    cfg={'kind':'benchmark','mode':'quick','seed':202601,'algorithms':args.algorithms,
         'snapshot_hash':snapshot['hash'],'solver_profile':args.profile,'solver_protocol_version':PROTOCOL_VERSION,
         'time_limit_sec':args.budget}
    eid=store.create_experiment('offline_validation',cfg,len(args.algorithms))
    directory=store.root/'experiments'/eid;directory.mkdir(parents=True)
    results=[]
    try:
        for algorithm in args.algorithms:
            cid=f'b_{algorithm}_202601'
            payload={'flights':snapshot['flights'],'gates':snapshot['gates'],'solver_config':snapshot['solver_config'],
                     'algorithm':algorithm,'mode':'benchmark','seed':202601,'budget':args.budget,
                     'solver_protocol_version':PROTOCOL_VERSION,'solver_profile':args.profile,
                     'snapshot_hash':snapshot['hash'],'case_id':cid}
            print('RUN',algorithm,args.profile,args.budget,flush=True)
            case=worker.supervised_case(store,eid,directory,cid,payload)
            brief={k:v for k,v in case.items() if k not in ('assignments','diagnostic','trace')}
            store.put_case(eid,{**brief,'case_id':cid})
            results.append(brief)
            print(json.dumps(brief,ensure_ascii=True),flush=True)
        store.experiment_update(eid,status='completed',stage='done')
        json_write(store.root/'acceptance.json',{'created_at':datetime.now(timezone.utc).isoformat(),
            'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'snapshot_hash':snapshot['hash'],
            'configuration':cfg,'cases':results})
    finally:
        if worker.CASE_HOST is not None and worker.CASE_HOST.poll() is None:worker.stop_owned(worker.CASE_HOST)
        assert args.snapshot.read_bytes()==raw,'Input snapshot changed'


if __name__=='__main__':main()
