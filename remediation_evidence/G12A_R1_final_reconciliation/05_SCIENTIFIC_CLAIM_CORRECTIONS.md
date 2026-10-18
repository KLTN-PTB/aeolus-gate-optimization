# AEOLUS-G12A-R1: SCIENTIFIC CLAIM CORRECTIONS & DOCUMENTATION INTEGRITY AUDIT

**Date:** 2026-10-12  
**Auditor:** Senior Scientific Software Verification Engineer, Academic Quality Assurance Lead  
**Scope:** Rigorous Epistemological Review of Technical Assertions Across G12A Reports  

---

## 1. Summary of Corrected Scientific Claims

In alignment with academic integrity standards and operations research rigor, the following claims from previous G12A reports are formally corrected and calibrated:

| Domain | Previous Unsubstantiated Phrasing | Formally Corrected Scientific Statement | Technical Rationale |
| :--- | :--- | :--- | :--- |
| **Data Nature** | *"Canonical Real-Data Scenario (120 flights)"* | **Canonical Synthetic Benchmark Scenario (`SCEN_P09_CANONICAL_120`)** | The schedule is generated via `generate_scalability_scenario()` with calibrated airline operational parameters (45–60 min turnaround, 15 min buffer), not a raw uncurated real airport flight log. |
| **Delay Generator** | *"Gaussian Copula empirical correlation $\rho=0.45$"* | **Gaussian Copula with calibrated nominal correlation parameter $\rho=0.45$** | $\rho=0.45$ is a standard benchmark modeling parameter reflecting positive correlation between arrival and departure delays, not an econometric estimation fitted in real time. |
| **Forecasting Method** | *"ML-driven online recourse policy"* | **Stochastic Online Recourse using Causal Operational Lower Bounds** | Mode B2 does not query trained ML models (LightGBM/XGBoost) at epoch $t$; it projects departure time using physical turnaround minimums and scheduled departure: $\max(T_{\text{sched\_dep}}, t + \text{Turnaround}_{\min})$. |
| **Information Value** | *"Formal Value of Perfect Information (VPI)"* | **Empirical Value of Dwell Foresight / Policy Cost Gap** | The $+6.38\%$ cost increase ($\text{Cost}(B_2) - \text{Cost}(B_1)$) reflects the empirical cost gap between an online greedy policy and a clairvoyant greedy heuristic, not a closed-form universal VPI across all theoretical policies. |
| **Oracle Classification** | *"Mode B1 Retrospective Optimal Oracle"* | **Mode B1 Retrospective Heuristic Benchmark** | Mode B1 uses `DeterministicGreedyGateSolver` with realized foresight. It is a heuristic benchmark. Only **Mode C2 (CP-SAT)** is a proven mathematical optimal oracle. |
| **Slot Consistency** | Ambiguity regarding 0% static slot consistency | **Expected Physical Slot Realignment** | Static slot consistency requires exact pre-tactical slot occupancy ($0$ min deviation). Delayed flights naturally violate static slots while maintaining 100% physical collision-free feasibility. |
| **Scalability Claim** | *"500 scenarios run in under 10 seconds"* | **Extrapolation Withdrawn (Empirically Measured at N=20 and N=100 only)** | Mode B2 executes in 1.60s for 300 runs ($N=100$), but Mode C2 CP-SAT requires $42.24$ seconds. Running 500 full CP-SAT scenarios would take $\approx 210$ seconds. Unverified extrapolations are retracted. |

---

## 2. In-Depth Clarification of Corrected Items

### 2.1 Distinction Between Synthetic Benchmark and Operational Field Data
- The test schedule (`SCEN_P09_CANONICAL_120`) consists of 120 flights across 25 contact gates and 5 remote stands.
- While the flight durations, turnaround constraints (30–60 min), separation buffers (15 min), and aircraft categories (narrow-body / wide-body) represent realistic airport operational constraints, the flight schedule itself is generated synthetically to enable controlled, reproducible scalability testing.
- It must not be cited in academic thesis chapters as "live operations from Tan Son Nhat / Noi Bai airport", but rather as a "realistically calibrated synthetic hub benchmark".

### 2.2 Mechanism of Causal Online Recourse
Mode B2 operates via an **event-driven rolling horizon**:
1. At decision epoch $t = T_{\text{arr}}^{\text{realized}}$, flight $f$ arrives at the airport.
2. The controller observes physical gate occupancy: gates with docked planes have estimated release time $\hat{T}_{\text{vacate}} = \max(T_{\text{sched\_dep}}, T_{\text{arr}} + \text{Turnaround}_{\min}, t) + \text{Buffer}$.
3. Gates reserved for approaching flights within $[t, t + 45\text{ min}]$ are protected against preemption.
4. If the nominal gate is blocked, the policy evaluates alternative contact gates. If none are available, it checks remote stand capacity. If all remote stands are full, the flight transitions to `UNASSIGNED / NO_CAPACITY`.
5. This mechanism is completely independent of ML model inference at epoch $t$, relying strictly on physical state observations and deterministic physical constraints.

### 2.3 Empirical Policy Cost Gap vs Formal VPI
- In Stochastic Programming, the **Expected Value of Perfect Information (EVPI)** is formally defined as:
  $$\text{EVPI} = \mathbb{E}_{\xi}\left[ \min_{x \in \mathcal{X}} f(x, \xi) \right] - \min_{x(\cdot) \in \Pi_{\text{non-anticipative}}} \mathbb{E}_{\xi}\left[ f(x(\xi), \xi) \right]$$
- In our benchmark:
  - $\text{Cost}(C_2) = 122.43$ represents the true mathematical lower bound $\mathbb{E}_{\xi}[\min f(x, \xi)]$.
  - $\text{Cost}(B_1) = 134.83$ represents the heuristic foresight cost using greedy dispatching.
  - $\text{Cost}(B_2) = 143.43$ represents the causal online greedy recourse cost.
- Therefore, $\text{Cost}(B_2) - \text{Cost}(B_1) = +8.60$ is an **empirical foresight gap within the greedy dispatching family**, while the true mathematical gap relative to the optimal lower bound is $\text{Cost}(B_2) - \text{Cost}(C_2) = 143.43 - 122.43 = +21.00$ ($+17.15\%$).

---

## 3. Thesis Writing & Defense Guidance

For the Bachelor's Thesis:
1. Present the ordering:
   $$\text{Optimal Foresight Oracle (C2: 122.43)} \le \text{Heuristic Foresight (B1: 134.83)} < \text{Causal Online Recourse (B2: 143.43)} \ll \text{Static Plan (A: 1,606.43)}$$
2. Emphasize that Mode B2 achieves **100% collision-free physical feasibility** without having a crystal ball to predict ground turnaround times.
3. Transparently state that Mode B2 uses physical turnaround constraints and nominal schedule bounds, avoiding misleading claims about real-time ML dwell prediction during online gate dispatch.
