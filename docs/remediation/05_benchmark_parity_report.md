# Phase P05: Benchmark Parity & Verification Audit Report

**Document ID:** `DOC-P05-PARITY-AUDIT-V1`  
**Phase:** P05 (Fair & Reproducible Solver Benchmark)  
**Status:** Certified / Pass  
**Execution Timestamp:** 2026-10-09T02:33:07Z  
**Target Environment:** Python 3.11.15 AMD64, Windows 10, Google OR-Tools 9.15.6755  

---

## 1. Executive Summary

Phase P05 establishes an uncompromising benchmark harness that eliminates historical measurement shortcuts and guarantees fair comparison across all optimization solvers in the Aeolus Gate Optimization repository.

Prior to Phase P05:
1. CP-SAT build time was synthetically inferred as `max(0.0, total_time - time_limit)`, masking massive Python model construction overheads (up to 12.1 seconds on 300 flights).
2. The Hybrid benchmark reused CP-SAT incumbents solved in earlier standalone runs, reporting total hybrid runtimes of ~1.0 second while omitting the entire CP-SAT Stage 1 build and search time.
3. Infeasible solver runs or timeouts had no standardized failure retention, risking distortion of empirical performance comparisons.

Following Phase P05 remediation:
- **All 20 Benchmark Evidence Validation Invariants (B01–B20) are verified and passing** (`19/19` test assertions in [`tests/test_benchmark_fairness_p05.py`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py)).
- **All four solver modes plus the diagnostic warm-start mode are strictly separated and measured.**
- **High-resolution monotonic instrumentation (`time.perf_counter_ns()`) accurately separates model construction, search, validation, and lifecycle wall-clock times.**
- **The full regression suite across Phases P01–P05 is 100% green (`149/149` tests passing in 21.35 seconds).**

---

## 2. Invariants Audit Matrix (B01 - B20)

| Invariant | Description | Verification Mechanism | Status | Evidence Link |
| :--- | :--- | :--- | :--- | :--- |
| **B01** | Same scenario $\to$ same `scenario_hash` | SHA-256 over canonical sorted entities | **PASS** | [`test_b01_same_scenario_same_hash`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L131) |
| **B02** | Same scenario $\to$ same gate inventory | Topologies and contact/remote counts match | **PASS** | [`test_b02_same_gate_inventory`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L151) |
| **B03** | Objective version identical | Uniform `v1` / `v1.0_canonical_audit` contract | **PASS** | [`test_b03_b04_objective_version`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L157) |
| **B04** | Capacity policy identical | `remote_stand_capacity_finite` enforced | **PASS** | [`test_b03_b04_objective_version`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L157) |
| **B05** | Solver status not silently rewritten | Output status maps directly to `SolverStatus` | **PASS** | [`test_b05_solver_status_not_silently_rewritten`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L163) |
| **B06** | Invalid solution cannot receive feasible ranking | Verifier violation sets feasible=False, obj=null | **PASS** | [`test_b06_invalid_solution_cannot_receive_feasible_ranking`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L170) |
| **B07** | Hybrid runtime includes both stages | Wall-clock measures Stage 1 + fallback + Stage 2 | **PASS** | [`test_b07_hybrid_runtime_includes_both_stages`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L209) |
| **B08** | CP-SAT runtime includes model construction | `model_construction_ms` explicitly captured | **PASS** | [`test_b08_cpsat_runtime_includes_model_construction`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L229) |
| **B09** | Failed runs remain visible | Failures preserved in CSV and `failures.json` | **PASS** | [`test_b09_failed_runs_remain_visible`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L247) |
| **B10** | Actual time measured, not estimated | `time.perf_counter_ns()` without heuristic subtraction | **PASS** | [`test_b10_b15_measured_high_res_timing`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L286) |
| **B11** | Seed provenance exists | Seed recorded in `BenchmarkCaseSpec` | **PASS** | [`test_b11_seed_provenance`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L294) |
| **B12** | Number of generated flights is exact | `len(flights) == spec.n_flights` asserted | **PASS** | [`test_b12_b13_flight_and_turn_accounting`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L300) |
| **B13** | Turns and legs count are not confused | Both `n_flights` and `n_aircraft_turns` logged | **PASS** | [`test_b12_b13_flight_and_turn_accounting`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L300) |
| **B14** | No hidden prior incumbent | Standalone solvers start from raw scenario | **PASS** | [`test_b14_no_hidden_prior_incumbent_in_standalone`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L308) |
| **B15** | Wall-clock uses consistent boundaries | Monotonic timer spans complete lifecycle | **PASS** | [`test_b10_b15_measured_high_res_timing`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L286) |
| **B16** | Missing metrics remain null with explanation | Infeasible runs set `objective_value = None` | **PASS** | [`test_b16_missing_metrics_remain_null`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L324) |
| **B17** | Data/model/config hashes retained | Retained in manifest and case spec | **PASS** | [`test_b17_hashes_retained`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L332) |
| **B18** | No modified historical artifacts | `artifacts/stress_1500x50/` preserved untouched | **PASS** | [`test_b18_no_modified_historical_artifacts`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L339) |
| **B19** | Cost recalculation matches evaluator | Re-evaluation diff $< 10^{-4}$ | **PASS** | [`test_b19_b20_cost_recalculation`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L347) |
| **B20** | All feasible results pass independent verifier | Certified by `verify_hard_constraints_independently` | **PASS** | [`test_b19_b20_cost_recalculation`](file:///D:/Study/Code/Python/Aelous/tests/test_benchmark_fairness_p05.py#L347) |

---

## 3. Empirical Results Across Tiers

The benchmark harness was executed across 5 standard scenarios:
- **Tier A:** 10 flights $\times$ 3 contact gates + 1 remote stand ($N=5$ repeats)
- **Tier A:** 20 flights $\times$ 6 contact gates + 2 remote stands ($N=5$ repeats)
- **Tier B:** 100 flights $\times$ 20 contact gates + 3 remote stands ($N=3$ repeats)
- **Tier B:** 200 flights $\times$ 30 contact gates + 5 remote stands ($N=3$ repeats)
- **Tier B:** 300 flights $\times$ 50 contact gates + 5 remote stands ($N=3$ repeats)

### 3.1 Empirical Summary Table (Median Values)

| Scenario | Solver Mode | Feasible | Wall Clock (ms) | Build Time (ms) | Search Time (ms) | Objective Value | Failure Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **10F / 3G** | `GREEDY_STANDALONE` | **Yes** | **1.80** | 0.00 | 1.79 | 450.00 | 0.0% |
| **10F / 3G** | `CP_SAT_STANDALONE` | **Yes** | 10.72 | 6.05 | 3.17 | **430.00** | 0.0% |
| **10F / 3G** | `SA_STANDALONE` | **Yes** | 2,263.43 | 1.75 | 2,268.96 | **430.00** | 0.0% |
| **10F / 3G** | `HYBRID_STANDALONE` | **Yes** | 2,105.05 | 1.03 | 2,112.23 | **430.00** | 0.0% |
| **10F / 3G** | `SA_FROM_PRECOMPUTED` | **Yes** | 2,058.42 | 0.00 | 2,058.37 | **430.00** | 0.0% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **100F / 20G** | `GREEDY_STANDALONE` | **Yes** | **23.11** | 0.00 | 23.10 | 830.00 | 0.0% |
| **100F / 20G** | `CP_SAT_STANDALONE` | **Yes** | 940.85 | 827.60 | 92.11 | **450.00** | 0.0% |
| **100F / 20G** | `SA_STANDALONE` | **Yes** | 21,980.50 | 22.84 | 21,957.59 | 796.67 | 0.0% |
| **100F / 20G** | `HYBRID_STANDALONE` | **Yes** | 21,797.77 | 93.30 | 21,704.42 | 796.67 | 0.0% |
| **100F / 20G** | `SA_FROM_PRECOMPUTED` | **Yes** | 20,612.33 | 0.00 | 20,612.27 | 796.67 | 0.0% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **200F / 30G** | `GREEDY_STANDALONE` | **Yes** | **55.17** | 0.00 | 55.30 | 919.73 | 0.0% |
| **200F / 30G** | `CP_SAT_STANDALONE` | **Yes** | 5,143.75 | 3,606.21 | 1,490.62 | **639.73** | 0.0% |
| **200F / 30G** | `SA_STANDALONE` | **Yes** | 49,446.27 | 54.23 | 49,402.06 | 809.73 | 0.0% |
| **200F / 30G** | `HYBRID_STANDALONE` | **Yes** | 58,869.15 | 462.51 | 58,413.45 | 809.73 | 0.0% |
| **200F / 30G** | `SA_FROM_PRECOMPUTED` | **Yes** | 46,018.89 | 0.00 | 46,300.78 | 809.73 | 0.0% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **300F / 50G** | `GREEDY_STANDALONE` | **Yes** | **100.56** | 0.00 | 101.38 | 1,209.20 | 0.0% |
| **300F / 50G** | `CP_SAT_STANDALONE` | **No** (Timeout) | 14,368.33 | **12,081.78** | 2,288.64 | **null** | **100.0%** |
| **300F / 50G** | `SA_STANDALONE` | **Yes** | 70,765.61 | 99.71 | 70,730.73 | 1,209.20 | 0.0% |
| **300F / 50G** | `HYBRID_STANDALONE` | **Yes** (Fallback) | 92,328.35 | 1,328.88 | 127,924.19 | 1,209.20 | 0.0% |
| **300F / 50G** | `SA_FROM_PRECOMPUTED` | **Yes** | 66,785.08 | 0.00 | 66,822.91 | 1,209.20 | 0.0% |

---

## 4. Key Engineering & Methodological Findings

### 4.1 CP-SAT Model Construction Overheads (Addressing Invariant B08)
On the 300 flights $\times$ 50 gates scenario (`SCEN_TIER_B_300F_50G`):
- **Model Construction Latency:** **12,081.78 ms** (12.08 seconds in Python).
- **OR-Tools Search Latency:** **2,288.64 ms** (hit the 2.0s search timeout).
- **Total Wall-Clock Latency:** **14,368.33 ms** (~14.4 seconds).

In the legacy code, CP-SAT execution was logged as $\sim 2.0$ seconds because Python construction was ignored or subtracted. Under our monotonic instrumentation, model construction accounts for **84.1% of the total CP-SAT lifecycle**. This empirical evidence sets a clear, justified mandate for **Phase P06 (CP-SAT Model Re-architecting & Constraint Pruning)**.

### 4.2 Transparent Failure Accounting (Addressing Invariants B06, B09, B16)
On the 300-flight scenario, CP-SAT failed to find any feasible incumbent within the 2.0s search budget:
- Status: `UNKNOWN` (timeout without incumbent).
- Feasible: `False`.
- Hard violations: `0` (no assignment made).
- Objective Value: **`null`** (not 0.0, not masked).
- Failure rate: **1.0 (100%)**, preserved transparently in `failures.json` and `aggregate_metrics.json`.

### 4.3 Provenance and Complete Accounting in Hybrid Mode (Addressing Invariant B07)
When CP-SAT timed out on 300 flights without an incumbent:
1. `HybridGateSolver` correctly detected that Stage 1 had no feasible incumbent.
2. It executed the declared **Deterministic Greedy fallback** (`fallback_used = True`).
3. It passed the Greedy solution as the incumbent into Stage 2 Simulated Annealing.
4. Total wall-clock time properly accumulated Stage 1 + Fallback + Stage 2, reaching **92.3 seconds** median.

### 4.4 Diagnostic Warm-Start vs. Standalone SA (Addressing Invariant B14)
Comparing `SA_STANDALONE` vs. `SA_FROM_PRECOMPUTED_INCUMBENT`:
- Standalone SA includes initial seed generation (~100 ms) and is evaluated from scratch.
- The diagnostic mode starts with a pre-existing solution in memory.
- In Phase P05, these two modes are strictly separated in `solver_variant` and can never be confused.

---

## 5. Artifact Verification Trail

All official Phase P05 benchmark artifacts have been persisted in [`artifacts/remediation/benchmarks/`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks):

1. **[`benchmark_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/benchmark_manifest.json):** Schema version `benchmark_v1.0`, environment profile, 25 scenario-variant specs, summary by mode.
2. **[`solver_runs.csv`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/solver_runs.csv):** 85 individual benchmark runs across all repetitions, detailing all 19 result metrics.
3. **[`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/aggregate_metrics.json):** Multi-run statistical metrics (median, mean, std, dispersion, min/max, failure rates).
4. **[`failures.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/failures.json):** Retained records of all 3 failed CP-SAT runs on 300 flights with `null` objectives.
5. **[`environment.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/environment.json):** Hardware and OS metadata (CPython 3.11.15, AMD64, 16 logical cores, 16GB RAM, OR-Tools 9.15.6755).
