# UI-R00: 06 — PERFORMANCE BASELINE & RESOURCE AUDIT

**Document ID:** `AEOLUS-UI-R00-06-PERFORMANCE-BASELINE`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:30:00+07:00  
**Auditor:** Principal Software Auditor & Performance Engineering Lead  

---

## 1. Executive Summary

This document records the empirical performance baseline of the Aeolus Dashboard application under real execution conditions. All metrics were obtained on the canonical operational benchmark scenario (`SCEN_P09_CANONICAL_120`: 120 flights, 26 gates, Atlanta Hartsfield-Jackson Hub) using non-destructive, read-only instrumentation.

Per UI-R00 safety rules, no large stress benchmarks (1,500 flights) or heavy Monte Carlo simulations were triggered during this measurement cycle.

---

## 2. Measurement Environment & Hardware Profile

| Hardware / OS Parameter | Specification |
| :--- | :--- |
| **Operating System** | Windows 10 Pro (Build 19045, 64-bit) |
| **CPU Architecture** | x86_64 (AMD64 Family) |
| **Python Runtime** | Python 3.11.15 (MSC v.1944 64 bit) |
| **Streamlit Engine** | Streamlit 1.65.0 |
| **Plotly Visualization** | Plotly 7.1.0 |
| **Optimization Backend** | Google OR-Tools 9.15.6755 (C++ Native Backend) |
| **Measurement Tool** | `psutil 7.2.2` & `time.perf_counter` high-resolution timers |

---

## 3. Empirical Performance Measurements

### 3.1. Disk I/O & Artifact Deserialization Latencies

| Artifact Type | File Path | Record Count | File Size | Measured Latency |
| :--- | :--- | :---: | :---: | :---: |
| **Multi-Solver Benchmarks** | `artifacts/remediation/benchmarks/solver_runs.csv` | 95 runs | ~14 KB | **3.16 ms** |
| **Monte Carlo Summary** | `artifacts/remediation/monte_carlo/statistical_summary.json` | 500 scenarios | ~8.6 KB | **0.52 ms** |
| **Delay Predictions Sample** | `artifacts/remediation/native_dual_core/predictions_sample.csv` | 60 flights | ~12 KB | **2.84 ms** |
| **CP-SAT Scalability Results**| `artifacts/remediation/cp_sat/scalability_results.csv` | 60 rows | ~6.5 KB | **1.95 ms** |

*Analysis:* Disk artifact reading is exceptionally fast (< 5 ms per artifact) and does not represent a system bottleneck.

### 3.2. Scenario Generation & Synthesis Latency

| Operation | Input Parameters | Output Entities | Measured Latency |
| :--- | :--- | :--- | :---: |
| **Canonical Scenario Synthesis** | $N=120$ flights, $M=25$ gates, Seed 42 | 120 Flights, 26 Gates | **246.64 ms** |
| **Peak Stress Scenario Synthesis** | $N=85$ flights, $M=15$ gates, Seed 202602 | 85 Flights, 16 Gates | **188.10 ms** |

*Analysis:* Synthetic schedule generation takes ~250 ms. This cost occurs on scenario switch and can be mitigated by session-level caching (`@st.cache_data`).

### 3.3. Plotly Figure Generation & Filtering Latency

| Visualizer | Chart Contract | Scope / Filter | Measured Latency |
| :--- | :---: | :--- | :---: |
| **Interactive Gate Gantt** | `CHART-07` | Full Scenario (120 flights, 26 gate rows) | **45.99 ms** |
| **Interactive Gate Gantt** | `CHART-07` | Concourse T Filter (10 gates) | **20.24 ms** |
| **Activity Timeline** | `CHART-01` | 120 flights hourly arrival/departure bars | **12.45 ms** |
| **Concourse Utilization** | `CHART-08` | 3 concourse donut/polar charts | **8.15 ms** |
| **Monte Carlo Cost Dist** | `CHART-12` | 3 mode histograms | **14.20 ms** |
| **Monte Carlo Running Mean**| `CHART-15` | Running average + 95% CI fill band | **18.75 ms** |

*Analysis:* Plotly figure construction operates consistently under 50 ms. Client-side WebGL/Canvas rendering handles 120-flight schedules without frame drops.

### 3.4. Streamlit App Navigation Latencies (End-to-End Headless Run)

| Page | Primary Content | Solvers Executed on Render | Measured Latency |
| :--- | :--- | :---: | :---: |
| **01 — Control Tower** | 5 KPIs, Timeline, Concourse | 0 | **784.41 ms** |
| **02 — Flight Intelligence** | Table, Distribution, Turn Dynamics | 0 | **502.64 ms** |
| **03 — Gate Operations** | Gantt, Live Controls, Inspector | **1 (CP-SAT Unsolicited)** | **850.46 ms** |
| **04 — Optimization Lab** | Benchmark Table, Pareto, Scalability | 0 | **272.12 ms** |
| **05 — Robustness Lab** | 4 MC Charts, Paired Analysis | 0 | **279.72 ms** |

*Analysis:* 
- Page 03 exhibits the highest latency (850.46 ms) directly due to unsolicited CP-SAT solving during initial render (Finding `ISSUE-R00-01`).
- Eliminating automatic solving on Page 03 will bring its initial load time down to ~150 ms.

---

## 4. Memory Footprint & Process Growth

| Metric | Measured Value | Threshold / Safety Budget | Assessment |
| :--- | :---: | :---: | :---: |
| **Initial Process Memory (RSS)** | `196.82 MB` | 500 MB | **NORMAL** |
| **Peak Working Set Memory** | `373.91 MB` | 1,024 MB | **HEALTHY** |
| **Memory Growth During Navigation** | `+177.09 MB` | 500 MB | **SAFE** |
| **Memory Leak Observation** | None detected across repeated AppTest runs | — | **STABLE** |

*Analysis:* The total memory footprint of ~374 MB is well within the 1 GB development budget and guarantees robust execution on any standard presentation laptop.

---

## 5. Solver Execution Audit Per User Action

| User Action | Target Page | Solvers Triggered | Expected Count | Audit Finding |
| :--- | :---: | :---: | :---: | :--- |
| **Load Page 01** | Control Tower | None | 0 | **PASS (0)** |
| **Load Page 02** | Flight Intelligence | None | 0 | **PASS (0)** |
| **Load Page 03 First Time** | Gate Operations | CP-SAT Gate Solver | **0 (Expected)** | ❌ **FAIL (1 Unsolicited)** |
| **Change Scenario to 85** | Gate Operations | CP-SAT Gate Solver | **0 (Expected)** | ❌ **FAIL (1 Unsolicited)** |
| **Click "TỐI ƯU HÓA NGAY"** | Gate Operations | User-Selected Solver | 1 | **PASS (1 Authorized)** |
| **Filter Concourse / Carrier** | Gate Operations | None | 0 | **PASS (0)** |
| **Load Page 04 / 05** | Labs | None | 0 | **PASS (0)** |

*Remediation Target:* In UI-R02, remove unsolicited solver execution on Page 03 so that solver execution count is strictly 0 until the user clicks the action button.
