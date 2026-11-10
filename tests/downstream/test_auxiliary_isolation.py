"""Tests for auxiliary model isolation and oracle labeling (Phase 8)."""

from __future__ import annotations

import pytest

from src.evaluation.downstream_comparison import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    DownstreamCandidate,
    assert_auxiliary_departure_isolated,
)


def test_auxiliary_departure_task_strictly_prohibited() -> None:
    """Departure tasks and auxiliary models must fail closed."""
    with pytest.raises(ValueError, match="Auxiliary departure task"):
        assert_auxiliary_departure_isolated(
            model_role="prediction_model",
            task_name="departure_delay_cls",
        )

    with pytest.raises(ValueError, match="Auxiliary departure task"):
        assert_auxiliary_departure_isolated(
            model_role="prediction_model",
            task_name="DEP_DELAY_REGRESSION",
        )

    with pytest.raises(ValueError, match="Auxiliary model role"):
        assert_auxiliary_departure_isolated(
            model_role="auxiliary_classifier",
            task_name="arrival_delay",
        )


def test_arrival_tasks_pass_isolation() -> None:
    """Core Arrival models pass isolation check cleanly."""
    assert_auxiliary_departure_isolated(
        model_role="prediction_model",
        task_name="arrival_delay",
    )
    assert_auxiliary_departure_isolated(
        model_role="baseline",
        task_name="arrival_delay",
    )
    assert_auxiliary_departure_isolated(
        model_role="non_deployable_reference",
        task_name="arrival_delay",
    )


def test_oracle_candidate_strictly_labeled() -> None:
    """Oracle candidate must be strictly labeled as non_deployable_reference."""
    oracle_cands = [c for c in DEFAULT_DOWNSTREAM_CANDIDATES if c.is_oracle]
    assert len(oracle_cands) == 1
    oracle = oracle_cands[0]
    assert oracle.role == "non_deployable_reference"
    assert "not a prediction model" in oracle.note.lower()

    # Attempting to declare an oracle as a deployable prediction model must raise ValueError
    with pytest.raises(ValueError, match="role='non_deployable_reference'"):
        DownstreamCandidate(
            candidate_id="illegal_oracle",
            display_name="Illegal Oracle",
            family="reference",
            is_oracle=True,
            role="prediction_model",
        )
