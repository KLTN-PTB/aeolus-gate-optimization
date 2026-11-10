"""Pytest fixtures and configuration for dashboard unit tests."""

import sys
from pathlib import Path

# Ensure project root is in sys.path before tests directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Remove tests directory if pytest prepended it and caused shadowing
tests_dir = str(PROJECT_ROOT / "tests")
if tests_dir in sys.path:
    sys.path.remove(tests_dir)
    sys.path.append(tests_dir)

import pytest
from typing import Dict, Any
from dashboard.core.config import DashboardConfig


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def test_config(project_root: Path) -> DashboardConfig:
    return DashboardConfig(project_root=project_root)


@pytest.fixture
def sample_prediction_row() -> Dict[str, Any]:
    return {
        "flight_id": "DL1024",
        "carrier": "DL",
        "origin": "ORD",
        "destination": "ATL",
        "sched_arr_time_min": 465,
        "predicted_arr_delay_min": 18.4,
        "lower_bound_delay_min": 5.0,
        "upper_bound_delay_min": 32.0,
        "confidence_score": 0.85,
        "top_shap_features": {"crs_dep_time_hour": 6.12},
    }
