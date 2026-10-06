# Decision — Gate Optimization Input Contract & Simulation Safety

Decision date: 2026-09-20  
Protocol version: 4.0  
Status: **LOCKED**

## Context

The downstream gate optimization module (Weeks 7–10) assigns arriving/departing flights to airport gates based on schedule data and ML model delay predictions.

## Decisions

1. **Optimizer Input Contract**:
   - The CP-SAT solver and Simulated Annealing metaheuristic MUST consume ONLY model-derived prediction outputs (`p_delay` probability and `delay_est_min` expected delay) as inputs.
   - Direct usage or injection of raw ground truth delay labels (`ARR_DELAY` or `DEP_DELAY`) into the optimizer is STRICTLY PROHIBITED.

2. **Synthetic Airport & Aircraft Identity**:
   - The Aeolus dataset contains no real airport gate topology, gate assignment histories, or physical aircraft tail numbers.
   - Airport gates, contact/remote stand designations, aircraft compatibility matrices, and aircraft types are synthetic simulation constructs.

3. **Sealed 2024 Holdout Protection**:
   - Monte Carlo simulation and gate optimization MUST NOT access or open the sealed 2024 Final Holdout.
   - All scenario delays generated during Monte Carlo robustness evaluation are derived using synthetic random sampling based on model predictions.

4. **Multi-Stage Optimization Sequence**:
   - Optimization follows the sequence: Greedy Baseline -> CP-SAT Exact Solver -> CP-SAT + Simulated Annealing (CP-SAT+SA).
   - CP-SAT guarantees feasibility against hard operational constraints (aircraft compatibility, gate availability windows, no-overlap occupancy).
   - SA optimizes soft trade-offs (reassignment penalties, expected delay risks, gate load balance, remote stand penalties).

## Consequences

- All gate optimization data models and contracts enforce type validation and prohibit passing raw ground truth values.
- Automated tests verify that 2024 holdout is unopened and synthetic sampling operates deterministically.
