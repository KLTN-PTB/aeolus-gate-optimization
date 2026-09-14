"""Portable, explicitly scoped runtime and memory measurements for Week 4."""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import asdict, dataclass
from typing import Any, Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ResourceMeasurement:
    """A phase measurement with a portable Python-allocation memory scope.

    ``tracemalloc`` is intentionally reported as Python allocation memory, not
    process RSS.  It is portable but does not claim to cover native allocations
    made by NumPy, SciPy or a future estimator.
    """

    runtime_seconds: float
    peak_memory_bytes: int
    memory_measurement_method: str = "tracemalloc_python_allocations"
    memory_scope: str = "python_allocations_only_not_process_rss"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def measure_phase(action: Callable[[], T]) -> tuple[T, ResourceMeasurement]:
    """Run one phase and record wall-clock duration plus portable peak memory."""

    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    started = time.perf_counter()
    try:
        value = action()
    finally:
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        if not was_tracing:
            tracemalloc.stop()
    return value, ResourceMeasurement(runtime_seconds=elapsed, peak_memory_bytes=int(peak))
