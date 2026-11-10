"""Opt-in execution hooks. Legacy solver callers keep their existing behavior."""
from __future__ import annotations
import time


class SolverDeadlineExceeded(TimeoutError):
    pass


def check_deadline(deadline):
    if deadline is not None and time.perf_counter() >= deadline:
        raise SolverDeadlineExceeded('Solver preparation reached its deadline')
