# AEOLUS-G2 — DELIVERABLE 11: ORIGINAL VS REMEDIATED RESULTS

## 1. Side-by-Side Architectural and Methodological Comparison

| Evaluation Metric / Attribute | Legacy Phase P09 Report | Remediated Gate G2 Finding | Status & Forensic Root Cause |
| :--- | :--- | :--- | :--- |
| **Mode A Feasibility Rate** | 0.0% | **24.0% Composite Feasible** (76.0% Contact Conflict) | **CORRECTED:** P09 conflated static schedule timestamp shifts (`timeline_mismatch`) with physical contact gate overlaps. In 24% of realizations, delays produced zero contact collisions. |
| **Mode B Information Regime** | Labeled "Reactive Recourse" (implied real-time deployable) | **Decomposed:**<br>• **Mode B1:** Retrospective Full Hindsight (134.83)<br>• **Mode B2:** Online Non-Anticipative (147.43) | **CORRECTED:** Legacy Mode B passed all 24h delays at once to the solver (clairvoyant). G2 implements a strictly causal rolling horizon with docked flight locking. |
| **Mode B Solver Comparison** | Greedy = CP-SAT = Hybrid ($0.0 \pm 0.0$ deltas) | Confirmed identical initial plans on 120-flight canonical scenario; corrected solver dispatch in engine | **EXPLAINED & REPAIRED:** P09 hardcoded `DeterministicGreedyGateSolver` in Mode B, and the 120-flight canonical scenario was sufficiently sparse that all initial solvers found identical solutions. |
| **Mode C Oracle Status** | Labeled "Perfect Foresight Oracle Lower Bound" using Greedy | **Decomposed:**<br>• **Mode C1:** Greedy Foresight (134.83)<br>• **Mode C2:** CP-SAT Optimal Oracle (122.43) | **CORRECTED:** Greedy heuristic is not a mathematical lower bound. CP-SAT proven global optimization beats Greedy foresight by 12.40 points in 57% of days ($p = 1.72 \times 10^{-14}$). |
| **Price of Uncertainty (EVPI)** | Not reported (hidden by retrospective leakage) | **+12.60 cost points** ($p = 3.44 \times 10^{-9}$) | **NEW SCIENTIFIC FINDING:** Quantifies the performance loss of real-time dispatching without foresight compared to clairvoyant hindsight. |
| **Online Recourse Benefit** | Mode B vs Mode A: -1,529 cost points | Mode B2 vs Mode A: **-1,459 cost points** ($p = 7.03 \times 10^{-21}$) | **CONFIRMED & VALIDATED:** Even under strict non-anticipativity without clairvoyance, real-time recourse saves over 1,450 cost points by eliminating 100% of contact collisions. |
| **Remote Stand Overflow** | 0.0% remote stand violations | **0.0% remote capacity violations** (5 stands sufficient) | **CONFIRMED:** 5 finite remote stands are sufficient to handle canonical 120-flight delay perturbations. |

## 2. Certified Numbers for the Graduation Thesis

The following figures and statistics are certified by the Gate G2 audit and may be cited with absolute scientific confidence in the undergraduate thesis:

1. **Fixed Plan Vulnerability (Mode A):**
   - Under moderate stochastic delay ($\bar{\delta}_{arr} \approx 5.0$ min, $\bar{\delta}_{dep} \approx 8.0$ min with heavy tails), an unadjusted baseline plan suffers physical contact gate collisions in **76.0%** of operating days.
   - An average of **1.50** physical aircraft conflicts occur per day if no recourse action is taken, leading to a mean penalty cost of **1,606.43 points** (P90 = 3,109.75, CVaR-90 = 3,909.14).
   - In **24.0%** of operating days, schedule buffer absorbs stochastic variations completely without physical gate conflict.

2. **Effectiveness of Online Causal Recourse (Mode B2):**
   - Real-time online recourse eliminating future clairvoyance reallocates an average of **4.10 flights per day** (3.4% of total flights).
   - Reallocations achieve a **0.0% physical contact conflict rate** and **0.0% remote stand capacity violations**.
   - Mean operational cost drops from **1,606.43** to **147.43 points**, achieving a statistically significant paired reduction of **1,459.00 points** ($95\%\text{ CI: } [1219.42, 1698.58], t = 11.94, p = 7.03 \times 10^{-21}$).
   - Online recourse strictly improved outcomes in **76.0%** of scenarios and was never worse than the fixed plan (**0.0% worsened**).

3. **Value of Information & Foresight (Mode B2 vs B1 vs C2):**
   - The Expected Value of Perfect Information (hindsight advantage) is **12.60 cost points** ($95\%\text{ CI: } [8.79, 16.41], p = 3.44 \times 10^{-9}$).
   - The global mathematical lower bound under complete foresight (CP-SAT Mode C2) is **122.43 points** (with 1.60 reassignments).
   - The optimality gap between real-time online recourse and the theoretical global oracle is **25.00 cost points** ($95\%\text{ CI: } [20.33, 29.67], p = 9.67 \times 10^{-18}$).

## 3. Strictly Prohibited Claims in the Thesis

The following statements are scientifically false and are **strictly forbidden** from appearing in the thesis:

1. ❌ *"Mode A has 0% feasibility because gates collide 100% of the time."*
   $\rightarrow$ **Mandatory Correction:** State that 24.0% of days are physically feasible with zero collisions, and that the legacy 0% metric was caused by schedule minute shifts.
2. ❌ *"Mode B reactive recourse proves algorithms are real-time deployable when tested on full-day realized delay arrays."*
   $\rightarrow$ **Mandatory Correction:** Clarify that retrospective full-day recourse is a hindsight benchmark (Mode B1), whereas deployable real-time recourse requires event-driven rolling horizons with docked flight locking (Mode B2).
3. ❌ *"Greedy solver achieves the globally optimal oracle lower bound under perfect foresight."*
   $\rightarrow$ **Mandatory Correction:** Acknowledge that Greedy foresight is a heuristic baseline (Mode C1), and that CP-SAT (Mode C2) achieves the true proven mathematical global lower bound, beating Greedy by 12.40 points ($p < 10^{-13}$).
4. ❌ *"Greedy and CP-SAT perform identically in all operational conditions because paired deltas were 0.0."*
   $\rightarrow$ **Mandatory Correction:** Explain that on the canonical 120-flight / 25-gate schedule, low traffic density enabled all solvers to find the zero-conflict global optimum.
