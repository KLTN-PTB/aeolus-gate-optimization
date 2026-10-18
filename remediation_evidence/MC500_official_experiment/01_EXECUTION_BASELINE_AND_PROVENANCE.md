# 01. EXECUTION BASELINE, RUN IDENTITY & SOURCE PROVENANCE

**Experiment Title:** Aeolus Monte Carlo Production Run ($N=500$ Stochastic Realizations)  
**Protocol:** AEOLUS-MC500-PRODUCTION  
**Run ID:** `mc500_20261012_173538_afa5db`  
**Execution Timestamp:** 2026-10-12T17:35:38Z đến 2026-10-12T17:39:02Z (Tổng thời gian: $203.68$ giây $\approx 3.4$ phút)  
**Output Directory:** `artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db`  
**Auditor:** Senior Scientific Computing Engineer, Operations Research Experiment Lead  

---

## 1. Môi Trường Thực Thi & Git Baseline

- **Repository:** `aeolus-gate-optimization`
- **Git Branch:** `remediation/g7-regression`
- **Git HEAD Commit:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Working Tree Patch Snapshot:** [`working_tree_pre_n500.patch`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/MC500_official_experiment/working_tree_pre_n500.patch)
- **Runtime Environment:**
  - Python: 3.11.15 (CPython 64-bit Windows)
  - OR-Tools (CP-SAT Solver): 9.9.3963
  - NumPy: 1.26.4
  - SciPy: 1.13.1
  - Pandas: 2.2.2
  - Pytest: 9.1.1

---

## 2. Bảng Băm Toàn Diện Của Mã Nguồn & Module Trọng Yếu (SHA-256 Hashes)

Tất cả các tệp mã nguồn tham gia vào quá trình sinh kịch bản ngẫu nhiên và giải bài toán tối ưu đều được đóng băng và tính mã băm SHA-256 trực tiếp:

| Thành phần Module | Đường dẫn tệp | SHA-256 Checksum (Full 64-hex) | Khớp Manifest MC500-Topology |
| :--- | :--- | :--- | :---: |
| **Production Runner** | [`scripts/run_g2_monte_carlo_remediation.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_g2_monte_carlo_remediation.py) | `c1ca2bdeb0d87d49e1cda52c407e1c5bf36012b5b0c710f4cd55405880a4a324` | **PASS (100%)** |
| **Simulation Engine** | [`src/simulation/monte_carlo_engine_v2.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/monte_carlo_engine_v2.py) | `49a78ecbac8313240c54713d7c30e11da9ce1b15243a959e6c314ee045208cf4` | **PASS (100%)** |
| **Topology & Scenario**| [`src/simulation/scalability_scenario.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_scenario.py) | `4654a04adca65596e00fad0c4065a2bacb47f5b22f5d36ced6d5a3b8c55138c0` | **PASS (100%)** |
| **Copula Generator** | [`src/simulation/monte_carlo_engine_p09.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/monte_carlo_engine_p09.py) | `655848601f3c4d17eb78b947cc5ebb42bbbce5f4bea513a45258199d3499026d` | **PASS (100%)** |
| **Optimization Domain**| [`src/optimization/domain.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py) | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | **PASS (100%)** |
| **Optimization Config**| [`src/optimization/config.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/config.py) | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | **PASS (100%)** |
| **CP-SAT Solver** | [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py) | `88c668895b215841e163638083b035abacc68027b0bc7fe70515a38711c7bad0` | **PASS (100%)** |
| **Greedy Solver** | [`src/optimization/solvers/greedy_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py) | `db750e91a6ecca0692548018d4e4e18a47c73198fcf73dede2824c8533837abc` | **PASS (100%)** |
| **Hybrid Solver** | [`src/optimization/solvers/hybrid_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/hybrid_solver.py) | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | **PASS (100%)** |
| **SA Annealer** | [`src/optimization/sa/annealer.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py) | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | **PASS (100%)** |
| **Gate Evaluator** | [`src/optimization/evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py) | `62de5417c576225b2d98e38e2df008653112a6ad360da49543874387fc9db8f1` | **PASS (100%)** |
| **Topology Inventory** | [`gate_inventory.json`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/MC500_topology_verification/GATE_INVENTORY.json) | `362728e8b70ab6258de9b6486588cfecf279dc5242f7fd2dd8674f20107421ab` | **PASS (100%)** |

Ba mã băm nguồn chủ chốt (`scalability_scenario.py`, `run_g2_monte_carlo_remediation.py`, `monte_carlo_engine_v2.py`) và mã băm `gate_inventory.json` khớp hoàn toàn 100% với phiên bản đã nghiệm thu tại giai đoạn MC500-TOPOLOGY-GATE.

---

## 3. Khẳng Định Kiểm Tra Trước Thực Thi (Pre-Execution Test Assertions)

Trước khi kích hoạt lệnh chạy chính thức $N=500$, toàn bộ bộ kiểm tra hồi quy liên quan gồm 13 test suite đã được thực thi độc lập:
- Số bài kiểm tra: **231 tests**
- Kết quả: **231 PASSED, 0 FAILED, 0 SKIPPED** (thời gian $39.36$ giây)
- Log kiểm tra preflight: [`preflight_pytest_log.txt`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/MC500_official_experiment/preflight_pytest_log.txt)
- Thoát mã: `0` (Clean Baseline).
