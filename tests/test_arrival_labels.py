from __future__ import annotations

import pandas as pd
import pytest

from src.features.tabular_features import ArrivalTargetError, build_arrival_labels


def test_arrival_labels_use_exact_threshold_and_preserve_signed_regression() -> None:
    frame = pd.DataFrame({"ARR_DELAY": [14.999, 15.0, 21.5, -7.0, 0.0]})

    labels, report = build_arrival_labels(frame)

    assert labels["y_arr_cls"].tolist() == [0, 1, 1, 0, 0]
    assert labels["y_arr_reg"].tolist() == [14.999, 15.0, 21.5, -7.0, 0.0]
    assert str(labels["y_arr_cls"].dtype) == "int8"
    assert report.input_rows == 5
    assert report.eligible_rows == 5
    assert report.dropped_missing_target_rows == 0


def test_missing_arrival_target_is_dropped_and_never_imputed() -> None:
    frame = pd.DataFrame({"ARR_DELAY": [3.0, None, -2.0]}, index=[10, 11, 12])

    labels, report = build_arrival_labels(frame)

    assert labels.index.tolist() == [10, 12]
    assert labels["y_arr_reg"].tolist() == [3.0, -2.0]
    assert report.input_rows == 3
    assert report.eligible_rows == 2
    assert report.dropped_missing_target_rows == 1
    assert report.target_imputation_used is False


@pytest.mark.parametrize("invalid", ["not-a-number", float("inf"), float("-inf")])
def test_invalid_nonmissing_arrival_target_fails_closed(invalid: object) -> None:
    with pytest.raises(ArrivalTargetError, match="invalid non-missing ARR_DELAY"):
        build_arrival_labels(pd.DataFrame({"ARR_DELAY": [invalid]}))


def test_build_arrival_labels_does_not_mutate_input() -> None:
    frame = pd.DataFrame({"ARR_DELAY": [-3.0, 18.0]})
    before = frame.copy(deep=True)

    build_arrival_labels(frame)

    pd.testing.assert_frame_equal(frame, before)
