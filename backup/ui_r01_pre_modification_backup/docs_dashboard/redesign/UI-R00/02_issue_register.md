# UI-R00: 02 — MASTER ISSUE REGISTER & ANOMALY INVENTORY

**Document ID:** `AEOLUS-UI-R00-02-ISSUE-REGISTER`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:26:00+07:00  
**Auditor:** Principal Software Auditor & Senior System QA Lead  
**Audit Scope:** 5 Pages, Core Services, View Adapters, UI Components, and Plotly Visualizers

---

## 1. Issue Severity Classification System

- **P0 (Critical Scientific / Execution / Leakage Defect):** Erroneous mathematical calculations, false solver optimality/verification claims, data leakage, unsolicited automated heavy computations, or severe provenance degradation.
- **P1 (Operational & Functional Integrity Defect):** Broken filters, misleading state tracking, erroneous domain entity categorization, missing drill-downs, or brittle session state.
- **P2 (Design System, Typography & Cognitive Load):** Unreadable font sizes (< 13px), unbalanced grid layouts, text-heavy scientific walls, or styling regressions.
- **P3 (Cosmetic & Polish):** Minor spacing alignment, phrasing enhancements, icon consistency.

---

## 2. Master Issue Catalog

---

### ISSUE-R00-01: Gate Operations Unsolicited Automatic Solver Execution on Page Render
- **Severity:** **P0**
- **File and Symbol:** [`dashboard/pages/page_03_gate_operations.py#L101-L113`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_03_gate_operations.py#L101-L113) (`render_page`)
- **Current Behavior:** Every time a user opens Page 03 or changes the scenario in the sidebar, `OptimizationService().solve(..., solver_name="cpsat")` is triggered synchronously during page render without explicit user consent.
- **Evidence:**
  ```python
  active_run = st.session_state.get(SessionStateKeys.ACTIVE_RESULT)
  if active_run is None or active_run.scenario_id != active_scenario_id:
      initial_run, _, _ = opt_service.solve(
          flights=flights, gates=gates, solver_name="cpsat", scenario_id=active_scenario_id
      )
  ```
- **Expected Behavior:** Page load must be instantaneous and idempotent. It should display either a cached precomputed canonical solution or the initial nominal schedule, with a prominent "RUN SOLVER" button for on-demand execution.
- **Reproduction Method:** Launch dashboard, navigate to "Gate Operations". Observe console log showing OR-Tools solver execution and 850ms latency spike on initial view.
- **Affected Page:** Page 03 (Gate Operations)
- **Scientific Impact:** Violates the principle of user-controlled experiment execution. Creates compute spikes and risks unexpected solver timeout on larger scenarios.
- **UX Impact:** Incurred UI freeze (up to several seconds) upon clicking the navigation tab.
- **Suggested Remediation Phase:** **UI-R02** (State & Execution Lifecycle)
- **Dependency:** None
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-02: Page 02 Flight Intelligence Table Displays Silent Fallback Defaults (Zero Real Metadata)
- **Severity:** **P0**
- **File and Symbol:** [`dashboard/adapters/prediction_adapter.py#L21-L30`](file:///D:/Study/Code/Python/Aelous/dashboard/adapters/prediction_adapter.py#L21-L30) (`adapt_prediction_row_to_view`) & [`dashboard/pages/page_02_flight_intelligence.py#L54-L72`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_02_flight_intelligence.py#L54-L72)
- **Current Behavior:** `predictions_sample.csv` only contains `flight_id` and numeric prediction columns (`predicted_delay_min`, etc.). Because it lacks `carrier`, `origin`, `destination`, and `sched_arr_time_min`, the adapter silently fills all 60 rows with `carrier="DL"`, `origin="ORD"`, `destination="ATL"`, and `sched_arr_time_min=480` (08:00).
- **Evidence:** Running a distinct value check across all 60 rows produces:
  - `Unique carriers: {'DL'}`
  - `Unique origins: {'ORD'}`
  - `Unique landing times: {480}` (08:00 AM)
- **Expected Behavior:** The prediction records must be joined against the active scenario flight manifest so that actual carriers (e.g., UA, AA, DL), actual origins, and authentic schedule times are presented.
- **Reproduction Method:** Navigate to Page 02 (Tab A). Observe the table: every single flight has carrier "DL", route "ORD➔ATL", and scheduled arrival "08:00".
- **Affected Page:** Page 02 (Flight Intelligence)
- **Scientific Impact:** Gives false impression of synthetic or monolithic dummy test data during thesis defense.
- **UX Impact:** Highly unrealistic table display; filtering by carrier or route is non-functional.
- **Suggested Remediation Phase:** **UI-R01** (Data Integrity & Provenance)
- **Dependency:** Scenario flight manifest joins
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-03: Robustness Lab Visualizers Conflate 1,500 Multi-Solver Evaluations Without Filtering
- **Severity:** **P0**
- **File and Symbol:** [`dashboard/pages/page_05_robustness_lab.py#L213-L238`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_05_robustness_lab.py#L213-L238) & [`dashboard/visualizers/robustness_charts.py#L51-L85`](file:///D:/Study/Code/Python/Aelous/dashboard/visualizers/robustness_charts.py#L51-L85)
- **Current Behavior:** `fixed_plan_results.csv` and `recourse_results.csv` contain 1,500 records (500 Greedy, 500 CPSat, 500 Hybrid). While `compute_paired_differences` correctly filters `solver_name == 'CPSat'`, `create_mc_cost_distribution_figure` (CHART-12), `create_mc_ecdf_figure` (CHART-13), `create_mc_boxplot_figure` (CHART-14), and `create_mc_convergence_figure` (CHART-15) receive the raw 1,500-row DataFrame.
- **Evidence:**
  - `recourse_df.shape` is `(1500, 14)`.
  - In `create_mc_convergence_figure`, `n_total = len(costs) = 1500`. The running mean aggregates 1,500 runs from 3 separate algorithms, while the label explicitly claims "500 Kịch bản".
- **Expected Behavior:** Visualizers must either be filtered to the authoritative CP-SAT solver (or user-selected solver), or provide an explicit solver toggle.
- **Reproduction Method:** Inspect CHART-12 and CHART-15 on Page 05. The sample size plotted on X-axis reaches 1,500 instead of 500.
- **Affected Page:** Page 05 (Robustness Lab)
- **Scientific Impact:** Severe statistical distortion: combines outputs from different solver paradigms into single empirical distributions and convergence traces.
- **UX Impact:** Confusion when text says "500 scenarios" but charts show 1,500 observations.
- **Suggested Remediation Phase:** **UI-R07** (Robustness Lab) & **UI-R01**
- **Dependency:** Solver filtering contract
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-04: Hardcoded KPIs on Control Tower (Page 01) and Optimization Lab (Page 04)
- **Severity:** **P0**
- **File and Symbol:** 
  - [`dashboard/pages/page_01_control_tower.py#L82`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L82), [`#L93`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L93), [`#L104`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L104), [`#L139-L141`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L139-L141)
  - [`dashboard/pages/page_04_optimization_lab.py#L140-L170`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_04_optimization_lab.py#L140-L170)
- **Current Behavior:**
  - Page 01 KPI cards hardcode `"13 Cặp xung đột"`, `"0 Xung đột"`, `"0 Cổng"`, and slack breakdown `"42 cặp (70.0%)"`, `"14 cặp (23.3%)"`, `"4 cặp (6.7%)"` in static HTML strings regardless of the active scenario.
  - Page 04 solver cards hardcode `"130.00 pts"`, `"Runtime: 1.8 ms"`, `"Runtime: 65.2 ms"`, `"Runtime: 182.4 ms"`, `"Runtime: 68.5 ms"` as literal strings, ignoring the computed averages in `summary_rows` above it.
- **Evidence:**
  ```python
  # page_04_optimization_lab.py
  with c1: render_kpi_card(title="DETERMINISTIC GREEDY", value="130.00 pts", subtitle="Runtime: 1.8 ms | Heuristic", ...)
  with c2: render_kpi_card(title="CP-SAT (SPARSE INTERVAL)", value="130.00 pts", subtitle="Runtime: 65.2 ms | Gap: 0.0%", ...)
  ```
- **Expected Behavior:** All KPI scorecards must dynamically pull values from active scenario analytics and calculated benchmark summary metrics.
- **Reproduction Method:** Switch scenario to `SCEN_2023_PEAK_01` (85 flights). Page 01 still reports "13 Cặp xung đột" and "42 cặp an toàn".
- **Affected Page:** Page 01 (Control Tower) and Page 04 (Optimization Lab)
- **Scientific Impact:** Disconnect between scenario context and reported metrics destroys credibility during defense.
- **UX Impact:** Misleading information displayed when interacting with filters or scenario switcher.
- **Suggested Remediation Phase:** **UI-R04** (Pages 01/02) & **UI-R06** (Optimization Lab)
- **Dependency:** Precomputed analytics models
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-05: False Premature Solver Optimality Status Displayed Across Context Bar
- **Severity:** **P0**
- **File and Symbol:** [`dashboard/components/context_bar.py#L15-L16`](file:///D:/Study/Code/Python/Aelous/dashboard/components/context_bar.py#L15-L16), [`dashboard/pages/page_01_control_tower.py#L37-L41`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L37-L41), [`dashboard/pages/page_02_flight_intelligence.py#L44-L48`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_02_flight_intelligence.py#L44-L48)
- **Current Behavior:** `render_context_bar` defaults to `solver_status_text="TỐI ƯU TUYỆT ĐỐI (CP-SAT)"` and `is_optimal=True`. Pages 01 and 02 explicitly pass these values, claiming CP-SAT optimality before any solver execution has occurred, and even on the ML-only page.
- **Evidence:**
  ```python
  # page_01_control_tower.py:37
  render_context_bar(context=scenario_context, solver_status_text="TỐI ƯU TUYỆT ĐỐI (CP-SAT)", is_optimal=True)
  # page_02_flight_intelligence.py:44
  render_context_bar(context=scenario_context, solver_status_text="TỐI ƯU TUYỆT ĐỐI (CP-SAT)", is_optimal=True)
  ```
- **Expected Behavior:** Context bar must accurately reflect the state of the active page:
  - Page 01: "CANONICAL BASELINE" or "CHƯA TỐI ƯU (DANH ĐỊNH)"
  - Page 02: "DỰ BÁO HỌC MÁY (ML INFERENCE)"
  - Page 03: Actual solver status badge from the active run.
- **Reproduction Method:** Open Page 01 or Page 02; look at top-right context bar: "TRẠNG THÁI BỘ GIẢI: 🛡️ TỐI ƯU TUYỆT ĐỐI (CP-SAT)".
- **Affected Page:** Global (All Pages)
- **Scientific Impact:** False optimality claim violates scientific integrity protocols (P10-00 Finding D5).
- **UX Impact:** Inaccurate status badge confuses users and reviewers.
- **Suggested Remediation Phase:** **UI-R02** (State & Execution)
- **Dependency:** `status_mapping.py`
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-06: Symbolic Hardcoded Scenario Hash Does Not Reflect Actual Data
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/services/scenario_service.py#L87-L90`](file:///D:/Study/Code/Python/Aelous/dashboard/services/scenario_service.py#L87-L90) (`compute_scenario_hash`)
- **Current Behavior:** `compute_scenario_hash` computes SHA-256 over a hardcoded string `f"{scenario_id}::ATL::BTS_2023::SEED_42"`. For `SCEN_2023_PEAK_01` (seed 202602), the hash still uses `SEED_42`. No flight schedules, gates, or data arrays are hashed.
- **Evidence:**
  ```python
  def compute_scenario_hash(self, scenario_id: str) -> str:
      raw_token = f"{scenario_id}::ATL::BTS_2023::SEED_42"
      return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
  ```
- **Expected Behavior:** Scenario hash must be a deterministic digest derived from the actual flights (IDs, arrival/departure minutes, gate requirements) and gate inventory.
- **Reproduction Method:** Inspect `scenario_hash` across scenarios. It only hashes the ID and hardcoded text.
- **Affected Page:** Global (Displayed in Context Bar and Research Inspector)
- **Scientific Impact:** Degrades data provenance; does not guarantee immutability of the actual flight schedule dataset.
- **UX Impact:** Minor directly, but visible in Research Mode audit tabs.
- **Suggested Remediation Phase:** **UI-R01** (Data Integrity & Provenance)
- **Dependency:** `ScenarioService`
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-07: Gantt Concourse Filter Erroneously Matches `APRON_*` Stands to Concourse A
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/visualizers/gantt_chart.py#L104-L113`](file:///D:/Study/Code/Python/Aelous/dashboard/visualizers/gantt_chart.py#L104-L113) & [`dashboard/adapters/assignment_adapter.py#L73-L75`](file:///D:/Study/Code/Python/Aelous/dashboard/adapters/assignment_adapter.py#L73-L75)
- **Current Behavior:** In the concourse determination chain:
  ```python
  if clean.startswith("REMOTE"): c = "REMOTE"
  elif clean.startswith("T"): c = "T"
  elif clean.startswith("A"): c = "A"
  ```
  If an overflow gate is named `APRON_01` or `APRON_OVERFLOW`, `clean.startswith("A")` evaluates to `True`, categorizing remote apron stands as Concourse A.
- **Evidence:** Code trace confirms `APRON` has no dedicated check before `"A"`.
- **Expected Behavior:** Remote stands and aprons must be recognized via `is_remote`, `resource_type`, or checking `APRON` before `A`.
- **Reproduction Method:** Add an apron stand `APRON_01` and filter for Concourse A; `APRON_01` is incorrectly included under Concourse A.
- **Affected Page:** Page 03 (Gate Operations - Gantt)
- **Scientific Impact:** Conflates remote apron capacity with terminal concourse gate capacity.
- **UX Impact:** Misplaced gate rows on the Gantt Y-axis and faulty Concourse A filter counts.
- **Suggested Remediation Phase:** **UI-R05** (Gantt Visualizer)
- **Dependency:** Gate classification rules
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-08: Stale-Result Detection Ignores Scenario Switch and Missing Parameter Keys
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/services/experiment_service.py#L52-L66`](file:///D:/Study/Code/Python/Aelous/dashboard/services/experiment_service.py#L52-L66) (`is_stale`)
- **Current Behavior:** `SOLVER_IDENTITY_KEYS` does not include `scenario_id`. If `scenario_id` changes, `is_stale` compares only solver weights and returns `False` if weights match, failing to warn the user that the solution belongs to a different scenario.
- **Evidence:** `SOLVER_IDENTITY_KEYS = ["solver_name", "w_pref", "w_remote", "w_conflict", "buffer_time_min", "allow_overflow", "finite_remote_capacity", "cp_sat_formulation"]`.
- **Expected Behavior:** Any mismatch in `scenario_id` must flag the solution as stale or force re-initialization.
- **Reproduction Method:** Switch scenario in sidebar while maintaining default sliders; note that `is_stale` does not trigger based on scenario change.
- **Affected Page:** Page 03 (Gate Operations)
- **Scientific Impact:** Potential presentation of gate assignments generated for 120 flights onto an 85-flight scenario context.
- **UX Impact:** Missing staleness warning when switching scenarios.
- **Suggested Remediation Phase:** **UI-R02** (State & Execution)
- **Dependency:** None
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-09: Hardcoded Representative Turns in Flight Intelligence Tab B
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/pages/page_02_flight_intelligence.py#L184-L236`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_02_flight_intelligence.py#L184-L236)
- **Current Behavior:** Tab B instantiates 3 hardcoded `AircraftTurnView` records (`TURN_DL1024_DL1502`, `TURN_DL0466_DL0764`, `TURN_NK0040_NK0041`) statically in Python code. It does not load or synthesize turns from the active scenario.
- **Evidence:** Lines 184–236 in `page_02_flight_intelligence.py` construct explicit Python dataclass instances with hardcoded minute values.
- **Expected Behavior:** Aircraft turn dynamics should be populated from actual aircraft rotations synthesized by `AircraftTurnSynthesis` or loaded from scenario turn pairs.
- **Reproduction Method:** Inspect Tab B. The dropdown only ever offers the same 3 hardcoded flight pairs regardless of scenario selection.
- **Affected Page:** Page 02 (Flight Intelligence)
- **Scientific Impact:** Disconnects turn dynamics analysis from the empirical dataset and simulation engine.
- **UX Impact:** Inability to inspect turns for arbitrary flights in the scenario.
- **Suggested Remediation Phase:** **UI-R04** (Pages 01/02)
- **Dependency:** Turn adapter
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-10: Inconsistent Session State Keys and Navigation Button Routing
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/pages/page_01_control_tower.py#L165-L169`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_01_control_tower.py#L165-L169), [`dashboard/app.py#L86-L98`](file:///D:/Study/Code/Python/Aelous/dashboard/app.py#L86-L98), [`dashboard/core/state.py#L15-L18`](file:///D:/Study/Code/Python/Aelous/dashboard/core/state.py#L15-L18)
- **Current Behavior:** Quick action buttons on Page 01 set `st.session_state[CURRENT_PAGE] = "Flight Intelligence"` instead of `"02_flight_intelligence"`. This required ad-hoc substring normalization in `app.py`. Furthermore, `state.py` defines redundant aliases (`IS_RESEARCH_MODE` vs `RESEARCH_MODE`, `ACTIVE_SCENARIO_ID` vs `SELECTED_SCENARIO_ID`).
- **Evidence:** `app.py` lines 86–98 contains custom fuzzy string matching (`if "Control" in current_page_key...`).
- **Expected Behavior:** All components and buttons must strictly reference canonical enum values without string parsing hacks.
- **Reproduction Method:** Review navigation code and button callbacks in `page_01_control_tower.py`.
- **Affected Page:** Global
- **Scientific Impact:** None directly, but represents technical debt and risk of state desynchronization.
- **UX Impact:** Fragile routing prone to breakage when page titles change.
- **Suggested Remediation Phase:** **UI-R02** (State & Execution)
- **Dependency:** None
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-11: Hardcoded Gate Counts in Concourse Filter UI Labels
- **Severity:** **P1**
- **File and Symbol:** [`dashboard/pages/page_03_gate_operations.py#L148-L150`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_03_gate_operations.py#L148-L150)
- **Current Behavior:** Concourse checkboxes hardcode: `st.checkbox("Concourse T (10)")`, `st.checkbox("Concourse A (15)")`, `st.checkbox("Bãi đỗ từ xa (1)")`. In scenario `SCEN_2023_PEAK_01` (15 contact gates total), Concourse A only has 5 gates, but the label still reads `(15)`.
- **Evidence:**
  ```python
  concourse_t = st.checkbox("Concourse T (10)", value=True)
  concourse_a = st.checkbox("Concourse A (15)", value=True)
  concourse_rem = st.checkbox("Bãi đỗ từ xa (1)", value=True)
  ```
- **Expected Behavior:** Concourse gate counts should be dynamically computed from `len([g for g in gates if ...])`.
- **Reproduction Method:** Switch to scenario `SCEN_2023_PEAK_01`; check concourse filter checkboxes.
- **Affected Page:** Page 03 (Gate Operations)
- **Scientific Impact:** Discrepancy between actual gate count and displayed filter count.
- **UX Impact:** User confusion regarding available resources.
- **Suggested Remediation Phase:** **UI-R05** (Gantt Visualizer)
- **Dependency:** Scenario gate inventory
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-12: Streamlit 1.65.0 Deprecation Warning on `use_container_width`
- **Severity:** **P2**
- **File and Symbol:** Multiple occurrences across `dashboard/pages/` and `dashboard/components/`
- **Current Behavior:** Streamlit 1.65.0 emits multiple warnings on runtime: `Please replace use_container_width with width. use_container_width will be removed after 2025-12-31. For use_container_width=True, use width='stretch'`.
- **Evidence:** Runtime console output logs 15+ warnings during page rendering.
- **Expected Behavior:** UI code should be updated or safely wrapped to eliminate console deprecation warnings.
- **Reproduction Method:** Run `streamlit run dashboard/app.py` or `AppTest`. Check terminal stderr.
- **Affected Page:** Global
- **Scientific Impact:** None.
- **UX Impact:** Pollutes terminal logs during defense rehearsals.
- **Suggested Remediation Phase:** **UI-R03** (Design System)
- **Dependency:** None
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-13: Excessive Information Density & Small Typography (11px)
- **Severity:** **P2**
- **File and Symbol:** [`dashboard/components/styles.py`](file:///D:/Study/Code/Python/Aelous/dashboard/components/styles.py) & [`dashboard/pages/page_03_gate_operations.py#L185`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_03_gate_operations.py#L185)
- **Current Behavior:** KPI titles, badges, and metadata text use `11px` and `12px` font sizes. In Page 03, the right sidebar takes only 3.5 out of 12 columns (~29%), cramming 5 sliders, checkboxes, buttons, and statistics into an uncomfortably narrow rail.
- **Evidence:**
  ```css
  .aeolus-kpi-title { font-size: 11px; }
  .aeolus-badge { font-size: 11px; }
  ```
- **Expected Behavior:** Standardize on minimum 13px–14px body typography for legibility during projected slide presentations, and rebalance grid columns (e.g., 9 / 3 or collapsible controls).
- **Reproduction Method:** Project dashboard on standard lecture display; 11px text is difficult to read from distance.
- **Affected Page:** Global, especially Page 03
- **Scientific Impact:** None.
- **UX Impact:** Significant eye strain and reduced readability for defense evaluation committee.
- **Suggested Remediation Phase:** **UI-R03** (Design System)
- **Dependency:** CSS Design System tokens
- **Status:** **VERIFIED (CONFIRMED)**

---

### ISSUE-R00-14: Verbose Scientific Text Walls in Robustness Lab & Research Inspector
- **Severity:** **P2**
- **File and Symbol:** [`dashboard/pages/page_05_robustness_lab.py#L305-L323`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_05_robustness_lab.py#L305-L323) & [`dashboard/components/research_inspector.py`](file:///D:/Study/Code/Python/Aelous/dashboard/components/research_inspector.py)
- **Current Behavior:** Lengthy multi-paragraph explanations of Findings D1–D4 and Protocol V4 are presented as monolithic blocks of dense text without progressive disclosure, structured summaries, or visual bullet hierarchy.
- **Evidence:** Section 6 in Page 05 contains over 250 words of dense academic prose in an expanded container.
- **Expected Behavior:** Refactor into concise executive callout cards with expandable deep-dive accordions, maintaining scientific rigor while avoiding cognitive overload.
- **Reproduction Method:** Open Page 05; scroll down to Section 6.
- **Affected Page:** Page 05 (Robustness Lab)
- **Scientific Impact:** None (content is accurate, but poorly digestible).
- **UX Impact:** Overwhelming presentation interface that obstructs chart analysis.
- **Suggested Remediation Phase:** **UI-R03** & **UI-R07**
- **Dependency:** None
- **Status:** **VERIFIED (CONFIRMED)**

---

## 3. Summary of Issues by Severity

| Severity Level | Count | Primary Focus Area |
| :---: | :---: | :--- |
| **P0** | **5** | Automatic CP-SAT solving, dummy flight metadata, 1,500 MC conflation, hardcoded KPIs, false optimality status |
| **P1** | **6** | Dummy scenario hash, concourse filter bug, stale detection, hardcoded turns, state routing, filter counts |
| **P2** | **3** | Streamlit deprecations, 11px typography, cramped 3.5-col layout, verbose text walls |
| **P3** | **0** | Deferred to UI-R08 final polish |
| **Total** | **14** | All verified directly on repository source code |
