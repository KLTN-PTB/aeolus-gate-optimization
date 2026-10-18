# AEOLUS-G2 — DELIVERABLE 03: TEST RESULTS REPORT

## 1. Test Suite Summary

- **Total Test Cases Executed:** 42
- **Passed:** 42 (100%)
- **Failed:** 0 (0%)
- **Execution Runtime:** 1.31 seconds
- **Test Runner:** `pytest 9.1.1` on Python 3.11.15 AMD64
- **Test Modules:**
  - `tests/test_g2_monte_carlo_causality.py` (14 tests)
  - `tests/test_monte_carlo_robustness_p09.py` (28 regression tests)

## 2. G2 Causality & Scientific Verification Breakdown

| Test Identifier | Specification Description | Outcome | Execution Details |
| :--- | :--- | :--- | :--- |
| `test_mc_causal_01` | Same history, diverging future $\rightarrow$ identical current action | **PASS** | Evaluated two scenarios with identical delays $\le 250$ min and divergent future delays ($+300$ min). Verified actions executed $\le 250$ min were identical. |
| `test_mc_causal_02` | Future delay mutation does not alter past decisions | **PASS** | Mutated downstream flight F4 (+300 min). Asserted gate assignments and traces for morning flights F1 and F2 remained 100% bit-exact identical. |
| `test_mc_causal_03` | Observed past event permitted to change future action | **PASS** | Flight F1 delayed departure into flight F2's arrival window. Verified online recourse causally reallocated F2 to an open contact gate. |
| `test_mc_causal_04_and_05` | Cannot move or alter gate of already docked flight | **PASS** | Flight F1 docked at gate G1 at $t=100$. Verified downstream arrival of conflicting flight F2 reallocated F2 without altering docked flight F1. |
| `test_mc_causal_06` | Timezone / midnight crossover handled monotonically | **PASS** | Simulated flights crossing midnight ($t \in [1400, 1540]$ min). Confirmed sequential chronology without numerical underflow or modulo wrapping. |
| `test_mc_causal_07` | Missing decision timestamp handled fail-closed | **PASS** | Injected `NaN` arrival timestamp into flight entity. Verified `ValueError` raised immediately, preventing silent corruption. |
| `test_mc_causal_08` | Decision trace contains decision epoch and rationale | **PASS** | Audited trace logs for presence of `decision_epoch_min`, `flight_id`, `previous_gate`, `reassigned_gate`, and `reason`. |
| `test_mc_causal_09` | Deterministic replay from identical state and seed | **PASS** | Replayed realization twice. Verified bit-exact equality of objective costs, reassignment counts, and realization hashes. |
| `test_feas_01` | Decomposition separates physical conflict from static consistency | **PASS** | Delay created zero contact overlaps. Verified `static_slot_consistency == False`, `physical_conflict == 0`, and `composite_feasible == True`. |
| `test_feas_02` | Physical collision causes composite infeasibility | **PASS** | Severe departure delay caused contact collision. Verified `physical_conflict > 0` and `composite_feasible == False`. |
| `test_mode_01` | Mode B1 explicitly recorded as retrospective regime | **PASS** | Asserted `information_regime == "RETROSPECTIVE"` and `recourse_policy == "FULL_INFORMATION_RETROSPECTIVE"`. |
| `test_mode_02` | Mode B2 explicitly recorded as online recourse regime | **PASS** | Asserted `information_regime == "ONLINE_RECOURSE"` and `recourse_policy == "ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN"`. |
| `test_mode_03` | Mode C1 labeled heuristic baseline vs Mode C2 proven optimal | **PASS** | Verified Mode C1 (Greedy) sets `is_optimal_proven == False` while Mode C2 (CP-SAT) sets `is_optimal_proven == True`. |
| `test_stat_01` | CRN paired comparison accurately computes deltas and proportions | **PASS** | Verified paired delta mean, standard error, confidence interval, and improved/worsened/tied counts on synthetic vectors. |

## 3. Legacy Regression Test Suite (`test_monte_carlo_robustness_p09.py`)

All 28 regression tests covering MC01 through MC28 continue to pass without error or modification:
- `test_mc01_requested_scenarios_count` through `test_mc05_perfect_foresight_oracle_labeling`: **PASS**
- `test_mc06_no_future_leakage_in_reactive_mode` through `test_mc10_planned_vs_realized_feasibility_separated`: **PASS**
- `test_mc11_monte_carlo_standard_error_formula` through `test_mc14_zero_cost_baseline_handled`: **PASS**
- `test_mc15_distribution_sampling_finite` through `test_mc19_random_seed_reproducibility`: **PASS**
- `test_mc20_failed_scenario_retention` through `test_mc24_simulation_mode_enum_explicit`: **PASS**
- `test_mc25_infeasible_when_conflicts_exist` through `test_mc28_summary_statistics_match_raw_evaluations`: **PASS**

## 4. Test Execution Reproducibility Stamp

```bash
$ pytest tests/test_g2_monte_carlo_causality.py tests/test_monte_carlo_robustness_p09.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
collected 42 items
tests/test_g2_monte_carlo_causality.py .............. [ 33%]
tests/test_monte_carlo_robustness_p09.py ............................ [100%]
============================= 42 passed in 1.31s ==============================
```
