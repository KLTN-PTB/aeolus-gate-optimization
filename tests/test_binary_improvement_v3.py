"""V3 temporal isolation, native categorical semantics and portable decisions."""
from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.dummy import DummyClassifier

from src.features.binary_improvement_v3 import NativeScheduleEncoder
from src.models.binary_improvement_v3 import (CarrierCalibrator, V3Bundle, absolute_gate,
    fixed_precision_threshold, bootstrap_with_f1)
from src.models.binary_v3_protocol import BoundedData, roles_for, warmup_indices
from src.models.binary_v3_execution import V3Experiment
from src.models.binary_improvement_execution import FitIncomplete


def frame():
    dates = pd.date_range("2018-01-01", periods=240)
    return pd.DataFrame({"__date": dates, "__key": [str(i) for i in range(len(dates))],
        "__target": np.arange(len(dates)) % 3 == 0, "calendar_year": dates.year,
        "calendar_month": dates.month, "calendar_day_of_month": dates.day,
        "calendar_day_of_week": dates.dayofweek + 1, "is_weekend": dates.dayofweek >= 5,
        "scheduled_departure_hour": 10, "scheduled_departure_minute": 15,
        "scheduled_arrival_hour": 12, "scheduled_arrival_minute": 30,
        "CRS_ELAPSED_TIME": 135., "OP_CARRIER": np.where(np.arange(len(dates)) % 2, "DL", "AA"),
        "ORIGIN": "JFK", "OP_CARRIER_FL_NUM": "100"})


@pytest.mark.parametrize("branch,cutoff,cal,select,threshold", [
    ("A", "2021-12-31", ("2022-01-01", "2022-03-31"), ("2022-04-01", "2022-06-30"), ("2022-07-01", "2022-09-30")),
    ("B", "2022-06-30", ("2022-07-01", "2022-07-31"), ("2022-08-01", "2022-08-31"), ("2022-09-01", "2022-09-30")),
])
def test_final_roles_have_no_overlap(branch, cutoff, cal, select, threshold):
    r = roles_for(branch, "2022Q4")
    assert r.train_end == pd.Timestamp(cutoff)
    for actual, expected in [(r.calibration, cal), (r.selection, select), (r.threshold, threshold)]:
        assert actual == tuple(map(pd.Timestamp, expected))
    assert r.threshold[1] < r.score[0]


def test_recent_verification_mirrors_time_horizon():
    assert roles_for("A", "2022Q2").train_end == pd.Timestamp("2021-06-30")
    assert roles_for("B", "2022Q2").train_end == pd.Timestamp("2021-12-31")


@pytest.mark.parametrize("end,purpose", [("2024-01-01", "development"), ("2022-12-31", "final"), ("2023-12-31", "confirmation")])
def test_final_labels_are_closed_before_any_io(tmp_path, end, purpose):
    data = BoundedData(tmp_path, tmp_path / "not_present")
    with pytest.raises(PermissionError):
        data.read("arrival", "2022-01-01", end, purpose=purpose)
    assert not list(tmp_path.iterdir())


def test_projected_read_excludes_q4_rows(tmp_path):
    root = tmp_path / "parent"
    path = root / "cache/arrival/2022.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"__date": pd.to_datetime(["2022-06-30", "2022-10-01"]),
                  "__target": [0, 1], "__key": ["early", "late"]}).to_parquet(path)
    data = BoundedData(tmp_path, root)
    result = data.read("arrival", "2022-01-01", "2022-06-30")
    assert result["__key"].tolist() == ["early"]


def test_q4_unlock_requires_real_untampered_model(tmp_path):
    import hashlib
    model = tmp_path / "model.joblib"
    model.write_bytes(b"test-model-state")
    freeze = tmp_path / "selection_freeze.json"
    record = {"path": model.name, "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}
    freeze.write_text(json.dumps({"status": "FROZEN_BEFORE_Q4", "models": {"model": record}}))
    data = BoundedData(tmp_path, tmp_path)
    data.unlock_q4(freeze)
    assert data.q4_unlocked
    model.write_bytes(b"changed-state")
    with pytest.raises(PermissionError, match="checksum"):
        BoundedData(tmp_path, tmp_path).unlock_q4(freeze)


def test_month_encoding_uses_only_prior_month_labels():
    f = frame()
    y = f["__target"].to_numpy(dtype=int)
    cutoff = pd.Timestamp("2018-05-01")
    changed = y.copy()
    changed[f["__date"].ge(cutoff)] = 1 - changed[f["__date"].ge(cutoff)]
    a = NativeScheduleEncoder("arrival", "history").fit_transform(f, y)
    b = NativeScheduleEncoder("arrival", "history").fit_transform(f, changed)
    pd.testing.assert_frame_equal(a.loc[f["__date"] < "2018-06-01"], b.loc[f["__date"] < "2018-06-01"])
    for col in a:
        if col.endswith("_rate"):
            assert (a.loc[f["__date"].dt.month.eq(1), col] == 0).all()
    assert "calendar_year" not in a and "__target" not in a


def test_history_exactly_matches_past_counts():
    f = frame()
    y = f["__target"].to_numpy(dtype=int)
    out = NativeScheduleEncoder("arrival", "history").fit_transform(f, y)
    index = int(np.flatnonzero(f["__date"].eq("2018-04-01"))[0])
    before = f["__date"] < "2018-04-01"
    same = before & f.OP_CARRIER.eq(f.OP_CARRIER.iloc[index])
    expected = (y[same].sum() + 50 * y[before].mean()) / (same.sum() + 50)
    assert out.carrier_rate.iloc[index] == pytest.approx(expected, abs=1e-7)
    assert out.carrier_frequency.iloc[index] == pytest.approx(same.sum() / before.sum())


def test_unknown_categories_are_missing_and_history_is_frozen():
    f = frame()
    encoder = NativeScheduleEncoder("arrival", "history")
    encoder.fit_transform(f, f["__target"])
    unknown = f.iloc[:2].copy()
    unknown.OP_CARRIER = "NEW"
    out = encoder.transform(unknown)
    assert out.OP_CARRIER.isna().all()
    assert str(out.OP_CARRIER.dtype) == "category"
    np.testing.assert_allclose(out.carrier_rate, float(f["__target"].mean()))
    assert (out.carrier_frequency == 0).all()


def test_exact_sampling_preserves_months_and_excludes_warmup():
    f = frame()
    i = warmup_indices(f, days=90, cap=63)
    assert len(i) == 63 and len(np.unique(i)) == 63
    assert f.iloc[i]["__date"].min() >= f["__date"].min() + pd.Timedelta(days=90)
    np.testing.assert_array_equal(i, warmup_indices(f, days=90, cap=63))


def test_fixed_floor_does_not_follow_selection_prevalence():
    y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    p = np.array([.1, .2, .3, .4, .5, .6, .7, .8, .9, .95])
    result = fixed_precision_threshold(y, p, .30965127426202366)
    assert result["precision_floor"] == .30965127426202366
    assert result["precision"] >= result["precision_floor"]


def test_gate_is_conjunction_of_all_frozen_targets():
    targets = {"ap_min": .3, "roc_min": .65, "brier_max": .15, "f1_min": .4, "precision_min": .3}
    m = {"ap": .31, "roc_auc": .66, "brier_score": .14, "f1": .39, "precision": .35}
    result = absolute_gate(m, targets, {"status": "SELECTED"})
    assert not result["passed"] and not result["checks"]["f1"]


def test_rare_unknown_carrier_uses_global_calibration():
    p = np.tile([.1, .2, .4, .6, .8, .9], 20)
    y = np.tile([0, 0, 1, 0, 1, 1], 20)
    carriers = np.where(np.arange(len(p)) < 100, "DL", "RARE")
    cal = CarrierCalibrator("carrier", min_rows=50, min_positives=20).fit(p, y, carriers)
    assert "RARE" not in cal.supported
    for name in ("RARE", "UNKNOWN"):
        np.testing.assert_allclose(cal.transform(p[:6], [name] * 6), cal.global_calibrator.transform(p[:6]))


def test_bundle_empty_and_expert_do_not_touch_other_carriers(tmp_path):
    f = frame()
    encoder = NativeScheduleEncoder("arrival", "native")
    a = encoder.fit_transform(f, f["__target"])
    global_model = DummyClassifier(strategy="prior").fit(a, f["__target"].astype(int))
    expert = DummyClassifier(strategy="constant", constant=1).fit(a, f["__target"].astype(int))
    model = V3Bundle(encoder, global_model, expert, alpha=.5)
    p = model.raw_probability(f)
    assert (p[f.OP_CARRIER.eq("DL")] > p[f.OP_CARRIER.eq("AA")].mean()).all()
    assert model.predict_proba(f.iloc[:0]).shape == (0, 2)
    path = tmp_path / "bundle.joblib"
    joblib.dump(model, path)
    np.testing.assert_allclose(model.predict_proba(f), joblib.load(path).predict_proba(f))


def test_bootstrap_adds_paired_f1_interval():
    f = frame().iloc[:56]
    y = f["__target"].to_numpy(dtype=int)
    p = np.tile([.2, .4, .6, .8], 14)
    stats = bootstrap_with_f1(f["__date"], y, p, p, .4, .4, iterations=20)
    np.testing.assert_allclose(stats["delta_ci_95"]["f1"], [0, 0])


def test_fit_deadline_and_exact_baseline_targets(tmp_path):
    config = yaml.safe_load(Path("configs/binary_improvement_v3.yaml").read_text())
    runner = V3Experiment(config, tmp_path)
    old = json.loads(Path(config["baseline_run"], "arrival/xgboost_baseline_metrics.json").read_text())
    assert runner.targets["arrival"]["precision_min"] == old["threshold_selection"]["precision_floor"]
    assert runner.targets["arrival"]["f1_min"] == old["q4_selected_threshold"]["f1"] + .02
    with pytest.raises(FitIncomplete):
        runner.fit_model("xgboost", {}, {}, {}, seed=202601, deadline=time.monotonic() - 1)


def test_weaker_baseline_cannot_change_acceptance_targets(tmp_path):
    config = yaml.safe_load(Path("configs/binary_improvement_v3.yaml").read_text())
    parent = tmp_path / "weaker"
    for task in config["tasks"]:
        folder = parent / task
        folder.mkdir(parents=True)
        source = Path(config["baseline_run"], task, "xgboost_baseline_metrics.json")
        record = json.loads(source.read_text())
        record["q4_selected_threshold"]["ap"] -= .01
        (folder / source.name).write_text(json.dumps(record))
    config["baseline_run"] = str(parent)
    with pytest.raises(ValueError, match="targets changed"):
        V3Experiment(config, tmp_path / "run")


@pytest.mark.parametrize("family", ["xgboost", "hgb", "lightgbm"])
def test_native_estimator_fits_and_reloads_with_unknown_categories(tmp_path, family):
    config = yaml.safe_load(Path("configs/binary_improvement_v3.yaml").read_text())
    runner = V3Experiment(config, tmp_path)
    f = frame()
    encoder = NativeScheduleEncoder("arrival", "native")
    a = encoder.fit_transform(f, f["__target"])
    matrix = {"train": a, "y": f["__target"].to_numpy(dtype=int), "dates": f["__date"].to_numpy(),
              "carriers": f.OP_CARRIER.to_numpy(), "train_end": str(f["__date"].max())}
    params = {"max_iter" if family == "hgb" else "n_estimators": 7}
    spec = {"half_life": 365, "weight": "sqrt"}
    model = runner.fit_model(family, params, matrix, spec, seed=202601, deadline=time.monotonic() + 90)
    bundle = V3Bundle(encoder, model).to_cpu()
    test = f.iloc[:4].copy()
    test.OP_CARRIER = "UNKNOWN"
    before = bundle.predict_proba(test)
    path = tmp_path / (family + ".joblib")
    joblib.dump(bundle, path)
    np.testing.assert_allclose(before, joblib.load(path).predict_proba(test))
    assert np.isfinite(before).all() and (before >= 0).all() and (before <= 1).all()


def test_persisted_data_cache_does_not_unlock_future_labels(tmp_path):
    import hashlib
    parent = tmp_path / "parent"
    path = parent / "cache/arrival/2022.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"__date": pd.to_datetime(["2022-10-01"]), "__key": ["q4"], "__target": [1]}).to_parquet(path)
    model = tmp_path / "model.joblib"
    model.write_bytes(b"frozen-model")
    freeze = tmp_path / "selection_freeze.json"
    freeze.write_text(json.dumps({"status": "FROZEN_BEFORE_Q4", "models": {
        "model": {"path": model.name, "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}}}))
    cache = tmp_path / "cache"
    data = BoundedData(tmp_path, parent, cache_root=cache)
    data.unlock_q4(freeze)
    assert len(data.read("arrival", "2022-10-01", "2022-12-31", purpose="final")) == 1
    assert list(cache.glob("*.parquet"))
    with pytest.raises(PermissionError):
        BoundedData(tmp_path, parent, cache_root=cache).read("arrival", "2022-10-01", "2022-12-31", purpose="final")


def test_metadata_write_retries_windows_reader_lock(tmp_path, monkeypatch):
    from src.models.binary_v3_execution import write_json
    original = Path.replace
    attempts = []
    def locked_then_available(path, target):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("sharing violation")
        return original(path, target)
    monkeypatch.setattr(Path, "replace", locked_then_available)
    path = tmp_path / "progress.json"
    write_json(path, {"status": "RUNNING"})
    assert len(attempts) == 3
    assert json.loads(path.read_text())["status"] == "RUNNING"


def test_shortlist_respects_roc_brier_and_precision_guards():
    guards = {name: True for name in ("roc_noninferiority", "brier_guard", "precision_floor", "threshold_feasible")}
    safe = {"relative_gate": {"passed": False, "checks": guards}, "ap_delta": .004, "f1_delta": .01}
    unsafe = {"relative_gate": {"passed": False, "checks": {**guards, "roc_noninferiority": False}},
              "ap_delta": .03, "f1_delta": .1}
    assert V3Experiment.rank([safe]) > V3Experiment.rank([unsafe])


def test_updated_data_control_can_win_the_same_absolute_goals():
    from src.models.binary_v3_execution import eligible_primary
    records = {"control": {"task": "arrival", "role": "matched_control", "seed": 202601},
        "hpo": {"task": "arrival", "role": "research_candidate", "seed": 202601},
        "diagnostic": {"task": "arrival", "role": "research_candidate", "seed": 202602}}
    assert eligible_primary(records, "arrival") == [records["control"], records["hpo"]]
