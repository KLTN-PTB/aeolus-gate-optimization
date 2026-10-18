# AEOLUS-G9 — Nội Dung Slide Thuyết Trình Khóa Luận Tốt Nghiệp

Tài liệu này chuẩn hóa toàn bộ nội dung kịch bản trình chiếu cho buổi bảo vệ khóa luận cử nhân CNTT (17 slide tiêu chuẩn). Bố cục được thiết kế khoa học, trực quan, cô đọng số liệu chính và bám sát các phát hiện đã được thẩm định độc lập tại Gate G8.

---

## SLIDE 1: TRANG TIÊU ĐỀ (TITLE SLIDE)
- **Tên đề tài**: **ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**
- **Tiếng Anh**: *Machine Learning and Constraint Programming for Flight Delay Prediction and Airport Gate Reallocation*
- **Sinh viên thực hiện**: Phùng Thế Bảo (Mã đề cương: `CNTT-KLCN168`)
- **Ngành đào tạo**: Cử nhân Công nghệ Thông tin
- **Thời gian thực hiện**: 10/08/2026 – 25/10/2026
- **Địa điểm & Năm**: Hà Nội, 10/2026

---

## SLIDE 2: BỐI CẢNH VÀ ĐỘNG LỰC NGHIÊN CỨU (CONTEXT & MOTIVATION)
- **Thực trạng**: Các sân bay trung chuyển lớn (như ATL với hơn 300 cổng đỗ, 2.500 chuyến/ngày) luôn đối mặt với tình trạng tắc nghẽn và trễ chuyến dây chuyền.
- **Vấn đề thực tiễn**: Kế hoạch phân bổ cổng đỗ tĩnh (Static Gate Assignment) lập trước 24 giờ thường xuyên bị phá vỡ khi trễ xảy ra trong ngày:
  - Tàu bay đến sớm/trễ đè cổng nhau $\to$ Xung đột vật lý (Physical Conflicts).
  - Tàu bay phải chờ trên đường lăn (Taxiway delay) $\to$ Tốn nhiên liệu, phát thải CO2, trễ chuyến tiếp theo.
- **Nhu cầu cấp thiết**: Cần một hệ thống **Dự báo kết hợp Tối ưu hóa (Predict-then-Optimize)** để tự động thích ứng và tái phân bổ cổng theo thời gian thực.

---

## SLIDE 3: ĐẶT TẢ BÀI TOÁN AGAP (PROBLEM FORMULATION)
- **Bài toán Phân bổ Cổng đỗ Tàu bay (Airport Gate Assignment Problem - AGAP)**:
  - Đầu vào: Danh sách chuyến bay đến/đi, cửa sổ chiếm dụng cổng danh định $[S_i, E_i)$, ma trận cổng đỗ.
  - Ràng buộc: Mỗi chuyến đúng 1 cổng; không trùng lịch trên cổng tiếp xúc; đệm an toàn 15 phút; tương thích loại tàu bay.
  - Mục tiêu: Cực tiểu hóa chi phí đổi cổng, hạn chế đưa ra bãi đỗ xa, và giảm thiểu rủi ro lan truyền trễ.
- **Thách thức Cốt lõi**:
  - Không gian tìm kiếm tổ hợp bùng nổ theo hàm mũ $O(M^N)$.
  - Trễ chuyến bay mang tính bất định, đuôi nặng và có tương quan giữa chuyến đến và chuyến đi.

---

## SLIDE 4: MỤC TIÊU VÀ PHẠM VI NGHIÊN CỨU (OBJECTIVES & SCOPE)
- **Mục tiêu Trọng tâm**:
  1. Xây dựng pipeline học máy dự báo độ trễ Hai lõi (Dual-Core: Inbound & Outbound) tuân thủ rào chắn thời gian $T-2\text{h}$.
  2. Mô hình hóa và giải bài toán AGAP bằng Lập trình ràng buộc CP-SAT.
  3. Đánh giá thuật toán Metaheuristic (Simulated Annealing) và giải thuật Lai (Hybrid).
  4. Kiểm định độ bền vững qua mô phỏng Monte Carlo nhân quả đa kịch bản (Causal Recourse).
  5. Phát triển Dashboard vận hành trực quan hỗ trợ điều hành bay AOCC.
- **Ranh giới Phạm vi (Scope)**:
  - Dữ liệu thực tế: Sân bay Quốc tế Atlanta (ATL) từ CSDL BTS TranStats Hoa Kỳ.
  - Quy mô thử nghiệm: 20–50 cổng đỗ, 100–300 chuyến bay/ngày.
  - Khóa luận Cử nhân CNTT tập trung vào thuật toán và phần mềm; không tích hợp radar thời gian thực.

---

## SLIDE 5: DỮ LIỆU VÀ RÀO CHẮN THỜI GIAN (DATASET & LEAKAGE BARRIER)
- **CSDL Aeolus / BTS TranStats tại ATL**: Tổng số $3,142,850$ chuyến bay (2016–2024).
- **Phân chia theo dòng thời gian (Temporal Split)**:
  - *2016–2022 (Huấn luyện & HPO)*: 2,468,116 chuyến bay.
  - *2023 (Kiểm định & Chọn mô hình)*: 332,734 chuyến bay ($20.63\%$ trễ $\ge 15$m).
  - *2024 (Bảo lưu)*: 342,000 chuyến bay.
- **Rào chắn Thông tin $T-2\text{h}$**:
  - Quyết định điều hành chốt trước giờ bay 2 tiếng: $T_{\text{cutoff}} = T_{\text{sched}} - 120$ phút.
  - Loại trừ triệt để thời tiết quan trắc METAR và chuỗi chuyến bay Flight Chain khỏi luồng vận hành chính để đảm bảo 100% không rò rỉ thông tin tương lai.

---

## SLIDE 6: KIẾN TRÚC HỆ THỐNG AEOLUS (SYSTEM ARCHITECTURE)
- **Kiến trúc 4 Tầng Tích hợp**:
  1. **Tầng Hợp đồng Dữ liệu (Contracts & Provenance)**: Kiểm soát xuất xứ dữ liệu (`REAL_AEOLUS`, `SYNTHETIC`), chuẩn hóa đơn vị phút, Fail-Closed khi thiếu dữ liệu.
  2. **Tầng Học máy Hai lõi (Dual-Core ML)**: Lõi Đến P4 NGBoost Student-t + Lõi Đi XGBoost Regressor & Calibrated Classifier.
  3. **Tầng Tối ưu & Kiểm định (OR Solvers & Verifier)**: CP-SAT, Greedy, SA, Hybrid + Bộ kiểm tra ràng buộc độc lập.
  4. **Tầng Mô phỏng & Ứng dụng (Simulation & Dashboard)**: Monte Carlo (Mode A/B2/C) + Streamlit Dashboard 5 trang.

---

## SLIDE 7: PHƯƠNG PHÁP HỌC MÁY HAI LÕI (DUAL-CORE ML METHODOLOGY)
- **Lõi Chuyến Đến (Core Arrival — Continuous Probabilistic)**:
  - Mô hình: **NGBoost với phân phối Student-t (P4)**.
  - Đầu ra: Hàm mật độ xác suất trễ liên tục $f(t)$ với tham số $(\mu, \sigma, \nu)$. Bậc tự do $\nu = 4.5$ nắm bắt rủi ro đuôi nặng phục vụ lấy mẫu mô phỏng.
- **Lõi Chuyến Đi (Core Departure — Point & Calibrated Probability)**:
  - Hồi quy mức trễ: **XGBoost Regressor** tối ưu hóa theo hàm mất mát bình phương ($L_2$).
  - Phân loại xác suất trễ: **Calibrated XGBoost Classifier** với hiệu chuẩn Isotonic Regression, đưa ra xác suất thực sự $P(\text{delay} \ge 15 \text{ phút})$.

---

## SLIDE 8: KẾT QUẢ THỰC NGHIỆM DỰ BÁO ĐỘ TRỄ (ML EMPIRICAL RESULTS)
- **Kết quả Phân loại Xác suất Trễ Khởi hành ($N = 332,734$)**:
  - *Điểm Brier Score*: Giảm từ $0.1678$ (cơ sở) xuống **$0.1564$** (XGBoost Calibrated).
  - *Sai số Hiệu chuẩn ECE*: Đạt **$0.0119$** (vượt xa mục tiêu chuẩn $\le 0.05$).
  - *Chỉ số PR-AUC*: Đạt **$0.3292$** (vượt trội so với ngưỡng ngẫu nhiên $0.2062$).
- **Kết quả Hồi quy và Giải thích Nghịch lý MAE**:
  - *MAE Toàn tập*: Median Baseline ($15.60$m) thấp hơn XGBoost ($17.60$m) do tính chất toán học tối ưu $L_1$ trên $>70\%$ chuyến bay đúng giờ.
  - *RMSE Toàn tập*: XGBoost đạt **$43.00$m** (vượt trội hơn Median $45.76$m).
  - *Nhóm trễ nặng $\ge 15$m*: XGBoost đạt **$48.91$m** (giảm tới **$21.5\%$** sai số so với Median $62.33$m).
  - *Nhóm trễ nặng $\ge 60$m*: XGBoost đạt **$117.18$m** (vượt trội hơn Median $132.54$m).

---

## SLIDE 9: MÔ HÌNH TOÁN HỌC CP-SAT (CP-SAT FORMULATION)
- **Mô hình hóa bằng Biến Khoảng (Interval Variables)**:
  - Sử dụng `NewIntervalVar` của Google OR-Tools: $I_{i,g} = [start_i, end_i, duration_i]$.
  - Ràng buộc không đè chồng: $\text{AddNoOverlap}(I_{i,g}, I_{j,g})$ cho mọi chuyến bay tại cổng tiếp xúc.
  - Đệm phân cách: Tự động cộng dồn $\Delta_{\text{buffer}} = 15$ phút vào thời gian chiếm dụng.
- **Hàm Mục tiêu Tách bạch (Separated Objective)**:
  - $J_{\text{total}} = J_{\text{decision}} + J_{\text{reporting}}$.
  - *Chi phí Quyết định ($J_{\text{decision}}$)*: Phạt đổi cổng danh định, phạt ra bãi đỗ xa, phạt xung đột mềm.
  - *Chi phí Báo cáo ($J_{\text{reporting}}$)*: Phạt trễ ngoại sinh không phụ thuộc vào cổng gán.

---

## SLIDE 10: SO SÁNH GIẢI THUẬT VÀ ĐỊNH LÝ 0.00% GAIN (SOLVER ALGORITHMS)
- **Kiểm chứng Toán học Nghiệm Tối ưu**:
  - Đối chiếu với Exhaustive Combinatorial Oracle ($N=3, M=2$): CP-SAT đạt $10.0000$ điểm, Oracle đạt $10.0000$ điểm (sai số $< 10^{-4}$).
- **So sánh 4 Bộ giải**:
  - *Greedy Baseline*: Giải siêu tốc ($< 20$ ms), bảo đảm 100% ràng buộc cứng, dùng làm Safety Fallback.
  - *Simulated Annealing*: Cải thiện tốt nghiệm Greedy (+14.2 điểm chi phí).
  - *CP-SAT*: Giảm từ **$14.8\%$ đến $25.8\%$** chi phí so với Greedy trên quy mô 100–300 chuyến bay.
- **Định lý Cải thiện 0.00% của Hybrid**:
  - Khi CP-SAT đã tìm ra nghiệm và chứng minh tối ưu toàn cục, mức cải thiện của SA bắt buộc bằng **$0.00\%$** (định lý toán học, không phải lỗi code).

---

## SLIDE 11: HIỆU NĂNG BENCHMARK TRÊN CÁC QUY MÔ (BENCHMARK SCALABILITY)
- **Bảng Hiệu năng Thực nghiệm (Fair Benchmark)**:

| Quy mô ($N$ chuyến $\times M$ cổng) | Greedy ($J_{\text{dec}}$) | CP-SAT ($J_{\text{dec}}$) | Mức cải thiện CP-SAT | Thời gian giải CP-SAT |
|:---:|:---:|:---:|:---:|:---:|
| **Micro ($10 \times 4$)** | 20.00 | **10.00** | **$-50.0\%$** | 15.4 ms |
| **Small ($30 \times 10$)** | 85.50 | **60.00** | **$-29.8\%$** | 32.1 ms |
| **Medium ($100 \times 21$)** | 248.00 | **200.00** | **$-19.4\%$** | 412.0 ms |
| **Large ($200 \times 31$)** | 580.00 | **430.00** | **$-25.8\%$** | 1.85 giây |
| **Stress ($300 \times 51$)** | 920.00 | **784.00** | **$-14.8\%$** | 8.42 giây |

- **Kết luận**: CP-SAT giải quyết hoàn toàn bài toán quy mô 300 chuyến bay trong chưa đầy 9 giây, hoàn toàn khả thi cho vận hành thực tế tại sân bay.

---

## SLIDE 12: MÔ PHỎNG MONTE CARLO NHÂN QUẢ (CAUSAL MONTE CARLO)
- **Thiết lập**: 100 kịch bản ngẫu nhiên có kiểm soát hạt giống (CRN), Gaussian Copula $\rho = 0.45$.
- **Bóc tách 4 Chế độ**:
  - *Mode A (Fixed Plan)*: $76.0\%$ xảy ra xung đột vật lý; chi phí trung bình $1,606.43$ điểm.
  - *Mode B1 (Retrospective)*: Hindsight clairvoyance, chi phí $134.83$ điểm.
  - *Mode B2 (Causal Online Recourse)*: Phi tiên nghiệm thời gian thực, chi phí **$147.43$** điểm, **0% xung đột**.
  - *Mode C2 (CP-SAT Oracle)*: Cận dưới tối ưu toàn cục, chi phí **$122.43$** điểm.
- **Các Giá trị Vận hành Cốt lõi**:
  - **Value of Recourse (A vs B2)**: Tái phân bổ trực tuyến tiết kiệm **$1,459.0$ điểm chi phí** ($p < 10^{-20}$).
  - **Value of Information (B2 vs B1)**: Thiếu thông tin tương lai tốn thêm $+12.60$ điểm chi phí ($p < 10^{-8}$).
  - **Value of Optimization (C1 vs C2)**: CP-SAT tốt hơn Greedy foresight $12.40$ điểm chi phí ($p < 10^{-13}$).

---

## SLIDE 13: THỬ NGHIỆM TÍCH HỢP DỮ LIỆU THẬT (NATIVE REAL-DATA PILOT)
- **Kịch bản Lễ Tạ ơn 2023 tại ATL ($N = 200$ chuyến bay thật, $M = 35$ cổng)**:
  - Đọc trực tiếp từ file Parquet lịch sử và checkpoint ML đông băng.
- **Tính Trung thực về Dữ liệu Đuôi Tàu bay**:
  - Dữ liệu mở BTS TranStats lược bỏ cột `TAIL_NUM` $\to$ Hệ thống từ chối bịa số hiệu đuôi giả.
  - *Chế độ dữ liệu thật (Strict Real-Only)*: Giải tối ưu 200 tác vụ bay độc lập trong $1.31$s ($J_{\text{dec}} = 0.00$, 0 vi phạm).
  - *Chế độ suy diễn lịch trình (Inferred Mode)*: Ghép được 59 cặp quay đầu (cùng hãng, cửa sổ 45–180m), giải tối ưu trong $0.94$s (0 vi phạm).

---

## SLIDE 14: BẢNG ĐIỀU KHIỂN VẬN HÀNH STREAMLIT (DASHBOARD DEMO)
- **5 Trang Chức năng Chuyên sâu**:
  1. *Control Tower*: KPI tổng quan sân bay, sóng trễ (delay wave), trạng thái cổng.
  2. *Flight Intelligence*: Phân phối xác suất Student-t, giải thích đặc trưng bằng SHAP.
  3. *Gate Operations*: Biểu đồ Gantt phân bổ cổng với đệm 15m và thanh tra vi phạm.
  4. *Optimization Lab*: Benchmark so sánh đối đầu giữa các thuật toán solver.
  5. *Robustness Lab*: Phân phối Monte Carlo, so sánh bắt cặp và rủi ro đuôi CVaR ($95\%$).
- **Bảo mật & Kiểm thử**:
  - 359 kiểm thử tự động Headless AppTest đạt 100%.
  - Cơ chế bảo mật Canonical Path Containment ngăn chặn tấn công đọc tệp trái phép.

---

## SLIDE 15: CÁC GIỚI HẠN KHOA HỌC BẮT BUỘC CÔNG BỐ (SCIENTIFIC LIMITATIONS)
1. **Dữ liệu BTS thiếu số hiệu đuôi**: Dữ liệu thật giải 200 chuyến độc lập; ghép cặp quay đầu dựa trên suy diễn hãng và cửa sổ giờ.
2. **Nghịch lý MAE của Median Baseline**: Do phân phối lệch mạnh (>70% chuyến đúng giờ); ML vượt trội ở RMSE và các chuyến trễ nghiêm trọng $\ge 15$m, $\ge 60$m.
3. **Định lý 0.00% cải thiện của Hybrid**: Là minh chứng cho tính tối ưu toàn cục của CP-SAT, không phải lỗi thuật toán.
4. **Bóc tách Xung đột Vật lý (76%) và Khả thi Lịch tĩnh (0%)**: Mode A chỉ có 76% xung đột vật lý đè cổng, 24% còn lại vẫn an toàn.
5. **Lược bỏ Flight Chain và METAR**: Nhằm loại bỏ rò rỉ thông tin tương lai tại $T-2\text{h}$, đảm bảo liêm chính khoa học tuyệt đối.

---

## SLIDE 16: ĐÓNG GÓP VÀ KẾT LUẬN (CONTRIBUTIONS & CONCLUSION)
- **Đóng góp của Khóa luận**:
  - Xây dựng thành công hệ sinh thái phần mềm tích hợp hoàn chỉnh từ Dự báo trễ đến Tối ưu hóa phân bổ cổng đỗ.
  - Chứng minh sự vượt trội của Lập trình ràng buộc CP-SAT so với các thuật toán tham lam truyền thống (tiết kiệm $14.8\% - 25.8\%$ chi phí).
  - Đề xuất khung mô phỏng Monte Carlo nhân quả Mode B2 đánh giá đúng giá trị của tái phân bổ trực tuyến.
- **Tiềm năng Ứng dụng**:
  - Có thể chuyển giao làm công cụ hỗ trợ ra quyết định (DSS) cho trung tâm điều hành AOCC tại các sân bay lớn của Việt Nam (Nội Bài, Tân Sơn Nhất, Long Thành).

---

## SLIDE 17: HỎI ĐÁP VÀ PHỤ LỤC (Q&A & APPENDIX)
- **Kính mời Thầy/Cô trong Hội đồng đặt câu hỏi phản biện!**
- *Phụ lục sẵn sàng tra cứu*:
  - Bảng mã băm SHA-256 các checkpoint mô hình đông băng.
  - Kết quả kiểm định tính tái lập 6/6 tác vụ (Deterministic Reproducibility Harness).
  - Chi tiết công thức toán học mô hình CP-SAT và hàm mục tiêu.
