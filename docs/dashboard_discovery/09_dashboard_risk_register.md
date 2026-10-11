# Phase P09.5 Technical Discovery: Dashboard Technical Risk Register

**Document ID:** `DISC-09-RISKS`  
**Phase:** `P09.5 — DASHBOARD DISCOVERY & TECHNICAL HANDOFF`  
**Audit Date:** 2026-10-09  
**Auditor Roles:** Senior Software Architect, QA Automation Lead, Research Software Auditor  

---

## 1. Risk Register Overview

Building an interactive demonstration dashboard for a mathematical optimization and machine learning research thesis introduces distinct technical, scientific, and usability risks. The matrix below documents 24 audited risks along with their likelihood, operational impact, affected components, proposed mitigations, and verification tests.

---

## 2. Comprehensive Risk Register

| Risk ID | Risk Description | Likelihood | Impact | Affected Component | Proposed Mitigation | Verification Test |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **RSK-01** | **Streamlit Rerun Solver Thrashing:** Widget interaction re-triggers expensive CP-SAT/SA optimization. | **High** | **High** | UI State / Solvers | Isolate solver invocation behind an explicit `st.button()`; store `OptimizationResult` in `st.session_state`. | Toggle dropdowns after solve; verify solver is not re-executed. |
| **RSK-02** | **Uncancellable Optimization Process:** User triggers long CP-SAT or SA run without ability to abort. | **Medium**| **Medium** | Solver Execution | Enforce strict `time_limit_seconds <= 10.0s` for interactive runs; default SA to precomputed view. | Trigger solve with 10s budget; verify return within 10.5s. |
| **RSK-03** | **CP-SAT Deadline Exceeded:** Python model build time exceeds time limit before search starts. | **Low** | **High** | CP-SAT Solver | Use `sparse_interval` formulation (OPT-B) exclusively for interactive mode ($< 3$s build). | Run 300-flight instance; assert build time $< 3.5$s. |
| **RSK-04** | **Host Memory Exhaustion (OOM):** Loading multi-year Parquet datasets into browser memory. | **Medium**| **Critical**| Data Ingestion | Restrict interactive mode to pre-sliced daily Parquet extracts ($< 5$ MB); forbid raw 15 GB scans. | Monitor RAM usage during scenario load; assert peak $\Delta\text{RAM} < 150$ MB. |
| **RSK-05** | **Missing Checkpoint Fail-Closed:** Serialized joblib checkpoint missing on demo machine. | **Low** | **Critical**| Native ML Pipeline | Pre-flight environment check on startup validating physical checkpoint paths and SHA-256 digests. | Unit test verifying `FileNotFoundError` is caught with clean UI alert. |
| **RSK-06** | **Corrupt / Tampered Model Artifact:** Model file has mismatched cryptographic hash. | **Low** | **High** | Security / Models | `verify_and_load_checkpoint` validates SHA-256 against frozen constant before deserialization. | Tamper test: corrupt 1 byte of joblib file; assert fail-closed rejection. |
| **RSK-07** | **Stale Streamlit Cache:** `@st.cache_data` returns outdated artifacts after script updates. | **Medium**| **Medium** | Caching Layer | Include artifact file modification timestamps or hash in `@st.cache_data` key. | Modify sample JSON; verify dashboard reloads updated data. |
| **RSK-08** | **Objective Function Version Mismatch:** Comparing runs generated under different objective definitions. | **Low** | **Critical**| Evaluation / UI | Enforce `assert_compatible_objective_version` (`v1`); reject comparing mismatched objective strings. | Benchmark parity test asserting ValueError on version mismatch. |
| **RSK-09** | **Cross-Scenario Comparison Confounding:** Comparing algorithm metrics across different flight subsets. | **Medium**| **Critical**| Benchmark View | Validate matching `scenario_hash` before rendering algorithm comparison bar charts. | Attempt comparing Tier A with Tier B; assert UI warning blocks render. |
| **RSK-10** | **Capacity Policy Confusion:** Comparing finite remote stand runs with unbounded overflow apron runs. | **Medium**| **High** | Gate Topology | Group comparison metrics strictly by `capacity_policy`; prohibit pooling finite and infinite runs. | Verify UI filter groups results by `capacity_policy`. |
| **RSK-11** | **Invalid Assignment Display:** Solver produces solution that violates hard mutual exclusion. | **Low** | **Critical**| Gantt / Verifier | Every solution audited by `verify_hard_constraints_independently()`; force `feasible=False` if invalid. | Inject synthetic overlap; assert Gantt displays red warning banner. |
| **RSK-12** | **False Optimality Certification:** Heuristic solver (Greedy/SA) displayed as `OPTIMAL`. | **Low** | **Critical**| Solver Status | Domain invariant enforces `optimality_proven=False` for any heuristic solver regardless of gap. | Check Greedy output; assert badge reads `FEASIBLE` not `OPTIMAL`. |
| **RSK-13** | **Mode A vs Mode B Confounding:** Confusing passive fixed plan with active recourse in Monte Carlo. | **Medium**| **Critical**| Monte Carlo View | Distinct color schemes (Red for Mode A, Green for Mode B) and explicit mathematical descriptions. | Audit legend labels; ensure Mode A is labeled "Fixed Plan (Zero Recourse)". |
| **RSK-14** | **Unclear Prediction Provenance:** Precomputed predictions mislabeled as native dynamic inference. | **Medium**| **High** | ML View / Provenance| Display explicit `provenance_mode` badge (`NATIVE_INFERENCE` vs `PRECOMPUTED_PREDICTION`). | Verify prediction table displays `provenance_mode` column. |
| **RSK-15** | **Data Leakage in Planning View:** Actual operational delays (`ARR_DELAY`) exposed during planning. | **Low** | **Critical**| Leakage Firewall | Exclude actual columns from planning data structures; restrict actuals to "Post-Hoc Evaluation". | Check planning DataFrame columns; assert `ARR_DELAY` not present. |
| **RSK-16** | **Gantt Buffer Omission:** Gantt chart renders flight dwell without mandatory separation buffer. | **Low** | **High** | Gantt Timeline | Render occupancy bars using `occupancy_end_min` ($D_{\text{gate\_out}} + B_{\text{buffer}}$) with buffer segment. | Verify Gantt end timestamp matches $D_{\text{gate\_out}} + 15\text{m}$. |
| **RSK-17** | **Cross-Midnight Timeline Wrapping:** Flights spanning across 00:00 render with negative durations. | **Low** | **High** | Timeline Math | Domain `FlightTimeWindow` enforces end $\ge$ start using continuous timeline minutes ($t \in [0, 2880]$). | Test flight arriving 23:45 and departing 01:15; assert duration $= 90\text{m}$. |
| **RSK-18** | **Division-by-Zero in Improvement %:** Calculating cost improvement against zero baseline cost. | **Low** | **Low** | Metric Cards | Use `compute_improvement_pct()` helper safely returning 0.0 when baseline cost $\le 10^{-9}$. | Test with zero-cost baseline; assert returns `0.0%` without crash. |
| **RSK-19** | **Irreproducible Experiment Runs:** Live solver produces different assignments upon repeat click. | **Low** | **High** | Optimization Engine | Single-worker CP-SAT search (`num_search_workers=1`) with fixed `random_seed=202601`. | Solve same scenario twice; assert assignments match 100%. |
| **RSK-20** | **Browser Freezing on Solver Run:** Synchronous execution blocks browser event loop. | **Medium**| **Medium** | Streamlit UI | Wrap solve calls in `st.spinner("Solving...")`; cap interactive flight size to $N \le 200$. | Verify UI spinner appears during solve execution. |
| **RSK-21** | **Unsafe Model Deserialization:** Arbitrary pickle execution vulnerability. | **Low** | **Critical**| Checkpoint Loader | Checkpoint paths strictly validated against `ALLOWLISTED_MODEL_ROOTS` before `joblib.load()`. | Pass path outside workspace; assert `CheckpointVerificationError`. |
| **RSK-22** | **Sensitive Local Path Exposure:** Full machine file paths exposed on public defense slides. | **Low** | **Low** | UI Presentation | Format all artifact paths as relative repository paths (e.g. `artifacts/remediation/...`). | Audit UI strings; assert no `C:\Users\Heikapu` in displayed text. |
| **RSK-23** | **Unchecked Missing Dependencies:** Running app in environment without Streamlit or Plotly. | **High** | **Critical**| Environment | Add `requirements-dashboard.txt` and startup check giving clear installation command. | Test running `python -c "import streamlit, plotly"`. |
| **RSK-24** | **Conflating Reporting with Decision Cost:** Solver claiming to reduce exogenous flight delays. | **Low** | **Critical**| Metric Cards | Dashboard KPI cards must display Decision Cost ($C_{\text{decision}}$) as primary optimization metric. | Verify KPI card reads "Decision Cost Saved" not "Delay Reduced". |

---

## 3. Testing & Verification Requirements for Phase P10

Prior to finalizing Phase P10 implementation, the dashboard must pass the following QA verification suite:
1. **Smoke Test (`test_dashboard_smoke.py`):** Verify all pages load without import errors or unhandled exceptions.
2. **State Guard Test:** Verify that changing sidebar filters does not trigger a re-solve of active scenarios.
3. **Hard Constraint Assertion:** Verify that 100% of assignments rendered on the Gantt chart pass `verify_hard_constraints_independently()`.
4. **Data Isolation Test:** Verify that no sealed 2024 holdout data is accessed by interactive demo pages.
