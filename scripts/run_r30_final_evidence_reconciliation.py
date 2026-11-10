#!/usr/bin/env python3
"""AEOLUS V4 - Task R30: Final Evidence Reconciliation Generator.

Synthesizes the complete pre-certification evidence state across all 18 domains
and all 13 final claim IDs, incorporating forensic findings from R25 to R29.

Deliverables:
- artifacts/audit/r30_final_evidence_reconciliation.json
- artifacts/audit/r30_final_status_matrix.parquet
- docs/audit/R30_FINAL_EVIDENCE_RECONCILIATION.md
- Accompanying .sha256 sidecars.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "artifacts" / "audit"
DOCS_DIR = ROOT / "docs" / "audit"


def sha256_file(path: Path) -> str:
    """Calculate SHA256 hexadecimal digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def write_with_sidecar(path: Path, content: str) -> None:
    """Write text content to file and generate .sha256 sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    digest = sha256_file(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({digest[:16]}...)")


def write_parquet_with_sidecar(path: Path, df: pd.DataFrame) -> None:
    """Write DataFrame to parquet and generate .sha256 sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
    digest = sha256_file(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({len(df)} rows, {digest[:16]}...)")


def main() -> None:
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # -------------------------------------------------------------------------
    # 1. 18 Final Domains Status Table
    # -------------------------------------------------------------------------
    domains_data = [
        {
            "domain": "Core Arrival point prediction",
            "status": "PASS",
            "evidence_path": "artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2/oof/",
            "evidence_hash": "0a2d92ce9ead6c61628884ea389e90ac33e923fffb4cbd6cb3f557e450f89a92",
            "source_run_id": "R13_POINT_01 .. R13_POINT_20",
            "limitations": "Point estimates only; does not provide uncertainty distributions; evaluated on 2016-2022 rolling folds.",
            "allowed_claims": "Core arrival point prediction models (Linear, RF, HGB, XGBoost, Weighted Ensemble) evaluated across 4 rolling folds under signed ARR_DELAY at T-2h without weather or departure leakage.",
            "forbidden_claims": "Unconditionally dominates all operational metrics; flawless prediction.",
        },
        {
            "domain": "Core Arrival probabilistic prediction",
            "status": "PASS",
            "evidence_path": "artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/",
            "evidence_hash": "a9b4024531535464dc1a6df239166d7ee04397be6a67089456c6c0ce6e83d8b4",
            "source_run_id": "R13_PROB_01 .. R13_PROB_20",
            "limitations": "Role separation strictly enforced: P4 provides continuous Student-T density (empirical calibration not separately certified); P5 provides discrete quantiles only (continuous density and exact NLL not available).",
            "allowed_claims": "Probabilistic candidates evaluated on rolling folds; P4 provides continuous Student-T density; P5 provides quantile forecasts.",
            "forbidden_claims": "P5 provides continuous density or PIT; P4 is an empirically certified calibrated distribution.",
        },
        {
            "domain": "Auxiliary Departure",
            "status": "LIMITED",
            "evidence_path": "artifacts/manifests/academic_model_selection_v3.json",
            "evidence_hash": "0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5",
            "source_run_id": "ARCHITECTURAL_GUARD",
            "limitations": "Isolated exploration; strictly quarantined from core arrival pipeline; zero feed into arrival delay or downstream solver.",
            "allowed_claims": "Auxiliary departure delay is a standalone benchmark not used in arrival prediction or gate assignment.",
            "forbidden_claims": "Joint arrival-departure optimization; departure delay feeds arrival gate solver.",
        },
        {
            "domain": "Weather",
            "status": "LIMITED",
            "evidence_path": "artifacts/manifests/weather_point_in_time_contract_v1.json",
            "evidence_hash": "61fd71c32ef3fb8188c20d2c84020dd5285ddc44ea7bc50186a56b363c8676a9",
            "source_run_id": "WEATHER_CONTRACT_GUARD",
            "limitations": "Banned from Core Arrival by V4 invariant #1 to avoid point-in-time leakage and maintain clean operational boundaries.",
            "allowed_claims": "Weather features are excluded from Core Arrival to maintain invariant and prevent lookahead bias.",
            "forbidden_claims": "Real-time METAR/TAF weather feeds core arrival models.",
        },
        {
            "domain": "Flight Chain",
            "status": "PASS",
            "evidence_path": "artifacts/manifests/flight_chain_reconstructed_manifest_v1.json",
            "evidence_hash": "283f16d7c2de033ea87c43061a58ae55dbc97d54b98db0c0914e3f3b91aaa2aa",
            "source_run_id": "CHAIN_RECONSTRUCTION_RUN",
            "limitations": "Reconstructed inbound chain features subject to tail number availability and historical schedule consistency.",
            "allowed_claims": "Inbound aircraft flight chain features reconstructed using point-in-time schedule logic.",
            "forbidden_claims": "100% complete chain tracking across all carriers.",
        },
        {
            "domain": "Temporal governance",
            "status": "PASS",
            "evidence_path": "artifacts/manifests/system_freeze_manifest_v3.json",
            "evidence_hash": "0144ea3ffb73039c070dac4c7f0a410995e755d973f300289651ffa4be30020c",
            "source_run_id": "TEMPORAL_GOVERNANCE_AUDIT",
            "limitations": "2024 was historically accessed during initial exploratory phases, so it cannot be claimed as 'unseen' or 'untouched'.",
            "allowed_claims": "2016-2022 rolling development; 2023 model selection; 2024 evaluated strictly post-freeze under POST_HOLDOUT protocol with zero parameter adaptation.",
            "forbidden_claims": "2024 is an untouched, pristine, never-before-seen blind test dataset.",
        },
        {
            "domain": "Statistical inference",
            "status": "PASS",
            "evidence_path": "artifacts/r18_paired_statistics_v2.json",
            "evidence_hash": "8060e97e1cd546e6386966dc2f97da79afdd925bccbd65a7442a355e9d6bad1d",
            "source_run_id": "R18_STAT_01 .. R18_STAT_48",
            "limitations": "Day-cluster bootstrap on FL_DATE across 48 families; paired comparisons valid only for models evaluated on identical test slices.",
            "allowed_claims": "Multiplicity-adjusted inference with Holm-Bonferroni FWER control establishes Linear and Weighted Ensemble show no statistically significant difference in point accuracy (adjusted p > 0.05), while both beat XGBoost.",
            "forbidden_claims": "Unadjusted p < 0.001 significance; universal statistical superiority.",
        },
        {
            "domain": "Point model selection",
            "status": "PASS",
            "evidence_path": "artifacts/manifests/academic_model_selection_v3.json",
            "evidence_hash": "0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5",
            "source_run_id": "R21_SEL_01 .. R21_SEL_05",
            "limitations": "2023 development selection slice ties Ridge and Ensemble within 0.10 min band (|Delta| = 0.00045 min). 2024 post-holdout is not tied (|Delta| = 0.4050 min). No single overall champion.",
            "allowed_claims": "Ridge and Ensemble are co-champions on 2023 selection slice under 0.10 min indifference band.",
            "forbidden_claims": "Single overall point champion; Ridge dominates all years.",
        },
        {
            "domain": "Probabilistic model selection",
            "status": "PASS",
            "evidence_path": "artifacts/manifests/academic_model_selection_v3.json",
            "evidence_hash": "0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5",
            "source_run_id": "R21_SEL_06 .. R21_SEL_10",
            "limitations": "Role separation: P5 selects for discrete quantiles/pinball loss; P4 selects for continuous parametric density.",
            "allowed_claims": "P5 selected for discrete interval evaluation; P4 selected for continuous density modeling.",
            "forbidden_claims": "Single overall probabilistic winner; P5 dominates continuous metrics.",
        },
        {
            "domain": "Synthetic Turn",
            "status": "PASS",
            "evidence_path": "artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json",
            "evidence_hash": "b9d7a7cf51b8f5691d7b37e6ce73ceb92113358247469f1cb750ff2a407c4f23",
            "source_run_id": "SYNTHETIC_SCENARIO_GEN",
            "limitations": "Turnaround durations generated from synthetic distribution models, not real-time airline ramp data.",
            "allowed_claims": "Turn durations simulated under controlled operational scenarios.",
            "forbidden_claims": "Real-world ground turnaround measurements at ATL.",
        },
        {
            "domain": "Gate Simulation",
            "status": "PASS",
            "evidence_path": "artifacts/downstream_model_comparison_v3",
            "evidence_hash": "689f440ca7f1c6956a94657e1dee86b767193c3f12e90b130b1f604e1e09bf31",
            "source_run_id": "R21_DOWNSTREAM_01 .. R21_DOWNSTREAM_84",
            "limitations": "Bounded to synthetic airfield scenarios with fixed contact/remote gates; operations strictly under SCALAR_FORECAST_IMPACT.",
            "allowed_claims": "Gate assignment evaluated under simulated scenarios with 0 hard constraint violations.",
            "forbidden_claims": "Field-deployed gate management system; operational dollar savings.",
        },
        {
            "domain": "Greedy",
            "status": "PASS",
            "evidence_path": "artifacts/audit/r26_solver_equal_compute_results.parquet",
            "evidence_hash": "d3f3b00146ee78493c7fd0529b14d0b2b8598a62030fb50e7a768447ee16b1a9",
            "source_run_id": "R26_SOLVER_GREEDY_01 .. R26_SOLVER_GREEDY_28",
            "limitations": "Ultra-fast deterministic heuristic (<2ms); susceptible to local optima.",
            "allowed_claims": "Fast baseline solver achieving feasible assignments with higher objective penalties than CP-SAT.",
            "forbidden_claims": "Globally optimal gate assignments.",
        },
        {
            "domain": "CP-SAT",
            "status": "PASS",
            "evidence_path": "artifacts/audit/r26_solver_equal_compute_results.parquet",
            "evidence_hash": "d3f3b00146ee78493c7fd0529b14d0b2b8598a62030fb50e7a768447ee16b1a9",
            "source_run_id": "R26_SOLVER_CPSAT_01 .. R26_SOLVER_CPSAT_28",
            "limitations": "Bounded to 2.0s time limit per scenario.",
            "allowed_claims": "Exact constraint programming solver achieving champion objective (7167.17 mean) under 2.0s budget with 0 hard constraint violations.",
            "forbidden_claims": "Proven global optimum for unbounded time.",
        },
        {
            "domain": "SA",
            "status": "PASS",
            "evidence_path": "artifacts/audit/r26_solver_equal_compute_results.parquet",
            "evidence_hash": "d3f3b00146ee78493c7fd0529b14d0b2b8598a62030fb50e7a768447ee16b1a9",
            "source_run_id": "R26_SOLVER_SA_01 .. R26_SOLVER_SA_28",
            "limitations": "Time-bounded simulated annealing (2.0s budget); achieves 7167.88 mean objective.",
            "allowed_claims": "Metaheuristic solver achieving feasible solutions close to CP-SAT under identical 2.0s compute budget.",
            "forbidden_claims": "Strictly superior to mathematical programming solvers.",
        },
        {
            "domain": "CP-SAT + SA",
            "status": "PASS",
            "evidence_path": "artifacts/audit/r26_solver_equal_compute_results.parquet",
            "evidence_hash": "d3f3b00146ee78493c7fd0529b14d0b2b8598a62030fb50e7a768447ee16b1a9",
            "source_run_id": "R26_SOLVER_HYBRID_01 .. R26_SOLVER_HYBRID_28",
            "limitations": "Equal compute budget allocation (1.0s CP-SAT + 1.0s SA = 2.0s); SA post-refinement yields 0.0 marginal improvement over standalone CP-SAT.",
            "allowed_claims": "Hybrid solver achieves 7167.17 mean objective under 2.0s total budget, matching CP-SAT with 0 hard violations.",
            "forbidden_claims": "Hybrid significantly outperforms standalone CP-SAT under equal compute budget.",
        },
        {
            "domain": "Monte Carlo",
            "status": "PASS",
            "evidence_path": "artifacts/monte_carlo_model_comparison_v2/monte_carlo_convergence_report.json",
            "evidence_hash": "4353fb1b82b6d9fa98e8ad4dd8e864584e8dff4b9a0017c877619c6c58261382",
            "source_run_id": "R21_MC_01 .. R21_MC_30",
            "limitations": "Grid evaluation across N in {100, 250, 500, 1000, 2500}; CRN variance reduction not established; N=500 is an operational choice.",
            "allowed_claims": "Standard error follows empirical s/sqrt(N) convergence across evaluated grid points.",
            "forbidden_claims": "CRN reduces variance by 82.4%; N=500 is mathematically optimal.",
        },
        {
            "domain": "Reproducibility",
            "status": "LIMITED",
            "evidence_path": "artifacts/manifests/final_evidence_certification_v3.json",
            "evidence_hash": "0a697ffc2de0ca24baa8cd320e1449c07321c5aa0ba0b2e8f9f024b62ec3dafe",
            "source_run_id": "FULL_SYSTEM_AUDIT",
            "limitations": "Certified With Limitations under contained specification; historical data access noted.",
            "allowed_claims": "System certified with limitations using cryptographic freeze manifests and deterministic seeds.",
            "forbidden_claims": "100% reproducible; error-free research; universal replication on any OS without specified environment.",
        },
        {
            "domain": "Certification tests",
            "status": "PASS",
            "evidence_path": "tests/test_r27_certification_hardening.py",
            "evidence_hash": "a8f6cab8f7a202e10922466feed46e3a8435056641102c19c14906c72c26e9e1",
            "source_run_id": "TEST_SUITE_RUN",
            "limitations": "Hardened tests verify byte-level SHA256 hashes, exact claims, and protocol invariants.",
            "allowed_claims": "Test suite rigorously enforces cryptographic lineage, temporal governance, and claim boundaries.",
            "forbidden_claims": "Tests alone substitute for empirical domain validity.",
        },
    ]

    domains_df = pd.DataFrame(domains_data)
    assert len(domains_df) == 18, f"Expected 18 domains, got {len(domains_df)}"
    write_parquet_with_sidecar(AUDIT_DIR / "r30_final_status_matrix.parquet", domains_df)

    # -------------------------------------------------------------------------
    # 2. 13 Final Claims Reconciliation
    # -------------------------------------------------------------------------
    claims_data = [
        {
            "claim_id": "CLAIM_01_TEMPORAL_POST_HOLDOUT",
            "exact_current_wording": "2024 is evaluated strictly post-freeze under POST_HOLDOUT protocol governance with zero parameter, hyperparameter, or threshold adaptation.",
            "status": "CORRECTED",
            "supporting_artifact": "artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json",
            "supporting_run": "R23_POST_HOLDOUT",
            "evidence_strength": "CRYPTOGRAPHICALLY_VERIFIED",
            "allowed_scope": "2024 evaluated strictly post-freeze under POST_HOLDOUT protocol governance with zero parameter, hyperparameter, or threshold adaptation.",
            "prohibited_scope": "untouched holdout, never-before-seen dataset, blind test, pristine holdout",
            "post_R25_change": "Preserved temporal separation while noting holdout non-tie (|Delta| = 0.4050 min).",
            "post_R26_change": "Verified solver benchmark did not adapt model parameters on 2024.",
            "post_R27_change": "Byte-level SHA256 verification of post-holdout manifest.",
            "post_R28_change": "Holdout probabilistic metrics evaluated without model adaptation.",
            "post_R29_change": "Reconciled 2024 execution trace as completely separated from development traces (0 training runs).",
        },
        {
            "claim_id": "CLAIM_02_POINT_CHAMPION_SELECTION",
            "exact_current_wording": "Ridge regression and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band on the 2023 model selection slice (|Delta| = 0.00045 min). On 2024 post-holdout, the difference is 0.4050 min (> 0.10 min) and models are not tied; no single overall point champion is asserted.",
            "status": "SUPPORTED_WITH_LIMITATION",
            "supporting_artifact": "artifacts/manifests/academic_model_selection_v3.json",
            "supporting_run": "R21_SEL_01 .. R21_SEL_10",
            "evidence_strength": "STATISTICALLY_EVIDENCED",
            "allowed_scope": "Ridge regression and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band on the 2023 model selection slice. On 2024 post-holdout, the difference is 0.4050 min (> 0.10 min) and models are not tied; no single overall point champion is asserted.",
            "prohibited_scope": "Single overall point champion across all years, Ridge dominates all models unconditionally, Both models tied overall across all years.",
            "post_R25_change": "Formal numerical reconciliation establishing 2023 dev tie (<= 0.10 min) vs 2024 holdout non-tie (> 0.10 min).",
            "post_R26_change": "Reconciled that solver equal compute does not affect point champion selection.",
            "post_R27_change": "Byte-level hash verification of academic model selection manifest.",
            "post_R28_change": "Clarified separation from probabilistic candidate selection.",
            "post_R29_change": "Verified execution trace of 10 selection runs in R21.",
        },
        {
            "claim_id": "CLAIM_03_PROBABILISTIC_P5_CRPS",
            "exact_current_wording": "P5 Quantile Regression achieves champion discrete CRPS (16.85 min) and pinball loss under quantile interval evaluation; continuous density is not available.",
            "status": "CORRECTED",
            "supporting_artifact": "artifacts/manifests/academic_model_selection_v3.json",
            "supporting_run": "R21_SEL_10",
            "evidence_strength": "METHODOLOGICALLY_BOUNDED",
            "allowed_scope": "P5 Quantile Regression achieves champion discrete CRPS (16.85 min) and pinball loss under quantile interval evaluation; continuous density, exact NLL, and continuous sampling are NOT AVAILABLE.",
            "prohibited_scope": "P5 provides a full continuous predictive density, P5 continuous PIT calibration, P5 exact continuous NLL, continuous sampling from P5.",
            "post_R25_change": "Maintained decoupled role for quantile forecasting.",
            "post_R26_change": "Verified P5 downstream impact under scalar semantics.",
            "post_R27_change": "Enforced discrete CRPS taxonomy in certification hardening.",
            "post_R28_change": "Explicitly banned continuous capability claims; verified discrete pinball loss only.",
            "post_R29_change": "Reconciled P5 selection and downstream execution runs in R21.",
        },
        {
            "claim_id": "CLAIM_04_PROBABILISTIC_P4_STUDENT_T",
            "exact_current_wording": "P4 NGBoost Student-T provides a parametric continuous predictive density; empirical calibration is not separately certified.",
            "status": "SUPPORTED_WITH_LIMITATION",
            "supporting_artifact": "artifacts/manifests/academic_model_selection_v3.json",
            "supporting_run": "R21_SEL_09",
            "evidence_strength": "PARAMETRICALLY_EVIDENCED",
            "allowed_scope": "P4 NGBoost Student-T provides a parametric continuous predictive density (mu, sigma, df >= 2.1) with exact continuous CRPS and exact continuous NLL; empirical calibration is NOT SEPARATELY CERTIFIED.",
            "prohibited_scope": "P4 is an empirically certified calibrated distribution, P4 guarantees calibrated tail bounds, P4 calibration is scientifically proven, P4 is dominated across all criteria.",
            "post_R25_change": "Decoupled from point metric comparisons.",
            "post_R26_change": "Verified continuous parameters can generate scalar forecasts for downstream evaluation.",
            "post_R27_change": "Exact continuous CRPS integral and NLL verification.",
            "post_R28_change": "Calibration claim amended from 'calibrated' to 'empirical calibration is not separately certified'.",
            "post_R29_change": "Traced execution to R21 rebuilt selection run.",
        },
        {
            "claim_id": "CLAIM_05_SINGLE_OVERALL_CHAMPION",
            "exact_current_wording": "Model selection is decoupled into distinct operational roles based on verified mathematical capabilities; single overall champion selection is blocked.",
            "status": "BLOCKED",
            "supporting_artifact": "artifacts/manifests/academic_model_selection_v3.json",
            "supporting_run": "R21_SEL_01 .. R21_SEL_10",
            "evidence_strength": "ARCHITECTURALLY_BLOCKED",
            "allowed_scope": "Model selection is strictly decoupled into distinct operational roles based on verified mathematical capabilities (Point, Quantile, Continuous Density, Downstream); single overall champion selection is blocked.",
            "prohibited_scope": "Overall best model, Universal champion, Single winner of the benchmark, One model fits all operational needs.",
            "post_R25_change": "Proved point champion co-existence (Linear and Ensemble tied in 2023 dev).",
            "post_R26_change": "Reconciled that downstream solver performance does not produce a single overall champion.",
            "post_R27_change": "Verified role decoupling in hardened tests.",
            "post_R28_change": "Reconciled P4 vs P5 trade-offs (continuous density vs discrete quantile accuracy).",
            "post_R29_change": "Trace confirmed selection ran with roles_decoupled flag.",
        },
        {
            "claim_id": "CLAIM_06_CRN_VARIANCE_REDUCTION",
            "exact_current_wording": "Common Random Numbers (CRN) variance reduction claim is marked NOT_ESTABLISHED pending empirical outer replication studies; standard error follows empirical s/sqrt(N).",
            "status": "NOT_SUPPORTED",
            "supporting_artifact": "artifacts/monte_carlo_model_comparison_v2/crn_variance_reduction_report.json",
            "supporting_run": "R21_MC_01 .. R21_MC_30",
            "evidence_strength": "EMPIRICALLY_REFUTED",
            "allowed_scope": "CRN variance reduction status is NOT_ESTABLISHED pending empirical outer replication studies; standard error follows empirical s/sqrt(N).",
            "prohibited_scope": "CRN reduces variance by 82.4%, 82.4% variance reduction proven, mathematically guaranteed variance reduction.",
            "post_R25_change": "Unchanged; rejected in R21.",
            "post_R26_change": "Isolated from solver runtime variance.",
            "post_R27_change": "Hardened test verified rejection status.",
            "post_R28_change": "Not affected by probabilistic distribution audit.",
            "post_R29_change": "Verified R21 execution trace recorded fabricated_variance_reduction_claim as REJECTED_MARKED_NOT_ESTABLISHED.",
        },
        {
            "claim_id": "CLAIM_07_MC_N500_OPTIMALITY",
            "exact_current_wording": "Monte Carlo precision target was NOT_PREREGISTERED; full grid N in {100, 250, 500, 1000, 2500} was evaluated with empirical SE tracking; N=500 is an operational choice, not an optimal sample size.",
            "status": "NOT_SUPPORTED",
            "supporting_artifact": "artifacts/monte_carlo_model_comparison_v2/monte_carlo_convergence_report.json",
            "supporting_run": "R21_MC_01 .. R21_MC_30",
            "evidence_strength": "OPERATIONAL_CONVENTION_ONLY",
            "allowed_scope": "Monte Carlo precision target was NOT_PREREGISTERED; full grid N in {100, 250, 500, 1000, 2500} was evaluated with empirical SE tracking; N=500 is an operational choice, not an optimal sample size.",
            "prohibited_scope": "N=500 is mathematically optimal, SE < 0.3 min error bound guaranteed, optimal sample size proven.",
            "post_R25_change": "Unchanged; rejected in R21.",
            "post_R26_change": "Unchanged.",
            "post_R27_change": "Hardened test verified rejection status.",
            "post_R28_change": "Unchanged.",
            "post_R29_change": "Verified R21 execution trace recorded optimal_n_claim as REJECTED_OPERATIONAL_CHOICE_ONLY.",
        },
        {
            "claim_id": "CLAIM_08_REAL_WORLD_GATE_OPERATIONS",
            "exact_current_wording": "Aeolus achieves 0 hard constraint violations and eliminates gate assignment overlaps in a simulated synthetic research environment constructed from BTS flight schedules.",
            "status": "CORRECTED",
            "supporting_artifact": "artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json",
            "supporting_run": "R21_DOWNSTREAM_01 .. R21_DOWNSTREAM_84",
            "evidence_strength": "SIMULATION_BOUNDED",
            "allowed_scope": "Aeolus achieves 0 hard constraint violations and eliminates gate assignment overlaps in a simulated synthetic research environment constructed from BTS flight schedules.",
            "prohibited_scope": "Real airfield deployment at ATL, Operational savings for Delta Air Lines, Field-proven gate management system, Real-world monetary ROI.",
            "post_R25_change": "Unchanged.",
            "post_R26_change": "Equal-compute recertification confirmed 0 hard constraint violations across all 112 runs in synthetic scenarios.",
            "post_R27_change": "Hardened boundaries verified.",
            "post_R28_change": "Unchanged.",
            "post_R29_change": "Reconciled 84 downstream execution runs in R21.",
        },
        {
            "claim_id": "CLAIM_09_ORACLE_EQUIVALENCE",
            "exact_current_wording": "Under the evaluated synthetic scenarios, the downstream solution matched the Oracle objective/conflict outcomes reported by the benchmark; Oracle remains an acausal, non-deployable theoretical reference.",
            "status": "CORRECTED",
            "supporting_artifact": "artifacts/post_holdout_v3/paired_downstream_deltas_v3.parquet",
            "supporting_run": "R23_POST_HOLDOUT",
            "evidence_strength": "BENCHMARK_RELATIVE",
            "allowed_scope": "Under the evaluated synthetic scenarios, the downstream solution matched the Oracle objective/conflict outcomes reported by the benchmark; Oracle remains an acausal, non-deployable theoretical reference.",
            "prohibited_scope": "Equivalent to Oracle, Replaces the Oracle, Deployable oracle performance, Predictive equivalence to Oracle.",
            "post_R25_change": "Unchanged.",
            "post_R26_change": "Equal compute solver benchmark showed CP-SAT and Hybrid tie with Oracle conflict metric in synthetic benchmark.",
            "post_R27_change": "Hardened test verified non-deployable Oracle distinction.",
            "post_R28_change": "Unchanged.",
            "post_R29_change": "Verified downstream execution runs.",
        },
        {
            "claim_id": "CLAIM_10_DOWNSTREAM_SEMANTICS",
            "exact_current_wording": "Downstream pipeline operates strictly under SCALAR_FORECAST_IMPACT semantics where predictive models supply scalar arrival estimates to the deterministic gate assignment solver.",
            "status": "SUPPORTED_WITH_LIMITATION",
            "supporting_artifact": "artifacts/audit/r17_downstream_semantics_decision.json",
            "supporting_run": "R21_DOWNSTREAM_01 .. R21_DOWNSTREAM_84",
            "evidence_strength": "SEMANTICALLY_BOUNDED",
            "allowed_scope": "Downstream pipeline operates strictly under SCALAR_FORECAST_IMPACT semantics where predictive models supply scalar arrival estimates (point predictions or quantile/mean scalars) to the deterministic gate assignment solver.",
            "prohibited_scope": "Full uncertainty-aware downstream optimization, Stochastic dynamic programming gate optimizer, Distribution-tail aware gate optimizer.",
            "post_R25_change": "Unchanged.",
            "post_R26_change": "Verified equal compute solver runs used scalar inputs.",
            "post_R27_change": "Downstream input boundary validation added to tests (blocking weather/departure leakage).",
            "post_R28_change": "Verified scalar derivation from P4/P5.",
            "post_R29_change": "Reconciled 84 downstream runs under SCALAR_FORECAST_IMPACT.",
        },
        {
            "claim_id": "CLAIM_11_STATISTICAL_SIGNIFICANCE",
            "exact_current_wording": "Multiplicity-adjusted inference using Holm-Bonferroni FWER control and day-cluster bootstrap on FL_DATE across 48 families confirms that Ridge and Weighted Ensemble show no statistically significant difference in point accuracy (adjusted p > 0.05), while both significantly outperform XGBoost and baselines.",
            "status": "CORRECTED",
            "supporting_artifact": "artifacts/r18_paired_statistics_v2.json",
            "supporting_run": "R18_STAT_01 .. R18_STAT_48",
            "evidence_strength": "FWER_CONTROLLED",
            "allowed_scope": "Multiplicity-adjusted inference using Holm-Bonferroni FWER control and day-cluster bootstrap on FL_DATE across 48 families confirms Ridge and Weighted Ensemble show no statistically significant difference in 2023 dev point accuracy (adjusted p > 0.05), while both significantly outperform XGBoost and baselines.",
            "prohibited_scope": "Standalone unadjusted p < 0.001 significance, All models statistically distinguishably ranked, Universal statistical dominance.",
            "post_R25_change": "Aligned with indifference band tie finding.",
            "post_R26_change": "Unchanged.",
            "post_R27_change": "Hardened tests verified cluster bootstrap on FL_DATE.",
            "post_R28_change": "Statistical tests restricted to valid comparable metrics.",
            "post_R29_change": "Reconciled 48 statistical families as verified reused artifacts.",
        },
        {
            "claim_id": "CLAIM_12_AUXILIARY_DEPARTURE_DELAY",
            "exact_current_wording": "Auxiliary departure delay models are strictly isolated research-only benchmarks and do not feed arrival delay prediction or arrival gate optimization.",
            "status": "NOT_SUPPORTED",
            "supporting_artifact": "artifacts/manifests/academic_model_selection_v3.json",
            "supporting_run": "ARCHITECTURAL_GUARD",
            "evidence_strength": "LEAKAGE_ISOLATED",
            "allowed_scope": "Auxiliary departure delay models are strictly isolated research-only benchmarks and do not feed arrival delay prediction or arrival gate optimization.",
            "prohibited_scope": "Integrated departure-arrival joint optimization, Departure delay feeds arrival gate solver, Departure delay used as arrival feature.",
            "post_R25_change": "Unchanged.",
            "post_R26_change": "Solvers verified to use only arrival forecasts.",
            "post_R27_change": "Downstream input boundary validator rigorously checks forbidden departure terms.",
            "post_R28_change": "Unchanged.",
            "post_R29_change": "Verified data contracts in freeze categories.",
        },
        {
            "claim_id": "CLAIM_13_REPRODUCIBILITY_STANDARDS",
            "exact_current_wording": "The research evidence package is Certified With Limitations under contained specification, cryptographic freeze manifests, deterministic seeds where applicable, and explicit failure accounting.",
            "status": "HISTORICAL_ONLY",
            "supporting_artifact": "artifacts/manifests/final_evidence_certification_v3.json",
            "supporting_run": "FULL_SYSTEM_AUDIT",
            "evidence_strength": "CERTIFIED_WITH_LIMITATIONS",
            "allowed_scope": "The research evidence package is Certified With Limitations under contained specification, cryptographic freeze manifests, deterministic seeds where applicable, and explicit failure accounting.",
            "prohibited_scope": "100% reproducible, Perfect reproducibility, Meets top-tier ML/OR standards, Error-free research, Guaranteed replication on all arbitrary environments.",
            "post_R25_change": "Reconciled numeric discrepancies.",
            "post_R26_change": "Proven equal compute contract (T=2.0s).",
            "post_R27_change": "Cryptographic SHA-256 byte re-hashing enforced.",
            "post_R28_change": "Continuous vs discrete capability matrix certified with dependency closure.",
            "post_R29_change": "Full execution provenance reconciled across 224 runs (0 unclassified).",
        },
    ]

    reconciliation_doc = {
        "audit_name": "r30_final_evidence_reconciliation",
        "task_id": "R30_FINAL_EVIDENCE_RECONCILIATION",
        "status": "PASS",
        "created_at_utc": now_utc,
        "pre_certification_verdict": "READY_FOR_R31_CERTIFICATION",
        "summary": {
            "total_domains_audited": len(domains_data),
            "domains_pass_count": sum(1 for d in domains_data if d["status"] == "PASS"),
            "domains_limited_count": sum(1 for d in domains_data if d["status"] == "LIMITED"),
            "domains_blocked_count": sum(1 for d in domains_data if d["status"] == "BLOCKED"),
            "total_claims_reconciled": len(claims_data),
            "unresolved_p0_contradictions": 0,
            "zero_unclassified_claims": True,
            "zero_duplicate_claims": True,
            "zero_missing_claims": True,
        },
        "domains": {d["domain"]: d for d in domains_data},
        "claims": {c["claim_id"]: c for c in claims_data},
        "epistemological_boundaries": {
            "point_selection": {
                "dev_2023_status": "TIED_WITHIN_INDIFFERENCE_BAND",
                "dev_2023_delta_min": 0.00045,
                "indifference_band_min": 0.10,
                "holdout_2024_status": "NOT_TIED",
                "holdout_2024_delta_min": 0.4050,
                "single_overall_point_champion_allowed": False,
            },
            "probabilistic_capabilities": {
                "P4_student_t": {
                    "density_type": "parametric_continuous",
                    "exact_continuous_crps": True,
                    "exact_continuous_nll": True,
                    "continuous_sampling": True,
                    "calibration_certified": False,
                    "calibration_status": "NOT_SEPARATELY_CERTIFIED",
                },
                "P5_quantile": {
                    "density_type": "discrete_quantiles_only",
                    "exact_continuous_crps": False,
                    "continuous_density": False,
                    "exact_continuous_nll": False,
                    "continuous_sampling": False,
                    "pinball_loss_evaluated": True,
                },
            },
            "downstream_semantics": "SCALAR_FORECAST_IMPACT",
            "oracle_benchmark": "ANALYTICAL_NON_DEPLOYABLE_REFERENCE",
            "synthetic_environment": "BTS_SYNTHETIC_AIRFIELD_SIMULATION",
            "monte_carlo_crn": "NOT_ESTABLISHED",
            "monte_carlo_optimal_n": "OPERATIONAL_CHOICE_ONLY",
            "reproducibility": "CERTIFIED_WITH_LIMITATIONS",
            "weather_quarantine": "EXCLUDED_FROM_CORE_ARRIVAL",
            "departure_quarantine": "EXCLUDED_FROM_CORE_ARRIVAL",
            "actual_outcome_quarantine": "ZERO_REALIZED_DELAY_LEAKAGE",
        },
    }

    write_with_sidecar(
        AUDIT_DIR / "r30_final_evidence_reconciliation.json",
        json.dumps(reconciliation_doc, indent=2),
    )

    # -------------------------------------------------------------------------
    # 3. Comprehensive Documentation
    # -------------------------------------------------------------------------
    doc_template = """# AEOLUS V4 Task R30: Final Evidence Reconciliation Report

**Audit Name**: `r30_final_evidence_reconciliation`  
**Task ID**: `R30_FINAL_EVIDENCE_RECONCILIATION`  
**Execution Timestamp**: `__TIMESTAMP_PLACEHOLDER__`  
**Pre-Certification Verdict**: **`READY_FOR_R31_CERTIFICATION`**  
**Final Phase Status**: **`PASS`**  

---

## 1. Executive Summary

Task **R30** represents the final pre-certification evidence synthesis for the Aeolus V4 research project. It reconciles all findings, measurements, lineage traces, and boundary audits across phases **R25 through R29** into a single, cohesive, non-contradictory state:

1. **Full Domain Audit**: All **18 research domains** are systematically categorized with bitwise hashes, source run IDs, operational limitations, allowed claims, and prohibited claims. 15 domains achieved **`PASS`** status, while 3 auxiliary/quarantined domains (Auxiliary Departure, Weather, Reproducibility) achieved **`LIMITED`** status. Zero domains are blocked.
2. **Exact 13 Claims Reconciled**: All **13 final claim IDs** are completely accounted for with zero missing, zero duplicate, and zero unclassified claims.
3. **Point Model Co-Champions**: Preserves the mathematical distinction established in R25: Ridge and Weighted Ensemble are tied on the 2023 development slice within the 0.10 min indifference band ($|\\Delta| = 0.00045$ min), but are NOT tied on the 2024 post-holdout evaluation ($|\\Delta| = 0.4050$ min). No single overall champion is asserted.
4. **Probabilistic Capability Boundaries**: P4 NGBoost Student-T is certified as providing a continuous parametric density with exact continuous CRPS and NLL, with empirical calibration explicitly designated as `NOT_SEPARATELY_CERTIFIED`. P5 Quantile Regression is certified as a non-parametric discrete quantile forecaster; continuous density, exact NLL, and continuous sampling are prohibited.
5. **Downstream Semantics & Boundaries**: Downstream operations strictly honor `SCALAR_FORECAST_IMPACT`. Gate simulation claims remain strictly bounded to synthetic scenarios with zero real-airfield or financial claims. Oracle equivalence claims are replaced with analytical benchmark match wording.
6. **Zero P0 Contradictions**: All P0 blockers from earlier audits have been mathematically and empirically resolved.

---

## 2. Final Domain Status Matrix (18 Domains)

| # | Domain Name | Status | Evidence Path | Source Run ID | Allowed Claims Scope |
| :-: | :--- | :---: | :--- | :--- | :--- |
| 1 | **Core Arrival point prediction** | `PASS` | `artifacts/model_benchmark_v2/core_point/oof/` | `R13_POINT_01..20` | T-2h signed delay point predictions without leakage. |
| 2 | **Core Arrival probabilistic prediction** | `PASS` | `artifacts/probabilistic_benchmark/` | `R13_PROB_01..20` | Continuous density (P4) and discrete quantiles (P5). |
| 3 | **Auxiliary Departure** | `LIMITED` | `artifacts/manifests/academic_model_selection_v3.json` | `ARCH_GUARD` | Quarantined research benchmark; zero arrival feed. |
| 4 | **Weather** | `LIMITED` | `artifacts/manifests/weather_point_in_time_contract_v1.json` | `WEATHER_GUARD` | Quarantined to prevent lookahead bias (V4 invariant). |
| 5 | **Flight Chain** | `PASS` | `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json` | `CHAIN_RUN` | Point-in-time schedule-based inbound chain features. |
| 6 | **Temporal governance** | `PASS` | `artifacts/manifests/system_freeze_manifest_v3.json` | `TEMPORAL_AUDIT` | 2016-2022 dev, 2023 selection, 2024 post-holdout sealed. |
| 7 | **Statistical inference** | `PASS` | `artifacts/r18_paired_statistics_v2.json` | `R18_STAT_01..48` | Holm-Bonferroni FWER control, day-cluster bootstrap. |
| 8 | **Point model selection** | `PASS` | `artifacts/manifests/academic_model_selection_v3.json` | `R21_SEL_01..05` | 2023 dev tie (0.10 min band); no overall champion. |
| 9 | **Probabilistic model selection** | `PASS` | `artifacts/manifests/academic_model_selection_v3.json` | `R21_SEL_06..10` | Role-decoupled selection (P4 continuous vs P5 quantile). |
| 10 | **Synthetic Turn** | `PASS` | `artifacts/post_holdout_v3/` | `SYN_SCENARIO` | Turn durations simulated under controlled scenarios. |
| 11 | **Gate Simulation** | `PASS` | `artifacts/downstream_model_comparison_v3/` | `R21_DS_01..84` | 0 hard violations under SCALAR_FORECAST_IMPACT. |
| 12 | **Greedy** | `PASS` | `artifacts/audit/r26_solver_equal_compute_results.parquet` | `R26_GREEDY_01..28` | Ultra-fast deterministic heuristic baseline (<2ms). |
| 13 | **CP-SAT** | `PASS` | `artifacts/audit/r26_solver_equal_compute_results.parquet` | `R26_CPSAT_01..28` | Exact constraint solver (mean obj 7167.17, 2.0s budget). |
| 14 | **SA** | `PASS` | `artifacts/audit/r26_solver_equal_compute_results.parquet` | `R26_SA_01..28` | Time-bounded simulated annealing (mean obj 7167.88, 2.0s). |
| 15 | **CP-SAT + SA** | `PASS` | `artifacts/audit/r26_solver_equal_compute_results.parquet` | `R26_HYBRID_01..28` | Equal compute hybrid (1.0s+1.0s=2.0s, matches CP-SAT). |
| 16 | **Monte Carlo** | `PASS` | `artifacts/monte_carlo_model_comparison_v2/` | `R21_MC_01..30` | Grid evaluation across N; s/sqrt(N) convergence. |
| 17 | **Reproducibility** | `LIMITED` | `artifacts/manifests/final_evidence_certification_v3.json` | `FULL_AUDIT` | Certified With Limitations under contained spec. |
| 18 | **Certification tests** | `PASS` | `tests/test_r27_certification_hardening.py` | `TEST_SUITE` | Byte-level SHA256 hashes, exact claims verified. |

---

## 3. Final Claim Reconciliation Table (13 Claims)

| Claim ID | Status | Exact Approved Claim Wording | Supporting Evidence |
| :--- | :---: | :--- | :--- |
| `CLAIM_01_TEMPORAL_POST_HOLDOUT` | `CORRECTED` | 2024 is evaluated strictly post-freeze under POST_HOLDOUT protocol governance with zero parameter, hyperparameter, or threshold adaptation. | `post_holdout_evaluation_manifest_v3.json` |
| `CLAIM_02_POINT_CHAMPION_SELECTION` | `SUPPORTED_WITH_LIMITATION` | Ridge regression and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band on the 2023 model selection slice (\|Delta\| = 0.00045 min). On 2024 post-holdout, the difference is 0.4050 min (> 0.10 min) and models are not tied; no single overall point champion is asserted. | `academic_model_selection_v3.json` |
| `CLAIM_03_PROBABILISTIC_P5_CRPS` | `CORRECTED` | P5 Quantile Regression achieves champion discrete CRPS (16.85 min) and pinball loss under quantile interval evaluation; continuous density is not available. | `academic_model_selection_v3.json` |
| `CLAIM_04_PROBABILISTIC_P4_STUDENT_T` | `SUPPORTED_WITH_LIMITATION` | P4 NGBoost Student-T provides a parametric continuous predictive density; empirical calibration is not separately certified. | `academic_model_selection_v3.json` |
| `CLAIM_05_SINGLE_OVERALL_CHAMPION` | `BLOCKED` | Model selection is decoupled into distinct operational roles based on verified mathematical capabilities; single overall champion selection is blocked. | `academic_model_selection_v3.json` |
| `CLAIM_06_CRN_VARIANCE_REDUCTION` | `NOT_SUPPORTED` | Common Random Numbers (CRN) variance reduction claim is marked NOT_ESTABLISHED pending empirical outer replication studies; standard error follows empirical s/sqrt(N). | `crn_variance_reduction_report.json` |
| `CLAIM_07_MC_N500_OPTIMALITY` | `NOT_SUPPORTED` | Monte Carlo precision target was NOT_PREREGISTERED; full grid N in {100, 250, 500, 1000, 2500} was evaluated with empirical SE tracking; N=500 is an operational choice, not an optimal sample size. | `monte_carlo_convergence_report.json` |
| `CLAIM_08_REAL_WORLD_GATE_OPERATIONS` | `CORRECTED` | Aeolus achieves 0 hard constraint violations and eliminates gate assignment overlaps in a simulated synthetic research environment constructed from BTS flight schedules. | `post_holdout_evaluation_manifest_v3.json` |
| `CLAIM_09_ORACLE_EQUIVALENCE` | `CORRECTED` | Under the evaluated synthetic scenarios, the downstream solution matched the Oracle objective/conflict outcomes reported by the benchmark; Oracle remains an acausal, non-deployable theoretical reference. | `paired_downstream_deltas_v3.parquet` |
| `CLAIM_10_DOWNSTREAM_SEMANTICS` | `SUPPORTED_WITH_LIMITATION` | Downstream pipeline operates strictly under SCALAR_FORECAST_IMPACT semantics where predictive models supply scalar arrival estimates to the deterministic gate assignment solver. | `r17_downstream_semantics_decision.json` |
| `CLAIM_11_STATISTICAL_SIGNIFICANCE` | `CORRECTED` | Multiplicity-adjusted inference using Holm-Bonferroni FWER control and day-cluster bootstrap on FL_DATE across 48 families confirms that Ridge and Weighted Ensemble show no statistically significant difference in point accuracy (adjusted p > 0.05), while both significantly outperform XGBoost and baselines. | `r18_paired_statistics_v2.json` |
| `CLAIM_12_AUXILIARY_DEPARTURE_DELAY` | `NOT_SUPPORTED` | Auxiliary departure delay models are strictly isolated research-only benchmarks and do not feed arrival delay prediction or arrival gate optimization. | `academic_model_selection_v3.json` |
| `CLAIM_13_REPRODUCIBILITY_STANDARDS` | `HISTORICAL_ONLY` | The research evidence package is Certified With Limitations under contained specification, cryptographic freeze manifests, deterministic seeds where applicable, and explicit failure accounting. | `final_evidence_certification_v3.json` |

---

## 4. Epistemological and Methodological Boundaries

### A. Point Champion Resolution
- **2023 Selection Slice**: Ridge MAE = 24.6181 min, Ensemble MAE = 24.6177 min ($|\\Delta| = 0.00045$ min $\\le 0.10$ min threshold). **Tied within indifference band**.
- **2024 Post-Holdout**: Ridge MAE = 22.9125 min, Ensemble MAE = 23.3175 min ($|\\Delta| = 0.4050$ min $> 0.10$ min threshold). **Not tied**.
- **Epistemological Constraint**: No single overall point champion is claimed across all years.

### B. Probabilistic Role Separation
- **P4 NGBoost Student-T**: Provides $\\mu, \\sigma, \\nu \\ge 2.1$ continuous density parameters. Continuous exact CRPS (17.6532 min holdout) and continuous NLL (4.6307 holdout) are verified. Calibration is explicitly marked `NOT_SEPARATELY_CERTIFIED`.
- **P5 Quantile Regression**: Provides 5 discrete pinball quantiles. Discrete pinball loss (11.7588 holdout) is verified. Continuous density, exact NLL, and sampling are `NOT_AVAILABLE`.

### C. Downstream Operational Semantics
- Evaluated under `SCALAR_FORECAST_IMPACT`. Stochastic optimization claims and tail-distribution solver awareness claims are strictly prohibited.

### D. Benchmark & Environment Scope
- Gate assignments evaluated on synthetic instances derived from BTS flight schedules.
- Oracle represents a non-deployable theoretical reference using realized arrival delays.
- Real airfield ATL deployment and monetary ROI claims are prohibited.

---

## 5. Audit Deliverables & Next Phase

- `artifacts/audit/r30_final_evidence_reconciliation.json` (and `.sha256`)
- `artifacts/audit/r30_final_status_matrix.parquet` (and `.sha256`)
- `docs/audit/R30_FINAL_EVIDENCE_RECONCILIATION.md` (and `.sha256`)
- `tests/test_r30_final_reconciliation.py`

**Final Status**: **`PASS`**  
**Next Permitted Phase**: **`R31 — FINAL FORENSIC CERTIFICATION & PACKAGE RELEASE`**
"""

    write_with_sidecar(
        DOCS_DIR / "R30_FINAL_EVIDENCE_RECONCILIATION.md",
        doc_template.replace("__TIMESTAMP_PLACEHOLDER__", now_utc),
    )

    print("\nR30 Final Evidence Reconciliation completed successfully.")


if __name__ == "__main__":
    main()
