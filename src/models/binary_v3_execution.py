"""Isolated, wall-clock-budgeted V3 experiment. Frozen V2 artifacts are read only."""
from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import importlib.metadata

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import psutil
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
import xgboost as xgb
import yaml

from src.features.binary_improvement_v3 import NativeScheduleEncoder, VERSION
from src.models.binary_improvement import binary_metrics, positive_probability, promotion_gate
from src.models.binary_improvement_execution import (Experiment, DeadlineCallback, FitIncomplete,
    digest, prevent_sleep)
from src.models.binary_improvement_v3 import (V3Bundle, choose_calibration,
    fixed_precision_threshold, absolute_gate, bootstrap_with_f1)
from src.models.binary_v3_protocol import BoundedData, Roles, roles_for, cache_key, train_window, warmup_indices

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ("xgboost", "hgb", "lightgbm")
EXPECTED_TARGETS = {
    "arrival": {"ap_min": .26620877341450533, "roc_min": .6580215998888602,
        "brier_max": .12630304139437235, "f1_min": .35030526755047664,
        "precision_min": .2520176356299507},
    "departure": {"ap_min": .3207038054844584, "roc_min": .6621305285107107,
        "brier_max": .14042784768846178, "f1_min": .3795574887830942,
        "precision_min": .30965127426202366},
}


def write_json(path, payload):
    """Atomic metadata replacement, tolerating short Windows read/index locks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False,
        default=lambda value: value.item() if isinstance(value, np.generic) else str(value)), encoding="utf-8")
    for attempt in range(61):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 60:
                raise
            time.sleep(.05)


def eligible_primary(records, task, seed=202601):
    """Retraining controls and HPO challengers face identical absolute gates."""
    return [record for record in records.values() if record["task"] == task and record["seed"] == seed]


class V3Experiment(Experiment):
    def __init__(self, config, output, *, smoke=False):
        super().__init__(config, output, smoke=smoke)
        self.final_fit_deadline = self.started + config["budget"]["final_fit_cutoff_hours"] * 3600
        self.v2 = ROOT / config["baseline_run"]
        self.data = BoundedData(ROOT, self.v2, smoke=smoke, cache_root=output / "data_cache")
        self.matrices = OrderedDict()
        self.control_cache = {}
        self.summary.update(protocol=VERSION, jobs={}, tasks={}, smoke=smoke)
        self.targets = {}
        for task in config["tasks"]:
            path = self.v2 / task / "xgboost_baseline_metrics.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            m = record["q4_selected_threshold"]
            self.targets[task] = {"ap_min": m["ap"] + .005, "roc_min": m["roc_auc"] - .005,
                "brier_max": m["brier_score"] * 1.02, "f1_min": m["f1"] + .02,
                "precision_min": record["threshold_selection"]["precision_floor"],
                "baseline_metrics_sha256": digest(path)}
            if any(self.targets[task][key] != value for key, value in EXPECTED_TARGETS[task].items()):
                raise ValueError("V2 absolute acceptance targets changed; refusing a weaker baseline")
        self.summary["absolute_targets"] = self.targets
        self.shortlists = {}

    def event(self, stage, **details):
        record = {"at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - self.started, 3), "stage": stage, **details}
        print(json.dumps(record, default=str), flush=True)
        try:
            with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, default=str) + "\n")
        except PermissionError:
            write_json(self.output / "event_fallback" / f"{time.time_ns()}.json", record)
        try:
            write_json(self.output / "progress.json", record)
        except PermissionError:
            print("Progress display is temporarily locked; training evidence remains in events.jsonl", flush=True)

    def checkpoint(self):
        self.summary["elapsed_seconds"] = time.monotonic() - self.started
        self.summary["observed_rss_mb"] = psutil.Process().memory_info().rss / 1024 ** 2
        write_json(self.output / "summary.json", self.summary)
        write_json(self.output / "data_sources.json", self.data.audit)

    def matrix(self, task, branch, quarter, spec, *, full=False, final=False):
        key = cache_key({"task": task, "branch": branch, "quarter": quarter,
            "group": spec["group"], "window": spec["window"], "full": full, "final": final,
            "smoke": self.smoke, "config": self.config})
        if key in self.matrices:
            self.matrices.move_to_end(key)
            return self.matrices[key]
        cache = self.output / "matrix_cache" / (key + ".joblib")
        if cache.exists():
            value = joblib.load(cache)
        else:
            roles = roles_for(branch, quarter)
            train = self.data.read(task, train_window(roles.train_end, spec["window"]), roles.train_end)
            encoder = NativeScheduleEncoder(task, spec["group"])
            self.event("encoding_started", task=task, branch=branch, quarter=quarter,
                       group=spec["group"], window=spec["window"], full=full, train_rows=len(train))
            encoded = encoder.fit_transform(train, train["__target"].to_numpy())
            cap = (1800 if self.smoke else self.config["budget"]["screening_train_cap"]) if not full else (4000 if self.smoke else None)
            indices = warmup_indices(train, days=self.config["selection"]["warmup_days"], cap=cap, seed=self.config["seed"])
            if len(indices) < 50:
                raise ValueError("Too few training rows after warmup")
            train_matrix = encoded.iloc[indices].reset_index(drop=True) if isinstance(encoded, pd.DataFrame) else encoded[indices]
            value = {"encoder": encoder, "train": train_matrix,
                "y": train.iloc[indices]["__target"].to_numpy(),
                "dates": train.iloc[indices]["__date"].to_numpy(),
                "carriers": train.iloc[indices].OP_CARRIER.to_numpy(), "parts": {},
                "train_rows": len(indices), "history_rows": len(train),
                "train_start": str(train["__date"].min()), "train_end": str(roles.train_end)}
            for role, (start, end) in roles.ranges().items():
                if final and role == "score":
                    continue
                frame = self.data.read(task, start, end)
                value["parts"][role] = {"data": encoder.transform(frame),
                    "y": frame["__target"].to_numpy(), "dates": frame["__date"].to_numpy(),
                    "keys": frame["__key"].to_numpy(), "carriers": frame.OP_CARRIER.to_numpy()}
            cache.parent.mkdir(exist_ok=True, parents=True)
            joblib.dump(value, cache)
        self.matrices[key] = value
        while len(self.matrices) > self.config["budget"]["matrix_cache_entries"]:
            self.matrices.popitem(last=False)
        return value

    def fit_model(self, family, params, matrix, spec, *, seed, deadline, subset=None):
        self.check_time(deadline)
        deadline = min(deadline, self.deadline, time.monotonic() + self.config["budget"]["fit_timeout_seconds"])
        a, y, dates = matrix["train"], matrix["y"], matrix["dates"]
        if subset is not None:
            a = a.loc[subset] if isinstance(a, pd.DataFrame) else a[subset]
            y, dates = y[subset], dates[subset]
        weights = np.ones(len(y))
        if spec["half_life"]:
            age = (pd.Timestamp(matrix["train_end"]) - pd.to_datetime(dates)).days.to_numpy()
            weights *= np.exp2(-age / spec["half_life"])
            weights /= weights.mean()
        ratio = float(np.sum(y == 0) / max(1, np.sum(y == 1)))
        multiplier = {"none": 1., "sqrt": np.sqrt(ratio), "balanced": ratio}[spec.get("weight", "none")]
        weights *= np.where(y == 1, multiplier, 1.)
        native = isinstance(a, pd.DataFrame)
        params = dict(params)
        if family == "xgboost":
            callback = DeadlineCallback(deadline)
            model = xgb.XGBClassifier(**params, objective="binary:logistic", eval_metric="aucpr",
                enable_categorical=native, tree_method="hist", device=self.device,
                n_jobs=self.config["budget"]["threads"], random_state=seed, callbacks=[callback])
            try:
                model.fit(a, y, sample_weight=weights, verbose=False)
            except xgb.core.XGBoostError as exc:
                if self.device != "cuda":
                    raise
                self.event("cuda_fit_failed", reason=str(exc))
                self.device = "cpu"
                return self.fit_model(family, params, matrix, spec, seed=seed, deadline=deadline, subset=subset)
            if callback.expired:
                raise FitIncomplete("Deadline-stopped XGBoost is not a complete candidate")
            model.set_params(callbacks=None)
        elif family == "lightgbm":
            def check_deadline(env):
                self.check_time(deadline)
            model = lgb.LGBMClassifier(**params, objective="binary", verbosity=-1, force_col_wise=True,
                n_jobs=self.config["budget"]["threads"], random_state=seed)
            model.fit(a, y, sample_weight=weights, callbacks=[check_deadline])
        else:
            maximum = int(params.pop("max_iter"))
            model = HistGradientBoostingClassifier(**params, max_iter=min(25, maximum),
                early_stopping=False, warm_start=True, categorical_features="from_dtype" if native else None,
                random_state=seed)
            for count in range(25, maximum + 25, 25):
                self.check_time(deadline)
                model.set_params(max_iter=min(count, maximum))
                model.fit(a, y, sample_weight=weights)
            model.set_params(warm_start=False)
        self.check_time(deadline)
        return model

    @staticmethod
    def spec_id(spec):
        return spec["family"] + "_" + spec["group"] + "_" + cache_key(spec)[:10]

    def raw_fit(self, task, branch, quarter, spec, *, full, deadline, seed=None, final=False, expert=False):
        matrix = self.matrix(task, branch, quarter, spec, full=full, final=final)
        self.check_time(deadline)
        start = time.monotonic()
        model = self.fit_model(spec["family"], spec["params"], matrix, spec,
                               seed=seed or self.seed, deadline=deadline)
        bundle = V3Bundle(matrix["encoder"], model, alpha=spec.get("alpha", 0.), metadata={
            "protocol": VERSION, "task": task, "branch": branch, "quarter": quarter, "spec": spec,
            "seed": seed or self.seed, "cutoff_hours": 2, "delay_minutes": 15,
            "train_start": matrix["train_start"], "train_end": matrix["train_end"],
            "train_rows": matrix["train_rows"], "history_rows": matrix["history_rows"],
            "smoke": self.smoke, "untouched_test_available": False})
        if expert or bundle.alpha:
            mask = matrix["carriers"] == "DL"
            if mask.sum() >= 1000 and matrix["y"][mask].sum() >= 100:
                bundle.expert = self.fit_model(spec["family"], spec["params"], matrix, spec,
                    seed=seed or self.seed, deadline=deadline, subset=mask)
            elif bundle.alpha:
                raise ValueError("DL expert insufficient training support")
        raw = {}
        for role, part in matrix["parts"].items():
            p = positive_probability(model, part["data"])
            expert_p = p.copy()
            mask = part["carriers"] == "DL"
            if bundle.expert is not None and mask.any():
                data = part["data"].loc[mask] if isinstance(part["data"], pd.DataFrame) else part["data"][mask]
                expert_p[mask] = positive_probability(bundle.expert, data)
            raw[role] = {"global": p, "expert": expert_p}
        return bundle, matrix, raw, time.monotonic() - start

    def postprocess(self, bundle, matrix, raw, *, final=False):
        scores = {role: (1 - bundle.alpha) * p["global"] + bundle.alpha * p["expert"] for role, p in raw.items()}
        def inputs(role):
            p = matrix["parts"][role]
            return scores[role], p["y"], p["carriers"]
        bundle.calibrator, calibration = choose_calibration(inputs("calibration"), inputs("selection"), self.config["selection"])
        threshold_part = matrix["parts"]["threshold"]
        p = bundle.calibrator.transform(scores["threshold"], threshold_part["carriers"])
        floor = self.targets[bundle.metadata["task"]]["precision_min"] if final else float(threshold_part["y"].mean() * self.config["selection"]["precision_multiplier_internal"])
        threshold = fixed_precision_threshold(threshold_part["y"], p, floor)
        bundle.threshold = threshold["threshold"]
        bundle.metadata.update(threshold_selection=threshold, calibration=calibration,
            temporal_roles={name: [str(v) for v in bounds] for name, bounds in roles_for(bundle.metadata["branch"], bundle.metadata["quarter"]).ranges().items()})
        record = {"spec": bundle.metadata["spec"], "threshold_selection": threshold,
                  "calibration": calibration, "train_rows": matrix["train_rows"]}
        if "score" in scores:
            part = matrix["parts"]["score"]
            p = bundle.calibrator.transform(scores["score"], part["carriers"])
            record.update(metrics=binary_metrics(part["y"], p, bundle.threshold),
                at_0_5=binary_metrics(part["y"], p), raw_metrics=binary_metrics(part["y"], scores["score"]),
                groups={str(group): binary_metrics(part["y"][part["carriers"] == group], p[part["carriers"] == group], bundle.threshold)
                        for group in np.unique(part["carriers"])})
        return record

    def evaluate(self, task, branch, quarter, spec, *, full, deadline):
        bundle, matrix, raw, seconds = self.raw_fit(task, branch, quarter, spec, full=full, deadline=deadline)
        record = self.postprocess(bundle, matrix, raw)
        record.update(quarter=quarter, seconds=seconds, status="COMPLETE")
        if full:
            part = matrix["parts"]["score"]
            raw_p = (1 - bundle.alpha) * raw["score"]["global"] + bundle.alpha * raw["score"]["expert"]
            p = bundle.calibrator.transform(raw_p, part["carriers"])
            path = self.output / "fold_predictions" / f"{task}_{branch}_{quarter}_{self.spec_id(spec)}.parquet"
            path.parent.mkdir(exist_ok=True)
            pd.DataFrame({"flight_key": part["keys"], "flight_date": part["dates"], "y_true": part["y"],
                "raw_probability": raw_p, "probability": p, "threshold": bundle.threshold,
                "carrier": part["carriers"]}).to_parquet(path, index=False)
            record["predictions"] = str(path.relative_to(self.output))
        return record

    def baseline(self, task, branch, quarter, *, full, deadline):
        key = (task, branch, quarter, full)
        if key not in self.control_cache:
            record = self.evaluate(task, branch, quarter, baseline_spec(), full=full, deadline=deadline)
            self.control_cache[key] = record
            write_json(self.output / "controls" / f"{task}_{branch}_{quarter}_{'full' if full else 'screen'}.json", record)
        return self.control_cache[key]

    def compare(self, record, baseline):
        gate = promotion_gate(record["metrics"], baseline["metrics"], record["threshold_selection"])
        record["relative_gate"] = gate
        record["ap_delta"] = record["metrics"]["ap"] - baseline["metrics"]["ap"]
        record["f1_delta"] = record["metrics"]["f1"] - baseline["metrics"]["f1"]
        return record

    @staticmethod
    def rank(records):
        count = sum(record["relative_gate"]["passed"] for record in records)
        guards = sum(record["relative_gate"]["checks"].get(name, False) for record in records
                     for name in ("roc_noninferiority", "brier_guard", "precision_floor", "threshold_feasible"))
        ap = float(np.mean([record["ap_delta"] for record in records]))
        f1 = float(np.mean([record["f1_delta"] for record in records]))
        return (count * 100 + guards, min(ap / .005, f1 / .02), ap, f1)

    def suggest(self, trial, family):
        spec = {"family": family, "group": trial.suggest_categorical("group", ["original", "native", "history"]),
            "window": trial.suggest_categorical("window", [0, 2, 3]),
            "half_life": trial.suggest_categorical("half_life", [0, 365]),
            "weight": trial.suggest_categorical("weight", ["none", "sqrt", "balanced"]), "alpha": 0.}
        if family == "xgboost":
            params = {"n_estimators": trial.suggest_categorical("n_estimators", [100, 300, 600, 1200]),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "learning_rate": trial.suggest_float("learning_rate", .02, .15, log=True),
                "min_child_weight": trial.suggest_float("min_child_weight", 1, 30, log=True),
                "subsample": trial.suggest_float("subsample", .65, 1),
                "colsample_bytree": trial.suggest_float("colsample_bytree", .65, 1),
                "reg_alpha": trial.suggest_float("reg_alpha", .001, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", .1, 30, log=True)}
        elif family == "lightgbm":
            params = {"n_estimators": trial.suggest_categorical("n_estimators", [100, 300, 600, 1200]),
                "num_leaves": trial.suggest_categorical("num_leaves", [15, 31, 63]),
                "learning_rate": trial.suggest_float("learning_rate", .02, .15, log=True),
                "min_child_samples": trial.suggest_int("min_child_samples", 30, 150),
                "colsample_bytree": trial.suggest_float("colsample_bytree", .65, 1),
                "reg_lambda": trial.suggest_float("reg_lambda", .1, 30, log=True), "cat_smooth": 20}
        else:
            params = {"max_iter": trial.suggest_categorical("max_iter", [100, 200, 300, 500]),
                "max_leaf_nodes": trial.suggest_categorical("max_leaf_nodes", [15, 31, 63]),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "learning_rate": trial.suggest_float("learning_rate", .02, .15, log=True),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 30, 150),
                "l2_regularization": trial.suggest_float("l2_regularization", .001, 10, log=True)}
        if self.smoke:
            params["max_iter" if family == "hgb" else "n_estimators"] = 25
        spec["params"] = params
        return spec

    def screen_job(self, task, branch, job_deadline):
        controls = {q: self.baseline(task, branch, q, full=False, deadline=job_deadline) for q in self.config["development_quarters"]}
        candidates = []
        for family in FAMILIES:
            study = optuna.create_study(directions=["maximize", "maximize"],
                sampler=optuna.samplers.TPESampler(seed=self.seed, n_startup_trials=6,
                    constraints_func=lambda trial: trial.user_attrs.get("constraints", [1.] * 8)),
                storage=f"sqlite:///{(self.output / f'{task}_{branch}_{family}.sqlite3').as_posix()}",
                study_name=f"{VERSION}_{task}_{branch}_{family}")
            for group in ("original", "native", "history"):
                study.enqueue_trial({"group": group, "window": 0, "half_life": 0, "weight": "none"})
            def objective(trial):
                self.check_time(job_deadline)
                spec = self.suggest(trial, family)
                records = [self.compare(self.evaluate(task, branch, q, spec, full=False, deadline=job_deadline), controls[q])
                           for q in self.config["development_quarters"]]
                trial.set_user_attr("spec", spec)
                trial.set_user_attr("records", records)
                trial.set_user_attr("rank", self.rank(records))
                violations = []
                for record, quarter in zip(records, self.config["development_quarters"]):
                    m, b = record["metrics"], controls[quarter]["metrics"]
                    violations.extend([b["roc_auc"] - .005 - m["roc_auc"],
                        m["brier_score"] - b["brier_score"] * 1.02,
                        record["threshold_selection"]["precision_floor"] - m["precision"],
                        0. if record["threshold_selection"]["status"] == "SELECTED" else 1.])
                trial.set_user_attr("constraints", violations)
                self.event("trial_complete", task=task, branch=branch, family=family, trial=trial.number,
                    ap_delta=self.rank(records)[2], f1_delta=self.rank(records)[3], group=spec["group"])
                return self.rank(records)[2:]
            count = 3 if self.smoke else self.config["budget"]["trials"][family]
            for _ in range(count):
                if time.monotonic() >= job_deadline:
                    break
                study.optimize(objective, n_trials=1, catch=(FitIncomplete, ValueError, xgb.core.XGBoostError, lgb.basic.LightGBMError))
            complete = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
            for trial in complete:
                candidates.append({"spec": trial.user_attrs["spec"], "records": trial.user_attrs["records"],
                    "rank": trial.user_attrs["rank"], "trial": trial.number, "family": family})
            write_json(self.output / "screening" / f"{task}_{branch}_{family}.json", {
                "requested": count, "complete": len(complete), "records": [c for c in candidates if c["family"] == family]})
        # Pareto candidates plus ranked fallbacks; do not discard F1 winners for AP alone.
        candidates.sort(key=lambda c: tuple(c["rank"]), reverse=True)
        # Keep family diversity when possible.
        winners = []
        for family in FAMILIES:
            values = [c for c in candidates if c["family"] == family]
            if values:
                winners.append(values[0])
        winners.sort(key=lambda c: tuple(c["rank"]), reverse=True)
        self.summary["jobs"][task + "_" + branch] = {"screen_trials_complete": len(candidates), "status": "SCREENED"}
        self.checkpoint()
        return [c["spec"] for c in winners[:self.config["selection"]["verify_per_job"]]]

    def verify_job(self, task, branch, specs):
        controls = {q: self.baseline(task, branch, q, full=True, deadline=self.verify_deadline)
                    for q in self.config["verification_quarters"]}
        verified = []
        for spec in specs:
            records = []
            try:
                for quarter in self.config["verification_quarters"]:
                    record = self.compare(self.evaluate(task, branch, quarter, spec, full=True, deadline=self.verify_deadline), controls[quarter])
                    records.append(record)
                    self.event("full_fold_complete", task=task, branch=branch, model=self.spec_id(spec), quarter=quarter,
                        ap=record["metrics"]["ap"], f1=record["metrics"]["f1"])
                verified.append({"spec": spec, "records": records, "rank": self.rank(records)})
                status = "COMPLETE"
            except FitIncomplete:
                status = "INCOMPLETE"
            write_json(self.output / "verification" / f"{task}_{branch}_{self.spec_id(spec)}.json", {"status": status, "spec": spec, "records": records})
        if verified:
            best = max(verified, key=lambda c: c["rank"])
            try:
                expert_records = {alpha: [] for alpha in self.config["selection"]["expert_alphas"]}
                for quarter in self.config["verification_quarters"]:
                    bundle, matrix, raw, seconds = self.raw_fit(task, branch, quarter, best["spec"], full=True,
                        deadline=self.verify_deadline, expert=True)
                    if bundle.expert is None:
                        raise ValueError("DL support below expert gate")
                    for alpha in expert_records:
                        bundle.alpha = alpha
                        spec = {**best["spec"], "alpha": alpha}
                        bundle.metadata["spec"] = spec
                        record = self.compare(self.postprocess(bundle, matrix, raw), controls[quarter])
                        record.update(quarter=quarter, seconds=seconds)
                        expert_records[alpha].append(record)
                for alpha, records in expert_records.items():
                    spec = {**best["spec"], "alpha": alpha}
                    verified.append({"spec": spec, "records": records, "rank": self.rank(records)})
                    write_json(self.output / "verification" / f"{task}_{branch}_{self.spec_id(spec)}.json",
                        {"status": "COMPLETE", "spec": spec, "records": records, "role": "DL_expert_challenger"})
            except (FitIncomplete, ValueError) as exc:
                self.event("expert_incomplete", task=task, branch=branch, reason=str(exc))
        verified.sort(key=lambda c: c["rank"], reverse=True)
        if not verified:
            raise FitIncomplete("No fully verified candidate")
        chosen = [v["spec"] for v in verified[:self.config["selection"]["finalists_per_job"]]]
        self.summary["jobs"][task + "_" + branch].update(status="VERIFIED", finalists=chosen)
        self.checkpoint()
        return chosen

    def final_models(self):
        records = {}
        for task in self.config["tasks"]:
            for branch in self.config["branches"]:
                specs = [("control", baseline_spec())] + [(self.spec_id(s), s) for s in self.shortlists[(task, branch)]]
                for name, spec in specs:
                    seeds = [self.config["seed"]] if self.smoke else [self.config["seed"], *self.config["stability_seeds"]]
                    for seed in seeds:
                        self.check_time(self.final_fit_deadline)
                        bundle, matrix, raw, seconds = self.raw_fit(task, branch, self.config["target_quarter"], spec,
                            full=True, deadline=self.final_fit_deadline, seed=seed, final=True)
                        record = self.postprocess(bundle, matrix, raw, final=True)
                        identifier = f"{task}_{branch}_{name}_s{seed}"
                        bundle.metadata.update(model_id=identifier, role="matched_control" if name == "control" else "research_candidate")
                        bundle.to_cpu()
                        path = self.output / "models" / (identifier + ".joblib")
                        path.parent.mkdir(exist_ok=True)
                        joblib.dump(bundle, path, compress=3)
                        sample = self.data.read(task, *roles_for(branch, self.config["target_quarter"]).threshold).iloc[:16]
                        sample_path = self.output / "reload_sample.parquet"
                        sample.to_parquet(sample_path, index=False)
                        expected = bundle.predict_proba(sample)
                        prediction_path = self.output / "reload.npy"
                        code = "import sys,joblib,pandas as pd,numpy as np; m=joblib.load(sys.argv[1]); np.save(sys.argv[3],m.predict_proba(pd.read_parquet(sys.argv[2])))"
                        child = subprocess.run([sys.executable, "-c", code, str(path), str(sample_path), str(prediction_path)],
                                               cwd=ROOT, capture_output=True, text=True, timeout=120)
                        if child.returncode:
                            raise RuntimeError("Fresh CPU reload failed: " + child.stderr)
                        np.testing.assert_allclose(np.load(prediction_path), expected, atol=1e-7, rtol=1e-6)
                        records[identifier] = {**record, "id": identifier, "task": task, "branch": branch,
                            "seed": seed, "role": bundle.metadata["role"], "path": str(path.relative_to(self.output)),
                            "sha256": digest(path), "cpu_reload": "PASS", "fit_seconds": seconds,
                            "threshold": bundle.threshold, "spec": spec}
                        self.event("final_model_frozen", task=task, branch=branch, model=identifier,
                            seed=seed, threshold=bundle.threshold, seconds=seconds)
                        write_json(self.output / "final_models_in_progress.json", records)
        if not records:
            raise FitIncomplete("No final portable model was completed")
        write_json(self.output / "selection_freeze.json", {"status": "FROZEN_BEFORE_Q4",
            "at": datetime.now(timezone.utc).isoformat(), "models": records, "absolute_targets": self.targets})
        return records

    def score_final(self, records):
        self.data.unlock_q4(self.output / "selection_freeze.json")
        for task in self.config["tasks"]:
            roles = roles_for("A", self.config["target_quarter"])
            frame = self.data.read(task, *roles.score, purpose="final")
            original = pd.read_parquet(self.v2 / task / "xgboost_baseline_2022.parquet")
            original = original.loc[pd.to_datetime(original["__date"]).dt.quarter.eq(4)]
            joined = frame[["__key", "__target"]].merge(original[["__key", "__target", "probability", "threshold"]],
                on="__key", validate="one_to_one", suffixes=("", "_v2"), how="left")
            if not self.smoke and len(frame) != len(original):
                raise ValueError("Full Q4 evaluation must retain every V2-eligible flight")
            if joined.probability.isna().any() or not np.array_equal(joined["__target"], joined["__target_v2"]):
                raise ValueError("Frozen V2/Q4 populations or labels disagree")
            y = frame["__target"].to_numpy()
            predictions = frame[["__key", "__date", "__target"]].copy()
            predictions["frozen_v2"] = joined.probability.to_numpy()
            for identifier, record in records.items():
                if record["task"] != task:
                    continue
                self.check_time()
                if digest(self.output / record["path"]) != record["sha256"]:
                    raise ValueError("Model changed after pre-Q4 freeze")
                model = joblib.load(self.output / record["path"])
                start = time.monotonic()
                p = model.predict_proba(frame)[:, 1]
                metrics = binary_metrics(y, p, model.threshold)
                gate = absolute_gate(metrics, self.targets[task], record["threshold_selection"])
                if self.smoke:
                    gate["passed"] = False
                    gate["smoke_not_eligible"] = True
                record["q4"] = {"metrics": metrics, "at_0_5": binary_metrics(y, p),
                    "gate": gate, "inference_seconds": time.monotonic() - start,
                    "groups": self.group_metrics(frame, y, p, model.threshold)}
                predictions[identifier] = p
                self.event("q4_scored", model=identifier, passed=gate["passed"], ap=metrics["ap"], f1=metrics["f1"])
            path = self.output / "predictions" / (task + "_q4.parquet")
            path.parent.mkdir(exist_ok=True)
            predictions.to_parquet(path, index=False)
            # Statistical evidence is attached after model/threshold freeze and never drives a new fit.
            for identifier, record in records.items():
                if record["task"] != task or record["seed"] != self.config["seed"]:
                    continue
                self.check_time()
                record["q4"]["uncertainty"] = bootstrap_with_f1(frame["__date"], y,
                    predictions[identifier].to_numpy(), joined.probability.to_numpy(), record["threshold"],
                    float(joined.threshold.iloc[0]), iterations=20 if self.smoke else self.config["selection"]["bootstrap_iterations"], seed=self.config["seed"])
        decisions = {}
        for task in self.config["tasks"]:
            primary = eligible_primary(records, task, self.config["seed"])
            for record in primary:
                related = [r for r in records.values() if r["task"] == task and r["branch"] == record["branch"] and r["spec"] == record["spec"]]
                record["seed_stability"] = {str(r["seed"]): r["q4"]["gate"]["passed"] for r in related}
                record["all_seeds_pass"] = all(record["seed_stability"].values()) and (len(related) == 3 if not self.smoke else False)
            passed = [r for r in primary if r["q4"]["gate"]["passed"]]
            if passed:
                best_ap = max(r["q4"]["metrics"]["ap"] for r in passed)
                tied = [r for r in passed if r["q4"]["metrics"]["ap"] >= best_ap - .005]
                winner = min(tied, key=lambda r: (r["q4"]["metrics"]["brier_score"], r["q4"]["inference_seconds"]))
                decisions[task] = {"status": "Q4_PASS", "model_id": winner["id"],
                    "winner_role": winner["role"],
                    "all_seeds_pass": winner["all_seeds_pass"],
                    "uncertainty": winner["q4"].get("uncertainty"), "historical_development_only": True}
            else:
                decisions[task] = {"status": "NO_Q4_PASS", "model_id": None,
                    "reason": "No primary-seed model passed every unchanged V2 target"}
        write_json(self.output / "q4_decision_freeze.json", {"status": "FROZEN_Q4_DECISION",
            "at": datetime.now(timezone.utc).isoformat(), "tasks": decisions})
        write_json(self.output / "model_results.json", records)
        return decisions

    @staticmethod
    def group_metrics(frame, y, p, threshold):
        result = {}
        route = "ORIGIN" if "ORIGIN" in frame else "DEST"
        for name, labels in [("month", frame["__date"].dt.month), ("carrier", frame.OP_CARRIER), ("route", frame[route])]:
            result[name] = {str(group): binary_metrics(y[indices], p[indices], threshold)
                            for group, indices in frame.groupby(labels, dropna=False).indices.items()}
        return result

    def confirmation(self, records, decisions):
        freeze = json.loads((self.output / "q4_decision_freeze.json").read_text())
        if freeze["status"] != "FROZEN_Q4_DECISION":
            raise PermissionError("Historical confirmation requires a Q4 decision")
        self.data.confirmation_unlocked = True
        for task in self.config["tasks"]:
            frame = self.data.read(task, "2023-01-01", "2023-12-31", purpose="confirmation")
            y = frame["__target"].to_numpy()
            predictions = frame[["__key", "__date", "__target"]].copy()
            for identifier, record in records.items():
                if record["task"] != task or record["seed"] != self.config["seed"]:
                    continue
                self.check_time()
                if digest(self.output / record["path"]) != record["sha256"]:
                    raise ValueError("Model changed after Q4 decision")
                model = joblib.load(self.output / record["path"])
                p = model.predict_proba(frame)[:, 1]
                record["historical_2023"] = {"metrics": binary_metrics(y, p, model.threshold),
                    "at_0_5": binary_metrics(y, p), "groups": self.group_metrics(frame, y, p, model.threshold),
                    "role": "historical_confirmation_no_retuning_or_reselection"}
                predictions[identifier] = p
            predictions.to_parquet(self.output / "predictions" / (task + "_2023.parquet"), index=False)
            self.event("historical_confirmation_complete", task=task, rows=len(frame), decision=decisions[task]["status"])
        write_json(self.output / "model_results.json", records)

    def diagnostic_experiments(self, task, branch, best):
        # Matched rows/hyperparameters: only representation changes.
        ablation = []
        try:
            for group in ("original", "native", "history"):
                spec = {**best, "group": group, "alpha": 0.}
                value = self.evaluate(task, branch, "2021Q4", spec, full=True, deadline=self.verify_deadline)
                ablation.append(value)
            stress = self.evaluate(task, branch, self.config["stress_quarter"], best, full=True, deadline=self.verify_deadline)
            write_json(self.output / "diagnostics" / f"{task}_{branch}.json", {
                "status": "COMPLETE", "matched_ablation": ablation,
                "fixed_parameters": best["params"], "stress_only_excluded_from_hpo": stress})
        except FitIncomplete as exc:
            write_json(self.output / "diagnostics" / f"{task}_{branch}.json", {"status": "INCOMPLETE", "reason": str(exc), "matched_ablation": ablation})

    def report(self, records=None, decisions=None):
        records, decisions = records or {}, decisions or {}
        lines = ["# Kết quả Binary Improvement V3", "", f"Trạng thái thực thi: **{self.summary['status']}**.", "",
            "Giữ T-2h, nhãn trễ ≥15 phút và mọi mốc nghiệm thu V2. Quý IV/2022 và năm 2023 là dữ liệu phát triển lịch sử đã từng xem.",
            "Không truy cập năm 2024. Model được lưu riêng; dashboard và optimizer chưa thay đổi.", "",
            "| Bài toán | Model | Nhánh | AP Q4 | ROC Q4 | Brier Q4 | Precision | Recall | F1 | Ngưỡng | Đạt đủ |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
        for identifier, record in records.items():
            if record["seed"] != self.config["seed"] or "q4" not in record:
                continue
            m = record["q4"]["metrics"]
            fields = " | ".join(f"{m[k]:.5f}" for k in ("ap", "roc_auc", "brier_score", "precision", "recall", "f1", "threshold"))
            lines.append(f"| {record['task']} | {identifier} | {record['branch']} | {fields} | {record['q4']['gate']['passed']} |")
        lines.extend(["", "## Quyết định đã khóa", ""])
        for task, decision in decisions.items():
            lines.append(f"- **{task}**: `{decision['status']}`; model: `{decision.get('model_id')}`.")
        lines.extend(["", "## Chỉ số bắt buộc (giá trị đầy đủ trong summary.json)", ""])
        for task, target in self.targets.items():
            lines.append(f"- {task}: AP ≥{target['ap_min']:.6f}; ROC-AUC ≥{target['roc_min']:.6f}; Brier ≤{target['brier_max']:.6f}; F1 ≥{target['f1_min']:.6f}; Precision ≥{target['precision_min']:.6f}.")
        lines.extend(["", "## Đối chiếu lịch sử 2023", "",
            "| Bài toán | Model | AP | ROC-AUC | Brier | Precision | Recall | F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|"])
        for identifier, record in records.items():
            if "historical_2023" not in record:
                continue
            m = record["historical_2023"]["metrics"]
            fields = " | ".join(f"{m[k]:.5f}" for k in ("ap", "roc_auc", "brier_score", "precision", "recall", "f1"))
            lines.append(f"| {record['task']} | {identifier} | {fields} |")
        lines.extend(["", "## Sử dụng", "",
            "Mỗi model CPU chứa đủ encoder, classifier, calibrator, ngưỡng và chuyên gia DL nếu được chọn. Giữ mã nguồn cùng requirements-binary-v3.txt.",
            "```python", "import joblib", "model = joblib.load('<run>/models/<model_id>.joblib')",
            "result = model.predict_schedule(canonical_schedule_dataframe)", "```", "",
            "Các file verification chứa kết quả từng fold. diagnostics chứa đối chứng đặc trưng cùng cấu hình và kiểm tra quý IV/2020. model_results.json có khoảng tin cậy và kết quả seed.",
            "Giá trị Q4_PASS chỉ nói đã vượt các mốc phát triển lịch sử; không phải chứng nhận từ một tập kiểm thử chưa từng xem.", ""])
        (self.output / "RESULTS.vi.md").write_text("\n".join(lines), encoding="utf-8")

    def run(self):
        self.output.mkdir(parents=True, exist_ok=False)
        sources = [ROOT / "src/features/binary_improvement_v3.py", ROOT / "src/models/binary_improvement_v3.py",
            Path(__file__), ROOT / "src/models/binary_v3_protocol.py", ROOT / "src/models/binary_improvement.py",
            ROOT / "src/features/binary_improvement.py", ROOT / "configs/binary_improvement_v3.yaml",
            ROOT / "src/models/binary_improvement_execution.py",
            ROOT / "requirements-binary-v3.txt", ROOT / "requirements-binary.txt", ROOT / "requirements.txt",
            ROOT / "src/features/tabular_features.py", ROOT / "src/features/departure_features.py",
            ROOT / "src/data/preprocessing.py", ROOT / "src/data/departure_preprocessing.py"]
        source_hashes = {}
        for path in sources:
            relative = path.relative_to(ROOT)
            destination = self.output / "source_snapshot" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            source_hashes[str(relative)] = digest(path)
        self.summary["environment"] = {"python": sys.version, "source_hashes": source_hashes,
            "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "xgboost", "lightgbm", "optuna", "pyarrow", "joblib")},
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
        write_json(self.output / "resolved_config.json", self.config)
        self.checkpoint()
        records, decisions = {}, {}
        try:
            with prevent_sleep(), threadpool_limits(limits=self.config["budget"]["threads"]):
                self.probe_gpu()
                jobs = [(task, branch) for task in self.config["tasks"] for branch in self.config["branches"]]
                screened = {}
                for number, (task, branch) in enumerate(jobs):
                    remaining = len(jobs) - number
                    job_deadline = min(self.screen_deadline, time.monotonic() + max(0, self.screen_deadline - time.monotonic()) / remaining)
                    self.event("screening_started", task=task, branch=branch)
                    screened[(task, branch)] = self.screen_job(task, branch, job_deadline)
                    if not screened[(task, branch)]:
                        raise FitIncomplete("No completed screening candidate")
                for task, branch in jobs:
                    self.event("verification_started", task=task, branch=branch)
                    self.shortlists[(task, branch)] = self.verify_job(task, branch, screened[(task, branch)])
                    self.diagnostic_experiments(task, branch, self.shortlists[(task, branch)][0])
                records = self.final_models()
                decisions = self.score_final(records)
                self.summary["tasks"] = decisions
                self.confirmation(records, decisions)
                self.summary["status"] = "COMPLETE"
        except Exception as exc:
            self.summary.update(status="INCOMPLETE" if isinstance(exc, FitIncomplete) else "FAILED",
                error=str(exc), traceback=traceback.format_exc())
            self.event("run_failed", reason=str(exc))
        if self.smoke:
            self.summary["status"] = "SMOKE_" + self.summary["status"]
        self.summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.checkpoint()
        self.report(records, decisions)
        self.event("run_finished", status=self.summary["status"])


def baseline_spec():
    return {"family": "xgboost", "group": "original", "window": 0, "half_life": 0, "weight": "none", "alpha": 0.,
        "params": {"n_estimators": 100, "max_depth": 6, "learning_rate": .05, "subsample": .8, "colsample_bytree": .8}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/binary_improvement_v3.yaml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if (config["protocol_version"] != VERSION or config["tasks"] != ["arrival", "departure"]
        or config["branches"] != ["A", "B"] or config["target_quarter"] != "2022Q4"
        or config["development_quarters"] != ["2019Q4", "2021Q4"]
        or config["verification_quarters"] != ["2019Q4", "2021Q4", "2022Q2"]
        or config["blocked_years"] != [2024] or config["cutoff_hours"] != 2
        or config["delay_minutes"] != 15 or config["seed"] != 202601
        or config["stability_seeds"] != [202602, 202603] or config["selection"]["warmup_days"] != 90
        or config["selection"]["include_matched_controls"] is not True
        or not 0 < config["budget"]["total_hours"] <= 12):
        parser.error("Frozen V3 task/temporal/target contracts cannot be overridden")
    output = args.output or ROOT / "artifacts/binary_improvement_v3" / datetime.now().strftime("%Y%m%d_%H%M%S")
    runner = V3Experiment(config, output.resolve(), smoke=args.smoke)
    runner.run()
    if runner.summary["status"] not in ("COMPLETE", "SMOKE_COMPLETE"):
        raise SystemExit(1)
