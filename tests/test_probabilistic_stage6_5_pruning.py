"""Unit tests for Stage 6.5 — Candidate Pruning.

Verifies:
1. Pruning logic adheres to pre-registered rules (CRPS <= best + 0.20m, calibration guard, tail guard).
2. Non-arbitrary candidate retention (no fixed top-k rule).
3. Material difference preservation (slightly worse CRPS retained if calibration/tail is valid).
4. Traceable rejection rationales.
"""

from __future__ import annotations

import pytest

from scripts.run_probabilistic_stage6_5_pruning import prune_candidates


def test_prune_candidates_rules():
    mock_stage6 = {
        "candidate_evaluations": {
            "D3_best": {
                "is_quantile_only": False,
                "gate_a_calibration": {
                    "intervals": {"cov_80": 0.81, "cov_90": 0.90},
                    "crossing_rate": 0.0,
                },
                "gate_b_proper_scoring": {"crps_mean": 13.28},
                "gate_c_event_probabilities": {
                    "event_15": {"brier_score": 0.11},
                    "event_60": {"brier_score": 0.040},
                    "event_120": {"brier_score": 0.015},
                },
            },
            "D3_near_best": {
                "is_quantile_only": False,
                "gate_a_calibration": {
                    "intervals": {"cov_80": 0.82, "cov_90": 0.91},
                    "crossing_rate": 0.0,
                },
                "gate_b_proper_scoring": {"crps_mean": 13.36},  # +0.08m < 0.20m screen
                "gate_c_event_probabilities": {
                    "event_15": {"brier_score": 0.11},
                    "event_60": {"brier_score": 0.041},  # +0.001 < 0.005 tolerance
                    "event_120": {"brier_score": 0.015},
                },
            },
            "B2_dominated": {
                "is_quantile_only": False,
                "gate_a_calibration": {
                    "intervals": {"cov_80": 0.95, "cov_90": 0.98},
                    "crossing_rate": 0.0,
                },
                "gate_b_proper_scoring": {"crps_mean": 18.44},  # +5.16m >> 0.20m screen
                "gate_c_event_probabilities": {
                    "event_15": {"brier_score": 0.13},
                    "event_60": {"brier_score": 0.052},  # +0.012 > 0.005 tolerance
                    "event_120": {"brier_score": 0.020},
                },
            },
            "B4_quantile_only": {
                "is_quantile_only": True,
                "gate_a_calibration": {
                    "intervals": {"cov_80": 0.80, "cov_90": 0.89},
                    "crossing_rate": 0.005,
                },
                "gate_b_proper_scoring": {},
                "gate_c_event_probabilities": {},
                "quantile_metrics": {"pinball_q90": 4.5, "pinball_q95": 3.2},
            },
        }
    }

    result = prune_candidates(mock_stage6)

    # Invariants
    assert result["best_candidate_crps"] == "D3_best"
    assert result["best_crps_value"] == 13.28

    # Retained candidates
    assert "D3_best" in result["retained_candidates"]
    assert "D3_near_best" in result["retained_candidates"]  # Preserved due to acceptable delta
    assert len(result["retained_candidates"]) == 2

    # Pruned candidates
    assert "B2_dominated" in result["pruned_candidates"]
    assert "B4_quantile_only" in result["pruned_candidates"]

    # Traceable reasons
    b2_dec = result["pruning_decisions"]["B2_dominated"]
    assert b2_dec["status"] == "PRUNED"
    assert any("dominated" in axis for axis in b2_dec["dominated_axes"])
