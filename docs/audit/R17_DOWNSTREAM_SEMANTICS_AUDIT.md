# R17: DOWNSTREAM PIPELINE SEMANTICS & DATAFLOW AUDIT

**Task ID**: `R17_DOWNSTREAM_SEMANTICS_AUDIT`  
**Date**: `2026-10-02`  
**Status**: `PASS`  
**Authoritative Decision**: `SCALAR_FORECAST_IMPACT` (Option A)

---

## 1. SCOPE OF AUDIT

Audited the end-to-end code path from Core Arrival forecasts through turn synthesis to gate assignment solvers:
$$\text{Core Arrival Prediction} \longrightarrow \text{Forecast Adapter} \longrightarrow \text{Synthetic Turn} \longrightarrow \text{Flight Domain} \longrightarrow \text{Solvers (Greedy / CP-SAT / SA)} \longrightarrow \text{Evaluation}$$

Audited across all 7 downstream candidates:
1. `schedule_only` (Operational Baseline)
2. `arrival_linear_baseline_v1` (Point Model Champion - Tied)
3. `arrival_xgboost_baseline_v1` (Point Model Comparator)
4. `arrival_weighted_ensemble_v1` (Point Ensemble Champion - Tied)
5. `P5_quantile_regression` (Probabilistic Forecast Champion)
6. `P4_ngboost_student_t` (Downstream-Eligible Candidate)
7. `oracle_actual` (Non-Deployable Ground-Truth Reference Arm)

---

## 2. EVIDENCE AND CODE CITATIONS

| Component | Code Location | Observed Implementation Reality | Uncertainty Status |
| :--- | :--- | :--- | :--- |
| **Point Models** | `run_downstream_model_comparison.py:257-270` | Passes scalar point prediction `pred_delay = reg.predict(X)` | Discarded / None |
| **P5 Quantile** | `run_downstream_model_comparison.py:272-274` | Passes scalar median `dist_p5.median()` ($q_{50}$). Quantiles $q_{10}, q_{25}, q_{75}, q_{90}$, intervals, and pinball risks are discarded. | Discarded |
| **P4 Student-T** | `run_downstream_model_comparison.py:275-277` | Passes scalar expectation `dist_p4.mean()` ($\mu$). Scale $\sigma$, degrees of freedom $\nu$, density, and sampling are discarded during planning. | Discarded |
| **Schedule-Only** | `run_downstream_model_comparison.py:254-255` | Passes constant $0.0$ delay array (`np.zeros`). | None |
| **Oracle Actual** | `run_downstream_model_comparison.py:279-280` | Passes realized actual delay `row["ARR_DELAY"]`. Reference bound only. | None |
| **Turn Synthesizer** | `src/simulation/aircraft_turn.py:149-175` | Accepts `sampled_delay_min: float`. Computes deterministic scalar clock minutes: $A_{\text{sim}} = \text{round}(A_{\text{sched}} + \text{delay})$. | Strictly Scalar |
| **Flight Domain** | `src/optimization/domain.py:102-180` | `Flight` stores integer timestamps (`scheduled_arrival_min`, `predicted_arrival_min`, `simulated_departure_min`, `gate_release_min`). Contains zero distributional or variance attributes. | Strictly Scalar |
| **Solvers** | `src/optimization/solvers/cp_sat_solver.py:116-155` | Solves deterministic interval scheduling: mutual exclusion added only if intervals overlap: $\max(s_i, s_j) < \min(e_i, e_j)$. Zero chance-constraints or scenario trees. | Strictly Scalar |
| **Monte Carlo** | `src/evaluation/monte_carlo_comparison_v2.py:200-240` | Evaluates independent scalar realizations per flight, passed as deterministic intervals to Greedy solver. Not stochastic programming. | Strictly Scalar Realizations |

---

## 3. SEMANTIC DECISION

### Selected: `OPTION A — SCALAR_FORECAST_IMPACT`

**Rationale**:
Code inspection establishes that downstream solvers and intermediate turn representations do not consume, propagate, or optimize probability distributions, variances, quantiles, or tail risks. P5 operates strictly via its median scalar $q_{50}$; P4 operates strictly via its expected value $\mu$. The downstream benchmark measures how differing scalar delay forecasts affect deterministic gate scheduling.

Labeling this pipeline as "uncertainty-aware optimization", "distributional gate allocation", or "chance-constrained optimization" is scientifically ungrounded. Locking semantics to `SCALAR_FORECAST_IMPACT` preserves scientific integrity without requiring unverified architecture redesigns.

### Mandatory Terminology
- **Required**: *"Forecast-derived scalar operational impact benchmark"*
- **Required**: *"Downstream synthetic gate assignment comparison"*
- **Forbidden**: *"Uncertainty-aware gate optimization"*
- **Forbidden**: *"Stochastic / distributional gate allocation"*
- **Forbidden**: *"Real-world gate assignment or airport delay reduction at ATL"*

---

## 4. BLOCKERS & GATING

- **Blockers for R17**: None. Dataflow is 100% verified and candidate labels are fully reconciled.
- **R17 Status**: `PASS`
- **Next Gate**: `R18` is authorized to proceed.

---

## 5. ARTIFACT SHA256 DIGESTS

| File Path | SHA256 Checksum |
| :--- | :--- |
| `artifacts/r17_downstream_dataflow_audit.json` | `15442bf070171ff69f00ed523e17b4d054587ca7b27d4bcdc8eb0b60dda7e96a` |
| `artifacts/r17_downstream_semantics_decision.json` | `e998cb3775d59d1841d18d3fdc1ba8e4866360545d57ab204b8e8424d38d7dfb` |
| `tests/test_r17_downstream_semantics.py` | `eb1c5b11826dd5b7f0cfa9860dfcafde6b979fa6d026bfad677d08207cb9206b` |
