# Aeolus Gate Optimization — Tóm tắt toàn bộ dự án

> **Trạng thái cập nhật chính thức**: Đã hoàn thành toàn bộ chuỗi nghiên cứu, thực nghiệm và kiểm toán pháp y đến **Phase R37 — Final Forensic Certification V5** (tháng 10/2026). Hệ thống đã đạt phán quyết **`CERTIFIED_WITH_LIMITATIONS`**. Toàn bộ dữ liệu kiểm định độc lập Post-Holdout năm 2024 đã được mở và đánh giá hậu đóng băng (post-freeze) với sự kiểm soát rò rỉ dữ liệu nghiêm ngặt.

---

## 1. Kết luận nhanh & Các cột mốc đã đạt được

1. **Chu trình hoạt động**: Dự án vận hành hoàn chỉnh theo chu trình khép kín:
   $$\text{Predict (Point + Probabilistic)} \longrightarrow \text{Simulate (Synthetic Turns)} \longrightarrow \text{Optimize (CP-SAT/SA/Greedy)} \longrightarrow \text{Evaluate \& Certify}$$
2. **Bài toán lõi (Core Arrival Task)**:
   - Quần thể: Các chuyến bay thương mại đến Atlanta Hartsfield-Jackson (`DEST = 'ATL'`).
   - Thời điểm chốt dự báo: $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ giờ}$ trước khi khởi hành.
   - Mục tiêu:
     - Phân loại: $y_{\text{arr\_cls}} = 1[\text{ARR\_DELAY} \ge 15\text{ phút}]$.
     - Hồi quy: $y_{\text{arr\_reg}} = \text{ARR\_DELAY}$ có dấu (signed minutes), không lấy trị tuyệt đối, không cắt ngọn (clipping) và không điền khuyết target.
   - Không gian đặc trưng: Chỉ sử dụng **Schedule + Calendar + Carrier + Route** đã được kiểm toán an toàn tại thời điểm $T-2\text{h}$. Tuyệt đối **không dùng Thời tiết (Weather)** và **không dùng Chuỗi tàu bay (Flight Chain)** trong luồng Core Arrival.
3. **Kết quả đánh giá trên tập kiểm định độc lập 2024 Post-Holdout ($N = 5.000$ chuyến bay)**:
   - **Mô hình Điểm (Point Regression)**:
     - Ridge Regression (`arrival_linear_baseline_v1`): $\text{MAE} = \mathbf{22.9125}\text{ phút}$.
     - 50/50 Weighted Ensemble (`arrival_weighted_ensemble_v1`): $\text{MAE} = \mathbf{23.3175}\text{ phút}$.
     - *(Ghi chú: Trên tập Dev 2023, Ridge và Ensemble hòa nhau trong dải vô sai $0.10$ phút; trên tập 2024 Holdout, Ridge có MAE thấp hơn $0.405$ phút. Không có một mô hình quán quân tổng thể duy nhất).*
   - **Mô hình Phân vị Xác suất (Quantile Forecasting)**:
     - P5 Quantile Regression (9 phân vị qua Multi-pinball LightGBM): Đạt xấp xỉ CRPS $\text{CRPS}_{\text{approx}} = \mathbf{16.7724}\text{ phút}$ (tập dev: $16.85$ min), Mean Pinball Loss $= \mathbf{6.8211}\text{ phút}$. P5 không có hàm mật độ liên tục (`CONTINUOUS_DENSITY: NOT_AVAILABLE`).
   - **Mô hình Mật độ Liên tục Tham số (Continuous Density)**:
     - P4 NGBoost Student-T: Cung cấp mật độ liên tục 3 tham số ($\mu, \sigma, \nu$), đạt Exact Continuous $\text{CRPS} = \mathbf{17.6532}\text{ phút}$ và Continuous $\text{NLL} = \mathbf{4.6307}$. P4 hỗ trợ lấy mẫu Monte Carlo liên tục cho mô phỏng cổng hạ nguồn.
4. **Kết quả tối ưu hóa gán cổng hạ nguồn (Downstream Gate Optimization)**:
   - Đánh giá trên 28 bài toán lập lịch theo 4 kịch bản mùa năm 2024 với trần thời gian thực $T = 2.0$ giây:
     - **Deterministic Greedy**: Chạy siêu nhanh trong **$1.1$ ms**, đạt chi phí mục tiêu $7181.45$ (khả thi ràng buộc cứng 100%).
     - **Google OR-Tools CP-SAT**: Giải bằng phương pháp nhánh cận (Branch-and-Bound), **chứng minh đạt nghiệm tối ưu toàn cục (OPTIMAL) trên 100% bài toán (28/28)** trong thời gian trung bình **$0.4438$ giây**, giảm chi phí xuống mức tối ưu **$7167.17$**.
     - **Simulated Annealing (SA)**: Chạy tìm kiếm cục bộ ngẫu nhiên hết $2.00$ giây, đạt chi phí $7167.88$.
     - **Hybrid CP-SAT + SA**: Chia đôi ngân sách ($1.0\text{s} + 1.0\text{s}$), đạt chi phí tối ưu **$7167.17$** với mức tăng biên $\Delta = 0.0000$ (do CP-SAT đã tìm ra nghiệm tối ưu toàn cục ngay trong 1.0s đầu).
5. **Chứng nhận pháp y & Kiểm thử hồi quy**:
   - Trạng thái: **`CERTIFIED_WITH_LIMITATIONS`** (Phase R37 V5).
   - Kiểm thử hồi quy: **180/180 bài test tự động vượt qua 100%** trong thời gian 5.0 giây.

---

## 2. Kiến trúc và các quyết định khóa

### Hai task độc lập (Dual Prediction Architecture)

| Task | Population | Target | Weather | Vai trò |
|---|---|---|---|---|
| **Core Arrival** | Inbound `DEST=ATL` | Phân loại $1[\text{ARR} \ge 15]$ + Hồi quy có dấu `ARR_DELAY` | **Không được dùng** | Nhánh duy nhất được đưa vào mô phỏng và tối ưu hóa cổng hạ nguồn |
| **Auxiliary Departure** | Outbound `ORIGIN=ATL` | Phân loại $y_{\text{dep\_cls}} = 1[\text{DEP\_DELAY} \ge 15]$ | Chỉ dùng external point-in-time Weather sau audit | Nghiên cứu phụ trợ, **tuyệt đối cách ly không feed vào optimizer** |

### Kỷ luật phân hoạch thời gian (Temporal Discipline)

| Phân hoạch | Năm dữ liệu | Mục đích sử dụng | Quy tắc quản trị |
|---|---|---|---|
| **Rolling Folds 1–4** | 2016–2022 | Huấn luyện mô hình, tinh chỉnh siêu tham số (HPO) | Nghiêm cấm random split, preprocessor chỉ fit trên train của từng fold |
| **Model Selection** | 2023 | Đánh giá so sánh, chọn cấu hình mô hình | Đóng băng siêu tham số, không dùng để tune lại model |
| **Post-Holdout** | 2024 | Kiểm định độc lập cuối cùng hậu đóng băng (Post-freeze) | Đánh giá một lần duy nhất theo giao thức đóng băng; cấm mọi hình thức retrain |

### Phân định dữ liệu Chuỗi tàu bay (Flight Chain) và Thời tiết (Weather)

- **Flight Chain thô (`.pt`)**: Giữ nhãn `FINAL_NO_GO`, chỉ đọc, tuyệt đối không dùng trong huấn luyện.
- **Schedule Flight Chain tái cấu trúc (`schedule_chain_v1`)**: Mặc dù đạt `FULL_DATA_PASS` ở cấp độ tái cấu trúc, nhưng kiểm toán E006 xác định không đủ bằng chứng công bố trước $T-2\text{h}$ nên toàn bộ đặc trưng Chain tiếp tục bị loại bỏ khỏi Core Arrival.
- **Dữ liệu thời tiết thô của Aeolus**: 6 trường `O_*` và `D_*` bị loại bỏ hoàn toàn (`DROP_FROM_PREDICTORS`) vì không chứng minh được tính sẵn sàng tại thời điểm dự báo.

---

## 3. Dataset từ thô đến tiền xử lý

### 3.1. Dữ liệu bảng thô (Raw Tabular)
Gồm 9 tập CSV hàng năm `data/raw/tabular/<year>/flight_with_weather_<year>.csv` (2016–2024) với tổng cộng **54.674.003 chuyến bay (15.2 GB)**. Tất cả 9 năm đều tuân thủ đúng 34 trường dữ liệu chuẩn hoá, không có bản ghi trùng lặp và min/max ngày chuẩn theo năm.

### 3.2. Phân chia lưu lượng chuyến bay theo ATL

| Năm | Vai trò phân hoạch | Toàn mạng bay Tabular | Inbound ATL (`DEST=ATL`) | Outbound ATL (`ORIGIN=ATL`) |
|---:|---|---:|---:|---:|
| 2016 | DEVELOPMENT | 5,537,987 | 381,166 | 381,303 |
| 2017 | DEVELOPMENT | 5,575,872 | 358,263 | 358,537 |
| 2018 | DEVELOPMENT | 6,986,842 | 386,580 | 386,460 |
| 2019 | DEVELOPMENT | 7,161,827 | 391,075 | 391,053 |
| 2020 | DEVELOPMENT | 4,312,091 | 242,121 | 242,207 |
| 2021 | DEVELOPMENT | 5,755,666 | 309,621 | 309,488 |
| 2022 | DEVELOPMENT | 6,413,416 | 311,701 | 311,746 |
| 2023 | SELECTION | 6,645,461 | 332,741 | 332,734 |
| 2024 | POST_HOLDOUT | 6,284,841 | 309,165 | 309,142 |
| **Tổng** | — | **54,674,003** | **3,022,433** | **3,022,670** |

---

## 4. Bảng tổng hợp mô hình và kết quả chính thức

### 4.1. Kết quả trên tập Holdout 2024 (Authoritative Final Post-Holdout)

| Mô hình | Họ thuật toán | Vai trò chính thức | MAE (phút) | Exact CRPS (phút) | Approx CRPS (phút) | Pinball (phút) | Continuous NLL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`arrival_linear_baseline_v1`** | Ridge | Point Co-champion (Dev 2023) | **22.9125** | — | — | — | — |
| **`arrival_xgboost_baseline_v1`** | XGBoost | Point Benchmark | 24.3643 | — | — | — | — |
| **`arrival_weighted_ensemble_v1`** | Ridge + XGBoost | Point Co-champion (Dev 2023) | 23.3175 | — | — | — | — |
| **`P5_quantile_regression`** | Multi-head LightGBM | Dự báo Phân vị Xác suất | 21.6881 | — | **16.7724** | **6.8211** | N/A |
| **`P4_ngboost_student_t`** | NGBoost Student-T | Mô phỏng Mật độ Liên tục | 23.2359 | **17.6532** | — | — | **4.6307** |
| **`oracle_actual`** | Thực tế trễ đã xảy ra | Chặn trên lý thuyết phi nhân quả | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |

### 4.2. Kết quả tối ưu hóa gán cổng hạ nguồn (28 kịch bản mùa 2024)

| Thuật toán Solver | Ngân sách cấu hình | Thời gian chạy thực tế trung bình | Khả thi ràng buộc cứng | Vi phạm cổng | Hàm mục tiêu chi phí trung bình | Trạng thái nghiệm |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`DeterministicGreedy`** | Wall-clock 2.0s | **0.0011 s (1.1 ms)** | 100% (28/28) | 0 | 7181.45 | FEASIBLE |
| **`CPSat`** | Wall-clock 2.0s | **0.4438 s** | 100% (28/28) | 0 | **7167.17** | **OPTIMAL (28/28)** |
| **`SimulatedAnnealing`** | Wall-clock 2.0s | **2.0009 s** | 100% (28/28) | 0 | 7167.88 | FEASIBLE |
| **`HybridCPSatSA`** | Split (1.0s + 1.0s) | **1.4531 s** | 100% (28/28) | 0 | **7167.17** | FEASIBLE |

---

## 5. Cập nhật trạng thái các hạng mục (Resolution Matrix)

So với trạng thái ban đầu của giai đoạn phát triển, toàn bộ 6 hạng mục kỹ thuật đã được giải quyết dứt điểm:

1. **Final Holdout 2024**: Đã mở và đánh giá hoàn tất post-freeze trong Phase R23, được kiểm toán rò rỉ dữ liệu và đối chiếu số liệu mã hóa trong R28, R31, R33, R36 và R37.
2. **Weighted Ensemble**: Đã hoàn thành huấn luyện và đánh giá. Mô hình đạt MAE $24.6177$ phút trên Dev 2023 (hòa với Ridge trong ngưỡng vô sai $0.10$ phút) và $23.3175$ phút trên Holdout 2024.
3. **Auxiliary Departure + External Weather**: Đã xây dựng đầy đủ hợp đồng point-in-time (`weather_point_in_time_contract_v1`), giữ nguyên ranh giới cách ly nghiên cứu không đưa vào bộ giải cổng.
4. **Flight Chain ML Ablation**: Hoàn tất kiểm toán dữ liệu và quyết định loại bỏ fail-closed khỏi Core Arrival do không có bằng chứng lịch phát hành trước $T-2\text{h}$.
5. **Mô phỏng và Tối ưu hóa hạ nguồn**: Đã xây dựng hoàn chỉnh benchmark 28 kịch bản operational seasonal với 4 solvers, chứng minh tính tối ưu toàn cục của CP-SAT và tính khả thi 100% của giải thuật.
6. **Toàn vẹn tệp tin và mã băm**: Tất cả 42 tệp tin manifest và kết quả kiểm toán cốt lõi đều được bảo vệ bằng mã băm SHA-256 sidecar với tỷ lệ khớp 100.0%.

---

## 6. Ranh giới luận điểm khoa học & Giới hạn được công nhận

Dự án tuân thủ nghiêm ngặt các ranh giới phương pháp luận đã được thẩm định pháp y tại R36 và R37:

- **Không tuyên bố một Quán quân duy nhất (No Single Overall Champion)**: Mỗi mô hình phục vụ một mục đích riêng (Ridge cho dự báo điểm nhanh, P5 cho phân vị xác suất, P4 cho mô phỏng Monte Carlo liên tục).
- **Không nhầm lẫn công bằng Wall-clock và Công tính toán**: Các solver cùng tuân thủ trần thời gian 2.0s nhưng thực hiện các mô thức tính toán khác nhau.
- **Môi trường tái lập có kiểm soát (Contained Specification)**: Tính lặp lại bit-for-bit được chứng nhận trong phạm vi Python 3.11.15 trên Windows 10 AMD64 với virtual environment đã cố định package; không khẳng định tái lập tuyệt đối trên mọi kiến trúc CPU/OS khác nhau.
- **Không phóng đại vận hành thực tế**: Toàn bộ kết quả tối ưu cổng được đánh giá trên dữ liệu mô phỏng tổng hợp (synthetic research instances); không khẳng định triển khai thực tế tại sân bay ATL.

---

## 7. Tài liệu chỉ dẫn tra cứu chính thức

1. **Sơ đồ mục lục tài liệu toàn diện**: [`docs/README.md`](docs/README.md)
2. **Chứng nhận pháp y tối hậu (V5)**: [`docs/audit/FINAL_EVIDENCE_CERTIFICATION_V5.md`](docs/audit/FINAL_EVIDENCE_CERTIFICATION_V5.md)
3. **Biên bản hợp nhất bằng chứng (V2)**: [`docs/audit/FINAL_EVIDENCE_RECONCILIATION_V2.md`](docs/audit/FINAL_EVIDENCE_RECONCILIATION_V2.md)
4. **Kiểm toán nguồn gốc số liệu P4**: [`docs/audit/R33_P4_METRIC_LINEAGE.md`](docs/audit/R33_P4_METRIC_LINEAGE.md)
5. **Kiểm toán toán học mô hình P5**: [`docs/audit/R34_P5_MATHEMATICAL_AUDIT.md`](docs/audit/R34_P5_MATHEMATICAL_AUDIT.md)
6. **Kiểm toán bộ giải và môi trường**: [`docs/audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md`](docs/audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md)
7. **Cấu trúc thư mục repository**: [`project_structure.md`](project_structure.md)
