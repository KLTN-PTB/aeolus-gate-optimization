# Aeolus Probabilistic Core Arrival & Gate Optimization — V4

[![Certification Status](https://img.shields.io/badge/Certification-CERTIFIED__WITH__LIMITATIONS-blue.svg)](FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)
[![Active Tests](https://img.shields.io/badge/Active%20Tests-1%2C216%20PASSED%20(exit%200)-success.svg)](pytest.ini)
[![Certification Suite](https://img.shields.io/badge/Certification%20Suite-75%2F75%20PASSED-brightgreen.svg)](tests/test_r24_final_certification.py)
[![Downstream Regression](https://img.shields.io/badge/Downstream%20Regression-21%2F21%20PASSED-success.svg)](tests/downstream/test_p11r_post_holdout.py)
[![Python Version](https://img.shields.io/badge/Python-3.11.15-informational.svg)](requirements.txt)
[![Branch](https://img.shields.io/badge/Branch-v4--final--forensic--certification-brightgreen.svg)](https://github.com/KLTN-PTB/aeolus-gate-optimization/tree/v4-final-forensic-certification)

> **Authoritative Scientific Release State**: The Aeolus research program has achieved **Phase P14 Final Scientific Certification** with verdict **`CERTIFIED_WITH_LIMITATIONS`** and **`REBUILD_REQUIRED = NO`**. All empirical claims across 13 certified scientific domains have been audited against raw physical artifacts, validated by a frozen post-holdout re-evaluation on calendar year 2024 (**Phase P11-R**), verified by a 1,216-test active test suite (100% clean pass rate), and certified under strict epistemic bounds.

---

## 1. Executive Summary & Research Workflow

Aeolus investigates whether machine-learned flight arrival delay forecasts—evaluated under point, quantile, and parametric continuous probabilistic representations—can measurably improve airport flight-to-gate assignment schedules relative to conventional heuristic dispatch.

The research framework operates strictly under the **Predict $\to$ Simulate $\to$ Optimize $\to$ Evaluate** operational loop:

```text
[BTS Inbound Traffic DEST=ATL] (CRS_DEP_TIME - 2h cutoff)
           │
           ▼
┌────────────────────────────────────────────────────────┐
│               PREDICTION ARCHITECTURE                  │
│  • Point Baseline: Ridge (2016-2022 fit; Dev Co-Champ) │
│  • Role B (Forecast-Only): P5 Multi-Pinball LightGBM   │
│  • Role C (Stochastic Engine): P4 Student-T NGBoost   │
└────────────────────────────────────────────────────────┘
           │ (Continuous parameter triplet mu, sigma, nu)
           ▼
┌────────────────────────────────────────────────────────┐
│            SYNTHETIC TURN SIMULATION (ATL)             │
│  • AircraftTurnModel: 45m turn, 60m dwell, 15m buffer  │
│  • 10 contact gates, 1 overflow apron                  │
│  • Stochastic arrival draws via PCG64 CRN matrix       │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│            GATE ASSIGNMENT OPTIMIZATION                │
│  • Deterministic Greedy (0.5 - 2.3 ms fast dispatch)   │
│  • Google OR-Tools CP-SAT (Branch-and-Bound, 2.0s max) │
│  • Simulated Annealing (Stochastic Local Search, 2.0s) │
│  • Hybrid CP-SAT + SA (Warm-Start Composition, 2.0s)   │
│  • Strict EQUAL_WALL_CLOCK_BUDGET (2.0s ceiling)       │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│       FORENSIC RECONCILIATION & CERTIFICATION          │
│  • 13 Certified Scientific Domains audited & locked    │
│  • 1,216 active tests (100% PASS, exit code 0)         │
│  • Final Status: CERTIFIED_WITH_LIMITATIONS            │
│  • Rebuild Required: NO                                │
└────────────────────────────────────────────────────────┘
```

---

## 2. Certified Core Experimental Results

### 2.1. Arrival Delay Prediction on Calendar Year 2024
In accordance with strict temporal governance, 2024 results are partitioned by evaluation generation. Evaluated on $N = 5,000$ monthly-stratified commercial passenger flights arriving at Atlanta Hartsfield-Jackson (`DEST = 'ATL'`), with feature cutoff strictly enforced at $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 120\text{ minutes}$:

| Model ID | Formal Scientific Role | Historical 2024 Holdout MAE (min) | Repaired P11-R 2024 MAE (min) | Exact Continuous CRPS (min) | Quantile CRPS Proxy (min) | Exact Continuous NLL | Downstream Engine Eligibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **`arrival_linear_baseline_v1` (Ridge)** | Point Baseline / Dev Co-Champion | 22.91 min | 23.39 min | — | — | — | Point Comparator Only |
| **`arrival_xgboost_baseline_v1`** | Point Benchmark | 24.36 min | — | — | — | — | Point Comparator Only |
| **`arrival_weighted_ensemble_v1`** | Point Co-Champion (Dev 2023) | 23.32 min | — | — | — | — | Point Comparator Only |
| **`P5_quantile_regression`** | **Role B: Marginal Quantile Forecast Champion** | **21.69 min** | Historical Ref | — | **16.77 min** (Pinball: 6.82m) | N/A (No density) | **INELIGIBLE (FORECAST_ONLY)** |
| **`P4_ngboost_student_t`** | **Role C: Continuous Downstream Stochastic Engine** | 21.96 min | **21.97 min** | **18.33 min** (Student-T closed form) | — | **4.62** | **CERTIFIED ENGINE** |
| **`oracle_actual`** | Acausal Theoretical Bound (Non-deployable) | 0.00 min | 0.00 min | 0.00 min | — | — | Theoretical Upper Bound |

*Authoritative Forensic Clarifications (Phases R39, P10-A, P11-R, P14)*:
- **P4 Student-T (Role C)**: Serialized checkpoint verified on disk ([`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib), SHA-256 `e7e7462f...`). Delivers exact closed-form Student-t CRPS (18.33 min) and continuous NLL (4.62). Captures fat-tailed arrival dynamics with empirical degrees of freedom mean $\nu = 2.52 \in [2.10, 2.78]$. Marginal interval calibration is disclaimed (`NOT_SEPARATELY_CERTIFIED`).
- **P5 Quantile Regression (Role B)**: Evaluates 9 discrete quantiles ($\tau \in \{0.10, \dots, 0.90\}$). Generates pinball loss of $6.82$ min and trapezoidal quantile CRPS proxy of $16.77$ min. Has no continuous density and is **strictly prohibited from acting as a downstream continuous stochastic sampler**. Absence of serialized checkpoint on disk is certified as non-blocking because P5 is permanently assigned to Role B.
- **Decoupled Roles**: Ridge and Weighted Ensemble tied on 2023 development data within $\pm 0.10$ min MAE band. The claim of a single joint champion is rejected; models serve mathematically decoupled roles.

---

### 2.2. Downstream Gate Assignment Benchmark Across 4 Seasonal Scenarios
Evaluated across 64 operational runs ($4\text{ scenarios} \times 4\text{ models} \times 4\text{ solvers}$) on calendar year 2024 banks under a uniform wall-clock compute ceiling ($T_{\text{total}} = 2.0\text{ seconds}$):

| Solver | Budget Type | Configured Limit | Actual Runtime Range | Hard Feasibility Rate | Proven CP-SAT Optimality | Mean Realized Conflicts | Solver Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **`DeterministicGreedy`** | `WALL_CLOCK` | 2.0 s | **0.51 ms – 2.31 ms** | **100% (64/64)** | N/A (Heuristic) | 0 | **FEASIBLE** |
| **`CPSat`** | `WALL_CLOCK` | 2.0 s | **65.7 ms – 1,016.5 ms**| **100% (64/64)** | **100% (16/16)** (0.0% gap) | 0 | **OPTIMAL** |
| **`SimulatedAnnealing`** | `WALL_CLOCK` | 2.0 s | **2,000.5 ms – 2,002.4 ms** | **100% (64/64)** | N/A (Metaheuristic) | 0 | **FEASIBLE** |
| **`HybridCPSatSA`** | `SPLIT_WALL_CLOCK` | 2.0 s (1.0+1.0) | **1,064.8 ms – 2,010.0 ms** | **100% (64/64)** | Matches CP-SAT (16/16) | 0 | **FEASIBLE** |

*Solver Fairness Semantics (Phases R35, P11-R, P14)*:
- **`EQUAL_WALL_CLOCK_BUDGET = PROVEN`**: All four solvers terminate within the uniform 2.0s envelope.
- **`EQUAL_COMPUTATIONAL_WORK = NOT_PROVEN`**: Computational operation counts (FLOPs) are fundamentally disparate ($O(N \log M)$ greedy dispatch vs. branch-and-bound search vs. stochastic neighborhood walks).
- **Hybrid Marginal Gain ($\Delta = 0.0$)**: In 100% of cases, CP-SAT proves global optimality during the first 1.0s sub-budget, leaving Simulated Annealing unable to find any strictly lower objective.

---

### 2.3. Monte Carlo Robustness & Recourse (Mode A & Mode B)
Subjected to $N = 500$ canonical stochastic realizations drawn via Common Random Numbers (CRN) from the certified continuous Student-t distribution ($P4$):

* **Mode A: Fixed-Plan Operational Robustness (No Reassignment Under Realization)**:
  - In peak summer congestion (`SCEN_2024_SUMMER`, 60 flights, 15 gates), the fixed schedule planned using **`P4_ngboost_student_t` achieved 100.0% feasibility** (zero gate conflicts across all 500 realizations).
  - In stark contrast, `schedule_only` suffered 0.72 average conflicts per realization and degraded to **27.6% feasibility**.
  - The linear baseline (`arrival_linear_baseline_v1`) collapsed to **2.4% feasibility** (1.67 average conflicts).
  - The acausal point oracle (`oracle_actual`) collapsed to **0.0% feasibility** (9.58 average conflicts), proving that point-optimized schedules without stochastic margin collapse catastrophically under arrival jitter.
* **Mode B: Recourse Dynamic Recovery**:
  - Dynamic real-time gate reassignments resolved **100% of realized conflicts** in $<1.0\text{ ms}$ per realization across all seasons.

---

## 3. Strict Epistemological Boundaries & Certified Disclaimers

In accordance with Phase P14 certification standards, the following boundaries are strictly enforced:

1. **2024 Post-Holdout Semantics**: Calendar year 2024 evidence is classified as `POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR` and must never be labeled as an untouched or first-access holdout.
2. **No Single Overall Champion**: Point, quantile, and continuous models serve mathematically distinct roles; asserting an overall benchmark winner is prohibited.
3. **P5 Forecast-Only Status**: P5 quantile regression has no continuous density and is strictly barred from continuous downstream sampling.
4. **P4 Calibration Disclosure**: Native P4 predictive intervals are mathematically proper but remain `NOT_SEPARATELY_CERTIFIED` for empirical coverage calibration.
5. **No Real Airfield Operations**: Evaluations are conducted in a synthetic simulation environment (10 contact gates, 1 apron); claims of live deployment at Atlanta (ATL) or real-world delay reductions are prohibited.
6. **Contained Reproducibility Only**: Bit-for-bit repeatability is certified strictly within Python 3.11.15 Windows AMD64 with pinned packages; universal cross-platform bit identity is disclaimed (`BITWISE_REPRODUCIBILITY = NOT_PROVEN`).
7. **No 82.4% CRN Variance Reduction**: Historical claim of 82.4% CRN variance reduction is formally retracted and marked `NOT_SUPPORTED`.
8. **No Mathematical Optimal Sample Size**: Monte Carlo $N = 500$ is an operational budget choice, not a proven asymptotic optimum.
9. **Raw Data Hash Limitation**: Raw multi-gigabyte data CSV files lack initial cryptographic SHA-256 checksum sidecars (`DATA_HASH = UNAVAILABLE`).

---

## 4. Quickstart: Reproducing Certified Verification Gates

### Prerequisites
- Python `3.11.15` (Windows AMD64)
- Git 2.40+

### Setup & Test Execution
```powershell
# 1. Clone repository and checkout certified branch
git clone https://github.com/KLTN-PTB/aeolus-gate-optimization.git
cd aeolus-gate-optimization
git checkout v4-final-forensic-certification

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Execute full active test suite (1,216 tests, Runtime: ~82s, exit code 0)
python -m pytest -q

# 4. Execute narrow current certification suite (75 tests, Runtime: ~1.5s, exit code 0)
python -m pytest tests/test_r24_final_certification.py `
                 tests/test_r27_certification_hardening.py `
                 tests/test_r31_final_certification.py `
                 tests/test_r37_final_certification.py `
                 tests/test_phase10_system_freeze.py

# 5. Execute P11-R downstream regression suite (21 tests, Runtime: ~6.7s, exit code 0)
python -m pytest tests/downstream/test_p11r_post_holdout.py `
                 tests/downstream/test_week10_robustness_freeze.py `
                 tests/downstream/test_native_p4_downstream.py

# 6. Execute active protocol & holdout guard suite (51 tests, Runtime: ~3.4s, exit code 0)
python -m pytest tests/test_audit_provenance_guards.py `
                 tests/test_holdout_guard.py `
                 tests/test_holdout_and_fold_guards.py `
                 tests/test_week5_hpo_guard_cleanup_provenance.py `
                 tests/test_r20_freeze_gate.py `
                 tests/test_r22_system_freeze_v3.py `
                 tests/test_phase10_system_freeze.py
```

---

## 5. Authoritative Documentation Roadmap

For detailed investigations, consult the specialized forensic and certification packages:

- 🏛️ **Final Scientific Certification Report (P14)**: [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)
- 🔬 **Scoped Reproducibility Audit (P13)**: [`SCOPED_REPRODUCIBILITY_AUDIT.md`](SCOPED_REPRODUCIBILITY_AUDIT.md)
- ⚖️ **Final Test Scope Reconciliation (P12-R1)**: [`FINAL_TEST_SCOPE_RECONCILIATION.md`](FINAL_TEST_SCOPE_RECONCILIATION.md)
- 📊 **2024 Post-Holdout Re-Evaluation Report (P11-R)**: [`P11R_FINAL_REPORT.md`](P11R_FINAL_REPORT.md)
- ❄️ **Authoritative Full System Freeze Manifest**: [`system_freeze_manifest.json`](system_freeze_manifest.json)
- 📜 **Master Documentation Index**: [`docs/README.md`](docs/README.md)
- 📐 **System State & Architectural Invariants**: [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
- 🗺️ **Repository Directory Layout**: [`project_structure.md`](project_structure.md)
