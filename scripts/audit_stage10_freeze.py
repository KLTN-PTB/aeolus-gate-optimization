"""Standalone Audit Script for Stage 10: Full System Freeze."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit.stage10_auditor import audit_stage10_freeze


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "artifacts" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = audit_stage10_freeze(root)
    output_path = output_dir / "stage10_freeze_audit.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print("=" * 80)
    print("STAGE 10 AUDIT RESULT")
    print(f"Status:                        {result.audit_status}")
    print(f"All 17 Step 7 Items Verified:  {result.all_step7_components_verified}")
    print(f"Model Weights SHA-256 Match:   {result.model_weights_sha256_verified}")
    print(f"Git Commit Hash Recorded:      {result.git_commit_hash_recorded}")
    print(f"Simulation Config Alignment:   {result.simulation_config_alignment}")
    print(f"Optimization Config Alignment: {result.optimization_config_alignment}")
    print("-" * 80)
    print("Component Audit Summary:")
    for comp, info in result.component_audit.items():
        print(f" - {comp:28s}: {info.get('status', 'N/A')}")
    print("-" * 80)
    print("Findings:")
    for f_item in result.audit_findings:
        print(f" - {f_item}")
    print(f"\nAudit artifact exported to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
