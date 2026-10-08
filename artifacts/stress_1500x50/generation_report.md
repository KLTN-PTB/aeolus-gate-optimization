# Aeolus Scalability Scenario Generation Report (Phase 1)
**Protocol**: Stress-Testing Solver Scalability at Scale (1500 Inbound Flights x 50 Gates)  
**Branch**: `development/scalability-1500x50`  
**Git HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Generated At (UTC)**: `2026-10-05 03:27:48`  
**Status**: Certified Complete  

---

## 1. Executive Summary

This engineering document certifies the successful design, implementation, and serialization of the synthetic scalability scenario (**1500 inbound flights x 50 gates**) and its nested scaling ladder (**250, 500, 750, 1000, 1250, 1500 flights**) on branch `development/scalability-1500x50`.

This experiment is strictly an **engineering and solver scalability benchmark**. It evaluates the combinatorial tractability and algorithmic degradation of CP-SAT, Deterministic Greedy, and Simulated Annealing solvers under heavy gate pressure. It is **NOT** an ML study, **NOT** an operational holdout evaluation, and **NOT** a reconstruction of physical ATL airfield operations.

---

## 2. Scientific & Safety Contract Compliance

| Requirement | Implementation State | Verification Method |
|---|---|---|
| **Frozen Scientific Baseline** | Checkpoint SHA256 preserved (`e7e746...`) | Read-only; zero model retraining |
| **Data Partition Boundary** | 2023 July development data (`year=2023`) | `assert_data_access_allowed`, zero 2024 access |
| **Leakage Isolation** | `ARR_DELAY`, `DEP_DELAY`, `DEP_TIME` stripped | `validate_downstream_input_boundary` passed |
| **Flight Population** | 100% Inbound flights (`DEST == 'ATL'`) | Asserted `(DEST == 'ATL').all()` |
| **No Real Rotations / Chains** | Independent synthetic turns synthesized | `AircraftTurnModel` canonical synthesis |
| **No Weather / No MARS / No Towing** | Excluded completely | Feature contract verified |
| **Gate Domain Geometry** | 50 Contact Gates + 1 Overflow Remote Apron | `build_scenario_gates(50)` |

---

## 3. Traffic Distribution & Diurnal Profile

The 1500 flights were sampled from the July 2023 inbound ATL partition (29,328 eligible flights) using `numpy.random.default_rng(202601)`.

### Carrier Distribution (Primary 1500 Scenario)
| Carrier | Flight Count | Proportion |
|---|---|---|
| `DL` | 1012 | 67.47% |
| `WN` | 167 | 11.13% |
| `9E` | 100 | 6.67% |
| `NK` | 46 | 3.07% |
| `F9` | 40 | 2.67% |
| `AA` | 39 | 2.60% |
| `UA` | 36 | 2.40% |
| `OO` | 31 | 2.07% |

### Aircraft Turn Synthesis Mechanics
Each synthetic flight follows the certified Aeolus `AircraftTurnModel`:
- **Turnaround Minimum**: $T_{turn} = 45$ minutes
- **Scheduled Dwell**: $D_{sched} = A_{sched} + 60$ minutes
- **Separation Buffer**: $B_{buffer} = 15$ minutes
- **Nominal Occupancy Window**: $A_{sim} \to A_{sim} + 75$ minutes (mean occupancy = 75.0 min).
- **Nominal Gate Assignment**: Round-robin across contact gates $G_{01} \dots G_{50}$.

---

## 4. Scaling Ladder & Occupancy Stress Analysis

The scaling ladder is strictly **nested**: smaller rungs ($N \in \{250, 500, 750, 1000, 1250\}$) are deterministic subsets of the primary 1500-flight scenario, sliced *prior* to sorting to preserve the complete 24-hour diurnal curve across all rungs.

| Flights ($N$) | Contact Gates | Peak Demand | Over-Capacity | Capacity Ratio | Flights / Gate | Nominal Utilization | Scenario Hash Prefix |
|---|---|---|---|---|---|---|---|
| 250 | 50 | 37 | 0 | 0.74 | 5.0 | 26.0% | `dc9a846716bc...` |
| 500 | 50 | 71 | 21 | 1.42 | 10.0 | 52.1% | `ce855ddec364...` |
| 750 | 50 | 102 | 52 | 2.04 | 15.0 | 78.1% | `aabcdf3c68d7...` |
| 1000 | 50 | 129 | 79 | 2.58 | 20.0 | 104.2% | `9329d6381b7a...` |
| 1250 | 50 | 158 | 108 | 3.16 | 25.0 | 130.2% | `734c64851183...` |
| 1500 | 50 | 186 | 136 | 3.72 | 30.0 | 156.2% | `112f4c824449...` |

### Key Structural Observations:
1. **$N=250$ (Under-Capacity Baseline)**: Peak demand reaches 37 flights, well within the 50 contact gates. Over-capacity is 0. All flights can be accommodated on contact gates without remote apron overflow.
2. **$N=500$ (Onset of Congestion)**: Peak demand reaches 71 flights, requiring 21 simultaneous remote apron overflows during peak bank hours.
3. **$N=1000$ (Capacity Parity)**: Aggregate daily demand reaches 104.2% of total contact gate capacity (72,000 gate-minutes capacity vs 75,000 min demand), creating structural saturation.
4. **$N=1500$ (Extreme Stress Horizon)**: Peak demand reaches 186 flights (3.72x contact gate count). Total daily demand is 112,500 gate-minutes (156.3% of 50-gate capacity), forcing extensive remote apron routing and stressing solver conflict-resolution mechanisms.

---

## 5. Artifact Directory Inventory

The following files are published in `artifacts/stress_1500x50/`:
- `input_manifest.json`: Lineage, source dataset, seed, git commit, safety contract.
- `scenario_metadata.json`: Primary 1500x50 scenario metadata and carrier distributions.
- `gate_inventory.json`: 50 contact gates (`G_01` to `G_50`) + 1 overflow stand (`REMOTE_APRON_01`).
- `scenario_summary.json`: Ladder metrics across all 6 rungs.
- `scenario_1500x50.parquet`: Certified leakage-safe serialized flights dataset.
- `generation_report.md`: This comprehensive engineering document.

---
**Aeolus Research Software**  
*Certified with Limitations — Clean Baseline Frozen*
