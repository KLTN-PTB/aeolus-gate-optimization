"""Authoritative frozen HPO inputs for Week-5 tuned development OOF refits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.run_week5_hist_gradient_boosting_hpo_v1_1 import _sqlite_state_evidence
from src.models.hpo import HPOFoldContext
from src.models.rolling import EstimatorBundle, FoldContext
from src.models.week5_contracts import load_week5_study_specs
from src.models.week5_hist_gradient_boosting_hpo import build_week5_hist_gradient_boosting_estimator
from src.models.week5_hpo_protocol import Week5HPOProtocol, Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import deterministic_v1_1_storage_path
from src.models.week5_random_forest_hpo import build_week5_random_forest_estimator
from src.models.week5_xgboost_hpo import build_week5_xgboost_hpo_estimator


PROTOCOL_HASH = "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"
_METHODS = ("random_forest", "hist_gradient_boosting", "xgboost")
_SUMMARY_PATHS = {
    "random_forest": Path("artifacts/manifests/week5_random_forest_hpo_v1_1_summary_v4.json"),
    "hist_gradient_boosting": Path("artifacts/manifests/week5_hist_gradient_boosting_hpo_v1_1_summary_v1.json"),
    "xgboost": Path("artifacts/manifests/week5_xgboost_hpo_v1_1_summary_v1.json"),
}


@dataclass(frozen=True)
class TunedMethodInputs:
    method_id: str
    protocol_hash: str
    classification_params: dict[str, Any]
    regression_params: dict[str, Any]
    summary_path: str
    summary_sha256: str
    classification_result_path: str
    classification_result_sha256: str
    regression_result_path: str
    regression_result_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week5ProtocolViolation(f"authoritative {label} is unreadable") from error
    if not isinstance(value, dict):
        raise Week5ProtocolViolation(f"authoritative {label} is malformed")
    return value


def _result_path(method: str, task: str) -> Path:
    return Path(f"artifacts/manifests/week5_hpo_protocol_v1_1__{method}_{task}_result_v1.json")


def load_tuned_method_inputs(
    root: Path, protocol: Week5HPOProtocol
) -> dict[str, TunedMethodInputs]:
    """Load frozen parameters only after manifest-to-SQLite agreement checks."""

    root = Path(root).resolve()
    if protocol.protocol_hash != PROTOCOL_HASH:
        raise Week5ProtocolViolation("authoritative tuned OOF protocol hash mismatch")
    specs = load_week5_study_specs(protocol)
    inputs: dict[str, TunedMethodInputs] = {}
    for method in _METHODS:
        summary_path = root / _SUMMARY_PATHS[method]
        summary = _read_json(summary_path, f"{method} summary")
        if summary.get("protocol_hash") != protocol.protocol_hash:
            raise Week5ProtocolViolation("authoritative summary protocol hash mismatch")
        if method != "random_forest" and summary.get("status") != "COMPLETED":
            raise Week5ProtocolViolation("authoritative HPO summary is not completed")
        task_data: dict[str, tuple[Path, dict[str, Any]]] = {}
        for task in ("classification", "regression"):
            study_id = f"{method}_{task}"
            result_path = root / _result_path(method, task)
            result = _read_json(result_path, f"{study_id} result")
            spec = specs[study_id]
            if (
                result.get("protocol_hash") != protocol.protocol_hash
                or result.get("study_id") != study_id
                or result.get("objective_match") is not True
                or result.get("best_params") is None
            ):
                raise Week5ProtocolViolation("authoritative result manifest is invalid")
            evidence = _sqlite_state_evidence(
                deterministic_v1_1_storage_path(root, study_id), spec.study_name
            )
            if (
                evidence["state_counts"].get("COMPLETE") != 10
                or evidence["state_counts"].get("RUNNING") != 0
                or evidence["best_trial"]["params"] != result["best_params"]
                or float(evidence["best_trial"]["value"]) != float(result["best_objective"])
            ):
                raise Week5ProtocolViolation("authoritative result disagrees with Optuna SQLite")
            summary_key = task if method == "random_forest" else study_id
            summary_study = summary.get("studies", {}).get(summary_key, {})
            if summary_study.get("best_params") != result["best_params"]:
                raise Week5ProtocolViolation("authoritative summary disagrees with result manifest")
            task_data[task] = (result_path, result)
        cls_path, cls_result = task_data["classification"]
        reg_path, reg_result = task_data["regression"]
        inputs[method] = TunedMethodInputs(
            method_id=method,
            protocol_hash=protocol.protocol_hash,
            classification_params=dict(cls_result["best_params"]),
            regression_params=dict(reg_result["best_params"]),
            summary_path=str(_SUMMARY_PATHS[method]),
            summary_sha256=_sha256(summary_path),
            classification_result_path=str(_result_path(method, "classification")),
            classification_result_sha256=_sha256(cls_path),
            regression_result_path=str(_result_path(method, "regression")),
            regression_result_sha256=_sha256(reg_path),
        )
    return inputs


def build_tuned_estimator_bundle_factory(
    inputs: TunedMethodInputs, protocol: Week5HPOProtocol
) -> Callable[[FoldContext], EstimatorBundle]:
    """Adapt frozen task-specific HPO factories to the shared rolling interface."""

    specs = load_week5_study_specs(protocol)
    cls_spec = specs[f"{inputs.method_id}_classification"]
    reg_spec = specs[f"{inputs.method_id}_regression"]
    factories = {
        "random_forest": build_week5_random_forest_estimator,
        "hist_gradient_boosting": build_week5_hist_gradient_boosting_estimator,
        "xgboost": build_week5_xgboost_hpo_estimator,
    }
    factory = factories[inputs.method_id]

    def build(context: FoldContext) -> EstimatorBundle:
        if context.spec.method_id != inputs.method_id or context.spec.seed != 202601:
            raise Week5ProtocolViolation("tuned OOF context does not match frozen method or seed")
        classification = factory(HPOFoldContext(
            fold=context.fold, method_id=cls_spec.method_id, model_family=cls_spec.model_family,
            task="classification", params=dict(inputs.classification_params),
            fixed_parameters=dict(cls_spec.fixed_parameters), seed=context.spec.seed,
            class_weights=context.class_weights,
        ))
        regression = factory(HPOFoldContext(
            fold=context.fold, method_id=reg_spec.method_id, model_family=reg_spec.model_family,
            task="regression", params=dict(inputs.regression_params),
            fixed_parameters=dict(reg_spec.fixed_parameters), seed=context.spec.seed,
            class_weights=None,
        ))
        return EstimatorBundle(classifier=classification, regressor=regression)

    return build
