# AEOLUS-G11 — DELIVERABLE 02: MODE B2 COUNTEREXAMPLE TESTS & DECISION LEAKAGE PROOF

---

**Audit Gate:** `AEOLUS-G11` — Targeted Causality, Hybrid Invariant & Snapshot Verification  
**Date of Audit:** 2026-10-12  
**Auditor Role:** Independent Scientific Software Verification Engineer  
**Audit Artifact:** `audit_exports/G11_targeted_verification/test_counterexample_b2_leakage.py`  
**Classification:** EMPIRICAL REPRODUCIBILITY PROOF  

---

## 1. THIẾT KẾ THỰC NGHIỆM ĐỐI CHỨNG (COUNTEREXAMPLE DESIGN)

Để phân định rạch ròi giữa hai khái niệm:
1. **`FUTURE_INFORMATION_ACCESS` (Truy cập thông tin tương lai):** Mã nguồn đọc một biến chứa dữ liệu xảy ra sau thời điểm quyết định $t$.
2. **`DECISION_LEAKAGE` (Rò rỉ thông tin làm thay đổi quyết định):** Việc đột biến thông tin tương lai (sau $t$) trực tiếp làm thay đổi hành động/quyết định được đưa ra tại thời điểm $t$.

Kiểm toán viên đã xây dựng bộ kiểm thử độc lập `test_counterexample_b2_leakage.py` với hai thí nghiệm đối chứng có kiểm soát.

---

## 2. THỬ NGHIỆM 1: BẰNG CHỨNG THAM SỐ `lock_horizon_minutes` LÀ MÃ CHẾT

### 2.1. Thiết lập kịch bản
- Kịch bản gồm 2 chuyến bay (`FL_A`, `FL_B`) và 2 cổng (`G1` - Contact Gate, `REMOTE` - Apron Stand).
- Chạy hàm `evaluate_mode_b2_rolling_online_recourse()` với 3 giá trị `lock_horizon_minutes` cách biệt cực đoan:
  - $\tau_1 = 0$ phút.
  - $\tau_2 = 45$ phút (mặc định của hệ thống).
  - $\tau_3 = 1000$ phút.

### 2.2. Kết quả thực thi thực tế (Raw Execution Log)
```text
================================================================================
TEST 1: UNUSED lock_horizon_minutes PARAMETER TEST
================================================================================
Results for lock_horizon=0:    obj=210.0000, reassignments=1
Results for lock_horizon=45:   obj=210.0000, reassignments=1
Results for lock_horizon=1000: obj=210.0000, reassignments=1
=> VERIFIED: lock_horizon_minutes has ZERO effect on logic and output. It is completely unused dead code.
```

### 2.3. Khẳng định Kiểm toán
- Toàn bộ các thuộc tính đầu ra: `objective_value` ($210.0000$), `reassignment_count` ($1$), và chuỗi vết quyết định `decision_trace` giống hệt nhau $100\%$ theo từng bit giữa cả ba lần chạy.
- **Kết luận:** Tham số `lock_horizon_minutes` hoàn toàn không có bất kỳ tác động logic nào trong `monte_carlo_engine_v2.py`.

---

## 3. THỬ NGHIỆM 2: CHỨNG MINH `DECISION_LEAKAGE` DO TRUY CẬP `precomputed_gate_out_min`

### 3.1. Thiết lập Cặp Kịch bản Ghép đôi (Twin Scenarios)

Xây dựng hai kịch bản đối chứng có **lịch sử hoạt động trước và tại thời điểm quyết định $t = 120$ hoàn toàn đồng nhất**:

| Thuộc tính | Kịch bản 1 (Scenario 1 - Baseline) | Kịch bản 2 (Scenario 2 - Mutated Dep Delay) | Đánh giá trước $t=120$ |
| :--- | :---: | :---: | :---: |
| Chuyến bay A: Thời điểm đến ($T_{\text{arr}}$) | $t = 60$ | $t = 60$ | **ĐỒNG NHẤT** |
| Chuyến bay A: Cổng ban đầu | Cổng `G1` | Cổng `G1` | **ĐỒNG NHẤT** |
| Chuyến bay B: Thời điểm đến ($T_{\text{arr}}$) | $t = 120$ | $t = 120$ | **ĐỒNG NHẤT** |
| Chuyến bay B: Cổng ban đầu | Cổng `G1` | Cổng `G1` | **ĐỒNG NHẤT** |
| Chuyến bay A: Giờ bay đi theo lịch | $100$ | $100$ | **ĐỒNG NHẤT** |
| **Chuyến bay A: Giờ bay đi thực tế (`precomputed_gate_out_min`)** | **$100$** (đúng giờ) | **$140$** (trễ đi $+40$ phút tại cổng) | **ĐỘT BIẾN TƯƠNG LAI** |
| **Thời điểm giải phóng cổng A ($T_{\text{dep}} + \text{buffer}$)** | $100 + 15 = \mathbf{115}$ | $140 + 15 = \mathbf{155}$ |  |

Tại thời điểm $t = 120$, chuyến bay B hạ cánh và yêu cầu tiếp nhận cổng:
- Trong Kịch bản 1: Cổng `G1` đã được giải phóng từ $t = 115$. Khoảng chiếm dụng của B $[120, 180]$ không bị chồng lấn với A $[60, 115]$.
- Trong Kịch bản 2: Tàu bay A bị kéo dài thời gian đỗ thực tế tới $t = 140$, giải phóng lúc $155$. Cổng `G1` bị chồng lấn tại khoảng $[120, 155]$.

### 3.2. Kết quả Thực thi Thực tế (Raw Execution Log)

```text
================================================================================
TEST 2: FUTURE INFORMATION ACCESS & DECISION LEAKAGE TEST
================================================================================
Scenario 1 (FL_A departs at 100, FL_B arrives at 120):
  FL_B reassignments count: 0
  Decision trace: ()

Scenario 2 (FL_A departs at 140 in future, FL_B arrives at 120):
  FL_B reassignments count: 1
  Decision trace: ({'flight_id': 'FL_B', 'decision_epoch_min': 120, 'previous_gate': 'G1', 'reassigned_gate': 'REMOTE', 'reason': 'ONLINE_NON_ANTICIPATIVE_RECOURSE'},)

================================================================================
ANALYSIS OF CAUSALITY IN SCENARIOS 1 vs 2:
================================================================================
CRITICAL FINDING: DECISION LEAKAGE PROVEN!
At epoch t=120:
  In Scenario 1, FL_B was NOT reassigned (reassignment_count=0)
  In Scenario 2, FL_B WAS reassigned (reassignment_count=1, trace=({'flight_id': 'FL_B', 'decision_epoch_min': 120, 'previous_gate': 'G1', 'reassigned_gate': 'REMOTE', 'reason': 'ONLINE_NON_ANTICIPATIVE_RECOURSE'},))
```

---

## 4. PHÂN TÍCH Ý NGHĨA KHOA HỌC & BẢN CHẤT VẬN HÀNH

### 4.1. Bản chất của sự rò rỉ (Information Leakage Mechanism)
1. Trong Kịch bản 2, tại mốc thời điểm quyết định $t = 120$, thuật toán đã sử dụng mốc thời gian $T_{\text{dep}} = 140$ để tính toán điều kiện giao cắt:
   $$\max(T_{\text{arr}}^B, T_{\text{arr}}^A) < \min(T_{\text{dep}}^B + \text{buf}, T_{\text{dep}}^A + \text{buf})$$
   $$\max(120, 60) = 120 < \min(195, 155) = 155 \implies \text{True (Xung đột!)}$$
2. Chuyến bay B bị đẩy ra bãi đỗ xa (`REMOTE`) ngay tại $t = 120$ dựa trên giá trị $T_{\text{dep}}^A = 140$ vốn diễn ra **sau $t=120$ tới 20 phút**.
3. Nếu hệ thống vận hành theo đúng chuẩn *Strict Non-anticipativity* (không dự đoán tương lai hoàn hảo):
   - Tại thời điểm $t = 120$, nếu chưa có thông tin độ trễ đi được cập nhật qua bộ lọc trạng thái (State Filter), người điều hành phải căn cứ vào thời gian quay đầu kế hoạch hoặc dự báo cập nhật tại thời điểm $t$.
   - Việc nạp sẵn mốc rời cổng thực tế cuối kịch bản vào trường tĩnh `precomputed_gate_out_min` đồng nghĩa với việc mô hình giả định **người điều hành có khả năng thấu thị hoàn hảo (Perfect Foresight)** về thời điểm máy bay sẽ đẩy lùi khỏi cổng.

### 4.2. Khía cạnh Biện hộ Vận hành (Operational Defense) & Giới hạn
- **Lập luận biện hộ có thể có:** Tại $t = 120$, tàu bay A đáng lẽ phải rời cổng lúc $100$ nhưng thực tế chưa rời cổng, nên nhân viên điều độ nhìn thấy tàu bay A vẫn đang chiếm cổng $G1$ tại $t = 120$. Do đó, việc chuyển chuyến B là hợp lý trên thực địa.
- **Giới hạn phản biện khoa học:** 
  1. Nếu tàu bay A có giờ khởi hành dự kiến là $t = 160$ (chưa tới hạn rời cổng tại $t = 120$), nhưng bị phát sinh trễ thành $t = 220$, thuật toán vẫn dùng mốc $220$ tại thời điểm $t = 120$ để tính toán cửa sổ giao cắt cho các chuyến bay tiếp theo.
  2. Thời gian đỗ của chính chuyến bay B (`current_end`) cũng đọc trực tiếp từ `current_flight.precomputed_gate_out_min` khi tìm cổng ứng viên (dòng 452). Tức là khi B vừa hạ cánh, thuật toán đã biết chính xác B sẽ đỗ bao nhiêu phút trong tương lai để chọn cổng tiếp xúc phù hợp!

---

## 5. PHÁN QUYẾT KIỂM TOÁN CHÍNH THỨC CHO TASK 1

| Tiêu chí Kiểm toán | Kết quả Kiểm toán | Định danh Phán quyết |
| :--- | :---: | :---: |
| **Truy cập thông tin tương lai qua `precomputed_gate_out_min`** | Có, đọc trực tiếp giờ rời cổng thực tế tại thời điểm đến $t$. | **VERIFIED (CONFIRMED ACCESS)** |
| **Rò rỉ làm thay đổi quyết định điều chuyển cổng tại epoch $t$** | Có, đã chứng minh bằng kịch bản phản chứng độc lập. | **VERIFIED (DECISION LEAKAGE)** |
| **Sử dụng và thực thi tham số `lock_horizon_minutes`** | Không thực thi, 0 lần xuất hiện trong thân hàm, là dead code. | **FAILED (UNUSED INVARIANT)** |
| **Tuyên bố Mode B2 "STRICTLY CAUSAL" trong báo cáo G10** | Không chính xác về mặt toán học quá trình ngẫu nhiên. Mode B2 là *Semi-Causal with Perfect Departure Dwell Foresight*. | **LIMITATION (RECLASSIFICATION REQUIRED)** |
