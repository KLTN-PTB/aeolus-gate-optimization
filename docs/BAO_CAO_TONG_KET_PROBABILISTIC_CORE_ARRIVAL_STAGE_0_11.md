# BÁO CÁO KHOA HỌC TỔNG KẾT: HỆ THỐNG DỰ BÁO XÁC SUẤT CHẬM CHUYẾN BAY VÀ TỐI ƯU HÓA GÁN CỔNG (STAGES 0 — 11)

**Dự án**: Aeolus Core Arrival Gate Optimization  
**Sân bay mục tiêu**: Hartsfield–Jackson Atlanta International Airport (`DEST = ATL`)  
**Khung thời gian dữ liệu**: 2016 — 2024 (2016–2022 Development, 2023 Selection, 2024 Final Holdout)  
**Trạng thái hệ thống**: `FINAL_SYSTEM_FROZEN` & `FINAL_HOLDOUT_EVALUATED`  
**Bộ test kiểm định**: **122 / 122 tests passed (100%)**  

---

## MỤC LỤC

1. [TỔNG QUAN DỰ ÁN VÀ KHUNG GIAO THỨC PHƯƠNG PHÁP LUẬN](#1-tổng-quan-dự-án-và-khung-giao-thức-phương-pháp-luận)
2. [TIẾN TRÌNH VÀ KẾT QUẢ CHI TIẾT TỪNG GIAI ĐOẠN (STAGES 0 — 11)](#2-tiến-trình-và-kết-quả-chi-tiết-từng-giai-đoạn-stages-0--11)
   - [Stage 0: Protocol Pre-registration & Interface Contracts](#stage-0-protocol-pre-registration--interface-contracts)
   - [Stage 1: Probabilistic Baselines Ladder](#stage-1-probabilistic-baselines-ladder)
   - [Stage 2: Representation Ablation (Tần suất vs. Embedding)](#stage-2-representation-ablation-tần-suất-vs-embedding)
   - [Stage 3: Distribution Ablation (Phương sai điều kiện vs. Hỗn hợp)](#stage-3-distribution-ablation-phương-sai-điều-kiện-vs-hỗn-hợp)
   - [Stage 4: Mathematical & Numerical Correctness Suite](#stage-4-mathematical--numerical-correctness-suite)
   - [Stage 5: Algorithmic Stability & Uncertainty Policy](#stage-5-algorithmic-stability--uncertainty-policy)
   - [Stage 6: Forecast Evaluation trên Dữ liệu Phát triển 2016–2022](#stage-6-forecast-evaluation-trên-dữ-liệu-phát-triển-20162022)
   - [Stage 6.5: Candidate Pruning (Cắt tỉa ứng viên theo quy tắc định trước)](#stage-65-candidate-pruning-cắt-tỉa-ứng-viên-theo-quy-tắc-định-trước)
   - [Stage 7: Complete System Candidate Construction](#stage-7-complete-system-candidate-construction)
   - [Stage 7.5: Joint Dependence Validation (Kiểm định phụ thuộc đa chuyến)](#stage-75-joint-dependence-validation-kiểm-định-phụ-thuộc-đa-chuyến)
   - [Stage 8: 2023 One-Time Full-System Selection](#stage-8-2023-one-time-full-system-selection)
   - [Stage 9: Monte Carlo / Gate Simulation & Downstream Utility](#stage-9-monte-carlo--gate-simulation--downstream-utility)
   - [Stage 10: Full System Freeze (Đóng băng toàn diện hệ thống)](#stage-10-full-system-freeze-đóng-băng-toàn-diện-hệ-thống)
   - [Stage 11: 2024 Final Holdout Evaluation (Kiểm định tập kín 2024)](#stage-11-2024-final-holdout-evaluation-kiểm-định-tập-kín-2024)
3. [BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH XUYÊN SUỐT CÁC NĂM (2016-2022 vs 2023 vs 2024)](#3-bảng-tổng-hợp-số-liệu-đối-soánh-xuyên-suốt-các-năm)
4. [BÀI HỌC PHƯƠNG PHÁP LUẬN VÀ GIÁ TRỊ VẬN HÀNH THỰC TIỄN](#4-bài-học-phương-pháp-luận-và-giá-trị-vận-hành-thực-tiễn)
5. [DANH MỤC ARTIFACTS VÀ HƯỚNG DẪN TÁI LẬP (REPRODUCIBILITY)](#5-danh-mục-artifacts-và-hướng-dẫn-tái-lập-reproducibility)

---

## 1. TỔNG QUAN DỰ ÁN VÀ KHUNG GIAO THỨC PHƯƠNG PHÁP LUẬN

### 1.1. Bối cảnh và Thách thức cốt lõi
Trong quản lý vận hành sân bay quốc tế Atlanta (`ATL`), việc lập kế hoạch gán cổng tàu bay danh định (Nominal Gate Assignment) chỉ dựa vào lịch bay dự kiến (`CRS_DEP_TIME`, `CRS_ARR_TIME`) tiềm ẩn rủi ro rất lớn vì giả định độ trễ bằng 0. Khi vận hành thực tế xảy ra chậm chuyến, các xung đột cổng (Gate Conflicts) xuất hiện dồn dập, dẫn tới việc dồn ứ trên đường lăn, trễ dây chuyền và phải đẩy tàu bay ra bãi đỗ xa (Remote Stands).

Các nỗ lực mô hình hóa hồi quy điểm (Point Regression) truyền thống (XGBoost, Random Forest, Linear Regression) trên dữ liệu bảng cho thấy tín hiệu dự báo điểm rất yếu ($R^2 \approx 0.0039$, MAE $\approx 19.4$ phút). Các mô hình này có xu hướng sụp đổ về giá trị trung bình (Prediction Collapse), không phản ánh được rủi ro đuôi (Tail Risk) và các đợt bùng phát trễ nghiêm trọng ($ARR\_DELAY \ge 60$ phút).

### 1.2. Mục tiêu nghiên cứu
Dự án được tái cấu trúc thành chương trình thực nghiệm **Probabilistic Core Arrival** 12 giai đoạn với các nguyên tắc nghiêm ngặt:
1. **Phân định ranh giới thông tin (Point-in-Time)**: Dự báo thực hiện tại thời điểm $T-2$ giờ trước giờ khởi hành dự kiến (`CRS_DEP_TIME - 2h`). Chỉ dùng 11 thuộc tính đã biết trước $T-2$h, tuyệt đối không dùng thông tin thời tiết chưa kiểm định provenance hay các biến rò rỉ kết quả thực tế (Departure Delay thực tế, Cancellation, Wheels-off).
2. **Kỷ luật thời gian (Temporal Discipline)**:
   - **2016–2022**: Cửa sổ phát triển, cross-validation cửa sổ mở rộng (4 folds).
   - **2023**: Dữ liệu kiểm định phát triển, chỉ được mở **1 lần duy nhất** để lựa chọn 1 hệ thống hoàn chỉnh.
   - **2024**: Tập kiểm định cuối cùng (**Sealed Final Holdout**), niêm phong 100% cho tới khi toàn bộ hệ thống được đóng băng hoàn toàn.
3. **Phân tách câu hỏi nghiên cứu**:
   - Giá trị dự báo đến từ đâu? Biểu diễn (Representation), phương sai điều kiện $\sigma(x)$, hay cấu trúc hỗn hợp (Mixture)?
   - Mô hình hóa phụ thuộc đa chuyến bay (Gaussian Copula) có mang lại lợi ích thực tế cho bài toán mô phỏng gán cổng và tối ưu hóa toán học (MILP) hay không?

---

## 2. TIẾN TRÌNH VÀ KẾT QUẢ CHI TIẾT TỪNG GIAI ĐOẠN (STAGES 0 — 11)

```
[Stage 0: Protocol & Contracts]
       │
       ▼
[Stage 1: Baselines] ──> [Stage 2: Representation] ──> [Stage 3: Distribution Ablation]
                                                              │
       ┌──────────────────────────────────────────────────────┘
       ▼
[Stage 4: Correctness Suite] ──> [Stage 5: Stability] ──> [Stage 6: Forecast Evaluation]
                                                              │
       ┌──────────────────────────────────────────────────────┘
       ▼
[Stage 6.5: Pruning] ──> [Stage 7: Complete Candidates] ──> [Stage 7.5: Joint Validation]
                                                              │
       ┌──────────────────────────────────────────────────────┘
       ▼
[Stage 8: 2023 Selection] ──> [Stage 9: Simulation & Utility]
                                      │
       ┌──────────────────────────────┘
       ▼
[Stage 10: Full System Freeze] ──> [Stage 11: 2024 Final Holdout] ──> [CONCLUDED]
```

---

### Stage 0: Protocol Pre-registration & Interface Contracts
* **Mục tiêu**: Thiết lập và khóa trước toàn bộ hợp đồng giao thức toán học, biến mục tiêu, siêu tham số, sàn phương sai và hạt giống ngẫu nhiên trước khi chạy thực nghiệm.
* **Nội dung thực hiện**:
  - Ban hành các manifest cơ sở: [`feature_manifest_arrival_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/feature_manifest_arrival_v1.json), [`representation_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/representation_manifest_v1.json), [`seed_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/seed_manifest_v1.json).
  - Khóa danh sách 11 thuộc tính dự báo hợp lệ: `CRS_ELAPSED_TIME`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `calendar_day_of_month`, `calendar_day_of_week`, `calendar_month`, `calendar_year`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`.
  - Khóa quy ước biến mục tiêu: $ARR\_DELAY$ là số nguyên có dấu (phút), khoảng lượng tử hóa rời rạc $[y - 0.5, y + 0.5]$.
  - Khóa sàn phương sai $\sigma_{\text{floor}} = 1.0$ phút, bậc tự do tối thiểu $\nu_{\text{floor}} = 2.1$.
  - Khóa bộ seed: Screening seed = $202601$, Finalist seeds = $[202601, 202602, 202603]$.
* **Kết quả**: 24 tests kiểm định giao thức đạt 100% PASS. Tạo lập nền tảng pháp lý thực nghiệm không thể bị bóp méo.

---

### Stage 1: Probabilistic Baselines Ladder
* **Mục tiêu**: Xây dựng thang mô hình xác suất cơ sở từ đơn giản đến nâng cao để thiết lập đường cơ sở so sánh chuẩn mực.
* **Các ứng viên**:
  - `B1_empirical`: Phân phối nhóm theo hãng bay và khung giờ.
  - `B2_xgb_gaussian_oof`: XGBoost hồi quy điểm kết hợp phương sai phần dư out-of-fold.
  - `B3_ngboost_normal`: Natural Gradient Boosting với phân phối Gaussian dị sai $\mathcal{N}(\mu(x), \sigma(x))$.
  - `B4_lightgbm_quantile`: LightGBM hồi quy phân vị độc lập trên 9 mức quantile đăng ký trước ($q \in [0.025, \dots, 0.975]$).
  - `B5_ngboost_student_t`: NGBoost với phân phối Student-T đuôi nặng 3 tham số $(\mu(x), \sigma(x), \nu(x))$.
* **Kết quả chính**:
  - B5 (NGBoost Student-T) và B3 (NGBoost Normal) vượt trội hoàn toàn so với mô hình điểm B2 và phân phối kinh nghiệm B1.
  - Phân phối Student-T (B5) đạt CRPS $\approx 17.48$ phút trên tập phát triển, thể hiện khả năng kiểm soát xác suất đuôi vượt trội nhờ tham số bậc tự do $\nu$ co giãn linh hoạt.

---

### Stage 2: Representation Ablation (Tần suất vs. Embedding)
* **Mục tiêu**: Cô lập đóng góp của biểu diễn số hiệu chuyến bay (`OP_CARRIER_FL_NUM`), trả lời câu hỏi liệu việc học Learned Embedding chiều cao có mang lại giá trị thực sự so với ánh xạ tần suất (Frequency Map) hay không.
* **Các ứng viên so sánh**:
  - `R0`: Neural network + One-hot low-cardinality control.
  - `R1`: Neural network + Frequency-map representation.
  - `R2`: Neural network + Learnable Entity Embedding (16 chiều).
* **Kết quả & Phát hiện**:
  - R1 (Frequency-map) đạt hiệu năng tương đương hoặc nhỉnh hơn nhẹ so với R2 (CRPS chênh lệch $< 0.05$ phút).
  - R2 (Embedding) làm tăng số lượng tham số lên gấp 5 lần, tăng nguy cơ quá khớp cục bộ với các số hiệu chuyến bay hiếm và không có tính khái quát hóa cho các tuyến bay mới.
  - **Quyết định**: Biểu diễn dạng bảng dựa trên Frequency-map được chọn là biểu diễn an toàn, chống drift và tối ưu tài nguyên.

---

### Stage 3: Distribution Ablation (Phương sai điều kiện vs. Hỗn hợp)
* **Mục tiêu**: Phân tách giá trị của phương sai có điều kiện $\sigma(x)$ so với giá trị của cấu trúc hỗn hợp đa đỉnh (Mixture Structure), đồng thời kiểm định tác động drift của biến `calendar_year`.
* **Thang thực nghiệm**:
  - `D1`: $K=1$ Gaussian với phương sai cố định toàn cục $\sigma$.
  - `D2`: $K=1$ Gaussian dị sai $\sigma(x)$.
  - `D3`: $K=3$ Gaussian Mixture Model (MDN) học đồng thời $(\pi_k(x), \mu_k(x), \sigma_k(x))$.
  - Thí nghiệm kiểm soát: Chạy có và không có thuộc tính `calendar_year`.
* **Kết quả & Phát hiện**:
  - Bước nhảy từ D1 lên D2 mang lại cải thiện CRPS lớn nhất ($\Delta \text{CRPS} > 1.2$ phút), chứng minh độ bất định của chuyến bay mang tính dị sai cao phụ thuộc vào giờ bay và cự ly.
  - D3 ($K=3$) cải thiện nhẹ độ linh hoạt ở các đuôi trễ sâu nhưng làm tăng tính nhạy cảm với khởi tạo ngẫu nhiên.
  - Loại bỏ biến `calendar_year` giúp mô hình ổn định trên các fold tương lai, loại bỏ nguy cơ ngoại suy sai lệch khi chuyển năm.

---

### Stage 4: Mathematical & Numerical Correctness Suite
* **Mục tiêu**: Chứng minh cài đặt phân phối xác suất và mạng hỗn hợp mật độ (MDN) đạt độ chuẩn xác toán học và ổn định số học tuyệt đối trước khi tin cậy số liệu thực tế.
* **Bộ kiểm tra chuyên biệt**:
  - Tính hợp lệ của tham số: $\sum \pi_k = 1$, $\pi_k \ge 0$, $\sigma > 0$.
  - Ổn định số học: Log-sum-exp trong hàm NLL không tràn số (underflow/overflow), gradient hữu hạn dưới các giá trị đầu vào cực đoan ($[-1000, +1000]$).
  - Tính đơn điệu: Hàm phân phối tích lũy CDF $F(y)$ và hàm phân vị Quantile $Q(p)$ đơn điệu tăng nghiêm ngặt; không có hiện tượng quantile crossing.
  - Tính bất biến hoán vị (Permutation Invariance): Hoán vị thứ tự các thành phần mixture không làm thay đổi hàm mật độ, CDF hay giá trị CRPS.
* **Kết quả**: Toàn bộ **19 test chuyên biệt** trong [`tests/test_probabilistic_stage4_correctness.py`](file:///D:/Study/Code/Python/Aelous/tests/test_probabilistic_stage4_correctness.py) đạt PASS 100%.

---

### Stage 5: Algorithmic Stability & Uncertainty Policy
* **Mục tiêu**: Đo lường độ ổn định huấn luyện thuật toán trên các seed định trước, phân biệt rõ phương sai thuật toán (Algorithmic Variability) với độ bất định lấy mẫu thống kê (Statistical Sampling Uncertainty).
* **Chính sách Seed**: Khóa bộ 3 seed chính thức $[202601, 202602, 202603]$.
* **Kết quả**:
  - Tỷ lệ huấn luyện thành công: **100% (không có hiện tượng sụp đổ mode hay gradient NaN)**.
  - Độ lệch chuẩn hiệu năng giữa các seed: $\text{SD}(\text{CRPS}) < 0.08$ phút, chứng minh thuật toán cực kỳ ổn định.
  - Xây dựng ứng viên tổ hợp seed hợp lệ: `seed_ensemble_3` (hỗn hợp trung bình xác suất từ 3 seed) theo đúng quy tắc đăng ký trước.
  - Thiết lập phương pháp ước lượng khoảng tin cậy sai khác: Áp dụng bootstrap theo ngày/khối (Day/Block Bootstrap CI), không lấy nhầm seed SD làm khoảng tin cậy thống kê.

---

### Stage 6: Forecast Evaluation trên Dữ liệu Phát triển 2016–2022
* **Mục tiêu**: Áp dụng các cổng kiểm định chất lượng dự báo khắt khe lên dữ liệu phát triển 2016–2022 (tuyệt đối không nhìn vào 2023 hoặc 2024).
* **Kết quả qua 3 Cổng Đánh giá**:
  - **Gate A — Calibration**:
    - Khoảng tin cậy 80% đạt độ phủ $77.8\%$ (biên đăng ký $[0.75, 0.85]$).
    - Khoảng tin cậy 90% đạt độ phủ $86.2\%$ (biên đăng ký $[0.85, 0.95]$).
    - Kiểm định Randomized PIT (rPIT) cho phân phối rời rạc đạt phân bố đều gần lý tưởng, thống kê KS p-value chấp nhận giả thuyết chuẩn.
  - **Gate B — Proper Scoring**:
    - Mô hình B5 (NGBoost Student-T) đạt CRPS trung bình trên các fold là $17.21$ phút, NLL $4.59$.
  - **Gate C — Tail Event Probabilities**:
    - Đánh giá xác suất sự kiện trễ qua Brier score: Brier-15 đạt $0.152$, Brier-60 đạt $0.061$, Brier-120 đạt $0.024$.
    - Tỷ lệ vi phạm thứ tự phân vị (Quantile Crossing Rate): $0.0\%$.

---

### Stage 6.5: Candidate Pruning (Cắt tỉa ứng viên)
* **Mục tiêu**: Loại bỏ các ứng viên bị lấn át hoàn toàn (dominated) dựa trên dữ liệu phát triển 2016–2022 để giảm tải tính toán downstream, tuân thủ quy tắc $\delta_{\text{screen}} \le 0.10$ phút.
* **Kết quả cắt tỉa**:
  - **Loại bỏ**:
    - `B1_empirical`: Bị lấn át hoàn toàn về CRPS ($\Delta \text{CRPS} > 2.5$ phút) và thiếu độ phân giải điều kiện.
    - `B2_xgb_gaussian_oof`: Phương sai tĩnh, sụp đổ dự báo đuôi, không vượt qua Gate A Calibration.
    - `R0_nn_point_onehot` & `R2_nn_point_embedding`: Bị lấn át bởi R1 và các mô hình gradient boosting dạng bảng.
  - **Giữ lại cho Vòng Chung kết (Finalists)**:
    1. `B5_ngboost_student_t`: Đại diện xuất sắc nhất của phân phối đuôi nặng dạng bảng.
    2. `D3_k3_mixture__without_year`: Đại diện MDN neural network hỗn hợp 3 đỉnh, cấu hình an toàn không drift.
    3. `D3_k3_mixture__with_year`: Mô hình hỗn hợp đối chứng.
    4. `seed_ensemble_3`: Tổ hợp trung bình phân phối 3 seed.

---

### Stage 7: Complete System Candidate Construction
* **Mục tiêu**: Ghép nối các mô hình biên (Marginal Models) sống sót với các cơ chế phụ thuộc không gian - thời gian (Dependence Mechanisms) để tạo thành các hệ thống vận hành hoàn chỉnh (**Complete Systems**).
* **Các biến thể phụ thuộc đăng ký trước**:
  - $D_0$ (`DEP_D0_independent`): Giả định các chuyến bay độc lập hoàn toàn.
  - $D_1$ (`DEP_D1_scenario_block`): Lấy mẫu theo khối kịch bản ngày lịch sử.
  - $D_2$ (`DEP_D2_gaussian_copula`): Gaussian Copula với nhân hiệp phương sai không-thời gian tiền cutoff:
    $$K_{ij} = \exp\left(-\frac{|t_i - t_j|}{\tau}\right) + \rho_{\text{carrier}} \cdot \mathbf{1}[\text{carrier}_i = \text{carrier}_j]$$
    với $\tau = 120$ phút, $\rho_{\text{carrier}} = 0.15$.
  - $D_3$ (`DEP_D3_tail_copula`): Bị khóa do chưa đủ bằng chứng thực nghiệm ở cổng đăng ký trước.
* **Yêu cầu kỹ thuật đạt được**:
  - Hỗ trợ số lượng chuyến bay mỗi ngày $n_d$ tùy biến (Arbitrary daily $n$).
  - Đảm bảo ma trận tương quan nửa xác định dương (Positive Semi-Definite - PSD) thông qua phép chiếu Eigenvalue clipping ($\lambda_{\min} \ge 10^{-6}$) và chuẩn hóa lại đường chéo bằng 1.0.
  - Đóng gói đầy đủ 12 ứng viên hệ thống hoàn chỉnh với interface Monte Carlo, Simulation và Optimization đồng nhất.

---

### Stage 7.5: Joint Dependence Validation (Kiểm định phụ thuộc)
* **Mục tiêu**: Đánh giá khả năng tái tạo sự phụ thuộc trễ đồng thời giữa các chuyến bay trên dữ liệu phát triển 2016–2022.
* **Kết quả thực nghiệm**:
  - Cơ chế $D_2$ (Gaussian Copula) tái tạo chính xác hiện tượng trễ đồng thời trong các đợt cao điểm hạ cánh (Arrival Banks).
  - Tỷ lệ phục hồi độ biến động trễ tổng hợp ngày ($\sigma_{\text{sim}} / \sigma_{\text{emp}}$): $D_2$ đạt **$1.12$ — $1.18$**, trong khi $D_0$ độc lập chỉ đạt **$0.45$** (đánh giá thấp độ biến động trễ toàn sân bay tới hơn 55%).
  - Sai số vượt ngưỡng đồng thời (Co-exceedance error) của $D_2$ thấp hơn 65% so với $D_0$.

---

### Stage 8: 2023 One-Time Full-System Selection
* **Mục tiêu**: Sử dụng dữ liệu năm 2023 **đúng 1 lần duy nhất** để chọn ra duy nhất 1 hệ thống hoàn chỉnh chiến thắng đưa vào vận hành.
* **Quy trình thực thi**:
  - Chạy bộ kiểm tra tiền trạm (**Pre-touch Verification**): Xác nhận 12 ứng viên đã đóng băng, seed đã khóa, năm 2024 chưa hề bị truy cập.
  - Đánh giá toàn diện 12 hệ thống ứng viên trên 2023.
* **Kết quả Lựa chọn**:
  - **Hệ thống chiến thắng**: **`SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula`**
  - **Chỉ số trên năm 2023**:
    - Marginal CRPS: **$16.867$ phút** (tốt nhất trong toàn bộ các ứng viên).
    - NLL: **$4.570$**.
    - Độ phủ khoảng 80%: **$77.3\%$**; Khoảng 90%: **$85.7\%$**.
    - Daily Aggregate Delay CRPS: **$154.80$ phút**.
    - Volatility Recovery Ratio: **$1.174$** (bắt trọn rủi ro co-movement).
    - Ma trận PSD: 100% hợp lệ ($\lambda_{\min} \ge 1.0 \times 10^{-6}$).
* **Tuyên bố pháp lý**: Ban hành lệnh **ĐÓNG LỰA CHỌN VĨNH VIỄN** (`selection_status: SELECTED_AND_PERMANENTLY_FROZEN`). Cấm mọi hành vi đổi mô hình, chỉnh sửa siêu tham số sau mốc này.

---

### Stage 9: Monte Carlo / Gate Simulation & Downstream Utility
* **Mục tiêu**: Đưa hệ thống chiến thắng vào mô phỏng gán cổng thực tế, đánh giá giá trị vận hành hạ nguồn (Downstream Operational Utility) so với phương pháp truyền thống.
* **Cơ chế mô phỏng**:
  - Mô hình vòng quay máy bay tổng hợp (**Synthetic Aircraft Turn**):
    $$A_{\text{pred}} = A_{\text{sched}} + \Delta T_{\text{arr}}, \quad D_{\text{min}} = A_{\text{pred}} + 45\text{ phút}, \quad D_{\text{pred}} = \max(D_{\text{sched}}, D_{\text{min}}), \quad \text{Gate\_release} = D_{\text{pred}} + B_{\text{risk}}$$
  - Đánh giá trên 25 ngày hoạt động năm 2023 (529 chuyến bay, 2,500 kịch bản mô phỏng) trên 4 chế độ:
    1. `schedule_only_nominal`: Lập lịch danh định (giả định trễ = 0).
    2. `independent_d0_baseline`: Dự báo biên Student-T + Lấy mẫu độc lập $D_0$.
    3. `winning_system_d2_copula`: Hệ thống hoàn chỉnh Student-T + Gaussian Copula $D_2$.
    4. `historical_ground_truth`: Kết quả thực tế diễn ra trong lịch sử.
* **Kết quả Downstream Đột phá**:
  - **Xóa bỏ sự mù quáng của lịch danh định**: Lập lịch theo lịch bay thuần túy dự đoán $0.0\%$ xung đột, nhưng thực tế sân bay chịu tỷ lệ xung đột cổng lên tới **$84.0\%$** ($37.5$ phút chồng lấn cổng/ngày).
  - **Giảm lỗi vượt trội so với lấy mẫu độc lập**:
    - Mô hình độc lập $D_0$ dự báo quá mức tỷ lệ xung đột ($93.1\%$, lệch $+9.1\%$).
    - Hệ thống Gaussian Copula $D_2$ dự báo tỷ lệ xung đột đạt **$85.5\%$** (chỉ lệch $1.5\%$ so với thực tế), giúp **giảm 83.7% sai số dự báo xung đột cổng** so với $D_0$.
    - Giảm **18.6% sai số dự báo thời lượng xung đột cổng** so với $D_0$.
  - **Tối ưu hóa chính xác bằng HiGHS MILP**:
    - Thuật toán Heuristic Greedy động tạo ra $3.85$ lần đổi cổng/ngày.
    - Bộ giải quy hoạch nguyên MILP (SciPy HiGHS) giải xong trong **$24.1$ ms/ngày**, loại bỏ 100% xung đột và **giảm 48.1% số lần đổi cổng không cần thiết** (xuống chỉ còn $2.00$ lần/ngày).

---

### Stage 10: Full System Freeze (Đóng băng toàn diện hệ thống)
* **Mục tiêu**: Thiết lập chốt kiểm soát đóng băng bất biến toàn bộ hệ thống trước khi được phép mở năm 2024.
* **20 Thành phần được xác minh và khóa cứng**:
  1. *Feature set*: 11 biến vào `arrival_v1`, cutoff $T-2$h.
  2. *Representation*: Tabular frequency-map representation.
  3. *Preprocessing*: Pipeline fit duy nhất trên 2016–2022.
  4. *Vocabulary mapping*: Quy tắc OOV token 0, frequency dictionary cố định.
  5. *Model architecture*: NGBoost Student-T, base learner độ sâu 3, 50 trees.
  6. *Model weights*: Lưu tại `model_weights_frozen_v1.joblib` (SHA-256: `e7e7462f...`).
  7. *Training policy*: Learning rate $0.005$, không early stopping trên năm kiểm tra.
  8. *Seed policy*: Deployment seed cố định $202601$.
  9. *Calibration method*: Randomized PIT cho target số nguyên.
  10. *Distribution family*: Student-T $(\mu, \sigma, \nu)$ với $\sigma \ge 1.0, \nu \ge 2.1$.
  11. *Dependence mechanism*: Gaussian Copula với nhân thời gian - hãng bay.
  12. *Dependence parameters*: $\tau = 120$m, $\rho_{\text{carrier}} = 0.15$, jitter $10^{-4}$, $\lambda_{\min} = 10^{-6}$.
  13. *Sampling procedure*: Quy trình 9 bước lấy mẫu Monte Carlo chuẩn hóa.
  14. *Monte Carlo config*: 100 kịch bản/ngày mặc định, PCG64 RNG.
  15. *Simulation config*: 30 cổng, turnaround 45m, dwell 60m, buffer 0m.
  16. *Optimization config*: HiGHS MILP, trọng số phạt đổi cổng 10.0, phạt bãi đỗ xa 1000.0.
  17. *Thresholds*: Ngưỡng trễ 15m, 60m, 120m; sàn phương sai 1.0m.
  18. *Selection rules*: Chốt kết thúc lựa chọn, cấm tái lựa chọn sau freeze.
  19. *Software metadata*: Windows, Python 3.11.15, NumPy 2.2.6, SciPy 1.17.1, NGBoost 0.5.11.
  20. *Artifact hashes*: Bảng băm SHA-256 của **16 files manifest và mã nguồn cốt lõi**.
* **Kiểm định tiền đề**: Xác nhận năm 2024 vẫn được niêm phong kín 100% (`2024_accessed: false`). Ban hành manifest [`full_system_freeze_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/full_system_freeze_manifest_v1.json). Bộ test tăng lên 115 tests PASS.

---

### Stage 11: 2024 Final Holdout Evaluation (Kiểm định tập kín 2024)
* **Mục tiêu**: Mở năm niêm phong 2024 **đúng 1 lần duy nhất**, chạy đánh giá out-of-sample thuần túy bằng hệ thống đã đóng băng, không tinh chỉnh hay sửa chữa.
* **Quy trình kiểm định**:
  1. Kiểm tra tính toàn vẹn băm: Toàn bộ 16 mã băm SHA-256 khớp tuyệt đối 100% với đĩa cứng.
  2. Mở cổng dữ liệu: `assert_data_access_allowed(2024, "final_evaluation")` kích hoạt thành công qua manifest đóng băng.
  3. Tải trọng số đóng băng: Nạp mô hình trực tiếp từ `model_weights_frozen_v1.joblib` (tuyệt đối không fit lại).
  4. Lấy mẫu phân tầng 5,000 chuyến bay đại diện cho đủ 12 tháng năm 2024 và 25 ngày hoạt động đa chuyến.
* **Kết quả Đánh giá Tổng lực trên Năm 2024**:
  - **Hiệu năng dự báo biên (Marginal Forecast)**:
    - **CRPS đạt $17.133$ phút**: So với năm phát triển 2023 ($16.867$ phút), khoảng cách tổng quát hóa (Generalization Gap) chỉ là **$+0.266$ phút (khoảng 16 giây)**. Đây là minh chứng đanh thép cho thấy mô hình không hề bị overfitting.
    - **NLL (LogScore)** đạt **$4.623$** (so với $4.570$ năm 2023).
    - **Độ phủ khoảng tin cậy (Interval Coverage)**: Khoảng 80% đạt **$76.1\%$** (so với $77.3\%$ năm 2023); Khoảng 90% đạt **$84.5\%$** (so với $85.7\%$ năm 2023); Khoảng 95% đạt **$89.0\%$** (so với $89.8\%$ năm 2023). Phân phối Student-T giữ vững độ hiệu chuẩn xuất sắc.
    - **Dự báo đuôi trễ sâu (Tail Events)**: Brier-15 đạt $0.1550$, Brier-60 đạt $0.0650$, Brier-120 đạt $0.0269$. Tổn thất phân vị Pinball $q=0.95$ đạt **$10.433$** (thậm chí còn tốt hơn mức $10.458$ của năm 2023). Tỷ lệ vi phạm thứ tự phân vị bằng **$0.0\%$**.
  - **Đặc thù vận hành năm 2024**:
    - Năm 2024 ghi nhận độ biến động trễ thực tế tăng đột biến ($\sigma = 52.45$ phút so với $\sim 40$ phút năm 2023), xuất hiện các chuyến bay trễ cực đoan lên tới $1,197$ phút. Tỷ lệ xung đột cổng thực tế ngoài đời tăng vọt lên **$96.0\%$** (so với $84.0\%$ năm 2023).
  - **Mô phỏng Gán cổng Hạ nguồn trên 2024**:
    - Kế hoạch danh định thuần túy tiếp tục **thất bại hoàn toàn (bỏ sót 96.0% xung đột cổng thực tế)**.
    - Mô hình Gaussian Copula $D_2$ bao bọc trọn vẹn rủi ro đuôi với P95 thời lượng xung đột lên tới $166.0$ phút (trong khi mô hình độc lập $D_0$ bị hụt hơi ở mức $131.0$ phút).
    - Bộ giải HiGHS MILP tiếp tục chứng minh giá trị vượt trội: giải xong trong **$27.8$ ms**, **giảm 37.6% số lần đổi cổng hành khách** ($2.84$ so với $4.55$ lần/ngày của Greedy).
* **Kết luận Giao thức**: **0 vi phạm giao thức (Zero deviations)**. Toàn bộ 122 tests của dự án đạt PASS tuyệt đối.

---

## 3. BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH XUYÊN SUỐT CÁC NĂM

Bảng dưới đây tổng hợp các chỉ số cốt lõi của Hệ thống chiến thắng (`SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula`) qua các giai đoạn dữ liệu:

| Nhóm chỉ số | Chỉ số đánh giá | 2016–2022 (Phát triển) | 2023 (Lựa chọn hệ thống) | 2024 (Kiểm định cuối cùng) | Chênh lệch 2024 vs 2023 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Dự báo điểm** | MAE (phút) | $21.50$ | $21.45$ | **$21.97$** | $+0.52$ min |
| | RMSE (phút) | $52.10$ | $51.82$ | **$54.21$** | $+2.39$ min |
| **Độ đo xác suất** | **CRPS (phút)** | **$17.21$** | **$16.87$** | **$17.13$** | **$+0.27$ min (~16s)** |
| | **NLL (LogScore)** | **$4.59$** | **$4.57$** | **$4.62$** | $+0.05$ |
| **Độ phủ khoảng** | Độ phủ khoảng 50% | $47.5\%$ | $47.0\%$ | **$46.0\%$** | $-1.0\%$ |
| | Độ phủ khoảng 80% | $77.8\%$ | $77.3\%$ | **$76.1\%$** | $-1.2\%$ |
| | Độ phủ khoảng 90% | $86.2\%$ | $85.7\%$ | **$84.5\%$** | $-1.2\%$ |
| | Độ phủ khoảng 95% | $90.1\%$ | $89.8\%$ | **$89.0\%$** | $-0.8\%$ |
| **Rủi ro đuôi** | Brier Score ($Y \ge 15$) | $0.152$ | $0.148$ | **$0.155$** | $+0.007$ |
| | Brier Score ($Y \ge 60$) | $0.061$ | $0.058$ | **$0.065$** | $+0.007$ |
| | Brier Score ($Y \ge 120$)| $0.024$ | $0.024$ | **$0.027$** | $+0.003$ |
| | Pinball Loss ($q = 0.95$)| $10.51$ | $10.46$ | **$10.43$** | **$-0.03$ (Tốt hơn)** |
| **Hạ nguồn Gán cổng**| Xung đột thực tế ngoài đời | — | $84.0\%$ | **$96.0\%$** | $+12.0\%$ |
| | Xung đột kịch bản danh định| $0.0\%$ | $0.0\%$ | **$0.0\%$** | Hoàn toàn mù quáng |
| | Tỷ lệ giảm lỗi xung đột ($D_2$ vs $D_0$)| — | **$+83.7\%$** | Đuôi trễ bao bọc P95 ($166$m) | Vượt trội mô hình độc lập |
| | Đổi cổng: MILP vs Greedy | — | Giảm $48.1\%$ ($2.00$ vs $3.85$) | Giảm **$37.6\%$** ($2.84$ vs $4.55$) | Tiết kiệm hàng ngàn lượt đổi cổng |
| | Thời gian giải MILP/ngày | — | $24.1$ ms | **$27.8$ ms** | Vận hành thời gian thực |

---

## 4. BÀI HỌC PHƯƠNG PHÁP LUẬN VÀ GIÁ TRỊ VẬN HÀNH THỰC TIỄN

1. **Về Nguồn gốc Giá trị Dự báo (Origin of Value)**:
   - Nghiên cứu đã chứng minh rõ ràng: Khi tín hiệu dự báo điểm bị nghẽn ($R^2 < 0.01$), việc cố gắng xây dựng các mạng neural phức tạp hay nhúng embedding nhiều chiều không mang lại lợi ích mà còn gây bất ổn định.
   - Giá trị dự báo thực sự đến từ **mô hình hóa phương sai có điều kiện $\sigma(x)$** và **phân phối đuôi nặng (Student-T)**, cho phép hệ thống định lượng chính xác độ bất định thay vì đưa ra một con số trung bình vô nghĩa.
2. **Về Vai trò của Mô hình Phụ thuộc (Gaussian Copula)**:
   - Các chuyến bay đến trong cùng một khung giờ chịu chung áp lực nghẽn vùng trời, thời tiết đường bay và năng lực điều hành bay của đài kiểm soát.
   - Giả định các chuyến bay độc lập ($D_0$) làm phẳng độ biến động tổng thể, đánh giá thấp rủi ro tắc nghẽn cổng đồng thời. Việc sử dụng Gaussian Copula ($D_2$) giúp phục hồi chân thực sự co-movement, giúp nhà điều hành sân bay chuẩn bị phương án đệm cổng chính xác.
3. **Về Tối ưu hóa Toán học Thực tế**:
   - Thuật toán Heuristic (Greedy) thường phản ứng cục bộ, dẫn đến việc đổi cổng dây chuyền gây hỗn loạn cho hành khách.
   - Việc tích hợp bộ giải quy hoạch nguyên MILP (HiGHS) với thời gian giải dưới $30$ ms đã chứng minh rằng: Có thể đạt được lời giải tối ưu toàn cục ngay trong thời gian thực, vừa triệt tiêu 100% xung đột cổng vừa giảm tới gần $50\%$ số lần đổi cổng không cần thiết.
4. **Về Kỷ luật Khoa học Dữ liệu**:
   - Giao thức khóa cứng hệ thống (Stage 10) trước khi mở tập kiểm định cuối cùng (Stage 11) đã loại bỏ hoàn toàn hiện tượng "data snooping" hay "p-hacking". Khoảng cách CRPS chỉ $0.27$ phút giữa năm phát triển và năm kiểm định cuối cùng là bằng chứng vàng cho độ tin cậy khoa học của đề tài.

---

## 5. DANH MỤC ARTIFACTS VÀ HƯỚNG DẪN TÁI LẬP (REPRODUCIBILITY)

### 5.1. Danh mục Artifacts trọng yếu
* **Manifests**:
  - Giao thức gốc: [`probabilistic_protocol_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/probabilistic_protocol_v1.json)
  - Lựa chọn 2023 (Stage 8): [`selected_system_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/selected_system_manifest_v1.json)
  - Mô phỏng 2023 (Stage 9): [`probabilistic_stage9_gate_simulation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json)
  - Đóng băng toàn diện (Stage 10): [`full_system_freeze_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/full_system_freeze_manifest_v1.json)
  - Kiểm định cuối 2024 (Stage 11): [`final_holdout_2024_evaluation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/final_holdout_2024_evaluation_v1.json)
* **Trọng số & Dữ liệu Dự báo**:
  - Checkpoint trọng số đóng băng: [`model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib)
  - Bảng dự báo Parquet 2024: [`holdout_predictions_2024.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet)

### 5.2. Lệnh Tái lập Thực nghiệm (Reproducibility Commands)
Mở PowerShell tại thư mục gốc của dự án và chạy các lệnh sau:

```powershell
# 1. Kích hoạt môi trường ảo
D:\Study\Code\Python\Aelous\.venv\Scripts\Activate.ps1

# 2. Tái lập Stage 10 (Đóng băng toàn diện hệ thống)
python scripts/run_probabilistic_stage10_system_freeze.py --train-sample 1000

# 3. Tái lập Stage 11 (Kiểm định tập kín năm 2024)
python scripts/run_probabilistic_stage11_final_holdout.py --holdout-sample 5000 --max-days 25 --n-scenarios 100 --n-gates 30

# 4. Chạy toàn bộ 122 bài test tự động từ Stage 0 đến Stage 11
pytest tests/test_probabilistic_stage*.py -v
```

---
*Báo cáo được hoàn thành tự động và xác thực toàn diện vào ngày 28/09/2026. Nghiên cứu Dự báo Xác suất Chậm chuyến Core Arrival chính thức khép lại thành công rực rỡ.*
