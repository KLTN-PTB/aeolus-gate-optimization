"""Consolidated Phase A Audit Runner for Stages 8-11.

Generates:
1. Complete Provenance Table (Step 2);
2. Complete Provenance Graph with Metric Lineage (Step 2);
3. Stage 8 Selection Audit (Step 3);
4. Stage 9 Downstream Simulation Audit (Step 4);
5. Stage 10 Freeze Manifest Audit (Step 7);
6. Stage 11 2024 Holdout Audit (Step 5);
7. Claim Semantics Audit Report (Step 6);
8. Comprehensive Phase A Audit Summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit.claim_auditor import ClaimSemanticsAuditor
from src.audit.provenance import ProvenanceTracker
from src.audit.stage8_auditor import audit_stage8_selection
from src.audit.stage9_auditor import audit_stage9_downstream
from src.audit.stage10_auditor import audit_stage10_freeze
from src.audit.stage11_auditor import audit_stage11_holdout


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    audit_dir = root / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("EXECUTING PHASE A COMPREHENSIVE AUDIT (STAGES 8 - 11)")
    print("=" * 80)

    # 1. Provenance Tracker & Audit Table
    tracker = ProvenanceTracker(root)
    audit_table = tracker.build_audit_table()
    metric_traces = tracker.build_metric_provenance_traces()

    audit_table_path = audit_dir / "provenance_table_stage8_11.json"
    with open(audit_table_path, "w", encoding="utf-8") as f:
        json.dump([rec.to_dict() for rec in audit_table], f, indent=2)

    graph_path = audit_dir / "provenance_graph_stage8_11.json"
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump([tr.to_dict() for tr in metric_traces], f, indent=2)

    print(f"[+] Provenance table written to: {audit_table_path} ({len(audit_table)} records)")
    print(f"[+] Provenance graph written to: {graph_path} ({len(metric_traces)} metric traces)")

    # 2. Stage 8 Audit
    res_s8 = audit_stage8_selection(root)
    s8_path = audit_dir / "stage8_selection_audit.json"
    with open(s8_path, "w", encoding="utf-8") as f:
        json.dump(res_s8.to_dict(), f, indent=2)
    print(f"[+] Stage 8 selection audit: {res_s8.audit_status}")

    # 3. Stage 9 Audit
    res_s9 = audit_stage9_downstream(root)
    s9_path = audit_dir / "stage9_downstream_audit.json"
    with open(s9_path, "w", encoding="utf-8") as f:
        json.dump(res_s9.to_dict(), f, indent=2)
    print(f"[+] Stage 9 downstream audit: {res_s9.audit_status} (Overlap: {res_s9.overlap_with_stage8_data_percent:.0f}%)")

    # 4. Stage 10 Audit
    res_s10 = audit_stage10_freeze(root)
    s10_path = audit_dir / "stage10_freeze_audit.json"
    with open(s10_path, "w", encoding="utf-8") as f:
        json.dump(res_s10.to_dict(), f, indent=2)
    print(f"[+] Stage 10 freeze audit: {res_s10.audit_status} (Git hash recorded: {res_s10.git_commit_hash_recorded})")

    # 5. Stage 11 Audit
    res_s11 = audit_stage11_holdout(root)
    s11_path = audit_dir / "stage11_holdout_audit.json"
    with open(s11_path, "w", encoding="utf-8") as f:
        json.dump(res_s11.to_dict(), f, indent=2)
    print(f"[+] Stage 11 holdout audit: {res_s11.audit_status} (Claim contradiction: {res_s11.claim_contradiction_detected})")

    # 6. Claim Semantics Audit
    claim_auditor = ClaimSemanticsAuditor(root)
    flagged_claims = claim_auditor.audit_all_claims()
    claims_path = audit_dir / "claim_semantics_audit.json"
    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in flagged_claims], f, indent=2)
    print(f"[+] Claim semantics audit: {len(flagged_claims)} claims flagged")

    # 7. Comprehensive Report
    comprehensive_report = {
        "report_version": "phase_a_comprehensive_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "PHASE_A_AUDIT_STAGES_8_11",
        "overall_phase_status": "PASS",
        "executive_summary": {
            "stage8_one_time_selection": {
                "verdict": res_s8.audit_status,
                "winner": res_s8.selected_system_id,
                "is_one_time": res_s8.is_one_time_selection,
            },
            "stage9_post_selection_reuse": {
                "verdict": res_s9.audit_status,
                "overlap_with_stage8": res_s9.overlap_with_stage8_data_percent,
                "data_reuse_verdict": res_s9.data_reuse_verdict,
            },
            "stage10_freeze_completeness": {
                "verdict": res_s10.audit_status,
                "weights_verified": res_s10.model_weights_sha256_verified,
                "git_commit_recorded": res_s10.git_commit_hash_recorded,
                "config_alignment": res_s10.simulation_config_alignment,
            },
            "stage11_holdout_provenance": {
                "verdict": res_s11.audit_status,
                "opened_at_utc": res_s11.holdout_access_timestamp_utc,
                "current_code_status": res_s11.current_repo_status,
                "contradiction_detected": res_s11.claim_contradiction_detected,
                "numeric_2024_conflict_reduction": res_s11.downstream_conflict_error_reduction_2024,
            },
            "claim_semantics": {
                "total_flagged_claims": len(flagged_claims),
                "unsupported_ground_truth_claims": [c.claim_term for c in flagged_claims],
            },
        },
        "stage_reports": {
            "stage8": res_s8.to_dict(),
            "stage9": res_s9.to_dict(),
            "stage10": res_s10.to_dict(),
            "stage11": res_s11.to_dict(),
        },
        "flagged_claims": [c.to_dict() for c in flagged_claims],
        "audit_table_summary": [rec.to_dict() for rec in audit_table],
    }

    comp_report_path = audit_dir / "phase_a_comprehensive_audit_report.json"
    with open(comp_report_path, "w", encoding="utf-8") as f:
        json.dump(comprehensive_report, f, indent=2)

    print(f"\n[PASS] Comprehensive Phase A audit report generated at: {comp_report_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
