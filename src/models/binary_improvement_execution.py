"""Budgeted research execution; no changes to dashboard or frozen V1 contracts."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import joblib
import numpy as np
import optuna
import pandas as pd
import psutil
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits
import xgboost as xgb
import yaml

from src.data.access_guard import assert_data_access_allowed
from src.data.departure_preprocessing import build_departure_linear_preprocessor
from src.data.preprocessing import build_linear_preprocessor
from src.features.binary_improvement import (VERSION, ScheduleHistoryEncoder,
    make_preprocessor, prepare_frame, source_columns)
from src.models.binary_improvement import (BinaryModelBundle, binary_metrics,
    paired_block_bootstrap, positive_probability, promotion_gate,
    select_calibrator, select_threshold)

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda v: v.item() if isinstance(v, np.generic) else str(v)), encoding="utf-8")
    temp.replace(path)


class FitIncomplete(RuntimeError):
    pass


class DeadlineCallback(xgb.callback.TrainingCallback):
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.expired = False

    def after_iteration(self, model, epoch, evals_log):
        self.expired = time.monotonic() >= self.deadline
        return self.expired


@contextmanager
def prevent_sleep():
    if os.name != "nt":
        yield
        return
    import ctypes
    previous = ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        yield
    finally:
        if previous:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


class Experiment:
    def __init__(self, config: dict, output: Path, *, smoke=False):
        self.config, self.output, self.smoke = config, output, smoke
        self.seed = int(config["seed"])
        self.started = time.monotonic()
        self.deadline = self.started + config["budget"]["total_hours"] * 3600
        self.screen_deadline = self.started + config["budget"]["screening_cutoff_hours"] * 3600
        self.verify_deadline = self.started + config["budget"]["verification_cutoff_hours"] * 3600
        self.audit = {}
        self.summary = {"protocol": VERSION, "status": "RUNNING", "smoke": smoke,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "untouched_test_available": False, "tasks": {},
                        "dashboard_changed": False, "optimizer_changed": False,
                        "config": config}
        self.device = "cpu"

    def event(self, stage: str, **details):
        record = {"at": datetime.now(timezone.utc).isoformat(),
                  "elapsed_seconds": round(time.monotonic() - self.started, 3),
                  "stage": stage, **details}
        print(json.dumps(record, default=str), flush=True)
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        write_json(self.output / "progress.json", record)

    def checkpoint(self):
        self.summary["elapsed_seconds"] = time.monotonic() - self.started
        self.summary["peak_observed_rss_mb"] = max(self.summary.get("peak_observed_rss_mb", 0), psutil.Process().memory_info().rss / 1024 ** 2)
        write_json(self.output / "summary.json", self.summary)
        write_json(self.output / "data_audit.json", self.audit)

    def check_time(self, deadline=None):
        if time.monotonic() >= min(self.deadline, deadline or self.deadline):
            raise FitIncomplete("Stage/global wall-clock deadline reached")

    def load_year(self, task: str, year: int) -> pd.DataFrame:
        # Check before any filesystem or cache access, even if the global guard changes.
        if year not in range(2016, 2024):
            raise PermissionError("binary_improvement_v2 categorically blocks 2024")
        assert_data_access_allowed(year, "development", config_version=VERSION)
        cache = self.output / "cache" / task / f"{year}.parquet"
        if cache.exists():
            return pd.read_parquet(cache)
        self.check_time()
        folder = "inbound_atl" if task == "arrival" else "outbound_atl"
        files = sorted((ROOT / "data" / "processed" / folder / f"year={year}").glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No {task} data for {year}")
        columns = source_columns(task)
        parts = [pq.ParquetFile(f).read(columns=columns).to_pandas() for f in files]
        raw = pd.concat(parts, ignore_index=True)
        if pd.to_datetime(raw["FL_DATE"]).dt.year.ne(year).any():
            raise ValueError("Partition year conflicts with flight date")
        if raw["flight_key"].isna().any() or raw["flight_key"].duplicated().any():
            raise ValueError("Missing/duplicate flight_key")
        target = "ARR_DELAY" if task == "arrival" else "DEP_DELAY"
        prepared = prepare_frame(raw, task)
        # Smoke is labelled throughout and cannot produce a promotable artifact.
        if self.smoke and len(prepared) > 2400:
            prepared = prepared.groupby(prepared["__date"].dt.month, group_keys=False).sample(frac=min(1, 2400 / len(prepared)), random_state=self.seed).reset_index(drop=True)
        self.audit[f"{task}_{year}"] = {
            "input_rows": len(raw), "eligible_rows": len(prepared), "missing_target": int(raw[target].isna().sum()),
            "prevalence": float(prepared["__target"].mean()),
            "missing_by_source": {c: int(raw[c].isna().sum()) for c in columns},
            "months": prepared.groupby(prepared["__date"].dt.month)["__target"].agg(["count", "mean"]).to_dict("index"),
            "source_files": [{"path": str(f.relative_to(ROOT)), "sha256": digest(f)} for f in files],
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        prepared.to_parquet(cache, index=False)
        self.event("data_prepared", task=task, year=year, rows=len(prepared))
        return prepared

    def probe_gpu(self):
        if not self.config["budget"]["prefer_gpu"]:
            return
        try:
            rng = np.random.default_rng(self.seed)
            probe = xgb.XGBClassifier(n_estimators=2, tree_method="hist", device="cuda", n_jobs=1)
            probe.fit(rng.normal(size=(100, 3)), np.arange(100) % 2)
            actual = json.loads(probe.get_booster().save_config())["learner"]["generic_param"]["device"]
            if not actual.startswith("cuda"):
                raise RuntimeError(f"XGBoost actually selected {actual}")
            self.device = "cuda"
        except Exception as exc:
            self.event("gpu_unavailable_cpu_fallback", reason=str(exc))
        self.summary["xgboost_device"] = self.device

    def encode(self, train, valid, task, features, *, linear=False):
        encoder = ScheduleHistoryEncoder(task, features)
        engineered = encoder.fit_transform(train, train["__target"].to_numpy())
        if linear:
            prep = build_linear_preprocessor() if task == "arrival" else build_departure_linear_preprocessor()
        else:
            prep = make_preprocessor(task, features, engineered)
        a = prep.fit_transform(engineered)
        b = prep.transform(encoder.transform(valid))
        if not linear:
            a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
        return encoder, prep, a, b

    def fit_classifier(self, family, params, a, y, *, valid=None, valid_y=None, deadline=None):
        self.check_time(deadline)
        deadline = min(self.deadline, deadline or self.deadline,
                       time.monotonic() + self.config["budget"]["fit_timeout_seconds"])
        params = dict(params)
        early_stopping = bool(params.pop("early_stopping", True))
        if not early_stopping:
            valid, valid_y = None, None
        weight_policy = params.pop("weight_policy", "none")
        ratio = float(np.sum(y == 0) / max(1, np.sum(y == 1)))
        positive_weight = {"none": 1.0, "sqrt": np.sqrt(ratio), "balanced": ratio}[weight_policy]
        if family == "xgboost":
            callback = DeadlineCallback(deadline)
            model = xgb.XGBClassifier(**params, objective="binary:logistic", eval_metric="aucpr",
                tree_method="hist", device=self.device, n_jobs=self.config["budget"]["threads"],
                random_state=self.seed, scale_pos_weight=positive_weight,
                callbacks=[callback], **({"early_stopping_rounds": 60} if valid is not None else {}))
            try:
                model.fit(a, y, **({"eval_set": [(valid, valid_y)], "verbose": False} if valid is not None else {}))
            except xgb.core.XGBoostError as exc:
                if self.device != "cuda":
                    raise
                self.device = "cpu"
                self.event("gpu_fit_failed_cpu_fallback", reason=str(exc))
                return self.fit_classifier(family, {**params, "weight_policy": weight_policy}, a, y,
                                           valid=valid, valid_y=valid_y, deadline=deadline)
            if callback.expired:
                raise FitIncomplete("XGBoost fit stopped at deadline; candidate discarded")
            model.set_params(callbacks=None)
        elif family == "hgb":
            maximum = int(params.pop("max_iter", 300))
            model = HistGradientBoostingClassifier(**params, max_iter=min(25, maximum),
                early_stopping=False, warm_start=True, random_state=self.seed)
            sample_weight = np.where(y == 1, positive_weight, 1.0)
            best, stale, best_model, best_iter = -np.inf, 0, None, 0
            for iteration in range(25, maximum + 25, 25):
                self.check_time(deadline)
                model.set_params(max_iter=min(iteration, maximum))
                model.fit(a, y, sample_weight=sample_weight)
                self.check_time(deadline)
                if valid is not None:
                    from sklearn.metrics import average_precision_score
                    score = average_precision_score(valid_y, positive_probability(model, valid))
                    if score > best + 1e-5:
                        best, stale, best_iter = score, 0, model.n_iter_
                        import copy
                        best_model = copy.deepcopy(model)
                    else:
                        stale += 25
                    if stale >= 60:
                        break
            if valid is not None:
                model = best_model
                model.best_iteration_ = best_iter
            model.set_params(warm_start=False)
        else:
            model = LogisticRegression(max_iter=300, C=1.0, random_state=self.seed, solver="lbfgs")
            model.fit(a, y)
            self.check_time(deadline)
        return model

    def screen(self, task, development):
        train = development.loc[development["__year"].between(2016, 2020)].copy()
        cap = 2400 if self.smoke else self.config["budget"]["screening_train_cap"]
        if len(train) > cap:
            # Proportional month/year sampling without altering natural prevalence.
            train = train.groupby([train["__year"], train["__date"].dt.month], group_keys=False).sample(frac=cap / len(train), random_state=self.seed)
        early = train.loc[train["__date"] >= "2020-11-01"]
        train = train.loc[train["__date"] < "2020-11-01"]
        validation = development.loc[development["__year"].eq(2021)]
        deadline = min(self.screen_deadline, time.monotonic() + self.config["budget"]["screening_seconds_per_task"])
        matrices = {}
        def matrix(features):
            if features not in matrices:
                enc, prep, a, b = self.encode(train, validation, task, features)
                e = np.asarray(prep.transform(enc.transform(early)), dtype=np.float32)
                matrices[features] = a, b, e
            return matrices[features]
        candidates, ablation = [], []
        for family in ("xgboost", "hgb"):
            study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=self.seed),
                pruner=optuna.pruners.NopPruner(), storage=f"sqlite:///{(self.output / (task + '_' + family + '.sqlite3')).as_posix()}",
                study_name=f"{VERSION}_{task}_{family}")
            for stop_early in (True, False):
                for feature_set in ("F0", "F1", "F2"):
                    study.enqueue_trial({"feature_set": feature_set, "weight_policy": "none", "early_stopping": stop_early})
            def objective(trial):
                self.check_time(deadline)
                features = trial.suggest_categorical("feature_set", ["F0", "F1", "F2"])
                stop_early = trial.suggest_categorical("early_stopping", [True, False])
                params = {"weight_policy": trial.suggest_categorical("weight_policy", ["none", "sqrt", "balanced"]),
                          "early_stopping": stop_early}
                if family == "xgboost":
                    iterations = trial.suggest_categorical("fixed_estimators", [100, 300, 600, 1200]) if not stop_early else 1200
                    params.update(n_estimators=120 if self.smoke else iterations,
                        max_depth=trial.suggest_int("max_depth", 3, 8),
                        learning_rate=trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                        min_child_weight=trial.suggest_float("min_child_weight", 1, 20, log=True),
                        subsample=trial.suggest_float("subsample", 0.6, 1.0),
                        colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
                        reg_alpha=trial.suggest_float("reg_alpha", 1e-4, 10, log=True),
                        reg_lambda=trial.suggest_float("reg_lambda", 0.1, 20, log=True))
                else:
                    iterations = trial.suggest_categorical("fixed_iterations", [100, 200, 300]) if not stop_early else 300
                    params.update(max_iter=50 if self.smoke else iterations,
                        learning_rate=trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                        max_leaf_nodes=trial.suggest_categorical("max_leaf_nodes", [15, 31, 63]),
                        max_depth=trial.suggest_int("max_depth", 3, 8),
                        min_samples_leaf=trial.suggest_int("min_samples_leaf", 20, 100),
                        l2_regularization=trial.suggest_float("l2_regularization", 1e-4, 10, log=True))
                a, b, e = matrix(features)
                t = time.monotonic()
                model = self.fit_classifier(family, params, a, train["__target"].to_numpy(),
                    valid=e, valid_y=early["__target"].to_numpy(), deadline=deadline)
                if family == "xgboost" and stop_early:
                    params["n_estimators"] = int(model.best_iteration + 1)
                elif family == "hgb" and stop_early:
                    params["max_iter"] = int(model.best_iteration_)
                # Refit the selected fixed iteration count without additional early stopping.
                params["early_stopping"] = False
                metrics = binary_metrics(validation["__target"], positive_probability(model, b))
                trial.set_user_attr("refit_parameters", params)
                trial.set_user_attr("metrics", metrics)
                self.event("trial_complete", task=task, family=family, trial=trial.number,
                           features=features, ap=metrics["ap"], seconds=time.monotonic() - t)
                return metrics["ap"]
            limit = (3 if self.smoke else self.config["budget"]["xgboost_trials_per_task" if family == "xgboost" else "hgb_trials_per_task"])
            for _ in range(limit):
                if time.monotonic() >= deadline:
                    break
                study.optimize(objective, n_trials=1, catch=(FitIncomplete, ValueError, xgb.core.XGBoostError))
            complete = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
            for trial in complete:
                ablation.append({"family": family, "feature_set": trial.params["feature_set"],
                    "ap": trial.value, "parameters": trial.user_attrs["refit_parameters"]})
            if complete:
                best = max(complete, key=lambda t: t.value)
                candidates.append({"id": family + "_candidate", "family": family,
                    "feature_set": best.params["feature_set"], "params": best.user_attrs["refit_parameters"],
                    "screen_ap": best.value, "trial": best.number,
                    "completed_trials": len(complete), "requested_trials": limit})
        write_json(self.output / task / "screening.json", {"candidates": candidates,
            "trial_diagnostics_not_controlled_ablation": ablation,
            "screen_validation_rows": len(validation), "train_rows": len(train)})
        return candidates

    def fit_bundle(self, task, spec, train, validation, deadline):
        start = time.monotonic()
        enc, prep, a, b = self.encode(train, validation, task, spec["feature_set"], linear=spec["family"] == "logistic")
        model = self.fit_classifier(spec["family"], spec["params"], a,
                                    train["__target"].to_numpy(), deadline=deadline)
        bundle = BinaryModelBundle(enc, prep, model, metadata={"protocol": VERSION, "task": task,
            "feature_set": spec["feature_set"], "cutoff_hours": 2, "delay_minutes": 15,
            "seed": self.seed, "spec": spec, "training_max_year": int(train["__year"].max()),
            "xgboost_device": self.device, "smoke": self.smoke})
        p = positive_probability(model, b)
        return bundle, p, time.monotonic() - start

    def verify(self, task, candidates, development):
        verified = []
        for spec in candidates:
            folds = []
            try:
                for year in (2019, 2020, 2021):
                    self.check_time(self.verify_deadline)
                    train, val = development.loc[development["__year"] < year], development.loc[development["__year"] == year]
                    bundle, p, seconds = self.fit_bundle(task, spec, train, val, self.verify_deadline)
                    metrics = binary_metrics(val["__target"], p)
                    folds.append({"validation_year": year, "metrics": metrics, "seconds": seconds})
                    self.event("verification_fold", task=task, candidate=spec["id"], year=year, ap=metrics["ap"], seconds=seconds)
                    del bundle
                verified.append(spec)
                status = "COMPLETE"
            except FitIncomplete as exc:
                status = "INCOMPLETE"
                self.event("verification_incomplete", task=task, candidate=spec["id"], reason=str(exc))
            macro = {name: float(np.mean([f["metrics"][name] for f in folds])) for name in ("ap", "roc_auc", "brier_score")} if folds else {}
            write_json(self.output / task / f"verification_{spec['id']}.json", {"status": status,
                "spec": spec, "folds": folds, "macro": macro})
        return verified

    def calibrate_evaluate(self, task, spec, train, calibration):
        bundle, raw, seconds = self.fit_bundle(task, spec, train, calibration, self.deadline)
        quarter = calibration["__date"].dt.quarter.to_numpy()
        y = calibration["__target"].to_numpy()
        bundle.calibrator, cal_scores = select_calibrator(raw[quarter == 1], y[quarter == 1], raw[quarter == 2], y[quarter == 2],
            indifference=self.config["evaluation"]["calibration_indifference"])
        p = bundle.calibrator.transform(raw)
        threshold = select_threshold(y[quarter == 3], p[quarter == 3], self.config["evaluation"]["precision_multiplier"])
        bundle.threshold = threshold["threshold"]
        bundle.metadata.update(calibration=cal_scores, calibration_method=bundle.calibrator.method,
            threshold_selection=threshold, fit_seconds=seconds,
            train_rows=len(train), q4_selection_role="development_selection_not_untouched_test")
        q4 = quarter == 4
        record = {"spec": spec, "calibration_scores": cal_scores,
            "calibration_method": bundle.calibrator.method, "threshold_selection": threshold,
            "q4_at_0_5": binary_metrics(y[q4], p[q4]),
            "q4_selected_threshold": binary_metrics(y[q4], p[q4], bundle.threshold),
            "fit_seconds": seconds, "status": "COMPLETE"}
        folder = self.output / task
        folder.mkdir(exist_ok=True, parents=True)
        predictions = calibration.loc[:, ["__key", "__date", "__target"]].copy()
        predictions["raw_probability"], predictions["probability"] = raw, p
        predictions["threshold"] = bundle.threshold
        predictions.to_parquet(folder / f"{spec['id']}_2022.parquet", index=False)
        model_path = folder / f"{spec['id']}.joblib"
        joblib.dump(bundle, model_path, compress=3)
        # Verify persistence in a new interpreter, not only in this importing process.
        sample = calibration.iloc[:32]
        sample_path = folder / "reload_sample.parquet"
        sample.to_parquet(sample_path, index=False)
        code = "import joblib,pandas as pd,numpy as np,sys; m=joblib.load(sys.argv[1]); np.save(sys.argv[3],m.predict_proba(pd.read_parquet(sys.argv[2])))"
        pred_path = folder / "reload_probabilities.npy"
        child = subprocess.run([sys.executable, "-c", code, str(model_path), str(sample_path), str(pred_path)],
                               cwd=ROOT, capture_output=True, text=True, timeout=90)
        if child.returncode:
            raise RuntimeError("Fresh-process model reload failed: " + child.stderr)
        np.testing.assert_allclose(np.load(pred_path), bundle.predict_proba(sample), rtol=1e-6, atol=1e-7)
        record["fresh_process_reload"] = "PASS"
        record["model_sha256"] = digest(model_path)
        write_json(folder / f"{spec['id']}_metrics.json", record)
        self.event("calibrated_candidate", task=task, candidate=spec["id"], ap=record["q4_selected_threshold"]["ap"],
                   threshold=bundle.threshold, seconds=seconds)
        return bundle, record

    def controlled_ablation(self, task, spec, development):
        """Matched parameters, rows, labels and seed; only the feature set changes."""
        train = development.loc[development["__year"] < 2021]
        val = development.loc[development["__year"] == 2021]
        records = []
        for features in ("F0", "F1", "F2"):
            self.check_time(self.verify_deadline)
            ablation = {**spec, "feature_set": features, "id": "ablation_" + features}
            _, p, seconds = self.fit_bundle(task, ablation, train, val, self.verify_deadline)
            records.append({"feature_set": features, "metrics": binary_metrics(val["__target"], p), "seconds": seconds})
        write_json(self.output / task / "controlled_ablation.json", {"status": "COMPLETE", "validation_year": 2021,
            "fixed_parameters": spec["params"], "records": records})

    def confirmation(self, task, bundles, records, selected):
        # This stage is called only after the Q4 decision and its hashes are saved.
        frame = self.load_year(task, 2023)
        y = frame["__target"].to_numpy()
        baseline = bundles["xgboost_baseline"]
        predictions = frame.loc[:, ["__key", "__date", "__target"]].copy()
        all_p = {}
        for name, bundle in bundles.items():
            self.check_time()
            start = time.monotonic()
            p = bundle.predict_proba(frame)[:, 1]
            all_p[name] = p
            predictions[name] = p
            metrics = {"at_0_5": binary_metrics(y, p), "selected_threshold": binary_metrics(y, p, bundle.threshold),
                       "inference_seconds": time.monotonic() - start,
                       "role": "previously_used_historical_confirmation_no_retuning"}
            groups = {}
            route = "ORIGIN" if task == "arrival" else "DEST"
            for column, labels in [("month", frame["__date"].dt.month), ("carrier", frame["OP_CARRIER"]), ("route", frame[route])]:
                groups[column] = {str(group): binary_metrics(y[np.asarray(indices)], p[np.asarray(indices)], bundle.threshold)
                                  for group, indices in frame.groupby(labels, dropna=False).indices.items()}
            metrics["groups"] = groups
            records[name]["historical_2023"] = metrics
            write_json(self.output / task / f"{name}_metrics.json", records[name])
        # Constant baseline uses training prevalence, never evaluation prevalence.
        prior = float(baseline.metadata["training_prevalence"])
        records["constant_baseline"] = {"historical_2023": binary_metrics(y, np.full(len(y), prior))}
        predictions.to_parquet(self.output / task / "historical_predictions_2023.parquet", index=False)
        result = {"selected_before_2023": selected, "status": "RETAIN_EXISTING", "reason": "No Q4 candidate passed"}
        if selected:
            candidate = bundles[selected]
            stats = paired_block_bootstrap(frame["__date"], y, all_p[selected], all_p["xgboost_baseline"],
                iterations=20 if self.smoke else self.config["evaluation"]["bootstrap_iterations"], seed=self.seed)
            gate = promotion_gate(records[selected]["historical_2023"]["selected_threshold"],
                                  records["xgboost_baseline"]["historical_2023"]["selected_threshold"],
                                  candidate.metadata["threshold_selection"], self.config["evaluation"])
            ci = stats.get("delta_ci_95", {}).get("ap", [-1, 1])
            result.update(historical_gate=gate, uncertainty=stats)
            if gate["passed"] and ci[0] > 0 and not self.smoke:
                result.update(status="RECOMMENDED_RESEARCH_UPGRADE", reason="Q4 and historical gates passed; not an untouched-test claim")
            else:
                result["reason"] = "Historical gate/uncertainty failed, or smoke run"
        self.save_plots(task, y, all_p, bundles)
        return result

    def save_plots(self, task, y, probabilities, bundles):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import precision_recall_curve, roc_curve
        folder = self.output / task / "figures"
        folder.mkdir(exist_ok=True)
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        for name, p in probabilities.items():
            precision, recall, _ = precision_recall_curve(y, p)
            fpr, tpr, _ = roc_curve(y, p)
            # Downsample plotted points only, never scoring rows.
            step = max(1, len(recall) // 2000)
            axes[0].plot(recall[::step], precision[::step], label=name)
            axes[1].plot(fpr, tpr, label=name)
            bins = binary_metrics(y, p)["reliability"]
            axes[2].plot([b["mean_probability"] for b in bins if b["count"]],
                         [b["observed_rate"] for b in bins if b["count"]], marker="o", label=name)
        for ax, title, xlabel, ylabel in zip(axes, ["Precision–Recall", "ROC", "Calibration"],
            ["Recall", "False positive rate", "Mean probability"], ["Precision", "True positive rate", "Observed rate"]):
            ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
            ax.grid(alpha=0.2)
        axes[2].plot([0, 1], [0, 1], "k--", alpha=0.4)
        axes[0].legend(fontsize=7)
        fig.suptitle(task + " — historical 2023; not an untouched test")
        fig.tight_layout()
        fig.savefig(folder / "historical_evaluation.png", dpi=150)
        plt.close(fig)

    def run_task(self, task):
        folder = self.output / task
        folder.mkdir(parents=True, exist_ok=True)
        development = pd.concat([self.load_year(task, y) for y in range(2016, 2022)], ignore_index=True)
        if development["__key"].duplicated().any():
            raise ValueError("Duplicate flight keys across training years")
        calibration = self.load_year(task, 2022)
        candidates = self.screen(task, development)
        candidates = self.verify(task, candidates, development)
        baseline_spec = {"id": "xgboost_baseline", "family": "xgboost", "feature_set": "F0",
            "params": {"n_estimators": 100, "max_depth": 6, "learning_rate": 0.05,
                       "subsample": 0.8, "colsample_bytree": 0.8, "weight_policy": "none"}}
        # All candidates and baselines get exactly the same data and postprocessing.
        specs = [baseline_spec, {"id": "logistic_baseline", "family": "logistic", "feature_set": "F0", "params": {}}, *candidates]
        bundles, records = {}, {}
        for spec in specs:
            try:
                bundle, record = self.calibrate_evaluate(task, spec, development, calibration)
                bundle.metadata["training_prevalence"] = float(development["__target"].mean())
                joblib.dump(bundle, folder / f"{spec['id']}.joblib", compress=3)
                record["model_sha256"] = digest(folder / f"{spec['id']}.joblib")
                bundles[spec["id"]], records[spec["id"]] = bundle, record
            except FitIncomplete as exc:
                self.event("final_fit_incomplete", task=task, candidate=spec["id"], reason=str(exc))
        if "xgboost_baseline" not in bundles:
            raise FitIncomplete("Full-data baseline unavailable; no promotion permitted")
        passed = []
        for spec in candidates:
            name = spec["id"]
            if name not in records:
                continue
            gate = promotion_gate(records[name]["q4_selected_threshold"], records["xgboost_baseline"]["q4_selected_threshold"],
                                  records[name]["threshold_selection"], self.config["evaluation"])
            records[name]["q4_promotion_gate"] = gate
            if gate["passed"]:
                passed.append(name)
        best_ap = max((records[n]["q4_selected_threshold"]["ap"] for n in passed), default=None)
        tied = [n for n in passed if records[n]["q4_selected_threshold"]["ap"] >= best_ap - 0.005] if passed else []
        selected = min(tied, key=lambda n: (records[n]["q4_selected_threshold"]["brier_score"], records[n]["fit_seconds"])) if tied else None
        selection = {"status": "FROZEN_BEFORE_2023", "selected": selected,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "models": {n: {"sha256": r["model_sha256"], "threshold": bundles[n].threshold} for n, r in records.items()}}
        write_json(folder / "selection_freeze.json", selection)
        if candidates:
            try:
                self.controlled_ablation(task, max(candidates, key=lambda s: s["screen_ap"]), development)
            except FitIncomplete as exc:
                write_json(folder / "controlled_ablation.json", {"status": "INCOMPLETE", "reason": str(exc)})
        del development, calibration
        result = self.confirmation(task, bundles, records, selected)
        self.summary["tasks"][task] = {"status": "COMPLETE", "selection": selection,
            "recommendation": result, "models": records}
        self.checkpoint()

    def report(self):
        lines = ["# Binary improvement V2", "", f"Status: {self.summary['status']}",
            "", "Historical development evidence; no untouched test available. 2024 was not accessed.",
            "Existing dashboard and optimizer models were not changed.", "",
            "| Task | Model | AP 2023 | ROC-AUC | Brier | Precision | Recall | F1 | Threshold |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for task, result in self.summary["tasks"].items():
            for name, record in result.get("models", {}).items():
                metrics = record.get("historical_2023", {}).get("selected_threshold")
                if metrics:
                    values = " | ".join(f"{metrics[k]:.4f}" for k in ("ap", "roc_auc", "brier_score", "precision", "recall", "f1", "threshold"))
                    lines.append(f"| {task} | {name} | {values} |")
            lines.extend(["", f"{task}: {result.get('recommendation', result.get('error'))}", ""])
        (self.output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self):
        self.output.mkdir(parents=True, exist_ok=False)
        self.summary["environment"] = {"python": sys.version, "platform": platform.platform(),
            "logical_cpus": os.cpu_count(), "ram_bytes": psutil.virtual_memory().total,
            "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "xgboost", "optuna", "pyarrow", "joblib", "matplotlib")},
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_hashes": {str(p.relative_to(ROOT)): digest(p) for p in [Path(__file__), ROOT / "src/features/binary_improvement.py", ROOT / "src/models/binary_improvement.py"]}}
        write_json(self.output / "resolved_config.json", self.config)
        self.checkpoint()
        with prevent_sleep(), threadpool_limits(limits=self.config["budget"]["threads"]):
            self.probe_gpu()
            for task in self.config["tasks"]:
                try:
                    self.event("task_started", task=task)
                    self.run_task(task)
                except Exception as exc:
                    status = "INCOMPLETE" if isinstance(exc, FitIncomplete) else "FAILED"
                    self.summary["tasks"][task] = {"status": status, "error": str(exc), "traceback": traceback.format_exc()}
                    self.event("task_failed", task=task, status=status, reason=str(exc))
                    self.checkpoint()
            statuses = [r["status"] for r in self.summary["tasks"].values()]
            self.summary["status"] = "COMPLETE" if all(s == "COMPLETE" for s in statuses) else "INCOMPLETE"
            if self.smoke:
                self.summary["status"] = "SMOKE_" + self.summary["status"]
            self.summary["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.checkpoint()
            self.report()
            self.event("run_finished", status=self.summary["status"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/binary_improvement_v2.yaml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true", help="Labelled tiny pipeline test; never promotable")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if config["protocol_version"] != VERSION or config["tasks"] != ["arrival", "departure"]:
        parser.error("Only the versioned Arrival + Departure protocol is supported")
    if config["allowed_training_years"] != list(range(2016, 2022)) or config["blocked_years"] != [2024]:
        parser.error("Temporal boundaries cannot be overridden")
    if (config["rolling_validation_years"] != [2019, 2020, 2021]
        or config["calibration_year"] != 2022 or config["historical_confirmation_year"] != 2023
        or config["cutoff_hours"] != 2 or config["label_delay_minutes"] != 15
        or config["evaluation"]["bootstrap_block_days"] != 7
        or not 0 < config["budget"]["total_hours"] <= 12):
        parser.error("Temporal, target and maximum-budget contracts cannot be overridden")
    output = args.output or ROOT / "artifacts/binary_improvement_v2" / datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment = Experiment(config, output.resolve(), smoke=args.smoke)
    experiment.run()
    if experiment.summary["status"] not in ("COMPLETE", "SMOKE_COMPLETE"):
        raise SystemExit(1)
