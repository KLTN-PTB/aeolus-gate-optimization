"""Locked inner/outer expanding-window folds and early-stopping protocol.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 3.4
Rules:
- Outer validation must never be used to choose epochs or hyperparameters.
- For each fold:
    outer_train = [y1, ..., ym]
    outer_val   = ym+1
    inner_train = [y1, ..., ym-1]
    inner_val   = ym
- Workflow:
    1. Fit inner preprocessor on inner_train.
    2. Train on inner_train; select best_epoch from inner_val.
    3. Discard inner model weights.
    4. Fit fresh outer preprocessor on full outer_train.
    5. Train fresh model on full outer_train for exactly best_epoch epochs.
    6. Transform outer_val; evaluate once.
- 2023 and 2024 are strictly sealed from development splits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence

from src.data.access_guard import assert_data_access_allowed
from src.data.temporal_protocol import (
    FINAL_HOLDOUT_YEAR,
    MODEL_SELECTION_YEAR,
    ROLLING_DEVELOPMENT_YEARS,
)
from src.models.probabilistic.contracts import (
    ProbabilisticContractViolation,
    ProbabilisticTemporalError,
)


@dataclass(frozen=True)
class ProbabilisticInnerOuterFold:
    """Locked expanding-window partition with inner/outer split boundaries."""

    fold_id: str
    outer_train_years: tuple[int, ...]
    outer_val_year: int
    inner_train_years: tuple[int, ...]
    inner_val_year: int

    def __post_init__(self) -> None:
        # Sealed holdout guards
        all_years = set(self.outer_train_years) | {self.outer_val_year}
        if FINAL_HOLDOUT_YEAR in all_years:
            raise ProbabilisticTemporalError(
                f"2024 is sealed FINAL_HOLDOUT and prohibited from {self.fold_id}"
            )
        if MODEL_SELECTION_YEAR in all_years:
            raise ProbabilisticTemporalError(
                f"2023 is DEVELOPMENT_MODEL_SELECTION and prohibited from rolling {self.fold_id}"
            )

        # Check years within ROLLING_DEVELOPMENT_YEARS
        invalid_years = all_years.difference(ROLLING_DEVELOPMENT_YEARS)
        if invalid_years:
            raise ProbabilisticTemporalError(
                f"{self.fold_id} contains years outside rolling development (2016-2022): {sorted(invalid_years)}"
            )

        # Expanding window logic
        if self.outer_val_year <= max(self.outer_train_years):
            raise ProbabilisticTemporalError(
                f"{self.fold_id} outer validation year ({self.outer_val_year}) must strictly succeed outer train years"
            )
        if self.inner_val_year <= max(self.inner_train_years):
            raise ProbabilisticTemporalError(
                f"{self.fold_id} inner validation year ({self.inner_val_year}) must strictly succeed inner train years"
            )

        # Inner split must be strict subset of outer_train
        inner_all = set(self.inner_train_years) | {self.inner_val_year}
        if inner_all != set(self.outer_train_years):
            raise ProbabilisticTemporalError(
                f"{self.fold_id} inner split must partition outer_train exactly"
            )

        # Outer validation must NEVER leak into inner split
        if self.outer_val_year in inner_all:
            raise ProbabilisticTemporalError(
                f"{self.fold_id} outer validation leaks into inner split"
            )


FROZEN_PROBABILISTIC_FOLDS: Final[tuple[ProbabilisticInnerOuterFold, ...]] = (
    ProbabilisticInnerOuterFold(
        fold_id="fold_1",
        outer_train_years=(2016, 2017, 2018),
        outer_val_year=2019,
        inner_train_years=(2016, 2017),
        inner_val_year=2018,
    ),
    ProbabilisticInnerOuterFold(
        fold_id="fold_2",
        outer_train_years=(2016, 2017, 2018, 2019),
        outer_val_year=2020,
        inner_train_years=(2016, 2017, 2018),
        inner_val_year=2019,
    ),
    ProbabilisticInnerOuterFold(
        fold_id="fold_3",
        outer_train_years=(2016, 2017, 2018, 2019, 2020),
        outer_val_year=2021,
        inner_train_years=(2016, 2017, 2018, 2019),
        inner_val_year=2020,
    ),
    ProbabilisticInnerOuterFold(
        fold_id="fold_4",
        outer_train_years=(2016, 2017, 2018, 2019, 2020, 2021),
        outer_val_year=2022,
        inner_train_years=(2016, 2017, 2018, 2019, 2020),
        inner_val_year=2021,
    ),
)


def get_probabilistic_inner_outer_folds() -> tuple[ProbabilisticInnerOuterFold, ...]:
    """Return the frozen inner/outer temporal folds for probabilistic development."""
    return FROZEN_PROBABILISTIC_FOLDS


def assert_early_stopping_safety(
    fold: ProbabilisticInnerOuterFold,
    *,
    monitored_val_year: int,
    is_outer_training: bool,
    early_stopping_enabled: bool,
) -> None:
    """Enforce that early stopping is driven ONLY by inner validation.

    Outer training must use a fixed epoch count determined from inner validation,
    with early stopping disabled and no validation evaluation during training.
    """
    if is_outer_training and early_stopping_enabled:
        raise ProbabilisticTemporalError(
            f"Outer training on {fold.fold_id} cannot use early stopping or monitor validation loss"
        )
    if is_outer_training and monitored_val_year == fold.outer_val_year:
        raise ProbabilisticTemporalError(
            f"Outer validation year {fold.outer_val_year} must not be monitored during training on {fold.fold_id}"
        )
    if not is_outer_training and monitored_val_year != fold.inner_val_year:
        raise ProbabilisticTemporalError(
            f"Inner early stopping must monitor inner_val_year ({fold.inner_val_year}), got {monitored_val_year}"
        )
