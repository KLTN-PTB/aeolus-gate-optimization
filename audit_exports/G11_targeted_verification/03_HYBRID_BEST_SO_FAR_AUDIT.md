# AEOLUS-G11 — DELIVERABLE 03: HYBRID SOLVER BEST-SO-FAR INVARIANT & G10 CLAIM AUDIT

---

**Audit Gate:** `AEOLUS-G11` — Targeted Causality, Hybrid Invariant & Snapshot Verification  
**Date of Audit:** 2026-10-12  
**Auditor Role:** Independent Scientific Software Verification Engineer  
**Audit Target:** `src/optimization/solvers/hybrid_solver.py` & `src/optimization/sa/annealer.py`  
**Classification:** CODE INSPECTION & INVARIANT INTEGRITY AUDIT  

---

## 1. MỤC TIÊU VÀ TUYÊN BỐ CẦN THẨM ĐỊNH TỪ G10

Trong báo cáo G10 (`audit_exports/G10_independent_verification/05_G5_HYBRID_DISCREPANCY.md`), kiểm toán viên tiền nhiệm đã giải thích hiện tượng thuật toán Hybrid đạt chi phí $710.1333$ (kém hơn CP-SAT $660.1333$) tại kịch bản $N=200$ bằng tuyên bố sau:

> **Trích dẫn dòng 56 Báo cáo G10:**  
> *"Nhờ cơ chế bảo toàn tính đơn điệu (Monotonicity Protection tại dòng 280: $\text{best\_cost} = \min(\text{initial\_cost}, \text{sa\_cost})$), Hybrid trả về chính nghiệm $710.1333$."*

> **Trích dẫn dòng 80 Báo cáo G10:**  
> *"KHÔNG CÓ LỖI ĐƠN ĐIỆU (No Monotonicity Bug): Hybrid không bao giờ làm suy giảm chất lượng nghiệm mà Stage 1 bàn giao cho nó. Nghiệm cuối cùng luôn thỏa mãn $\mathcal{Z}_{\text{final}} \le \mathcal{Z}_{\text{initial}}$."*

Nhiệm vụ của đợt kiểm toán G11 là đối chiếu trực tiếp mã nguồn thực tế tại `hybrid_solver.py` để xác minh xem logic $\text{best\_cost} = \min(\dots)$ có thực sự tồn tại tại dòng 280 hay không, và cơ chế bảo toàn tính đơn điệu thực sự nằm ở đâu.

---

## 2. ĐỐI CHẤU TRỰC TIẾP MÃ NGUỒN `src/optimization/solvers/hybrid_solver.py`

### 2.1. Kiểm tra Dòng 280 và Khu vực Lân cận

Trích xuất nguyên văn mã nguồn thực tế từ dòng 273 đến dòng 293 của `src/optimization/solvers/hybrid_solver.py`:

```python
# File: src/optimization/solvers/hybrid_solver.py (Lines 273-293)
273:         # Step 8: Validate final assignment independently
274:         final_diag = verify_hard_constraints_independently(
275:             flights=flights,
276:             gates=gate_list,
277:             assignments=sa_result.assignments,
278:         )
279:         final_feasible = bool(final_diag.is_valid and len(sa_result.assignments) == len(flights))
280: 
281:         total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0
282: 
283:         # Step 9: Compute objective independently
284:         final_eval = evaluate_gate_assignment(
285:             assignments=sa_result.assignments,
286:             flights=flights,
287:             gates=gate_list,
288:             config=self.config,
289:             runtime_ms=total_wall_clock_ms,
290:             solver_status="FEASIBLE" if final_feasible else "INFEASIBLE",
291:             solver_name="HybridCPSatSA",
292:         )
```

Và tại dòng 337–345 khi trả về kết quả cuối cùng:
```python
# File: src/optimization/solvers/hybrid_solver.py (Lines 337-345)
337:         return OptimizationResult(
338:             status=hybrid_status,
339:             objective_value=final_eval.objective_value,
340:             objective_breakdown=final_eval.objective_breakdown,
341:             feasible=final_feasible,
342:             runtime_ms=total_wall_clock_ms,
343:             optimality_gap=opt_gap,
344:             assignments=dict(sa_result.assignments),  # <--- TRẢ VỀ TRỰC TIẾP NGHIỆM SA
345:             constraint_diagnostics=final_diag,
...
```

### 2.2. Kết luận Kiểm tra Mã Nguồn Cấp Thấp
1. **Dòng 280 thực tế là một dòng trống (blank line)**.
2. Dòng 281 là câu lệnh đo thời gian: `total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0`.
3. Trong toàn bộ tệp `hybrid_solver.py`, **HOÀN TOÀN KHÔNG CÓ BẤT KỲ DÒNG NÀO** chứa biểu thức `best_cost = min(initial_cost, sa_cost)`.
4. Không có câu lệnh điều kiện nào kiểm tra `if final_eval.objective_value > initial_cost:` để quay lui về nghiệm khởi đầu `incumbent_assignments`.
5. Tuyên bố của Báo cáo G10 về dòng 280 là **SAI SỰ THẬT / BỊA ĐẶT NỘI DUNG MÃ NGUỒN (FABRICATED CODE AUDIT CLAIM)**.

---

## 3. CƠ CHẾ BẢO TOÀN ĐƠN ĐIỆU NỘI TẠI TRONG `SimulatedAnnealingGateSolver`

Nếu `hybrid_solver.py` không có lớp bọc bảo vệ đơn điệu ở tầng ngoài (Outer Monotonicity Protection), vì sao trong thực nghiệm G5 và G10, thuật toán Hybrid không bao giờ trả về nghiệm tệ hơn nghiệm khởi đầu?

Nguyên nhân nằm ở tầng thuật toán con bên trong: `src/optimization/sa/annealer.py`.

```python
# File: src/optimization/sa/annealer.py (Lines 180-184 & 247-270)
# 1. Khởi tạo best_state từ nghiệm khởi đầu:
initial_obj = compute_state_objective(curr_state, self.config)
curr_obj = initial_obj
best_state = curr_state.copy()
best_obj = curr_obj

# 2. Vòng lặp SA chỉ cập nhật best_state khi tìm thấy nghiệm TỐT HƠN NGHIÊM NGẶT:
if curr_obj < best_obj:
    best_state = curr_state.copy()
    best_obj = curr_obj

# 3. Khẳng định bất biến toán học trước khi kết thúc giải thuật:
# Invariant I2: Objective never worse than initial solution
assert best_obj <= initial_obj + 1e-9, (
    f"Invariant I2: SA best objective ({best_obj:.4f}) is worse than initial ({initial_obj:.4f})"
)
```

**Nhận xét:**
- Tính bảo toàn đơn điệu **thực sự được đảm bảo bên trong `SimulatedAnnealingGateSolver`** nhờ cơ chế theo dõi biến `best_state` và bất biến khẳng định `Invariant I2`.
- Nếu SA không tìm thấy bất kỳ lời giải nào tốt hơn trong 300 bước lặp, `best_state` giữ nguyên chính xác trạng thái ban đầu của `incumbent_assignments`.

---

## 4. LỖ HỔNG KIẾN TRÚC TẦNG NGOÀI (OUTER VULNERABILITY EXPERIMENT)

Mặc dù `SimulatedAnnealingGateSolver` nội tại bảo toàn đơn điệu theo hàm mục tiêu nội bộ của nó (`compute_state_objective`), việc `hybrid_solver.py` thiếu cơ chế kiểm tra và chốt chặn ở tầng ngoài (Outer Fallback) tạo ra rủi ro kiến trúc nghiêm trọng:

### 4.1. Thử nghiệm với SA Stub trong `test_hybrid_monotonicity_micro.py`
Kiểm toán viên đã mô phỏng tình huống solver SA trả về một nghiệm khả thi nhưng có chi phí suy giảm (tệ hơn) so với nghiệm khởi đầu của Stage 1 (ví dụ chi phí ban đầu $0.0$, chi phí SA trả về là $400.0$ do gán vào bãi đỗ Apron):

```text
Stubbed SA (returning worse feasible solution obj=400.0):
  Stage 1 initial_cost was: 0.0000
  Hybrid returned status:   FEASIBLE
  Hybrid returned objective:420.0000
  Hybrid assignments:       REMOTE, REMOTE
=> CRITICAL VERIFICATION:
  hybrid_solver.py returned the WORSE SA solution! It did NOT fall back to initial_cost.
  This definitively proves hybrid_solver.py lacks outer monotonicity protection.
```

### 4.2. Phân tích Rủi ro
1. **Không có cơ chế phòng vệ tự vệ (Zero Defensive Guard):** `hybrid_solver.py` phó thác toàn bộ trách nhiệm đơn điệu cho solver con. Nếu solver con gặp lỗi làm suy giảm mục tiêu hoặc bị thay thế bằng một metaheuristic khác không có cơ chế `best_state`, `HybridGateSolver` sẽ trả về nghiệm kém cỏi mà không kích hoạt bất kỳ cảnh báo nào.
2. **Khác biệt hàm mục tiêu tiềm ẩn:** Nếu hàm đánh giá nội bộ của SA (`compute_state_objective`) có sự sai khác dù chỉ là làm tròn số học so với `evaluate_gate_assignment`, `hybrid_solver.py` không có logic để phát hiện và giữ lại nghiệm Stage 1.

---

## 5. TỔNG KẾT VÀ PHÁN QUYẾT KIỂM TOÁN CHO TASK 2.1

| Hạng mục Thẩm định | Kết quả Kiểm tra Thực tế | Phán quyết Kiểm toán |
| :--- | :--- | :---: |
| **Tuyên bố dòng 280 có `best_cost = min(...)`** | Dòng 280 là dòng trống; toàn văn file không có `min(...)`. | **FAILED (CLAIM FABRICATION)** |
| **Bảo vệ đơn điệu ở tầng ngoài (`hybrid_solver.py`)** | Hoàn toàn không có logic fallback hoặc so sánh chi phí. | **FAILED (ABSENT IN HYBRID SOLVER)** |
| **Bảo vệ đơn điệu ở tầng trong (`annealer.py`)** | Có, thông qua biến `best_state` và khẳng định `Invariant I2`. | **VERIFIED (INTERNAL SA ONLY)** |
| **Kết quả thực nghiệm benchmark không bị suy giảm** | Do SA nội tại trả về nghiệm khởi đầu khi không tìm thấy nghiệm tốt hơn. | **VERIFIED (EXPLAINED VIA INNER SA)** |
