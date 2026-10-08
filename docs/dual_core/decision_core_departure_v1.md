# ADR: Core Departure Contract, Registry Specification & Leakage Guard V1

- **Document ID**: `ADR-DUAL-CORE-001`
- **Protocol**: Aeolus Dual Core Architecture Protocol V2
- **Author**: Senior ML Platform Engineer
- **Date**: 2026-10-08
- **Status**: APPROVED / SEALED
- **Supersedes**: Single-core arrival-only paradigm for downstream gate optimization

---

## 1. Context and Problem Statement

Aeolus Gate Optimization historically operated on a single-core ML model architecture:
1. **Core Arrival (`ModelTask.CORE_ARRIVAL`)**: Trained on inbound flights with `DEST = "ATL"`, predicting signed `ARR_DELAY` minutes at `CRS_DEP_TIME - 2h`. Certified arrival models (e.g., P4 NGBoost Student-T, HistGradientBoosting, Ridge) feed downstream turn simulation and gate solvers.
2. **Auxiliary Departure (`ModelTask.AUXILIARY_DEPARTURE`)**: An exploratory binary classification model predicting delay $\ge 15$ minutes on outbound flights (`ORIGIN = "ATL"`). It was strictly prohibited from feeding downstream solvers (`downstream_eligible = False`).

### The Problem
Downstream gate optimization requires precise modeling of aircraft turn times:
$$\text{Turn Duration} = \text{Actual Gate-Out Time} - \text{Actual Gate-In Time}$$
Without an authoritative outbound continuous delay forecast, gate assignment must rely on static scheduled buffer assumptions or uncertified heuristics. To upgrade Aeolus into a **Dual Core** prediction engine (Arrival + Departure), a dedicated, independent `CORE_DEPARTURE` task is required to forecast continuous signed `DEP_DELAY` at $T-2\text{h}$ before scheduled pushback.

---

## 2. Decision Summary

We formally establish the **Core Departure V1 Contract**, integrating:
1. `ModelTask.CORE_DEPARTURE = "core_departure"` in `src/models/interfaces.py`.
2. `ModelTarget.DEPARTURE_DELAY_SIGNED = "departure_delay_signed"` in `src/models/interfaces.py`.
3. An audited 10-feature predictor matrix in `src/features/departure_features.py` and `configs/departure_core_v1.yaml`.
4. Extended task-aware leakage guards in `src/data/leakage_rules.py`.
5. Registration of `departure_linear_baseline_v1` in `src/models/registry.py` with `downstream_eligible = False`.
6. Enforced role-based gating requiring certified role `GATE_OUT_PREDICTION` before any departure model may execute in downstream gate solvers.

---

## 3. Detailed Specification

### 3.1 Population and Operational Cutoff
- **Population Boundary**: Outbound flights with scheduled departure from Atlanta (`ORIGIN == "ATL"`).
- **Constant Dropping**: `ORIGIN` is constant across all records and is dropped from feature matrix $X$ (`DROP_CONSTANT`).
- **Route Feature**: `DEST` is preserved as an active categorical feature.
- **Prediction Cutoff**: $T-2\text{h}$ before scheduled departure:
  $$\text{Cutoff} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$$
  Evaluated in local Atlanta time (`America/New_York`).

### 3.2 Target Definition and Treatment
- **Primary Continuous Regression Target**:
  $$y_{\text{dep\_reg}} = \text{signed DEP\_DELAY}$$
  - Units: Continuous signed minutes (e.g., $-5.0$ represents a pushback 5 minutes early; $+32.0$ represents a pushback 32 minutes late).
  - P1 Audit Confirmation: 3,022,670 outbound records (2016–2024), 0 missing values, 59.05% early pushbacks.
  - Invariant: **Strictly NO clipping and NO imputation**. Early pushbacks reflect valid operational realities and cannot be floored at 0.
- **Auxiliary Classification Label**:
  $$y_{\text{dep\_cls}} = \mathbf{1}[\text{DEP\_DELAY} \ge 15.0]$$
  - Used for secondary classification evaluations and hurdle models.

### 3.3 The 10 Approved V1 Predictor Features
The feature matrix $X$ for Core Departure V1 consists exclusively of the following 10 features:
1. `CRS_ELAPSED_TIME` (float64) — Scheduled gate-to-gate duration.
2. `calendar_month` (int16) — Derived from `FL_DATE` (1–12).
3. `calendar_day_of_month` (int16) — Derived from `FL_DATE` (1–31).
4. `calendar_day_of_week` (int16) — Derived from `FL_DATE` (1 = Monday, 7 = Sunday).
5. `is_weekend` (int8) — Indicator whether `calendar_day_of_week` $\in \{6, 7\}$.
6. `scheduled_departure_hour` (int16) — Hour of `CRS_DEP_TIME` (0–23).
7. `scheduled_departure_minute` (int16) — Minute of `CRS_DEP_TIME` (0–59).
8. `OP_CARRIER` (str / category) — Operating airline carrier code.
9. `DEST` (str / category) — Destination airport code.
10. `OP_CARRIER_FL_NUM` (str / category) — Flight number string.

#### Explicit Exclusions in V1
- `calendar_year`: Excluded to prevent temporal extrapolation artifacts across years.
- Raw Weather (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`): Excluded under the audited `DROP` policy.
- Reconstructed Chain Features (`chain_id`, `flight_chain`): Excluded from V1 baseline until outbound flight turn linkage is audited and approved.

---

## 4. Leakage Policy & Fail-Closed Guard

The Core Departure leakage contract enforces strict isolation:
| Column Category | Fields | Policy / Status |
| :--- | :--- | :--- |
| **Delay Targets** | `DEP_DELAY`, `ARR_DELAY`, `y_dep_reg`, `y_arr_reg`, `y_dep_cls`, `y_arr_cls` | `TARGET` / Forbidden in $X$ |
| **Arrival Targets** | `ARR_DELAY`, `y_arr_cls`, `y_arr_reg` | `LEAKAGE` (strictly forbidden in outbound models) |
| **Realized Ops** | `DEP_TIME`, `ARR_TIME`, `WHEELS_OFF`, `WHEELS_ON`, `TAXI_OUT`, `TAXI_IN`, `AIR_TIME`, `ACTUAL_ELAPSED_TIME` | `LEAKAGE` (future realization forbidden at $T-2\text{h}$) |
| **Weather** | `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD` | `INSUFFICIENT_EVIDENCE` / `DROP` |
| **Identifiers** | `flight_key`, `chain_id`, `source_row_number`, `source_year` | `IDENTIFIER_ONLY` / Forbidden in $X$ |
| **Simulation** | `p_delay`, `actual_delay_min`, `pred_time_min` | `SIMULATION_LEAKAGE` / Forbidden in $X$ |
| **Constants** | `ORIGIN`, `ORIGIN_INDEX`, `O_LATITUDE`, `O_LONGITUDE` | `DROP_CONSTANT` / Forbidden in $X$ |
| **Conditional** | `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE` | `CONDITIONAL` (blocked without explicit review) |
| **Uncertain** | `FLIGHTS` | `UNCERTAIN` / Blocked |
| **Unknown Fields**| Any unclassified column | **Fails Closed** immediately (`LeakageRuleViolation`) |

---

## 5. Model Registry and Downstream Gating

### 5.1 Registration of `departure_linear_baseline_v1`
In `src/models/registry.py`:
- `model_id`: `"departure_linear_baseline_v1"`
- `family`: `"linear"`
- `task`: `ModelTask.CORE_DEPARTURE` (`"core_departure"`)
- `target`: `ModelTarget.DEPARTURE_DELAY_SIGNED` (`"departure_delay_signed"`)
- `status`: `ModelStatus.RESEARCH_CANDIDATE` (`"research_candidate"`)
- `category`: `ModelCategory.CORE_DEPARTURE` (`"CORE_DEPARTURE"`)
- `downstream_eligible`: `False` (in P2)
- `selection_role`: `"core_departure_linear_baseline"`

### 5.2 Protection of Existing Subsystems
1. **Core Arrival 5-Method Cap**: Untouched. Exactly 5 canonical families remain registered under `CORE_POINT`.
2. **Auxiliary Departure Isolation**: `departure_auxiliary_baseline_v1` remains unconditionally blocked from downstream optimization (`is_downstream_eligible` returns `False`).
3. **Downstream Certification Gate**: For any `CORE_DEPARTURE` model, `is_downstream_eligible(model_id)` evaluates:
   ```python
   if spec.task == ModelTask.CORE_DEPARTURE.value:
       if spec.selection_role != "GATE_OUT_PREDICTION":
           return False
       return bool(spec.downstream_eligible)
   ```
4. **Dual Core Feature Flag**: Downstream solvers remain in single-core arrival mode by default. The optimizer dual-core flag is explicitly `False`.

---

## 6. Deliverable Artifacts

- Configuration: `configs/departure_core_v1.yaml`
- Feature Manifest: `artifacts/dual_core/contracts/feature_manifest_departure_v1.json`
- Model Task Contract: `artifacts/dual_core/contracts/model_task_contract_v2.json`
- Feature Builder: `src/features/departure_features.py`
- Leakage Rules: `src/data/leakage_rules.py`
- Registry & Interfaces: `src/models/interfaces.py`, `src/models/registry.py`
- Test Suite: `tests/test_core_departure_contracts.py`
