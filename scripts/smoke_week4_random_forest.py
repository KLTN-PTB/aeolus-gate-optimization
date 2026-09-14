"""Bounded real-data smoke for the Week-4 Core Arrival Random Forest baseline.

Uses only fold_1 development years and capped row reads.  This script is not a
production rolling run and does not write production artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.load_aeolus import load_base_config  # noqa: E402
from src.data.preprocessing import load_arrival_development_batch  # noqa: E402
from src.features.tabular_features import prepare_arrival_features  # noqa: E402
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame  # noqa: E402
from src.models.contracts import ExperimentSpec, FoldData, load_week4_rolling_folds  # noqa: E402
from src.models.random_forest_models import (  # noqa: E402
    RANDOM_FOREST_BASELINE_VERSION,
    build_random_forest_estimators,
    load_random_forest_baseline_config,
)
from src.models.rolling import run_fold_experiment  # noqa: E402


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-per-train-year", type=_positive_int, default=128)
    parser.add_argument("--validation-rows", type=_positive_int, default=128)
    parser.add_argument("--batch-size", type=_positive_int, default=128)
    return parser


def _smoke_validation_features(prepared: object) -> object:
    """Exercise tree-preprocessor unknown/missing handling on a copy only."""

    features = getattr(prepared, "X").copy(deep=True)
    if len(features) < 3:
        raise AssertionError("bounded smoke requires at least three validation rows")
    features.loc[features.index[0], "OP_CARRIER"] = "__W4_RF_SMOKE_UNKNOWN__"
    features.loc[features.index[1], "ORIGIN"] = np.nan
    features.loc[features.index[2], "CRS_ELAPSED_TIME"] = np.nan
    return replace(prepared, X=features)


def _run_once(spec: ExperimentSpec, data: FoldData) -> tuple[object, pd.DataFrame]:
    config = load_random_forest_baseline_config(project_root=ROOT)
    fold = load_week4_rolling_folds(project_root=ROOT)[0]
    return run_fold_experiment(
        spec,
        fold=fold,
        data=data,
        estimator_factory=lambda context: build_random_forest_estimators(context, config=config),
    )


def run_bounded_smoke(args: argparse.Namespace) -> dict[str, object]:
    fold = load_week4_rolling_folds(project_root=ROOT)[0]
    train_raw = pd.concat(
        [
            load_arrival_development_batch(
                year,
                project_root=ROOT,
                max_rows=args.rows_per_train_year,
                batch_size=args.batch_size,
            )
            for year in fold.train_years
        ],
        ignore_index=True,
    )
    validation_raw = load_arrival_development_batch(
        fold.validation_year,
        project_root=ROOT,
        max_rows=args.validation_rows,
        batch_size=args.batch_size,
    )
    data = FoldData(
        train=prepare_arrival_features(train_raw),
        validation=_smoke_validation_features(prepare_arrival_features(validation_raw)),
    )
    project = load_base_config(project_root=ROOT)
    config = load_random_forest_baseline_config(project_root=ROOT)
    spec = ExperimentSpec(
        method_id="random_forest",
        model_version=RANDOM_FOREST_BASELINE_VERSION,
        config_version=project["project"]["version"],
        seed=project["reproducibility"]["project_seed"],
    )
    result_a, oof_a = _run_once(spec, data)
    result_b, oof_b = _run_once(spec, data)
    validate_oof_frame(oof_a)
    validate_oof_frame(oof_b)
    if tuple(oof_a.columns) != OOF_COLUMNS:
        raise AssertionError("OOF schema mismatch")
    if not np.isfinite(oof_a["p_arr_delay_15"]).all() or not oof_a["p_arr_delay_15"].between(0, 1).all():
        raise AssertionError("Random Forest probabilities are invalid")
    if not np.isfinite(oof_a["predicted_arr_delay_min"]).all():
        raise AssertionError("Random Forest regression predictions are invalid")
    if not bool((data.train.y_arr_reg < 0).any()):
        raise AssertionError("bounded training sample lost signed negative ground truth")
    probability_equal = np.array_equal(
        oof_a["p_arr_delay_15"].to_numpy(), oof_b["p_arr_delay_15"].to_numpy()
    )
    regression_equal = np.array_equal(
        oof_a["predicted_arr_delay_min"].to_numpy(), oof_b["predicted_arr_delay_min"].to_numpy()
    )
    if not probability_equal or not regression_equal:
        raise AssertionError("fixed-seed Random Forest smoke is not deterministic")
    return {
        "status": "PASS",
        "method": "random_forest",
        "fold_id": fold.fold_id,
        "train_years": list(fold.train_years),
        "validation_year": fold.validation_year,
        "train_rows": len(data.train.X),
        "validation_rows": len(data.validation.X),
        "model_version": config.baseline_version,
        "classifier": "RandomForestClassifier",
        "regressor": "RandomForestRegressor",
        "unknown_category_exercised": True,
        "missing_values_exercised": True,
        "signed_negative_train_targets": int((data.train.y_arr_reg < 0).sum()),
        "classification": getattr(result_a, "classification").to_dict(),
        "regression": getattr(result_a, "regression").to_dict(),
        "preprocessor_state_unchanged_after_validation": getattr(
            result_a, "preprocessor_state_unchanged_after_validation"
        ),
        "deterministic_probability_predictions": probability_equal,
        "deterministic_regression_predictions": regression_equal,
        "resources": {
            "fit": getattr(result_a, "fit_resources").to_dict(),
            "prediction": getattr(result_a, "prediction_resources").to_dict(),
            "peak_traced_python_bytes": getattr(result_a, "peak_memory_bytes"),
        },
        "resource_policy": {
            "n_jobs": config.n_jobs,
            "max_samples": None,
            "production_sampling_allowed": False,
        },
        "row_level_2023_access": False,
        "row_level_2024_access": False,
        "production_four_fold_run": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_bounded_smoke(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
