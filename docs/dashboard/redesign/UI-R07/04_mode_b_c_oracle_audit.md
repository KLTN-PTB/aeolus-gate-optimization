# AEOLUS DASHBOARD — MODE B VS MODE C ORACLE AUDIT
**Phase**: UI-R07 v2.0  
**Audit Reference**: Finding D2 (P10-00 Research Audit)  

---

## 1. Problem Statement: Parity & False Optimality Claims

In the historical P09 report and earlier dashboard prototypes:
- Mode B (Reactive Recourse) mean cost was reported as **130.7302 pts**.
- Mode C (Perfect-Foresight Oracle) mean cost was also reported as **130.7302 pts**.
- On every single one of the 500 scenarios:
  $$\max_{i \in [0, 499]} |C_{\text{Mode B}, i} - C_{\text{Mode C}, i}| \equiv 0.0000$$
  $$\max_{i \in [0, 499]} |R_{\text{Mode B}, i} - R_{\text{Mode C}, i}| \equiv 0$$

Earlier UI versions claimed: *"This equality proves that our real-time reactive recourse achieves the global mathematical theoretical lower bound."*

**This was a false scientific claim that Phase UI-R07 permanently eliminates.**

---

## 2. Technical Code Audit of `monte_carlo_engine_p09.py`

Detailed inspection of the simulation engine source code reveals the true underlying mechanism:

### In Mode B (`evaluate_mode_b_reactive_recourse`, lines 374–379):
```python
recourse_solver = DeterministicGreedyGateSolver(config=config)
res_recourse = recourse_solver.solve(
    flights=recourse_flights,
    gates=gates,
    allow_overflow=True,
)
```

### In Mode C (`evaluate_mode_c_perfect_foresight_oracle`, lines 446–447):
```python
oracle_solver = DeterministicGreedyGateSolver(config=config)
res_oracle = oracle_solver.solve(
    flights=realized_flights,
    gates=gates,
    allow_overflow=True,
)
```

### The 11 Audited Verification Dimensions:
1. **Information set at decision time**: Mode B was intended to be causal; Mode C had offline future delay information.
2. **Effective solver in Mode B**: `DeterministicGreedyGateSolver`.
3. **Effective solver in Mode C**: `DeterministicGreedyGateSolver` (NOT CP-SAT, NOT MILP).
4. **Objective & Capacity**: Identical configuration and finite remote capacity.
5. **Input flights**: Identical 120 flights with realized delays.
6. **Decision order**: Both sort flights by arrival time.
7. **Tie-breaking**: Identical deterministic rule.
8. **Resulting gate assignments**: **Identical across 100% of flights and scenarios**.
9. **Scenario costs**: **Identical ($0.0$ difference)**.
10. **Causality of equality**: Induced **100% by shared implementation (`DeterministicGreedyGateSolver`)**.
11. **Optimality certificate**: **None exists**. Deterministic Greedy cannot prove global optimality.

---

## 3. Mandatory Scientific Directives

1. **Elimination of Global Optimum Claims**:
   - The dashboard strictly prohibits asserting that Mode B achieved the "proven global optimum" or that equality with Mode C proves mathematical optimality.
2. **Re-Designation of Mode C**:
   - Mode C must be titled: **`Mode C: Greedy Perfect-Foresight Reference [NON-DEPLOYABLE]`**.
   - The UI states clearly: *"Mode C uses Deterministic Greedy as an empirical benchmark with full future delay information. It is NOT an exact mathematical global lower bound."*
3. **Non-Deployability Callout**:
   - Mode C requires clairvoyant advance knowledge of actual downstream flight delays. In aviation operations, this is non-causal and impossible.
   - It is permanently tagged: **`NON-DEPLOYABLE`**.
