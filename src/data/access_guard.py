"""Access policy for development, schema audit, and the sealed 2024 holdout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from src.data.project_logging import log_data_access


SUPPORTED_YEARS: Final = frozenset(range(2016, 2025))
VALID_PURPOSES: Final = frozenset(
    {
        "development",
        "schema_audit",
        "canonicalize_holdout",
        "hpo",
        "final_evaluation",
    }
)
DEFAULT_FREEZE_MANIFEST_PATH: Final = Path(
    "artifacts/manifests/system_freeze_manifest.json"
)
DEFAULT_CONFIG_VERSION: Final = "0.1.0"


class DataAccessDenied(PermissionError):
    """Raised when a requested data access violates the temporal protocol."""


def is_system_freeze_confirmed(manifest_path: Path) -> bool:
    """Return whether a future freeze manifest explicitly authorizes final 2024 access.

    The manifest is a future generated artifact, not an environment-variable bypass.
    It must be valid JSON and state that the 2024 final holdout is frozen and approved.
    """
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("freeze_status") == "FROZEN"
        and payload.get("final_holdout_year") == 2024
        and bool(payload.get("frozen_at"))
    )


def assert_data_access_allowed(
    year: int,
    purpose: str,
    *,
    freeze_manifest_path: Path | None = None,
    config_version: str = DEFAULT_CONFIG_VERSION,
) -> None:
    """Allow only access compatible with the locked temporal protocol.

    `schema_audit` and `canonicalize_holdout` are the only Week-2 purposes which
    may access 2024 before final evaluation. Neither authorizes modelling,
    results, HPO, or development access. `final_evaluation` remains blocked
    until a valid future freeze manifest is present.
    """
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"Unsupported Aeolus year: {year}")
    if purpose not in VALID_PURPOSES:
        raise ValueError(f"Unsupported data-access purpose: {purpose}")

    manifest = freeze_manifest_path or DEFAULT_FREEZE_MANIFEST_PATH
    allowed = False
    reason = ""

    if purpose == "development":
        allowed = year <= 2023
        reason = (
            "development access is allowed for 2016-2023"
            if allowed
            else "2024 is sealed from development access"
        )
    elif purpose == "schema_audit":
        allowed = True
        reason = "schema audit is allowed for structural metadata only"
    elif purpose == "canonicalize_holdout":
        allowed = year == 2024
        reason = (
            "sealed 2024 canonicalization is allowed without development access"
            if allowed
            else "canonicalize_holdout is reserved for the sealed 2024 partition"
        )
    elif purpose == "hpo":
        allowed = year <= 2022
        reason = (
            "HPO is allowed only within rolling-development years 2016-2022"
            if allowed
            else "HPO is blocked for 2023 model selection and the 2024 final holdout"
        )
    else:
        allowed = year == 2024 and is_system_freeze_confirmed(manifest)
        reason = (
            "2024 final evaluation is authorized by the freeze manifest"
            if allowed
            else "final evaluation requires a valid future 2024 freeze manifest"
        )

    log_data_access(
        operation="assert_data_access_allowed",
        config_version=config_version,
        year=year,
        purpose=purpose,
        allowed=allowed,
        reason=reason,
    )
    if not allowed:
        raise DataAccessDenied(reason)
