# AEOLUS-G8 — Comprehensive Limitations, Edge Cases and Operational Risks

## 1. Academic & Scientific Limitations

This independent audit identifies the following explicit limitations that must be transparently disclosed in the Bachelor thesis manuscript and defense presentation:

### 1.1 Limitation 1: BTS TranStats Aircraft Tail Number Absence
- **Observation**: The raw BTS TranStats on-time performance dataset for Atlanta (ATL) does not contain physical airframe tail identifiers (`TAIL_NUM` is absent or stripped in the tabular distribution).
- **Consequence**: The deterministic pairing engine (`DeterministicPairingEngine`), which strictly requires verified tail numbers to declare `VERIFIED_ROTATION`, yields **0 verified pairs** on raw BTS data in real-only mode.
- **Remediation & Defense Position**: Rather than synthetically faking tail numbers, the engine operates honestly:
  - In `REAL_ONLY` mode, arrivals and departures are treated as independent gate allocation jobs ($N = 200$ jobs on Thanksgiving 2023).
  - In `INFERRED` mode, turnaround pairs are linked using carrier matching and operational dwell windows ($45 \le \Delta t \le 180$ min), yielding 59 inferred pairs.
  - This preserves scientific truthfulness without compromising optimizer capability.

### 1.2 Limitation 2: Flight Chain & Weather Lookahead Barrier (REQ-04)
- **Observation**: The thesis outline proposed comparing Tabular vs Tabular + Flight Chain.
- **Consequence**: Flight chain features require snapshot knowledge of upstream inbound aircraft states at $T-2\text{h}$. In historical retrospective datasets, upstream delay information is often recorded post-hoc, introducing subtle temporal leakage. Raw METAR weather data also lacks numerical weather prediction (NWP) forecast timestamps at $T-2\text{h}$.
- **Remediation & Defense Position**: Flight chain and weather features were intentionally quarantined to exploratory ablation studies. The production gate pipeline certifies Tabular features exclusively, eliminating $T-2\text{h}$ lookahead leakage. This deviation is a scientific strength (demonstrating data leakage rigor) but requires formal advisor notation.

### 1.3 Limitation 3: Outbound Classification Model Scope (REQ-02)
- **Observation**: The thesis outline specified Logistic Regression, Random Forest, and XGBoost for $P(\text{delay} \ge 15)$.
- **Consequence**: Inbound has all three models plus continuous NGBoost Student-t. For Outbound, calibrated Logistic Regression and calibrated XGBoostClassifier were trained and serialized in G3; Random Forest was evaluated historically but not serialized as a final outbound classifier checkpoint.
- **Remediation & Defense Position**: Disclose that Outbound classification is anchored by Logistic Regression (linear baseline) and XGBoost Classifier (non-linear champion), both verified with Platt and Isotonic calibration ($\text{ECE} \approx 0.011$).

### 1.4 Limitation 4: P5 Quantile Regression Native Checkpoint Absence
- **Observation**: Model P5 (Quantile Gradient Boosting) has historical prediction parquet outputs in `artifacts/probabilistic/`, but no native serialized model binary (`model.pkl`).
- **Consequence**: Model P5 cannot perform online inference on new flight instances at runtime without re-fitting.
- **Remediation & Defense Position**: Disclose Model P5 as a historical benchmark baseline; continuous probabilistic inference in production is driven exclusively by Model P4 (NGBoost Student-t).

### 1.5 Limitation 5: Monte Carlo Remediation Realization Count (REQ-08)
- **Observation**: Historical Monte Carlo P09 ran 500 realizations, but suffered from retrospective hindsight in Mode B and heuristic foresight in Mode C.
- **Consequence**: The remediated engine (`monte_carlo_engine_v2.py`) with non-anticipative Mode B2 and CP-SAT proven optimal Mode C-Oracle was verified on $N=100$ pilot realizations to maintain reasonable testing runtime.
- **Remediation & Defense Position**: Disclose that while historical 500-scenario data exists for Mode A, the causal Mode B2 and CP-SAT Mode C-Oracle were validated on $N=100$ scenarios with full Common Random Numbers and 95% confidence intervals. Scaling to $N=500$ scenarios with CP-SAT oracle takes approximately 2 hours and can be run as an overnight batch job.

### 1.6 Limitation 6: Dashboard Live Browser Visual QA (REQ-09)
- **Observation**: All 359 Streamlit tests passed headlessly via `streamlit.testing.v1.AppTest`.
- **Consequence**: Interactive visual inspection on a live Chromium/Firefox browser by human evaluators remains designated as `VISUAL_QA_PENDING`.
- **Remediation & Defense Position**: Disclose that headless programmatic rendering, state isolation, and status mappings are 100% verified; the live interactive browser demo will be presented directly during the defense.

---

## 2. Operational Risk Matrix

| Risk Code | Risk Summary | Severity | Mitigation & Defense Shield |
|:---|:---|:---:|:---|
| **RSK-01** | Defense committee asks why hybrid CP-SAT+SA has 0.0% improvement | High | Present mathematical theorem: CP-SAT global optimum is proven; no heuristic can improve upon a proven global minimum. |
| **RSK-02** | Committee asks why Median predictor beats ML on MAE | High | Present L1 statistical theorem: Median minimizes absolute loss on zero-skew bulk; ML is optimized for RMSE and dominates on tail delays ($\ge 15$, $\ge 60$ min). |
| **RSK-03** | Committee asks why 2024 holdout wasn't used for final selection | High | Disclose that 2024 was previously touched during exploratory auditing; 2023 serves as the clean selection benchmark to prevent holdout overfitting. |
| **RSK-04** | Committee asks why flight chain features were omitted | Medium | Demonstrate that historical BTS data lacks verified $T-2\text{h}$ upstream snapshots; omitting them prevents catastrophic temporal leakage. |
