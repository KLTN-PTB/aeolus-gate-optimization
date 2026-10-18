# AEOLUS-G2 — DELIVERABLE 09: FEASIBILITY DEFINITIONS

## 1. Deconstruction of the "0% Feasibility" Legacy Misconception

In legacy P09 artifacts, Mode A (Fixed Plan) was reported as having **0.0% feasibility** across all 500 scenarios. A naive interpretation might conclude that under stochastic delays, a pre-operational gate plan results in a physical aircraft collision or apron disaster 100% of the time.

Forensic audit of `verify_hard_constraints_independently()` revealed why this occurred:
```python
if (
    assign.occupancy_start_min != f.time_window.start_min
    or assign.occupancy_end_min != f.time_window.end_min
):
    timeline_mismatch_violations.append(...)
```
And:
```python
total_hard_violations = len(conflict_pairs) + ... + len(timeline_mismatch_violations)
is_valid = (total_hard_violations == 0)
```
In Mode A, `assign.occupancy_start_min` reflects the *scheduled* arrival time ($t_{arr}^{sched}$). However, under any stochastic realization where even a single flight arrives 1 minute early or late, $f.\text{time\_window}.\text{start\_min} = t_{arr}^{real} \neq t_{arr}^{sched}$. This automatically generated a `timeline_mismatch_violation`, setting `is_valid = False`!

Because the probability that all 120 flights arrive with exactly zero minutes of delay is virtually zero ($\mathbb{P}(\cap_{i=1}^{120} \delta_i = 0) \approx 0$), `is_valid` was `False` in 100% of scenarios!

## 2. Orthogonal Feasibility Dimensions

To restore scientific truth, Gate G2 defines five mutually orthogonal dimensions of operational feasibility:

```
                                  Operational Feasibility Dimensions
                                                 │
          ┌────────────────────────┬─────────────┴───────────────┬────────────────────────┐
          ▼                        ▼                             ▼                        ▼
1. Physical Contact      2. Buffer Clearance            3. Remote Apron           4. Static Slot
   Conflict                 Deficit                        Capacity                  Consistency
   [Aircraft overlap]       [Buffer < 15 min]              [Apron usage > K=5]       [Delta = 0 min]
          │                        │                             │                        │
          └────────────────────────┴─────────────┬───────────────┴────────────────────────┘
                                                 ▼
                                    5. Composite Feasibility
                                       [Physically executable]
```

### 2.1 Physical Contact Gate Conflict (`physical_contact_conflict_count`)
- **Definition:** Two distinct aircraft concurrently occupy the same physical contact gate.
- **Mathematical Condition:**
  $$\exists f_1, f_2 \in \mathcal{F}, f_1 \neq f_2 \quad \text{s.t.} \quad g(f_1) = g(f_2) \in \mathcal{G}_{contact} \quad \text{and} \quad [t_{arr}(f_1), t_{dep}(f_1)) \cap [t_{arr}(f_2), t_{dep}(f_2)) \neq \emptyset$$
- **Operational Severity:** **CRITICAL SAFETY VIOLATION** (aircraft wingtip collision or inability to dock).
- **Mode A Realized Rate:** **76.0%** (24.0% of scenarios had **ZERO** physical contact conflicts!).

### 2.2 Buffer Clearance Deficit (`buffer_violation_count`)
- **Definition:** Two aircraft occupy the same contact gate with less than the mandatory minimum separation buffer ($S_{min} = 15$ min):
  $$t_{arr}(f_2) - t_{dep}(f_1) < S_{min} \quad \text{for consecutive flights } f_1, f_2 \text{ on gate } g$$
- **Operational Severity:** **OPERATIONAL RISK / PROCEDURAL INFRACTION** (pushback tug congestion or minor gate entry delay).

### 2.3 Remote Apron Capacity Violation (`remote_capacity_violation`)
- **Definition:** The concurrent number of aircraft dispatched to remote apron stands exceeds physical stand capacity ($K = 5$).
- **Mathematical Condition:**
  $$\max_{t \in \mathbb{T}} \sum_{f \in \mathcal{F}} \mathbb{I}(g(f) \in \mathcal{G}_{remote} \land t \in [t_{arr}(f), t_{dep}(f))) > K$$
- **Operational Severity:** **SEVERE INFRASTRUCTURE BOTTLENECK** (no available parking stands on airport surface).
- **Mode A Realized Rate:** **0.0%** (remote stands were not utilized in the baseline plan).

### 2.4 Static Schedule Slot Consistency (`static_slot_consistency`)
- **Definition:** Every flight occupies its gate at the exact pre-operational published schedule time:
  $$\delta_{arr}(f) = 0 \quad \text{and} \quad \delta_{dep}(f) = 0 \quad \forall f \in \mathcal{F}$$
- **Operational Severity:** **STATIC SCHEDULE INVARIANCE** (not a physical safety hazard).
- **Mode A Realized Rate:** **0.0%** (stochastic delays naturally disrupt published schedule minutes).

### 2.5 Composite Operational Feasibility (`composite_feasible`)
- **Definition:** A gate plan is physically executable on the airfield without physical collisions, remote stand overflows, unassigned flights, or aircraft incompatibilities:
  $$\text{Composite} = (\text{Physical Conflicts} = 0) \land (\neg \text{Remote Violation}) \land (\text{Unassigned} = 0) \land (\text{Compatibilities Valid})$$
- **Mode A Realized Rate:** **24.0%**. In nearly one in four operating days, the baseline schedule absorbed stochastic delays completely without requiring a single gate reassignment!
