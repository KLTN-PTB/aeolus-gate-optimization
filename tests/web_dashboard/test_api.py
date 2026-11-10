import io

from fastapi.testclient import TestClient

from web_dashboard.app import create_app
from web_dashboard.worker import execute


def test_upload_run_results_exports_and_history(tmp_path, raw_table):
    app = create_app(tmp_path, launch_jobs=False)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        raw = io.BytesIO()
        raw_table.to_parquet(raw, index=False)
        response = client.post("/api/datasets", files={"files": ("raw.parquet", raw.getvalue())})
        assert response.status_code == 201, response.text
        dataset = response.json()
        assert dataset["can_run"]
        body = {"dataset_id": dataset["id"], "service_date": "2026-07-01", "solver": "greedy"}
        response = client.post("/api/runs", json=body)
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert client.post("/api/runs", json=body).status_code == 409
        assert client.get(f"/api/runs/{run_id}/results").status_code == 409
        execute(tmp_path, run_id)
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"
        assert client.get(f"/api/runs/{run_id}/results").json()["summary"]["assigned_count"] == 3
        assert client.get(f"/api/runs/{run_id}/exports/bundle").content[:2] == b"PK"
        assert client.get(f"/api/runs/{run_id}/exports/worker.log").status_code == 404
        assert len(client.get("/api/runs").json()) == 1
    with TestClient(create_app(tmp_path, launch_jobs=False)) as client:
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"


def test_export_roundtrip_and_tamper_rejection(tmp_path, raw_table):
    import json
    import hashlib
    import zipfile
    import pandas as pd
    app = create_app(tmp_path, launch_jobs=False)
    with TestClient(app) as client:
        raw = io.BytesIO()
        raw_table.to_parquet(raw, index=False)
        dataset = client.post('/api/datasets', files={'files': ('raw.parquet', raw.getvalue())}).json()
        rid = client.post('/api/runs', json={'dataset_id':dataset['id'], 'service_date':'2026-07-01', 'solver':'greedy'}).json()['id']
        execute(tmp_path, rid)
        result = client.get(f'/api/runs/{rid}/results').json()
        csv = pd.read_csv(io.BytesIO(client.get(f'/api/runs/{rid}/exports/assignments.csv').content))
        parquet = pd.read_parquet(io.BytesIO(client.get(f'/api/runs/{rid}/exports/assignments.parquet').content))
        assert len(csv) == len(parquet) == result['summary']['assigned_count']
        assert csv.flight_id.tolist() == parquet.flight_id.tolist()
        bundle = client.get(f'/api/runs/{rid}/exports/bundle').content
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            checksums = json.loads(archive.read('checksums.json'))
            for name, digest in checksums['files'].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
            assert json.loads(archive.read('result.json'))['manifest'] == json.loads(archive.read('manifest.json'))
        path = tmp_path / 'runs' / rid / 'result.json'
        tampered = json.loads(path.read_text(encoding='utf-8'))
        tampered['summary']['decision_cost'] = 999
        path.write_text(json.dumps(tampered), encoding='utf-8')
        assert client.get(f'/api/runs/{rid}/results').status_code == 409
        assert client.get(f'/api/runs/{rid}/exports/bundle').status_code == 409


def test_invalid_upload_and_foreign_origin(tmp_path):
    with TestClient(create_app(tmp_path, launch_jobs=False)) as client:
        assert client.post("/api/datasets", files={"files": ("x.csv", b"x")}).status_code == 422
        assert client.post("/api/datasets", files={"files": ("x.parquet", b"invalid")}).status_code == 422
        assert client.post("/api/runs", json={}, headers={"Origin": "https://example.com"}).status_code == 403
        assert client.get("/api/runs/not-a-run").status_code == 404


def test_interrupted_run_is_recovered(tmp_path):
    app = create_app(tmp_path, launch_jobs=False)
    run_id = app.state.store.create_run({"dataset_id": "a" * 32})
    with TestClient(app) as client:
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "interrupted"


def test_job_runner_shutdown_marks_active_job_interrupted(tmp_path, monkeypatch):
    import subprocess
    from web_dashboard.app import JobRunner
    from web_dashboard.storage import Store
    store = Store(tmp_path)
    run_id = store.create_run({"dataset_id": "a" * 32})
    runner = JobRunner(store)
    class FakeProc:
        pid = 999999
        def wait(self, timeout=None):
            runner.closing = True
            return 1
        def poll(self):
            return 1
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(runner, "stop_process_tree", lambda proc: None)
    runner._monitor(run_id, experiment=False)
    assert store.run(run_id)["status"] == "interrupted"


def test_upload_name_never_becomes_a_server_path(tmp_path, raw_table):
    with TestClient(create_app(tmp_path, launch_jobs=False)) as client:
        content = io.BytesIO()
        raw_table.to_parquet(content, index=False)
        response = client.post("/api/datasets", files={"files": ("../../outside.parquet", content.getvalue())})
        assert response.status_code == 201
        assert response.json()["filenames"] == ["outside.parquet"]
        assert not (tmp_path.parent / "outside.parquet").exists()
