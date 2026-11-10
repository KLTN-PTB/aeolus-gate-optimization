"""The offline diagnostic can remove deadlines without changing app validation."""
from dataclasses import replace
import math

import pytest

from scripts.diagnose_dashboard_comparison import DiagnosticConfig
from src.optimization.config import GateOptimizationConfig


def test_unbounded_diagnostic_config_survives_hybrid_stage_replacement():
    cfg = DiagnosticConfig(time_limit_seconds=math.inf)
    stage = replace(cfg, time_limit_seconds=math.inf)
    assert stage.time_limit_seconds == math.inf
    assert stage.total_wall_clock_budget_seconds is None
    with pytest.raises(ValueError, match='positive finite'):
        GateOptimizationConfig(time_limit_seconds=math.inf)


@pytest.mark.parametrize('budget', [-1, 0, math.nan])
def test_diagnostic_keeps_invalid_budget_validation(budget):
    with pytest.raises(ValueError):
        DiagnosticConfig(time_limit_seconds=budget)
