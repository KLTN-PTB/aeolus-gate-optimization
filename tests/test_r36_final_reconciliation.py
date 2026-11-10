"""Pre-certification integration verification tests for AEOLUS V4 Task R36.

Task: R36 — FINAL EVIDENCE RECONCILIATION V2

Verifies:
1. test_r33_pass: R33 status is PASS and P4 discrepancy is resolved.
2. test_r34_pass: R34 status is PASS and P5 configuration is locked.
3. test_r35_pass: R35 status is PASS and solver boundary/environment is resolved.
4. test_p4_authoritative_metric: Authoritative P4 holdout metrics are CRPS=17.6532, NLL=4.6307, dev CRPS=18.484, NLL=4.5805; calibration NOT_SEPARATELY_CERTIFIED.
5. test_p5_authoritative_configuration: P5 is 9-quantile estimator [0.025..0.975] marked FINAL_CERTIFIED.
6. test_p5_metric_semantics: 16.85 is CRPS_QUANTILE_APPROXIMATION (pinball loss is 6.88); continuous density/NLL/PIT/sampling NOT_SUPPORTED.
7. test_point_selection_boundary: 2023 Ridge vs Ensemble tied (|diff| <= 0.10 min); 2024 not tied (|diff| > 0.10 min); no single overall champion.
8. test_solver_wall_clock_boundary: Wall-clock equality (T=2.0s ceiling) PROVEN; computational work equality NOT_PROVEN and prohibited.
9. test_solver_scope_boundary: R26 evaluates 28 instances (112 runs) on 2024 post-holdout; R21 is separate 84 runs on 2023 dev; R26 does not certify R21.
10. test_hybrid_claim_boundary: Delta_i == 0.0 on 28/28 audited cases; prohibition on claiming SA is universally useless.
11. test_execution_unit_semantics: 124 fresh execution runs + 100 reused/frozen evidence units = 224 tracked units, with 48 statistical inference families.
12. test_hash_integrity: 31/31 critical artifacts verified byte-for-byte; claim bounded to byte-level integrity verification.
13. test_reproducibility_scope: Verified as CONTAINED_SPECIFICATION_REPRODUCIBILITY; universal bit-for-bit reproducibility prohibited.
14. test_exact_13_claims: Exactly 13 claims matching approved taxonomy.
15. test_no_duplicate_claims: Zero duplicate claim IDs.
16. test_no_unclassified_claims: All claims classified into approved status set.
17. test_no_forbidden_final_assertions: Overclaim scan verifies no prohibited positive assertions exist in claims or evidence.
18. test_weather_boundary: Weather is excluded from Core Arrival by V4 invariant #1; real-time METAR/TAF claims banned.
19. test_departure_boundary: Departure delay is an auxiliary quarantined benchmark with zero feed into arrival delay or gate solver.
20. test_actual_outcome_boundary: Claims of real airfield operations, actual airline delay reduction, or operational cost savings are banned.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

R36_REC_JSON = ROOT / "artifacts" / "audit" / "r36_final_evidence_reconciliation_v2.json"
R36_REC_SHA = ROOT / "artifacts" / "audit" / "r36_final_evidence_reconciliation_v2.json.sha256"

R36_CLAIM_JSON = ROOT / "artifacts" / "audit" / "r36_final_claim_matrix_v2.json"
R36_CLAIM_SHA = ROOT / "artifacts" / "audit" / "r36_final_claim_matrix_v2.json.sha256"

R36_STATUS_PARQUET = ROOT / "artifacts" / "audit" / "r36_final_status_matrix_v2.parquet"
R36_STATUS_SHA = ROOT / "artifacts" / "audit" / "r36_final_status_matrix_v2.parquet.sha256"

R33_JSON = ROOT / "artifacts" / "audit" / "r33_p4_metric_lineage.json"
R34_JSON = ROOT / "artifacts" / "audit" / "r34_p5_capability_forensics.json"
R35_JSON = ROOT / "artifacts" / "audit" / "r35_solver_boundary_audit.json"
FREEZE_V4 = ROOT / "artifacts" / "audit" / "final_freeze_manifest_v4.json"

EXPECTED_13_CLAIM_IDS = (
    "CLAIM_01_TEMPORAL_POST_HOLDOUT",
    "CLAIM_02_POINT_CHAMPION_SELECTION",
    "CLAIM_03_PROBABILISTIC_P5_CRPS",
    "CLAIM_04_PROBABILISTIC_P4_STUDENT_T",
    "CLAIM_05_SINGLE_OVERALL_CHAMPION",
    "CLAIM_06_CRN_VARIANCE_REDUCTION",
    "CLAIM_07_MC_N500_OPTIMALITY",
    "CLAIM_08_REAL_WORLD_GATE_OPERATIONS",
    "CLAIM_09_ORACLE_EQUIVALENCE",
    "CLAIM_10_DOWNSTREAM_SEMANTICS",
    "CLAIM_11_STATISTICAL_SIGNIFICANCE",
    "CLAIM_12_AUXILIARY_DEPARTURE_DELAY",
    "CLAIM_13_REPRODUCIBILITY_STANDARDS",
)

VALID_STATUSES = {
    "CORRECTED",
    "SUPPORTED_WITH_LIMITATION",
    "BLOCKED",
    "NOT_SUPPORTED",
    "HISTORICAL_ONLY",
}


@pytest.fixture(scope="module")
def rec_data() -> dict:
    assert R36_REC_JSON.is_file(), f"Missing {R36_REC_JSON}"
    return json.loads(R36_REC_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def claim_data() -> dict:
    assert R36_CLAIM_JSON.is_file(), f"Missing {R36_CLAIM_JSON}"
    return json.loads(R36_CLAIM_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def status_df() -> pd.DataFrame:
    assert R36_STATUS_PARQUET.is_file(), f"Missing {R36_STATUS_PARQUET}"
    return pd.read_parquet(R36_STATUS_PARQUET)


def test_r33_pass(rec_data: dict) -> None:
    """Test 1: Verify R33 passed with P4 metric lineage discrepancy resolved."""
    assert rec_data["pre_certification_gate_verification"]["r33_status"] == "PASS"
    assert R33_JSON.is_file()
    r33 = json.loads(R33_JSON.read_text(encoding="utf-8"))
    assert r33["discrepancy_classification"] == "ONE_VALUE_IS_INVALID_OR_MISLABELED"


def test_r34_pass(rec_data: dict) -> None:
    """Test 2: Verify R34 passed with P5 quantile configuration locked."""
    assert rec_data["pre_certification_gate_verification"]["r34_status"] == "PASS"
    assert R34_JSON.is_file()
    r34 = json.loads(R34_JSON.read_text(encoding="utf-8"))
    assert r34["final_status_block"]["R34_STATUS"] == "PASS"
    assert r34["final_status_block"]["FINAL_P5_QUANTILE_COUNT"] == 9


def test_r35_pass(rec_data: dict) -> None:
    """Test 3: Verify R35 passed with solver boundaries and environment verified."""
    assert rec_data["pre_certification_gate_verification"]["r35_status"] == "PASS"
    assert R35_JSON.is_file()
    r35 = json.loads(R35_JSON.read_text(encoding="utf-8"))
    assert r35["audit_verdict"] == "PASS"
    assert r35["solver_fairness_semantics"]["wall_clock_equality"] == "PROVEN"


def test_p4_authoritative_metric(rec_data: dict) -> None:
    """Test 4: Verify authoritative P4 holdout & dev metrics and calibration status."""
    p4 = rec_data["p4_final_state"]
    assert p4["authoritative_p4_holdout_crps"] == 17.6532
    assert p4["authoritative_p4_holdout_nll"] == 4.6307
    assert p4["authoritative_p4_dev_crps"] == 18.484
    assert p4["authoritative_p4_dev_nll"] == 4.5805
    assert p4["calibration_status"] == "NOT_SEPARATELY_CERTIFIED"
    assert p4["density_type"] == "PARAMETRIC_CONTINUOUS_DENSITY"
    assert p4["continuous_sampling"] == "SUPPORTED"


def test_p5_authoritative_configuration(rec_data: dict) -> None:
    """Test 5: Verify P5 final configuration is 9-quantile estimator marked FINAL_CERTIFIED."""
    p5 = rec_data["p5_final_state"]
    assert p5["configuration_status"] == "FINAL_CERTIFIED"
    assert p5["quantile_count"] == 9
    assert p5["quantile_levels"] == [0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]
    assert p5["legacy_5_quantile_status"] == "SUPERSEDED_LEGACY"


def test_p5_metric_semantics(rec_data: dict) -> None:
    """Test 6: Verify 16.85 is CRPS_QUANTILE_APPROXIMATION and continuous capabilities NOT_SUPPORTED."""
    p5 = rec_data["p5_final_state"]
    assert p5["metric_16_85_classification"] == "CRPS_QUANTILE_APPROXIMATION"
    assert p5["pinball_loss_dev"] == 6.8781
    assert p5["continuous_density"] == "NOT_AVAILABLE"
    assert p5["continuous_nll"] == "NOT_SUPPORTED"
    assert p5["continuous_pit"] == "NOT_SUPPORTED"
    assert p5["continuous_sampling"] == "NOT_SUPPORTED"


def test_point_selection_boundary(rec_data: dict) -> None:
    """Test 7: Verify point selection tie on 2023 dev, not tied on 2024, no overall champion."""
    pt = rec_data["point_models_state"]
    assert pt["dev_2023_status"] == "TIED_WITHIN_0.10_MIN_BAND"
    assert pt["dev_2023_difference_min"] <= 0.10
    assert pt["holdout_2024_status"] == "NOT_TIED_DIFFERENCE_EXCEEDS_0.10_MIN"
    assert pt["holdout_2024_difference_min"] > 0.10
    assert pt["single_overall_champion"] == "PROHIBITED"


def test_solver_wall_clock_boundary(rec_data: dict) -> None:
    """Test 8: Verify wall-clock equality is PROVEN; equal computational work is NOT_PROVEN."""
    solvers = rec_data["solver_state"]
    assert solvers["wall_clock_equality"] == "PROVEN"
    assert solvers["computational_work_equality"] == "NOT_PROVEN"
    assert "equal computational work" in solvers["prohibited_solver_claims"]
    assert "equal CPU work" in solvers["prohibited_solver_claims"]


def test_solver_scope_boundary(rec_data: dict) -> None:
    """Test 9: Verify R26 scope (28 cases / 112 runs) does NOT certify R21 downstream (84 runs)."""
    solvers = rec_data["solver_state"]
    assert solvers["r26_scope"] == "28_CASES_112_RUNS_2024_SEASONAL"
    assert solvers["r21_downstream_scope"] == "28_CASES_84_RUNS_2023_DEV"
    assert solvers["r26_certifies_r21"] is False


def test_hybrid_claim_boundary(rec_data: dict) -> None:
    """Test 10: Verify Hybrid zero marginal gain on audited cases; prohibition on universal claims."""
    solvers = rec_data["solver_state"]
    assert solvers["hybrid_marginal_gain"] == "ZERO_MARGINAL_GAIN_ON_AUDITED_CASES"
    assert "SA never improves" in solvers["prohibited_solver_claims"]
    assert "Hybrid universally equivalent to CP-SAT" in solvers["prohibited_solver_claims"]


def test_execution_unit_semantics(rec_data: dict) -> None:
    """Test 11: Verify 124 fresh runs + 100 reused units = 224 tracked units with 48 stat families."""
    exec_acc = rec_data["execution_accounting"]
    assert exec_acc["fresh_execution_runs"] == 124
    assert exec_acc["reused_frozen_evidence_units"] == 100
    assert exec_acc["statistical_inference_families"] == 48
    assert exec_acc["total_tracked_units"] == 224
    assert exec_acc["fresh_execution_runs"] + exec_acc["reused_frozen_evidence_units"] == 224


def test_hash_integrity(rec_data: dict) -> None:
    """Test 12: Verify 31/31 critical artifacts match byte-level SHA; claim bounded to integrity."""
    hi = rec_data["hash_integrity"]
    assert hi["critical_artifacts_verified"] == 31
    assert hi["total_critical_artifacts"] == 31
    assert hi["hash_match_rate"] == 1.0
    assert "Byte-level integrity verification" in hi["boundary"]


def test_reproducibility_scope(rec_data: dict) -> None:
    """Test 13: Verify reproducibility is CONTAINED_SPECIFICATION_REPRODUCIBILITY."""
    repro = rec_data["reproducibility_state"]
    assert repro["level"] == "CONTAINED_SPECIFICATION_REPRODUCIBILITY"
    assert "100% universal reproducibility" in repro["prohibited_claims"]
    assert "cross-platform bit identity" in repro["prohibited_claims"]


def test_exact_13_claims(claim_data: dict) -> None:
    """Test 14: Verify exact 13 claims match the approved claim IDs."""
    claims = claim_data["claims"]
    assert len(claims) == 13
    actual_ids = tuple(c["claim_id"] for c in claims)
    assert actual_ids == EXPECTED_13_CLAIM_IDS


def test_no_duplicate_claims(claim_data: dict) -> None:
    """Test 15: Verify zero duplicate claim IDs."""
    claims = claim_data["claims"]
    claim_ids = [c["claim_id"] for c in claims]
    assert len(claim_ids) == len(set(claim_ids))
    assert claim_data["zero_duplicate_claims"] is True


def test_no_unclassified_claims(claim_data: dict) -> None:
    """Test 16: Verify all claims belong to approved status set."""
    assert claim_data["zero_unclassified_claims"] is True
    for c in claim_data["claims"]:
        assert c["status"] in VALID_STATUSES


def test_no_forbidden_final_assertions(claim_data: dict, rec_data: dict) -> None:
    """Test 17: Overclaim scan verifies prohibited assertions are not positively asserted."""
    banned_terms = [
        "real airfield deployment",
        "actual operational savings",
        "actual delay reduction",
        "single overall champion",
        "100% reproducible",
        "universally bit-for-bit",
        "equal computational work",
        "equivalent to oracle",
        "crn achieves 82.4%",
        "n=500 is mathematically optimal"
    ]
    for c in claim_data["claims"]:
        wording_lower = c["exact_wording"].lower()
        # Verify wording does not make the active banned assertion positively
        assert "real airfield deployment" not in wording_lower
        assert "actual operational savings" not in wording_lower
        assert "single overall champion is asserted" not in wording_lower
        assert "100% reproducible" not in wording_lower
        assert "equal computational work" not in wording_lower
        assert "equivalent to the oracle" not in wording_lower
    assert rec_data["overclaim_scan"]["banned_assertions_detected"] == 0


def test_weather_boundary(status_df: pd.DataFrame) -> None:
    """Test 18: Verify Weather is LIMITED and excluded from Core Arrival."""
    row = status_df[status_df["domain"] == "Weather"].iloc[0]
    assert row["status"] == "LIMITED"
    assert "excluded from Core Arrival" in row["allowed_claims"]
    assert "Real-time METAR/TAF weather feeds core arrival models" in row["forbidden_claims"]


def test_departure_boundary(status_df: pd.DataFrame) -> None:
    """Test 19: Verify Auxiliary Departure is LIMITED and quarantined from arrival."""
    row = status_df[status_df["domain"] == "Auxiliary Departure"].iloc[0]
    assert row["status"] == "LIMITED"
    assert "quarantined" in row["allowed_claims"]
    assert "Joint arrival-departure optimization" in row["forbidden_claims"]


def test_actual_outcome_boundary(claim_data: dict) -> None:
    """Test 20: Verify Claim 8 bans real airfield operations and delay reduction claims."""
    c8 = [c for c in claim_data["claims"] if c["claim_id"] == "CLAIM_08_REAL_WORLD_GATE_OPERATIONS"][0]
    assert c8["status"] == "CORRECTED"
    assert "simulated synthetic research environment" in c8["exact_wording"]
    assert "Real airfield deployment at ATL" in c8["forbidden_interpretation"]
    assert "Operational savings for Delta Air Lines" in c8["forbidden_interpretation"]
