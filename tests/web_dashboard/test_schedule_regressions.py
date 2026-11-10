import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.features.binary_improvement import prepare_frame
from src.features.tabular_features import ArrivalFeatureContractViolation
from web_dashboard.normalization import normalize_files, dataset_eligibility, validate_run_dates, InputError
from web_dashboard.schedule_features import prepare_schedule_inference
from web_dashboard.thesis_profile import ThesisInference, canonical_schedule, ACTIVE, explain
from web_dashboard.app import create_app


def normalize(tmp_path, raw):
    source = tmp_path / "raw.parquet"
    raw.to_parquet(source, index=False)
    return normalize_files([source])


@pytest.mark.parametrize("task", ["arrival", "departure"])
@pytest.mark.parametrize("clock", [0, 2400])
def test_midnight_inference_and_training_boundary(tmp_path, raw_table, task, clock):
    raw = raw_table.iloc[:1].copy()
    raw["CRS_DEP_TIME"], raw["CRS_ARR_TIME"] = clock, 130
    if task == "departure":
        raw["ORIGIN"], raw["DEST"] = "ATL", "MCO"
    normalized, report = normalize(tmp_path, raw)
    assert report["can_run"]
    frame = prepare_schedule_inference(normalized, task)
    assert frame.scheduled_departure_hour.tolist() == [0]
    assert frame.calendar_day_of_month.tolist() == [1]
    assert frame["__key"].tolist() == normalized.flight_key.tolist()
    assert normalized.prediction_cutoff_utc.iloc[0].startswith(
        "2026-07-01T02:00" if clock == 0 else "2026-07-02T02:00")
    if task == "arrival":
        with pytest.raises(ArrivalFeatureContractViolation):
            prepare_frame(canonical_schedule(normalized), task, inference=True)
    if ACTIVE.exists():
        engine = ThesisInference()
        models = engine.load_and_verify_models()
        incoming = normalized if task == "arrival" else normalized.iloc[:0]
        outgoing = normalized if task == "departure" else normalized.iloc[:0]
        records, lookup = engine.run_native_inference(incoming, outgoing, models)
        assert len(records) == len(lookup) == 1 and np.isfinite(list(lookup.values())).all()
        if task == "arrival" and clock == 2400:
            explanation = explain(normalized, task, "regression")
            assert len(explanation["values"]) == 1


@pytest.mark.parametrize("task", ["arrival", "departure"])
def test_feature_and_checkpoint_parity(tmp_path, raw_table, task):
    raw = raw_table.loc[raw_table.DEST.eq("ATL") if task == "arrival" else raw_table.ORIGIN.eq("ATL")].copy()
    normalized, _ = normalize(tmp_path, raw)
    before = prepare_frame(canonical_schedule(normalized), task, inference=True)
    after = prepare_schedule_inference(normalized, task)
    pd.testing.assert_frame_equal(before, after)
    if ACTIVE.exists():
        engine = ThesisInference()
        models = engine.load_and_verify_models()
        for kind in ("model", "classifier"):
            bundle = models[task][kind]
            pd.testing.assert_frame_equal(bundle.predict_schedule(canonical_schedule(normalized)), bundle.predict_prepared_schedule(after))
    normalized["ARR_DELAY"], normalized["DEP_DELAY"] = 123456., -123456.
    pd.testing.assert_frame_equal(after, prepare_schedule_inference(normalized, task))


@pytest.mark.parametrize("value", ["2099-99-99 09:30:00", "2026-07-02 09:30:00", "2026-07-01 09:30:00+01:00",
    "2026-07-01 09:30:01", "2026-07-01 09:30:00garbage", "09:30:01", "0930x"])
def test_invalid_arrival_timestamp_is_rejected(tmp_path, raw_table, value):
    raw = raw_table.iloc[:1].copy()
    raw["CRS_ARR_TIME"] = value
    _, report = normalize(tmp_path, raw)
    assert not report["can_run"] and report["invalid_rows"] == 1


@pytest.mark.parametrize("value", ["2026-07-01 09:30:00", "2026-07-01T09:30:00-04:00", "09:30", 930])
def test_valid_arrival_representations(tmp_path, raw_table, value):
    raw = raw_table.iloc[:1].copy()
    raw["CRS_ARR_TIME"] = value
    assert normalize(tmp_path, raw)[1]["can_run"]


def test_operating_year_eligibility_and_legacy_report(tmp_path, raw_table):
    raw = raw_table.iloc[:1].copy()
    raw["FL_DATE"], raw["CRS_DEP_TIME"], raw["CRS_ARR_TIME"] = "2023-12-31", 2330, 100
    frame, report = normalize(tmp_path, raw)
    assert not report["can_run"] and not report["dates"][0]["eligible"]
    assert report["dates"][0]["blocked_reason"]
    with pytest.raises(InputError):
        validate_run_dates(frame, "2024-01-01")
    old = {**report, "can_run": True, "dates": [{"date": "2024-01-01", "total": 1}]}
    assert not dataset_eligibility(old)["can_run"]
    raw2 = raw.copy()
    raw2["CRS_DEP_TIME"], raw2["CRS_ARR_TIME"], raw2["OP_CARRIER_FL_NUM"] = 800, 930, 999
    _, mixed = normalize(tmp_path, pd.concat([raw, raw2], ignore_index=True))
    assert mixed["can_run"] and [d["eligible"] for d in mixed["dates"]] == [True, False]
    with TestClient(create_app(tmp_path / "runtime", launch_jobs=False)) as client:
        data = io.BytesIO()
        raw.to_parquet(data, index=False)
        uploaded = client.post("/api/datasets", files={"files": ("raw.parquet", data.getvalue())}).json()
        assert not uploaded["can_run"]
        response = client.post("/api/runs", json={"dataset_id": uploaded["id"], "service_date": "2024-01-01"})
        assert response.status_code == 422


def test_api_and_worker_recheck_normalized_source_year(tmp_path, raw_table):
    from web_dashboard.storage import Store
    from web_dashboard.worker import execute
    from web_dashboard.contracts import RunRequest
    from web_dashboard.pipeline import run_pipeline
    frame, report = normalize(tmp_path, raw_table)
    store = Store(tmp_path / "runtime")
    dataset_id = "a" * 32
    folder = store.root / "datasets" / dataset_id
    folder.mkdir(parents=True)
    # Simulate a report/data mismatch in an older saved dataset.
    frame.loc[0, "FL_DATE"] = "2024-07-01"
    frame.to_parquet(folder / "normalized.parquet", index=False)
    store.put_dataset(dataset_id, report)
    config = {"dataset_id": dataset_id, "service_date": "2026-07-01"}
    with TestClient(create_app(store.root, launch_jobs=False)) as client:
        assert client.post("/api/runs", json=config).status_code == 422
    rid = store.create_run(config)
    execute(store.root, rid)
    assert store.run(rid)["status"] == "failed"
    with pytest.raises(InputError, match="2024"):
        run_pipeline(frame, RunRequest(**config), tmp_path / "no_model_load", report)
