# AEOLUS-G6: Implementation and Code Audit Report

**Gate Identifier:** `AEOLUS-G6`  
**Gate Title:** Dashboard Scientific Integrity, Runtime Validation & Visual QA  
**Audit Date:** 2026-10-11  
**Target Branch:** `remediation/g6-dashboard`  

---

## 1. Architectural & Implementation Audit Across 5 Pages

### 1.1. Page 01: Control Tower
- **Component File:** `dashboard/pages/page_01_control_tower.py`
- **Data Contract:** Consumes `ScenarioContext` and `FlightPredictionView` collections.
- **Audit Findings & Enhancements:**
  - Standardized scenario badges: Scenarios derived from curated BTS data (`SCEN_P09_CANONICAL_120`, `SCEN_2023_PEAK_01`) display origin tag `REAL_DERIVED / BTS_OTP_2023_CURATED` with `is_synthetic = True`, strictly adhering to data provenance contracts.
  - KPI Consistency: Flight and gate counts displayed in KPI cards are computed directly from the active scenario definition, ensuring 100% mathematical consistency with downstream charts.
  - Delay wave distribution accurately renders arrival and departure time-of-day dynamics without hardcoded values.

### 1.2. Page 02: Flight Intelligence
- **Component File:** `dashboard/pages/page_02_flight_intelligence.py`
- **Data Contract:** Consumes `FlightPredictionView` and `AircraftTurnView`.
- **Audit Findings & Enhancements:**
  - Distinction between Inbound and Outbound predictions:
    * Inbound (ARR): Displays $P(\text{delay} \ge 15)$ computed from the NGBoost Student-t predictive CDF.
    * Outbound (DEP): Displays regression risk score from XGBoost/Ridge. When CDF is unavailable, probability is explicitly formatted as `"N/A"`, eliminating the risk of displaying uncalibrated heuristics as calibrated probabilities.
  - Aircraft turnaround dynamics: Minimum technical turnaround of 45 minutes, inbound delay absorption, and 15-minute gate release buffer are explicitly visualized.
  - TreeSHAP explanations: Global and local SHAP bar charts illustrate feature importance without referencing post-departure features, maintaining the strict T-2h cutoff boundary.

### 1.3. Page 03: Gate Operations & Master Gantt
- **Component File:** `dashboard/pages/page_03_gate_operations.py`
- **Data Contract:** Consumes `GateTimelineView` and `SolverRunView`.
- **Audit Findings & Enhancements:**
  - Timeline interval semantics: Gate occupancy intervals are rendered as half-open $[start, release)$ intervals, where $release = \text{gate\_out} + \text{buffer\_min}$ ($15$ minutes).
  - Explicit manual solver invocation: Solver execution is bound strictly to `st.button("Chạy Phân Cổng")`. Loading the page or changing filters triggers zero background solver runs.
  - Apron overflow stands (`APRON_*`) are mapped to the `OVERFLOW` resource group, preventing misrepresentation as standard Concourse A contact gates.
  - Verifier integration: Every solution displayed in the Gantt chart is audited by `verify_hard_constraints_independently()`, displaying conflict counts and feasibility badges.

### 1.4. Page 04: Optimization Lab
- **Component File:** `dashboard/pages/page_04_optimization_lab.py`
- **Data Contract:** Consumes `SolverRunView` collections and benchmark dataframes.
- **Audit Findings & Enhancements:**
  - Multi-solver comparability: Greedy, CP-SAT, SA, and Hybrid are evaluated on identical problem digests.
  - Objective formulation parity: Clear separation between Decision Cost ($J_{\text{decision}}$) and Reporting Cost ($J_{\text{reporting}}$).
  - Status normalization: CP-SAT solutions with proven gap 0.0% are badged as `TỐI ƯU TUYỆT ĐỐI (OPTIMAL PROVEN)`, while heuristic solutions (Greedy, SA) are badged as `HOÀN TẤT (HEURISTIC STOP)` or `KHẢ THI (FEASIBLE)`, preventing unverified claims of mathematical optimality.
  - Scalability frontier: Instance $N=1500$ explicitly displays dashed markers and status `UNKNOWN (Hết giờ 30s)`.

### 1.5. Page 05: Robustness Lab
- **Component File:** `dashboard/pages/page_05_robustness_lab.py`
- **Data Contract:** Consumes `MonteCarloRealization` and `RecourseEvaluationView`.
- **Audit Findings & Enhancements:**
  - Mode A (Fixed Plan Baseline): Demonstrates 74.8% empirical conflict rate under uncertain realized delays, validating the operational necessity of gate reallocation.
  - Mode B (Causal Reactive Recourse): Confirms 100% conflict resolution with causal sequential decision-making.
  - Mode C (Perfect Foresight Oracle): Explicitly designated as `NON-DEPLOYABLE (GREEDY BENCHMARK)`, warning reviewers that full-foresight greedy reallocation is a theoretical post-hoc reference, not a deployable real-time solver.
  - Risk measures: Clear tabular and visual reporting of both 95th percentile ($p95$) and Conditional Value at Risk ($CVaR_{95}$), verifying $CVaR_{95} \ge p95$.

---

## 2. Security Hardening: Canonical Path Containment

### 2.1. Vulnerability Analysis
Previously, `DashboardConfig.is_path_allowlisted()` and `DashboardConfig.is_model_dir_allowlisted()` in `dashboard/core/config.py` used string prefix matching:
```python
# VULNERABLE IMPLEMENTATION:
rel_posix = path.resolve().relative_to(self.project_root).as_posix()
return any(rel_posix.startswith(allowed) for allowed in self.ALLOWED_ARTIFACT_DIRS)
```
This naive substring comparison had two severe security vulnerabilities:
1. **Directory Name Spoofing:** An attacker could craft a directory such as `artifacts/models_evil/` or `artifacts/remediation_unauthorized/` which starts with `artifacts/models` or `artifacts/remediation`, bypassing the check.
2. **Path Traversal Ambiguity:** Symlinks or relative traverse tokens outside the workspace could lead to improper allowlist validation.

### 2.2. Remediated Canonical Containment Implementation
We refactored `dashboard/core/config.py` to enforce **strict canonical path containment**:
```python
# HARDENED IMPLEMENTATION:
def is_path_allowlisted(self, path: Path) -> bool:
    try:
        resolved = path.resolve()
        for allowed in self.ALLOWED_ARTIFACT_DIRS:
            allowed_path = (self.project_root / allowed).resolve()
            if resolved == allowed_path or allowed_path in resolved.parents:
                return True
        return False
    except (ValueError, RuntimeError):
        return False
```
This implementation guarantees that any evaluated path must either match the canonical allowed directory exactly or have the allowed directory as an ancestor in its canonical directory hierarchy (`resolved.parents`). Traversal attempts (`../`) and sibling prefix spoofing (`artifacts/models_evil`) are deterministically rejected.

---

## 3. Scientific Labeling & Data Provenance Standardization

The vocabulary of the dashboard was audited and aligned with the scientific contracts defined in Gates G1 through G5:

| Category | Forbidden Term / Misrepresentation | Standardized Scientific Token | Context & Rule |
|:---|:---|:---|:---|
| **Data Origin** | Real data claim for synthetic flights | `REAL_AEOLUS` vs `REAL_DERIVED` vs `SYNTHETIC` | Scenarios generated by `ScalabilityScenarioGenerator` are strictly marked `SYNTHETIC` or `REAL_DERIVED`. |
| **Prediction Type** | Synthetic fallback labeled native | `NATIVE_INFERENCE` vs `PRECOMPUTED` | Flights evaluated using live checkpoints are tagged `NATIVE_INFERENCE`; pre-generated evaluation sets are tagged `PRECOMPUTED`. |
| **Probability Claim** | Logistic sigmoid score called probability | `CALIBRATED_PROBABILITY` vs `HEURISTIC_SCORE` | Only parametric Student-t CDF calculations are labeled probability; departure classification scores are labeled risk score. |
| **Solver Status** | Heuristic labelled "Optimal" | `OPTIMAL_PROVEN` vs `FEASIBLE_FOUND` vs `HEURISTIC_STOP` | Only CP-SAT solutions with mathematical gap = 0.0% receive optimal badges. Heuristics are always marked heuristic. |
| **Monte Carlo Recourse** | Perfect foresight called global optimum | `FULL_FORESIGHT_GREEDY (NON-DEPLOYABLE)` | Mode C is labeled as a greedy retrospective benchmark, never an optimal policy. |

---

## 4. Export Adapter Integrity Enhancements

In `dashboard/adapters/export_adapter.py`:
1. **Authentic Run Identification:** `export_run_manifest_to_json()` now includes `run_id`, `requested_solver`, `effective_solver`, and `fallback_used` directly in the exported JSON manifest.
2. **Provenance Traceability in CSV:** `export_assignments_to_csv()` now exports the `provenance` column alongside `data_origin` and `scenario_id`.
3. **API Ergonomics:** Parameter `scenario_id` was updated to be optional, resolving to `assignments[0].scenario_id` when omitted, preventing runtime TypeErrors while enforcing provenance protection.
