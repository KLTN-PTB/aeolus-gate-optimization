"""Bounded real-data smoke for the Week-4 Logistic/Ridge baseline.

Reads only capped Core Arrival partitions for fold_1 (2016-2018 -> 2019).
It does not produce a production artifact or run all four production folds.
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
from src.models.linear_models import (  # noqa: E402
    LINEAR_BASELINE_VERSION,
    build_linear_estimators,
    load_linear_baseline_config,
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
    """Exercise unknown categories and missing values on a copy, never raw data."""

    features = getattr(prepared, "X").copy(deep=True)
    if len(features) < 3:
        raise AssertionError("bounded smoke requires at least three validation rows")
    features.loc[features.index[0], "OP_CARRIER"] = "__W4_SMOKE_UNKNOWN__"
    features.loc[features.index[1], "ORIGIN"] = np.nan
    features.loc[features.index[2], "CRS_ELAPSED_TIME"] = np.nan
    return replace(prepared, X=features)


def run_bounded_smoke(args: argparse.Namespace) -> dict[str, object]:
    fold = load_week4_rolling_folds()[0]
    train_raw = pd.concat(
        [
            load_arrival_development_batch(
                year,
                max_rows=args.rows_per_train_year,
                batch_size=args.batch_size,
            )
            for year in fold.train_years
        ],
        ignore_index=True,
    )
    validation_raw = load_arrival_development_batch(
        fold.validation_year,
        max_rows=args.validation_rows,
        batch_size=args.batch_size,
    )
    train = prepare_arrival_features(train_raw)
    validation = _smoke_validation_features(prepare_arrival_features(validation_raw))
    project = load_base_config(project_root=ROOT)
    baseline = load_linear_baseline_config(project_root=ROOT)
    spec = ExperimentSpec(
        method_id="linear",
        model_version=LINEAR_BASELINE_VERSION,
        config_version=project["project"]["version"],
        seed=project["reproducibility"]["project_seed"],
    )
    result, oof = run_fold_experiment(
        spec,
        fold=fold,
        data=FoldData(train=train, validation=validation),
        estimator_factory=lambda context: build_linear_estimators(context, config=baseline),
    )
    validate_oof_frame(oof)
    if tuple(oof.columns) != OOF_COLUMNS:
        raise AssertionError("OOF schema mismatch")
    if not np.isfinite(oof["p_arr_delay_15"]).all() or not oof["p_arr_delay_15"].between(0, 1).all():
        raise AssertionError("Logistic probabilities are invalid")
    if not np.isfinite(oof["predicted_arr_delay_min"]).all():
        raise AssertionError("Ridge predictions are invalid")
    if not bool((train.y_arr_reg < 0).any()):
        raise AssertionError("bounded training sample lost signed negative ground truth")
    if not result.preprocessor_state_unchanged_after_validation:
        raise AssertionError("validation mutated fitted training preprocessor state")
    return {
        "status": "PASS",
        "fold_id": fold.fold_id,
        "train_years": list(fold.train_years),
        "validation_year": fold.validation_year,
        "train_rows": len(train.X),
        "validation_rows": len(validation.X),
        "model_version": baseline.baseline_version,
        "classifier": "LogisticRegression",
        "regressor": "Ridge",
        "unknown_category_exercised": True,
        "missing_values_exercised": True,
        "signed_negative_train_targets": int((train.y_arr_reg < 0).sum()),
        "classification": result.classification.to_dict(),
        "regression": result.regression.to_dict(),
        "preprocessor_state_unchanged_after_validation": True,
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
