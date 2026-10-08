# THESIS EVIDENCE NORMALIZATION REPORT (PHASE P15)

**Phase**: `P15 — Thesis Evidence Normalization Without Scientific Changes`  
**Generated At**: 2026-10-04T13:00:00Z  
**Branch**: `v4-final-forensic-certification`  
**Git HEAD Commit**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Precondition Status**:
- `P14_STATUS = PASS`
- `CERTIFICATION_STATUS = CERTIFIED_WITH_LIMITATIONS`
- `REBUILD_REQUIRED = NO`

---

## 1. Executive Summary & Verification of Boundaries

Phase P15 is a **STRICTLY DOCUMENTATION-ONLY** phase designed to synchronize all current-facing scientific documentation with the authoritative determinations of Phase P14 ([`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md) and [`artifacts/audit/final_scientific_certification_p14.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_scientific_certification_p14.json)).

### Strict Non-Negotiable Invariants Verified:
1. **Zero Code Modifications**: No python scripts in `src/`, `scripts/`, or `tests/` were altered.
2. **Zero Model Modifications**: Model checkpoints, weights, and parameters were untouched. P4 checkpoint hash `e7e7462fa1a115160da3ec4416ad8b857790150965d1d6a623719b0f4dcfbc1a` verified.
3. **Zero Parquet / Data Access**: Row-level 2024 data was NOT accessed or reopened.
4. **Zero Config / Manifest Invalidation**: [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml) and [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json) remained bit-for-bit immutable; freeze integrity was preserved.
5. **Dual 2024 Evidence Separation**: Preserved clear demarcation between `HISTORICAL_2024_RESULTS` (pre-repair) and `P11R_POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR` (post-repair).

---

## 2. Comprehensive Normalization Matrix

The following table documents every documentation change performed across the repository during Phase P15, detailing the prior state, normalized state, authoritative forensic source, and rationale.

| Target Document | Section / Location | Pre-Normalization State (Old / Incomplete) | Normalized State (Phase P15 / P14 Authority) | Authoritative Source | Forensic Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md) | Header & Badges | Referenced Phase R37 V5 Certified; cited 180 regression tests. | Updated to Phase P14 Certified (`CERTIFIED_WITH_LIMITATIONS`, `REBUILD_REQUIRED = NO`); active test badge updated to 1,216 active tests (100% PASS). | P14 Report, P12-R1 Report | Reflected current full test collection and P14 final scientific certification. |
| [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md) | Section 2.1 (2024 Arrival Prediction Table) | Reported only Historical 2024 metrics from `post_holdout_v3`; lacked post-repair P11-R metrics. | Dual reporting implemented: presents both Historical 2024 (Ridge MAE 22.91m, P5 Approx CRPS 16.77m, P4 CRPS 17.65m) and Repaired P11-R 2024 (Ridge MAE 23.39m, P4 Point MAE 21.97m, RMSE 54.21m, Continuous CRPS 18.33m closed-form, NLL 4.62, Brier 0.1544, $\nu=2.52$). | P11-R Report, P14 Claim 04/05/06 | Mandated dual reporting preventing confusion between historical and post-repair evidence generations. |
| [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md) | Section 2.2 (Downstream Optimization) | Described only R26 28-instance seasonal benchmark; lacked P10-A/P11-R 64-run native P4 evaluation. | Added P4 native downstream evaluation (64 runs, 500 shocks, 100% feasibility Summer peak vs 27.6% schedule-only, 2.4% Ridge, 0.0% oracle); emphasized equal wall-clock 2.0s budget and zero real-world ATL claims. | P10-A Report, P11-R Report, P14 Claim 07/08/09 | Clearly defined downstream synthetic simulation boundary and equal wall-clock fairness. |
| [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md) | Section 3 (Scientific Boundaries) | Enumerated R37 forensic boundaries. | Formally enumerated all 9 epistemological limitations certified in Phase P14. | P14 Report Section 4 | Formal alignment with P14 limitation registry. |
| [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md) | Section 4 (Verification Instructions) | Listed historical 180-test invocation. | Added commands for full 1,216 test suite, 75 narrow certification suite, 21 P11-R downstream suite, and 51 protocol guard suite. | P12-R1 Report Section 6 | Enabled independent verification of all active test tiers. |
| [`project_structure.md`](file:///D:/Study/Code/Python/Aelous/project_structure.md) | Header & Protocol | Protocol: `AEOLUS_V4_SYNCHRONIZED_PROTOCOL` (R37); 180 regression tests. | Protocol: `AEOLUS_V4_PHASE14_FINAL_CERTIFICATION`; Lifecycle: `CERTIFIED_WITH_LIMITATIONS` (`REBUILD_REQUIRED = NO`); 1,216 active tests (100% PASS). | P14 Report, P12-R1 Report | Accurate protocol and lifecycle state specification. |
| [`project_structure.md`](file:///D:/Study/Code/Python/Aelous/project_structure.md) | Directory Tree | Missing downstream modules (`src/evaluation/native_downstream_p4.py`, `week10_robustness_recourse.py`), scripts (`run_native_p4_downstream.py`, `run_p11r_...`), and new root reports. | Full directory tree updated with all Phase P10–P15 source files, test suites, scripts, and root forensic reports. | Codebase inspection | Complete and faithful architectural representation. |
| [`project_structure.md`](file:///D:/Study/Code/Python/Aelous/project_structure.md) | Section 2 (Downstream Flow) | Forecast input described as generic arrival delay predictions without decoupled roles. | Clarified decoupled roles: Role B (P5, forecast-only 9 quantiles) vs Role C (P4, 3-parameter continuous density, native Monte Carlo sampling). | R39, P10-A, P14 Claim 05/06 | Architectural firewall between quantile forecasting and continuous simulation. |
| [`project_structure.md`](file:///D:/Study/Code/Python/Aelous/project_structure.md) | Section 3 (Verification) | Listed 180-test single line command. | Listed 75-test narrow certification command, 21-test P11-R regression command, and full 1,216 active test command. | P12-R1 Report | Reproducibility instruction normalization. |
| [`docs/CURRENT_STATE.md`](file:///D:/Study/Code/Python/Aelous/docs/CURRENT_STATE.md) | Document Version & Header | Version 3.0.0; State: `FINAL_FORENSICALLY_CERTIFIED_WITH_LIMITATIONS` (R37 V5). | Version 4.0.0; State: `CERTIFIED_WITH_LIMITATIONS` (Phase P14 Final Certification, `REBUILD_REQUIRED = NO`). | P14 Report | Synchronized state registry with latest supreme audit. |
| [`docs/CURRENT_STATE.md`](file:///D:/Study/Code/Python/Aelous/docs/CURRENT_STATE.md) | Section 1 & 2 (Catalog & Invariants) | Reported only historical 2024 metrics; lacked dual generation framing. | Full dual reporting: Historical 2024 vs Repaired P11-R 2024; detailed P4 Student-T closed form formula and parameter properties; P5 forecast-only boundaries. | P11-R Report, P14 Claim 04/05/06 | Definitive technical documentation of model capabilities. |
| [`docs/CURRENT_STATE.md`](file:///D:/Study/Code/Python/Aelous/docs/CURRENT_STATE.md) | Section 3.4 (Test Suite Reconciliation) | Did not exist. | Added Section 3.4 documenting test harness deconstruction: 1,216 active tests, 75 certification tests, 21 downstream tests, 51 protocol guard tests, 4 quarantined legacy guard tests. | P12-R1 Report | Full resolution of historical test count discrepancies. |
| [`PROJECT_SUMMARY.md`](file:///D:/Study/Code/Python/Aelous/PROJECT_SUMMARY.md) | Header & Section 1 | Trạng thái Phase R37 V5; 180 tests; số liệu 2024 đơn lẻ. | Trạng thái Phase P14 Tối hậu (`CERTIFIED_WITH_LIMITATIONS`, `REBUILD_REQUIRED = NO`); 1.216 bài test; số liệu 2 thế hệ (Lịch sử vs P11-R Repaired); kết quả mô phỏng P4 native draws 100% khả thi mùa hè. | P11-R, P12-R1, P14 Report | Đồng bộ hóa toàn diện tài liệu tóm tắt tiếng Việt. |
| [`PROJECT_SUMMARY.md`](file:///D:/Study/Code/Python/Aelous/PROJECT_SUMMARY.md) | Section 5 (Resolution Matrix) | Dừng lại ở các mốc R25–R37. | Mở rộng bổ sung đầy đủ các pha P10-A, P10-B, Freeze-Gate, P11-R, P12/P12.1/P12-R1, P13, P14, P15. | P10–P15 Trajectory | Lịch sử giải quyết vấn đề xuyên suốt và nhất quán. |
| [`PROJECT_SUMMARY.md`](file:///D:/Study/Code/Python/Aelous/PROJECT_SUMMARY.md) | Section 7 (Tài liệu tra cứu) | Tham chiếu các tài liệu V5 cũ. | Cập nhật bộ báo cáo tối hậu P10–P15 ở thư mục gốc repository. | P10–P15 Reports | Bản đồ điều hướng tài liệu chuẩn xác cho hội đồng nghiệm thu. |
| [`docs/README.md`](file:///D:/Study/Code/Python/Aelous/docs/README.md) | Supercedence Matrix | V5 (R37) ranked highest; lacks P10-P15 entries. | Updated matrix: P14 Certification Report ranked HIGHEST PRECEDENCE, followed by P11-R, P12-R1, P13, and P15 reports; `CURRENT_STATE.md` updated to v4.0.0. | P14 Report | Master documentation supercedence hierarchy clearly established. |
| [`docs/README.md`](file:///D:/Study/Code/Python/Aelous/docs/README.md) | Navigation Map | 5 sections without root reports. | Added Section 0 for Root Supreme Certification Reports (P10–P15). | Repository structure | Transparent access to supreme forensic evidence. |
| [`docs/README.md`](file:///D:/Study/Code/Python/Aelous/docs/README.md) | Section 3 (Citation Guidance) | Prescribed quoting single holdout table. | Prescribed strict dual holdout citation rules, decoupled role boundaries, synthetic downstream limits, and 1,216 test citation. | P14 Report, P12-R1 Report | Fail-safe guidance preventing misquotation in academic papers and thesis. |

---

## 3. Epistemological and Methodological Boundaries Normalized

1. **Role Decoupling (No Single Overall Champion)**:
   - **`arrival_linear_baseline_v1` (Ridge)**: Fast linear point reference (P11-R MAE $23.39$ min; Historical MAE $22.91$ min).
   - **`P5_quantile_regression` (Role B)**: Marginal Quantile Forecast Champion across 9 pre-registered quantiles (Historical Approx CRPS $16.77$ min, Pinball Loss $6.82$ min). Strictly **forecast-only**, ineligible for continuous simulation, never reconstructed or retrained.
   - **`P4_ngboost_student_t` (Role C)**: Continuous Downstream Simulation Champion providing a 3-parameter Student-T parametric distribution ($\mu, \sigma, \nu$). Checkpoint `e7e7462f...` verified. P11-R Repaired metrics: Continuous closed-form CRPS $18.33$ min, NLL $4.62$, MAE $21.97$ min, RMSE $54.21$ min, Brier $0.1544$, $\nu = 2.52$. Sole authorized probabilistic engine for Monte Carlo downstream simulation.
2. **Dual 2024 Evaluation Reporting**:
   - Historical 2024 results (`HISTORICAL_2024_RESULTS`, pre-repair) and post-repair re-evaluation results (`P11R_POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR`) are presented distinctly in all tables and text.
   - The post-repair evaluation is never characterized as "unseen", "first-access", or "untouched".
3. **Downstream Equal Wall-Clock Fairness & Synthetic Scope**:
   - All 4 solvers (Greedy, CP-SAT, SA, Hybrid) operate under a uniform configured ceiling of $T_{\text{total}} = 2.0$ seconds. Wall-clock equality is proven; computational work equality is not proven due to intrinsic algorithmic differences.
   - Simulation is conducted on synthetic operational scenarios; zero claim of real-world ATL airport deployment is made.
4. **Reproducibility Scope**:
   - Reproducibility is formally classified as `CONTAINED_SPECIFICATION_REPRODUCIBILITY` under Python 3.11.15 AMD64 on Windows 10 within the pinned virtual environment. Universal bit-for-bit reproducibility across disparate architectures is disclaimed.
5. **Test Scope Governance**:
   - Total active pytest collection: **1,216 tests passing 100%**.
   - Narrow certification gate: **75 tests passing 100%**.
   - Downstream regression suite: **21 tests passing 100%**.
   - Protocol guard suite: **51 tests passing 100%**.
   - Four legacy freeze-guard tests are safely quarantined in `pytest.ini` (`retired_guard_scope_manifest.json`), preserving historical auditability with zero active production callers.

---

## 4. Verification of Frozen Integrity

Live execution during Phase P15 verified:
- `python -m pytest tests/test_r24_final_certification.py tests/test_r27_certification_hardening.py tests/test_r31_final_certification.py tests/test_r37_final_certification.py tests/test_phase10_system_freeze.py -q`: **75 passed in 1.43s**.
- `python -m pytest tests/downstream/test_p11r_post_holdout.py tests/downstream/test_week10_robustness_freeze.py tests/downstream/test_native_p4_downstream.py -q`: **21 passed in 6.69s**.
- `python -m pytest tests/test_audit_provenance_guards.py tests/test_holdout_guard.py tests/test_holdout_and_fold_guards.py tests/test_week5_hpo_guard_cleanup_provenance.py tests/test_r20_freeze_gate.py tests/test_r22_system_freeze_v3.py tests/test_phase10_system_freeze.py -q`: **51 passed in 3.37s**.
- Model weights SHA-256: `e7e7462fa1a115160da3ec4416ad8b857790150965d1d6a623719b0f4dcfbc1a` (MATCH).
- System freeze manifest SHA-256: `9e6693dafae3ba439c0b6b9a5f3038ec87f0dd63f75dbcad5752ff8da0f98214` (MATCH).

---

## 5. Phase P15 Final Determination

```
================================================================================
PHASE P15 GATE CERTIFICATION VERDICT
================================================================================
P15_STATUS                                  = PASS
GATE_P15                                    = PASS
NORMALIZATION_TYPE                          = DOCUMENTATION_ONLY
SCIENTIFIC_METHODOLOGY_MODIFIED             = NO
MODELS_RETRAINED                            = NO
2024_REOPENED_OR_RE_EVALUATED               = NO
CODE_ASSERTIONS_MODIFIED                    = NO
FREEZE_MANIFEST_VALID                       = YES
AUTHORITATIVE_SOURCE_ALIGNMENT              = COMPLETE (P14 ALIGNED)
FINAL_THESIS_CERTIFICATION_STATE            = CERTIFIED_WITH_LIMITATIONS
REBUILD_DECISION                            = NO_REBUILD_REQUIRED
================================================================================
```
