# BÁO CÁO KẾT QUẢ HIỆU CHUẨN XÁC SUẤT (PROBABILITY CALIBRATION) CHO BỘ GIẢI CP-SAT
**Mã đề tài**: CNTT-KLCN168  
**Thời gian thực hiện**: 25/10/2026 08:34:05  
**Mục tiêu**: Khắc phục sai lệch xác suất do `scale_pos_weight = 1.644` của Optuna, hạ chỉ số Brier Score và chuẩn hóa vùng đệm an toàn $B_{\text{risk}}$ cho bộ giải tối ưu cổng CP-SAT.

---

## 1. Bản chất Vấn đề Đã Khắc phục
* **Nguyên nhân**: Khi huấn luyện XGBoost phân loại trễ chuyến đến ($P(\text{delay} \ge 15\text{m})$), Optuna đã chọn `scale_pos_weight = 1.644` nhằm tối đa hóa ROC-AUC và khả năng bắt trễ (Recall đạt ~74%). Tuy nhiên, điều này làm hàm `predict_proba()` phóng đại tỷ lệ odds, đẩy xác suất trung bình lên **28.12%** trong khi tỷ lệ trễ thực tế chỉ là **20.40%**.
* **Hậu quả trước đây**:
  * Chỉ số Brier Score thô là **0.1602**, ngang với mức đoán hằng số baseline (**0.1624**).
  * Sai số hiệu chuẩn kỳ vọng (**ECE**) lên tới **7.71%**.
  * Vùng đệm rủi ro $B_{\text{risk}} = \text{round}(15 \times P)$ bị tính đội lên trung bình **4.22 phút/chuyến**, gây lãng phí công suất cầu tàu bay.

---

## 2. Bảng Đối chuẩn Trước và Sau Hiệu chuẩn (Test Set 2024 - 300,000 dòng)

| Chỉ số Đánh giá | Baseline Dự báo Hằng số | XGBoost Thô (Chưa Calibrate) | Sau Hiệu chuẩn Platt (Sigmoid) | Sau Hiệu chuẩn Isotonic (Đề xuất) | Mức Cải thiện |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Xác suất TB (Mean Prob)** | 20.40% | **28.12%** *(thổi phồng)* | **19.13%** | **19.18%** | Về sát thực tế (20.40%) |
| **Brier Score** *(càng thấp càng tốt)* | 0.1624 | 0.1602 | **0.1540** | **0.1542** | **Giảm 0.0060 (Vượt qua baseline)** |
| **ECE (Expected Calib Error)** | - | 7.71% | 1.44% | **1.42%** | **Giảm 6.30% sai số** |
| **Log Loss** | - | 0.4966 | **0.4809** | **0.4836** | Tối ưu độ bất định |
| **ROC-AUC** | 0.5000 | **0.6590** | **0.6590** | **0.6589** | **Bảo toàn 100% năng lực phân loại** |
| **Mean $B_{\text{risk}}$ (Phút)** | 3.00 m | **4.22 m** | **2.88 m** | **2.92 m** | **Tiết kiệm 1.29 m đệm ảo/chuyến** |

---

## 3. Biểu đồ Độ Tin cậy (Reliability Diagram)

Biểu đồ đã được xuất sang: `artifacts/reports/figures/reliability_diagram_xgboost.png`.

* **Đường màu đỏ (XGBoost thô)**: Nằm hoàn toàn lệch về bên phải đường lý tưởng $y=x$, minh chứng cho việc mô hình tự tin thái quá (overconfident).
* **Đường màu xanh lá (Isotonic)** & **Đường màu xanh dương (Platt)**: Ôm sát đường chéo lý tưởng 45 độ, chứng minh xác suất dự báo đã phản ánh đúng tần suất trễ thực nghiệm.

---

## 4. Tích hợp Hoàn tất cho Bộ giải CP-SAT
* File dữ liệu Parquet `artifacts/predictions/unified_xgboost_5m_predictions_for_cpsat.parquet` đã được cập nhật thêm các trường:
  * `prob_arr_delay_calibrated`: Xác suất đến trễ đã hiệu chuẩn.
  * `b_risk_min`: Vùng đệm rủi ro chuẩn hóa $\text{clip}(\text{round}(15 \times P_{\text{calibrated}}), 0, 15)$.
  * `b_risk_raw_min`: Vùng đệm thô trước đây để đối chuẩn độ nhạy (sensitivity analysis).
