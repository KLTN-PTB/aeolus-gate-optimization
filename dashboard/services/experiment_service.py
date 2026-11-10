"""Experiment identity, staleness tracking, and configuration lifecycle service."""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from dashboard.core.contracts import SolverRunView
from dashboard.core.validation import ScientificValidator


class ExperimentService:
    """Manages run identities, parameter staleness, and fair benchmark comparisons."""

    # Meaningful optimization parameters that affect mathematical solver outcomes (Task R02-C)
    SOLVER_IDENTITY_KEYS: List[str] = [
        "scenario_id",
        "solver_name",
        "w_pref",
        "w_remote",
        "w_conflict",
        "buffer_time_min",
        "time_limit_sec",
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
    def normalize_optimization_config(cls, raw_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize raw or draft optimization configuration into canonical types and defaults (Task R02-C)."""
        if not raw_config:
            return {}
        cfg = dict(raw_config)
        norm: Dict[str, Any] = {}

        if "scenario_id" in cfg and cfg["scenario_id"] is not None:
            norm["scenario_id"] = str(cfg["scenario_id"]).strip()

        if "solver_name" in cfg and cfg["solver_name"] is not None:
            norm["solver_name"] = str(cfg["solver_name"]).lower().strip()

        for float_key in ("w_pref", "w_remote", "w_conflict", "time_limit_sec"):
            if float_key in cfg and cfg[float_key] is not None:
                norm[float_key] = float(cfg[float_key])

        for int_key in ("buffer_time_min", "solver_seed"):
            if int_key in cfg and cfg[int_key] is not None:
                norm[int_key] = int(cfg[int_key])

        for bool_key in ("allow_overflow", "finite_remote_capacity", "warm_start"):
            if bool_key in cfg and cfg[bool_key] is not None:
                norm[bool_key] = bool(cfg[bool_key])

        for str_key in ("cp_sat_formulation", "objective_version", "prediction_source"):
            if str_key in cfg and cfg[str_key] is not None:
                norm[str_key] = str(cfg[str_key]).strip()

        return norm

    @classmethod
    def compute_configuration_hash(
        cls,
        scenario_id: str,
        config_dict: Dict[str, Any],
    ) -> str:
        """Compute SHA256 identity hash for an optimization run configuration.

        Only considers parameters that change mathematical solver behavior.
        """
        norm = cls.normalize_optimization_config(config_dict)
        norm["scenario_id"] = str(scenario_id).strip()
        filtered = {k: norm[k] for k in cls.SOLVER_IDENTITY_KEYS if k in norm}
        serialized = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def check_staleness_detailed(
        cls,
        draft_config: Optional[Dict[str, Any]],
        executed_config: Optional[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """Detailed staleness comparison between draft parameters and executed solution configuration (Task R02-C).

        Returns:
            Tuple[bool, List[str]]: (is_stale, list_of_differing_keys)
        """
        if executed_config is None:
            return True, ["executed_config_missing"]
        if draft_config is None:
            return False, []

        norm_draft = cls.normalize_optimization_config(draft_config)
        norm_exec = cls.normalize_optimization_config(executed_config)

        differing_keys: List[str] = []
        for key in cls.SOLVER_IDENTITY_KEYS:
            if key in norm_draft:
                draft_val = norm_draft[key]
                exec_val = norm_exec.get(key)
                if exec_val is None or draft_val != exec_val:
                    differing_keys.append(key)

        return len(differing_keys) > 0, differing_keys

    @classmethod
    def is_stale(
        cls,
        draft_config: Dict[str, Any],
        executed_config: Optional[Dict[str, Any]],
    ) -> bool:
        """Check if user modified draft parameters without re-running the solver (Task R02-C / ISSUE-R00-08)."""
        is_stale_flag, _ = cls.check_staleness_detailed(draft_config, executed_config)
        return is_stale_flag

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
