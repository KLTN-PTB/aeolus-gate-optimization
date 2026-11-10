from collections import OrderedDict
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from src.pipeline import thesis_training as training
from src.pipeline.verified_cache import VerifiedCache, CacheValidationError


@pytest.fixture
def runner(tmp_path, monkeypatch):
    year = tmp_path / "data/processed/inbound_atl/year=2016"
    year.mkdir(parents=True)
    data = pd.DataFrame({"FL_DATE": ["2016-07-01 00:00:00"]*3, "OP_CARRIER": ["DL"]*3,
        "OP_CARRIER_FL_NUM": [1, 2, 3], "ORIGIN": ["MCO"]*3, "DEST": ["ATL"]*3,
        "CRS_DEP_TIME": ["2016-07-01 08:00:00"]*3, "CRS_ARR_TIME": ["2016-07-01 09:30:00"]*3,
        "CRS_ELAPSED_TIME": [90.]*3, "MONTH": [7]*3, "DAY_OF_MONTH": [1]*3, "DAY_OF_WEEK": [5]*3,
        "flight_key": ["c", "a", "b"], "ARR_DELAY": [-5., 14., 15.]})
    data.to_parquet(year / "part.parquet", index=False)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    monkeypatch.setattr(training, "assert_data_access_allowed", lambda *a, **kw: None)
    value = object.__new__(training.Training)
    value.output = tmp_path / "run"
    value.frames, value.matrices = OrderedDict(), OrderedDict()
    value.state = {"data": {}}
    value.config = {"budget": {"train_cap": 100}}
    value.smoke, value.seed, value.evaluation_open = False, 202601, False
    value.cache = VerifiedCache(tmp_path, value.output, {"test_version": 1})
    return value


def clear_memory(runner):
    runner.frames.clear()
    runner.matrices.clear()


def test_create_reload_and_preflight(runner):
    first = runner.read_year("arrival", 2016)
    matrix = runner.matrix("arrival", 2016)
    clear_memory(runner)
    pd.testing.assert_frame_equal(first, runner.read_year("arrival", 2016))
    np.testing.assert_array_equal(matrix["x"], runner.matrix("arrival", 2016)["x"])
    runner.cache.preflight()
    assert list(first["__reg"]) == [14., 15., -5.]


@pytest.mark.parametrize("failure", ["missing_manifest", "modified_payload", "changed_source", "changed_contract", "partial_write"])
def test_fail_closed_without_changing_published_cache(runner, failure):
    runner.read_year("arrival", 2016)
    path = runner.output / "data_cache/arrival_2016.parquet"
    if failure == "missing_manifest":
        runner.cache.sidecar(path).unlink()
    elif failure == "modified_payload":
        pd.DataFrame({"wrong": [1]}).to_parquet(path)
    elif failure == "changed_source":
        source = runner.cache.root / "data/processed/inbound_atl/year=2016/part.parquet"
        data = pd.read_parquet(source)
        data.loc[0, "ARR_DELAY"] = 500
        data.to_parquet(source, index=False)
    elif failure == "changed_contract":
        runner.cache.contract = {"test_version": 2}
    else:
        (path.parent / "interrupted.tmp").write_text("partial")
    before = path.read_bytes()
    with pytest.raises(CacheValidationError, match="Create a new run"):
        runner.cache.preflight()
    assert path.read_bytes() == before


def test_valid_checksums_do_not_bypass_semantic_data_validation(runner):
    data = runner.read_year("arrival", 2016).copy()
    path = runner.output / "data_cache/arrival_2016.parquet"
    context = runner.cache.metadata(path)["context"]
    data.loc[0, "__reg"] = np.inf
    runner.cache.save(path, data, context)
    clear_memory(runner)
    with pytest.raises(CacheValidationError, match="targets/year"):
        runner.read_year("arrival", 2016)


def test_matrix_manifest_links_data_and_checks_shape(runner):
    runner.matrix("arrival", 2016)
    path = runner.output / "matrix_cache/arrival_2016_False.joblib"
    context = runner.cache.metadata(path)["context"]
    assert context["sources_by_year"][0]["data_sha256"]
    runner.cache.save(path, {"sentinel": "stale_matrix"}, context)
    clear_memory(runner)
    with pytest.raises(CacheValidationError, match="matrix/encoder"):
        runner.matrix("arrival", 2016)


def test_atomic_failure_leaves_unusable_pair(runner, monkeypatch):
    runner.read_year("arrival", 2016)
    path = runner.output / "data_cache/arrival_2016.parquet"
    context = runner.cache.metadata(path)["context"]
    data = runner.read_year("arrival", 2016).copy()
    data.loc[0, "__key"] = "new"
    import src.pipeline.verified_cache as cache_module
    original = cache_module.os.replace
    def interrupt(source, target):
        if str(target).endswith("manifest.json"):
            raise OSError("interrupted manifest publication")
        original(source, target)
    monkeypatch.setattr(cache_module.os, "replace", interrupt)
    with pytest.raises(OSError):
        runner.cache.save(path, data, context)
    with pytest.raises(CacheValidationError, match="checksum"):
        runner.cache.preflight()


def test_matrix_dependency_cannot_silently_change(runner):
    runner.matrix("arrival", 2016)
    path = runner.output / "data_cache/arrival_2016.parquet"
    data = runner.read_year("arrival", 2016).copy()
    context = runner.cache.metadata(path)["context"]
    data.loc[0, "__key"] = "replacement"
    runner.cache.save(path, data, context)
    with pytest.raises(CacheValidationError, match="matrix input cache changed"):
        runner.cache.preflight()


def test_resume_old_run_rejected_before_modifying_its_state(tmp_path):
    config = yaml.safe_load((training.ROOT / "configs/thesis_completion.yaml").read_text())
    output = tmp_path / "historical"
    (output / "data_cache").mkdir(parents=True)
    pd.DataFrame({"old": [1]}).to_parquet(output / "data_cache/arrival_2016.parquet")
    state = output / "training_state.json"
    state.write_text('{"active_seconds": 1, "models": {}, "data": {}}')
    before = state.read_bytes()
    with pytest.raises(CacheValidationError, match="Create a new run"):
        training.Training(output, config, resume=True)
    assert state.read_bytes() == before and not (output / "resolved_config.json").exists()


def test_new_run_contract_can_resume_and_changed_config_is_rejected(tmp_path):
    config = yaml.safe_load((training.ROOT / "configs/thesis_completion.yaml").read_text())
    output = tmp_path / "fresh"
    training.Training(output, config)
    resumed = training.Training(output, config, resume=True)
    assert resumed.cache.contract["version"] == 2
    changed = json.loads(json.dumps(config))
    changed["seed"] += 1
    with pytest.raises(CacheValidationError, match="contract changed"):
        training.Training(output, changed, resume=True)


def development_partitions(runner):
    source = runner.cache.root / 'data/processed/inbound_atl/year=2016/part.parquet'
    raw = pd.read_parquet(source)
    for year in range(2017, 2023):
        table = raw.copy()
        table['FL_DATE'] = f'{year}-07-01 00:00:00'
        table['CRS_DEP_TIME'] = f'{year}-07-01 08:00:00'
        table['CRS_ARR_TIME'] = f'{year}-07-01 09:30:00'
        table['DAY_OF_WEEK'] = pd.Timestamp(year, 7, 1).isoweekday()
        table['flight_key'] = [f'{year}_{key}' for key in table.flight_key]
        path = source.parent.parent / f'year={year}' / 'part.parquet'
        path.parent.mkdir()
        table.to_parquet(path, index=False)
    runner.event = lambda *args, **kwargs: None
    runner.check = lambda *args: None
    runner.config['validation_years'] = [2019, 2020, 2021, 2022]
    runner.config['budget']['trials_per_target'] = 1
    calls = []
    def fit(task, kind, family, end_year, params=None):
        from types import SimpleNamespace
        calls.append((task, kind, family, end_year))
        return SimpleNamespace(raw_predict=lambda frame: np.full(len(frame), .25), metadata={'train_end': f'{end_year}-12-31'})
    runner.fit = fit
    return calls


def test_oof_cache_is_verified_and_matches_population(runner):
    development_partitions(runner)
    first = runner.fixed_oof('arrival', 'classification')
    second = runner.fixed_oof('arrival', 'classification')
    pd.testing.assert_frame_equal(first, second)
    path = runner.output / 'oof/arrival_classification_2019.parquet'
    context = runner.cache.metadata(path)['context']
    table = pd.read_parquet(path)
    table.loc[0, 'year'] = 2099
    runner.cache.save(path, table, context)
    with pytest.raises(CacheValidationError, match='OOF population'):
        runner.fixed_oof('arrival', 'classification')


def test_hpo_json_sqlite_and_resume_lineage(runner):
    calls = development_partitions(runner)
    params = runner.tune('arrival', 'classification')
    count = len(calls)
    assert runner.tune('arrival', 'classification') == params and len(calls) == count
    path = runner.output / 'hpo/arrival_classification.json'
    context = runner.cache.metadata(path)['context']
    result = json.loads(path.read_text())
    result['params']['max_depth'] = -999
    runner.cache.save(path, result, context)
    with pytest.raises(CacheValidationError, match='search space|best trial'):
        runner.tune('arrival', 'classification')


def test_hpo_interrupted_trial_resumes_only_after_seal(runner):
    development_partitions(runner)
    fit = runner.fit
    def interrupt(*args, **kwargs):
        raise training.FitIncomplete('fixture interruption')
    runner.fit = interrupt
    with pytest.raises(training.FitIncomplete):
        runner.tune('arrival', 'regression')
    runner.fit = fit
    assert runner.tune('arrival', 'regression')['max_depth'] in range(3, 7)


def test_legacy_oof_and_hpo_refused(runner):
    development_partitions(runner)
    path = runner.output / 'oof/arrival_classification_2017.parquet'
    path.parent.mkdir(parents=True)
    pd.DataFrame({'year': [2099]}).to_parquet(path)
    with pytest.raises(CacheValidationError, match='manifest'):
        runner.fixed_oof('arrival', 'classification')
    path = runner.output / 'hpo/arrival_classification.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'params': {'max_depth': -999}}))
    with pytest.raises(CacheValidationError, match='manifest'):
        runner.tune('arrival', 'classification')
