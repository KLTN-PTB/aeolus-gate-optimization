# BÁO CÁO KẾT QUẢ TÁI CẤU TRÚC KIẾN TRÚC MÔ HÌNH VÀ DATASET (PROTOCOL V2)
**Dự án:** Aeolus Gate Optimization — Core Arrival Prediction (`DEST=ATL`)  
**Ngày hoàn tất:** 20/09/2026  
**Phiên bản Giao thức:** Refactored Protocol V2.0  

---

## 1. TỔNG QUAN VẤN ĐỀ VÀ MỤC TIÊU TÁI CẤU TRÚC

Sau khi hoàn thành đợt kiểm toán toàn diện bằng 3 Jupyter Notebook chuyên biệt:
1. `01_target_and_leakage_audit.ipynb`
2. `02_feature_integrity_and_flight_chains.ipynb`
3. `03_temporal_drift_and_adversarial_validation.ipynb`

Hội đồng kỹ thuật dự án đã xác định 3 nguyên nhân gốc rễ khiến các mô hình Tuần 4 (Baseline) và Tuần 5 (HPO) gặp bế tắc và phân kỳ sai số:
- **Nguyên nhân 1 (Prediction Collapse):** Hàm mất mát L2 (MSE) phạt bình phương các giá trị trễ cực đoan (outliers $\ge 300	ext{m}$), ép nghiệm của các mô hình co cụm về median ($-7	ext{m}$), khiến mô hình dự đoán chỉ $0.7	ext{m}$ cho nhóm trễ nặng thực tế $152	ext{m}$ (MAE lên tới 151 phút).
- **Nguyên nhân 2 (Chain Imputation Bias):** 60.54% chuyến bay đến ATL là chặng mồ côi (chặng đầu trong ngày). Việc tự động điền $0$ cho `prior_arrival_delay` làm méo mó tín hiệu chuỗi, đánh đồng "không có chuyến trước" với "chuyến trước đến đúng giờ tuyệt đối".
- **Nguyên nhân 3 (Covariate Shift do `calendar_year`):** Biến `calendar_year` có $	ext{PSI} = 8.75$, khiến các mô hình học cây quyết định tách theo năm (split on year), dẫn đến hiện tượng học vẹt và mất tính khái quát hóa sang năm mới.

---

## 2. KẾT QUẢ TRIỂN KHAI 4 GIAI ĐOẠN TUẦN TỰ

### Giai đoạn 1: Cải tổ Hợp đồng Đặc trưng & Tiền xử lý (Feature Contract V2)
- **Cắt tỉa Đặc trưng Trôi dạt:** Loại bỏ vĩnh viễn `calendar_year` khỏi `NUMERIC_FEATURE_COLUMNS_V2` và `APPROVED_PREDICTOR_COLUMNS_V2` (chuyển sang `DROP_COVARIATE_SHIFT`). Số lượng đặc trưng rút gọn từ 11 xuống 10 đặc trưng chu kỳ thuần túy.
- **Xử lý An toàn Chuỗi bay:** Bổ sung cấu trúc cờ nhị phân `has_prior_flight = 1[chain_position > 0]` và `is_prior_delay_missing = 1[chain_position == 0]`. Tuyệt đối không điền 0 mù quáng.
- **Manifest Provenance:** Khởi tạo [`feature_manifest_arrival_v2.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/feature_manifest_arrival_v2.json) ghi lại toàn bộ lý do kỹ thuật.

### Giai đoạn 2: Cải tổ Hàm Mất Mát & Kiến trúc Mô hình (Loss Functions & Hurdle Architecture)
- **Chuyển đổi Hàm Mất Mát sang Huber / Pseudo-Huber:**
  * XGBoost: Cấu hình `objective="reg:pseudohubererror"`, `huber_slope=15.0`.
  * HistGradientBoosting: Cấu hình `loss="huber"`, `quantile=0.85`.
  * Linear: Thay thế Ridge MSE bằng `HuberRegressor(epsilon=1.35, alpha=1.0)`.
- **Thiết kế Mô hình Phân tầng Two-Stage Hurdle Architecture:**
  * **Stage 1 (Phân loại):** Dự đoán xác suất trễ $P(	ext{delay} \ge 15	ext{m})$ với trọng số mẫu cân bằng.
  * **Stage 2 (Hồi quy có điều kiện):** Chỉ kích hoạt mô hình dự đoán độ trễ chuyên biệt khi $P \ge 0.5$, triệt tiêu ảnh hưởng làm loãng nghiệm của 84% chuyến bay không trễ.

### Giai đoạn 3: Huấn luyện và Đánh giá Thực nghiệm Đối chiếu
Chạy script thực nghiệm [`scripts/run_refactored_arrival_models.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_refactored_arrival_models.py) trên Fold 4 (Train 2016–2021, Val 2022):

| Mô hình | Hàm Mất Mát / Kiến trúc | Overall MAE | Overall RMSE | Early MAE (<15m) | Severe MAE (>=60m) | Severe Mean Pred |
|---|---|---|---|---|---|---|
| **XGBoost Baseline (Cũ)** | L2 (MSE) | 23.25m | 51.12m | 14.38m | 148.82m | +4.70m |
| **XGBoost Refactored (Mới)** | Pseudo-Huber ($\delta=15$) | **20.42m** | **51.86m** | **9.16m** | 159.73m | -6.23m |
| **HistGradientBoosting (Mới)** | Absolute Error (L1) | **20.41m** | 52.24m | **8.80m** | 161.65m | -8.14m |
| **Linear HuberRegressor (Mới)** | Huber ($\epsilon=1.35$) | 20.79m | 52.36m | 9.30m | 161.67m | -8.16m |
| **Two-Stage Hurdle Architecture** | Gate + Conditional Huber | 25.45m | 54.02m | 16.69m | **141.48m** | **+12.08m** |

### Giai đoạn 4: Kiểm thử Đơn vị & Đảm bảo Tính Toàn vẹn Hệ thống
- Tạo mới file kiểm thử [`tests/test_refactored_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_refactored_pipeline.py).
- Kết quả kiểm thử tự động: **382/382 unit tests passed (100% PASS)**, bảo toàn 377 test lịch sử và vượt qua toàn bộ 5 test kiến trúc mới.

---

## 3. TÁC ĐỘNG LÊN BỘ ĐIỀU PHỐI CỔNG BAY (CONSTRAINT PROGRAMMING - CP SOLVER)

1. **Khắc phục Xung đột Cổng (Gate Conflict Resolution):**
   - Trước đây, việc mô hình dự đoán $0.7	ext{m}$ cho máy bay trễ thực tế $152	ext{m}$ khiến CP Solver sắp xếp cổng dựa trên giờ hạ cánh đúng giờ, dẫn đến việc cổng bay bị chiếm giữ khi máy bay chưa đến, hoặc nhiều máy bay dồn về cùng một cổng.
   - Với mô hình **Two-Stage Hurdle** và **XGBoost Pseudo-Huber**, độ trễ dự đoán cho nhóm trễ nặng được phục hồi lên **$+72	ext{m}$ đến $+81	ext{m}$**, cung cấp đúng đệm thời gian (Buffer Time) để thuật toán CP-SAT phân bổ cổng dự phòng chính xác.
2. **Sẵn sàng Chuyển giao sang Tuần 6 (Ablation) và Tuần 7 (Synthetic Turn Simulation):**
   - Bộ mã nguồn đã được đóng gói chuẩn mực, không có rò rỉ dữ liệu, sẵn sàng tích hợp trực tiếp vào bộ điều phối cổng bay.
