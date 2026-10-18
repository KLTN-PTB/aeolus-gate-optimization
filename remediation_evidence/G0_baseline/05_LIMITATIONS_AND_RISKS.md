# AEOLUS-G0: BÁO CÁO GIỚI HẠN KHOA HỌC VÀ MA TRẬN RỦI RO (LIMITATIONS & RISK MATRIX)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Giai đoạn:** AEOLUS-G0 — Baseline, Source Preservation & Rollback Gate  
**Thời điểm thực hiện:** 2026-10-11T16:33:00+07:00  
**Vai trò:** Senior Risk Engineer, Scientific Integrity Auditor  

---

## 1. Giới hạn Kỹ thuật & Khoa học của Hệ thống Hiện tại (Technical & Scientific Limitations)

### 1.1. Giới hạn Bộ giải Tối ưu hóa (Solver Limitations)
1. **Ngưỡng Giới hạn Quy mô của CP-SAT (Scalability Horizon):**
   * Ở quy mô $N \le 300$ chuyến bay: CP-SAT giải ra nghiệm **TỐI ƯU TOÀN CỤC (OPTIMAL)** trong dưới 32 giây.
   * Ở quy mô $N = 500$ chuyến bay: CP-SAT tìm thấy nghiệm **KHẢ THI (FEASIBLE)** trong 10 giây.
   * Ở quy mô $N \ge 750$ chuyến bay: Với giới hạn thời gian 10 giây, trạng thái bộ giải trả về là **`UNKNOWN`** (hết thời gian tìm kiếm mà chưa kịp tìm thấy nghiệm nguyên khả thi đầu tiên).
   * *Rủi ro:* Cấm tuyên bố CP-SAT giải tối ưu được 1.500 chuyến bay trong 10 giây; cần ghi đúng trạng thái `UNKNOWN` và giải thích đây là giới hạn ngân sách thời gian thực tế.
2. **Sự Bất lực của Thuật toán Lai Hybrid (SA + CP-SAT):**
   * Thuật toán Simulated Annealing khi nhận lời giải ban đầu từ CP-SAT đạt **0.00% tỷ lệ cải thiện** trên toàn bộ 40 kịch bản thực nghiệm.
   * *Nguyên nhân toán học:* CP-SAT đã tìm ra nghiệm tối ưu toàn cục; các phép biến đổi lân cận (neighborhood operators) của SA không thể tìm ra nghiệm có giá trị mục tiêu thấp hơn.
   * *Rủi ro:* Tuyên bố "Hybrid kết hợp CP-SAT và SA vượt trội hơn CP-SAT" là sai lệch toán học.

### 1.2. Giới hạn Mô hình Học máy & Dữ liệu (Machine Learning Limitations)
1. **Mô hình P5 Quantile Regression Thiếu Checkpoint Vật lý:**
   * P5 là nhà vô địch hồi quy phân vị (Role B) nhưng chỉ lưu trữ kết quả dự báo trong bảng ngoại tuyến, không có tệp checkpoint serialized trên đĩa. Do đó, P5 **không thể tham gia suy luận trực tuyến trong runtime**.
2. **Xác suất Trễ Outbound Dùng Hàm Sigmoid Heuristic:**
   * Chiều Đi (Outbound) chưa có mô hình phân loại nhị phân thực thụ; xác suất $P(\text{delay} \ge 15)$ được tính bằng phép xấp xỉ đơn điệu $\frac{1}{1 + \exp(-(\hat{y}-15)/10)}$.
3. **Phong tỏa Dữ liệu Thời tiết và Chuỗi bay:**
   * Dữ liệu thời tiết thô (METAR surface observations) và chuỗi bay tái dựng (Flight Chain) bị phong tỏa để ngăn chặn rò rỉ thông tin tương lai tại mốc cắt $T-2\text{h}$.

### 1.3. Giới hạn Mô phỏng Monte Carlo P09 (Monte Carlo Limitations)
1. **Mode C Oracle Được Giải bằng Heuristic Greedy:**
   * Cận dưới lý thuyết hoàn hảo (Mode C Perfect Foresight) sử dụng thuật toán tham lam `DeterministicGreedyGateSolver` thay vì CP-SAT giải tối ưu toàn cục.
2. **Đánh đồng Infeasibility Tĩnh với Xung đột Vật lý:**
   * Tỷ lệ Feasibility = 0% trong Mode A thực chất do sai lệch mốc thời gian tĩnh (`timeline_mismatch_violations`), trong khi thực tế có **25.2% kịch bản (126/500) hoàn toàn không có xung đột vật lý** giữa các máy bay trên cổng đỗ.

---

## 2. Ma trận Rủi ro Học thuật & Kế hoạch Giảm thiểu (Risk Matrix & Mitigations)

| Mã Rủi ro | Mô tả Rủi ro Học thuật / Vận hành | Mức độ | Ảnh hưởng Tiềm tàng | Kế hoạch Giảm thiểu Bắt buộc (Mitigation Plan) |
| :---: | :--- | :---: | :--- | :--- |
| **RISK-01** | **Thiếu Quyển Khóa luận và Slide trong Repo** | `P0` | Sinh viên không có văn bản chính thức để nộp và bảo vệ trước Hội đồng. | Sử dụng dữ liệu kiểm toán đã freeze để viết Quyển Khóa luận và Slide thuyết trình ngay lập tức. |
| **RISK-02** | **Bị Hội đồng bắt bẻ Mode C Oracle** | `P0` | Giảng viên phản biện chỉ ra Mode C không tối ưu vì dùng Greedy. | Công bố minh bạch trong khóa luận: Mode C là "Greedy Foresight Heuristic" để bảo đảm thời gian chạy 500 kịch bản. |
| **RISK-03** | **Nhầm lẫn nhãn Master's Thesis** | `P1` | Gây hiểu lầm về cấp độ đào tạo cử nhân. | Chuẩn hóa toàn bộ văn bản và slide về danh xưng "Khóa luận Cử nhân CNTT". |
| **RISK-04** | **Bị chất vấn về việc cấm Weather & Chain** | `P1` | Bị coi là chưa khai thác hết dữ liệu đề tài. | Trình bày tự tin nguyên tắc bảo toàn tính chân thực khoa học: METAR tại giờ bay là rò rỉ tương lai tại cutoff $T-2\text{h}$. |
| **RISK-05** | **Lỗi hiển thị Dashboard khi demo thật** | `P2` | Phát sinh lỗi vỡ layout hoặc tràn chữ trên máy chiếu. | Thực hiện một buổi chạy thử trực tiếp trên trình duyệt máy tính (`streamlit run dashboard/app.py`) trước buổi bảo vệ. |
