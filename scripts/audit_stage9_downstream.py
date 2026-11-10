"""Standalone Audit Script for Stage 9: Downstream Gate Simulation & Operational Utility."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit.stage9_auditor import audit_stage9_downstream


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "artifacts" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = audit_stage9_downstream(root)
    output_path = output_dir / "stage9_downstream_audit.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print("=" * 80)
    print("STAGE 9 AUDIT RESULT")
    print(f"Status:                      {result.audit_status}")
    print(f"Days Evaluated:              {result.days_evaluated}")
    print(f"Flights Evaluated:           {result.flights_evaluated}")
    print(f"Pre-Registered Pre-Stage8:   {result.were_days_preregistered_before_stage8}")
    print(f"Excluded from Stage 8:       {result.were_days_excluded_from_stage8}")
    print(f"Overlap with Stage 8:        {result.overlap_with_stage8_data_percent:.1f}%")
    print(f"Data Reuse Verdict:          {result.data_reuse_verdict}")
    print(f"Ground Truth Semantics:      {result.ground_truth_type}")
    print(f"Config Match Freeze Manifest:{result.simulation_config_matches_freeze_manifest}")
    print("-" * 80)
    print("Findings:")
    for f_item in result.audit_findings:
        print(f" - {f_item}")
    print(f"\nAudit artifact exported to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
