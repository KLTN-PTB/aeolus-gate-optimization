# AEOLUS-G8 — Approved Experimental Results for Bachelor Thesis

## 1. Classification Taxonomy

To ensure uncompromising academic rigor during thesis manuscript compilation and oral defense, all experimental results produced across the Aeolus Gate Optimization repository are strictly categorized into four authoritative tiers:

1. **TIER 1: Recomputed & Verified Results (Kết quả đã tính lại và xác minh)**: Certified with full code lineage, cryptographic hashes, deterministic reproducibility, and active tests. Permitted as primary thesis claims.
2. **TIER 2: Historical-Evidence-Only Results (Kết quả chỉ có bằng chứng lịch sử)**: Derived from frozen experimental runs whose artifacts exist in the repository, but whose live generation scripts are obsolete or exploratory. Permitted with documented historical attribution.
3. **TIER 3: Illustrative-Only Results (Kết quả chỉ dùng minh họa)**: Synthetic scenarios and conceptual proofs used to demonstrate algorithmic scaling or UI rendering. Permitted strictly for architectural illustration, not empirical performance claims.
4. **TIER 4: Disallowed As Primary Claims (Kết quả không được dùng làm claim chính)**: Deprecated, heuristic, or unverified claims that must NOT be presented as factual empirical findings.

---

## 2. Category Breakdown & Catalog

### 2.1 TIER 1: Recomputed & Verified Results (Approved as Primary Claims)

| Result Domain | Verified Metric / Finding | Exact Values & Tolerance | Evidence Source Path |
|:---|:---|:---|:---|
| **CP-SAT Mathematical Optimality** | Exact optimality proof and parity with Combinatorial Oracle on small instances ($N=3, M=2$). | Parity diff $< 10^{-4}$; CP-SAT objective = $10.0000$, Oracle = $10.0000$. | `artifacts/remediation/cp_sat/parity_results.json` |
| **Solver Benchmark Comparison** | CP-SAT dramatically reduces gate conflict and assignment costs compared to Greedy baseline on thesis-scale instances ($N \le 300$). | 100 flights: $-19.4\%$ cost reduction;<br>200 flights: $-25.8\%$ cost reduction;<br>300 flights: $-14.8\%$ cost reduction. | `artifacts/remediation/benchmarks/g5_fair_benchmark/fair_benchmark_results.json` |
| **Hybrid 0% Improvement Theorem** | Simulated Annealing achieves $0.0\%$ improvement on CP-SAT optimal solutions because CP-SAT is already globally optimal. | Delta = $0.0000$ points across all optimal instances. | `artifacts/development_end_to_end/aggregate_metrics.json` |
| **Outbound Delay Classification** | Calibrated Logistic Regression and XGBoost classifiers predict $P(\text{delay} \ge 15)$ on 2023 Selection Split ($N=332,734$). | XGBoost: ROC-AUC = $0.6429$, PR-AUC = $0.3292$, Brier = $0.1564$, $\text{ECE} \approx 0.0119$.<br>LR: ROC-AUC = $0.6134$, Brier = $0.1589$, $\text{ECE} \approx 0.0105$. | `artifacts/remediation/outbound_classification/calibrated_metrics.json` |
| **Arrival Continuous NGBoost** | Model P4 (NGBoost Student-t) generates calibrated heavy-tailed distributions with native checkpoint. | Degrees of freedom $\nu = 4.5$, capturing non-Gaussian apron spikes. | `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` |
| **Monte Carlo Causal Recourse** | Online non-anticipative recourse (Mode B2) eliminates 100% of physical gate collisions under realized delays. | Physical conflict rate: Mode A = $76.0\% \to$ Mode B2 = $0.0\%$. Recourse saves $1,459.0$ cost points ($p = 7.03 \times 10^{-21}$). | `artifacts/remediation/monte_carlo_remediated/remediated_statistical_summary.json` |
| **Information Value (B2 vs B1)** | Hindsight clairvoyance incurs $-12.60$ cost points compared to causal online recourse. | Cost delta = $+12.60$ points ($p = 3.44 \times 10^{-9}$). | `artifacts/remediation/monte_carlo_remediated/remediated_paired_comparison.csv` |
| **Optimization Value (C1 vs C2)** | CP-SAT global optimization proves Greedy foresight is sub-optimal by $12.40$ points. | Cost delta = $-12.40$ points ($p = 1.72 \times 10^{-14}$). | `artifacts/remediation/monte_carlo_remediated/remediated_statistical_summary.json` |

---

### 2.2 TIER 2: Historical-Evidence-Only Results (Permitted with Attribution)

| Result Domain | Metric / Finding | Condition for Inclusion in Thesis | Evidence Source Path |
|:---|:---|:---|:---|
| **Optuna HPO Hyperparameters** | Hyperparameter configurations discovered on 2016–2022 development split. | Present as pre-experimental optimization study establishing model configurations. | `artifacts/optuna_studies/` |
| **Model P5 Quantile Regression** | Quantile regression predictions across 5 pinball loss quantiles ($\tau \in \{0.1, 0.25, 0.5, 0.75, 0.9\}$). | Present as historical offline benchmark; state clearly that Model P5 is predictions-only (no native binary). | `artifacts/probabilistic/` |
| **Historical 500-Scenario MC** | Historical 500-scenario simulation results under legacy Mode A / Mode B / Mode C semantics. | Present as baseline robustness exploration; contrast with remediated causal 100-scenario pilot. | `artifacts/remediation/monte_carlo/fixed_plan_results.csv` |

---

### 2.3 TIER 3: Illustrative-Only Results (Permitted Strictly for Illustration)

| Result Domain | Illustrative Use Case | Explicit Thesis Caveat Required | Evidence Source Path |
|:---|:---|:---|:---|
| **Synthetic Scalability Scenarios** | Scalability evaluation on 100 flights x 21 gates, 200 flights x 31 gates, 300 flights x 51 gates. | State clearly: Demonstrates solver algorithmic complexity on synthetic schedules, NOT real flight histories. | `artifacts/remediation/cp_sat/scalability_results.csv` |
| **Gantt Chart Visualizations** | Streamlit Gantt chart timeline depicting flight dwell intervals and buffer windows. | State clearly: Visual aid demonstrating interval constraint modeling and operational buffer enforcement. | `docs/dashboard/redesign/UI-R08/` |
| **Inferred Aircraft Turn Linkage** | 59 inferred turns generated on Thanksgiving 2023 ATL ($N=200$ flights) using carrier and dwell windows. | State clearly: Inferred operational rotation heuristic, NOT physical tail-number airframe tracking. | `artifacts/remediation/native_dual_core_g4_pilot_inferred/` |

---

### 2.4 TIER 4: Disallowed As Primary Claims (Prohibited in Thesis Claims)

| Disallowed Claim | Reason for Prohibition | Required Corrected Claim |
|:---|:---|:---|
| **"Hybrid CP-SAT+SA outperforms CP-SAT"** | Factual error: Hybrid achieves exactly $0.0\%$ improvement on optimal instances. | State: CP-SAT reaches proven global optimum; SA acts as heuristic safety fallback. |
| **"Outbound delay probability was computed via Sigmoid"** | Methodological flaw: Sigmoid on regression scores is an uncalibrated heuristic risk score. | State: Outbound delay probability is computed using calibrated Logistic Regression & XGBoost ($\text{ECE} \approx 0.011$). |
| **"Mode C Greedy is the optimal lower bound"** | Mathematical error: Greedy is a heuristic, sub-optimal by $12.4$ points compared to CP-SAT. | State: Mode C-Heuristic is a greedy benchmark; Mode C-Oracle with CP-SAT is the true lower bound. |
| **"Mode A has 0% feasibility due to 100% gate collisions"** | Misleading conflation: 24.0% of Mode A realizations have zero physical contact conflicts. | State: Mode A incurs 76.0% physical contact collisions; 0% feasibility reflects static timeline mismatches. |
| **"P07 real-data pilot verified physical tail-number rotations"** | Factually untrue: BTS TranStats omits `TAIL_NUM`; real-only mode yields unlinked turn jobs. | State: BTS data omits `TAIL_NUM`; pairing engine operates honestly without synthetic spoofing. |
| **"Tabular + Flight Chain is superior and ready for deployment"** | Data leakage risk: Historical Flight Chain lacks verified $T-2\text{h}$ snapshot availability. | State: Flight Chain is an exploratory research concept; Tabular is the certified production standard. |
