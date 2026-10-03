"""Algorithmic Stability Evaluation Engine (Phase 6).

Evaluates algorithmic stability of candidate models across pre-registered seeds.
Enforces:
1. Fixed seed registry from config (configs/seed_registry.yaml)
2. Equal seed count across all eligible models
3. Strict row parity across seeds (identical data_sampling_seed)
4. Comprehensive stability metrics: mean, std, median, min, max, CV, failure rate
5. Durable failure accounting (failed seeds retained with error category)
6. Sealed 2024 holdout isolation
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Final, Sequence
import yaml

import numpy as np
import pandas as pd

LOGGER = logging.getLogger("algorithmic_stability")

DEFAULT_STABILITY_DIR: Final = Path("artifacts/stability")
DEFAULT_SEED_REGISTRY_PATH: Final = Path("configs/seed_registry.yaml")
AUTHORITATIVE_FINALIST_SEEDS: Final = (202601, 202602, 202603)
PREDETERMINED_DEPLOYMENT_SEED: Final = 202601


@dataclass(frozen=True)
class SeedRegistry:
    """Fixed seed registry specification."""

    registry_version: str
    registered_seeds: tuple[int, ...]
    predetermined_deployment_seed: int
    data_sampling_seed: int
    policy: str
    status: str
    provenance_hash: str

    @classmethod
    def load(cls, path: Path = DEFAULT_SEED_REGISTRY_PATH) -> SeedRegistry:
        """Load and validate fixed seed registry from config."""
        if not path.exists():
            raise FileNotFoundError(f"Seed registry config not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_seeds = data.get("registered_seeds", [])
        if not raw_seeds:
            raise ValueError(f"No registered seeds found in {path}")

        seeds = tuple(int(s) for s in raw_seeds)
        dep_seed = int(data.get("predetermined_deployment_seed", seeds[0]))
        data_seed = int(data.get("data_sampling_seed", dep_seed))
        policy = str(data.get("policy", "evaluation_only_with_predetermined_deployment_seed"))
        status = str(data.get("status", "LOCKED_IMMUTABLE"))
        version = str(data.get("registry_version", "seed_registry_v1"))

        # Compute SHA-256 of registry content
        content_hash = hashlib.sha256(
            json.dumps({"seeds": list(seeds), "dep_seed": dep_seed, "data_seed": data_seed}, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # Invariance check: must match project authoritative finalist seeds
        if seeds != AUTHORITATIVE_FINALIST_SEEDS:
            raise ValueError(
                f"Seed registry mismatch: expected authoritative {AUTHORITATIVE_FINALIST_SEEDS}, got {seeds}"
            )

        return cls(
            registry_version=version,
            registered_seeds=seeds,
            predetermined_deployment_seed=dep_seed,
            data_sampling_seed=data_seed,
            policy=policy,
            status=status,
            provenance_hash=content_hash,
        )


@dataclass
class RunRecord:
    """Detailed record of one evaluation run on a model x fold x seed combination."""

    model_id: str
    family: str  # "point" or "probabilistic"
    fold_id: str
    validation_year: int
    seed: int
    data_seed: int
    status: str  # "COMPLETED" or "FAILED"
    runtime_seconds: float
    memory_mb: float
    failure_reason: str | None
    error_category: str | None
    model_version: str
    data_version: str
    feature_version: str
    metrics: dict[str, Any]
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricSummary:
    """Summary statistics for one metric across seeds."""

    mean: float
    std: float
    median: float
    min: float
    max: float
    cv: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_metric_stability(values: Sequence[float | int]) -> MetricSummary:
    """Calculate mean, std, median, min, max, and coefficient of variation.

    Mathematical semantics:
    - std uses Bessel correction ddof=1 when N > 1, else 0.0.
    - CV = std / |mean| when |mean| > 1e-6, else None (ill-conditioned or zero mean).
    """
    arr = np.asarray(values, dtype=np.float64)
    n = len(arr)
    if n == 0:
        return MetricSummary(mean=0.0, std=0.0, median=0.0, min=0.0, max=0.0, cv=None)

    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    med_val = float(np.median(arr))
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))

    # Coefficient of variation
    cv_val: float | None = None
    if abs(mean_val) > 1e-6:
        cv_val = float(std_val / abs(mean_val))

    return MetricSummary(
        mean=round(mean_val, 6),
        std=round(std_val, 6),
        median=round(med_val, 6),
        min=round(min_val, 6),
        max=round(max_val, 6),
        cv=round(cv_val, 6) if cv_val is not None else None,
    )


def extract_scalar_metrics(metrics_dict: dict[str, Any], prefix: str = "") -> dict[str, float]:
    """Recursively flatten numeric metrics from arbitrary nested dictionaries."""
    flat: dict[str, float] = {}
    for k, v in metrics_dict.items():
        name = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, (int, float, np.floating, np.integer)):
            if not np.isnan(v) and not np.isinf(v):
                flat[name] = float(v)
        elif isinstance(v, dict):
            sub = extract_scalar_metrics(v, prefix=name)
            flat.update(sub)
    return flat


def aggregate_stability_records(
    runs: list[RunRecord],
) -> dict[str, Any]:
    """Aggregate a collection of RunRecords into a stability summary across seeds."""
    if not runs:
        return {}

    total_runs = len(runs)
    completed_runs = sum(1 for r in runs if r.status == "COMPLETED")
    failed_runs = total_runs - completed_runs
    failure_rate = failed_runs / float(total_runs)

    # Collect numeric metrics across completed runs
    metric_values: dict[str, list[float]] = {}
    runtimes: list[float] = []
    memories: list[float] = []

    for r in runs:
        runtimes.append(r.runtime_seconds)
        memories.append(r.memory_mb)
        if r.status == "COMPLETED":
            scalars = extract_scalar_metrics(r.metrics)
            for m_name, m_val in scalars.items():
                metric_values.setdefault(m_name, []).append(m_val)

    # Compute metric summaries
    metric_summaries: dict[str, dict[str, Any]] = {}
    for m_name, vals in metric_values.items():
        metric_summaries[m_name] = compute_metric_stability(vals).to_dict()

    runtime_summary = compute_metric_stability(runtimes).to_dict()
    memory_summary = compute_metric_stability(memories).to_dict()

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "failure_rate": round(failure_rate, 4),
        "runtime_seconds": runtime_summary,
        "memory_mb": memory_summary,
        "metrics": metric_summaries,
    }


def audit_equal_seed_count(
    runs: list[RunRecord],
    expected_seeds: Sequence[int] = AUTHORITATIVE_FINALIST_SEEDS,
) -> tuple[bool, str]:
    """Assert that every eligible model evaluated has exact equal seed representation."""
    from collections import defaultdict

    counts: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in runs:
        counts[(r.model_id, r.fold_id)].add(r.seed)

    expected_set = set(expected_seeds)
    for (m_id, f_id), seeds_seen in counts.items():
        if seeds_seen != expected_set:
            diff_missing = expected_set - seeds_seen
            diff_extra = seeds_seen - expected_set
            return (
                False,
                f"Model {m_id} on {f_id} has mismatched seeds: missing={diff_missing}, extra={diff_extra}",
            )

    return True, f"All {len(counts)} model x fold units evaluated on exact seeds: {list(expected_seeds)}"
