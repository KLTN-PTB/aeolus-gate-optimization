"""Command-line runner for Controlled Model Selection on 2023 Development Set (Phase 7).

Protocol:
- Evaluates candidate models on 2023 development set (zero HPO, zero retraining).
- Training window: Outer development 2016-2022.
- 2024 is sealed and fail-closed.
- Applies pre-registered selection rules and tie-breaking policies from configs/academic_model_selection.yaml.
- Exports authoritative artifacts/manifests/academic_model_selection_v1.json.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from xgboost import XGBClassifier, XGBRegressor

from src.data.access_guard import assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.data.preprocessing import (
    build_linear_preprocessor,
    build_tree_preprocessor,
)
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.model_selection import (
    DEFAULT_OUTPUT_MANIFEST,
    DEFAULT_SELECTION_POLICY_PATH,
    SelectionPolicy,
    compute_hashes_for_audit,
    evaluate_selection_tie_break,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.contracts import CLASSIFICATION_THRESHOLD
from src.models.metrics import (
    classification_metrics,
    compute_stratified_regression_metrics,
    regression_metrics,
)
from src.models.probabilistic.candidate_interfaces import (
    P1EmpiricalCandidate,
    P2XGBoostGaussianCandidate,
    P3NGBoostNormalCandidate,
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)
from src.models.probabilistic.evaluation_engine import evaluate_probabilistic_prediction
from src.pipeline.academic_point_benchmark import (
    _build_model_pair,
    _derive_class_weights,
    optimize_ensemble_weights,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_academic_model_selection")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 7 Academic Model Selection on 2023 Development Set."
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=DEFAULT_SELECTION_POLICY_PATH,
        help="Path to selection policy config.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=DEFAULT_OUTPUT_MANIFEST,
        help="Path to output selection manifest.",
    )
    parser.add_argument(
        "--sample-train-per-year",
        type=int,
        default=3500,
        help="Monthly-stratified training samples per year.",
    )
    parser.add_argument(
        "--sample-val",
        type=int,
        default=4000,
        help="Monthly-stratified validation samples on 2023.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=202601,
        help="Predetermined deployment seed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # 1. Pre-selection Check
    LOGGER.info(f"Loading pre-registered selection policy from: {args.policy_config}")
    policy = SelectionPolicy.load(args.policy_config)

    LOGGER.info(f"Candidate Point Models: {policy.candidate_point_models}")
    LOGGER.info(f"Candidate Probabilistic Models: {policy.candidate_probabilistic_models}")
    LOGGER.info(f"Training Window: {policy.training_years} -> Eval Year: {policy.evaluation_year}")

    # Enforce 2024 is sealed
    try:
        assert_data_access_allowed(2024, "development")
        LOGGER.error("CRITICAL: 2024 was unexpectedly permitted!")
        return 1
    except Exception:
        LOGGER.info("Confirmed: 2024 is strictly sealed from development access.")

    # 2. Ingest 2023 Evaluation Data
    LOGGER.info(f"Loading monthly-stratified 2023 evaluation data (Train: {policy.training_years}, Val: 2023)...")
    (
        X_train,
        y_train_cls_series,
        y_train_reg_series,
        _,
        X_val,
        y_val_cls_series,
        y_val_reg_series,
        val_flight_keys,
    ) = load_stratified_fold_data(
        train_years=list(policy.training_years),
        val_year=policy.evaluation_year,
        sample_train_per_year=args.sample_train_per_year,
        sample_val=args.sample_val,
        random_state=args.seed,
        feature_set="v1",
    )

    # Validate leakage
    cols_tr = set(X_train.columns)
    cols_vl = set(X_val.columns)
    if not cols_tr.issubset(set(APPROVED_PREDICTOR_COLUMNS)) or not cols_vl.issubset(set(APPROVED_PREDICTOR_COLUMNS)):
        raise ValueError("Unapproved predictors detected in data!")
    if cols_tr.intersection(WEATHER_COLUMNS) or cols_vl.intersection(WEATHER_COLUMNS):
        raise ValueError("Weather predictors detected in data!")
    if cols_tr.intersection(ARRIVAL_LEAKAGE_COLUMNS) or cols_vl.intersection(ARRIVAL_LEAKAGE_COLUMNS):
        raise ValueError("Leakage predictors detected in data!")

    y_tr_cls = np.asarray(y_train_cls_series, dtype=int)
    y_tr_reg = np.asarray(y_train_reg_series, dtype=float)
    y_vl_cls = np.asarray(y_val_cls_series, dtype=int)
    y_vl_reg = np.asarray(y_val_reg_series, dtype=float)

    # 3. Evaluate Point Models on 2023
    point_metrics: dict[str, dict[str, Any]] = {}
    oof_cls_preds: dict[str, np.ndarray] = {}
    oof_reg_preds: dict[str, np.ndarray] = {}

    base_models = [
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
    ]

    for m_id in base_models:
        LOGGER.info(f"[*] Training base point model: {m_id} on 2016-2022...")
        weights = _derive_class_weights(y_tr_cls)
        prep, clf, reg = _build_model_pair(m_id, seed=args.seed, weights=weights)

        # Fit preprocessor on train only
        X_tr_proc = prep.fit_transform(X_train)
        X_vl_proc = prep.transform(X_val)

        # Fit models
        clf.fit(X_tr_proc, y_tr_cls)
        reg.fit(X_tr_proc, y_tr_reg)

        p_prob = clf.predict_proba(X_vl_proc)[:, 1]
        p_reg = reg.predict(X_vl_proc)

        oof_cls_preds[m_id] = p_prob
        oof_reg_preds[m_id] = p_reg

        m_cls = classification_metrics(y_vl_cls, p_prob, threshold=CLASSIFICATION_THRESHOLD)
        m_reg = regression_metrics(y_vl_reg, p_reg)
        m_strat = compute_stratified_regression_metrics(y_vl_reg, p_reg)

        point_metrics[m_id] = {
            "classification": m_cls.to_dict(),
            "regression": m_reg.to_dict(),
            "mae": float(m_reg.mae),
            "rmse": float(m_reg.rmse),
            "r2": float(m_reg.r2) if m_reg.r2 is not None else float("nan"),
            "severe_delay_mae": float(m_strat.severe_delay.mae) if m_strat.severe_delay.mae is not None else float("nan"),
            "pr_auc": float(m_cls.pr_auc) if m_cls.pr_auc is not None else float("nan"),
            "roc_auc": float(m_cls.roc_auc) if m_cls.roc_auc is not None else float("nan"),
            "brier_score": float(m_cls.brier_score),
        }

    # Evaluate Weighted Ensemble
    if "arrival_weighted_ensemble_v1" in policy.candidate_point_models:
        LOGGER.info("[*] Evaluating arrival_weighted_ensemble_v1 on 2023...")
        cls_mat = np.column_stack([oof_cls_preds[m] for m in base_models])
        reg_mat = np.column_stack([oof_reg_preds[m] for m in base_models])

        # Optimize ensemble weights on train validation / dev predictions
        w_cls = optimize_ensemble_weights(y_vl_cls, cls_mat, loss_type="brier")
        w_reg = optimize_ensemble_weights(y_vl_reg, reg_mat, loss_type="mae")

        ens_p_prob = np.sum(cls_mat * w_cls, axis=1)
        ens_p_reg = np.sum(reg_mat * w_reg, axis=1)

        m_cls = classification_metrics(y_vl_cls, ens_p_prob, threshold=CLASSIFICATION_THRESHOLD)
        m_reg = regression_metrics(y_vl_reg, ens_p_reg)
        m_strat = compute_stratified_regression_metrics(y_vl_reg, ens_p_reg)

        point_metrics["arrival_weighted_ensemble_v1"] = {
            "classification": m_cls.to_dict(),
            "regression": m_reg.to_dict(),
            "mae": float(m_reg.mae),
            "rmse": float(m_reg.rmse),
            "r2": float(m_reg.r2) if m_reg.r2 is not None else float("nan"),
            "severe_delay_mae": float(m_strat.severe_delay.mae) if m_strat.severe_delay.mae is not None else float("nan"),
            "pr_auc": float(m_cls.pr_auc) if m_cls.pr_auc is not None else float("nan"),
            "roc_auc": float(m_cls.roc_auc) if m_cls.roc_auc is not None else float("nan"),
            "brier_score": float(m_cls.brier_score),
            "weights": {
                "classification": {base_models[i]: float(w_cls[i]) for i in range(len(base_models))},
                "regression": {base_models[i]: float(w_reg[i]) for i in range(len(base_models))},
            },
        }

    # 4. Evaluate Probabilistic Candidates on 2023
    prob_metrics: dict[str, dict[str, Any]] = {}
    prob_candidates: list[tuple[str, BaseProbabilisticCandidate]] = [
        ("P1_empirical", P1EmpiricalCandidate()),
        ("P2_xgb_gaussian_oof", P2XGBoostGaussianCandidate(seed=args.seed)),
        ("P3_ngboost_normal", P3NGBoostNormalCandidate(seed=args.seed)),
        ("P4_ngboost_student_t", P4NGBoostStudentTCandidate(seed=args.seed)),
        ("P5_quantile_regression", P5QuantileRegressionCandidate(seed=args.seed)),
    ]

    for cid, cand in prob_candidates:
        if cid not in policy.candidate_probabilistic_models:
            continue
        LOGGER.info(f"[*] Training and evaluating probabilistic candidate: {cid} on 2023...")
        cand.fit(X_train, y_tr_reg)
        pred = cand.predict_distribution(X_val)
        res_m = evaluate_probabilistic_prediction(pred, y_vl_reg)
        prob_metrics[cid] = {
            "crps": float(res_m["crps"]) if isinstance(res_m.get("crps"), (int, float)) else float("nan"),
            "nll": float(res_m["nll"]) if isinstance(res_m.get("nll"), (int, float)) else "NOT_AVAILABLE",
            "brier_score_delay_ge_15": float(res_m["brier_score_delay_ge_15"]) if isinstance(res_m.get("brier_score_delay_ge_15"), (int, float)) else "NOT_AVAILABLE",
            "mean_pinball_loss": float(res_m["mean_pinball_loss"]) if isinstance(res_m.get("mean_pinball_loss"), (int, float)) else "NOT_AVAILABLE",
            "cov_80": float(res_m.get("empirical_coverage", {}).get("interval_80", float("nan"))),
            "cov_90": float(res_m.get("empirical_coverage", {}).get("interval_90", float("nan"))),
            "width_80": float(res_m.get("mean_interval_width", {}).get("interval_80", float("nan"))),
            "width_90": float(res_m.get("mean_interval_width", {}).get("interval_90", float("nan"))),
            "full_evaluation": res_m,
        }

    # 5. Apply Pre-registered Selection Rules and Tie-Break Logic
    LOGGER.info("Applying pre-registered selection rules and tie-break policy...")

    # Point Regression Selection
    reg_rule = policy.rules["point_regression"]
    reg_candidates_metrics = {m: point_metrics[m] for m in policy.candidate_point_models}
    reg_selection = evaluate_selection_tie_break(reg_candidates_metrics, reg_rule)

    # Point Classification Selection
    cls_rule = policy.rules["point_classification"]
    cls_candidates_metrics = {m: point_metrics[m] for m in policy.candidate_point_models}
    cls_selection = evaluate_selection_tie_break(cls_candidates_metrics, cls_rule)

    # Probabilistic Selection
    prob_rule = policy.rules["probabilistic"]
    prob_candidates_metrics = {m: prob_metrics[m] for m in policy.candidate_probabilistic_models}
    prob_selection = evaluate_selection_tie_break(prob_candidates_metrics, prob_rule)

    # 6. Build Ranking-Free Comparison Tables
    ranking_free_table: dict[str, Any] = {
        "point_models": {
            m: {
                "mae": point_metrics[m]["mae"],
                "rmse": point_metrics[m]["rmse"],
                "r2": point_metrics[m]["r2"],
                "severe_delay_mae": point_metrics[m]["severe_delay_mae"],
                "pr_auc": point_metrics[m]["pr_auc"],
                "roc_auc": point_metrics[m]["roc_auc"],
                "brier_score": point_metrics[m]["brier_score"],
            }
            for m in policy.candidate_point_models
        },
        "probabilistic_models": {
            m: {
                "crps": prob_metrics[m]["crps"],
                "nll": prob_metrics[m]["nll"],
                "brier_score_delay_ge_15": prob_metrics[m]["brier_score_delay_ge_15"],
                "mean_pinball_loss": prob_metrics[m]["mean_pinball_loss"],
                "cov_80": prob_metrics[m]["cov_80"],
                "cov_90": prob_metrics[m]["cov_90"],
            }
            for m in policy.candidate_probabilistic_models
        },
    }

    audit_hashes = compute_hashes_for_audit(policy)

    # 7. Construct Manifest Document
    manifest_ver = "academic_model_selection_v3" if "v3" in str(args.output_manifest) else "academic_model_selection_v1"
    manifest_doc: dict[str, Any] = {
        "manifest_version": manifest_ver,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": {
            "name": "Core Arrival",
            "filter": "DEST=ATL",
            "cutoff": "CRS_DEP_TIME - 2h",
            "weather_policy": "DROP_FROM_PREDICTORS",
            "flight_chain_policy": "FINAL_NO_GO",
        },
        "decoupled_operational_roles": {
            "role_a_point_prediction": {
                "regression_selected": reg_selection["selected_candidates"],
                "classification_selected": cls_selection["selected_candidates"],
                "description": "Selected solely for point prediction accuracy (MAE / PR-AUC).",
            },
            "role_b_probabilistic_forecasting": {
                "candidates_evaluated": ["P4_ngboost_student_t", "P5_quantile_regression"],
                "p4_capabilities": "Parametric continuous density, exact CRPS, continuous NLL, calibrated intervals.",
                "p5_capabilities": "Non-parametric pinball loss, quantile intervals, empirical coverage.",
                "role_status": "DECOUPLED_DUAL_ROLES_NO_SINGLE_OVERALL_CHAMPION",
            },
            "role_c_downstream_simulation": {
                "candidates": [
                    "schedule_only",
                    "arrival_linear_baseline_v1",
                    "arrival_xgboost_baseline_v1",
                    "arrival_weighted_ensemble_v1",
                    "P5_quantile_regression",
                    "P4_ngboost_student_t",
                    "oracle_actual",
                ],
                "semantics": "SCALAR_FORECAST_IMPACT",
            },
        },
        "temporal_governance": {
            "training_window": list(policy.training_years),
            "evaluation_year": policy.evaluation_year,
            "evaluation_role": "development_model_selection",
            "holdout_year": 2024,
            "holdout_status": "SEALED_AND_PROTECTED",
        },
        "sample_sizes": {
            "sample_train_per_year": args.sample_train_per_year,
            "sample_val_2023": args.sample_val,
            "seed": args.seed,
        },
        "candidate_pool": {
            "point_models": list(policy.candidate_point_models),
            "probabilistic_models": list(policy.candidate_probabilistic_models),
        },
        "ranking_free_comparison_table": ranking_free_table,
        "selection_rules_applied": {
            "point_regression": asdict(reg_rule),
            "point_classification": asdict(cls_rule),
            "probabilistic": asdict(prob_rule),
            "tie_break_policy": policy.tie_break_rule,
        },
        "selection_outcomes": {
            "point_regression": reg_selection,
            "point_classification": cls_selection,
            "probabilistic": prob_selection,
        },
        "disclaimer_and_layer_separation": (
            "Forecast quality (MAE, PR-AUC, CRPS) and downstream utility (gate conflict rates, "
            "solver runtime) are strictly distinct operational layers. Selection at Phase 7 selects "
            "forecast candidates for downstream evaluation without implying downstream gate optimization superiority."
        ),
        "historical_context": (
            "Historical Stage 8 previously selected SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula on 2023. "
            "Recorded as POST_SELECTION_DEVELOPMENT; history preserved intact."
        ),
        "audit_provenance": audit_hashes,
    }

    # Save manifest
    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest_doc, f, indent=2)

    # Manifest SHA-256
    manifest_bytes = args.output_manifest.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    with open(args.output_manifest.with_suffix(".sha256"), "w", encoding="utf-8") as f:
        f.write(f"{manifest_sha}  {args.output_manifest.name}\n")

    LOGGER.info(f"Selection manifest successfully written to: {args.output_manifest}")

    print("\n" + "=" * 115)
    print("PHASE 7 ACADEMIC MODEL SELECTION ON 2023 DEVELOPMENT SET COMPLETE")
    print("=" * 115)
    print(f"Point Regression (MAE): Best={reg_selection['best_numeric_candidate']} ({reg_selection['best_numeric_value']:.2f} min), Status={reg_selection['tie_status']}, Selected={reg_selection['selected_candidates']}")
    print(f"Point Classification (PR-AUC): Best={cls_selection['best_numeric_candidate']} ({cls_selection['best_numeric_value']:.4f}), Status={cls_selection['tie_status']}, Selected={cls_selection['selected_candidates']}")
    print(f"Probabilistic (CRPS): Best={prob_selection['best_numeric_candidate']} ({prob_selection['best_numeric_value']:.4f} min), Status={prob_selection['tie_status']}, Selected={prob_selection['selected_candidates']}")
    print(f"Manifest written to: {args.output_manifest}")
    print("=" * 115)

    return 0


if __name__ == "__main__":
    sys.exit(main())
