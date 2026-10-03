"""Standalone Audit Script for Stage 11: 2024 Final Holdout Evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit.stage11_auditor import audit_stage11_holdout


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "artifacts" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = audit_stage11_holdout(root)
    output_path = output_dir / "stage11_holdout_audit.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print("=" * 80)
    print("STAGE 11 AUDIT RESULT")
    print(f"Status:                        {result.audit_status}")
    print(f"2024 Opened Timestamp:         {result.holdout_access_timestamp_utc}")
    print(f"Accessed Before Freeze:        {result.accessed_before_freeze}")
    print(f"Used for Tuning / Fitting:     {result.used_for_tuning_or_fitting}")
    print(f"Used for Calibration:          {result.used_for_calibration}")
    print(f"Current Repository Status:     {result.current_repo_status}")
    print(f"Marginal CRPS Gap (2024-2023): {result.marginal_forecast_gap_crps:+.3f}m")
    print(f"2024 Conflict Error Reduction: {result.downstream_conflict_error_reduction_2024*100:.1f}%")
    print(f"Claim Contradiction Detected:  {result.claim_contradiction_detected}")
    print("-" * 80)
    if result.claim_contradiction_detected:
        print("CONTRADICTION DETAILS:")
        for k, v in result.contradiction_details.items():
            print(f"   {k}: {v}")
    print("-" * 80)
    print("Findings:")
    for f_item in result.audit_findings:
        print(f" - {f_item}")
    print(f"\nAudit artifact exported to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
