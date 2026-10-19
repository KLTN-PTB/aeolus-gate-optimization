"""Small persistent local store; runtime state never touches research artifacts."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
                    stage TEXT NOT NULL, error TEXT, config TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments(
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL, error TEXT, config TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS experiment_cases(
                    experiment_id TEXT NOT NULL, case_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(experiment_id, case_id));
            """)

    def connect(self):
        db = sqlite3.connect(self.root / "dashboard.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def put_dataset(self, dataset_id: str, report: dict):
        with self.connect() as db:
            db.execute("INSERT INTO datasets VALUES (?, ?)", (dataset_id, json.dumps(report, ensure_ascii=False)))

    def dataset(self, dataset_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def create_run(self, config: dict):
        with self.connect() as db:
            # Serialize admission across browser sessions and concurrent requests.
            db.execute("BEGIN IMMEDIATE")
            if self.busy(db):
                raise RuntimeError("Đang có tác vụ chạy. Vui lòng đợi tác vụ hoàn tất.")
            run_id = uuid4().hex
            db.execute("INSERT INTO runs VALUES (?, ?, 'queued', 'validation', NULL, ?)",
                       (run_id, datetime.now(timezone.utc).isoformat(), json.dumps(config)))
        return run_id

    def update(self, run_id: str, *, status: str, stage: str, error: str | None = None):
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?,stage=?,error=? WHERE id=?", (status, stage, error, run_id))

    def run(self, run_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["config"] = json.loads(result["config"])
        return result

    def runs(self):
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT 50")]
        return [self.run(run_id) for run_id in ids]

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE runs SET status='interrupted', error='Ứng dụng đã khởi động lại; hãy chạy lại tác vụ.' "
                       "WHERE status IN ('queued','running')")
            db.execute("UPDATE experiments SET status='interrupted', stage='interrupted' WHERE status IN ('queued','running')")

    @staticmethod
    def busy(db):
        return (db.execute("SELECT 1 FROM runs WHERE status IN ('queued','running')").fetchone()
                or db.execute("SELECT 1 FROM experiments WHERE status IN ('queued','running')").fetchone())

    def experiment(self, experiment_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['config'] = json.loads(result['config'])
        return result

    def experiments(self, run_id):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM experiments WHERE run_id=? ORDER BY created_at DESC", (run_id,))]
        return [self.experiment(i) for i in ids]

    def create_experiment(self, run_id, config, total):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.busy(db):
                raise RuntimeError('Đang có tác vụ tính toán. Vui lòng đợi hoặc dừng tác vụ đó.')
            eid = uuid4().hex
            db.execute("INSERT INTO experiments VALUES (?, ?, ?, 'queued', 'preparation', NULL, ?, 0, ?, 0)",
                       (eid, run_id, datetime.now(timezone.utc).isoformat(), json.dumps(config), total))
        return eid

    def experiment_update(self, eid, **values):
        allowed = {'status', 'stage', 'error', 'completed', 'cancel_requested'}
        if not values or not set(values) <= allowed:
            raise ValueError('Invalid experiment fields')
        with self.connect() as db:
            db.execute('UPDATE experiments SET ' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?', (*values.values(), eid))

    def resume_experiment(self, eid):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status FROM experiments WHERE id=?', (eid,)).fetchone()
            if not row or row[0] not in ('cancelled', 'interrupted', 'failed', 'partial'):
                raise RuntimeError('Chỉ tiếp tục tác vụ bị hủy, gián đoạn hoặc chưa hoàn tất.')
            if self.busy(db):
                raise RuntimeError('Đang có tác vụ tính toán khác.')
            db.execute("UPDATE experiments SET status='queued',cancel_requested=0,error=NULL WHERE id=?", (eid,))

    def cases(self, eid):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT payload FROM experiment_cases WHERE experiment_id=? ORDER BY case_id', (eid,))]

    def put_case(self, eid, case):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO experiment_cases VALUES (?, ?, ?)', (eid, case['case_id'], json.dumps(case, allow_nan=False)))
            db.execute('UPDATE experiments SET completed=(SELECT COUNT(*) FROM experiment_cases WHERE experiment_id=?) WHERE id=?', (eid, eid))
