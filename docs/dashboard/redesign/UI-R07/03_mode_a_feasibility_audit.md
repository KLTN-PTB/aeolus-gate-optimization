# AEOLUS DASHBOARD — MODE A FEASIBILITY & CONFLICT AUDIT
**Phase**: UI-R07 v2.0  
**Audit Reference**: Finding D1 (P10-00 Research Audit)  

---

## 1. The Apparent Paradox

The P10-00 research audit identified a key apparent paradox in the Monte Carlo results for Mode A (Fixed Plan Robustness):
- **Physical Contact-Gate Conflict Probability**: **74.8%** (374 out of 500 scenarios have at least one pair of flights physically occupying the same contact gate simultaneously).
- **Static Hard Feasibility Rate**: **0.0%** (0 out of 500 scenarios are certified feasible by the independent verifier).

Prior dashboard versions occasionally presented confusing statements such as *"25.2% of scenarios had no conflicts, so they remained feasible"*. Such statements violate scientific truth and are banned in Phase UI-R07.

---

## 2. Root Cause Analysis: The Remaining 25.2%

Why are the 126 non-conflicting scenarios (25.2%) still certified as `feasible = False`?

### Code Trace in Independent Verifier (`src/optimization/domain.py` & `src/simulation/monte_carlo_engine_p09.py`)
```python
is_feasible = bool(
    eval_res.feasible
    and diag.is_valid
    and diag.conflict_count == 0
    and not remote_violation
)
```
In `verify_hard_constraints_independently`:
1. **Separation Buffer Invalidation (`buffer_violations`)**:
   - Contact gates mandate a 15-minute separation buffer ($B=15\text{ min}$) between consecutive flights to allow for pushback, wing-walker clearance, and apron taxiing.
   - Even when flight delays do not cause two aircraft to overlap physically ($T_{\text{overlap}} = 0$), late departures frequently erode the 15-minute buffer deficit ($W_2.\text{start} < W_1.\text{end} + B$), creating a safety violation.
2. **Static Slot Timeline Mismatch (`timeline_mismatch_violations`)**:
   - The frozen gate assignment contract assigns a flight to a planned time interval $[T_{\text{arr}}^{\text{sched}}, T_{\text{dep}}^{\text{sched}} + B)$.
   - Realized stochastic delays shift the actual turnaround window. Without tactical reassignment or slot adjustment, the frozen gate assignment is legally and operationally invalidated.

### Summary Partition of the 500 Scenarios (Mode A)
```
[ 500 Stochastic Scenarios in Mode A ]
  ├── 374 scenarios (74.8%): Direct Physical Contact-Gate Overlap  ---> Infeasible
  └── 126 scenarios (25.2%): Separation Buffer Deficit / Slot Shift ---> Infeasible
  --------------------------------------------------------------------------------
  Total Statically Feasible: 0 scenarios (0.0%)
```

---

## 3. UI Presentation Mandate

The dashboard must display **both metrics distinctly with precise domain definitions**:
1. **Physical Conflict Rate (Xác suất Xung đột Vật lý Cổng)**: `74.8%` (Direct physical contact gate overlap).
2. **Static Hard Feasibility Rate (Tỷ lệ Khả thi Kế hoạch Tĩnh)**: `0.0%` (Zero scenarios comply 100% with static slot windows, buffer separation, and timing contracts without recourse re-optimization).
