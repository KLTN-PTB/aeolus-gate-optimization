# AEOLUS-G9 — Đề Cương Khóa Luận Tốt Nghiệp Cử Nhân CNTT Chi Tiết

## 1. THÔNG TIN KHÓA LUẬN VÀ QUY CHUẨN ĐÀO TẠO

- **Tên đề tài**: *Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay*
- **Sinh viên thực hiện**: Phùng Thế Bảo
- **Mã đề cương**: `CNTT-KLCN168`
- **Hệ đào tạo**: Cử nhân Công nghệ Thông tin (Chương trình đào tạo đại học chính quy)
- **Thời gian thực hiện**: 10/08/2026 – 25/10/2026 (12 tuần)
- **Đơn vị đào tạo**: Khoa Công nghệ Thông tin
- **Khung lý thuyết chủ đạo**: Mô hình Dự báo kết hợp Tối ưu hóa (Predict-then-Optimize Framework), Học máy xác suất (Probabilistic ML), Lập trình ràng buộc (Constraint Programming - CP-SAT), Tối ưu hóa siêu siêu nghiệm (Simulated Annealing), Mô phỏng Monte Carlo đa kịch bản.

---

## 2. BẢNG ĐỐI CHIẾU 10 MỤC TIÊU ĐỀ CƯƠNG VÀ CÁC CHƯƠNG KHÓA LUẬN

| Mã Mục tiêu | Nội dung Mục tiêu Đề cương | Chương Luận văn Phụ trách | Mức độ Hoàn thành (G8 Certified) |
|:---:|:---|:---:|:---:|
| **REQ-01** | Tiền xử lý dữ liệu Aeolus (ATL, xử lý giá trị khuyết, rào chắn $T-2\text{h}$). | Chương 3 (Mục 3.1, 3.2, 3.3) | **`FULLY_ACCEPTED`** |
| **REQ-02** | Dự báo xác suất trễ $P(\text{delay} \ge 15)$ và mức độ trễ (LR, RF, XGBoost). | Chương 3 (Mục 3.4), Chương 5 (Mục 5.1, 5.2) | **`ACCEPTED_WITH_LIMITATION`** |
| **REQ-03** | Tối ưu siêu tham số Optuna HPO và đánh giá phân chia thời gian (Temporal Split). | Chương 3 (Mục 3.2), Chương 5 (Mục 5.1) | **`FULLY_ACCEPTED`** |
| **REQ-04** | So sánh Tabular và Tabular + Flight Chain (nghiên cứu cắt bỏ đặc trưng). | Chương 3 (Mục 3.3), Chương 5 (Mục 5.3) | **`PARTIAL` (Nghiên cứu Khám phá)** |
| **REQ-05** | Xây dựng CP-SAT với 100% ràng buộc cứng (cổng tiếp xúc, đệm 15m, sức chứa). | Chương 3 (Mục 3.5), Chương 4 (Mục 4.3), Chương 5 (Mục 5.4) | **`FULLY_ACCEPTED`** |
| **REQ-06** | Ứng dụng Simulated Annealing để cải thiện nghiệm phân bổ cổng. | Chương 2 (Mục 2.4), Chương 4 (Mục 4.3), Chương 5 (Mục 5.5) | **`FULLY_ACCEPTED`** |
| **REQ-07** | So sánh giải thuật Greedy, CP-SAT và Hybrid (CP-SAT + SA) trên benchmark công bằng. | Chương 4 (Mục 4.3), Chương 5 (Mục 5.5) | **`FULLY_ACCEPTED`** |
| **REQ-08** | Mô phỏng Monte Carlo đa kịch bản ngẫu nhiên và đánh giá độ bền vững (Robustness). | Chương 3 (Mục 3.6), Chương 4 (Mục 4.4), Chương 5 (Mục 5.6) | **`ACCEPTED_WITH_LIMITATION`** |
| **REQ-09** | Bảng điều khiển (Streamlit Dashboard) trực quan hóa Gantt, cảnh báo, tối ưu và mô phỏng. | Chương 4 (Mục 4.5), Chương 5 (Mục 5.8) | **`ACCEPTED_WITH_LIMITATION`** |
| **REQ-10** | Thực nghiệm tập con dữ liệu Aeolus (20–50 cổng, 100–300 chuyến bay/ngày). | Chương 5 (Mục 5.4, 5.7) | **`ACCEPTED_WITH_LIMITATION`** |

---

## 3. CẤU TRÚC CHI TIẾT CỦA BẢN THẢO KHÓA LUẬN (6 CHƯƠNG)

### LỜI CAM ĐOAN
### LỜI CẢM ƠN
### MỤC LỤC & DANH MỤC TỪ VIẾT TẮT
### DANH MỤC BẢNG BIỂU & HÌNH VẼ

---

### CHƯƠNG 1: TỔNG QUAN VÀ BỐI CẢNH ĐỀ TÀI
- **1.1. Bối cảnh ngành hàng không và thách thức trễ chuyến bay**
  - Thực trạng tăng trưởng vận tải hàng không toàn cầu và tại các sân bay trung chuyển (Hub Airport).
  - Tác động dây chuyền của trễ chuyến bay đến chi phí hãng hàng không, dịch vụ mặt đất và hành khách.
  - Sân bay Quốc tế Hartsfield-Jackson Atlanta (ATL) như một trường hợp nghiên cứu điển hình.
- **1.2. Bài toán phân bổ và tái phân bổ cổng đỗ tàu bay (Gate Assignment & Reassignment Problem - AGAP)**
  - Phân bổ tĩnh theo lịch trình (Static Gate Allocation) và sự phá vỡ kế hoạch do biến động thời gian thực.
  - Yêu cầu chuyển dịch từ phân bổ tiền định sang phân bổ thích ứng có dự báo trễ (Predict-then-Optimize).
- **1.3. Mục tiêu và phạm vi nghiên cứu**
  - Mục tiêu nghiên cứu: Xây dựng pipeline tích hợp giữa học máy dự báo trễ và tối ưu ràng buộc toán học.
  - Phạm vi nghiên cứu: Dữ liệu bay nội địa ATL từ CSDL Aeolus/BTS TranStats; quy mô 20–50 cổng đỗ, 100–300 chuyến/ngày.
  - Ranh giới đề tài: Khóa luận cử nhân CNTT tập trung vào phương pháp luận kỹ thuật phần mềm, học máy và vận trù học; không triển khai tích hợp radar thực tế.
- **1.4. Đóng góp khoa học và thực tiễn của khóa luận**
  - Đóng góp 1: Xây dựng kiến trúc Hai lõi (Dual-Core) dự báo đồng thời độ trễ đến (Inbound) và đi (Outbound) tuân thủ rào chắn thời gian nghiêm ngặt $T-2\text{h}$.
  - Đóng góp 2: Mô hình hóa bài toán AGAP bằng quy hoạch ràng buộc CP-SAT với biến khoảng (Interval Variables), triệt tiêu bùng nổ ràng buộc so với mô hình MIP truyền thống.
  - Đóng góp 3: Thiết kế động cơ mô phỏng Monte Carlo nhân quả không nhìn trước tương lai (Causal Non-anticipative Recourse - Mode B2), tách bạch xung đột vật lý và lệch khe giờ danh định.
  - Đóng góp 4: Phát triển bảng điều khiển vận hành tương tác Streamlit với cơ chế kiểm soát nguồn gốc dữ liệu chống ngụy tạo.
- **1.5. Cấu trúc của khóa luận**

---

### CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC CÔNG TRÌNH LIÊN QUAN
- **2.1. Tổng quan các phương pháp dự báo độ trễ chuyến bay**
  - Dự báo phân loại nhị phân ($P(\text{delay} \ge 15)$) và hồi quy giá trị trễ liên tục.
  - Các thuật toán học máy giám sát: Hồi quy Logistic, Rừng ngẫu nhiên (Random Forest), Tăng cường độ dốc (Gradient Boosting / XGBoost).
  - Học máy xác suất (Probabilistic Machine Learning) và mô hình NGBoost với phân phối Student-t.
- **2.2. Khung làm việc Dự báo kết hợp Tối ưu hóa (Predict-then-Optimize)**
  - So sánh giữa tiếp cận tuần tự rời rạc (Decoupled sequential) và tiếp cận tích hợp bất định (Stochastic / Robust).
  - Tác động của hàm mất mát ML đến nghiệm tối ưu vận trù: Nghịch lý hàm mất mát $L_1$ (MAE) và $L_2$ (RMSE/Variance).
- **2.3. Lập trình ràng buộc và bộ giải CP-SAT**
  - Nguyên lý giải bài toán thỏa mãn ràng buộc và tối ưu hóa tổ hợp (Constraint Programming & SAT Solving).
  - Biến khoảng thời gian (`NewIntervalVar`) và ràng buộc không đè chồng (`AddNoOverlap`).
- **2.4. Thuật toán tôi luyện thép mô phỏng (Simulated Annealing - SA)**
  - Nguyên lý nhiệt động lực học Metropolis-Hastings trong tìm kiếm cục bộ metaheuristic.
  - Vai trò của SA: Cải thiện nghiệm tham lam (Greedy) và vai trò giải pháp dự phòng tài nguyên hữu hạn (Safety Fallback).
- **2.5. Phương pháp mô phỏng Monte Carlo và phụ thuộc đa chiều**
  - Đánh giá độ bền vững của kế hoạch phân bổ dưới biến động ngẫu nhiên.
  - Mô hình phụ thuộc Gaussian Copula giữa trễ chuyến đến và trễ chuyến đi của cùng tàu bay.
  - Kỹ thuật biến ngẫu nhiên chung (Common Random Numbers - CRN) trong so sánh bắt cặp.
- **2.6. Tổng quan các nghiên cứu liên quan và khoảng trống nghiên cứu**
  - Bảng tổng hợp các công trình quốc tế về AGAP và dự báo trễ (2018–2025).
  - Khoảng trống nghiên cứu được đề tài giải quyết: Ngăn chặn rò rỉ thông tin trong chuỗi quay đầu và tính toán nhân quả trong mô phỏng ứng phó.

---

### CHƯƠNG 3: DỮ LIỆU, PHƯƠNG PHÁP VÀ MÔ HÌNH TOÁN HỌC
- **3.1. Nguồn dữ liệu Aeolus và phân vùng nghiên cứu**
  - Tập dữ liệu BTS TranStats: Đặc trưng chuyến bay, hãng vận chuyển, cự ly, thời gian danh định và thực tế.
  - Quy chuẩn lọc sân bay trung chuyển ATL: Chuyến đến (`DEST == 'ATL'`) và Chuyến đi (`ORIGIN == 'ATL'`).
  - Xử lý giá trị khuyết và chuẩn hóa đơn vị thời gian (Monotonic Timeline Minutes).
- **3.2. Chiến lược phân chia dữ liệu theo thời gian (Temporal Split)**
  - Nguyên tắc chống rò rỉ tương lai: Phân vùng Huấn luyện/Phát triển (2016–2022), Chọn mô hình (2023), và Vùng cấm bảo lưu (2024).
  - Cơ chế tối ưu hóa siêu tham số bằng Optuna trên phân vùng phát triển.
- **3.3. Rào chắn thông tin thời gian $T-2\text{h}$ và kỹ thuật tạo đặc trưng**
  - Định nghĩa điểm chặn thông tin $T_{\text{cutoff}} = T_{\text{sched}} - 120$ phút.
  - Bộ đặc trưng dạng bảng (Tabular Features): Lịch trình, thời gian trong ngày, ngày trong tuần, mùa vụ, thống kê trễ lịch sử theo hãng và tuyến bay.
  - Phân tích rò rỉ dữ liệu và lý do phong tỏa chuỗi chuyến bay (Flight Chain) và thời tiết quan trắc (METAR) khỏi luồng vận hành chính.
- **3.4. Mô hình học máy dự báo độ trễ Hai lõi (Dual-Core ML Pipeline)**
  - Lõi Đến (Inbound Core): Mô hình hồi quy phân phối NGBoost Student-t (P4) tạo hàm mật độ xác suất trễ.
  - Lõi Đi (Outbound Core): Mô hình hồi quy XGBoost và bộ phân loại xác suất $P(\text{delay} \ge 15)$ được hiệu chuẩn (Platt / Isotonic Calibration).
- **3.5. Mô hình toán học phân bổ cổng đỗ tàu bay (CP-SAT Mathematical Formulation)**
  - Tập hợp, chỉ số và tham số: Tập chuyến bay $\mathcal{F}$, tập cổng đỗ $\mathcal{G}$, cửa sổ chiếm dụng $[S_i, E_i)$, đệm phân cách $\Delta = 15$ phút.
  - Biến quyết định: Phân bổ nhị phân $x_{i,g} \in \{0, 1\}$, biến khoảng $I_{i,g}$.
  - Hệ ràng buộc cứng (Hard Constraints):
    - (C1) Phân bổ duy nhất: $\sum_{g \in \mathcal{G}} x_{i,g} = 1, \quad \forall i \in \mathcal{F}$.
    - (C2) Không đè chồng trên cổng tiếp xúc: $\text{NoOverlap}(I_{i,g}, I_{j,g}), \quad \forall i \neq j, \forall g \in \mathcal{G}_{\text{contact}}$.
    - (C3) Sức chứa hữu hạn của bãi đỗ xa: $\text{Cumulative}(I_{i,\text{remote}}, 1, K_{\text{remote}})$.
    - (C4) Tương thích loại tàu bay và hãng hàng không: $x_{i,g} = 0, \quad \forall (i, g) \notin \text{Compatible}$.
    - (C5) Thời gian quay đầu tối thiểu: $E_i - S_i \ge T_{\text{min\_turn}}$.
  - Hàm mục tiêu đa thành phần (Objective Function):
    - Tách bạch Chi phí Quyết định ($J_{\text{decision}}$) gồm đổi cổng danh định, đưa ra bãi đỗ xa, xung đột mềm.
    - Chi phí Báo cáo ngoại sinh ($J_{\text{reporting}}$) gồm phạt trễ ngoại sinh và rủi ro thời gian đệm.
- **3.6. Mô hình mô phỏng Monte Carlo nhân quả (Causal Monte Carlo Framework)**
  - Tạo kịch bản ngẫu nhiên bằng Gaussian Copula kết hợp phân phối Student-t hai chiều.
  - Ba chế độ mô phỏng:
    - Mode A (Fixed Plan): Kế hoạch tĩnh đóng băng, 0 tối ưu lại.
    - Mode B1 (Retrospective Recourse): Tái phân bổ biết trước tương lai hoàn hảo (phi vận hành).
    - Mode B2 (Rolling Horizon Online Recourse): Tái phân bổ phi tiên nghiệm theo dòng sự kiện thời gian thực.
    - Mode C (Foresight Oracle): Cận dưới lý thuyết giải bằng CP-SAT tối ưu toàn cục.
  - Phân rã 5 chiều khả thi: Xung đột cổng tiếp xúc, vi phạm đệm, quá tải bãi đỗ xa, chuyến bay không gán, lệch khe giờ tĩnh.

---

### CHƯƠNG 4: THIẾT KẾ VÀ KIẾN TRÚC HỆ THỐNG
- **4.1. Kiến trúc tổng thể hệ thống Aeolus Gate Optimization**
  - Sơ đồ kiến trúc 4 tầng: Tầng Dữ liệu & Hợp đồng $\to$ Tầng Lõi Học máy $\to$ Tầng Động cơ Tối ưu & Mô phỏng $\to$ Tầng Ứng dụng & Trực quan hóa.
- **4.2. Thiết kế hợp đồng dữ liệu và kiểm soát xuất xứ (Data Provenance & Lineage)**
  - Module `src.contracts.provenance`: Phân loại xuất xứ `REAL_AEOLUS`, `SYNTHETIC_CANONICAL`, `INFERRED`.
  - Bộ kiểm tra Fail-Closed chống ngụy tạo nhãn và ngăn chặn rò rỉ dữ liệu khi xuất tệp.
- **4.3. Động cơ ghép cặp chuyến bay quay đầu (Deterministic Pairing Engine)**
  - Thuật toán ghép cặp xác định bảo toàn bất biến hoán vị.
  - Quy tắc phân loại nghiêm ngặt: `VERIFIED_ROTATION`, `INFERRED_PAIR`, `UNMATCHED_ARR`, `UNMATCHED_DEP`.
- **4.4. Triển khai các bộ giải tối ưu và kiểm định độc lập**
  - Bộ giải CP-SAT Solver (`CPSatGateSolver`).
  - Bộ giải Tham lam đơn định (`DeterministicGreedyGateSolver`).
  - Bộ giải Tôi luyện thép mô phỏng (`SimulatedAnnealingGateSolver`).
  - Bộ giải Lai hai giai đoạn (`HybridGateSolver`).
  - Bộ kiểm định ràng buộc cứng độc lập (`verify_hard_constraints_independently`).
- **4.5. Thiết kế bảng điều khiển vận hành Streamlit (Dashboard Architecture)**
  - Cấu trúc 5 trang chức năng: Đài Kiểm soát (Control Tower), Trí tuệ Chuyến bay (Flight Intelligence), Vận hành Cổng (Gate Operations), Phòng thí nghiệm Tối ưu (Optimization Lab), Phòng kiểm thử Độ bền vững (Robustness Lab).
  - Phân tách hai chế độ hiển thị: Presentation Mode (trình diễn đại chúng) và Research Mode (phân tích chuyên sâu).
  - Cơ chế bảo mật cách ly thư mục (Canonical Path Containment).

---

### CHƯƠNG 5: KẾT QUẢ THỰC NGHIỆM VÀ THẢO LUẬN
- **5.1. Kết quả thực nghiệm dự báo độ trễ chuyến bay**
  - Đánh giá phân loại trễ khởi hành Outbound: Đường cong ROC, PR, điểm Brier Score và độ tin cậy hiệu chuẩn ECE.
  - Đánh giá hồi quy trễ: Phân tích so sánh giữa Median Baseline, Ridge và XGBoost.
  - Giải thích nghịch lý MAE và sự vượt trội của ML ở sai số đuôi nặng.
- **5.2. Đánh giá mô hình học máy xác suất NGBoost Student-t**
  - Độ phủ phân vị và khả năng nắm bắt độ trễ bất định phục vụ lấy mẫu mô phỏng.
- **5.3. Kết quả phân tích cắt bỏ đặc trưng (Feature Ablation Study)**
  - Đánh giá thực nghiệm giữa Tabular, Flight Chain và Weather; đối soát lý do khoa học của việc phong tỏa rò rỉ thông tin.
- **5.4. Đánh giá hiệu năng và tính tối ưu của bộ giải CP-SAT**
  - Đối chiếu kiểm chứng nghiệm tối ưu với Exhaustive Combinatorial Oracle.
  - Mức độ cải thiện chi phí của CP-SAT so với bộ giải Tham lam (Greedy) trên các quy mô 100, 200, 300 chuyến bay.
- **5.5. Đánh giá bộ giải Tôi luyện thép mô phỏng (SA) và Bộ giải Lai (Hybrid)**
  - Năng lực cải thiện của SA đối với nghiệm Greedy.
  - Chứng minh định lý cải thiện 0.00% của Hybrid khi nghiệm CP-SAT đã đạt tối ưu toàn cục.
- **5.6. Kết quả mô phỏng Monte Carlo và đánh giá độ bền vững**
  - So sánh phân phối chi phí và tỷ lệ vi phạm giữa Mode A, Mode B1, Mode B2 và Mode C.
  - Giá trị của Tái phân bổ (Value of Recourse) và Giá trị của Thông tin (Value of Information).
  - Phân tích rủi ro đuôi với chỉ số CVaR (Conditional Value-at-Risk).
- **5.7. Thử nghiệm tích hợp luồng dữ liệu thực tế (Thanksgiving 2023 ATL)**
  - Thực nghiệm trên 200 chuyến bay thật với checkpoint ML nguyên bản; phân tích minh bạch tình trạng khuyết cột số hiệu đuôi máy bay trong CSDL mở.
- **5.8. Thử nghiệm và đánh giá bảng điều khiển vận hành Streamlit**
  - Kết quả kiểm thử tự động 359 test headless và kịch bản vận hành thực tế.

---

### CHƯƠNG 6: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN
- **6.1. Những kết quả chính đã đạt được và chứng minh thực nghiệm**
  - Tổng kết các mục tiêu kỹ thuật và đề cương đã hoàn thành xuất sắc.
- **6.2. Các giới hạn khoa học bắt buộc công bố**
  - Tóm tắt 10 giới hạn khoa học của đề tài (dữ liệu đuôi tàu bay, rào chắn $T-2\text{h}$, v.v.).
- **6.3. Đóng góp thực tiễn và giá trị chuyển giao**
  - Ứng dụng tiềm năng cho trung tâm điều hành sân bay (AOCC) tại Việt Nam (Nội Bài, Tân Sơn Nhất, Long Thành).
- **6.4. Hướng nghiên cứu và phát triển tiếp theo**
  - Tích hợp radar ADS-B thời gian thực, mở rộng quy hoạch kéo dắt tàu bay (Towing Routing) và tối ưu hóa đa mục tiêu với phát thải carbon.

---

### TÀI LIỆU THAM KHẢO
### PHỤ LỤC: HƯỚNG DẪN CÀI ĐẶT VÀ TÁI LẬP HỆ THỐNG
