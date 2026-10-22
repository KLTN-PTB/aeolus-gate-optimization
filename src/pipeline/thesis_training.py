"""Resumable temporal training for the adjusted proposal. Never reads 2024."""
from __future__ import annotations
import argparse
from collections import OrderedDict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import warnings
import shutil

import joblib
import numpy as np
import optuna
import pandas as pd
import psutil
import pyarrow.dataset as ds
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from threadpoolctl import threadpool_limits
import xgboost as xgb
import yaml

from src.data.access_guard import assert_data_access_allowed
from src.features.binary_improvement import prepare_frame, source_columns
from src.models.binary_improvement import ProbabilityCalibrator, binary_metrics, positive_probability
from src.models.binary_improvement_execution import DeadlineCallback, FitIncomplete, digest, prevent_sleep
from src.models.binary_v3_execution import write_json
from src.models.binary_improvement_v3 import fixed_precision_threshold
from src.models.binary_v3_protocol import warmup_indices
from src.models.thesis_models import ScheduleEncoder, ThesisBundle, temporal_meta_training

ROOT = Path(__file__).resolve().parents[2]


def regression_metrics(y, p):
    return {"n": len(y), "mae": float(mean_absolute_error(y, p)),
            "rmse": float(np.sqrt(mean_squared_error(y, p)))}


class Training:
    def __init__(self, output, config, *, smoke=False, resume=False):
        self.output, self.config, self.smoke = output, config, smoke
        if output.exists() and not resume:
            raise FileExistsError("Use --resume or a new output directory")
        output.mkdir(parents=True, exist_ok=True)
        saved = output / "resolved_config.json"
        if saved.exists() and json.loads(saved.read_text()) != config:
            raise ValueError("Resume cannot change the frozen configuration")
        write_json(saved, config)
        contract = output / "run_contract.json"
        if contract.exists() and json.loads(contract.read_text())["smoke"] != smoke:
            raise ValueError("A smoke run cannot be resumed as a full run")
        write_json(contract, {"smoke": smoke})
        self.started = time.monotonic()
        state = output / "training_state.json"
        self.state = json.loads(state.read_text()) if state.exists() else {"active_seconds": 0, "models": {}, "data": {}}
        self.previous_seconds = self.state["active_seconds"]
        self.frames, self.matrices = OrderedDict(), OrderedDict()
        self.device = "cpu"
        self.evaluation_open = False
        self.seed = config["seed"]
        # Exact source bytes, not just HEAD (working code can be uncommitted).
        source_paths = [Path(__file__), ROOT / "src/models/thesis_models.py", ROOT / "configs/thesis_completion.yaml",
                        ROOT / "src/features/binary_improvement.py", ROOT / "src/models/binary_improvement.py",
                        ROOT / "src/data/preprocessing.py", ROOT / "src/data/departure_preprocessing.py",
                        ROOT / "src/features/tabular_features.py", ROOT / "src/features/departure_features.py"]
        hashes = {str(path.relative_to(ROOT)): digest(path) for path in source_paths}
        frozen = output / "source_hashes.json"
        if frozen.exists() and json.loads(frozen.read_text()) != hashes:
            raise ValueError("Training sources changed since the run started")
        write_json(frozen, hashes)
        for path in source_paths:
            copy = output / "source_snapshot" / path.relative_to(ROOT)
            if not copy.exists():
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, copy)

    def elapsed(self):
        return self.previous_seconds + time.monotonic() - self.started

    def check(self, hours=16):
        if self.elapsed() >= min(hours, self.config["budget"]["total_hours"]) * 3600:
            raise FitIncomplete("Proposal experiment exhausted its stage budget")

    def event(self, stage, **fields):
        record = {"at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(self.elapsed(), 2),
                  "stage": stage, **fields}
        print(json.dumps(record), flush=True)
        write_json(self.output / "progress.json", record)
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        self.state["active_seconds"] = self.elapsed()
        write_json(self.output / "training_state.json", self.state)

    def read_year(self, task, year):
        if not 2016 <= year <= 2023 or (year == 2023 and not self.evaluation_open):
            raise PermissionError("Future labels closed before any filesystem access")
        assert_data_access_allowed(year, "development", config_version="thesis_completion_v1")
        key = (task, year)
        if key in self.frames:
            self.frames.move_to_end(key)
            return self.frames[key]
        cache = self.output / "data_cache" / f"{task}_{year}.parquet"
        if cache.exists():
            frame = pd.read_parquet(cache)
        else:
            folder = ROOT / "data/processed" / ("inbound_atl" if task == "arrival" else "outbound_atl") / f"year={year}"
            files = sorted(folder.glob("*.parquet"))
            if not files:
                raise FileNotFoundError(folder)
            raw = ds.dataset(files, format="parquet").to_table(columns=source_columns(task)).to_pandas()
            target = "ARR_DELAY" if task == "arrival" else "DEP_DELAY"
            raw = raw.loc[raw[target].notna()].copy()
            frame = prepare_frame(raw, task)
            frame["__reg"] = frame["__key"].map(raw.assign(flight_key=raw.flight_key.astype(str)).set_index("flight_key")[target])
            if frame["__reg"].isna().any() or frame["__key"].duplicated().any():
                raise ValueError("Invalid label/key alignment")
            frame = frame.sort_values(["__date", "__key"]).reset_index(drop=True)
            if self.smoke:
                frame = frame.groupby(frame["__date"].dt.month, group_keys=False).sample(
                    frac=min(1, 2400 / len(frame)), random_state=self.seed).reset_index(drop=True)
            cache.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cache, index=False)
            self.state["data"][f"{task}_{year}"] = [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)} for path in files]
        self.frames[key] = frame
        while len(self.frames) > 2:
            self.frames.popitem(last=False)
        return frame

    def matrix(self, task, end_year, linear=False):
        key = (task, end_year, linear)
        if key in self.matrices:
            self.matrices.move_to_end(key)
            return self.matrices[key]
        path = self.output / "matrix_cache" / f"{task}_{end_year}_{linear}.joblib"
        if path.exists():
            value = joblib.load(path)
        else:
            frame = pd.concat([self.read_year(task, y) for y in range(2016, end_year + 1)], ignore_index=True)
            cap = 2500 if self.smoke else self.config["budget"]["train_cap"]
            indices = warmup_indices(frame, days=0, cap=cap, seed=self.seed)
            frame = frame.iloc[indices].reset_index(drop=True)
            encoder = ScheduleEncoder(task, linear)
            x = encoder.fit_transform(frame)
            value = {"encoder": encoder, "x": x, "classification": frame["__target"].to_numpy(),
                     "regression": frame["__reg"].to_numpy(), "train_rows": len(frame), "train_end": f"{end_year}-12-31"}
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(value, path)
        self.matrices[key] = value
        while len(self.matrices) > 2:
            self.matrices.popitem(last=False)
        return value

    def fit(self, task, kind, family, end_year, params=None):
        self.check()
        matrix = self.matrix(task, end_year, family == "linear")
        x, y = matrix["x"], matrix[kind]
        deadline = time.monotonic() + self.config["budget"]["fit_timeout_seconds"]
        cfg = self.config["baseline"]
        if family == "linear":
            if kind == "classification":
                model = LogisticRegression(C=cfg["linear"]["C"], solver="saga", max_iter=cfg["linear"]["max_iter"],
                    tol=cfg["linear"]["tol"], random_state=self.seed, class_weight="balanced")
            else:
                model = Ridge(alpha=cfg["linear"]["ridge_alpha"], solver="lsqr")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                if kind == "classification":
                    model.set_params(max_iter=75, warm_start=True)
                    for _ in range(max(1, cfg["linear"]["max_iter"] // 75)):
                        if time.monotonic() >= deadline:
                            raise FitIncomplete("Logistic fit deadline exceeded")
                        model.fit(x, y)
                        if model.n_iter_.max() < 75:
                            break
                    model.set_params(warm_start=False)
                else:
                    model.fit(x, y)
        elif family == "random_forest":
            settings = dict(cfg[family])
            count = 10 if self.smoke else settings.pop("n_estimators")
            settings.pop("n_estimators", None)
            klass = RandomForestClassifier if kind == "classification" else RandomForestRegressor
            model = klass(**settings, n_estimators=min(25, count), warm_start=True,
                          n_jobs=self.config["budget"]["threads"], random_state=self.seed,
                          **({"class_weight": "balanced"} if kind == "classification" else {}))
            for n in range(25, count + 25, 25):
                if time.monotonic() >= deadline:
                    raise FitIncomplete("Random Forest fit deadline exceeded")
                model.set_params(n_estimators=min(n, count))
                model.fit(x, y)
            model.set_params(warm_start=False)
        else:
            settings = dict(params or cfg["xgboost"])
            if self.smoke:
                settings["n_estimators"] = 10
            callback = DeadlineCallback(deadline)
            klass = xgb.XGBClassifier if kind == "classification" else xgb.XGBRegressor
            model = klass(**settings, tree_method="hist", device=self.device,
                          n_jobs=self.config["budget"]["threads"], random_state=self.seed,
                          callbacks=[callback], objective="binary:logistic" if kind == "classification" else "reg:squarederror")
            try:
                model.fit(x, y, verbose=False)
            except xgb.core.XGBoostError:
                if self.device == "cpu":
                    raise
                self.device = "cpu"
                return self.fit(task, kind, family, end_year, params)
            if callback.expired:
                raise FitIncomplete("XGBoost fit incomplete")
            model.set_params(callbacks=None)
        if time.monotonic() >= deadline:
            raise FitIncomplete("Fit exceeded its timeout")
        return ThesisBundle(task, kind, family, matrix["encoder"], model,
            metadata={"train_end": matrix["train_end"], "train_rows": matrix["train_rows"],
                      "cutoff_hours": 2, "delay_minutes": 15, "seed": self.seed, "smoke": self.smoke})

    def fixed_oof(self, task, kind):
        pieces = []
        for year in range(2017, 2023):
            path = self.output / "oof" / f"{task}_{kind}_{year}.parquet"
            if path.exists():
                pieces.append(pd.read_parquet(path))
                continue
            frame = self.read_year(task, year)
            table = pd.DataFrame({"flight_key": frame["__key"], "date": frame["__date"], "year": year,
                                  "carrier": frame.OP_CARRIER, "y": frame["__target" if kind == "classification" else "__reg"]})
            for family in ("linear", "random_forest", "xgboost_fixed"):
                self.event("oof_fit", task=task, kind=kind, family=family, validation_year=year)
                bundle = self.fit(task, kind, "xgboost" if family == "xgboost_fixed" else family, year - 1)
                table[family] = bundle.raw_predict(frame)
            path.parent.mkdir(parents=True, exist_ok=True)
            table.to_parquet(path, index=False)
            pieces.append(table)
        return pd.concat(pieces, ignore_index=True)

    def tune(self, task, kind):
        self.check(8)
        path = self.output / "hpo" / f"{task}_{kind}.json"
        if path.exists():
            return json.loads(path.read_text())["params"]
        path.parent.mkdir(parents=True, exist_ok=True)
        study = optuna.create_study(study_name=f"{task}_{kind}", direction="maximize" if kind == "classification" else "minimize",
            storage=f"sqlite:///{(path.with_suffix('.sqlite3')).as_posix()}", load_if_exists=True,
            sampler=optuna.samplers.TPESampler(seed=self.seed))
        def objective(trial):
            params = {"n_estimators": trial.suggest_categorical("n_estimators", [100, 300, 600]),
                "max_depth": trial.suggest_int("max_depth", 3, 6),
                "learning_rate": trial.suggest_float("learning_rate", .03, .15, log=True),
                "min_child_weight": trial.suggest_float("min_child_weight", 1, 20),
                "subsample": trial.suggest_float("subsample", .7, 1),
                "colsample_bytree": trial.suggest_float("colsample_bytree", .7, 1),
                "reg_lambda": trial.suggest_float("reg_lambda", .1, 10, log=True)}
            scores, folds = [], []
            for year in self.config["validation_years"]:
                self.check(8)
                bundle = self.fit(task, kind, "xgboost", year - 1, params)
                frame = self.read_year(task, year)
                y, p = frame["__target" if kind == "classification" else "__reg"], bundle.raw_predict(frame)
                metrics = binary_metrics(y, p) if kind == "classification" else regression_metrics(y, p)
                scores.append(metrics["ap" if kind == "classification" else "mae"])
                folds.append({"year": year, "train_end": bundle.metadata["train_end"], "metrics": metrics})
            trial.set_user_attr("folds", folds)
            self.event("trial_complete", task=task, kind=kind, trial=trial.number)
            return float(np.mean(scores))
        wanted = 1 if self.smoke else self.config["budget"]["trials_per_target"]
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.RUNNING:
                study.tell(trial.number, state=optuna.trial.TrialState.FAIL)
        remaining = wanted - sum(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials)
        if remaining > 0:
            study.optimize(objective, n_trials=remaining)
        complete = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if len(complete) != wanted:
            raise FitIncomplete("Not all required HPO trials completed")
        write_json(path, {"params": study.best_params, "best_value": study.best_value,
                         "trials": [{"number": t.number, "params": t.params, "value": t.value, "folds": t.user_attrs["folds"]} for t in complete]})
        return study.best_params

    def target(self, task, kind, params):
        oof = self.fixed_oof(task, kind)
        tables, final_bases, final_models = {}, [], {}
        for family in ("linear", "random_forest", "xgboost_fixed"):
            final_bases.append(self.fit(task, kind, "xgboost" if family == "xgboost_fixed" else family, 2022))
        final_models.update(linear=final_bases[0], random_forest=final_bases[1])
        final_models["xgboost"] = self.fit(task, kind, "xgboost", 2022, params)
        meta, meta_audit = temporal_meta_training(oof, 2023, kind)
        final_models["stacking"] = ThesisBundle(task, kind, "stacking", estimator=meta, bases=final_bases,
            metadata={"train_end": "2022-12-31", "meta": meta_audit, "smoke": self.smoke, "cutoff_hours": 2})
        evaluation = oof.loc[oof.year.isin(self.config["validation_years"])].copy()
        for family, model in final_models.items():
            table = evaluation[["flight_key", "date", "year", "carrier", "y"]].copy()
            if family in ("linear", "random_forest"):
                table["raw_probability_or_delay"] = evaluation[family].to_numpy()
            else:
                prediction_parts = []
                for year in self.config["validation_years"]:
                    part = evaluation.loc[evaluation.year == year]
                    if family == "stacking":
                        fitted, audit = temporal_meta_training(oof, year, kind)
                        x = oof.loc[oof.year == year, ["linear", "random_forest", "xgboost_fixed"]].to_numpy()
                        p = positive_probability(fitted, x) if kind == "classification" else fitted.predict(x)
                        write_json(self.output / "meta_audit" / f"{task}_{kind}_{year}.json", audit)
                    else:
                        fitted = self.fit(task, kind, family, year - 1, params)
                        p = fitted.raw_predict(self.read_year(task, year))
                    if len(p) != len(part):
                        raise ValueError("OOF row count mismatch")
                    prediction_parts.append(p)
                table["raw_probability_or_delay"] = np.concatenate(prediction_parts)
            if kind == "classification":
                fit = table.date.between("2022-01-01", "2022-06-30")
                select = table.date.between("2022-07-01", "2022-12-31")
                try:
                    model.calibrator = ProbabilityCalibrator("sigmoid").fit(table.loc[fit, "raw_probability_or_delay"], table.loc[fit, "y"])
                except ValueError:
                    model.calibrator = ProbabilityCalibrator("identity").fit(table.loc[fit, "raw_probability_or_delay"], table.loc[fit, "y"])
                p = model.calibrator.transform(table.loc[select, "raw_probability_or_delay"])
                selected = fixed_precision_threshold(table.loc[select, "y"], p, 0.)
                model.threshold = selected["threshold"]
                model.metadata.update(calibration_method=model.calibrator.method, threshold_selection=selected,
                    calibration_period=["2022-01-01", "2022-06-30"], threshold_period=["2022-07-01", "2022-12-31"])
            tables[family] = table
            table.to_parquet(self.output / "oof" / f"{task}_{kind}_{family}_full.parquet", index=False)
            folds = []
            for year, part in table.groupby("year"):
                m = binary_metrics(part.y, part.raw_probability_or_delay) if kind == "classification" else regression_metrics(part.y, part.raw_probability_or_delay)
                folds.append({"year": int(year), "metrics": m, "role": "historical_development_raw_oof"})
            name = f"{task}_{kind}_{family}"
            model.metadata.update(model_id=name, protocol="thesis_completion_v1", inference_device="cpu", untouched_test_available=False)
            model.to_cpu()
            path = self.output / "models" / f"{name}.joblib"
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, path, compress=3)
            self.state["models"][name] = {"path": str(path.relative_to(self.output)), "sha256": digest(path),
                "task": task, "kind": kind, "family": family, "threshold": model.threshold, "folds": folds,
                "metadata": model.metadata}
            self.event("model_frozen", model=name)
        # Residual bank contains only temporal OOF errors, never 2023 outcomes.
        if kind == "regression":
            table = tables["xgboost"]
            residual = table.y.to_numpy() - table.raw_probability_or_delay.to_numpy()
            banks = {"global": residual.tolist()}
            for carrier, indices in table.groupby("carrier").indices.items():
                if len(indices) >= 100:
                    banks[str(carrier)] = residual[indices].tolist()
            joblib.dump(banks, self.output / "models" / f"{task}_residuals.joblib", compress=3)

    def evaluate(self):
        if len(self.state["models"]) != 16:
            raise FitIncomplete("All 16 models must be frozen before evaluation")
        residuals = {task: {"path": f"models/{task}_residuals.joblib", "sha256": digest(self.output / "models" / f"{task}_residuals.joblib")}
                     for task in self.config["tasks"]}
        freeze_path = self.output / "selection_freeze.json"
        if freeze_path.exists():
            previous = json.loads(freeze_path.read_text())
            if previous["models"] != self.state["models"] or previous["residuals"] != residuals:
                raise ValueError("Cannot refit or change artifacts after the evaluation freeze")
        else:
            write_json(freeze_path, {"status": "FROZEN_BEFORE_2023", "at": datetime.now(timezone.utc).isoformat(),
                "models": self.state["models"], "residuals": residuals, "historical_development_only": True})
        self.evaluation_open = True
        records = {}
        for task in self.config["tasks"]:
            frame = self.read_year(task, 2023)
            for name, rec in self.state["models"].items():
                if rec["task"] != task:
                    continue
                self.check(24)
                path = self.output / rec["path"]
                if digest(path) != rec["sha256"]:
                    raise ValueError("Frozen model checksum changed")
                model = joblib.load(path)
                sample = frame.iloc[:16]
                sample_path = self.output / "reload_sample.parquet"
                sample.to_parquet(sample_path, index=False)
                out = self.output / "reload.npy"
                method = "predict_proba" if rec["kind"] == "classification" else "predict"
                child = subprocess.run([sys.executable, "-c",
                    "import sys,joblib,pandas as pd,numpy as np; m=joblib.load(sys.argv[1]); np.save(sys.argv[3],getattr(m,sys.argv[4])(pd.read_parquet(sys.argv[2])))",
                    str(path), str(sample_path), str(out), method], cwd=ROOT, capture_output=True, text=True, timeout=120)
                if child.returncode:
                    raise RuntimeError(child.stderr)
                np.testing.assert_allclose(np.load(out), getattr(model, method)(sample), rtol=1e-6, atol=1e-7)
                table = frame[["__key", "__date"]].copy()
                table["y"] = frame["__target" if rec["kind"] == "classification" else "__reg"]
                p = model.predict_proba(frame)[:, 1] if rec["kind"] == "classification" else model.predict(frame)
                table["prediction"] = p
                metrics = binary_metrics(table.y, p, model.threshold) if rec["kind"] == "classification" else regression_metrics(table.y, p)
                (self.output / "predictions").mkdir(exist_ok=True)
                table.to_parquet(self.output / "predictions" / f"{name}_2023.parquet", index=False)
                records[name] = {**rec, "historical_2023": metrics, "fresh_cpu_reload": "PASS"}
                if rec["kind"] == "classification":
                    records[name]["historical_2023_at_0_5"] = binary_metrics(table.y, p)
                self.event("historical_evaluated", model=name)
        write_json(self.output / "model_results.json", records)
        summary = {"status": "SMOKE_COMPLETE" if self.smoke else "MODELS_COMPLETE", "models": len(records),
                   "elapsed_seconds": self.elapsed(), "config": self.config, "smoke": self.smoke,
                   "historical_development_only": True, "v3_acceptance_not_claimed": True}
        write_json(self.output / "summary.json", summary)
        self.event("models_complete", status=summary["status"])

    def run(self):
        with prevent_sleep(), threadpool_limits(limits=self.config["budget"]["threads"]):
            if self.config["budget"]["prefer_gpu"]:
                try:
                    probe = xgb.XGBClassifier(n_estimators=1, device="cuda")
                    probe.fit(np.arange(40).reshape(20, 2), np.arange(20) % 2)
                    self.device = "cuda" if '"device":"cuda' in probe.get_booster().save_config() else "cpu"
                except xgb.core.XGBoostError:
                    pass
            self.event("training_started", device=self.device)
            # All tuning precedes expensive nested OOF/final fitting, within 8h.
            specs = {(task, kind): self.tune(task, kind) for task in self.config["tasks"] for kind in self.config["kinds"]}
            for task, kind in specs:
                completed = all(f"{task}_{kind}_{family}" in self.state["models"] for family in self.config["families"])
                if kind == "regression":
                    completed = completed and (self.output / "models" / f"{task}_residuals.joblib").exists()
                if not completed:
                    self.target(task, kind, specs[task, kind])
            self.evaluate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/thesis_completion.yaml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        if not args.output:
            parser.error("--status requires --output")
        print((args.output / "progress.json").read_text(encoding="utf-8"))
        return
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if (config["version"] != "thesis_completion_v1" or config["training_years"] != list(range(2016, 2023))
        or config["validation_years"] != [2019, 2020, 2021, 2022] or config["evaluation_year"] != 2023
        or config["tasks"] != ["arrival", "departure"] or config["kinds"] != ["classification", "regression"]
        or config["weather"] or config["flight_chain"] or config["cutoff_hours"] != 2
        or config["delay_minutes"] != 15 or not 0 < config["budget"]["total_hours"] <= 24):
        parser.error("Frozen proposal data/task contracts cannot be overridden")
    output = (args.output or ROOT / "artifacts/thesis_completion" / datetime.now().strftime("%Y%m%d_%H%M%S")).resolve()
    runner = Training(output, config, smoke=args.smoke, resume=args.resume)
    lock = output / "training.lock.json"
    owner = {"pid": os.getpid(), "created": psutil.Process().create_time()}
    if lock.exists():
        existing = json.loads(lock.read_text())
        try:
            active = psutil.Process(existing["pid"]).create_time() == existing["created"]
        except psutil.NoSuchProcess:
            active = False
        if active:
            raise RuntimeError("This run already has a live training worker; use --status")
        lock.unlink()
    with lock.open("x", encoding="utf-8") as stream:
        json.dump(owner, stream)
    try:
        runner.run()
    except Exception as exc:
        write_json(output / "summary.json", {"status": "INCOMPLETE" if isinstance(exc, FitIncomplete) else "FAILED",
                   "error": str(exc), "traceback": traceback.format_exc(), "smoke": args.smoke})
        runner.event("failed", error=str(exc))
        raise
    finally:
        if lock.exists() and json.loads(lock.read_text()) == owner:
            lock.unlink()
