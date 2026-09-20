# TỔNG HỢP CÁC HẠNG MỤC VÀ KẾT QUẢ ĐÃ HOÀN THÀNH

**Đề tài:** Aeolus Gate Optimization  
**Phiên bản giao thức hiện hành:** Research Protocol V4.0 — Dual Prediction Architecture  
**Ngày tổng hợp:** 09/09/2026  
**Mục đích tài liệu:** Làm nguồn nội dung để biên soạn báo cáo hoặc chuyển đổi sang Microsoft Word (`.docx`).

---

## 1. Lưu ý về phạm vi và mức độ tin cậy của kết quả

Tài liệu này phân biệt hai nhóm kết quả:

1. **Kết quả chính thức theo protocol V4:** dữ liệu, schema, temporal split, kiểm soát leakage, preprocessing, Flight Chain và các manifest đã được kiểm thử trong pipeline của dự án.
2. **Kết quả notebook khám phá:** các thông số mô hình đã được lưu trong output của hai file `.ipynb`. Các kết quả này có giá trị tham khảo và chứng minh notebook đã chạy, nhưng **chưa được xem là kết quả đánh giá cuối cùng của protocol V4**.

Nguyên nhân là các notebook đã trực tiếp sử dụng năm 2024 để đánh giá, trong khi protocol hiện hành quy định 2024 là `FINAL_HOLDOUT`, chỉ được mở sau khi toàn bộ hệ thống đã được đóng băng. Ngoài ra, một số bước tiền xử lý và lựa chọn biến trong notebook chưa tuân thủ hoàn toàn feature contract V4. Chi tiết được trình bày tại Mục 10.

---

## 2. Tóm tắt điều hành

Dự án đã hoàn thành nền tảng dữ liệu và phương pháp cho bài toán dự báo chậm chuyến tại sân bay ATL, bao gồm:

- Kiểm kê và audit dữ liệu Aeolus từ năm 2016 đến 2024.
- Chuẩn hóa schema gồm 34 trường cho toàn bộ chín năm.
- Xây dựng dữ liệu Parquet theo năm với ba luồng: toàn bộ chuyến bay, chuyến đến ATL và chuyến rời ATL.
- Thiết lập bài toán dự báo tại thời điểm `CRS_DEP_TIME - 2 giờ`.
- Thiết lập temporal protocol theo expanding window, không dùng random split.
- Hoàn thiện feature contract và preprocessing contract cho Core Arrival.
- Audit Flight Chain gốc và quyết định không sử dụng do thiếu bằng chứng mapping/an toàn thời điểm.
- Tái dựng Schedule Flight Chain từ dữ liệu Tabular cho giai đoạn 2016–2023 với độ phủ 100%.
- Audit 18 feature ứng viên từ reconstructed Flight Chain; chưa có feature nào đủ bằng chứng để đưa vào mô hình.
- Chuẩn bị contract cho nguồn Weather point-in-time trong tương lai; chưa tải hoặc tích hợp dữ liệu Weather ngoài.
- Chạy hai notebook thử nghiệm với Logistic Regression, Random Forest và XGBoost cho hai bài toán phân loại `DEP_DELAY >= 15` và `ARR_DELAY >= 15`.
- Xác minh repository hiện tại với **222 unit tests passed** và **smoke test PASS** ngày 09/09/2026.

Trạng thái tổng thể hiện tại:

| Hạng mục | Trạng thái |
|---|---|
| Tuần 1 — phạm vi, audit plan, reproducibility | Hoàn thành |
| Tuần 2 — schema, canonical data, temporal protocol | Hoàn thành |
| Week 3A — Core Arrival preprocessing | Hoàn thành |
| Week 3B — Flight Chain feature gate | Hoàn thành, nhánh ML bị khóa |
| Week 3C — Weather contract | Hoàn thành contract, chưa có dữ liệu Weather |
| Notebook thử nghiệm classification | Đã chạy và có output |
| Core Arrival model chính thức theo V4 | Chưa huấn luyện |
| Simulation và gate optimization | Chưa thực hiện |
| Đánh giá final holdout 2024 theo V4 | Chưa được phép thực hiện |

---

## 3. Mục tiêu và kiến trúc nghiên cứu

### 3.1. Mục tiêu tổng quát

Dự án hướng tới xây dựng chuỗi xử lý:

```text
Dự báo chậm chuyến
    -> Tạo Synthetic Aircraft Turn
    -> Mô phỏng hoạt động cổng
    -> Tối ưu phân bổ cổng
    -> Đánh giá và trực quan hóa
```

### 3.2. Kiến trúc dự báo V4

Protocol V4 tách hai bài toán:

#### Core Arrival

- Phạm vi: các chuyến bay đến ATL, điều kiện `DEST = ATL`.
- Thời điểm dự báo: `T = CRS_DEP_TIME - 2 giờ`.
- Phân loại: `y_arr_cls = 1[ARR_DELAY >= 15]`.
- Hồi quy: `y_arr_reg = ARR_DELAY` theo số phút có dấu.
- Nhóm thông tin: Schedule, Calendar, Carrier và Route.
- Không sử dụng Weather, biến vận hành thực tế hoặc kết quả Departure.
- Đây là nguồn prediction duy nhất được phép đưa vào simulation và optimization.

#### Auxiliary Departure

- Phạm vi thiết kế: các chuyến bay rời ATL, điều kiện `ORIGIN = ATL`.
- Phân loại: `y_dep_cls = 1[DEP_DELAY >= 15]`.
- Mục tiêu nghiên cứu tương lai: so sánh Schedule-only với Schedule + Weather point-in-time đã được audit.
- Không có bài toán Departure regression trong baseline V4.
- Kết quả Auxiliary Departure không được đưa vào optimizer.

---

## 4. Dữ liệu đã audit và xử lý

### 4.1. Dữ liệu Tabular gốc

Đã audit đầy đủ dữ liệu từ năm 2016 đến 2024 theo từng năm và theo chunks. Kết quả:

- Tổng số bản ghi: **54.674.003**.
- Tổng số trường trong schema: **34**.
- Cả chín năm có đủ 34 trường theo cùng thứ tự.
- Không phát hiện schema drift không thể dung hòa.
- `FL_DATE` bao phủ đúng năm được gắn nhãn.
- Không phát hiện dòng trùng lặp chính xác trong từng file năm.
- `ARR_DELAY` có giá trị hữu hạn trên toàn bộ dữ liệu đã audit.
- Sáu trường Weather đều có mặt, nhưng chưa có bằng chứng chúng là forecast sẵn có tại T−2h.

| Năm | Tổng số dòng | Inbound ATL | Outbound ATL | Vai trò hiện hành |
|---:|---:|---:|---:|---|
| 2016 | 5.537.987 | 381.166 | 381.303 | Rolling development |
| 2017 | 5.575.872 | 358.263 | 358.537 | Rolling development |
| 2018 | 6.986.842 | 386.580 | 386.460 | Rolling development |
| 2019 | 7.161.827 | 391.075 | 391.053 | Rolling development/validation |
| 2020 | 4.312.091 | 242.121 | 242.207 | Rolling development/validation |
| 2021 | 5.755.666 | 309.621 | 309.488 | Rolling development/validation |
| 2022 | 6.413.416 | 311.701 | 311.746 | Rolling development/validation |
| 2023 | 6.645.461 | 332.741 | 332.734 | Development model selection |
| 2024 | 6.284.841 | 309.165 | 309.142 | Final holdout |
| **Tổng** | **54.674.003** | **3.022.433** | **3.022.670** | — |

### 4.2. Dữ liệu processed đã tạo

Ba bộ dữ liệu Parquet phân vùng theo năm đã được materialize:

| Dataset | Nội dung | Tổng dòng |
|---|---|---:|
| `data/processed/tabular_by_year/` | Toàn bộ dữ liệu canonical | 54.674.003 |
| `data/processed/inbound_atl/` | Các chuyến có `DEST = ATL` | 3.022.433 |
| `data/processed/outbound_atl/` | Các chuyến có `ORIGIN = ATL` | 3.022.670 |

Các bước validation đã kiểm tra:

- Row count và schema của Parquet khớp manifest.
- Bộ inbound chỉ chứa `DEST = ATL`.
- Bộ outbound chỉ chứa `ORIGIN = ATL`.
- Chữ ký và metadata của nguồn raw không thay đổi.
- `flight_key` phục vụ truy vết và join, không phải mã máy bay và không phải feature ML.
- Phân vùng 2024 vẫn được gắn vai trò `FINAL_HOLDOUT`.

---

## 5. Temporal protocol và kiểm soát leakage

### 5.1. Expanding-window split

Không sử dụng random split. Bốn fold development được khóa như sau:

| Fold | Năm huấn luyện | Năm validation |
|---|---|---:|
| Fold 1 | 2016–2018 | 2019 |
| Fold 2 | 2016–2019 | 2020 |
| Fold 3 | 2016–2020 | 2021 |
| Fold 4 | 2016–2021 | 2022 |

Vai trò các năm sau development:

- **2023:** model selection và controlled ablation; không dùng để HPO hoặc fit calibration/ensemble weights.
- **2024:** final holdout; không dùng để chọn feature, model, hyperparameter, simulation parameter hoặc optimization configuration.

### 5.2. Các nhóm biến bị loại khỏi Core Arrival

Các trường sau không được dùng làm predictor trong Core Arrival:

- Target và outcome: `ARR_DELAY`, `DEP_DELAY`.
- Thời gian/vận hành thực tế: `DEP_TIME`, `ARR_TIME`, `TAXI_OUT`, `TAXI_IN`, `WHEELS_OFF`, `WHEELS_ON`, `ACTUAL_ELAPSED_TIME`, `AIR_TIME`.
- Raw Weather: `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`.
- Identifier: `flight_key`, `chain_id`, `source_year`, `source_row_number`.
- Hằng số trong luồng inbound ATL: `DEST`, `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE`.
- Các trường chưa đủ bằng chứng: `FLIGHTS`, `ORIGIN_INDEX`, `O_LATITUDE`, `O_LONGITUDE`, `CRS_ARR_TIME`.

---

## 6. Feature engineering và preprocessing chính thức đã hoàn thành

### 6.1. Nhãn đầu ra

Pipeline chính thức đã triển khai:

- `y_arr_cls = 1[ARR_DELAY >= 15]`.
- `y_arr_reg = ARR_DELAY` theo phút có dấu.
- Các dòng thiếu target phải được loại và báo cáo số lượng.
- Không impute target.
- Không dùng trị tuyệt đối và không clip ground truth để cải thiện metric.

### 6.2. Bộ 11 predictor được phê duyệt cho Core Arrival

| Nhóm | Predictor |
|---|---|
| Schedule | `CRS_ELAPSED_TIME`, `scheduled_departure_hour`, `scheduled_departure_minute` |
| Calendar | `calendar_year`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend` |
| Carrier | `OP_CARRIER`, `OP_CARRIER_FL_NUM` |
| Route | `ORIGIN` |

Bảy feature được dẫn xuất từ ngày/giờ kế hoạch:

- `calendar_year`
- `calendar_month`
- `calendar_day_of_month`
- `calendar_day_of_week`
- `is_weekend`
- `scheduled_departure_hour`
- `scheduled_departure_minute`

### 6.3. Transformer đã triển khai

#### Pipeline tuyến tính

- Numeric: median imputation trên fold train, missing indicators và `StandardScaler`.
- Categorical: sentinel imputation và `OneHotEncoder(handle_unknown="ignore")`.
- Số hiệu chuyến bay có cardinality cao: frequency mapping không dùng target; unknown nhận giá trị 0.

#### Pipeline tree/boosting

- Numeric: median imputation trên fold train, missing indicators, không scale.
- Categorical: sentinel imputation và ordinal encoding; unknown nhận mã −1.
- Số hiệu chuyến bay: frequency mapping không dùng target; unknown nhận giá trị 0.

Mọi statistic, vocabulary và mapping đều được fit riêng trên phần train của từng fold. Chưa gắn estimator vào các preprocessing pipeline chính thức.

### 6.4. Bounded smoke validation

Đã chạy validation giới hạn trên dữ liệu thật:

- Train-like: 1.024 dòng inbound năm 2016, đọc theo batch 256.
- Validation-like: 512 dòng inbound năm 2019, đọc theo batch 256.
- Số cột projected: 14.
- Số predictor được duyệt: 11.
- Cả linear và tree transformers đều fit/transform thành công.
- Median và categorical vocabulary không thay đổi khi transform validation.
- Alignment giữa identifier, feature và target đạt yêu cầu.
- Giữ nguyên 732 giá trị regression target âm trong batch train-like.

---

## 7. Flight Chain gốc

Đã audit cấu trúc 27/27 file `.pt` Flight Chain gốc từ năm 2016 đến 2024 bằng phương pháp giới hạn:

- Không sử dụng `torch.load`.
- Không đọc payload tensor.
- Chỉ kiểm tra container metadata và pickle metadata an toàn.
- Các file 2016–2023 có cấu trúc năm tensor.
- Các file 2024 có cấu trúc bốn tensor không tương thích với các năm trước.
- Không có exact sample-to-Tabular mapping đáng tin cậy.
- Không có encoder mappings và bằng chứng point-in-time đầy đủ.
- Không có physical-aircraft identifier được chứng minh.

Quyết định cuối cùng:

```text
Original raw Flight Chain: FINAL_NO_GO
```

Các file `.pt` gốc được giữ read-only và không được sử dụng trong core hoặc ablation.

---

## 8. Reconstructed Schedule Flight Chain

### 8.1. Phạm vi và ý nghĩa

Đã tái dựng một artifact riêng từ canonical Tabular với phiên bản `schedule_chain_v1`.

Một chain được nhóm theo:

```text
source_year + FL_DATE + OP_CARRIER + OP_CARRIER_FL_NUM
```

Các thành viên được sắp theo scheduled departure, sau đó dùng `ORIGIN`, `DEST` và `flight_key` làm tie-breaker.

Artifact này chỉ biểu diễn ngữ cảnh lịch bay cùng ngày, hãng và số hiệu chuyến bay. Nó **không phải** tail number, aircraft registration, physical-aircraft rotation hoặc bằng chứng các chặng dùng cùng một máy bay.

### 8.2. Các bảng processed

#### `chain_groups`

- `chain_id`
- `chain_version`
- `source_year`
- `FL_DATE`
- `OP_CARRIER`
- `OP_CARRIER_FL_NUM`
- `member_count`
- `first_scheduled_departure`
- `last_scheduled_departure`
- `has_order_tie`

#### `chain_members`

- `chain_id`
- `chain_version`
- `chain_position`
- `flight_key`
- `schedule_signature`
- `source_year`
- `source_row_number`
- `FL_DATE`
- `OP_CARRIER`
- `OP_CARRIER_FL_NUM`
- `ORIGIN`
- `DEST`
- `CRS_DEP_TIME`
- `CRS_ARR_TIME`
- `CRS_ELAPSED_TIME`
- `scheduled_departure_timestamp`
- `is_inbound_atl`
- `order_ambiguous`

#### `inbound_target_map`

- `target_flight_key`
- `chain_id`
- `chain_position`
- `chain_length`
- `source_year`

### 8.3. Kết quả tái dựng 2016–2023

| Năm | Dòng được map | Số chain | Inbound ATL targets | Median length | P95 | Max | Chain dài hơn 6 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 5.537.987 | 4.153.379 | 381.166 | 1 | 2 | 8 | 3.104 |
| 2017 | 5.575.872 | 4.213.097 | 358.263 | 1 | 2 | 8 | 3.709 |
| 2018 | 6.986.842 | 5.370.758 | 386.580 | 1 | 2 | 8 | 5.611 |
| 2019 | 7.161.827 | 5.522.884 | 391.075 | 1 | 2 | 8 | 4.344 |
| 2020 | 4.312.091 | 3.476.881 | 242.121 | 1 | 2 | 8 | 593 |
| 2021 | 5.755.666 | 4.734.600 | 309.621 | 1 | 2 | 8 | 777 |
| 2022 | 6.413.416 | 5.192.960 | 311.701 | 1 | 2 | 8 | 885 |
| 2023 | 6.645.461 | 5.339.817 | 332.741 | 1 | 2 | 8 | 241 |
| **Tổng** | **48.389.162** | **38.004.376** | **2.713.268** | **1** | **2** | **8** | **19.264** |

Các thông số kiểm định tổng hợp:

- Coverage: **100%**.
- Số dòng bị loại: **0**.
- Ambiguous chains: **3**.
- Ambiguous timestamps: **3**.
- Ambiguous members: **6**.
- Duplicate schedule signatures: **1**; excess row: **1**.
- Kích thước output: **4.056.921.478 bytes**, xấp xỉ **3,78 GiB**.
- Tổng runtime: **32.912,12 giây**, xấp xỉ **9 giờ 08 phút 32 giây**.
- Không tạo reconstructed partition cho năm 2024.
- Trạng thái dataset: `FULL_DATA_PASS / GO_FOR_ABLATION`.
- Artifact bị tắt mặc định và không nằm trong core model.

### 8.4. Audit feature Flight Chain

Đã audit 18 feature ứng viên theo khả năng sẵn có tại T−2h.

#### Nhóm `REVIEW_REQUIRED` — 7 feature

- `chain_position`
- `legs_before_target`
- `is_first_chain_leg`
- `minutes_from_chain_first_departure`
- `minutes_since_previous_scheduled_departure`
- `has_previous_chain_leg`
- `previous_leg_destination_matches_target_origin`

#### Nhóm `BLOCKED_UNTIL_PROVEN` — 11 feature

- `is_single_leg_chain`
- `chain_length`
- `legs_after_target`
- `is_last_chain_leg`
- `chain_length_gt_6`
- `minutes_to_chain_last_departure`
- `minutes_to_next_scheduled_departure`
- `has_next_chain_leg`
- `next_leg_origin_matches_target_destination`
- `chain_schedule_span_minutes`
- `chain_position_fraction`

#### Nhóm identifier-only

- `flight_key`
- `chain_id`
- `source_year`
- `source_row_number`

Kết luận feature gate:

```text
KEEP_SAFE_FEATURES = []
CHAIN_ML_BRANCH = BLOCKED_PENDING_NEW_EVIDENCE
ARR-B enabled = false
```

Các trường cấu trúc như `chain_position`, `chain_length` đã tồn tại trong processed Parquet. Tuy nhiên, chưa có bảng feature engineering riêng được materialize và chưa có feature Flight Chain nào được phép đưa vào ma trận `X`.

---

## 9. Weather point-in-time contract

Đã hoàn thành phần thiết kế và kiểm thử contract cho nguồn Weather ngoài trong tương lai:

- Phiên bản: `weather_point_in_time_contract_v1`.
- Trạng thái nguồn: `AUDIT_REQUIRED`.
- Provider: `TBD`.
- `enabled = false`.
- Chưa tải dữ liệu Weather.
- Chưa gọi API.
- Chưa join Weather vào chuyến bay.
- Chưa tạo feature matrix Weather.
- Chưa huấn luyện DEP-A/DEP-B theo contract này.

Contract yêu cầu phân biệt rõ forecast, observation, reanalysis, model analysis và model fill; đồng thời lưu `issue_time`, `publication_time`, `available_time`, `valid_time`, timezone, location và variable provenance. Điều kiện bắt buộc là thông tin phải có `available_time <= prediction_cutoff`.

---

## 10. Các notebook đã chạy và thông số thu được

Hai notebook có output hoàn chỉnh, với execution count từ 1 đến 6:

1. `src/notebooks/preprocessing_notebook.ipynb`
2. `src/notebooks/classification_notebook.ipynb`

Hai notebook sử dụng gần như cùng một quy trình và cho ra cùng bộ kết quả. Vì vậy, các metric không được xem là hai thí nghiệm độc lập để cộng hoặc lấy trung bình. `classification_notebook.ipynb` bổ sung bảng tổng hợp metric cuối cùng.

### 10.1. Dữ liệu notebook đã sử dụng

- Nguồn đọc thực tế: `data/processed/inbound_atl/`.
- Dữ liệu ban đầu: **3.022.433 dòng × 38 cột**.
- Sau khi tạo `CRS_DEP_HOUR` và `CRS_ARR_HOUR`: **3.022.433 dòng × 40 cột**.
- Missing Weather sau median imputation: **0**.

Phân bố số dòng theo năm:

| Năm | Số dòng |
|---:|---:|
| 2016 | 381.166 |
| 2017 | 358.263 |
| 2018 | 386.580 |
| 2019 | 391.075 |
| 2020 | 242.121 |
| 2021 | 309.621 |
| 2022 | 311.701 |
| 2023 | 332.741 |
| 2024 | 309.165 |

Notebook chia dữ liệu như sau:

| Tập | Năm | Số dòng |
|---|---|---:|
| Train | 2016–2022 | 2.380.527 |
| Validation | 2023 | 332.741 |
| Test trong notebook | 2024 | 309.165 |

Số biến đầu vào sau bước drop động:

- Bài toán Departure classification: **22 feature**.
- Bài toán Arrival classification: **16 feature**.

### 10.2. Feature engineering và tiền xử lý trong notebook

Các notebook đã thực hiện:

- Chuyển `CRS_DEP_TIME` thành `CRS_DEP_HOUR`.
- Chuyển `CRS_ARR_TIME` thành `CRS_ARR_HOUR`.
- Median imputation cho sáu trường Weather.
- `LabelEncoder` cho `OP_CARRIER`, `ORIGIN`, `DEST`.
- Loại các dòng thiếu `CRS_ELAPSED_TIME`, hai cột giờ, `ARR_DELAY` hoặc `DEP_DELAY`.
- Tạo target nhị phân với ngưỡng chậm 15 phút.
- Fit `StandardScaler` trên tập train 2016–2022 và transform validation/test.
- Loại các trường vận hành thực tế như actual time, taxi time, wheels time và air time khỏi feature matrix.

Riêng Arrival task, notebook loại Weather tại điểm đến (`D_TEMP`, `D_PRCP`, `D_WSPD`) cùng tọa độ/chỉ mục điểm đến, nhưng vẫn có thể giữ Weather/coordinate phía origin. Đây không phải feature policy của Core Arrival V4.

### 10.3. Thuật toán và cấu hình notebook

| Mô hình | Cấu hình chính |
|---|---|
| XGBoost | `n_estimators=100`, `max_depth=10`, `random_state=42`, `tree_method="hist"`, ưu tiên CUDA |
| Logistic Regression | `max_iter=200`; notebook fallback từ cuML sang scikit-learn CPU |
| Random Forest | `n_estimators=50`, `max_depth=10`, `random_state=42`, `n_jobs=-1` |

Trong output đã lưu, Logistic Regression sử dụng scikit-learn CPU vì cuML không được tìm thấy.

### 10.4. Kết quả bài toán Departure Delay

Target:

```text
DEP_DELAY >= 15 phút
```

Test 2024 có:

- Class 0: 254.658 dòng.
- Class 1: 54.507 dòng.
- Tỷ lệ class dương: khoảng **17,63%**.

| Model | Validation ROC-AUC 2023 | Test ROC-AUC 2024 | Test Accuracy | Precision class 1 | Recall class 1 | F1 class 1 |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | 0,6916 | 0,6837 | 0,8195 | 0,45 | 0,11 | 0,1722 |
| Logistic Regression | 0,6651 | 0,6610 | 0,8238 | 0,58 | xấp xỉ 0,00 | 0,0028 |
| Random Forest | **0,6932** | **0,6893** | **0,8239** | 0,58 | xấp xỉ 0,00 | 0,0089 |

Nhận xét:

- Random Forest có ROC-AUC cao nhất trên validation và test.
- XGBoost có F1 cho class chậm chuyến cao hơn rõ rệt so với hai mô hình còn lại.
- Accuracy khoảng 82% chủ yếu chịu ảnh hưởng bởi class 0 chiếm đa số.
- Logistic Regression và Random Forest gần như không phát hiện class 1 ở threshold mặc định 0,5, dù ROC-AUC vẫn lớn hơn 0,5.

### 10.5. Kết quả bài toán Arrival Delay

Target:

```text
ARR_DELAY >= 15 phút
```

Test 2024 có:

- Class 0: 255.127 dòng.
- Class 1: 54.038 dòng.
- Tỷ lệ class dương: khoảng **17,48%**.

| Model | Validation ROC-AUC 2023 | Test ROC-AUC 2024 | Test Accuracy | Precision class 1 | Recall class 1 | F1 class 1 |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | 0,6822 | 0,6690 | 0,8212 | 0,44 | 0,09 | 0,1459 |
| Logistic Regression | 0,6416 | 0,6325 | 0,8252 | 0,00 | 0,00 | 0,0000 |
| Random Forest | **0,6900** | **0,6826** | **0,8254** | 0,63 | xấp xỉ 0,00 | 0,0058 |

Nhận xét:

- Random Forest có ROC-AUC cao nhất trên validation và test.
- XGBoost tiếp tục cho F1 class dương cao nhất.
- Logistic Regression không dự đoán được class dương tại threshold mặc định.
- Accuracy khoảng 82–83% không phản ánh tốt khả năng phát hiện chuyến bay trễ do mất cân bằng lớp.

### 10.6. So sánh tổng hợp kết quả notebook

| Task | Model tốt nhất theo ROC-AUC validation | ROC-AUC validation | Model tốt nhất theo F1 class dương | F1 test 2024 |
|---|---|---:|---|---:|
| Departure delay | Random Forest | 0,6932 | XGBoost | 0,1722 |
| Arrival delay | Random Forest | 0,6900 | XGBoost | 0,1459 |

Kết quả cho thấy các mô hình có khả năng xếp hạng rủi ro ở mức vừa phải, nhưng threshold mặc định tạo recall rất thấp cho lớp chậm chuyến. Các bước tiếp theo nên tập trung vào đánh giá PR-AUC, balanced accuracy, class weighting, threshold selection và calibration trên development folds thay vì dựa vào accuracy.

### 10.7. Các hạn chế bắt buộc phải ghi khi sử dụng kết quả notebook

Các metric trên chỉ nên đặt trong mục **“Thử nghiệm khám phá ban đầu”** vì:

1. Notebook fit median imputer và `LabelEncoder` trên toàn bộ dữ liệu 2016–2024 trước khi chia train/validation/test. Đây là preprocessing leakage, dù không trực tiếp sử dụng target.
2. Notebook đã đọc và đánh giá 2024 trước khi full-system freeze, không phù hợp vai trò `FINAL_HOLDOUT` của protocol V4.
3. Departure task sử dụng dữ liệu `inbound_atl`, trong khi Auxiliary Departure V4 yêu cầu `outbound_atl` với `ORIGIN = ATL`.
4. Arrival task chưa tuân thủ bộ 11 predictor chính thức; raw Weather không được phép dùng trong Core Arrival V4.
5. Việc encoding category trên toàn bộ dữ liệu cho phép vocabulary của các năm tương lai ảnh hưởng preprocessing.
6. Chưa có expanding-window evaluation trên bốn fold 2019–2022.
7. Chưa có PR-AUC, calibration, confusion matrix theo threshold tối ưu hoặc confidence interval.
8. Hai notebook lặp lại cùng quy trình/kết quả, không tạo thành hai lần thực nghiệm độc lập.

Do đó, không nên gọi các số liệu test 2024 này là “kết quả final”. Khi viết DOCX, có thể trình bày chúng như bằng chứng đã xây dựng và chạy được baseline, sau đó nêu rõ sẽ tái chạy bằng pipeline V4 trước khi chốt kết luận khoa học.

---

## 11. Kiểm thử và khả năng tái lập

### 11.1. Kết quả kiểm thử hiện tại

Ngày 09/09/2026 đã xác minh:

```text
222 passed in 9.56s
SMOKE_TEST: PASS
```

Smoke test xác nhận:

- Các artifact Week 1–2 còn đầy đủ.
- Cấu hình dual-task V4 hợp lệ.
- Week 3A transformer contracts/manifests hợp lệ.
- Week 3B feature-availability audit và closure hợp lệ.
- Week 3C Weather contract hợp lệ.
- Metadata/manifests và imports hợp lệ.
- Access guard vẫn chặn development access tới 2024.

### 11.2. Môi trường đã ghi nhận

- Python cho reconstructed Chain: **3.11.15**.
- pandas: **2.3.3**.
- PyArrow: **25.0.1**.
- SQLite: **3.50.4**.
- scikit-learn tại Week 3A: **1.9.0**.
- Reconstructed Chain chunk size: **100.000 dòng**.

---

## 12. Các sản phẩm đã tạo

### 12.1. Code và script chính

- `src/data/load_aeolus.py`
- `src/data/schema_audit.py`
- `src/data/canonicalize.py`
- `src/data/leakage_rules.py`
- `src/data/temporal_protocol.py`
- `src/data/chain_inspection.py`
- `src/data/flight_chain_reconstruction.py`
- `src/data/preprocessing.py`
- `src/data/weather_contract.py`
- `src/features/tabular_features.py`
- `src/features/chain_feature_policy.py`
- `scripts/materialize_canonical_data.py`
- `scripts/create_temporal_manifests.py`
- `scripts/reconstruct_flight_chain.py`
- `scripts/smoke_week3a_preprocessing.py`
- `scripts/smoke_test.py`
- `scripts/validate_processed_data.py`

### 12.2. Notebook

- `src/notebooks/preprocessing_notebook.ipynb`
- `src/notebooks/classification_notebook.ipynb`

### 12.3. Manifest và bằng chứng chính

- `artifacts/manifests/canonical_schema_v1.json`
- `artifacts/manifests/processed_data_manifest_v1.json`
- `artifacts/manifests/temporal_folds_manifest.json`
- `artifacts/manifests/split_manifest.json`
- `artifacts/manifests/airport_index_mapping_audit.json`
- `artifacts/manifests/flight_chain_structure_audit_v1.json`
- `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`
- `artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json`
- `artifacts/manifests/feature_manifest_arrival_v1.json`
- `artifacts/manifests/feature_pipeline_registry_arrival_v1.json`
- `artifacts/manifests/weather_point_in_time_contract_v1.json`

### 12.4. Báo cáo audit và quyết định

- `docs/dataset_audit/schema_compatibility_matrix.md`
- `docs/dataset_audit/canonical_schema_v1.md`
- `docs/dataset_audit/data_dictionary_v1.md`
- `docs/dataset_audit/leakage_audit.md`
- `docs/dataset_audit/weather_timing_audit.md`
- `docs/dataset_audit/flight_chain_feasibility_report.md`
- `docs/dataset_audit/flight_chain_reconstruction_report.md`
- `docs/dataset_audit/reconstructed_chain_feature_availability_audit_v1.md`
- `docs/dataset_audit/weather_point_in_time_contract_v1.md`
- `docs/decisions/decision_registry.md`
- `docs/decisions/decision_dual_prediction_architecture_v4.md`
- `docs/decisions/decision_include_chain.md`
- `docs/decisions/decision_reconstructed_chain.md`

---

## 13. Những phần chưa hoàn thành

Các hạng mục sau chưa nên được mô tả là đã hoàn thành:

- Huấn luyện Core Arrival classification/regression bằng pipeline V4 chính thức.
- Expanding-window cross-validation cho các model chính thức.
- HPO chỉ trên development folds 2016–2022.
- Calibration, threshold selection và weighted ensemble.
- Controlled model selection trên 2023.
- Feature engineering Flight Chain được phê duyệt cho ML.
- Chọn provider và audit dữ liệu Weather point-in-time.
- DEP-A/DEP-B controlled Weather experiment.
- Synthetic Aircraft Turn.
- Gate simulation.
- Greedy, CP-SAT và CP-SAT + SA optimization.
- Monte Carlo robustness evaluation.
- Full-system freeze và final evaluation trên 2024.
- Dashboard kết quả cuối cùng.

---

## 14. Đề xuất bố cục khi chuyển sang DOCX

Có thể dùng trực tiếp tài liệu này để tạo báo cáo Word theo bố cục:

1. **Giới thiệu đề tài** — lấy từ Mục 2 và 3.
2. **Dữ liệu và phương pháp xử lý** — lấy từ Mục 4 và 5.
3. **Feature engineering và preprocessing** — lấy từ Mục 6.
4. **Nghiên cứu Flight Chain** — lấy từ Mục 7 và 8.
5. **Nghiên cứu Weather point-in-time** — lấy từ Mục 9.
6. **Thử nghiệm mô hình ban đầu** — lấy từ Mục 10, giữ nguyên cảnh báo exploratory.
7. **Kiểm thử và khả năng tái lập** — lấy từ Mục 11.
8. **Kết quả đạt được và công việc tiếp theo** — lấy từ Mục 12, 13 và 15.

Các hình nên bổ sung trong DOCX:

- Sơ đồ pipeline `Predict -> Simulate -> Optimize -> Evaluate`.
- Biểu đồ số dòng theo năm.
- Biểu đồ ROC-AUC của ba model theo hai task.
- Biểu đồ F1 class dương để thể hiện ảnh hưởng của mất cân bằng lớp.
- Sơ đồ temporal split 2016–2024.
- Sơ đồ ba bảng của Reconstructed Schedule Flight Chain.

---

## 15. Kết luận có thể sử dụng trong báo cáo

Dự án đã hoàn thành phần nền tảng dữ liệu, kiểm soát tính hợp lệ theo thời gian và preprocessing cho bài toán dự báo chậm chuyến tại ATL. Toàn bộ 54.674.003 bản ghi giai đoạn 2016–2024 đã được audit và chuẩn hóa thành schema thống nhất; ba luồng dữ liệu Parquet đã được materialize và kiểm tra. Temporal protocol expanding window, feature contract và leakage rules đã được khóa nhằm bảo đảm mô hình chỉ sử dụng thông tin hợp lệ tại thời điểm T−2h.

Đối với Flight Chain, dữ liệu gốc `.pt` bị loại khỏi pipeline do thiếu mapping và bằng chứng an toàn. Một Schedule Flight Chain mới đã được tái dựng thành công cho 48.389.162 dòng giai đoạn 2016–2023 với coverage 100%. Tuy nhiên, audit point-in-time chưa phê duyệt feature Chain nào cho ML, nên Core Arrival hiện vẫn sử dụng Tabular-only.

Hai notebook thử nghiệm đã chạy thành công ba thuật toán Logistic Regression, Random Forest và XGBoost trên hai target chậm khởi hành và chậm đến. ROC-AUC validation cao nhất lần lượt là 0,6932 và 0,6900 với Random Forest; XGBoost cho F1 class chậm chuyến cao nhất. Các kết quả này cho thấy baseline có tín hiệu dự báo nhưng khả năng phát hiện class chậm chuyến tại threshold mặc định còn thấp. Vì notebook chưa tuân thủ hoàn toàn holdout và preprocessing contract V4, các metric hiện tại được xem là exploratory và cần được tái xác nhận bằng expanding-window pipeline chính thức trước khi đưa ra kết luận cuối cùng.

Tại thời điểm tổng hợp, repository đạt 222 unit tests passed và smoke test PASS. Core Arrival đã sẵn sàng chuyển sang giai đoạn huấn luyện mô hình chính thức; simulation, optimization và final holdout evaluation vẫn là các bước tiếp theo.

---

## 16. Nguồn bằng chứng sử dụng để lập tài liệu

- `docs/experiments/experiment_log.md`
- `project_structure.md`
- `README.md`
- `artifacts/manifests/processed_data_manifest_v1.json`
- `artifacts/manifests/temporal_folds_manifest.json`
- `artifacts/manifests/feature_manifest_arrival_v1.json`
- `artifacts/manifests/feature_pipeline_registry_arrival_v1.json`
- `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`
- `artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json`
- `docs/dataset_audit/schema_compatibility_matrix.md`
- `docs/dataset_audit/flight_chain_reconstruction_report.md`
- `docs/dataset_audit/reconstructed_chain_feature_availability_audit_v1.md`
- Outputs đã lưu trong `src/notebooks/preprocessing_notebook.ipynb`
- Outputs đã lưu trong `src/notebooks/classification_notebook.ipynb`

