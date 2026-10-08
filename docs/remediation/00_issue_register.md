# P00 Issue Register: Baseline Defects & Evidence Audit Findings

**Phase:** `P00 — BASELINE FREEZE & EVIDENCE AUDIT`  
**Audit Date:** 2026-10-09  
**Auditor:** Senior Software Architect & Research Auditor  

This register documents all issues, defects, methodological discrepancies, and suspected anomalies identified during the Phase P00 baseline audit. Every issue is categorized as either `CONFIRMED` (verified by physical code and test execution) or `SUSPECTED` (requires targeted experimental reproduction).

---

## 1. Master Issue Summary Table

| Issue ID | Suspect Reference | Severity | Status | Short Description | Recommended Phase |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **`ISSUE-01`** | F01 | `MAJOR` | **CONFIRMED** | Simulated Annealing unconditionally self-assigns `solver_status="OPTIMAL"`. | P07 / P08 |
| **`ISSUE-02`** | F02 | `MAJOR` | **CONFIRMED** | Remote stand / overflow apron is treated as having infinite capacity with no concurrency bounds. | P06 / P08 |
| **`ISSUE-03`** | F03 | `MAJOR` | **CONFIRMED** | CP-SAT experiences quadratic model construction bottleneck (190s build vs 2s search at $N=1500$). | P08 / P09 |
| **`ISSUE-04`** | F04 | `MAJOR` | **CONFIRMED** | Wall-clock time limit parameter only caps solver search in C++, leaving Python model construction uncapped. | P08 |
| **`ISSUE-05`** | F05 | `MAJOR` | **CONFIRMED** | Scalability benchmark for Hybrid CP-SAT+SA does not execute or account for CP-SAT stage runtime. | P08 / P09 |
| **`ISSUE-06`** | F06 | `MINOR` | **CONFIRMED** | Monte Carlo 100% feasibility refers strictly to Mode B dynamic recourse, not Mode A fixed-plan. | P10 / P11 |
| **`ISSUE-07`** | F07 | `MINOR` | **CONFIRMED** | Historical report narratives contained unbacked metrics (R32 P4 CRPS 17.15m, 82.4% CRN variance reduction). | P11 / P12 |
| **`ISSUE-08`** | F08 | `MAJOR` | **CONFIRMED** | Dual-core benchmark bypasses live model inference, reading pre-cooked predictions from fixture CSV. | P05 / P09 |
| **`ISSUE-09`** | F09 | `MAJOR` | **CONFIRMED** | Incomplete dependencies in `requirements.txt` and missing serialized checkpoint for `P5_quantile_regression`. | P01 / P03 |
| **`ISSUE-10`** | F10 | `CRITICAL` | **CONFIRMED** | Presentation layer completely missing (`dashboard/` empty, `streamlit`/`plotly`/`shap` uninstalled). | P12 / Presentation |
| **`ISSUE-11`** | Legacy Guards | `MINOR` | **CONFIRMED** | Four historical freeze-rigidity tests fail due to legitimate contract additions in Dual Core. | P02 / P03 |

---

## 2. Detailed Issue Records

### `ISSUE-01`: Simulated Annealing Tautological `OPTIMAL` Status

- **Issue ID:** `ISSUE-01`
- **Suspect Reference:** F01
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** Simulated Annealing assigns `solver_status="OPTIMAL"` unconditionally because the status check is mathematically tautological.
- **Root Cause Hypothesis:** In [`src/optimization/sa/annealer.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py#L231), the evaluation call sets:
  ```python
  solver_status="OPTIMAL" if best_obj <= curr_obj else "FEASIBLE"
  ```
  Since `best_obj` tracks the minimum encountered objective ($\text{best\_obj} \le \text{curr\_obj}$ at all times), this condition is always `True`. As a stochastic heuristic, SA cannot prove global optimality or establish dual bounds.
- **Affected Files:**
  - [`src/optimization/sa/annealer.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py)
- **Reproduction Steps:**
  1. Inspect line 231 of `src/optimization/sa/annealer.py`.
  2. Run SA on any non-trivial instance where the global optimum is unknown.
  3. Observe that `res.status` is reported as `"OPTIMAL"`.
- **Expected Behavior:** Heuristic solvers must return `"FEASIBLE"` or `"HEURISTIC_INCUMBENT"`. Only exact solvers (like CP-SAT with 0.0% optimality gap) should return `"OPTIMAL"`.
- **Actual Behavior:** SA returns `"OPTIMAL"`, misleading downstream reports that an optimal gate plan was proven.
- **Evidence:** Physical code at [`src/optimization/sa/annealer.py#L231`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py#L231).
- **Recommended Phase:** P07 (Metaheuristic Calibration) or P08 (Solver Standardization).

---

### `ISSUE-02`: Unbounded Capacity on Remote Stands / Overflow Apron

- **Issue ID:** `ISSUE-02`
- **Suspect Reference:** F02
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** Remote stands (`is_overflow=True`) have zero capacity constraints, permitting an infinite number of aircraft to occupy the apron simultaneously.
- **Root Cause Hypothesis:**
  In [`src/optimization/domain.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py#L430-L431):
  ```python
  for g in gates:
      if g.is_overflow:
          continue  # Remote stand allows concurrent occupancy / bussing
  ```
  In [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py#L141-L142):
  ```python
  for g_idx, gate in enumerate(gate_list):
      if gate.is_overflow:
          continue  # Overflow stand has infinite capacity / no conflict
  ```
  In greedy and SA solvers, all overflow flights are mapped to the single `OVERFLOW_APRON` without capacity checking.
- **Affected Files:**
  - [`src/optimization/domain.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py)
  - [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py)
  - [`src/optimization/solvers/greedy_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py)
  - [`src/optimization/sa/neighborhood.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/neighborhood.py)
- **Reproduction Steps:** Run 1500 flights on 50 gates. At peak congestion, 847 flights are dumped into the single overflow apron simultaneously. The independent verifier reports 0 hard constraint violations.
- **Expected Behavior:** Real airports possess a finite number of remote parking stands (e.g., $K_{\text{remote}} \in [5, 20]$). A physical capacity limit $C_{\text{remote}}$ should be enforceable.
- **Actual Behavior:** An infinite number of flights can be accommodated on remote apron, preventing realistic infeasibility detection.
- **Evidence:** Code in `src/optimization/domain.py:431` and `src/optimization/solvers/cp_sat_solver.py:142`.
- **Recommended Phase:** P06 (Domain & Constraints) / P08 (Solver Tuning).

---

### `ISSUE-03`: Quadratic Model Construction Overhead in CP-SAT

- **Issue ID:** `ISSUE-03`
- **Suspect Reference:** F03
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** Generating pairwise exclusion constraints in Python scales quadratically ($O(N^2 \cdot G)$), consuming 190.0 seconds and 2.2 GB RAM at $N=1500$.
- **Root Cause Hypothesis:** Pairwise non-overlap formulation adds an individual constraint `x[i, g] + x[j, g] <= 1` for every overlapping pair $(i, j)$ on every contact gate $g$. At $N=1500$, this generates 8,704,850 constraints in pure Python before the C++ solver starts.
- **Affected Files:**
  - [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py)
  - [`src/simulation/scalability_benchmark.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py)
- **Reproduction Steps:** Execute [`scripts/run_scalability_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_scalability_benchmark.py) on $N=1500, G=50$.
- **Expected Behavior:** Sweep-line interval formulation or cumulative constraints should be used to avoid $O(N^2 \cdot G)$ explicit pairwise constraints, keeping model build time in milliseconds.
- **Actual Behavior:** Python loops freeze the process for 190 seconds creating millions of constraints.
- **Evidence:** Table in [`artifacts/stress_1500x50/benchmark_report.md#L36`](file:///D:/Study/Code/Python/Aelous/artifacts/stress_1500x50/benchmark_report.md#L36): `Model Build: 190,034.4 ms`, `Solver Search: 2,000.0 ms`.
- **Recommended Phase:** P08 (CP-SAT Interval Formulation) / P09 (Scalability Engineering).

---

### `ISSUE-04`: Unenforced Model Building Wall-Clock Time Limit

- **Issue ID:** `ISSUE-04`
- **Suspect Reference:** F04
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** The configured time limit (`time_limit_seconds = 2.0`) is passed only to `solver.parameters.max_time_in_seconds`, leaving Python model construction completely unconstrained.
- **Root Cause Hypothesis:** Total execution time of `CPSatGateSolver.solve()` is the sum of model creation and solver search. Since OR-Tools `max_time_in_seconds` only halts C++ search, total runtime was 192,034.4 ms (over 3 minutes) instead of 2.0 seconds.
- **Affected Files:**
  - [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py#L201-L208)
- **Reproduction Steps:** Run `CPSatGateSolver.solve()` on $N=1500$ with `time_limit_seconds = 2.0`. Measure total time between call entry and return.
- **Expected Behavior:** Total wall-clock budget should encompass the entire solver lifecycle. If model building exceeds budget, solver should timeout gracefully.
- **Actual Behavior:** Process takes 192 seconds while claiming a 2.0s ceiling.
- **Evidence:** `src/optimization/solvers/cp_sat_solver.py:202` and `artifacts/stress_1500x50/aggregate_metrics.json`.
- **Recommended Phase:** P08 (Solver Lifecycle & Time Budgeting).

---

### `ISSUE-05`: Omission of CP-SAT Phase in Hybrid Scalability Benchmark

- **Issue ID:** `ISSUE-05`
- **Suspect Reference:** F05
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** In the scalability benchmark, Hybrid solver does not run or time the CP-SAT stage when standalone CP-SAT timed out, artificially recording $0.1$ ms model build time and $1.0$ s total runtime.
- **Root Cause Hypothesis:**
  In [`src/simulation/scalability_benchmark.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py#L438-L456):
  ```python
  if res_cpsat is not None and res_cpsat.feasible:
      incumbent = res_cpsat.assignments
  else:
      incumbent = res_greedy.assignments
  solver_sa_half = TimeBudgetedSimulatedAnnealingSolver(...)
  res_hyb, ... = solver_sa_half.solve(...)
  ```
  Instead of calling `HybridGateSolver.solve()`, the benchmark reuses `res_cpsat`. Because CP-SAT returned `UNKNOWN` (not feasible), Hybrid directly fell back to Greedy and executed SA with a 1.0s budget, omitting CP-SAT building time entirely.
- **Affected Files:**
  - [`src/simulation/scalability_benchmark.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py)
  - [`src/optimization/solvers/hybrid_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/hybrid_solver.py)
- **Reproduction Steps:** Inspect lines 435–480 in `src/simulation/scalability_benchmark.py`. Compare recorded Hybrid model construction time ($0.1$ ms) with CP-SAT model construction time ($190,034$ ms).
- **Expected Behavior:** Hybrid solver execution should fairly measure both Stage 1 (CP-SAT/Greedy) and Stage 2 (SA refinement) within its integrated budget.
- **Actual Behavior:** Hybrid appears to execute in 1,078 ms without incurring CP-SAT overhead.
- **Evidence:** `src/simulation/scalability_benchmark.py:438-477` and `artifacts/stress_1500x50/benchmark_report.md:38`.
- **Recommended Phase:** P08 / P09 (Benchmark Parity).

---

### `ISSUE-06`: Ambiguity in Monte Carlo 100% Feasibility Interpretation

- **Issue ID:** `ISSUE-06`
- **Suspect Reference:** F06
- **Severity:** `MINOR`
- **Status:** `CONFIRMED` (Presentation/Interpretation Risk)
- **Description:** Claims that "P4 achieved 100% feasibility under Monte Carlo realizations" can be misinterpreted as fixed-schedule robustness, whereas 100% feasibility was achieved only under Mode B dynamic recourse.
- **Root Cause Hypothesis:**
  In [`src/evaluation/week10_robustness_recourse.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/week10_robustness_recourse.py), Mode A evaluates the fixed plan (no reassignment, conflicts occur), while Mode B re-optimizes assignments dynamically. On summer peak (`SCEN_2024_SUMMER`), Mode A fixed plan maintained feasibility only for P4 (100%), while Schedule-only dropped to 27.6% and Ridge dropped to 2.4%. Mode B dynamic recourse resolved 100% of conflicts for all models. If reports do not sharply distinguish Mode A vs Mode B, readers may assume all models achieved 100% fixed-plan feasibility.
- **Affected Files:**
  - [`src/evaluation/week10_robustness_recourse.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/week10_robustness_recourse.py)
  - [`README.md`](file:///D:/Study/Code/Python/Aelous/README.md)
  - [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)
- **Reproduction Steps:** Review Section 2.3 of `README.md` and `test_p11r_post_holdout.py:test_p11r_robustness_and_recourse`.
- **Expected Behavior:** Documentation and metrics must always explicitly specify `MODE_A_FIXED_PLAN` vs `MODE_B_DYNAMIC_RECOURSE`.
- **Actual Behavior:** Reconciled in Phase P14/P15 documentation, but remains an interpretation hazard in the thesis narrative.
- **Evidence:** Detailed in `FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md` Claim 09 & 10.
- **Recommended Phase:** P10 / P11 (Evaluation Protocol).

---

### `ISSUE-07`: Inconsistent Historical Metrics in Documentation

- **Issue ID:** `ISSUE-07`
- **Suspect Reference:** F07
- **Severity:** `MINOR`
- **Status:** `CONFIRMED`
- **Description:** Prior historical documentation drafts contained unbacked metric values (e.g., Phase R32 draft claimed P4 CRPS was $17.15$ m and NLL was $4.03$, which were unbacked by underlying artifacts; an early claim of "82.4% CRN variance reduction" was unproven).
- **Root Cause Hypothesis:** Historical audit documentation accumulated unverified claims before the forensic reconciliations in R33–R37 and P14 established strict artifact lineage.
- **Affected Files:**
  - [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)
  - [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)
  - [`THESIS_EVIDENCE_NORMALIZATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/THESIS_EVIDENCE_NORMALIZATION_REPORT.md)
- **Reproduction Steps:** Read `artifacts/audit/r33_p4_metric_lineage.json` Section `discrepancy_investigation`.
- **Expected Behavior:** All claims in thesis text must match the exact serialized numbers in certified Parquet/JSON artifacts.
- **Actual Behavior:** Fully documented and retracted in Phase P14 (`CLAIM_06_CRN_VARIANCE_REDUCTION = NOT_SUPPORTED`, R32 values marked invalid).
- **Evidence:** `artifacts/audit/r33_p4_metric_lineage.json:47-64`.
- **Recommended Phase:** P11 / P12 (Scientific Normalization).

---

### `ISSUE-08`: Dual Core Benchmark Uses Pre-cooked Predictions

- **Issue ID:** `ISSUE-08`
- **Suspect Reference:** F08
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** The Dual Core end-to-end benchmark (`src/evaluation/dual_core_benchmark.py`) does not perform native model inference on raw features. Instead, it parses pre-calculated prediction columns from a fixture CSV file.
- **Root Cause Hypothesis:** In `load_and_build_branch_turns()` ([`src/evaluation/dual_core_benchmark.py#L150-L161`](file:///D:/Study/Code/Python/Aelous/src/evaluation/dual_core_benchmark.py#L150-L161)), delays are extracted as `pred_delays[fkey] = p_min - s_min` from `atl_1500_flights_cpsat_turnaround_schedule.csv`. For `DUAL_PROBABILISTIC`, it simply adds Gaussian noise `rng.normal(0.0, 10.0)` instead of sampling from the trained NGBoost model.
- **Affected Files:**
  - [`src/evaluation/dual_core_benchmark.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/dual_core_benchmark.py)
  - [`scripts/run_dual_core_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_dual_core_benchmark.py)
- **Reproduction Steps:** Inspect lines 150–198 of `src/evaluation/dual_core_benchmark.py`.
- **Expected Behavior:** True end-to-end evaluation should feed tabular features into `p4_model.predict_distribution()` and `dep_model.predict_distribution()`.
- **Actual Behavior:** Benchmark is decoupled into a fixture-based simulation evaluation.
- **Evidence:** `src/evaluation/dual_core_benchmark.py:153-198`.
- **Recommended Phase:** P05 (Turn Pairing & Synthesis) / P09 (Dual Core Integration).

---

### `ISSUE-09`: Missing Requirements Pins & Unserialized Checkpoints

- **Issue ID:** `ISSUE-09`
- **Suspect Reference:** F09
- **Severity:** `MAJOR`
- **Status:** `CONFIRMED`
- **Description:** `requirements.txt` lacks critical production dependencies (`ortools`, `ngboost`, `lightgbm`, `torch`), and `P5_quantile_regression` lacks a physical serialized model checkpoint file on disk.
- **Root Cause Hypothesis:**
  - `requirements.txt` was locked in Week 5 with a test enforcing that future dependencies were omitted.
  - P5 was fitted in earlier research phases and only its evaluation predictions were retained in Parquet/JSON artifacts; the raw model weights were never serialized to disk.
- **Affected Files:**
  - [`requirements.txt`](file:///D:/Study/Code/Python/Aelous/requirements.txt)
  - [`tests/test_feature_manifest.py`](file:///D:/Study/Code/Python/Aelous/tests/test_feature_manifest.py)
  - `artifacts/probabilistic/`
- **Reproduction Steps:** Run `pip install -r requirements.txt` in a fresh environment. Attempting to import `ortools` or `ngboost` will fail. Look for P5 weights file in `artifacts/probabilistic/` (does not exist).
- **Expected Behavior:** A unified `requirements.txt` or `requirements-full.txt` should declare all dependencies needed to run optimization and probabilistic modeling.
- **Actual Behavior:** `.venv` has the dependencies installed, but `requirements.txt` does not declare them.
- **Evidence:** Line count of `requirements.txt` is only 12 lines; P14 Report Step 7 notes `NO_SERIALIZED_CHECKPOINT` for P5.
- **Recommended Phase:** P01 (Environment & Dependency Harmonization) / P03 (Contract Reconciliation).

---

### `ISSUE-10`: Presentation Layer (Dashboard & SHAP) Completely Missing

- **Issue ID:** `ISSUE-10`
- **Suspect Reference:** F10
- **Severity:** `CRITICAL` (Thesis Deliverable Gap)
- **Status:** `CONFIRMED`
- **Description:** The interactive presentation layer (Streamlit/Plotly dashboard in `dashboard/`) and SHAP explainability analyses outlined in the thesis roadmap (Week 12) are completely unimplemented.
- **Root Cause Hypothesis:** Development prioritized scientific pipeline certification (Phases R20–R39, P10–P15) over the frontend presentation layer.
- **Affected Files:**
  - `dashboard/` (completely empty, 0 bytes)
  - `docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md`
- **Reproduction Steps:** Check directory `dashboard/`. Search installed packages for `streamlit`, `plotly`, `shap`.
- **Expected Behavior:** An interactive web dashboard displaying gate timelines, flight delays, ML risk distributions, and optimization KPIs.
- **Actual Behavior:** `dashboard/` contains 0 files; neither `streamlit` nor `plotly` nor `shap` is installed.
- **Evidence:** Documented in `artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md` Section 7.
- **Recommended Phase:** P12 (Presentation Layer / Dashboard Implementation).

---

### `ISSUE-11`: Four Historical Freeze-Rigidity Test Failures

- **Issue ID:** `ISSUE-11`
- **Suspect Reference:** Legacy Rigidity
- **Severity:** `MINOR`
- **Status:** `CONFIRMED`
- **Description:** 4 historical tests fail during full pytest runs because legacy freeze manifests and task enums were not updated when `ModelTask.CORE_DEPARTURE` and `domain.py` Dual Turn extensions were legitimately introduced.
- **Root Cause Hypothesis:**
  1. `test_registry_integration_retrieval`: Asserts `task in {'auxiliary_departure', 'core_arrival'}`. Adding `core_departure` triggered an `AssertionError`.
  2. `test_guard_v3_verifies_all_frozen_files` & `test_guard_v3_authorizes_clean_post_holdout_access`: `FinalEvaluationGuardV2` checks `leakage_rules.py` against its pre-Dual-Core hash.
  3. `test_r22_freeze_manifest_integrity`: Asserts hash of `domain.py`, which was extended with `precomputed_gate_out_min` for Dual Turn Engine.
- **Affected Files:**
  - [`tests/benchmark/test_model_registry.py`](file:///D:/Study/Code/Python/Aelous/tests/benchmark/test_model_registry.py#L33)
  - [`tests/test_r22_system_freeze_v3.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r22_system_freeze_v3.py)
  - [`tests/test_r27_certification_hardening.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r27_certification_hardening.py#L266)
- **Reproduction Steps:** Run `.venv/Scripts/python.exe -m pytest tests/benchmark/test_model_registry.py tests/test_r22_system_freeze_v3.py tests/test_r27_certification_hardening.py -q`.
- **Expected Behavior:** Guard and registry tests should be task-aware, recognizing `CORE_DEPARTURE` and certified Dual Core extensions without breaking historical freeze validation.
- **Actual Behavior:** 4 tests fail with hash mismatch or enum mismatch; 1,369 pass.
- **Evidence:** Full pytest output: `4 failed, 1369 passed in 95.25s`.
- **Recommended Phase:** P02 / P03 (Test Suite Reconciliation & Guard Modernization).
