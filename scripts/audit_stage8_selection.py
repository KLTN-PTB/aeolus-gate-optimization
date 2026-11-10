"""Standalone Audit Script for Stage 8: 2023 One-Time Full-System Selection."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit.stage8_auditor import audit_stage8_selection


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "artifacts" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = audit_stage8_selection(root)
    output_path = output_dir / "stage8_selection_audit.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print("=" * 80)
    print("STAGE 8 AUDIT RESULT")
    print(f"Status:                      {result.audit_status}")
    print(f"Is One-Time Selection:       {result.is_one_time_selection}")
    print(f"Candidate Pool Pre-Frozen:   {result.candidate_pool_pre_frozen}")
    print(f"Exactly One System Selected: {result.exactly_one_system_selected}")
    print(f"Selected System ID:          {result.selected_system_id}")
    print(f"Tie-Break Compliance:        {result.tie_break_protocol_compliance}")
    print("-" * 80)
    print("Findings:")
    for f_item in result.audit_findings:
        print(f" - {f_item}")
    print(f"\nAudit artifact exported to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
