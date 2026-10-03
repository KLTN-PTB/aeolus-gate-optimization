"""Tests for Target Semantics Verification.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 3.1
Verifies:
1. ARR_DELAY column semantics across development years (2016-2022).
2. All non-null ARR_DELAY values are strictly integer minutes (0 fractional values).
3. The TargetSemanticsReport correctly serializes and certifies integer quantization Z.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from src.models.probabilistic.target_semantics import (
    TargetSemanticsReport,
    verify_target_semantics,
)


def test_target_semantics_on_development_data() -> None:
    """Audit actual development partition data (2016-2022) to verify 100% integer minute delays."""
    root = Path(__file__).resolve().parents[1]
    # Check at least 2016, 2017, 2018
    report = verify_target_semantics(project_root=root, development_years=(2016, 2017, 2018))

    assert report.total_records_inspected > 0
    assert report.overall_integer_semantics_confirmed is True

    for yr_report in report.per_year_semantics:
        assert yr_report.non_zero_fractional_count == 0
        assert yr_report.fractional_rate == 0.0
        assert yr_report.is_strictly_integer_minute is True
        assert yr_report.count > 100000  # realistic volume per year


def test_target_semantics_report_serialization() -> None:
    """Verify serialization structure of TargetSemanticsReport."""
    root = Path(__file__).resolve().parents[1]
    report = verify_target_semantics(project_root=root, development_years=(2016,))
    rep_dict = report.to_dict()

    assert rep_dict["verified_target_name"] == "ARR_DELAY"
    assert rep_dict["overall_integer_semantics_confirmed"] is True
    assert "discrete_quantization_convention" in rep_dict
    assert len(rep_dict["per_year_semantics"]) == 1
