# AEOLUS-G10 — DELIVERABLE 02: G3 OUTBOUND CLASSIFICATION METRIC RECOMPUTATION & ROOT CAUSE AUDIT

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Independent ML Scientific Reviewer & Statistical Reproducibility Specialist  
**Target Phase:** Phase G3 Outbound Probability Calibration & Metric Lineage  

---

## 1. MỤC TIÊU VÀ TÀI LIỆU KIỂM TOÁN

Nhiệm vụ kiểm toán độc lập đối với Phase G3 là:
1. Mở và kiểm tra trực tiếp tệp dự báo cấp bản ghi (prediction-level):  
   `artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet`
2. Tính toán lại từ đầu (recompute from raw predictions) toàn bộ các chỉ số thống kê và đánh giá mô hình.
3. Đối chiếu đối đầu giữa:
   - Số liệu tính toán trực tiếp từ dữ liệu cấp bản ghi (Audited Recomputation).
   - Tệp chỉ số tổng hợp: `artifacts/remediation/outbound_classification/metrics/outbound_classification_metrics_2023.csv`.
   - Tệp biểu đồ độ tin cậy: `artifacts/remediation/outbound_classification/metrics/reliability_diagrams_2023.json`.
   - Báo cáo G3 Deliverable 08: `remediation_evidence/G3_ml_validation/08_OUTBOUND_CLASSIFIER_REPORT.md`.
   - Bản thảo khóa luận G9: `remediation_evidence/G9_thesis/03_THESIS_DRAFT.md` (Bảng 5.2).
4. Xác định nguyên nhân thực chất của sự sai lệch:
   - Reported ECE = 0.01192 so với ECE suy ra từ Bảng 4 trong Deliverable 08 (~0.00260).
   - Reported Prevalence = 20.63% so với Prevalence suy ra từ Bảng 4 trong Deliverable 08 (~21.55%).

---

## 2. KẾT QUẢ TÍNH TOÁN LẠI TỪ DỮ LIỆU CẤP BẢN GHI (PREDICTION-LEVEL AUDIT)

Kiểm toán viên đã thực thi đoạn mã kiểm chứng độc lập trên tệp `outbound_classification_selection_2023.parquet` (kích thước: 13,97 MB, gồm 332.734 dòng và 7 cột):

```
Dữ liệu kiểm thử: 2023 Selection Split (DEST != 'ATL', ORIGIN == 'ATL')
Tổng số chuyến bay (N): 332.734 bản ghi
Số chuyến bay trễ thực tế (Positives, DEP_DELAY >= 15 phút): 68.628 bản ghi
Tỷ lệ trễ thực tế (True Class Prevalence): 68.628 / 332.734 = 20,62548% (20,63%)
```

### 2.1. Bảng đối chiếu kết quả tính lại trực tiếp cho toàn bộ 5 mô hình (Ngưỡng phân loại = 0.5)

| Tên Mô hình / Cột Dự báo | ROC-AUC | PR-AUC | Brier Score | Log Loss | ECE (10 Bins) | TP | FP | TN | FN | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`prob_constant`** (Prior Baseline) | 0,50000 | 0,20625 | 0,16776 | 0,52382 | 0,06360 | 0 | 0 | 264.106 | 68.628 | 0,00000 | 0,00000 | 0,00000 |
| **`prob_logistic_raw`** | 0,61343 | 0,29708 | 0,16196 | 0,51062 | 0,05507 | 286 | 315 | 263.791 | 68.342 | 0,47587 | 0,00417 | 0,00826 |
| **`prob_logistic_calibrated`** | 0,61336 | 0,29381 | 0,15892 | 0,49534 | **0,01047** | 2.698 | 3.265 | 260.841 | 65.930 | 0,45246 | 0,03931 | 0,07234 |
| **`prob_xgboost_raw`** | 0,64289 | 0,32916 | 0,15891 | 0,50072 | 0,05644 | 2.618 | 2.423 | 261.683 | 66.010 | 0,51934 | 0,03815 | 0,07107 |
| **`prob_xgboost_calibrated`** | **0,64289** | **0,32915** | **0,15637** | **0,48800** | **0,01192** | 3.337 | 3.437 | 260.669 | 65.291 | 0,49262 | 0,04862 | 0,08851 |

**Kết luận bước 1:** Toàn bộ các giá trị tính lại trực tiếp từ tệp Parquet khớp **chính xác 100% đến 5 chữ số thập phân** với các giá trị được lưu trữ trong tệp `outbound_classification_metrics_2023.csv`.

---

## 3. KIỂM TOÁN TẬP THUẬT TOÁN ĐỘ TIN CẬY (RELIABILITY BINS AUDIT)

### 3.1. Dữ liệu thực tế trong tệp `reliability_diagrams_2023.json` (Mô hình XGBoost Calibrated)

Khi trích xuất trực tiếp mảng `outbound_xgboost_calibrated_v1` trong tệp `reliability_diagrams_2023.json`, các thùng xác suất thực tế ghi nhận như sau:

| Bin Index | Khoảng Xác suất | Số mẫu thực tế ($N_b$) | Xác suất TB ($\bar{p}_b$) | Tỷ lệ trễ thực nghiệm ($\bar{y}_b$) | Độ lệch tuyệt đối ($|\bar{y}_b - \bar{p}_b|$) | Đóng góp vào ECE ($N_b \cdot \text{gap} / N$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bin 1** | [0.0, 0.1) | 0 | None | None | 0,00000 | 0,00000 |
| **Bin 2** | [0.1, 0.2) | 226.683 | 0,15658 | 0,15672 | 0,00014 | 0,00010 |
| **Bin 3** | [0.2, 0.3) | 73.871 | 0,23678 | 0,26653 | 0,02975 | 0,00660 |
| **Bin 4** | [0.3, 0.4) | 18.320 | 0,34021 | 0,38570 | 0,04549 | 0,00250 |
| **Bin 5** | [0.4, 0.5) | 7.086 | 0,44385 | 0,42478 | 0,01907 | 0,00041 |
| **Bin 6** | [0.5, 0.6) | 3.642 | 0,54400 | 0,42504 | 0,11896 | 0,00130 |
| **Bin 7** | [0.6, 0.7) | 2.086 | 0,64847 | 0,55465 | 0,09382 | 0,00059 |
| **Bin 8** | [0.7, 0.8) | 1.013 | 0,73354 | 0,60020 | 0,13334 | 0,00041 |
| **Bin 9** | [0.8, 0.9) | 33 | 0,81094 | 0,72727 | 0,08367 | 0,00001 |
| **Bin 10**| [0.9, 1.0] | 0 | None | None | 0,00000 | 0,00000 |
| **Tổng cộng** | | **332.734** | | | | **ECE = 0,01192** |

- Tổng số mẫu trong các thùng: $226.683 + 73.871 + 18.320 + 7.086 + 3.642 + 2.086 + 1.013 + 33 = \mathbf{332.734}$ (khớp 100% N).
- Tổng số ca dương tính suy ra từ bảng JSON:  
  $\sum (N_b \cdot \bar{y}_b) = 35.526 + 19.689 + 7.066 + 3.010 + 1.548 + 1.157 + 608 + 24 = \mathbf{68.628}$ ca.
- Tỷ lệ trễ tổng thể suy ra từ bảng JSON: $68.628 / 332.734 = \mathbf{20,63\%}$ (khớp 100%).
- Chỉ số ECE có trọng số tính từ bảng JSON: $\mathbf{0,01192}$ (khớp 100% với CSV và Parquet).

---

## 4. XÁC ĐỊNH NGUYÊN NHÂN THỰC CHẤT CỦA SỰ MÂU THUẪN TRONG BÁO CÁO G3

Bảng dưới đây so sánh Bảng 4 trong báo cáo văn bản `08_OUTBOUND_CLASSIFIER_REPORT.md` với Dữ liệu thực nghiệm thật:

| Chỉ số / Đặc tính | Bảng 4 trong Báo cáo Văn bản G3-08 | Dữ liệu Thật (`reliability_diagrams_2023.json`) | Đánh giá Sai lệch |
| :--- | :---: | :---: | :--- |
| **Số chuyến bay Bin 1** | 1.428 | **0** | Ngụy tạo / Sai nguồn |
| **Số chuyến bay Bin 2** | 168.419 | **226.683** | Lệch -58.264 chuyến |
| **Số chuyến bay Bin 3** | 120.534 | **73.871** | Lệch +46.663 chuyến |
| **Độ lệch gap Bin 6** | 0,00342 | **0,11896** | Báo cáo giảm thiểu sai lệch 35 lần |
| **Độ lệch gap Bin 8** | 0,00675 | **0,13334** | Báo cáo giảm thiểu sai lệch 20 lần |
| **Prevalence suy ra từ bảng** | **21,55%** | **20,63%** | Không khớp tỷ lệ tổng |
| **ECE suy ra từ bảng** | **0,00260** | **0,01192** | Không khớp chỉ số ECE báo cáo |

### Kết luận Nguyên nhân Gốc rễ:
1. **Lỗi nằm ở văn bản báo cáo Markdown (Documentation Error), KHÔNG nằm ở artifact hay dữ liệu.**
2. Tác giả khi viết Báo cáo G3 (`08_OUTBOUND_CLASSIFIER_REPORT.md`) đã tự tạo hoặc sao chép một bảng số liệu giả định/minh họa (illustrative/fabricated numbers) vào Bảng 4, trong đó các khoảng cách hiệu chuẩn (calibration gaps) được làm đẹp nhân tạo xuống dưới $0,008$ nhằm tạo ấn tượng mô hình hiệu chuẩn hoàn hảo.
3. Trong khi đó, văn bản lại ghi dòng kết luận ECE = **0.01192** (lấy từ tệp CSV), dẫn đến mâu thuẫn nội tại: Bảng số liệu trong văn bản tính ra ECE = 0.00260, nhưng dòng chữ ngay dưới bảng lại ghi ECE = 0.01192!
4. **Về mặt khoa học:** Giá trị ECE thực chất là **0.01192** ($1.19\%$). Đây vẫn là một kết quả hiệu chuẩn rất tốt (đạt mục tiêu $\text{ECE} \le 0.05$). Tuy nhiên, việc đưa bảng số liệu 0.00260 vào báo cáo là hành vi vi phạm tính trung thực khoa học trong khâu báo cáo.

---

## 5. MÂU THUẪN NGHIÊM TRỌNG GIỮA G3 VÀ KHÓA LUẬN G9

Kiểm toán viên phát hiện một sai lệch khoa học ở cấp độ P0 khi đối chiếu giữa G3 và Khóa luận G9 (`03_THESIS_DRAFT.md` Bảng 5.2):

| Mô hình & Thước đo | Giá trị Thực nghiệm Đã kiểm toán (G3 / Parquet) | Giá trị Tuyên bố trong Khóa luận G9 (Bảng 5.2) | Đánh giá Kiểm toán G10 |
| :--- | :---: | :---: | :--- |
| **Outbound Logistic ROC-AUC** | **0,613** | **0,762** | **UNSUPPORTED CLAIM (Tự nâng khống +0.149)** |
| **Outbound Random Forest ROC-AUC**| *Không có checkpoint* | **0,779** | **FABRICATION (Không có mô hình trong repo)** |
| **Outbound XGBoost ROC-AUC** | **0,643** | **0,795** | **UNSUPPORTED CLAIM (Tự nâng khống +0.152)** |
| **Outbound XGBoost F1-Score** | **0,089** | **0,528** | **UNSUPPORTED CLAIM (Tự nâng khống 6 lần)** |
| **Outbound XGBoost Regressor MAE**| **17,60 phút** | **16,40 phút** | **UNSUPPORTED CLAIM (Lấy sai số liệu)** |

> **CẢNH BÁO KIỂM TOÁN TỐI CAO:**  
> Toàn bộ các con số phân loại Outbound trong Khóa luận G9 (ROC-AUC 0.795, F1 0.528, Acc 0.845) là **HOÀN TOÀN KHÔNG CÓ BẰNG CHỨNG TRONG BẤT KỲ ARTIFACT NÀO CỦA REPOSITORY**. Giá trị ROC-AUC thực chất đo lường được trên 332.734 chuyến bay chỉ là **0.643**.  
> Sinh viên **TUYỆT ĐỐI KHÔNG ĐƯỢC SỬ DỤNG CON SỐ 0.795** trước Hội đồng chấm khóa luận vì đây là lỗi ngụy tạo số liệu nghiêm trọng có thể dẫn đến việc hủy tư cách bảo vệ nếu bị chất vấn truy xuất nguồn gốc.
