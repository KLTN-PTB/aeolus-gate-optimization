# BÁO CÁO 03: CHUẨN HÓA TOÁN HỌC, TÍNH TỐI ƯU VÀ ĐỊNH NGHĨA EVPI
## AEOLUS-G12C — SCIENTIFIC MATHEMATICS & THEORETICAL BOUNDS AUDIT

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Chủ đề:** Chuẩn hóa các phát biểu toán học về Cận tối ưu, EVPI, Quan hệ B1/B2/C1 và Giới hạn Thời gian Bộ giải  

---

## 1. MINH BẠCH TÍNH TỐI ƯU CỦA MODE C2 VÀ BẢN CHẤT CẬN TOÁN HỌC

### 1.1. Thực Trạng Kết Quả Mode C2 Trong Dữ Liệu Thô N=500
Trong $500$ kịch bản ngẫu nhiên của thí nghiệm Monte Carlo chính thức:
- **Số kịch bản đạt chứng chỉ tối ưu toàn cục (Certified Global Optimum):** **$499 / 500$ kịch bản** ($99.80\%$). Các kịch bản này có `solver_status = "OPTIMAL"` và `is_optimal_proven = True`.
- **Số kịch bản đạt nghiệm khả thi chưa chứng minh tối ưu:** **$1 / 500$ kịch bản** ($0.20\%$). Đó là kịch bản `MC_REM_S0183` (scenario index 183).

### 1.2. Bản Chất Toán Học của Nghiệm Khả Thi (Feasible Incumbent)
Trong bài toán tối thiểu hóa chi phí (Minimization Problem):
$$\min_{x \in \mathcal{X}} f(x)$$
- Bất kỳ nghiệm khả thi $x_{\text{feasible}} \in \mathcal{X}$ nào cũng thỏa mãn:
  $$f(x_{\text{feasible}}) \ge f(x^*)$$
- **Khẳng định chuẩn hóa:** Nghiệm khả thi tìm được của kịch bản 183 ($f = 168.80$) đóng vai trò là một **cận trên (Upper Bound)** của chi phí tối ưu toàn cục thực sự đối với kịch bản đó, **KHÔNG PHẢI là một cận dưới đã được chứng minh (Proven Lower Bound)**. Cận dưới lý thuyết chỉ được xác lập khi bộ giải hoàn tất nhánh cận (Branch-and-Bound) hoặc cung cấp dual bound hợp lệ.
- **Phân loại cấp độ hiển thị (Presentation-Level Classification):** Trong tệp kết quả thô `foresight_c2_optimal_results.csv`, trường metadata `recourse_policy` được gán tĩnh nhãn `"PROVEN_MATHEMATICAL_OPTIMAL_FORESIGHT"`. Để bảo vệ tính bất biến của tệp thô, hệ thống không sửa tệp CSV này mà áp dụng bộ phân loại presentation-level:
  - Nếu `solver_status == "OPTIMAL"` và `is_optimal_proven == True`: Phân loại là **Certified Global Optimum**.
  - Nếu `solver_status == "FEASIBLE"` và `is_optimal_proven == False`: Phân loại là **Feasible Upper Bound within Deadline**.

### 1.3. Forensic Kịch Bản `MC_REM_S0183` và Chuẩn Hóa Thuật Ngữ
- **Thời gian thực thi:** $1,572.82$ ms (ngưỡng giới hạn cấu hình là $1,500$ ms / $1.5$s).
- **Thuật ngữ chuẩn hóa:** Kịch bản này không bị lỗi crash hệ thống, không bị deadlock, mà đã **chạm giới hạn thời gian (Time Limit / Deadline reached)** của bộ giải CP-SAT. Bộ giải đã dừng lại an toàn theo cơ chế fail-safe và trả về nghiệm khả thi tốt nhất hiện có (best incumbent found).
- **Nguyên tắc đóng băng:** Không được tự ý tăng ngân sách thời gian cho kịch bản 183 (ví dụ lên 10s hay 60s) rồi ghi đè vào dữ liệu MC500 chính thức.

---

## 2. HIỆU ĐÍNH CÔNG THỨC TOÁN HỌC CỦA EVPI (EXPECTED VALUE OF PERFECT INFORMATION)

### 2.1. Định Nghĩa Chuẩn trong Tối Ưu Hóa Ngẫu Nhiên (Stochastic Programming)
Trong bài toán tối thiểu hóa chi phí với biến ngẫu nhiên $\xi$:
- **Bài toán Recourse (Here-and-Now / RP):** Ra quyết định $x$ trước khi biết hiện thực ngẫu nhiên $\xi$:
  $$\text{RP} = \min_{x} \mathbb{E}_{\xi} [f(x, \xi)]$$
- **Bài toán Thông tin Hoàn hảo (Wait-and-See / WS):** Ra quyết định sau khi đã quan sát hoàn hảo hiện thực $\xi$:
  $$\text{WS} = \mathbb{E}_{\xi} \left[ \min_{x} f(x, \xi) \right]$$
- Do với mọi nghiệm $x$ cố định, $f(x, \xi) \ge \min_{x'} f(x', \xi)$, lấy kỳ vọng hai vế ta luôn có $\mathbb{E}[f(x, \xi)] \ge \mathbb{E}[\min_{x'} f(x', \xi)]$. Do đó:
  $$\text{RP} \ge \text{WS}$$
- **Công thức EVPI chuẩn xác cho bài toán Tối thiểu hóa:**
  $$\text{EVPI} = \text{RP} - \text{WS} = \min_{x} \mathbb{E}_{\xi} [f(x, \xi)] - \mathbb{E}_{\xi} \left[ \min_{x} f(x, \xi) \right] \ge 0$$

> [!WARNING]
> **Hiệu đính dấu công thức cũ:**
> Trong Báo cáo 07 trước đây, công thức EVPI bị viết ngược thứ tự thành $\mathbb{E}[\min] - \min \mathbb{E} \le 0$ (vốn là dạng của bài toán tối đa hóa lợi nhuận). Báo cáo G12C chính thức hiệu đính công thức EVPI theo đúng bài toán cực tiểu hóa chi phí: $\text{EVPI} = \text{RP} - \text{WS} \ge 0$.

### 2.2. Phân Biệt Thực Nghiệm "Price of Uncertainty" vs. Lý Thuyết "Formal EVPI"
- Khoảng cách chênh lệch giữa Mode B2 và Mode C2 trong thí nghiệm MC500 là:
  $$\Delta_{\text{B2} - \text{C2}} = 139.49 - 120.39 = 19.10 \text{ đơn vị} \quad (95\%\text{ CI: } [15.93, 22.27])$$
- **Tuyên bố ranh giới học thuật:** Khoảng cách này là một **"Empirical Policy-to-Foresight Gap" (hoặc Empirical Price of Uncertainty)** trong bối cảnh thực nghiệm cụ thể của thuật toán heuristic rolling-horizon Mode B2 so với bộ giải CP-SAT Mode C2.
- Đại lượng này **KHÔNG ĐƯỢC ĐỒNG NHẤT** với formal theoretical EVPI của lý thuyết quy hoạch ngẫu nhiên hai giai đoạn vì:
  1. Mode B2 là một heuristic trực quan thời gian thực chứ không phải nghiệm tối ưu của bài toán quy hoạch ngẫu nhiên 2 giai đoạn (stochastic program recourse solution).
  2. Mode C2 có 1 kịch bản dừng ở nghiệm khả thi chứ không phải 100% exact global optimum.
  3. Phân phối ngẫu nhiên là mô hình tham số thực nghiệm (Gaussian Copula Student-t) chứ không phải phân phối tiên nghiệm thực tế của toàn bộ không gian mẫu.

---

## 3. PHÂN TÍCH QUAN HỆ TOÁN HỌC GIỮA MODE B1 VÀ MODE B2

1. **Bản chất của Mode B1 và B2:**
   - **Mode B1 (Retrospective Recourse):** Quan sát toàn bộ hiện thực chậm trễ của cả ngày rồi giải một lần duy nhất từ đầu đến cuối bằng thuật toán tham lam Deterministic Greedy.
   - **Mode B2 (Rolling Online Recourse):** Hoạt động theo nhân quả thời gian thực (causal / non-anticipative), chỉ xử lý các xung đột xuất hiện tại mốc thời gian hiện hành.
2. **Không có quan hệ thứ tự bảo đảm trên từng kịch bản đơn lẻ:**
   - Mặc dù trung bình mẫu lớn $\mathbb{E}[B1] = 130.73 < \mathbb{E}[B2] = 139.49$ với ý nghĩa thống kê vượt trội ($p = 4.0 \times 10^{-9}$), **không có định lý toán học nào bảo đảm Mode B1 luôn có chi phí nhỏ hơn hoặc bằng Mode B2 trên từng realization riêng biệt**.
   - Nguyên nhân: Cả hai chế độ đều sử dụng quy tắc chọn cổng Greedy cục bộ và phá vỡ thế hòa (tie-breaking). Một quyết định Greedy trong B1 có thể vô tình dẫn tới chuỗi gán cổng bất lợi hơn so với một quyết định xử lý cục bộ của B2 trên một kịch bản cá biệt.

---

## 4. GIẢI MÃ SỰ ĐỒNG NHẤT SỐ HỌC GIỮA MODE B1 VÀ MODE C1

Trong kết quả thực nghiệm MC500, một hiện tượng toán học thú vị được ghi nhận:
$$\text{Objective}(B1_{\text{Greedy}}) = \text{Objective}(C1) \quad (\text{Sai lệch tuyệt đối } = 0.00 \text{ trên toàn bộ 500 kịch bản})$$
$$\text{Mean} = 130.730234, \quad \text{Std} = 25.370665, \quad \text{Median} = 126.29165$$

### Phân Tích Cơ Chế Mã Nguồn:
1. Trong `scripts/run_g2_monte_carlo_remediation.py`:
   - Mode B1 gọi hàm `evaluate_mode_b1_retrospective_recourse(..., recourse_solver_name="DeterministicGreedy")`.
   - Mode C1 gọi hàm `evaluate_mode_c_greedy_foresight(...)`.
2. Trong `src/simulation/monte_carlo_engine_v2.py`:
   - Cả hai hàm đều khởi tạo `solver = DeterministicGreedyGateSolver(config=config)` và giải bài toán trên cùng một tập chuyến bay đã thực nhận độ trễ (`realized_flights`) với cùng danh mục cổng (`all_gates`).
   - Bộ giải `DeterministicGreedyGateSolver` duyệt các chuyến bay theo thứ tự thời gian xuất hiện và gán vào cổng đỗ khả thi đầu tiên có chỉ số nhỏ nhất.
   - Thuật toán này không tính chi phí tái gán vào hàm mục tiêu nội tại của bước giải greedy.
3. **Kết luận khoa học:** Mode B1 và Mode C1 trong MC500 là **hai tên gọi cho cùng một cơ chế giải toán học Greedy Full-Hindsight**. Sự khác biệt duy nhất là Mode B1 được tính toán 3 lần trên mỗi kịch bản để đo lường số lượt đổi cổng so với 3 kế hoạch ban đầu (Greedy, CP-SAT, Hybrid), trong khi Mode C1 được ghi nhận 1 lần làm mốc đối chứng heuristic foresight độc lập.

---

## 5. GIỚI HẠN DIỄN GIẢI THỰC TẾ (REAL-WORLD DEPLOYMENT LIMITATIONS)

1. **Hiệu năng Benchmark Synthetic vs. Triển khai Thực tế:**
   - Thời gian chạy trung bình của Mode B2 là $3.95$ ms/kịch bản trên benchmark tổng hợp 120 chuyến bay.
   - Kết quả này chứng minh thuật toán có độ phức tạp thời gian thấp trong môi trường mô phỏng, nhưng **KHÔNG ĐƯỢC SUY DIỄN** rằng hệ thống đã sẵn sàng kết nối trực tiếp với trung tâm điều hành sân bay (AOCC) thời gian thực mà không qua kiểm thử tải mạng, độ trễ API và tích hợp thông điệp ACARS/AIDX.
2. **Dữ liệu 120 Chuyến bay Inbound Synthetic vs. Toàn bộ Lịch sử Sân bay:**
   - Thí nghiệm MC500 được thiết kế trên mô hình kịch bản synthetic 120 chuyến bay (Atlanta Inbound Bank), mô phỏng phân phối độ trễ tham số.
   - Kết quả này kiểm chứng tính đúng đắn toán học của các thuật toán tối ưu hóa phân bổ cổng, nhưng **KHÔNG ĐƯỢC TUYÊN BỐ** là đã kiểm chứng toàn diện cho toàn bộ lịch sử khai thác cả năm 2016–2024 của Sân bay Quốc tế Atlanta.
