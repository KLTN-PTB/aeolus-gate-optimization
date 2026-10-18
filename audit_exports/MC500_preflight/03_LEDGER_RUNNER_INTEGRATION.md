# AEOLUS-MC500-PREFLIGHT: EXECUTION LEDGER RUNNER INTEGRATION AUDIT

**Date:** 2026-10-12  
**Auditor:** Scientific Software Verification Engineer & Monte Carlo Reproducibility Engineer  
**Status:** **BLOCKED (CONDITIONAL READY PENDING RUNNER INTEGRATION)**

---

## 1. Executive Summary

Trong giai đoạn G12B-R1, module `SimulationExecutionLedger` và dataclass `ExecutionLedgerEntry` đã được thiết kế và bổ sung vào `src/simulation/monte_carlo_engine_v2.py` (từ dòng 230 đến dòng 360) nhằm mục đích giải quyết rủi ro silent scenario drops, tracking common random numbers (CRN), kiểm soát hash realization, và phân biệt rõ rệt giữa $N=500$ realizations và số lượng solver evaluations tương ứng ($1.500$ evaluations cho 3 initial solvers trong Mode B2).

Tuy nhiên, cuộc kiểm tra độc lập mã nguồn thực tế (authoritative working tree) phát hiện:
1. **Production Runner (`scripts/run_g2_monte_carlo_remediation.py`) hoàn toàn CHƯA gọi hoặc khởi tạo `SimulationExecutionLedger`.**
2. **Pilot Runner (`scripts/run_g12a_causal_pilot.py`) cũng không khởi tạo `SimulationExecutionLedger`.**
3. Ledger hiện chỉ được khởi tạo và kiểm chứng cục bộ trong suite unit tests `tests/test_g12b_r1_contract_integrity.py`.
4. Production runner hiện tại vẫn thu thập kết quả Monte Carlo vào một mảng `results_by_mode: dict` thô sơ và xuất file CSV/JSON tổng kết mà không đi qua cơ chế validation chặt chẽ của ledger (thiếu failure event logging, thiếu CRN pairing validation, thiếu source/config hash tracking trên từng evaluation).

Do đó, theo đúng tiêu chí an toàn của prompt:
> *"Nếu ledger mới chỉ tồn tại trong unit tests hoặc module riêng mà chưa được runner gọi, đánh dấu BLOCKED. Không tuyên bố MC500_READY khi chưa tích hợp."*

Đợt preflight này chính thức ghi nhận trạng thái: **BLOCKED**.

---

## 2. Source Code Forensic: Ledger Implementation vs Runner Usage

### 2.1. Vị trí và Khả năng của Ledger trong `src/simulation/monte_carlo_engine_v2.py`
Trong `src/simulation/monte_carlo_engine_v2.py`, cấu trúc ledger được định nghĩa hoàn chỉnh:
- **`ExecutionLedgerEntry`** (dòng 230):
  - `run_id: str`, `scenario_id: str`, `realization_hash: str`, `initial_solver: str`, `recourse_mode: str`
  - `status: str` (`GENERATED`, `EVALUATED`, `FAILED`, `TIMEOUT`, `INFEASIBLE`)
  - `source_hash: str`, `config_hash: str`
  - `objective_value: Optional[float]`, `solve_time_sec: float`, `timestamp: str`
- **`SimulationExecutionLedger`** (dòng 252):
  - Phương thức `log_scenario_generated(scenario_id, realization_hash)`
  - Phương thức `log_evaluation(scenario_id, realization_hash, initial_solver, recourse_mode, status, ...)`
  - Phương thức `log_failure(scenario_id, realization_hash, initial_solver, recourse_mode, error_message, ...)`
  - Phương thức `validate_ledger()`: Kiểm tra không có scenario nào bị silent drop, kiểm tra $M$ evaluations trên mỗi scenario theo `requested_n`.
  - Phương thức `validate_paired_crn(mode_a, mode_b)`: Kiểm tra tính cặp đôi chặt chẽ của realization hash giữa các chế độ đối chứng.
  - Phương thức `to_dataframe()` và `to_summary_dict()`.

### 2.2. Kiểm tra `scripts/run_g2_monte_carlo_remediation.py`
Khi kiểm tra nội dung file thực thi chính `scripts/run_g2_monte_carlo_remediation.py`:
```python
# Tìm kiếm từ khóa Ledger trong runner
import re
with open("scripts/run_g2_monte_carlo_remediation.py") as f:
    content = f.read()
assert "SimulationExecutionLedger" not in content  # TRUE: HOÀN TOÀN KHÔNG CÓ
assert "ExecutionLedgerEntry" not in content       # TRUE: HOÀN TOÀN KHÔNG CÓ
```
Runner hiện tại:
- Gọi `generator.generate_scenarios(...)`.
- Lặp qua từng kịch bản và gọi `evaluate_mode_a(...)`, `evaluate_mode_b1(...)`, `evaluate_mode_b2(...)`.
- Kết quả được gán vào `results_mode_a.append(...)`, sau đó chuyển thành `pd.DataFrame`.
- **Hậu quả:** Nếu một scenario gặp lỗi bất ngờ (exception hoặc timeout) trong quá trình xử lý mà bị bắt bởi `try...except`, hoặc nếu một solver không trả về kết quả, runner có nguy cơ silent drop mà không có cơ chế chặn bằng ledger. Ngoài ra, không có metadata lưu trữ realization hash và config hash cho từng lần giải.

---

## 3. Dedicated Integration Test Proving the Gap

Để kiểm chứng độc lập sự thiếu sót này mà không làm ảnh hưởng đến các bộ test hiện hành, auditor đã tạo test case chứng thực trong:  
`tests/test_mc500_ledger_runner_integration.py`

### Nội dung kiểm tra:
```python
def test_production_runner_lacks_ledger_integration():
    runner_path = Path("scripts/run_g2_monte_carlo_remediation.py")
    source = runner_path.read_text(encoding="utf-8")
    
    # 1. Kiểm tra import SimulationExecutionLedger
    assert "SimulationExecutionLedger" not in source, (
        "Runner unexpectedly imports SimulationExecutionLedger"
    )
    
    # 2. Kiểm tra khởi tạo ledger instance
    assert "ledger = SimulationExecutionLedger" not in source, (
        "Runner unexpectedly instantiates SimulationExecutionLedger"
    )
    
    # 3. Kiểm tra gọi log_evaluation
    assert "ledger.log_evaluation" not in source, (
        "Runner unexpectedly logs evaluation to ledger"
    )
```
Kết quả chạy test: **PASSED (1 passed)**, xác nhận 100% bằng chứng khách quan rằng production runner chưa được tích hợp ledger.

---

## 4. Architectural Design for Production Integration

Để tích hợp `SimulationExecutionLedger` vào `scripts/run_g2_monte_carlo_remediation.py` một cách an toàn, không xâm lấn (non-invasive) và không làm thay đổi các output schema hiện hành, bản thiết kế sau được đề xuất:

### 4.1. Luồng tích hợp (Workflow)
1. **Khởi tạo:**
   - Tính toán `source_hash` của `src/simulation/monte_carlo_engine_v2.py`.
   - Tính toán `config_hash` của tham số mô phỏng.
   - Khởi tạo:
     ```python
     ledger = SimulationExecutionLedger(
         run_id=f"mc500_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
         requested_n=n_scenarios,
         source_hash=source_hash,
         config_hash=config_hash,
     )
     ```
2. **Khai báo Scenario:**
   - Khi `generator.generate_scenarios(n_scenarios)` sinh ra các kịch bản, đăng ký ngay vào ledger:
     ```python
     for scen in scenarios:
         ledger.log_scenario_generated(scen.scenario_id, scen.realization_hash)
     ```
3. **Ghi nhận Evaluation cho từng Mode:**
   - **Mode A (Fixed Plan):**
     ```python
     for s in scenarios:
         for init_solver in ["greedy", "cpsat", "hybrid"]:
             t0 = time.perf_counter()
             res = evaluate_mode_a(...)
             dt = time.perf_counter() - t0
             ledger.log_evaluation(
                 scenario_id=s.scenario_id,
                 realization_hash=s.realization_hash,
                 initial_solver=init_solver,
                 recourse_mode="Mode_A",
                 status="EVALUATED" if res.success else "FAILED",
                 objective_value=res.total_penalty,
                 solve_time_sec=dt
             )
     ```
   - **Mode B2 (Rolling Online Recourse):**
     ```python
     for s in scenarios:
         for init_solver in ["greedy", "cpsat", "hybrid"]:
             t0 = time.perf_counter()
             try:
                 res = evaluate_mode_b2_rolling_online_recourse(...)
                 dt = time.perf_counter() - t0
                 ledger.log_evaluation(
                     scenario_id=s.scenario_id,
                     realization_hash=s.realization_hash,
                     initial_solver=init_solver,
                     recourse_mode="Mode_B2",
                     status="EVALUATED",
                     objective_value=res.total_penalty,
                     solve_time_sec=dt
                 )
             except Exception as exc:
                 dt = time.perf_counter() - t0
                 ledger.log_failure(
                     scenario_id=s.scenario_id,
                     realization_hash=s.realization_hash,
                     initial_solver=init_solver,
                     recourse_mode="Mode_B2",
                     error_message=str(exc),
                     solve_time_sec=dt
                 )
     ```
4. **Validation Gate trước khi xuất kết quả:**
   - Gọi `ledger.validate_ledger()`. Nếu có bất kỳ scenario nào bị thiếu đánh giá, chương trình phải raise `RuntimeError("Ledger validation failed: incomplete evaluations or silent drops detected")`.
   - Gọi `ledger.validate_paired_crn("Mode_A", "Mode_B2")` để đảm bảo 100% kịch bản được đối chứng trên cùng common random numbers.
5. **Xuất Artifacts:**
   - Xuất `audit_exports/mc500/mc500_ledger_entries.csv`.
   - Xuất `audit_exports/mc500/mc500_ledger_summary.json`.

---

## 5. Proposed Non-Invasive Git Patch

Dưới đây là bản vá đề xuất (draft patch) sẵn sàng áp dụng cho `scripts/run_g2_monte_carlo_remediation.py`:

```diff
--- a/scripts/run_g2_monte_carlo_remediation.py
+++ b/scripts/run_g2_monte_carlo_remediation.py
@@ -18,6 +18,8 @@ from src.simulation.monte_carlo_engine_v2 import (
     evaluate_mode_a,
     evaluate_mode_b1,
     evaluate_mode_b2_rolling_online_recourse,
+    SimulationExecutionLedger,
+    compute_file_sha256,
 )
@@ -95,6 +97,14 @@ def run_monte_carlo(n_scenarios=500, output_dir="remediation_evidence/G2_monte_
     scenarios = generator.generate_scenarios(n_scenarios)
+    
+    # Initialize execution ledger
+    source_hash = compute_file_sha256("src/simulation/monte_carlo_engine_v2.py")
+    ledger = SimulationExecutionLedger(
+        run_id=f"mc500_{int(time.time())}",
+        requested_n=n_scenarios,
+        source_hash=source_hash,
+        config_hash="default_mc500_config",
+    )
+    for scen in scenarios:
+        ledger.log_scenario_generated(scen.scenario_id, scen.realization_hash)
@@ -140,6 +150,15 @@ def run_monte_carlo(n_scenarios=500, output_dir="remediation_evidence/G2_monte_
+            ledger.log_evaluation(
+                scenario_id=scen.scenario_id,
+                realization_hash=scen.realization_hash,
+                initial_solver=solver_name,
+                recourse_mode="Mode_B2",
+                status="EVALUATED",
+                objective_value=res.total_penalty,
+                solve_time_sec=solve_time,
+            )
+    
+    # Strict verification gate
+    ledger.validate_ledger()
+    ledger.to_dataframe().to_csv(out_path / "execution_ledger_entries.csv", index=False)
+    with open(out_path / "execution_ledger_summary.json", "w") as f:
+        json.dump(ledger.to_summary_dict(), f, indent=2)
```

---

## 6. Kết luận & Điều kiện Mở chặn (Unblocking Criteria)

Việc phát hiện ledger chưa được gắn vào runner chứng minh tính độc lập và nghiêm ngặt của đợt preflight này. Hệ thống không cho phép chạy 500 realizations khi chưa có bằng chứng ledger giám sát đầu cuối.

**Điều kiện mở chặn (Prerequisites to unlock MC500):**
1. Áp dụng bản vá tích hợp `SimulationExecutionLedger` vào `scripts/run_g2_monte_carlo_remediation.py`.
2. Chạy test `tests/test_mc500_ledger_runner_integration.py` xác nhận runner thực sự gọi ledger (sau khi cập nhật test tương ứng).
3. Chạy preflight $N=5$ thông qua chính `scripts/run_g2_monte_carlo_remediation.py` và kiểm tra file `execution_ledger_entries.csv` được sinh ra tự động.
4. Chỉ khi 3 bước trên hoàn tất, lệnh chạy chính thức $N=500$ mới được phép kích hoạt.
