# AEOLUS-G11 — DELIVERABLE 04: HYBRID SOLVER WALL-CLOCK BUDGET CONTRACT & OVERRUN AUDIT

---

**Audit Gate:** `AEOLUS-G11` — Targeted Causality, Hybrid Invariant & Snapshot Verification  
**Date of Audit:** 2026-10-12  
**Auditor Role:** Independent Scientific Software Verification Engineer  
**Audit Target:** `src/optimization/solvers/hybrid_solver.py`, `src/optimization/sa/annealer.py`, `scripts/run_g5_fair_benchmark.py`  
**Classification:** RUNTIME BENCHMARK INTEGRITY & CONTRACT VERIFICATION  

---

## 1. BỐI CẢNH VÀ QUY TẮC PHÂN BỔ NGÂN SÁCH THỜI GIAN (BENCHMARK CONTRACT)

Trong thỏa ước benchmark công bằng (Fair Benchmark Contract) của G5 và G10:
- Mỗi thuật toán được cấp một ngân sách thời gian thực tối đa là **$T_{\text{max}} = 5.0\text{ giây}$** (`time_limit_seconds = 5.0`).
- Bộ giải Standalone CP-SAT tuân thủ nghiêm ngặt mốc này, dừng lại ngay sau khi hoàn tất bước cắt tỉa tại thời điểm khoảng $5.19\text{s}$ ($N=200$) và $5.44\text{s}$ ($N=300$).
- Tuy nhiên, số liệu thực nghiệm được ghi nhận tại `05_G5_HYBRID_DISCREPANCY.md` cho thấy bộ giải Hybrid có thời gian chạy thực tế vượt trần nghiêm trọng:
  - Tại $N=200$: Hybrid mất **$9.046\text{ms}$ ($9,05\text{ giây}$)**.
  - Tại $N=300$: Hybrid mất **$12.500\text{ms}$ ($12,50\text{ giây}$)**.

Nhiệm vụ kiểm toán là phân tích chi tiết mã nguồn để xác định nguyên nhân kỹ thuật khiến Hybrid vi phạm hợp đồng thời gian, và đánh giá tác động khoa học của hiện tượng này.

---

## 2. PHÂN TÍCH NGUYÊN NHÂN GỐC TRONG MÃ NGUỒN (ROOT CAUSE ANALYSIS)

### 2.1. Phân chia Ngân sách một chiều tại Stage 1

Tại `src/optimization/solvers/hybrid_solver.py` (dòng 121–125):
```python
# Stage 1: CP-SAT được áp đặt ngân sách chặt chẽ
cp_budget_seconds = max(0.01, self.config.time_limit_seconds * self.cp_ratio)  # = 5.0 * 0.5 = 2.5s
cp_config = replace(self.config, time_limit_seconds=cp_budget_seconds)
cp_solver = CPSatGateSolver(config=cp_config)
t_cp0 = time.perf_counter()
cp_result = cp_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
cp_wall_clock_ms = (time.perf_counter() - t_cp0) * 1000.0
```
- CP-SAT nhận đúng tham số `time_limit_seconds = 2.5s` và dừng lại đúng sau $\approx 2.5\text{ giây}$.

---

### 2.2. Sự Vắng mặt Hoàn toàn của Ràng buộc Thời gian tại Stage 2

Tại `src/optimization/solvers/hybrid_solver.py` (dòng 260–271):
```python
# Stage 2: Simulated Annealing được khởi tạo và kích hoạt
sa_solver = SimulatedAnnealingGateSolver(
    config=self.config,
    sa_config=self.sa_config,
)
t_sa0 = time.perf_counter()
sa_result = sa_solver.solve(
    flights=flights,
    gates=gate_list,
    initial_assignments=incumbent_assignments,
    allow_overflow=allow_overflow,
)
sa_wall_clock_ms = (time.perf_counter() - t_sa0) * 1000.0
```

Kiểm tra chữ ký hàm và vòng lặp giải thuật trong `src/optimization/sa/annealer.py`:
1. **Chữ ký hàm `solve()`:**
   ```python
   def solve(
       self,
       flights: Sequence[Flight],
       gates: Sequence[Gate],
       *,
       initial_assignments: Mapping[str, GateAssignment] | None = None,
       allow_overflow: bool = True,
   ) -> OptimizationResult:
   ```
   **Nhận xét:** Hàm `solve()` **HOÀN TOÀN KHÔNG NHẬN** bất kỳ tham số giới hạn thời gian nào (`time_limit_seconds` hay `remaining_budget_seconds`).
2. **Vòng lặp hạ nhiệt (Annealing Loop dòng 201–260):**
   ```python
   for k in range(1, self.sa_config.iterations + 1):
       # Sinh lân cận và đánh giá...
   ```
   **Nhận xét:** Vòng lặp duyệt tuần tự cố định đúng $K = 300$ bước lặp. Trong thân vòng lặp **HOÀN TOÀN KHÔNG CÓ CÂU LỆNH KIỂM TRA THỜI GIAN THỰC (Zero Wall-Clock Timeout Check)** dạng:
   ```python
   if (time.perf_counter() - t0) > max_allowed_seconds:
       break
   ```

---

## 3. PHÂN RÃ THỜI GIAN THỰC HIỆN TẠI CÁC KỊCH BẢN QUY MÔ LỚN

Bảng phân rã thời gian tính toán chi tiết (Decomposed Wall-Clock Audit):

| Quy mô Kịch bản | Ngân sách Quy định ($T_{\text{max}}$) | Stage 1: CP-SAT Time | Cơ chế Chuyển tiếp | Stage 2: SA Time (300 buớc) | Xác minh Độc lập | Tổng Thời gian Thực tế | Tỷ lệ Vượt ngân sách |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`MICRO_PARITY`** ($N=4, M=4$) | $5.0\text{s}$ | $5.9\text{ms}$ (Optimal) | Không fallback | $98.8\text{ms}$ | $0.6\text{ms}$ | **$105.3\text{ms}$** | Không vượt (Hợp lệ) |
| **`THESIS_200_30`** ($N=200, M=35$) | $5.0\text{s}$ | **$2.540\text{ms}$** (Timeout 2.5s) | Dùng Incumbent ($710.13$) | **$6.506\text{ms}$** ($\approx 21.7\text{ms}$/buớc) | Sau SA | **$9.046\text{ms}$** | **$+80.9\%$ VƯỢT TRẦN** |
| **`THESIS_300_50`** ($N=300, M=56$) | $5.0\text{s}$ | **$2.550\text{ms}$** (Timeout No Inc) | Greedy Fallback ($18\text{ms}$) | **$9.215\text{ms}$** ($\approx 30.7\text{ms}$/buớc) | $717\text{ms}$ | **$12.500\text{ms}$** | **$+150.0\%$ VƯỢT TRẦN** |

---

## 4. TÁC ĐỘNG KHOA HỌC VÀ ĐÁNH GIÁ TÍNH CÔNG BẰNG (FAIRNESS EVALUATION)

### 4.1. Sự Bất đối xứng trong Thử nghiệm (Benchmark Asymmetry)
- Standalone CP-SAT bị giới hạn cứng ở $5.0$ giây.
- Hybrid được phép chạy tới **$9.05$ giây** và **$12.50$ giây** (gấp $2.5$ lần ngân sách).
- **Hệ quả khoa học đáng chú ý:** Dù được hưởng thời gian chạy thực tế gấp đôi ngân sách, Hybrid vẫn đạt kết quả kém xa CP-SAT:
  - Ở $N=200$: Hybrid mất $9.05\text{s}$ để đạt chi phí $710.13$, trong khi CP-SAT chỉ mất $5.19\text{s}$ để đạt chi phí vượt trội $660.13$.
  - Ở $N=300$: Hybrid mất $12.50\text{s}$ chỉ để đạt chi phí của Greedy ($1219.47$), trong khi CP-SAT chỉ mất $5.44\text{s}$ để tìm được nghiệm tối ưu cục bộ sâu $1039.47$.

### 4.2. Khuyết tật Thiết kế Kiến trúc (Architectural Defect)
1. Báo cáo G10 tuyên bố *"2.5 giây còn lại được dành cho Giai đoạn 2 (Stage 2)"* chỉ là phép trừ số học trên giấy tờ ($5.0 - 2.5 = 2.5$). Trên thực tế, **con số 2.5 giây đó chưa từng được chuyển giao cho bộ giải SA**.
2. Độ phức tạp tính toán của mỗi bước lặp SA tăng phi tuyến theo số lượng chuyến bay và cổng ($O(N \cdot M)$ để sinh và kiểm tra ràng buộc hard constraint cho mỗi lân cận). Do đó, việc cố định $300$ bước lặp mà không kiểm soát thời gian khiến SA bùng nổ thời gian khi $N \ge 200$.

---

## 5. PHÁN QUYẾT KIỂM TOÁN CHÍNH THỨC CHO TASK 2.2

| Tiêu chí | Hiện trạng Thực tế | Phán quyết Kiểm toán |
| :--- | :--- | :---: |
| **Thực thi ngân sách thời gian Stage 1** | CP-SAT dừng chính xác theo `cp_budget_seconds = 2.5s`. | **VERIFIED** |
| **Thực thi ngân sách thời gian Stage 2** | SA không có tham số giới hạn thời gian, chạy đủ 300 bước lặp. | **FAILED (UNCONTROLLED RUNTIME)** |
| **Tuân thủ ngân sách tổng 5.0s của Hybrid** | Vi phạm nghiêm trọng tại $N=200$ ($9.05\text{s}$) và $N=300$ ($12.50\text{s}$). | **LIMITATION (BUDGET OVERRUN)** |
| **Tuyên bố của G10 về phân bổ thời gian** | Trình bày thiếu sót, không chỉ ra hiện tượng SA chạy quá thời gian thực tế. | **LIMITATION (INCOMPLETE DISCLOSURE)** |
