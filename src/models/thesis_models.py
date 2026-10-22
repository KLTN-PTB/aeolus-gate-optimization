"""Portable schedule-only models. No UI, dataset paths or training state required."""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge

from src.features.binary_improvement import ScheduleHistoryEncoder, prepare_frame
from src.data.preprocessing import build_linear_preprocessor, build_tree_preprocessor
from src.data.departure_preprocessing import build_departure_linear_preprocessor, build_departure_tree_preprocessor
from src.models.binary_improvement import positive_probability


class ScheduleEncoder:
    def __init__(self, task, linear=False):
        self.task, self.linear = task, linear

    def fit_transform(self, frame, y=None):
        self.engineer = ScheduleHistoryEncoder(self.task, "F0")
        x = self.engineer.fit_transform(frame, y)
        builders = {(False, "arrival"): build_tree_preprocessor,
                    (True, "arrival"): build_linear_preprocessor,
                    (False, "departure"): build_departure_tree_preprocessor,
                    (True, "departure"): build_departure_linear_preprocessor}
        self.preprocessor = builders[self.linear, self.task]()
        if self.linear:
            self.preprocessor.set_params(sparse_threshold=1.)
        return self.preprocessor.fit_transform(x)

    def transform(self, frame):
        return self.preprocessor.transform(self.engineer.transform(frame))

    def feature_names(self):
        return list(self.preprocessor.get_feature_names_out())


def meta_estimator(kind, seed=202601):
    return (LogisticRegression(C=1., max_iter=1000, random_state=seed)
            if kind == "classification" else Ridge(alpha=1.))


def temporal_meta_training(oof, validation_year, kind):
    """Only earlier OOF years may train the outer-fold meta learner."""
    earlier = oof.loc[oof.year < validation_year]
    if earlier.empty or earlier.flight_key.duplicated().any():
        raise ValueError("Meta training requires unique, strictly earlier OOF rows")
    x = earlier[["linear", "random_forest", "xgboost_fixed"]].to_numpy()
    y = earlier.y.to_numpy()
    model = meta_estimator(kind).fit(x, y)
    return model, {"first_year": int(earlier.year.min()), "last_year": int(earlier.year.max()),
                   "rows": len(earlier), "validation_year": validation_year}


@dataclass
class ThesisBundle:
    task: str
    kind: str
    family: str
    encoder: object = None
    estimator: object = None
    bases: list = field(default_factory=list)
    calibrator: object = None
    threshold: float = .5
    metadata: dict = field(default_factory=dict)

    def raw_predict(self, frame):
        if not len(frame):
            return np.empty(0)
        x = (np.column_stack([base.raw_predict(frame) for base in self.bases])
             if self.family == "stacking" else self.encoder.transform(frame))
        p = (positive_probability(self.estimator, x) if self.kind == "classification"
             else np.asarray(self.estimator.predict(x), dtype=float))
        if p.shape != (len(frame),) or not np.isfinite(p).all():
            raise ValueError("Malformed or non-finite model predictions")
        return p

    def predict(self, frame):
        p = self.raw_predict(frame)
        if self.kind == "classification":
            if self.calibrator is not None:
                p = self.calibrator.transform(p)
            return (p >= self.threshold).astype(np.int8)
        return p

    def predict_proba(self, frame):
        if self.kind != "classification":
            raise TypeError("A regressor cannot provide classification probabilities")
        p = self.raw_predict(frame)
        if self.calibrator is not None:
            p = self.calibrator.transform(p)
        return np.column_stack([1 - p, p])

    def predict_schedule(self, raw):
        frame = prepare_frame(raw, self.task, inference=True)
        result = pd.DataFrame({"flight_key": frame["__key"]})
        if self.kind == "classification":
            result["p_delay"] = self.predict_proba(frame)[:, 1]
            result["predicted_delayed"] = result.p_delay >= self.threshold
            result["decision_threshold"] = self.threshold
        else:
            result["predicted_delay_min"] = self.predict(frame)
        return result

    def to_cpu(self):
        if hasattr(self.estimator, "get_booster"):
            self.estimator.set_params(device="cpu", callbacks=None)
        for base in self.bases:
            base.to_cpu()
        self.metadata["inference_device"] = "cpu"
        return self


class CalibratedPredictor:
    """Stable equivalent of the historical script-local pickle wrapper."""
    def __init__(self, base_estimator, method="isotonic"):
        from sklearn.isotonic import IsotonicRegression
        self.base_estimator, self.method = base_estimator, method
        self.calibrator = IsotonicRegression(out_of_bounds="clip") if method == "isotonic" else LogisticRegression()

    def fit_calibration(self, x, y):
        raw = self.base_estimator.predict_proba(x)[:, 1]
        self.calibrator.fit(raw if self.method == "isotonic" else raw.reshape(-1, 1), y)
        return self

    def predict_proba(self, x):
        raw = self.base_estimator.predict_proba(x)[:, 1]
        if self.method == "isotonic":
            p = self.calibrator.predict(raw)
        else:
            p = self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        p = np.clip(p, 0., 1.)
        return np.column_stack([1 - p, p])

    def predict(self, x):
        return (self.predict_proba(x)[:, 1] >= .5).astype(int)
