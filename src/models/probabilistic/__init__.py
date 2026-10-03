"""Aeolus Probabilistic Core Arrival package.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md
Scope: Distributional forecasting at T-2h, calibration, proper scoring,
       representation ablation, joint dependence, and simulation integration.
"""

from __future__ import annotations

from src.models.probabilistic.contracts import (
    PROBABILISTIC_PROTOCOL_VERSION,
    TARGET_SEMANTICS_DECISION,
    ProbabilisticContractViolation,
    ProbabilisticTemporalError,
)

__all__ = [
    "PROBABILISTIC_PROTOCOL_VERSION",
    "TARGET_SEMANTICS_DECISION",
    "ProbabilisticContractViolation",
    "ProbabilisticTemporalError",
]
