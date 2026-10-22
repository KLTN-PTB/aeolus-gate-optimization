"""Verified proposal profile and on-demand explanations; no implicit fallback."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd

from src.features.binary_improvement import prepare_frame
from src.models.binary_improvement_execution import digest
from src.simulation.native_dual_core_pipeline import StandardizedPredictionRecord

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "artifacts/thesis_completion/active_profile.json"


def artifact(record):
    path = (ROOT / record["path"]).resolve()
    allowed = (ROOT / "artifacts/thesis_completion").resolve()
    if not path.is_relative_to(allowed) or not path.is_file() or digest(path) != record["sha256"]:
        raise ValueError("Proposal artifact path/checksum is invalid")
    return path


def profile():
    if not ACTIVE.is_file():
        raise ValueError("Profile XGBoost chưa sẵn sàng. Cần hoàn tất và kiểm tra bộ model đề cương.")
    value = json.loads(ACTIVE.read_text(encoding="utf-8"))
    if value.get("profile") != "thesis_xgboost" or value.get("status") != "READY" or value.get("smoke"):
        raise ValueError("Proposal model profile is not qualified for inference")
    return value


def profiles():
    values = [{"id": "legacy_native", "label": "Native hiện có", "ready": True}]
    try:
        ready = profile()
        values.append({"id": "thesis_xgboost", "label": "Đề cương · XGBoost", "ready": True,
                       "model_run": ready["model_run"], "evaluation": ready.get("comparison")})
    except (ValueError, OSError, KeyError) as exc:
        values.append({"id": "thesis_xgboost", "label": "Đề cương · XGBoost", "ready": False, "reason": str(exc)})
    return values


def validate_release():
    """Fail setup when a portable dashboard release is incomplete or corrupt."""
    value = profile()
    expected = {f'{task}_{kind}_xgboost' for task in ('arrival', 'departure')
                for kind in ('classification', 'regression')}
    if set(value['models']) != expected or set(value['residuals']) != {'arrival', 'departure'}:
        raise ValueError('Proposal release must contain four XGBoost bundles and two residual banks')
    for record in (*value['models'].values(), *value['residuals'].values()):
        joblib.load(artifact(record))
    global_shap = ROOT / value['model_run'] / 'shap_global.json'
    if not global_shap.is_file():
        raise ValueError('Proposal global SHAP evidence is missing')
    json.loads(global_shap.read_text(encoding='utf-8'))
    for name in ('data/raw/ATL_20260701_02_schedule_raw.parquet',
                 'data/simulation/SCEN_2023_STRESS_1500_50.parquet',
                 'data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES.parquet',
                 'data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES_movements.parquet'):
        if not (ROOT / name).is_file():
            raise ValueError(f'Bundled dashboard scenario is missing: {name}')
    return value['version']


class ThesisInference:
    def __init__(self):
        self.profile = profile()

    def load_and_verify_models(self):
        models = {}
        for task in ("arrival", "departure"):
            reg = self.profile["models"][f"{task}_regression_xgboost"]
            cls = self.profile["models"][f"{task}_classification_xgboost"]
            models[task] = {"model": joblib.load(artifact(reg)), "classifier": joblib.load(artifact(cls)),
                "spec": SimpleNamespace(model_id=f"thesis_{task}_xgboost", status="proposal_profile", artifact_version=self.profile["version"]),
                "meta": {"sha256": reg["sha256"], "path": reg["path"], "classification_model_id": f"{task}_classification_xgboost",
                         "classification_model_sha256": cls["sha256"]}}
        return models

    def run_native_inference(self, inbound, outbound, models):
        result, lookup = [], {}
        for task, raw in (("arrival", inbound), ("departure", outbound)):
            if raw.empty:
                continue
            entry = models[task]
            canonical = canonical_schedule(raw)
            regression = entry["model"].predict_schedule(canonical)
            classification = entry["classifier"].predict_schedule(canonical)
            if regression.flight_key.tolist() != raw.flight_key.astype(str).tolist() or classification.flight_key.tolist() != regression.flight_key.tolist():
                raise ValueError("Proposal prediction keys differ from uploaded schedules")
            for i, row in enumerate(raw.to_dict("records")):
                fid, delay = str(row["flight_key"]), float(regression.predicted_delay_min.iloc[i])
                p = float(classification.p_delay.iloc[i])
                result.append(StandardizedPredictionRecord(fid, "ARR" if task == "arrival" else "DEP", "ATL",
                    str(row["prediction_cutoff_utc"]), entry["spec"].model_id, task, self.profile["version"],
                    entry["meta"]["sha256"], "schedule_only_F0", "ARR_DELAY" if task == "arrival" else "DEP_DELAY",
                    "arrival_delay_signed" if task == "arrival" else "departure_delay_signed", delay,
                    datetime.now(timezone.utc).isoformat(), "NATIVE_INFERENCE", probability_delay_15=p))
                lookup[fid] = delay
        return result, lookup

    def turns_to_flights(self, turns, models):
        # Independent profile qualification; legacy certification is never
        # relabelled or changed for these proposal artifacts.
        from src.models.thesis_models import ThesisBundle
        for task, entry in models.items():
            for key, kind in (('model', 'regression'), ('classifier', 'classification')):
                bundle = entry[key]
                if not isinstance(bundle, ThesisBundle) or (bundle.task, bundle.kind, bundle.family) != (task, kind, 'xgboost'):
                    raise ValueError('Proposal optimizer requires verified XGBoost classification and regression bundles')
        return [turn.to_flight(flight_index=i, dual_core_enabled=True) for i, turn in enumerate(turns)]


def sample_residual_delays(snapshot, scenarios, seed):
    """Predictive uncertainty from development OOF residuals, not upload labels."""
    uncertainty = snapshot["uncertainty"]
    banks = {task: joblib.load(artifact(record)) for task, record in uncertainty["residuals"].items()}
    ids = sorted(snapshot["predictions"])
    rng = np.random.default_rng(seed)
    columns = []
    for fid in ids:
        info = uncertainty["flights"][fid]
        bank = banks[info["task"]]
        values = np.asarray(bank.get(str(info["carrier"]), bank["global"]), dtype=float)
        if not len(values) or not np.isfinite(values).all():
            raise ValueError("Residual bank must be nonempty and finite")
        columns.append(snapshot["predictions"][fid] + rng.choice(values, size=scenarios))
    return ids, np.column_stack(columns) if columns else np.empty((scenarios, 0))


def canonical_schedule(raw):
    # Upload normalization stores YYYY-MM-DD; frozen training contracts require
    # the same date at 00:00:00. No timezone or observed event is inferred here.
    frame = raw.copy()
    dates = pd.to_datetime(frame['FL_DATE'])
    frame['FL_DATE'] = dates.dt.strftime('%Y-%m-%d 00:00:00')
    for name, values in (('MONTH',dates.dt.month),('DAY_OF_MONTH',dates.dt.day),('DAY_OF_WEEK',dates.dt.dayofweek+1)):
        if name not in frame:
            frame[name] = values
    return frame


def explain(raw, task, kind, *, model_record=None):
    """Explain one exact XGBoost checkpoint before probability calibration."""
    import shap
    record = model_record or profile()["models"][f"{task}_{kind}_xgboost"]
    bundle = joblib.load(artifact(record))
    x = bundle.encoder.transform(prepare_frame(canonical_schedule(raw), task, inference=True))
    explainer = shap.TreeExplainer(bundle.estimator, model_output="raw")
    explanation = explainer(x)
    contributions = np.asarray(explanation.values)
    base = np.asarray(explanation.base_values).reshape(-1)
    expected = bundle.estimator.predict(x, output_margin=True)
    np.testing.assert_allclose(base + contributions.sum(axis=1), expected, atol=1e-4, rtol=1e-5)
    names = bundle.encoder.feature_names()
    return {"model_sha256": record["sha256"], "task": task, "kind": kind,
        "output_space": "raw_margin_before_calibration" if kind == "classification" else "signed_delay_minutes",
        "features": names, "values": contributions.tolist(), "base_values": base.tolist(),
        "raw_predictions": np.asarray(expected).tolist(), "scope": "requested_schedule_rows_only"}
