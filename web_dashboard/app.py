"""Local-only FastAPI backend + built React frontend (one server, one worker)."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4

import psutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from web_dashboard.contracts import MAX_SELECTED_LEGS, MAX_UPLOAD_BYTES, PRESETS, RunRequest, ExperimentRequest
from web_dashboard.normalization import InputError, normalize_files
from web_dashboard.pipeline import ROOT, json_write
from web_dashboard.storage import Store

DIST = ROOT / "web_dashboard/frontend/dist"
ALLOWED_ORIGINS = {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (8000, 5173)}
EXPORTS = {"bundle": "bundle.zip", "manifest": "manifest.json", "normalized": "normalized.parquet",
           **{f"{name}.{ext}": f"{name}.{ext}" for name in ("predictions", "occupancies", "assignments")
              for ext in ("csv", "parquet")}}


class BodyTooLarge(Exception):
    pass


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        size = 0
        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > MAX_UPLOAD_BYTES + 1024 * 1024:
                raise BodyTooLarge()
            return message
        try:
            await self.app(scope, bounded_receive, send)
        except BodyTooLarge:
            await JSONResponse({"detail": "Tổng dữ liệu tải lên vượt 500 MB."}, status_code=413)(scope, receive, send)


class JobRunner:
    def __init__(self, store):
        self.store, self.process = store, None
        self.lock = threading.Lock()
        self.closing = False

    def start(self, run_id, experiment=False):
        # Store.create_run already provides transactional single-job admission.
        threading.Thread(target=self._monitor, args=(run_id, experiment), daemon=True).start()

    @staticmethod
    def stop_process_tree(process):
        # Windows venv launchers can create a second Python process. Stop ONLY
        # descendants of this owned worker, otherwise a timeout could leave ML
        # running after the job has already been marked interrupted.
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        psutil.wait_procs(children, timeout=5)

    def _monitor(self, run_id, experiment=False):
        with self.lock:
            update = self.store.experiment_update if experiment else self.store.update
            get = self.store.experiment if experiment else self.store.run
            if self.closing:
                update(run_id, status="interrupted", stage="validation", error="Ứng dụng đang dừng.")
                return
            directory = self.store.root / ("experiments" if experiment else "runs") / run_id
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "worker.log").open("w", encoding="utf-8") as log:
                try:
                    env = {**os.environ, "PYTHONUTF8": "1"}
                    self.process = subprocess.Popen(
                        [sys.executable, "-m", "web_dashboard.experiment_worker" if experiment else "web_dashboard.worker", str(self.store.root), run_id],
                        cwd=ROOT, stdout=log, stderr=log, env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    if self.closing:
                        self.stop_process_tree(self.process)
                        update(run_id, status="interrupted", stage="worker", error="Ứng dụng đã dừng trước khi worker sẵn sàng.")
                        return
                    try:
                        self.process.wait(timeout=None if experiment else 600)
                    except subprocess.TimeoutExpired:
                        self.stop_process_tree(self.process)
                        update(run_id, status="failed", stage="timeout", error="Tác vụ vượt ngân sách tổng 10 phút.")
                    current = get(run_id)
                    if current["status"] in ("queued", "running"):
                        update(run_id, status="failed", stage=current["stage"],
                                          error="Tiến trình tính toán đã dừng bất thường; xem worker.log.")
                except Exception as exc:
                    update(run_id, status="failed", stage="worker", error=str(exc))
                finally:
                    self.process = None

    def shutdown(self):
        self.closing = True
        process = self.process
        if process is not None and process.poll() is None:
            self.stop_process_tree(process)


def create_app(storage_root: Path | None = None, *, launch_jobs: bool = True) -> FastAPI:
    store = Store(storage_root or ROOT / "artifacts/web_dashboard")
    runner = JobRunner(store)

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        runner.shutdown()
        store.recover()

    app = FastAPI(title="Aeolus End-to-End API", version="1.0.0", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def local_only(request, call_next):
        origin = request.headers.get("origin")
        same_local_origin = origin == str(request.base_url).rstrip("/") and request.url.hostname in ("localhost", "127.0.0.1")
        if request.method == "POST" and origin and origin not in ALLOWED_ORIGINS and not same_local_origin:
            return JSONResponse({"detail": "Chỉ cho phép thao tác từ giao diện localhost."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def get_run(run_id):
        run = store.run(run_id)
        if not run:
            raise HTTPException(404, "Không tìm thấy lần chạy.")
        return run

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "local", "frontend_built": DIST.exists()}

    @app.get("/api/airport-profiles")
    def profiles():
        return {"airports": [{"code": "ATL", "name": "Hartsfield–Jackson Atlanta", "timezone": "America/New_York"}],
                "presets": PRESETS, "max_upload_mb": 500, "max_selected_legs": MAX_SELECTED_LEGS,
                "historical_replay_url": "http://127.0.0.1:8501"}

    @app.get("/api/example.parquet")
    def example():
        from web_dashboard.examples import sample_schedule
        buffer = io.BytesIO()
        sample_schedule().to_parquet(buffer, index=False)
        return Response(buffer.getvalue(), media_type="application/octet-stream",
                        headers={"Content-Disposition": 'attachment; filename="ILLUSTRATIVE_ONLY_ATL_schedule.parquet"'})

    @app.get('/api/model-profiles')
    def model_profiles():
        from web_dashboard.thesis_profile import profiles
        return profiles()

    @app.get('/api/model-comparison')
    def model_comparison():
        from web_dashboard.thesis_profile import profile
        try:
            p = profile()
            global_path = ROOT / p['model_run'] / 'shap_global.json'
            return {'scope': p['evaluation_scope'], 'models': p['comparison'],
                    'global_shap': json.loads(global_path.read_text()) if global_path.exists() else None}
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/runs/{run_id}/explanation/{flight_id}')
    def explanation(run_id: str, flight_id: str, kind: str = 'regression'):
        import pandas as pd
        from web_dashboard.thesis_profile import profile, explain
        get_run(run_id)
        if kind not in ('regression', 'classification'):
            raise HTTPException(422, 'Unknown explanation target')
        directory = store.root / 'runs' / run_id
        result_path = directory / 'result.json'
        if not result_path.exists():
            raise HTTPException(409, 'Run is not complete')
        result = json.loads(result_path.read_text(encoding='utf-8'))
        if result['manifest']['config'].get('model_profile') != 'thesis_xgboost':
            raise HTTPException(409, 'SHAP này chỉ giải thích checkpoint XGBoost của profile đề cương.')
        frame = pd.read_parquet(directory / 'normalized.parquet')
        raw = frame.loc[frame.flight_key.eq(flight_id)]
        if len(raw) != 1:
            raise HTTPException(404, 'Flight not found')
        task = 'arrival' if raw.direction.iloc[0] == 'ARR' else 'departure'
        model_run = result['manifest']['models'][task]['version']
        try:
            active = profile()
            if active['version'] != model_run:
                raise ValueError('The checkpoint used by this run is no longer the active release')
            record = active['models'][f'{task}_{kind}_xgboost']
            import hashlib
            key = hashlib.sha256(f'{flight_id}:{record["sha256"]}'.encode()).hexdigest()
            cache = directory / f'shap_{key}.json'
            if not cache.exists():
                json_write(cache, explain(raw, task, kind, model_record=record))
            return json.loads(cache.read_text())
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/datasets", status_code=201)
    async def upload(files: list[UploadFile] = File(...)):
        if not 1 <= len(files) <= 2:
            raise HTTPException(422, "Tải một file tổng hợp hoặc hai file đến/đi.")
        dataset_id = uuid4().hex
        directory = store.root / "datasets" / dataset_id
        directory.mkdir(parents=True)
        paths, names, size = [], [], 0
        try:
            for index, file in enumerate(files):
                if not file.filename or not file.filename.lower().endswith(".parquet"):
                    raise HTTPException(422, "Chỉ nhận file .parquet.")
                path = directory / f"source_{index}.parquet"
                with path.open("wb") as stream:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_UPLOAD_BYTES:
                            raise HTTPException(413, "Tổng file vượt 500 MB.")
                        stream.write(chunk)
                paths.append(path)
                names.append(Path(file.filename.replace("\\", "/")).name)
            table, report = await run_in_threadpool(normalize_files, paths)
            report.update({"id": dataset_id, "filenames": names, "size_bytes": size})
            for source, name in zip(report["sources"], names):
                source["filename"] = name
            await run_in_threadpool(table.to_parquet, directory / "normalized.parquet", index=False)
            json_write(directory / "validation.json", report)
            store.put_dataset(dataset_id, report)
            return report
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            for file in files:
                await file.close()
            # Uploaded raw copies are temporary. Retain source hashes, validation,
            # and normalized records; do not retain rejected/oversize raw data.
            for path in directory.glob("source_*.parquet"):
                path.unlink(missing_ok=True)

    @app.get("/api/datasets/{dataset_id}")
    def dataset(dataset_id: str):
        report = store.dataset(dataset_id)
        if report is None:
            raise HTTPException(404, "Không tìm thấy dữ liệu.")
        return report

    @app.post("/api/runs", status_code=202)
    def start_run(request: RunRequest):
        if request.model_profile == 'thesis_xgboost':
            from web_dashboard.thesis_profile import profile
            try:
                profile()
            except (ValueError, OSError) as exc:
                raise HTTPException(409, str(exc)) from exc
        report = store.dataset(request.dataset_id)
        if report is None:
            raise HTTPException(404, "Không tìm thấy dữ liệu.")
        if not report["can_run"]:
            raise HTTPException(422, "File còn lỗi dữ liệu; vui lòng sửa và tải lại.")
        day = next((d for d in report["dates"] if d["date"] == request.service_date.isoformat()), None)
        if day is None:
            raise HTTPException(422, "Ngày đã chọn không có lượt bay ATL.")
        if day["total"] > MAX_SELECTED_LEGS:
            raise HTTPException(422, f"Ngày đã chọn vượt {MAX_SELECTED_LEGS} lượt bay; không tự lấy mẫu.")
        try:
            run_id = store.create_run(request.model_dump(mode="json"))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        if launch_jobs:
            runner.start(run_id)
        return get_run(run_id)

    @app.get("/api/runs")
    def history():
        return store.runs()

    @app.get("/api/runs/{run_id}")
    def status(run_id: str):
        return get_run(run_id)

    @app.get("/api/runs/{run_id}/results")
    def results(run_id: str):
        run = get_run(run_id)
        if run["status"] != "completed":
            raise HTTPException(409, "Lần chạy chưa hoàn tất.")
        return json.loads((store.root / "runs" / run_id / "result.json").read_text(encoding="utf-8"))

    @app.get("/api/runs/{run_id}/exports/{kind}")
    def export(run_id: str, kind: str):
        run = get_run(run_id)
        if run["status"] != "completed":
            raise HTTPException(409, "Lần chạy chưa hoàn tất.")
        if kind not in EXPORTS:
            raise HTTPException(404, "Loại file xuất không hợp lệ.")
        path = store.root / "runs" / run_id / EXPORTS[kind]
        if not path.is_file():
            raise HTTPException(404, "Chưa có file kết quả.")
        return FileResponse(path, filename=f"aeolus_{run_id[:8]}_{path.name}")

    from web_dashboard.experiments import (ANALYSIS_VERSION, available_plans, experiment_results, export_experiment, load_plan,
        read_json, render_plan, snapshot_for, has_predictive_uncertainty)
    from web_dashboard.solver_execution import PROTOCOL_VERSION, version_for
    experiment_export_lock = threading.Lock()

    def get_experiment(eid):
        exp = store.experiment(eid)
        if not exp:
            raise HTTPException(404, 'Không tìm thấy thí nghiệm.')
        return exp

    @app.get('/api/runs/{run_id}/plans')
    def plans(run_id: str):
        run = get_run(run_id)
        if run['status'] != 'completed':
            return {'plans': [], 'ready': False, 'reason': 'Pipeline chưa hoàn tất.'}
        try:
            snapshot = snapshot_for(store, run_id)
            return {'plans': available_plans(store, run_id), 'ready': True,
                    'snapshot_hash': snapshot['hash'], 'has_arrivals': any(p.get('arrival_leg_id') for p in snapshot['pairing']),
                    'has_uncertainty':has_predictive_uncertainty(snapshot)}
        except ValueError as exc:
            return {'plans': [], 'ready': False, 'reason': str(exc)}

    @app.get('/api/runs/{run_id}/experiments')
    def experiments(run_id: str):
        get_run(run_id)
        return store.experiments(run_id)

    @app.post('/api/runs/{run_id}/experiments', status_code=202)
    def start_experiment(run_id: str, request: ExperimentRequest):
        get_run(run_id)
        try:
            snapshot = snapshot_for(store, run_id)
            config = request.model_dump(mode='json')
            config['snapshot_hash'] = snapshot['hash']
            config['solver_protocol_version'] = PROTOCOL_VERSION
            if request.kind == 'montecarlo':
                if not has_predictive_uncertainty(snapshot):
                    raise ValueError('Không có nguồn bất định dự báo đã xác minh để lấy mẫu Monte Carlo.')
                available = available_plans(store, run_id)
                selected = [p for p in available if p['id'] in request.plan_ids]
                if not selected or len(selected) != len(request.plan_ids):
                    raise ValueError('Chọn từ 1 đến 4 lịch ban đầu hợp lệ.')
                if len({p['algorithm'] for p in selected}) != len(selected):
                    raise ValueError('Chỉ chọn một lịch cho mỗi thuật toán để đối chiếu.')
                if any(p['snapshot_hash'] != snapshot['hash'] for p in selected):
                    raise ValueError('Các lịch không dùng cùng snapshot.')
                for p in selected:
                    load_plan(store, run_id, p['id'])
                config['plans'] = selected
                total = request.scenarios * len(selected) * 2
            else:
                total = len(request.algorithms) * (5 if request.mode == 'research' else 1)
            eid = store.create_experiment(run_id, config, total)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        if launch_jobs:
            runner.start(eid, experiment=True)
        return get_experiment(eid)

    @app.get('/api/experiments/{eid}')
    def experiment(eid: str):
        return get_experiment(eid)

    @app.get('/api/experiments/{eid}/results')
    def experiment_output(eid: str):
        exp = get_experiment(eid)
        path = store.root / 'experiments' / eid / 'results.json'
        if exp['status'] not in ('queued', 'running') and path.exists():
            cached = read_json(path)
            if cached.get('analysis_version') == version_for(exp) and cached['experiment']['completed'] == exp['completed'] and cached['experiment']['status'] == exp['status']:
                cached['experiment'] = exp
                return cached
        return experiment_results(store, eid)

    @app.get('/api/experiments/{eid}/plans/{plan_id}')
    def experiment_plan(eid: str, plan_id: str):
        get_experiment(eid)
        try:
            return render_plan(store, eid, plan_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get('/api/experiments/{eid}/cases/{case_id}')
    def experiment_case(eid: str, case_id: str):
        get_experiment(eid)
        case = next((c for c in store.cases(eid) if c['case_id'] == case_id), None)
        if not case:
            raise HTTPException(404, 'Không có lượt đánh giá này.')
        path = store.root / 'experiments' / eid / f'{case_id}.json'
        detail = read_json(path) if path.exists() else {}
        return {**case, 'trace': detail.get('trace'), 'diagnostic': detail.get('diagnostic')}

    @app.post('/api/experiments/{eid}/cancel')
    def cancel_experiment(eid: str):
        exp = get_experiment(eid)
        if exp['status'] not in ('queued', 'running'):
            raise HTTPException(409, 'Tác vụ không còn chạy.')
        store.experiment_update(eid, cancel_requested=1)
        return get_experiment(eid)

    @app.post('/api/experiments/{eid}/resume', status_code=202)
    def resume_experiment(eid: str):
        exp = get_experiment(eid)
        try:
            if exp['config'].get('solver_protocol_version') != PROTOCOL_VERSION:
                raise RuntimeError('Solver protocol changed; create a new experiment instead of mixing historical results.')
            snapshot_for(store, exp['run_id'])
            if exp['completed'] == exp['total']:
                raise RuntimeError('Mọi lượt đã được ghi nhận; tạo thí nghiệm mới nếu muốn chạy lại.')
            store.resume_experiment(eid)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        if launch_jobs:
            runner.start(eid, experiment=True)
        return get_experiment(eid)

    @app.get('/api/experiments/{eid}/exports/{kind}')
    def experiment_export(eid: str, kind: str):
        exp = get_experiment(eid)
        allowed = {'bundle': 'bundle.zip', 'manifest': 'manifest.json', 'cases.csv': 'cases.csv',
                   'cases.parquet': 'cases.parquet', 'results': 'results.json'}
        if kind not in allowed:
            raise HTTPException(404, 'Loại file không hợp lệ.')
        if exp['status'] in ('queued', 'running'):
            raise HTTPException(409, 'Đợi hoàn tất hoặc dừng thí nghiệm trước khi xuất.')
        path = store.root / 'experiments' / eid / allowed[kind]
        with experiment_export_lock:
            state_path = path.parent / '.export_state.json'
            expected = {'analysis_version': version_for(exp), 'completed': exp['completed'], 'status': exp['status']}
            if not path.exists() or not state_path.exists() or read_json(state_path) != expected:
                export_experiment(store, eid)
        return FileResponse(path, filename=f'aeolus_{eid[:8]}_{path.name}')

    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def frontend():
        if not (DIST / "index.html").is_file():
            return JSONResponse({"detail": "Chưa build frontend. Chạy npm ci và npm run build trong web_dashboard/frontend."}, status_code=503)
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
