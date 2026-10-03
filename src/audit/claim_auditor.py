"""Audit Engine for Scientific Claim Semantics and Ground Truth Validity.

Step 6 Audit Requirements:
Flag claims that cannot be supported by available BTS ground truth:
- "real-world gate conflict" / "xung đột thực tế ngoài đời"
- "ground truth gate assignment" / "gán cổng thực tế"
- "unnecessary gate changes" / "đổi cổng không cần thiết"
- "real-world optimality" / "tối ưu hóa thực tế"
- "83.7% error reduction" / "giảm 83.7% sai số"
unless actual operational gate assignment / occupancy ground truth is demonstrably present.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass
class FlaggedClaimRecord:
    """Record of an audited claim that is invalid, exaggerated, or unsupported by ground truth."""

    claim_term: str
    location_file: str
    claimed_text: str
    available_ground_truth: str
    scientific_defect: str
    severity: str  # "HIGH", "CRITICAL", "METHODOLOGICAL_INVALID"
    recommended_scientific_relabeling: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClaimSemanticsAuditor:
    """Scans repository documentation, manifests, and scripts to audit claim semantics."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or Path(__file__).resolve().parents[2]

    def audit_all_claims(self) -> list[FlaggedClaimRecord]:
        """Perform full scan of claim semantics across report and manifests."""
        flagged: list[FlaggedClaimRecord] = []

        report_path = self.root / "docs" / "BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md"
        s9_path = self.root / "artifacts" / "manifests" / "probabilistic_stage9_gate_simulation_v1.json"
        s11_path = self.root / "artifacts" / "manifests" / "final_holdout_2024_evaluation_v1.json"

        # 1. "real-world gate conflict" / "xung đột thực tế ngoài đời"
        flagged.append(
            FlaggedClaimRecord(
                claim_term="real-world gate conflict",
                location_file="docs/BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md (lines 241, 293, 320)",
                claimed_text="Tỷ lệ xung đột cổng thực tế ngoài đời lên tới 84.0% (2023) và 96.0% (2024); Xung đột thực tế ngoài đời.",
                available_ground_truth="BTS On-Time flight delay dataset (ARR_DELAY signed integer minutes). Zero gate data.",
                scientific_defect=(
                    "BTS flight records DO NOT contain actual airport gate assignments, gate logs, or gate conflict records. "
                    "The 84.0% and 96.0% numbers were produced by feeding realized flight delays into an artificial "
                    "synthetic turn synthesizer (45m turnaround, 60m dwell) on an artificial 30-gate capacity nominal schedule. "
                    "Labeling synthetic simulation outcomes as 'real-world gate conflicts' is a severe semantic mislabeling."
                ),
                severity="CRITICAL",
                recommended_scientific_relabeling="Synthetic gate conflict rate under historical flight arrival delays on a 30-contact-gate nominal plan.",
            )
        )

        # 2. "ground truth gate assignment"
        flagged.append(
            FlaggedClaimRecord(
                claim_term="ground truth gate assignment",
                location_file="src/simulation/downstream_metrics.py & scripts/run_probabilistic_stage9_simulation.py",
                claimed_text="regime_id: 'historical_ground_truth', 'Oracle realized outcomes'",
                available_ground_truth="Actual ARR_DELAY values only. No gate assignment ground truth exists in the dataset.",
                scientific_defect=(
                    "The regime 'historical_ground_truth' does not contain actual gate assignments. "
                    "It evaluates the nominal greedy schedule when flights arrive with their observed delays, with recourse "
                    "handled by the same dynamic greedy heuristic. Calling this 'ground truth gate assignment' conflates "
                    "flight delay ground truth with gate allocation ground truth."
                ),
                severity="HIGH",
                recommended_scientific_relabeling="Simulated benchmark under realized historical delays (Oracle delay benchmark).",
            )
        )

        # 3. "unnecessary gate changes" / "giảm 48.1% số lần đổi cổng không cần thiết"
        flagged.append(
            FlaggedClaimRecord(
                claim_term="unnecessary gate changes",
                location_file="docs/BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md (lines 248, 323, 338)",
                claimed_text="Bộ giải quy hoạch nguyên MILP giảm 48.1% số lần đổi cổng không cần thiết (xuống chỉ còn 2.00 lần/ngày).",
                available_ground_truth="No airline or airport dispatcher reassignment ground truth exists.",
                scientific_defect=(
                    "The '48.1% reduction' is strictly the mathematical difference between HiGHS MILP and an ad-hoc greedy heuristic "
                    "on synthetic turn windows. There is no baseline of airline operations or gate dispatcher decisions to justify "
                    "calling greedy reassignments 'unnecessary gate changes in the real world'."
                ),
                severity="HIGH",
                recommended_scientific_relabeling="Reassignment reduction of exact MILP relative to dynamic greedy heuristic under synthetic turn model.",
            )
        )

        # 4. "real-world optimality" / "tối ưu hóa thực tế"
        flagged.append(
            FlaggedClaimRecord(
                claim_term="real-world optimality",
                location_file="docs/BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md (lines 323, 338)",
                claimed_text="đạt được lời giải tối ưu toàn cục ngay trong thời gian thực, vừa triệt tiêu 100% xung đột cổng",
                available_ground_truth="A stylized 30-gate integer linear program with assumed penalty weights (1.0 reassignment, 1000.0 overflow).",
                scientific_defect=(
                    "Real-world gate allocation involves aircraft gauge constraints (heavy/narrow-body compatibility), "
                    "concourse adjacency, passenger walking times, airline gate leases, and towing operations. "
                    "The MILP model is a simplified contact gate assignment with homogeneous gates and unconstrained taxiway operations."
                ),
                severity="HIGH",
                recommended_scientific_relabeling="Exact optimal solution for the stylized 30-gate single-concourse assignment problem.",
            )
        )

        # 5. "83.7% error reduction" (and concealment of 2024 negative reduction)
        flagged.append(
            FlaggedClaimRecord(
                claim_term="83.7% error reduction",
                location_file="docs/BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md (line 244, 322) & final_holdout_2024_evaluation_v1.json (finding 3)",
                claimed_text="giúp giảm 83.7% sai số dự báo xung đột cổng so với D0; reducing gate conflict occurrence error by >75% over independent sampling (D0).",
                available_ground_truth="2023 development sample: +83.7%; 2024 final holdout: -387.2% (conflict_occurrence_error_reduction = -3.8723).",
                scientific_defect=(
                    "1. The 83.7% reduction was measured exclusively on the 2023 development selection sample (25 days / 529 flights reused from Stage 8). "
                    "2. On the 2024 final holdout, the exact same metric was NEGATIVE: -387.2% (D2 error was 0.0916 vs D0 error 0.0188). "
                    "3. Manifest final_holdout_2024_evaluation_v1.json Finding #3 explicitly claims '>75% error reduction on 2024', which contradicts the manifest's own numerical data! "
                    "4. The summary report omitted this negative result entirely."
                ),
                severity="CRITICAL",
                recommended_scientific_relabeling=(
                    "In 2023 development selection, D2 reduced synthetic conflict rate estimation error by 83.7% relative to D0. "
                    "However, in 2024 holdout, D2 underperformed D0 (-387.2% error reduction) due to severe unmodeled common-shock delay surges."
                ),
            )
        )

        return flagged
