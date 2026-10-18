# BÁO CÁO 07: GIỚI HẠN VÀ ĐIỀU KIỆN TÁI LẬP KHOA HỌC (REPRODUCIBILITY & SCIENTIFIC LIMITATIONS)

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** Production Monte Carlo N=500 Verification  
**Run ID:** `mc500_20261012_173538_afa5db`  
**Ngày thực hiện:** 2026-10-13  
**Phạm vi:** Tuyên bố tính hợp lệ phương pháp luận, giới hạn suy diễn và điều kiện tái lập  

---

## 1. PHẠM VI DỮ LIỆU VÀ TÍNH CHẤT BENCHMARK TỔNG HỢP (SYNTHETIC BENCHMARK SCOPE)

1. **Bản chất tập dữ liệu:**
   - Dữ liệu thử nghiệm gồm $120$ chuyến bay là một **canonical parametric synthetic benchmark** được xây dựng dựa trên cấu trúc lịch bay thực tế (inbound bank structure mô phỏng sân bay quốc tế Hartsfield–Jackson Atlanta - ATL).
   - Phân phối độ trễ ngẫu nhiên được sinh ra từ mô hình toán học: **Gaussian Copula với hệ số tương quan $\rho = 0.45$** kết hợp các phân phối biên **Student-t ($df = 4$)** cho thời gian trễ đến và trễ đi.
2. **Giới hạn diễn giải:**
   - Kết quả này **KHÔNG PHẢI** là lịch sử vận hành thực tế đã ghi nhận của một hãng hàng không hay cảng hàng không cụ thể trong một ngày lịch sử nhất định.
   - Không được suy diễn trực tiếp rằng tỷ lệ vi phạm của Mode A ($74.8\%$) phản ánh tỷ lệ trễ cổng của các sân bay đang vận hành thương mại, vì các sân bay thực tế luôn áp dụng quy trình điều phối can thiệp của kiểm soát viên mặt đất (ATC/Apron Control).

---

## 2. PHÂN BIỆT VỀ MẶT KHÁI NIỆM: THỰC NGHIỆM PRICE OF UNCERTAINTY VS. TOÁN HỌC EVPI

1. **Khái niệm Expected Value of Perfect Information (EVPI):**
   - Trong lý thuyết Tối ưu hóa ngẫu nhiên (Stochastic Programming), $\text{EVPI} = \mathbb{E}_\xi [\min_x c(x, \xi)] - \min_x \mathbb{E}_\xi [c(x, \xi)]$ là một đại lượng toán học chính xác đo lường giá trị kỳ vọng của thông tin hoàn hảo dưới phân phối tiên nghiệm đã biết, với giả định tất cả các bài toán tối ưu được giải tới **nghiệm tối ưu toàn cục tuyệt đối (exact global optimum)**.
2. **Bản chất của khoảng cách Mode B2 vs Mode C2 trong Aeolus:**
   - Khoảng cách chênh lệch thực nghiệm giữa Mode B2 và Mode C2 là $\Delta = 19.10 \pm 3.17$ ($p < 10^{-15}$).
   - Đây là **"Empirical Price of Uncertainty / Heuristic Recourse Gap"** đo lường sự kết hợp giữa:
     - Giá trị của việc không biết trước tương lai (online uncertainty).
     - Độ lệch giữa chiến lược heuristic rolling-horizon (Mode B2) và bộ giải quy hoạch nguyên CP-SAT có giới hạn thời gian $1.5$s (Mode C2).
   - **Tuyên bố minh bạch:** Báo cáo **không** đánh đồng khoảng cách thực nghiệm này với formal EVPI lý thuyết của bài toán quy hoạch ngẫu nhiên hai giai đoạn (two-stage stochastic program).

---

## 3. QUAN HỆ BẬC THANG GIỮA MODE B1 VÀ MODE B2 (RETROSPECTIVE VS. ONLINE)

1. **Bản chất hai thuật toán:**
   - **Mode B1 (Retrospective Recourse):** Nhìn thấy toàn bộ hiện thực kịch bản sau khi đã xảy ra, sau đó giải một lượt từ đầu đến cuối bằng thuật toán Greedy.
   - **Mode B2 (Rolling Online Recourse):** Hoạt động theo thời gian thực (causal / non-anticipative), chỉ được biết thông tin khi chuyến bay hạ cánh hoặc cất cánh, bảo vệ lịch bay hiện hành (incumbent protection) và tái gán cửa khi phát hiện xung đột.
2. **Giới hạn so sánh trên từng kịch bản đơn lẻ:**
   - Về mặt thống kê mẫu lớn ($N=500$), kỳ vọng chi phí của B1 ($130.73$) thấp hơn B2 ($139.49$) với ý nghĩa thống kê vượt trội ($t = -5.99, p = 4.0 \times 10^{-9}$).
   - Tuy nhiên, vì cả B1 và B2 đều sử dụng các quy tắc heuristics và tie-breaking, **không có sự bảo đảm toán học tuyệt đối (deterministic dominance)** rằng Mode B1 luôn có chi phí nhỏ hơn hoặc bằng Mode B2 trên từng realization riêng lẻ.

---

## 4. TÍNH TẤT ĐỊNH VÀ ĐỘ NHẠY ĐỐI VỚI SEED (DETERMINISM & SEED SENSITIVITY)

1. **Tái lập tất định (Single-Worker Determinism):**
   - Thí nghiệm được thực hiện trên môi trường đơn luồng/single-worker process với random seed cố định `seed = 202601`.
   - Bất kỳ hệ thống nào thực thi lại đúng mã nguồn, phiên bản dependency (Python 3.11, OR-Tools, NumPy, SciPy) và seed này sẽ thu được chính xác từng giá trị trong số $5,500$ dòng ledger entries mà không có bất kỳ sai lệch nào.
2. **Độ nhạy ngẫu nhiên (Seed Sensitivity):**
   - Nếu thay đổi seed khởi tạo ngẫu nhiên hoặc các tham số copula ($\rho \ne 0.45$), giá trị tuyệt đối của hàm mục tiêu trên từng realization sẽ thay đổi.
   - Tuy nhiên, phân tích cận tin cậy (Confidence Interval) và độ lệch chuẩn mẫu cho thấy cấu trúc thứ bậc $C2 \le B1 \le B2 \ll A$ mang tính bất biến về mặt cấu trúc (structurally invariant).

---

## 5. GIỚI HẠN TÍNH TOÁN CỦA BỘ GIẢI (SOLVER TIME LIMITS)

- Giới hạn thời gian $1.5$s cho CP-SAT trong Mode C2 là một thỏa hiệp thực tế cho phép chạy $500$ scenarios trong khoảng thời gian $\approx 3.4$ phút.
- Giới hạn này đảm bảo $99.8\%$ số bài toán đạt nghiệm tối ưu toàn cục được chứng minh bằng toán học (provably optimal status), và $0.2\%$ đạt nghiệm khả thi chất lượng cao (status feasible).
- Nếu kéo dài time limit (ví dụ lên $30$s hoặc $60$s), scenario `MC_REM_S0183` có thể được chứng minh tối ưu toàn cục, nhưng sự khác biệt về hàm mục tiêu kỳ vọng trên toàn bộ $500$ realizations là không đáng kể ($< 0.01\%$).
