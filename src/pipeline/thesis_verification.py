"""Executable code acceptance, independent of thesis documents or old V3 gates."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import hashlib
import shutil

import pandas as pd

from src.models.binary_improvement_execution import digest
from src.pipeline.thesis_release import validate
from web_dashboard.normalization import REQUIRED
from web_dashboard.pipeline import ROOT, json_write


def source_signature():
    paths = set()
    for folder in ('src','dashboard','tests'):
        paths.update((ROOT / folder).rglob('*.py'))
    paths.update((ROOT / 'web_dashboard').glob('*.py'))
    paths.update((ROOT / 'web_dashboard/frontend/src').rglob('*'))
    paths.update((ROOT / 'web_dashboard/frontend').glob('*.*'))
    paths.update((ROOT / 'scripts').glob('*.*'))
    paths.update((ROOT / 'configs').glob('*.*'))
    paths.update(ROOT.glob('requirements*.txt'))
    paths.update(ROOT / name for name in ('.gitignore','.gitattributes','pytest.ini','conftest.py'))
    records = {p.relative_to(ROOT).as_posix():digest(p) for p in paths if p.is_file() and p.suffix not in ('.pyc','.tsbuildinfo')}
    return hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()


def verify_historical_evidence(output):
    """Verify archived evidence independently; never waive a failed current test.

    Published inputs can live in their exact byte-preserving archive after a source
    revision. Validation deliberately does not depend on Git HEAD, so it also works
    after committing the new code or cloning it elsewhere.
    """
    inventory = json.loads((ROOT / 'artifacts/reconciliation/phase1_2/source_inventory.json').read_text(encoding='utf-8'))
    report = output / 'historical_audit_blocks.json'
    if not report.exists():
        baseline = json.loads((ROOT / 'artifacts/thesis_completion/historical_evidence_baseline.json').read_text(encoding='utf-8'))
        if baseline.get('version') != 1 or baseline.get('scope') != 'published_phase1_2_input_source_revisions':
            raise ValueError('Unknown historical source baseline')
        revisions = []
        for row in baseline['published_source_revisions']:
            name = row['path']
            if name not in inventory['inputs'] or row['published_sha256'] != inventory['inputs'][name]['sha256']:
                raise ValueError(f'Historical baseline does not match the published inventory: {name}')
            source = (ROOT / row['historical_source_snapshot']).resolve()
            if (not source.is_relative_to((ROOT / 'artifacts/thesis_completion').resolve())
                    or digest(source) != row['published_sha256']):
                raise ValueError(f'Historical baseline source is unavailable or altered: {name}')
            destination = (output / 'historical_input_snapshot' / name).resolve()
            if not destination.is_relative_to((output / 'historical_input_snapshot').resolve()):
                raise ValueError(f'Historical baseline path escapes the run: {name}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            revisions.append({**row, 'historical_source_snapshot': destination.relative_to(ROOT).as_posix()})
        json_write(report, {'status':'ARCHIVED_PUBLISHED_SOURCES', 'published_source_revisions':revisions,
                            'historical_certifications_modified':False, '2024_opened':False})
    previous = json.loads(report.read_text(encoding='utf-8'))
    revisions = {row['path']:row for row in previous['published_source_revisions']}
    archived = []
    for name, record in inventory['inputs'].items():
        current = digest(ROOT / name)
        if current == record['sha256']:
            continue
        revision = revisions.get(name)
        if revision is None or revision['current_sha256'] != current:
            raise ValueError(f'Unreviewed historical input revision: {name}')
        snapshot = (ROOT / revision['historical_source_snapshot']).resolve()
        if (not snapshot.is_relative_to((output / 'historical_input_snapshot').resolve())
                or revision['published_sha256'] != record['sha256']
                or digest(snapshot) != record['sha256']):
            raise ValueError(f'Published historical source archive is invalid: {name}')
        archived.append(name)
    from src.evaluation.final_evaluation_guard_v2 import FinalEvaluationGuardV2, FinalEvaluationGuardV2Error
    guard = FinalEvaluationGuardV2(project_root=ROOT, freeze_version='v3')
    manifest = json.loads(guard.manifest_path.read_text(encoding='utf-8'))
    domain_hash = next(expected for category in manifest['freeze_categories'].values()
                       for name, expected in category['files'].items()
                       if name.replace('\\','/') == 'src/optimization/domain.py')
    try:
        guard.assert_evaluation_authorized(evaluation_role='POST_HOLDOUT', year=2024,
                                          purpose='post_holdout_evaluation')
    except FinalEvaluationGuardV2Error as exc:
        message = str(exc)
        if not all(value in message for value in ('Integrity hash mismatch', 'domain.py', domain_hash,
                                                  digest(ROOT / 'src/optimization/domain.py'))):
            raise
    else:
        raise ValueError('Revised code must not inherit historical 2024 authorization')
    result = {'status':'PASS', 'published_inputs':len(inventory['inputs']),
              'exact_archived_sources':archived, 'legacy_v3_evaluation':'BLOCKED_SOURCE_REVISION',
              'guard_error':message, 'historical_certifications_modified':False, '2024_opened':False}
    json_write(output / 'historical_evidence_validation.json',result)
    return result


def verify_checks(output, remaining=lambda:10800):
    """Reuse a passing check only for exactly the same source/test/config bytes."""
    logs = output / 'verification_logs'
    logs.mkdir(exist_ok=True)
    cache_path = output / 'checks_cache.json'
    signature = source_signature()
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if cache.get('source_signature') != signature:
        cache = {'source_signature':signature,'checks':{}}
    commands = [
        ('python_tests',[sys.executable,'-m','pytest','tests','-q','-p','no:cacheprovider','--basetemp',
                         str(Path(os.environ['TEMP']) / 'aeolus_thesis_acceptance')],ROOT),
        ('frontend_tests',['npm.cmd','test','--','--reporter=dot'],ROOT / 'web_dashboard/frontend'),
        ('frontend_build',['npm.cmd','run','build'],ROOT / 'web_dashboard/frontend'),
        ('launcher_check',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT / 'scripts/start_web_dashboard.ps1'),'-Check'],ROOT)]
    for name, command, cwd in commands:
        path = logs / f'{name}.log'
        if cache['checks'].get(name,{}).get('status') == 'PASS' and path.exists() and digest(path) == cache['checks'][name]['log_sha256']:
            continue
        print(json.dumps({'stage':'verification','check':name}),flush=True)
        with path.open('w',encoding='utf-8') as stream:
            process = subprocess.run(command,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=min(10800,remaining()),
                                     env={**os.environ,'PYTHONUTF8':'1'})
        status = 'PASS' if process.returncode == 0 else 'FAIL'
        cache['checks'][name] = {'status':status, 'log_sha256':digest(path),'returncode':process.returncode}
        if source_signature() != signature:
            raise RuntimeError('Sources changed while checks were running; results cannot be cached')
        json_write(cache_path,cache)
        if status == 'FAIL':
            raise RuntimeError(f'{name} failed; inspect {path}')
    return {name:cache['checks'][name]['status'] for name,_,_ in commands}


def verify(output, *, run_checks=True):
    started = time.monotonic()
    baseline = json.loads((output / 'training_state.json').read_text())['active_seconds']
    baseline += json.loads((output / 'experiments/stage_state.json').read_text()).get('active_seconds',0)
    state = output / 'verification_state.json'
    previous = json.loads(state.read_text()).get('active_seconds',0) if state.exists() else 0
    baseline += previous
    def remaining():
        duration = time.monotonic()-started
        json_write(state,{'active_seconds':previous+duration})
        seconds = 24*3600-baseline-duration
        if seconds <= 0:
            raise TimeoutError('Total 24-hour execution budget exhausted')
        return seconds
    validation = validate(output)
    historical = verify_historical_evidence(output)
    folder = output / 'experiments'
    benchmark = json.loads((folder / 'benchmark_summary.json').read_text())
    monte = json.loads((folder / 'monte_carlo_summary.json').read_text())
    if benchmark['status'] != 'COMPLETE' or benchmark['cases'] != 108 or monte['scenarios'] != 500 or monte['cases'] != 2500:
        raise ValueError('Proposal experiment counts are incomplete')
    for name, expected in (('benchmark.csv',108),('monte_carlo.csv',2500)):
        table = pd.read_csv(folder / name)
        if len(table) != expected or table.case_id.duplicated().any():
            raise ValueError('Missing or duplicated experiment slots')
        if table.status.isin(['ERROR','GENERATION_ERROR','NO_SOURCE_PLAN']).any():
            raise ValueError('Code/initial-plan errors remain in the experiment ledger')
    shap = json.loads((output / 'shap_global.json').read_text())
    if len(shap) != 4 or any(r['sample_count'] != 1000 for r in shap.values()):
        raise ValueError('Global XGBoost explanations are incomplete')
    sample = output / 'sample_schedule.parquet'
    source = folder / '2023-01-15_100/run/normalized.parquet'
    frame = pd.read_parquet(source)
    frame[[*REQUIRED,'TAIL_NUM']].to_parquet(sample,index=False)
    checks = {'model_validation':validation['status'],'historical_evidence':historical['status'],
              'legacy_v3_evaluation':historical['legacy_v3_evaluation'],'benchmark_cases':108,'monte_carlo_scenarios':500,
              'monte_carlo_cases':2500,'global_shap_models':4,'global_shap_rows_each':1000,
              'runnable_sample':sample.relative_to(ROOT).as_posix(),'sample_sha256':digest(sample)}
    code = ('from pathlib import Path; import sys; from web_dashboard.normalization import normalize_files; '
            'from web_dashboard.contracts import RunRequest; from web_dashboard.pipeline import run_pipeline; '
            'f,r=normalize_files([Path(sys.argv[1])]); '
            'q=RunRequest(dataset_id="0"*32,service_date="2023-01-15",preset="custom",contact_gates=20,remote_gates=5,'
            'solver="greedy",model_profile="thesis_xgboost",gate_time_mode="bounded_wait"); '
            'v=run_pipeline(f,q,Path(sys.argv[2]),r); assert v["summary"]["feasible"]; '
            'assert len(v["predictions"])==100; assert v["summary"]["independent_verifier_valid"]; print("FRESH_CPU_SAMPLE_PASS")')
    child = subprocess.run([sys.executable,'-c',code,str(sample),str(output / 'portable_sample_run')],cwd=ROOT,
                           capture_output=True,text=True,timeout=min(180,remaining()))
    if child.returncode:
        raise RuntimeError(child.stderr)
    checks['fresh_cpu_schedule_run']='PASS'
    if run_checks:
        checks.update(verify_checks(output,remaining))
    else:
        raise ValueError('A complete acceptance run requires regression checks')
    json_write(output / 'verification.json',checks)
    remaining()
    completion = {'status':'COMPLETE',
        'scope':'code_only_adjusted_proposal','checks':checks,
        'historical_2023_only':True,'untouched_test_claimed':False,'v3_metric_pass_claimed':False,
        'weather_and_flight_chain':'excluded_by_user','browser_opened':False}
    json_write(output / 'completion.json',completion)
    return completion
