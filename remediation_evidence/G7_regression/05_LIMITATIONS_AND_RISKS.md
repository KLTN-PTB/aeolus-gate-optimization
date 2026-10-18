# AEOLUS-G7 — Limitations, Edge Cases and Operational Risks

## 1. Technical & Methodological Limitations

1. **Dual-Core Departure Ground Truth Horizon**:
   - Outbound departure delay predictions are constrained by historical flight schedule reporting patterns in the BTS TranStats database. For turnaround rotations with scheduled turnaround < 45 minutes, turnaround buffer propagation dominates exogenous runway weather features.

2. **Copula Modeling Assumptions**:
   - The Monte Carlo engine P09/V2 relies on a calibrated Gaussian Copula with empirical correlation $\rho \in [0.40, 0.50]$ between inbound and outbound turnaround legs. While valid for nominal hub operations at ATL, extreme convective weather events exhibiting fat-tailed comonotonic breakdown may exceed the calibrated correlation structure.

3. **CP-SAT Timeout Dynamics under Complex Wave Peaks**:
   - On extreme scale stress instances ($N > 300$ flights, $M > 100$ gates), CP-SAT may encounter the 30-second time horizon without completing the branch-and-bound tree. In such cases, the status mapping correctly reflects `FEASIBLE` with `TIME_LIMIT`, but the gap to global optimality cannot be zero.

4. **Historical Intermediate Freeze Snapshot Obsoletion**:
   - As documented in `02_IMPLEMENTATION_REPORT.md`, tests asserting `system_freeze_manifest_v3.json` (Phase R22, September 2026) fail because research development legitimately expanded the domain model. A future clean freeze manifest (e.g. `system_freeze_manifest_final.json`) should formally baseline the remediated codebase upon release.

---

## 2. Risk Matrix & Mitigations

| Risk ID | Risk Description | Severity | Probability | Mitigation Implemented |
|:---|:---|:---:|:---:|:---|
| **RSK-01** | Silent fallback to synthetic pairing in production data pipeline | High | Low | Engine requires explicit `tail_number` verification; fails closed or tags `INFERRED_PAIR` with audit trail. |
| **RSK-02** | Hindsight information leakage in Monte Carlo recourse | High | Low | Mode B2 enforces event sweep chronology; future delays cannot alter past gate lockings. |
| **RSK-03** | Solver claiming mathematical optimum without CP-SAT proof | High | None | `map_solver_status_to_badge` enforces `is_optimal_proven` boolean flag. |
| **RSK-04** | Dashboard misrepresenting synthetic scenarios as authentic Aeolus records | Medium | None | Export adapters throw `ProvenanceMismatchError` upon claimed origin mismatch. |
| **RSK-05** | Numerical instability in Student-t quantile sampling | Medium | Low | Uniform quantiles clipped to $[10^{-4}, 1 - 10^{-4}]$ prior to inverse CDF transformation. |

---

## 3. Boundary Conditions & Non-Goals

- **Non-Goal**: Re-training legacy neural networks or changing frozen weights in `artifacts/models/`. Historical model checkpoints remain frozen as scientific artifacts.
- **Boundary**: Testing is performed under Python 3.11 AMD64 on Windows. POSIX container parity is verified via standard cross-platform path handling (`pathlib.Path`), forward slash serialization, and UTF-8 encoding.
