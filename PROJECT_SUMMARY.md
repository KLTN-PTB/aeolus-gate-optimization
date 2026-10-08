# Aeolus Gate Optimization — Tóm tắt toàn bộ dự án

> **Trạng thái cập nhật chính thức**: Đã hoàn thành toàn bộ chuỗi nghiên cứu, thực nghiệm, sửa chữa phương pháp luận và kiểm toán chứng nhận khoa học đến **Phase P14 — Final Scientific Certification & Conditional Rebuild Decision** (tháng 10/2026). Hệ thống đã đạt phán quyết tối hậu **`CERTIFIED_WITH_LIMITATIONS`** với kết luận **`REBUILD_REQUIRED = NO`**. Dữ liệu 2024 được quản trị chặt chẽ qua 2 thế hệ bằng chứng độc lập: dữ liệu lịch sử trước sửa chữa (`HISTORICAL_2024_RESULTS`) và đợt tái đánh giá hậu đóng băng sau sửa chữa (`P11R_POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR`).

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
   - Không gian đặc trưng: Chỉ sử dụng **Schedule + Calendar + Carrier + Route** (10 đặc trưng dạng bảng) đã được kiểm toán an toàn tại thời điểm $T-2\text{h}$. Tuyệt đối **không dùng Thời tiết (Weather)** và **không dùng Chuỗi tàu bay (Flight Chain)** trong luồng Core Arrival.
3. **Kết quả kiểm định trên tập dữ liệu 2024 (Dual Evidence Generations)**:
   - **Thế hệ 1 — Dữ liệu Lịch sử (`HISTORICAL_2024_RESULTS`)**:
     - Ridge Regression: $\text{MAE} = \mathbf{22.9125}\text{ phút}$.
     - P5 Quantile Regression (Role B): $\text{CRPS}_{\text{approx}} = \mathbf{16.7724}\text{ phút}$, Pinball Loss $= \mathbf{6.8211}\text{ phút}$, MAE $= 21.6881$ phút. (Chỉ dự báo phân vị cận biên, forecast-only, không hỗ trợ lấy mẫu Monte Carlo).
     - P4 NGBoost Student-T: Continuous $\text{CRPS} = \mathbf{17.6532}\text{ phút}$, Continuous $\text{NLL} = \mathbf{4.6307}$.
   - **Thế hệ 2 — Tái đánh giá Hậu đóng băng sau Sửa chữa (`P11R_POST_HOLDOUT_REEVALUATION`)**:
     - Ridge Regression Baseline: $\text{MAE} = \mathbf{23.39}\text{ phút}$.
     - P4 NGBoost Student-T (Role C — Continuous Downstream Simulation Champion): $\text{MAE} = \mathbf{21.97}\text{ phút}$, $\text{RMSE} = \mathbf{54.21}\text{ phút}$, Continuous $\text{CRPS} = \mathbf{18.33}\text{ phút}$ (tính bằng công thức giải tích đóng Student-T của Jordan et al.), Continuous $\text{NLL} = \mathbf{4.62}$, Brier ($Y \ge 15$) $= \mathbf{0.1544}$, bậc tự do trung bình $\nu = \mathbf{2.52} \in [2.10, 2.78]$.
     - P5 Quantile Regression: Giữ nguyên là mô hình Role B (forecast-only), không tái huấn luyện hay tái cấu trúc theo quyết định R39/P10-A.
4. **Kết quả tối ưu hóa gán cổng hạ nguồn (Downstream Gate Optimization)**:
   - Đánh giá trên 28 bài toán mùa lịch sử (112 runs) và 16 bài toán kiểm định P11-R (64 runs) với trần thời gian thực nghiêm ngặt $T = 2.0$ giây:
     - **Deterministic Greedy**: Chạy trong **$1.1$ ms**, đạt khả thi ràng buộc cứng 100%.
     - **Google OR-Tools CP-SAT**: Phương pháp nhánh cận (Branch-and-Bound), **chứng minh đạt nghiệm tối ưu toàn cục (OPTIMAL) trên 100% bài toán (28/28)** trong trung bình **$0.44$ giây**.
     - **Simulated Annealing (SA)**: Chạy tìm kiếm cục bộ ngẫu nhiên trần $2.00$ giây, đạt chi phí bám sát tối ưu.
     - **Mô phỏng khả thi hạ nguồn với P4 Native Draws**: Dưới 500 cú sốc ngẫu nhiên phân phối Student-T tại cao điểm mùa hè, giải pháp gán cổng bằng P4 đạt **100% khả thi ràng buộc cứng** (0 xung đột cổng, 0 vi phạm đệm tow-buffer), vượt trội hoàn toàn so với 27.6% của schedule-only, 2.4% của Ridge baseline, và 0.0% của oracle baseline.
5. **Chứng nhận khoa học & Kiểm thử hồi quy**:
   - Trạng thái tối hậu: **`CERTIFIED_WITH_LIMITATIONS`** với **`REBUILD_REQUIRED = NO`** (Phase P14).
   - Toàn bộ suite kiểm thử: **1.216 bài test tự động vượt qua 100%** (trong đó có 75 certification gate tests, 21 P11-R downstream parity tests, 180 regression tests lịch sử; 4 guard tests cũ được cách ly bảo lưu an toàn qua `pytest.ini`).

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
| **Historical 2024** | 2024 | Đánh giá ban đầu trước sửa chữa phương pháp luận | Lưu trữ bất biến (`artifacts/post_holdout_v3/`) |
| **P11-R Re-evaluation** | 2024 | Tái đánh giá độc lập một lần sau đóng băng hệ thống P10-B | Đánh giá hậu đóng băng (`artifacts/post_holdout_re_evaluation_v1/`) |

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

## 4. Bảng tổng hợp mô hình và số liệu chính thức

### 4.1. Bảng đối chiếu số liệu kiểm định 2024 (Lịch sử vs P11-R Repaired)

| Mô hình | Vai trò chức năng | MAE Lịch sử (2024) | MAE P11-R (2024) | Continuous CRPS | Approx CRPS | Continuous NLL | Nguồn minh chứng |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`arrival_linear_baseline_v1`** | Point Baseline | 22.9125 min | 23.39 min | — | — | — | `marginal_forecast_metrics_2024_v3.json`<br>`p11r_marginal_forecast_metrics_2024.json` |
| **`P5_quantile_regression`** | **Role B**: Quantile Champion | 21.6881 min | *(Forecast-only, giữ nguyên)* | — | 16.7724 min | — | `r34_p5_capability_forensics.json`<br>`final_scientific_certification_p14.json` |
| **`P4_ngboost_student_t`** | **Role C**: Continuous Simulation | 23.2359 min | **21.97 min** (RMSE: 54.21) | **18.33 min** (P11-R)<br>17.65 min (Hist) | — | **4.62** (P11-R)<br>4.63 (Hist) | `r33_p4_metric_lineage.json`<br>`p11r_marginal_forecast_metrics_2024.json` |
| **`oracle_actual`** | Chặn trên lý thuyết | 0.0000 min | — | 0.0000 min | 0.0000 min | — | `marginal_forecast_metrics_2024_v3.json` |

### 4.2. Kết quả tối ưu hóa gán cổng hạ nguồn (28 kịch bản mùa)

| Thuật toán Solver | Ngân sách cấu hình | Thời gian chạy thực tế trung bình | Khả thi ràng buộc cứng | Vi phạm cổng | Hàm mục tiêu chi phí trung bình | Trạng thái nghiệm |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`DeterministicGreedy`** | Wall-clock 2.0s | **0.0011 s (1.1 ms)** | 100% (28/28) | 0 | 7181.45 | FEASIBLE |
| **`CPSat`** | Wall-clock 2.0s | **0.4438 s** | 100% (28/28) | 0 | **7167.17** | **OPTIMAL (28/28)** |
| **`SimulatedAnnealing`** | Wall-clock 2.0s | **2.0009 s** | 100% (28/28) | 0 | 7167.88 | FEASIBLE |
| **`HybridCPSatSA`** | Split (1.0s + 1.0s) | **1.4531 s** | 100% (28/28) | 0 | **7167.17** | FEASIBLE |

---

## 5. Tiến trình Giải quyết Vấn đề & Chứng nhận Khoa học (Phases P10 – P15)

Dự án đã hoàn thành trọn vẹn chuỗi nhiệm vụ phương pháp luận và kiểm toán chứng nhận:

1. **Phase P10-A (P4 Native Downstream Parity)**: Triển khai động cơ lấy mẫu ngẫu nhiên trực tiếp từ phân phối Student-T của P4 cho Simulated Annealing, đạt 100% khả thi và giảm tối đa chi phí.
2. **Phase P10-B (Robustness, Recourse & System Freeze)**: Đánh giá độ bền vững trước 500 cú sốc, phân tích độ nhạy chi phí đệm và cố định trạng thái hệ thống trong `system_freeze_manifest.json`.
3. **Freeze-Gate & Phase P11-R (Post-Holdout Re-evaluation after Methodology Repair)**: Đánh giá độc lập 2024 hậu đóng băng; xác nhận độ chính xác của P4 (CRPS 18.33 min, NLL 4.62, MAE 21.97 min, $\nu = 2.52$) và tính khả thi 100% trong mô phỏng.
4. **Phases P12, P12.1, P12-R1 (Test Scope Reconciliation)**: Làm rõ cấu trúc 1.216 bài test hoạt động, 75 certification gate tests; cách ly an toàn 4 freeze-guard tests lịch sử không có caller thông qua `pytest.ini`.
5. **Phase P13 (Scoped Reproducibility Audit)**: Xác nhận khả năng tái lập độc lập trong phạm vi môi trường chuẩn (`CONTAINED_SPECIFICATION_REPRODUCIBILITY`).
6. **Phase P14 (Final Scientific Certification & Conditional Rebuild Decision)**: Thẩm định toàn bộ 13 luận điểm khoa học, kết luận `CERTIFIED_WITH_LIMITATIONS` và xác nhận thỏa mãn toàn bộ 8 tiêu chuẩn không cần xây dựng lại (`REBUILD_REQUIRED = NO`).
7. **Phase P15 (Thesis Evidence Normalization)**: Chuẩn hóa toàn bộ hệ thống tài liệu khoa học đồng bộ với phán quyết P14 mà không thay đổi bất kỳ hiện vật khoa học hay mã nguồn mô hình nào.

---

## 6. Ranh giới Luận điểm Khoa học & Giới hạn Được Công nhận

Dự án tuân thủ nghiêm ngặt 9 giới hạn nhận thức luận chính thức:

- **Phân định rõ vai trò chức năng (Decoupled Roles)**: Ridge cho dự báo điểm tham chiếu, P5 cho phân vị cận biên (forecast-only), P4 cho mô phỏng Monte Carlo liên tục hạ nguồn. Tuyệt đối không tuyên bố một mô hình quán quân duy nhất.
- **Ranh giới công bằng thời gian thực (Equal Wall-Clock Budget)**: Các solver tuân thủ cùng trần thời gian 2.0s; không đồng nhất trần thời gian thực với lượng công toán học bằng nhau.
- **Không khẳng định hiệu chuẩn riêng cho P4**: `P4_CALIBRATION = NOT_SEPARATELY_CERTIFIED`.
- **Ranh giới mô phỏng nghiên cứu tổng hợp**: Toàn bộ kết quả tối ưu cổng được đánh giá trên kịch bản mô phỏng nghiên cứu; không tuyên bố áp dụng thực tế hay vận hành hiện trường tại ATL.
- **Không suy diễn ngoài tập dữ liệu**: Kết quả chỉ có giá trị trên quần thể đến ATL giai đoạn 2016–2024 với bộ 10 đặc trưng an toàn được phê duyệt.

---

## 7. Danh mục Tài liệu Chỉ dẫn Tra cứu Chính thức

1. **Chứng nhận Khoa học Tối hậu P14**: [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)
2. **Kiểm toán Khả năng Tái lập P13**: [`SCOPED_REPRODUCIBILITY_AUDIT.md`](SCOPED_REPRODUCIBILITY_AUDIT.md)
3. **Biên bản Hợp nhất Test Suite P12-R1**: [`FINAL_TEST_SCOPE_RECONCILIATION.md`](FINAL_TEST_SCOPE_RECONCILIATION.md)
4. **Báo cáo Tái đánh giá Hậu đóng băng P11-R**: [`P11R_FINAL_REPORT.md`](P11R_FINAL_REPORT.md)
5. **Báo cáo Chuẩn hóa Tài liệu Luận văn P15**: [`THESIS_EVIDENCE_NORMALIZATION_REPORT.md`](THESIS_EVIDENCE_NORMALIZATION_REPORT.md)
6. **Sổ đăng ký Kiến trúc & Mô hình (v4.0.0)**: [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
7. **Sơ đồ Cấu trúc Repository Toàn diện**: [`project_structure.md`](project_structure.md)
8. **Mục lục Tài liệu Master & Bản đồ Điều hướng**: [`docs/README.md`](docs/README.md)
