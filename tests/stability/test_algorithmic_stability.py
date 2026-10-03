"""Unit tests for Phase 6 Algorithmic Stability Benchmark.

Tests:
1. Fixed seed determinism
2. Seed manifest immutability
3. Equal seed count across eligible models
4. Failure retention
5. Aggregate stability calculations (mean, std, median, min, max, cv)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import numpy as np
import yaml

from src.evaluation.algorithmic_stability import (
    AUTHORITATIVE_FINALIST_SEEDS,
    DEFAULT_SEED_REGISTRY_PATH,
    MetricSummary,
    RunRecord,
    SeedRegistry,
    aggregate_stability_records,
    audit_equal_seed_count,
    compute_metric_stability,
    extract_scalar_metrics,
)
from src.models.probabilistic.contracts import FINALIST_SEEDS


def test_seed_manifest_immutability(tmp_path: Path):
    """Seed registry must match authoritative finalist seeds and fail on alteration."""
    # 1. Authoritative config check
    assert DEFAULT_SEED_REGISTRY_PATH.exists(), "configs/seed_registry.yaml must exist"
    reg = SeedRegistry.load(DEFAULT_SEED_REGISTRY_PATH)

    assert reg.registered_seeds == AUTHORITATIVE_FINALIST_SEEDS
    assert reg.registered_seeds == FINALIST_SEEDS
    assert reg.predetermined_deployment_seed == 202601
    assert reg.data_sampling_seed == 202601
    assert reg.status == "LOCKED_IMMUTABLE"

    # Also check JSON seed manifest in manifests
    manifest_p = Path("artifacts/manifests/seed_manifest_v1.json")
    assert manifest_p.exists()
    with open(manifest_p, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert tuple(meta["finalist_seeds"]) == AUTHORITATIVE_FINALIST_SEEDS

    # 2. Tampered config must fail validation
    bad_cfg = tmp_path / "bad_seed_registry.yaml"
    bad_data = {
        "registry_version": "tampered_v1",
        "registered_seeds": [42, 123, 2024],
        "predetermined_deployment_seed": 42,
        "data_sampling_seed": 42,
    }
    with open(bad_cfg, "w", encoding="utf-8") as f:
        yaml.safe_dump(bad_data, f)

    with pytest.raises(ValueError, match="Seed registry mismatch"):
        SeedRegistry.load(bad_cfg)


def test_fixed_seed_determinism():
    """Point and probabilistic algorithms must produce bitwise/numerically identical outputs under fixed seed."""
    from sklearn.ensemble import RandomForestRegressor

    rng_seed = 202601
    X = np.random.default_rng(42).normal(size=(100, 5))
    y = np.random.default_rng(42).normal(size=100)

    m1 = RandomForestRegressor(n_estimators=10, random_state=rng_seed)
    m1.fit(X, y)
    preds1 = m1.predict(X)

    m2 = RandomForestRegressor(n_estimators=10, random_state=rng_seed)
    m2.fit(X, y)
    preds2 = m2.predict(X)

    np.testing.assert_array_equal(preds1, preds2)


def test_equal_seed_count_across_eligible_models():
    """Fairness audit must verify every model x fold has identical seed representation."""
    models = ["model_a", "model_b"]
    folds = ["fold_1", "fold_2"]
    seeds = [202601, 202602, 202603]

    runs: list[RunRecord] = []
    for m in models:
        for f in folds:
            for s in seeds:
                runs.append(
                    RunRecord(
                        model_id=m,
                        family="point",
                        fold_id=f,
                        validation_year=2020,
                        seed=s,
                        data_seed=202601,
                        status="COMPLETED",
                        runtime_seconds=1.0,
                        memory_mb=10.0,
                        failure_reason=None,
                        error_category=None,
                        model_version="v1",
                        data_version="v1",
                        feature_version="v1",
                        metrics={"mae": 10.0},
                    )
                )

    # Perfect parity: passes
    ok, msg = audit_equal_seed_count(runs, expected_seeds=seeds)
    assert ok is True
    assert "exact seeds" in msg

    # One model missing a seed on fold_2
    bad_runs = [r for r in runs if not (r.model_id == "model_b" and r.fold_id == "fold_2" and r.seed == 202603)]
    ok_bad, msg_bad = audit_equal_seed_count(bad_runs, expected_seeds=seeds)
    assert ok_bad is False
    assert "missing={202603}" in msg_bad


def test_failure_retention():
    """Failed seeds must not be dropped; status and error category must be preserved."""
    runs = [
        RunRecord(
            model_id="candidate_x",
            family="probabilistic",
            fold_id="fold_1",
            validation_year=2019,
            seed=202601,
            data_seed=202601,
            status="COMPLETED",
            runtime_seconds=2.0,
            memory_mb=20.0,
            failure_reason=None,
            error_category=None,
            model_version="v1",
            data_version="v1",
            feature_version="v1",
            metrics={"crps": 12.0},
        ),
        RunRecord(
            model_id="candidate_x",
            family="probabilistic",
            fold_id="fold_1",
            validation_year=2019,
            seed=202602,
            data_seed=202601,
            status="FAILED",
            runtime_seconds=0.5,
            memory_mb=5.0,
            failure_reason="FloatingPointError: NaN gradient encountered",
            error_category="NUMERICAL_INSTABILITY",
            model_version="v1",
            data_version="v1",
            feature_version="v1",
            metrics={},
        ),
        RunRecord(
            model_id="candidate_x",
            family="probabilistic",
            fold_id="fold_1",
            validation_year=2019,
            seed=202603,
            data_seed=202601,
            status="COMPLETED",
            runtime_seconds=2.1,
            memory_mb=21.0,
            failure_reason=None,
            error_category=None,
            model_version="v1",
            data_version="v1",
            feature_version="v1",
            metrics={"crps": 12.5},
        ),
    ]

    agg = aggregate_stability_records(runs)

    assert agg["total_runs"] == 3
    assert agg["completed_runs"] == 2
    assert agg["failed_runs"] == 1
    assert agg["failure_rate"] == pytest.approx(1.0 / 3.0, abs=1e-4)

    # Metrics computed only from completed runs
    assert "crps" in agg["metrics"]
    assert agg["metrics"]["crps"]["mean"] == pytest.approx(12.25, abs=1e-4)
    assert agg["metrics"]["crps"]["min"] == 12.0
    assert agg["metrics"]["crps"]["max"] == 12.5


def test_aggregate_calculation():
    """Verify numeric precision for mean, std, median, min, max, cv."""
    # Synthetic values: [10.0, 12.0, 14.0]
    vals = [10.0, 12.0, 14.0]
    res = compute_metric_stability(vals)

    assert res.mean == pytest.approx(12.0)
    assert res.std == pytest.approx(2.0)  # sample std ddof=1
    assert res.median == pytest.approx(12.0)
    assert res.min == pytest.approx(10.0)
    assert res.max == pytest.approx(14.0)
    assert res.cv == pytest.approx(2.0 / 12.0, abs=1e-5)

    # Zero mean case: CV must be None (not divide by zero error)
    zero_mean_vals = [-5.0, 5.0]
    res_zero = compute_metric_stability(zero_mean_vals)
    assert res_zero.mean == pytest.approx(0.0)
    assert res_zero.cv is None

    # Empty list case
    res_empty = compute_metric_stability([])
    assert res_empty.mean == 0.0
    assert res_empty.cv is None
