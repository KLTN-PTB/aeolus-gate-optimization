"""Bounded, transformer-only Week 3A smoke on rolling-development partitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.preprocessing import (  # noqa: E402
    build_linear_preprocessor,
    build_tree_preprocessor,
    load_arrival_development_batch,
)
from src.data.temporal_protocol import ROLLING_DEVELOPMENT_YEARS  # noqa: E402
from src.features.tabular_features import (  # noqa: E402
    ARRIVAL_PROJECTED_SOURCE_COLUMNS,
    prepare_arrival_features,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-year", type=int, default=2016)
    parser.add_argument("--validation-year", type=int, default=2019)
    parser.add_argument("--train-rows", type=_positive_int, default=1024)
    parser.add_argument("--validation-rows", type=_positive_int, default=512)
    parser.add_argument("--batch-size", type=_positive_int, default=256)
    return parser


def _categories(transformer: object) -> tuple[tuple[object, ...], ...]:
    encoder = transformer.named_transformers_["categorical"].named_steps["encoder"]
    return tuple(tuple(values) for values in encoder.categories_)


def _validate_years(train_year: int, validation_year: int) -> None:
    if train_year not in ROLLING_DEVELOPMENT_YEARS:
        raise ValueError("train-year must remain within 2016-2022")
    if validation_year not in ROLLING_DEVELOPMENT_YEARS:
        raise ValueError("validation-year must remain within 2016-2022")
    if train_year >= validation_year:
        raise ValueError("train-year must be earlier than validation-year")


def run_bounded_smoke(args: argparse.Namespace) -> dict[str, object]:
    _validate_years(args.train_year, args.validation_year)
    train_raw = load_arrival_development_batch(
        args.train_year, max_rows=args.train_rows, batch_size=args.batch_size
    )
    validation_raw = load_arrival_development_batch(
        args.validation_year,
        max_rows=args.validation_rows,
        batch_size=args.batch_size,
    )
    train = prepare_arrival_features(train_raw)
    validation = prepare_arrival_features(validation_raw)

    shapes: dict[str, dict[str, list[int]]] = {}
    for name, builder in (
        ("linear", build_linear_preprocessor),
        ("tree", build_tree_preprocessor),
    ):
        transformer = builder()
        transformed_train = transformer.fit_transform(train.X)
        names_before = tuple(transformer.get_feature_names_out())
        statistics_before = transformer.named_transformers_["numeric"].named_steps[
            "imputer"
        ].statistics_.copy()
        categories_before = _categories(transformer)
        transformed_validation = transformer.transform(validation.X)
        statistics_after = transformer.named_transformers_["numeric"].named_steps[
            "imputer"
        ].statistics_
        if not np.array_equal(statistics_before, statistics_after):
            raise AssertionError(f"{name} numeric state changed during validation transform")
        if categories_before != _categories(transformer):
            raise AssertionError(f"{name} category state changed during validation transform")
        if names_before != tuple(transformer.get_feature_names_out()):
            raise AssertionError(f"{name} output schema changed during validation transform")
        shapes[name] = {
            "train": list(transformed_train.shape),
            "validation": list(transformed_validation.shape),
        }

    if not train.X.index.equals(train.identifiers.index):
        raise AssertionError("Training identifiers are not aligned with X")
    if not validation.X.index.equals(validation.identifiers.index):
        raise AssertionError("Validation identifiers are not aligned with X")
    return {
        "status": "PASS",
        "train_year": args.train_year,
        "validation_year": args.validation_year,
        "train_raw_rows": len(train_raw),
        "train_eligible_rows": len(train.X),
        "validation_raw_rows": len(validation_raw),
        "validation_eligible_rows": len(validation.X),
        "batch_size": args.batch_size,
        "projected_columns": len(ARRIVAL_PROJECTED_SOURCE_COLUMNS),
        "approved_predictors": len(train.X.columns),
        "signed_negative_train_targets": int((train.y_arr_reg < 0).sum()),
        "transformed_shapes": shapes,
        "training_state_unchanged_after_validation": True,
        "model_trained": False,
        "row_level_2023_access": False,
        "row_level_2024_access": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_bounded_smoke(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
