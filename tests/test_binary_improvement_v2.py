"""Behavioral checks for leakage, probability decisions and portable bundles."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.dummy import DummyClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from src.features.binary_improvement import ScheduleHistoryEncoder, make_preprocessor, prepare_frame
from src.models.binary_improvement import (BinaryModelBundle, ProbabilityCalibrator,
    binary_metrics, paired_block_bootstrap, positive_probability, select_threshold,
    promotion_gate, select_calibrator)
from src.models.binary_improvement_execution import Experiment


def features():
    dates = pd.to_datetime(["2019-01-01", "2019-01-02", "2020-01-01", "2020-01-02"])
    return pd.DataFrame({"__date": dates, "calendar_year": dates.year,
        "calendar_month": 1, "calendar_day_of_month": dates.day,
        "calendar_day_of_week": dates.dayofweek + 1, "is_weekend": 0,
        "scheduled_departure_hour": [10, 11, 10, 11], "scheduled_departure_minute": 0,
        "scheduled_arrival_hour": 12, "scheduled_arrival_minute": 0,
        "CRS_ELAPSED_TIME": 120., "OP_CARRIER": "AA", "ORIGIN": "JFK",
        "OP_CARRIER_FL_NUM": ["1", "2", "1", "2"]})


def test_historical_training_never_reads_current_or_future_labels():
    frame = features()
    a = ScheduleHistoryEncoder("arrival", "F2").fit_transform(frame, [0, 1, 0, 0])
    b = ScheduleHistoryEncoder("arrival", "F2").fit_transform(frame, [0, 1, 1, 1])
    pd.testing.assert_frame_equal(a, b)
    assert (a.loc[:1, "OP_CARRIER_historical_rate"] == 0.5).all()
    c = ScheduleHistoryEncoder("arrival", "F2").fit_transform(frame, [1, 1, 0, 0])
    assert (c.loc[2:, "OP_CARRIER_historical_rate"] > a.loc[2:, "OP_CARRIER_historical_rate"]).all()


def test_inference_history_maps_are_frozen_and_unknowns_safe():
    frame = features()
    enc = ScheduleHistoryEncoder("arrival", "F2").fit(frame, [0, 0, 0, 1])
    new = frame.iloc[:1].copy()
    new["OP_CARRIER"] = "NEW"
    result = enc.transform(new)
    assert result["OP_CARRIER_historical_rate"].iloc[0] == 0.25
    assert result["OP_CARRIER_frequency"].iloc[0] == 0
    assert "__date" not in result and "__target" not in result


@pytest.mark.parametrize("bad", [[np.nan], [np.inf], [-0.1], [1.1]])
def test_invalid_probability_rejected(bad):
    with pytest.raises(ValueError):
        binary_metrics([1], bad)


def test_threshold_can_improve_recall_without_changing_ranking():
    y = np.array([0, 0, 0, 1, 0, 1, 1, 1])
    p = np.array([.01, .02, .04, .2, .1, .25, .3, .4])
    result = select_threshold(y, p)
    before = binary_metrics(y, p)
    after = binary_metrics(y, p, result["threshold"])
    assert after["recall"] > before["recall"]
    assert after["precision"] >= result["precision_floor"]
    assert after["ap"] == before["ap"]
    assert after["roc_auc"] == before["roc_auc"]


def test_infeasible_threshold_keeps_half():
    result = select_threshold([1, 1, 1, 0], [.5, .5, .5, .5])
    assert result["status"] == "NO_FEASIBLE_THRESHOLD"
    assert result["threshold"] == .5


@pytest.mark.parametrize("method", ["identity", "sigmoid", "isotonic"])
def test_calibrator_roundtrip(method, tmp_path):
    p, y = np.array([.1, .2, .3, .4, .6, .7, .8, .9]), np.array([0, 0, 1, 0, 1, 0, 1, 1])
    cal = ProbabilityCalibrator(method).fit(p, y)
    path = tmp_path / "cal.joblib"
    joblib.dump(cal, path)
    np.testing.assert_allclose(cal.transform(p), joblib.load(path).transform(p))
    assert cal.transform(np.array([])).shape == (0,)


def test_bundle_loads_in_fresh_process_handles_empty_and_unseen(tmp_path):
    frame = features()
    enc = ScheduleHistoryEncoder("arrival", "F2")
    derived = enc.fit_transform(frame, [0, 1, 0, 1])
    prep = make_preprocessor("arrival", "F2", derived)
    a = prep.fit_transform(derived)
    model = DummyClassifier(strategy="prior").fit(a, [0, 1, 0, 1])
    bundle = BinaryModelBundle(enc, prep, model, metadata={"task": "arrival"})
    joblib.dump(bundle, tmp_path / "model.joblib")
    frame.to_parquet(tmp_path / "sample.parquet", index=False)
    result = subprocess.run([sys.executable, "-c",
        "import joblib,pandas as pd,sys; m=joblib.load(sys.argv[1]); print(m.predict_proba(pd.read_parquet(sys.argv[2])).shape)",
        str(tmp_path / "model.joblib"), str(tmp_path / "sample.parquet")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "(4, 2)" in result.stdout
    assert bundle.predict_proba(frame.iloc[:0]).shape == (0, 2)
    new = frame.copy()
    new["OP_CARRIER"] = "UNKNOWN"
    assert np.isfinite(bundle.predict_proba(new)).all()


def test_reversed_class_order_is_respected():
    class Reverse:
        classes_ = np.array([1, 0])
        def predict_proba(self, X):
            return np.tile([.7, .3], (len(X), 1))
    np.testing.assert_allclose(positive_probability(Reverse(), np.zeros((3, 2))), .7)


def test_bootstrap_is_paired_and_preserves_ties():
    dates = pd.Series(pd.date_range("2023-01-01", periods=56))
    y = np.arange(56) % 2
    p = np.tile([.2, .4, .4, .8], 14)
    stats = paired_block_bootstrap(dates, y, p, p, iterations=20)
    for interval in stats["delta_ci_95"].values():
        np.testing.assert_allclose(interval, [0, 0], atol=1e-12)


def test_bootstrap_ranking_matches_sklearn_with_tied_scores():
    dates = pd.Series(pd.date_range("2023-01-01", periods=6))
    y = np.array([0, 1, 0, 1, 0, 1])
    candidate = np.array([.1, .5, .5, .5, .3, .9])
    baseline = np.array([.2, .2, .4, .4, .6, .6])
    stats = paired_block_bootstrap(dates, y, candidate, baseline, iterations=3)
    ap_delta = average_precision_score(y, candidate) - average_precision_score(y, baseline)
    auc_delta = roc_auc_score(y, candidate) - roc_auc_score(y, baseline)
    np.testing.assert_allclose(stats["delta_ci_95"]["ap"], [ap_delta, ap_delta])
    np.testing.assert_allclose(stats["delta_ci_95"]["roc_auc"], [auc_delta, auc_delta])


def test_calibration_refit_does_not_use_threshold_or_q4_labels():
    q1 = np.array([.1, .2, .4, .6, .8, .9])
    y1 = np.array([0, 0, 1, 0, 1, 1])
    q2 = np.array([.15, .3, .5, .7, .85, .95])
    y2 = np.array([0, 0, 0, 1, 1, 1])
    calibration, scores = select_calibrator(q1, y1, q2, y2)
    expected = ProbabilityCalibrator(calibration.method).fit(np.r_[q1, q2], np.r_[y1, y2])
    np.testing.assert_allclose(calibration.transform(q2), expected.transform(q2))
    assert set(scores) == {"identity", "sigmoid", "isotonic"}


def test_deadline_discards_fit_before_start(tmp_path):
    from src.models.binary_improvement_execution import FitIncomplete
    import time
    config = yaml.safe_load(Path("configs/binary_improvement_v2.yaml").read_text())
    experiment = Experiment(config, tmp_path)
    with pytest.raises(FitIncomplete):
        experiment.fit_classifier("xgboost", {}, np.zeros((4, 1)), np.array([0, 1, 0, 1]), deadline=time.monotonic() - 1)


@pytest.mark.parametrize("family,count_key", [("xgboost", "n_estimators"), ("hgb", "max_iter")])
def test_fixed_iteration_challenger_does_not_use_early_stop_labels(tmp_path, family, count_key):
    config = yaml.safe_load(Path("configs/binary_improvement_v2.yaml").read_text())
    experiment = Experiment(config, tmp_path)
    rng = np.random.default_rng(12)
    a = rng.normal(size=(80, 3)).astype(np.float32)
    y = np.arange(80) % 2
    model = experiment.fit_classifier(family, {count_key: 7, "early_stopping": False}, a, y,
        valid=a, valid_y=np.zeros(80))
    actual = model.get_booster().num_boosted_rounds() if family == "xgboost" else model.n_iter_
    assert actual == 7


def test_promotion_rejects_only_threshold_improvement():
    baseline = {"ap": .3, "roc_auc": .65, "brier_score": .15, "f1": .3, "precision": .4}
    candidate = {**baseline, "f1": .5}
    result = promotion_gate(candidate, baseline, {"precision_floor": .3, "status": "SELECTED"})
    assert not result["passed"]
    assert not result["checks"]["ap_gain"]


def test_holdout_blocked_even_before_cache_or_io(tmp_path):
    config = yaml.safe_load(Path("configs/binary_improvement_v2.yaml").read_text())
    experiment = Experiment(config, tmp_path)
    with pytest.raises(PermissionError, match="2024"):
        experiment.load_year("arrival", 2024)
    assert not list(tmp_path.iterdir())


def test_raw_schedule_inference_ignores_actual_delay_and_needs_no_target():
    dates = pd.Series(pd.to_datetime(["2023-01-01", "2023-01-02"]))
    raw = pd.DataFrame({"FL_DATE": dates, "OP_CARRIER": "AA", "OP_CARRIER_FL_NUM": 1,
        "ORIGIN": "JFK", "DEST": "ATL", "CRS_DEP_TIME": dates + pd.Timedelta(hours=10), "CRS_ARR_TIME": dates + pd.Timedelta(hours=12),
        "CRS_ELAPSED_TIME": 120, "MONTH": 1, "DAY_OF_MONTH": dates.dt.day,
        "DAY_OF_WEEK": dates.dt.dayofweek + 1, "flight_key": ["a", "b"]})
    a = prepare_frame(raw, "arrival", inference=True)
    raw["ARR_DELAY"] = [999, -999]
    b = prepare_frame(raw, "arrival", inference=True)
    pd.testing.assert_frame_equal(a, b)
    assert "__target" not in a


@pytest.mark.parametrize("status,smoke", [("SMOKE_COMPLETE", True), ("INCOMPLETE", False), ("RUNNING", False)])
def test_packaging_rejects_nonfinal_or_smoke_results(tmp_path, status, smoke):
    import json
    from scripts.package_binary_improvement_v2 import package
    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text(json.dumps({"status": status, "smoke": smoke}))
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="completed full-data"):
        package(run, output)
    assert not output.exists()
