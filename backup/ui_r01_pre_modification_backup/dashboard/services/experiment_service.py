"""Experiment identity, staleness tracking, and configuration lifecycle service."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from dashboard.core.contracts import SolverRunView
from dashboard.core.validation import ScientificValidator


class ExperimentService:
    """Manages run identities, parameter staleness, and fair benchmark comparisons."""

    # Meaningful optimization parameters that affect mathematical solver outcomes
    SOLVER_IDENTITY_KEYS: List[str] = [
        "solver_name",
        "w_pref",
        "w_remote",
        "w_conflict",
        "buffer_time_min",
        "allow_overflow",
        "finite_remote_capacity",
        "cp_sat_formulation",
    ]

    # Chart/presentation-only filter keys that MUST NOT alter experiment identity
    CHART_ONLY_FILTER_KEYS: List[str] = [
        "concourse_filter",
        "search_query",
        "time_zoom_start",
        "time_zoom_end",
        "highlight_carrier",
        "view_mode",
    ]

    @classmethod
    def compute_configuration_hash(
        cls,
        scenario_id: str,
        config_dict: Dict[str, Any],
    ) -> str:
        """Compute SHA256 identity hash for an optimization run configuration.

        Only considers parameters that change mathematical solver behavior.
        """
        filtered = {k: config_dict[k] for k in cls.SOLVER_IDENTITY_KEYS if k in config_dict}
        filtered["scenario_id"] = scenario_id
        serialized = json.dumps(filtered, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def is_stale(
        cls,
        draft_config: Dict[str, Any],
        executed_config: Optional[Dict[str, Any]],
    ) -> bool:
        """Check if user modified draft parameters without re-running the solver."""
        if executed_config is None:
            return True

        for key in cls.SOLVER_IDENTITY_KEYS:
            draft_val = draft_config.get(key)
            exec_val = executed_config.get(key)
            if draft_val is not None and exec_val is not None and draft_val != exec_val:
                return True
        return False

    @classmethod
    def is_presentation_filter_mutation(
        cls,
        prev_filters: Dict[str, Any],
        new_filters: Dict[str, Any],
    ) -> bool:
        """Verify whether a parameter change is purely a visual/presentation filter.

        Guarantees that chart filters do not corrupt experiment identity.
        """
        for key in cls.CHART_ONLY_FILTER_KEYS:
            if prev_filters.get(key) != new_filters.get(key):
                return True
        return False

    @classmethod
    def rank_solver_runs(
        cls,
        runs: List[SolverRunView],
    ) -> List[SolverRunView]:
        """Rank solver runs by objective value, enforcing scientific compatibility checks."""
        if not runs:
            return []

        # Validate pairwise compatibility against the first run
        baseline = runs[0]
        for candidate in runs[1:]:
            ScientificValidator.validate_solver_ranking_compatibility(baseline, candidate)

        # Sort ascending by decision cost
        return sorted(
            runs,
            key=lambda r: (
                r.decision_cost if r.decision_cost is not None else float("inf")
            ),
        )
