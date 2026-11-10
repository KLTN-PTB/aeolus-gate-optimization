"""Independent checks, portable exports and explicit proposal-profile activation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd

from src.models.binary_improvement import binary_metrics
from src.models.binary_improvement_execution import digest
from src.pipeline.thesis_training import ROOT, regression_metrics
from web_dashboard.pipeline import json_write
from src.pipeline.verified_cache import VerifiedCache


def validate_lineage(output):
    """Qualify new publications; existing active legacy checkpoints stay readable."""
    path = output / 'cache_contract.json'
    if not path.is_file():
        raise ValueError('Legacy run lacks OOF/HPO lineage; create a new run for activation')
    contract = json.loads(path.read_text())
    if contract.get('version') != 2 or contract.get('smoke'):
        raise ValueError('Activation requires a full version-2 lineage contract')
    cache = VerifiedCache(ROOT, output, contract)
    cache.preflight()
    from src.pipeline.thesis_training import Training
    checker = object.__new__(Training)
    checker.config, checker.smoke, checker.output, checker.cache = contract['config'], False, output, cache
    for task in ('arrival', 'departure'):
        for kind in ('classification', 'regression'):
            hpo_path = output / 'hpo' / f'{task}_{kind}.json'
            context = checker._artifact_context(task, kind, 2022, 'hpo')
            study = cache.load(hpo_path, context)
            checker._validate_hpo(study, kind)
            if study.get('study_sha256') != cache.metadata(hpo_path.with_suffix('.sqlite3'), context)['sha256']:
                raise ValueError('HPO database differs from frozen selection')
            for year in range(2017, 2023):
                oof_context = checker._artifact_context(task, kind, year, 'oof')
                table = cache.load(output / 'oof' / f'{task}_{kind}_{year}.parquet', oof_context)
                data_path = output / 'data_cache' / f'{task}_{year}.parquet'
                frame = cache.load(data_path, cache.context(task, year,
                    sources_by_year=[{'year': year, 'files': cache.sources(task, year)}]))
                checker._validate_oof(table, frame, kind, year)
            reference = pd.concat([cache.load(output / 'oof' / f'{task}_{kind}_{year}.parquet',
                checker._artifact_context(task, kind, year, 'oof')) for year in checker.config['validation_years']], ignore_index=True)
            for family in ('linear', 'random_forest', 'xgboost', 'stacking'):
                full = cache.load(output / 'oof' / f'{task}_{kind}_{family}_full.parquet',
                                  checker._artifact_context(task, kind, 2022, 'full_oof'))
                pd.testing.assert_frame_equal(full[['flight_key','date','year','carrier','y']],
                                              reference[['flight_key','date','year','carrier','y']])
                prediction = full.raw_probability_or_delay.to_numpy(dtype=float)
                if not np.isfinite(prediction).all() or kind == 'classification' and not ((prediction >= 0) & (prediction <= 1)).all():
                    raise ValueError('Full OOF predictions are malformed')
    return {'version': 2, 'oof_hpo_verified': True}


def verify_freeze_records(freeze, records):
    if set(freeze['models']) != set(records):
        raise ValueError('Frozen model identities differ from evaluated records')
    for name, frozen in freeze['models'].items():
        if any(records[name].get(key) != value for key, value in frozen.items()):
            raise ValueError(f'Frozen/evaluated model provenance differs: {name}')


def inspect_source_lineage(output, *, require_current=False):
    hashes = json.loads((output / 'source_hashes.json').read_text())
    matches = True
    for name, sha in hashes.items():
        name = name.replace('\\', '/')
        snapshot = (output / 'source_snapshot' / name).resolve()
        if not snapshot.is_relative_to((output / 'source_snapshot').resolve()) or digest(snapshot) != sha:
            raise ValueError('Training snapshot integrity check failed')
        current = ROOT / name
        matches &= current.is_file() and current.read_bytes().replace(b'\r\n', b'\n') == snapshot.read_bytes().replace(b'\r\n', b'\n')
    if not hashes or require_current and not matches:
        raise ValueError('Training source lineage differs from current publication code')
    return {'snapshot_integrity': True, 'matches_current_code': matches}


def validate(output):
    summary = json.loads((output / 'summary.json').read_text())
    if summary['status'] != 'MODELS_COMPLETE' or summary['smoke']:
        raise ValueError('Only a completed full model run can be activated')
    lineage = validate_lineage(output)
    records = json.loads((output / 'model_results.json').read_text())
    expected = {f'{t}_{k}_{f}' for t in ('arrival', 'departure') for k in ('classification', 'regression')
                for f in ('linear', 'random_forest', 'xgboost', 'stacking')}
    if set(records) != expected:
        raise ValueError('The proposal requires all sixteen models')
    sources = inspect_source_lineage(output, require_current=True)
    freeze = json.loads((output / 'selection_freeze.json').read_text())
    verify_freeze_records(freeze, records)
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
    first_eval = min(e['at'] for e in events if e['stage'] == 'historical_evaluated')
    if freeze['at'] >= first_eval or freeze['status'] != 'FROZEN_BEFORE_2023':
        raise ValueError('Evaluation must follow selection freeze')
    comparisons, populations = {}, {}
    for name, rec in records.items():
        if digest(output / rec['path'].replace('\\','/')) != rec['sha256'] or rec['fresh_cpu_reload'] != 'PASS':
            raise ValueError('Model checksum or fresh-process CPU validation failed')
        bundle = joblib.load(output / rec['path'].replace('\\','/'))
        if (bundle.task,bundle.kind,bundle.family) != (rec['task'],rec['kind'],rec['family']) or bundle.metadata.get('smoke'):
            raise ValueError('Bundle identity disagrees with the frozen model contract')
        if bundle.metadata['train_end'] != '2022-12-31' or bundle.metadata.get('inference_device') != 'cpu':
            raise ValueError('Bundle train cutoff or CPU portability is invalid')
        if rec['kind'] == 'classification' and (bundle.threshold != rec['threshold'] or bundle.calibrator is None):
            raise ValueError('Classifier calibration or threshold is missing')
        table = pd.read_parquet(output / 'predictions' / f'{name}_2023.parquet')
        if table.__key.duplicated().any() or not np.isfinite(table[['y', 'prediction']]).all().all():
            raise ValueError('Evaluation has invalid or duplicate rows')
        key = rec['task'], rec['kind']
        signature = digest(output / 'predictions' / f'{name}_2023.parquet')
        population = table[['__key', '__date', 'y']]
        if key in populations:
            pd.testing.assert_frame_equal(populations[key], population)
        else:
            populations[key] = population
        measured = binary_metrics(table.y, table.prediction, rec['threshold']) if rec['kind'] == 'classification' else regression_metrics(table.y, table.prediction)
        for field in ('ap', 'f1', 'precision', 'recall', 'roc_auc', 'brier_score', 'log_loss', 'ece_10') if rec['kind'] == 'classification' else ('mae', 'rmse'):
            np.testing.assert_allclose(measured[field], rec['historical_2023'][field], atol=1e-12)
        if rec['kind'] == 'classification':
            measured['accuracy'] = (measured['tn']+measured['tp'])/measured['n']
        else:
            from sklearn.metrics import r2_score
            measured['r2'] = float(r2_score(table.y, table.prediction))
        comparisons[name] = {'metrics': measured, 'prediction_sha256': signature, 'threshold': rec['threshold'],
                             'task': rec['task'], 'kind': rec['kind'], 'family': rec['family']}
        if rec['family'] == 'stacking':
            for year in (2019, 2020, 2021, 2022):
                audit = json.loads((output / 'meta_audit' / f"{rec['task']}_{rec['kind']}_{year}.json").read_text())
                if audit['last_year'] >= year or audit['validation_year'] != year:
                    raise ValueError('Temporal stacking leakage')
    trials = {}
    for task in ('arrival', 'departure'):
        for kind in ('classification', 'regression'):
            study = json.loads((output / 'hpo' / f'{task}_{kind}.json').read_text())
            if len(study['trials']) != 16 or any(len(t['folds']) != 4 for t in study['trials']):
                raise ValueError('Expected 16 completed four-fold trials per target')
            trials[f'{task}_{kind}'] = len(study['trials'])
    for task, rec in freeze['residuals'].items():
        if digest(output / rec['path'].replace('\\','/')) != rec['sha256']:
            raise ValueError('OOF residual bank hash mismatch')
    result = {'status': 'PASS', 'models': 16, 'completed_trials': trials, 'comparison': comparisons,
              'lineage': lineage, 'sources': sources,
              'acceptance': 'proposal_functionality_and_measured_historical_metrics',
              'untouched_test_claimed': False, 'weather_required': False, 'flight_chain_required': False}
    json_write(output / 'validation.json', result)
    return result


def activate(output):
    validation = validate(output)
    freeze = json.loads((output / 'selection_freeze.json').read_text())
    def portable(rec):
        path = output / rec['path'].replace('\\','/')
        return {**rec, 'path': path.relative_to(ROOT).as_posix()}
    value = {'profile': 'thesis_xgboost', 'status': 'READY', 'version': output.name,
             'lineage_version': validation['lineage']['version'],
             'model_run': output.relative_to(ROOT).as_posix(), 'smoke': False,
             'created_at': datetime.now(timezone.utc).isoformat(),
             'models': {name: portable(rec) for name, rec in freeze['models'].items()
                        if name in {f'{task}_{kind}_xgboost' for task in ('arrival', 'departure')
                                    for kind in ('classification', 'regression')}},
             'residuals': {task: portable(rec) for task, rec in freeze['residuals'].items()},
             'comparison': validation['comparison'], 'evaluation_scope': 'historical_2023_already_seen'}
    json_write(ROOT / 'artifacts/thesis_completion/active_profile.json', value)
    return value


def repack_legacy(output):
    """Map only the known script-local class, without altering global unpickling."""
    from joblib.numpy_pickle import NumpyUnpickler, _validate_fileobject_and_memmap
    from src.models.thesis_models import CalibratedPredictor
    class KnownLegacyUnpickler(NumpyUnpickler):
        def find_class(self, module, name):
            if module == '__main__' and name == 'CalibratedPredictor':
                return CalibratedPredictor
            return super().find_class(module, name)
    folder = ROOT / 'artifacts/remediation/outbound_classification/models'
    destination = output / 'legacy_portable'
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for family in ('logistic', 'xgboost'):
        source = folder / f'outbound_{family}_calibrated_v1.joblib'
        before = digest(source)
        with source.open('rb') as stream:
            with _validate_fileobject_and_memmap(stream, str(source), None) as (handle, _):
                model = KnownLegacyUnpickler(str(source), handle, True).load()
        target = destination / source.name
        joblib.dump(model, target, compress=3)
        sample = np.linspace(.01, .99, 50)
        old = model.calibrator.predict(sample) if model.method == 'isotonic' else model.calibrator.predict_proba(sample.reshape(-1, 1))[:, 1]
        loaded = joblib.load(target)
        new = loaded.calibrator.predict(sample) if loaded.method == 'isotonic' else loaded.calibrator.predict_proba(sample.reshape(-1, 1))[:, 1]
        np.testing.assert_array_equal(old, new)
        probe = np.zeros((5, model.base_estimator.n_features_in_))
        np.testing.assert_array_equal(model.predict_proba(probe), loaded.predict_proba(probe))
        np.save(destination / f'{family}_probe.npy', probe)
        np.save(destination / f'{family}_expected.npy', model.predict_proba(probe))
        child = subprocess.run([sys.executable, '-c',
            'import joblib,sys,numpy as np; m=joblib.load(sys.argv[1]); assert type(m).__module__=="src.models.thesis_models"; np.testing.assert_array_equal(m.predict_proba(np.load(sys.argv[2])),np.load(sys.argv[3]))',
            str(target),str(destination / f'{family}_probe.npy'),str(destination / f'{family}_expected.npy')],
            cwd=ROOT, capture_output=True, text=True, timeout=90)
        if child.returncode or digest(source) != before:
            raise ValueError(child.stderr or 'Original legacy checkpoint changed')
        records.append({'source': str(source.relative_to(ROOT)), 'source_sha256': before,
                        'path': str(target.relative_to(ROOT)), 'sha256': digest(target), 'fresh_reload': 'PASS'})
    json_write(destination / 'manifest.json', records)
    return records
