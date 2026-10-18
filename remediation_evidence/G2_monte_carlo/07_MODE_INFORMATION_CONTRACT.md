# AEOLUS-G2 — DELIVERABLE 07: MODE INFORMATION CONTRACT

## 1. Mathematical Formalism of Information Filtration

Let $(\Omega, \mathcal{F}, \mathbb{P})$ be the probability space governing daily flight schedule execution, where $\omega \in \Omega$ represents a realized vector of flight arrival and departure delays:
$$\omega = \{ (\delta_{arr}(f), \delta_{dep}(f)) \}_{f \in \mathcal{F}}$$

Let $\mathbb{T} = [0, T_{max}]$ denote the continuous operational timeline (in minutes from midnight). We define the operational information filtration $(\mathcal{F}_t)_{t \ge 0}$ as the non-decreasing sequence of sub-$\sigma$-algebras:
$$\mathcal{F}_t = \sigma \left( \{ (f, t_{arr}(f), t_{dep}(f)) \mid t_{arr}(f) \le t \} \right)$$
representing all flight arrival events and gate occupations physically realized up to epoch $t$.

## 2. Information Regimes & Decision Rules

```
Information Regime           Available Information               Decision Epoch(s)       Deployability
───────────────────────────────────────────────────────────────────────────────────────────────────────
PRE_OPERATIONAL (Mode A)     F_0 (Predictions at T-2h cutoff)    t = 0 (Pre-ops)         Deployable (Static)
ONLINE_RECOURSE (Mode B2)    F_t (Sequential event filtration)   t = t_arr(f) (Dynamic)  Deployable (Real-Time)
RETROSPECTIVE   (Mode B1)    F_Tmax (Full hindsight at day end)  t = T_max (Post-hoc)    Non-Deployable (Benchmark)
FULL_FORESIGHT  (Mode C)     F_Tmax (Full foresight from start)  t = 0 with F_Tmax       Non-Deployable (Oracle)
```

### 2.1 Mode A: Pre-Operational Static Plan
- **Information Filtration:** $\mathcal{F}_{cutoff} = \mathcal{F}_0$.
- **Decision Variable:** $x_{f, g} \in \{0, 1\}$.
- **Mathematical Invariant:**
  $$x_{f, g}(\omega) = x_{f, g}(\omega') \quad \forall \omega, \omega' \in \Omega$$
  Assignments are frozen prior to operation and are strictly independent of realized delays.

### 2.2 Mode B2: Online Non-Anticipative Recourse
- **Information Filtration:** $\mathcal{F}_t$ at epoch $t = t_{arr}(f_{curr})$.
- **Mathematical Non-Anticipativity Invariant:**
  Let $\omega, \omega' \in \Omega$ be two realizations such that $\omega|_{\mathcal{F}_t} = \omega'|_{\mathcal{F}_t}$ (identical history up to epoch $t$). Then for any flight $f$ with $t_{arr}(f) \le t$:
  $$x_{f, g}(\omega) = x_{f, g}(\omega')$$
  Decisions executed at or prior to epoch $t$ are measurable with respect to $\mathcal{F}_t$ and are strictly invariant to future realizations $\omega \setminus \mathcal{F}_t$.
- **Docked Aircraft Invariant:**
  If an aircraft $f$ has arrived and commenced boarding/deplaning at gate $g$ prior to epoch $t$:
  $$t_{arr}(f) < t \implies x_{f, g} = 1 \quad \text{is fixed and immutable}.$$

### 2.3 Mode B1: Full-Information Retrospective Recourse
- **Information Filtration:** $\mathcal{F}_{T_{max}}$.
- **Mathematical Nature:**
  $$x_{f, g} = \arg\min_{x} \sum_f \left( c_{reassign} \cdot |x_{f, g} - x_{f, g}^{plan}| + c_{overflow} \cdot x_{f, remote} \right) \quad \text{s.t. hard constraints under } \omega$$
  Because all $\delta_{arr}(f')$ and $\delta_{dep}(f')$ for all $f' \in \mathcal{F}$ are available simultaneously, the solver exploits future slack to optimize past or present gate reallocations. This mode is strictly non-deployable in operational reality.

### 2.4 Mode C: Perfect Foresight Oracle
- **Information Filtration:** $\mathcal{F}_{T_{max}}$ available at planning inception without nominal reassignment penalties:
  $$x_{f, g} = \arg\min_{x} \sum_f c_{overflow} \cdot x_{f, remote} \quad \text{s.t. hard constraints under } \omega$$
  Mode C establishes the theoretical unconstrained minimum cost achievable if the dispatcher possessed a crystal ball.
