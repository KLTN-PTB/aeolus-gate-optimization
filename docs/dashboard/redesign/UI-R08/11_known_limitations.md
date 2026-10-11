# UI-R08 Deliverable 11: Scientific Scope & Known Research Limitations

**Audit Date:** 2026-10-11  
**Auditor:** Principal Scientific Software Engineer & Research Reproducibility Specialist  
**Standard:** Open Science & Academic Research Transparency  
**Purpose:** Comprehensive declaration of methodological boundaries, assumptions, and constraints

---

## 1. Machine Learning & Predictive Scope

### 1.1. Point Forecasts vs Probabilistic Predictive Distributions (Finding D1/D2)
- **Current Formulation:** The dual-core XGBoost models provide deterministic expected point predictions ($\hat{y} = \mathbb{E}[Y | X]$). Safety margins against delay uncertainty are handled via a fixed 15-minute separation buffer and turnaround slack absorption.
- **Limitation:** The models do not currently output full Bayesian posteriors or conformal prediction intervals in real-time solving. Future research should integrate quantile loss regression ($q_{0.1}, q_{0.5}, q_{0.9}$) directly into the solver's chance-constrained programming model.

### 1.2. Temporal Quarantine of Holdout Operational Year 2024
- **Boundary:** To avoid out-of-sample data contamination and temporal leakage, the operational BTS OTP data for year `2024` is strictly quarantined (`DashboardConfig.quarantined_years`).
- **Research Impact:** All reported benchmarks, turn synthesis experiments, and training checkpoints reflect BTS OTP `2023` curated datasets. Performance under severe 2024 airspace disruption scenarios (e.g., nationwide ground stops) has not been empirically evaluated in this thesis phase.

---

## 2. Aircraft Turnaround & Operational Domain

### 2.1. Synthesized Turn Linkages vs Proprietary Airline Tail Routings
- **Boundary:** In the public BTS OTP dataset, airframe tail numbers are logged, but private airline dispatch turn pairing manifests are proprietary and confidential.
- **Synthesis Rule:** Aircraft turn linkages are reconstructed using the standard aviation domain rule: matching identical carrier, same aircraft tail, and a minimum turnaround window $\ge 45$ minutes.
- **Limitation:** Complex airline operational constraints—such as flight crew duty time limits, gate catering vehicle routing, and overnight maintenance checks—are omitted from the objective function.

### 2.2. Single-Hub Operational Scope (Atlanta ATL)
- **Boundary:** Canonical evaluation scenarios are focused on Atlanta Hartsfield-Jackson International Airport (ATL), representing the world's highest-density hub.
- **Limitation:** Network-wide ripple effects connecting downstream hubs (e.g. ATL -> ORD -> DFW) are not modeled simultaneously in a multi-airport network optimization framework.

---

## 3. Optimization Solvers & Scalability Limits

### 3.1. CP-SAT Mega-Hub Scalability Boundary ($N=1500$ Flights)
- **Empirical Boundary:** Under a 30-second operational time limit, exact CP-SAT successfully solves up to $N=500$ flights. At $N=1500$ flights on 50 gates, CP-SAT halts without finding a feasible integer solution (`status: "UNKNOWN"`, `feasible: False`).
- **Scientific Implication:** Confirms that exact constraint programming alone is insufficient for real-time mega-hub dispatching, necessitating the development and validation of heuristic (Greedy, Simulated Annealing) and hybrid decomposition methods.

### 3.2. Mode C Oracle Reference Heuristic Nature
- **Boundary:** Mode C evaluates perfect-foresight hindsight across 500 stochastic realization scenarios using a deterministic Greedy solver.
- **Limitation:** Mode C provides an empirical upper-bound benchmark; it **does not** constitute a mathematically proven global optimal bound, and it **cannot** be deployed in operational environments where future realization delays are unknown at dispatch time.
