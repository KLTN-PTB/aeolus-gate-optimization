"""Export all recorded model-training parameters and dataset scopes to Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import optuna
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("docs/model_training_parameters_all_datasets.md")
PROTOCOL_VERSION = "week5_hpo_protocol_v1_1"
PROTOCOL_HASH = "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"

BASELINE_CONFIGS = {
    "Linear / Ridge (Week 4)": Path("configs/week4_linear_baseline.yaml"),
    "Random Forest (Week 4)": Path("configs/week4_random_forest_baseline.yaml"),
    "HistGradientBoosting (Week 4)": Path(
        "configs/week4_hist_gradient_boosting_baseline.yaml"
    ),
    "XGBoost baseline (Prompt 03)": Path("configs/week5_xgboost_baseline.yaml"),
}
BASELINE_MANIFESTS = {
    "linear": Path("artifacts/manifests/arrival_linear_rolling_run_v1.json"),
    "random_forest": Path("artifacts/manifests/arrival_random_forest_rolling_run_v1.json"),
    "hist_gradient_boosting": Path(
        "artifacts/manifests/arrival_hist_gradient_boosting_rolling_run_v1.json"
    ),
    "xgboost": Path("artifacts/manifests/arrival_xgboost_rolling_run_v1.json"),
}
TUNED_MANIFESTS = {
    "Random Forest tuned": Path(
        "artifacts/manifests/arrival_random_forest_tuned_rolling_run_v1_1.json"
    ),
    "HistGradientBoosting tuned": Path(
        "artifacts/manifests/arrival_hist_gradient_boosting_tuned_rolling_run_v1_1.json"
    ),
    "XGBoost tuned": Path(
        "artifacts/manifests/arrival_xgboost_tuned_rolling_run_v1_1.json"
    ),
}
RESULT_MANIFESTS = {
    "random_forest_classification": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json"
    ),
    "random_forest_regression": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_regression_result_v1.json"
    ),
    "hist_gradient_boosting_classification": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__hist_gradient_boosting_classification_result_v1.json"
    ),
    "hist_gradient_boosting_regression": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__hist_gradient_boosting_regression_result_v1.json"
    ),
    "xgboost_classification": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_classification_result_v1.json"
    ),
    "xgboost_regression": Path(
        "artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
    ),
}
SUMMARY_MANIFEST = Path(
    "artifacts/manifests/week5_core_arrival_xgboost_optuna_summary_v1.json"
)
PROTOCOL_MANIFEST = Path("artifacts/manifests/week5_hpo_protocol_v1_1.json")
FEATURE_MANIFEST = Path("artifacts/manifests/feature_manifest_arrival_v1.json")
DATA_MANIFEST = Path("artifacts/manifests/processed_data_manifest_v1.json")
FOLD_MANIFEST = Path("artifacts/manifests/temporal_folds_manifest.json")


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    value = json.loads((root / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(root: Path, path: Path) -> str:
    absolute = path if path.is_absolute() else root / path
    if not absolute.exists():
        raise RuntimeError(f"missing source artifact: {absolute}")
    relative = absolute.resolve().relative_to(root.resolve()).as_posix()
    return f"`{relative}` (SHA-256: `{_sha256(absolute)}`)"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)


def _yaml_block(value: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True).rstrip()


def _metric_summary(manifest: Mapping[str, Any]) -> str:
    metrics = manifest.get("aggregate_development_metrics", {})
    cls = metrics.get("classification", {})
    reg = metrics.get("regression", {})
    return (
        f"PR-AUC={cls.get('pr_auc', 'n/a')}; ROC-AUC={cls.get('roc_auc', 'n/a')}; "
        f"Brier={cls.get('brier_score', 'n/a')}; MAE={reg.get('mae', 'n/a')}; "
        f"RMSE={reg.get('rmse', 'n/a')}; R²={reg.get('r2', 'n/a')}"
    )


def _study_uri(root: Path, storage: str) -> str:
    path = Path(storage)
    if not path.is_absolute():
        path = root / path
    return f"sqlite:///{path.resolve().as_posix()}"


def _load_trials(root: Path, result: Mapping[str, Any]) -> list[dict[str, Any]]:
    storage = str(result["storage_path"])
    study = optuna.load_study(study_name=str(result["study_name"]), storage=_study_uri(root, storage))
    rows = []
    for trial in study.trials:
        rows.append(
            {
                "number": trial.number,
                "state": trial.state.name,
                "value": trial.value,
                "params": trial.params,
                "datetime_start": trial.datetime_start.isoformat() if trial.datetime_start else None,
                "datetime_complete": trial.datetime_complete.isoformat() if trial.datetime_complete else None,
                "user_attrs": trial.user_attrs,
            }
        )
    return rows


def build_markdown(root: Path) -> str:
    root = root.resolve()
    protocol = _read_json(root, PROTOCOL_MANIFEST)
    feature = _read_json(root, FEATURE_MANIFEST)
    data = _read_json(root, DATA_MANIFEST)
    folds = _read_json(root, FOLD_MANIFEST)

    results = {study_id: _read_json(root, path) for study_id, path in RESULT_MANIFESTS.items()}
    tuned = {name: _read_json(root, path) for name, path in TUNED_MANIFESTS.items()}
    baselines = {method: _read_json(root, path) for method, path in BASELINE_MANIFESTS.items()}
    closeout = _read_json(root, SUMMARY_MANIFEST)

    if protocol["protocol_version"] != PROTOCOL_VERSION or protocol["protocol_sha256"] != PROTOCOL_HASH:
        raise RuntimeError("Week-5 protocol version/hash mismatch")
    for result in results.values():
        if result.get("protocol_hash") != PROTOCOL_HASH:
            raise RuntimeError("result manifest protocol hash mismatch")

    lines: list[str] = [
        "# Aeolus - Model Training Parameters Across All Recorded Datasets",
        "",
        f"> Generated: `{datetime.now(timezone.utc).isoformat()}`",
        ">",
        "> This file is a parameter/provenance inventory. It does not retrain models, alter parameters, or perform model selection.",
        "",
        "## 1. Scope and interpretation",
        "",
        "The inventory covers every recorded Arrival Core model run: Week-4 Linear/Ridge, Random Forest, HistGradientBoosting, the Prompt-03 XGBoost baseline, Week-5 Optuna HPO trials and best configurations, and Week-5 tuned OOF refits. Auxiliary Departure/Weather models, Weighted Ensemble, SHAP, 2023 selection, and ARR/DEP ablations were not trained in the recorded scope.",
        "",
        "## 2. Dataset and common information contract",
        "",
        f"- Dataset manifest: {_artifact(root, DATA_MANIFEST)}",
        f"- Feature manifest: {_artifact(root, FEATURE_MANIFEST)}",
        f"- Temporal fold manifest: {_artifact(root, FOLD_MANIFEST)}",
        "- Arrival population: inbound flights with `DEST=ATL`.",
        "- Prediction cutoff: `CRS_DEP_TIME - 2 hours`.",
        "- Classification target: `y_arr_cls = 1[ARR_DELAY >= 15]`.",
        "- Regression target: signed `ARR_DELAY` minutes (`y_arr_reg`).",
        "- Approved feature families: Schedule, Calendar, Carrier, Route.",
        f"- Final approved predictor columns ({len(feature.get('final_approved_predictor_columns', []))}): `{'`, `'.join(feature.get('final_approved_predictor_columns', []))}`.",
        "- Preprocessing fit boundary: each fold's training rows only.",
        "- Excluded predictors: Weather, DEP_DELAY, predicted Departure, actual operational outcomes, Chain, identifiers as predictors.",
        "",
        "### Dataset partitions and roles",
        "",
        "| Year | Role | Source rows | Inbound ATL rows | Outbound ATL rows |",
        "|---:|---|---:|---:|---:|",
    ]
    for year_info in data.get("years", []):
        partitions = {item.get("flow"): item.get("row_count") for item in year_info.get("partitions", [])}
        lines.append(
            f"| {year_info['year']} | {year_info['role']} | {year_info.get('source_rows', 'n/a'):,} | "
            f"{partitions.get('inbound_atl', 'n/a'):,} | {partitions.get('outbound_atl', 'n/a'):,} |"
        )
    lines.extend([
        "",
        "### Locked folds",
        "",
        "| Fold | Training years | Validation year |",
        "|---|---|---:|",
    ])
    for fold in protocol.get("folds", []):
        lines.append(f"| {fold['id']} | {', '.join(map(str, fold['train_years']))} | {fold['validation_year']} |")

    lines.extend([
        "",
        "## 3. Model inventory",
        "",
        "| Model/run | Dataset scope | Classifier | Regressor | Status |",
        "|---|---|---|---|---|",
        "| Linear / Ridge Week 4 | Arrival Core, rolling OOF 2016-2022 | LogisticRegression | Ridge | PASS / preserved |",
        "| Random Forest Week 4 baseline | Arrival Core, rolling OOF 2016-2022 | RandomForestClassifier | RandomForestRegressor | PASS / preserved |",
        "| HistGradientBoosting Week 4 baseline | Arrival Core, rolling OOF 2016-2022 | HistGradientBoostingClassifier | HistGradientBoostingRegressor | PASS / preserved |",
        "| XGBoost Prompt-03 baseline | Arrival Core, rolling OOF 2016-2022 | XGBClassifier | XGBRegressor | PASS / preserved |",
        "| Random Forest Week 5 tuned | Arrival Core, four locked folds | RandomForestClassifier | RandomForestRegressor | PASS |",
        "| HistGradientBoosting Week 5 tuned | Arrival Core, four locked folds | HistGradientBoostingClassifier | HistGradientBoostingRegressor | PASS |",
        "| XGBoost Week 5 tuned | Arrival Core, four locked folds | XGBClassifier | XGBRegressor | PASS |",
        "",
        "## 4. Week-4 baseline configurations",
        "",
        "The following blocks are complete YAML configurations, including estimator, regularization, sampling, resource, threshold, and HPO-policy fields.",
    ])
    for title, config_path in BASELINE_CONFIGS.items():
        config = yaml.safe_load((root / config_path).read_text(encoding="utf-8"))
        lines.extend([
            "",
            f"### {title}",
            "",
            f"Source: {_artifact(root, config_path)}",
            "",
            "```yaml",
            _yaml_block(config),
            "```",
        ])

    lines.extend([
        "",
        "## 5. Week-4 baseline results",
        "",
        "| Method | Model version | Rows | Pooled development diagnostics | Manifest |",
        "|---|---|---:|---|---|",
    ])
    for method, manifest in baselines.items():
        model = manifest.get("method", {})
        lines.append(
            f"| {method} | `{model.get('model_version')}` | {manifest.get('aggregate_development_metrics', {}).get('rows', 'n/a'):,} | "
            f"{_metric_summary(manifest)} | {_artifact(root, BASELINE_MANIFESTS[method])} |"
        )
    lines.extend([
        "",
        "## 6. Week-5 frozen HPO settings",
        "",
        f"Protocol: `{PROTOCOL_VERSION}`; hash: `{PROTOCOL_HASH}`.",
        "",
        "- Trials per study: 10 COMPLETE.",
        "- Sampler: TPESampler, seed 202601.",
        "- Pruner: NopPruner.",
        "- Optuna parallelism: 1; timeout: 14,400 seconds per study.",
        "- Classification objective: maximize equal-fold macro mean PR-AUC using `predict_proba`.",
        "- Regression objective: minimize equal-fold macro mean MAE on signed `ARR_DELAY`.",
        "- Reporting threshold: 0.5; threshold tuning disabled.",
        "",
        f"Protocol source: {_artifact(root, PROTOCOL_MANIFEST)}",
        "",
        "### Search spaces, fixed parameters, and selected parameters",
    ])
    for study_id in protocol.get("studies", {}):
        spec = protocol["studies"][study_id]
        result = results[study_id]
        lines.extend([
            "",
            f"#### `{study_id}`",
            "",
            f"- Study name: `{result['study_name']}`",
            f"- Direction/objective: `{result['direction']}` / `{result['objective_name']}`",
            f"- Best trial: `{result['best_trial']}`; best objective: `{result['best_objective']}`",
            f"- Result manifest: {_artifact(root, RESULT_MANIFESTS[study_id])}",
            f"- SQLite storage: `{result['storage_path']}`; SHA-256: `{result['storage_sha256']}`",
            "",
            "Frozen search space:",
            "```json",
            _json(spec.get("search_space", {})),
            "```",
            "",
            "Frozen fixed parameters:",
            "```json",
            _json(spec.get("fixed_parameters", {})),
            "```",
            "",
            "Selected best parameters:",
            "```json",
            _json(result.get("best_params", {})),
            "```",
        ])

    lines.extend([
        "",
        "### Every recorded HPO trial configuration",
        "",
        "The tables below are read-only projections of the six authoritative Optuna SQLite studies. They include every recorded trial state, objective value, parameter set, and timestamps.",
    ])
    for study_id, result in results.items():
        lines.extend([
            "",
            f"#### `{study_id}`",
            "",
            "| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |",
            "|---:|---|---:|---|---|---|",
        ])
        for trial in _load_trials(root, result):
            params = json.dumps(trial["params"], ensure_ascii=False, sort_keys=True, separators=(", ", ": "))
            value = "n/a" if trial["value"] is None else str(trial["value"])
            lines.append(
                f"| {trial['number']} | {trial['state']} | {value} | `{params}` | "
                f"{trial['datetime_start'] or 'n/a'} | {trial['datetime_complete'] or 'n/a'} |"
            )

    lines.extend([
        "",
        "## 7. Tuned Week-5 OOF refit configurations",
        "",
        "These are deterministic refits from the frozen best parameters above; no additional tuning was performed.",
    ])
    for title, manifest in tuned.items():
        method = manifest.get("method", {})
        lines.extend([
            "",
            f"### {title}",
            "",
            f"- Run version: `{manifest.get('run_version')}`",
            f"- Method: `{method.get('method_id')}`; seed: `{method.get('seed')}`",
            f"- Feature manifest: `{method.get('feature_manifest_version')}`",
            f"- Preprocessing: `{method.get('preprocessing_version')}`",
            f"- OOF schema: `{manifest.get('oof_schema_version')}`",
            f"- Rows: `{manifest.get('aggregate_development_metrics', {}).get('rows'):,}`",
            f"- HPO linkage: `{manifest.get('hpo_result_source', {})}`",
            "",
            "Frozen parameters:",
            "```json",
            _json(manifest.get("frozen_best_params", {})),
            "```",
            "",
            f"Pooled development diagnostics: {_metric_summary(manifest)}",
            "",
            "| Fold | Train years | Validation year | Rows | OOF artifact |",
            "|---|---|---:|---:|---|",
        ])
        for fold in manifest.get("folds", []):
            lines.append(
                f"| {fold['fold_id']} | {', '.join(map(str, fold['train_years']))} | {fold['validation_year']} | "
                f"{fold['oof_rows']:,} | `{fold['oof_artifact']}` |"
            )
        lines.append(f"\nFinal manifest: {_artifact(root, TUNED_MANIFESTS[title])}")

    lines.extend([
        "",
        "## 8. Week-5 final status and boundaries",
        "",
        f"Authoritative closeout: {_artifact(root, SUMMARY_MANIFEST)}",
        f"- Protocol: `{closeout['protocol']['version']}` / `{closeout['protocol']['hash']}`.",
        f"- Status: `{closeout['week5_final_status']}`; Week 5 completed: `{closeout['week5_completed']}`.",
        f"- OOF parity: `{closeout['oof']['row_parity']}` row parity, `{closeout['oof']['target_parity']}` target parity; {closeout['oof']['common_rows']:,} common rows.",
        "- No 2023 HPO or model selection; no row-level 2024 access.",
        "- Weather, predicted Departure, DEP_DELAY, actual operational outcomes, and Chain predictors were not used.",
        "- ARR-B disabled; auxiliary Weather not run because point-in-time provenance remains AUDIT_REQUIRED.",
        "- Weighted Ensemble, SHAP, 2023 selection, and controlled ablations remain Week-6 work and were not started.",
        "",
        "## 9. Important interpretation",
        "",
        "The listed metrics are development OOF diagnostics for 2016-2022. They are not final 2024 holdout results and are not a model-champion decision. The original interrupted RF protocol-v1 attempt remains historical evidence and is not counted as an additional completed production study.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    root = ROOT.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing export: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(root), encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(output), "sha256": _sha256(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
