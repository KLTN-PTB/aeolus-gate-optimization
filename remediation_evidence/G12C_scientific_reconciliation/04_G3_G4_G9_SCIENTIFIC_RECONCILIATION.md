# BÁO CÁO 04: ĐỐI SOÁT VÀ CHUẨN HÓA KẾT QUẢ ML VÀ DUAL-CORE G3 / G4 / G9
## AEOLUS-G12C — MACHINE LEARNING & FLIGHT TURN EVIDENCE RECONCILIATION

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Phạm vi:** Đối chiếu kết quả dự báo Học máy (G3), tích hợp chuỗi quay đầu Dual-Core (G4) và bản thảo Khóa luận (G9)  

---

## 1. KẾT QUẢ KIỂM CHỨNG CHÍNH THỨC CỦA G3 (OUTBOUND CLASSIFICATION BENCHMARK)

Toàn bộ các số liệu mô hình học máy phân loại trễ khởi hành của G3 được xác thực trực tiếp từ tệp kết quả thô:
`artifacts/remediation/outbound_classification/metrics/outbound_classification_metrics_2023.csv`
được sinh bởi script huấn luyện và đánh giá `scripts/train_outbound_classifiers_g3.py`:

### 1.1. Bảng Số Liệu Kiểm Chứng G3 Đầy Đủ và Toàn Vẹn ($N = 332,734$)

| Tác vụ / Đặc tả | Constant Prevalence Baseline | Calibrated Logistic Regression | Calibrated XGBoost Classifier (Champion) |
|:---|:---:|:---:|:---:|
| **Tác vụ (Task)** | `core_departure_classification` | `core_departure_classification` | `core_departure_classification` |
| **Model ID** | `constant_prevalence_baseline` | `outbound_logistic_calibrated_v1` | `outbound_xgboost_calibrated_v1` |
| **Họ mô hình (Family)** | Constant baseline | Linear logistic + Isotonic | XGBoost Tree + Sigmoid (Platt) |
| **Tập đánh giá** | `development_selection_2023` | `development_selection_2023` | `development_selection_2023` |
| **Cỡ mẫu đánh giá ($N$)** | **332,734** chuyến bay | **332,734** chuyến bay | **332,734** chuyến bay |
| **Tỷ lệ nhãn dương (Trễ $\ge 15$m)** | **20.625%** | **20.625%** | **20.625%** |
| **ROC-AUC** ($\uparrow$) | **0.50000** | **0.61336** | **0.64289** |
| **PR-AUC** ($\uparrow$, Baseline = $0.20625$) | **0.20625** | **0.29381** | **0.32916** |
| **Brier Score** ($\downarrow$) | **0.16776** | **0.15892** | **0.15637** |
| **Log Loss** ($\downarrow$) | 0.52382 | 0.49534 | **0.48800** |
| **Weighted ECE** ($\downarrow$, Ngưỡng $\le 0.05$) | 0.06361 | **0.01047** | **0.01192** ($0.01191552$) |
| **Ngưỡng quyết định (Threshold)** | 0.50 | 0.50 | 0.50 |
| **True Positives (TP)** | 0 | 2,698 | **3,337** |
| **False Positives (FP)** | 0 | 3,265 | **3,437** |
| **True Negatives (TN)** | 264,106 | 260,841 | **260,669** |
| **False Negatives (FN)** | 68,628 | 65,930 | **65,291** |
| **Precision** | 0.00000 | 0.45246 | **0.49262** |
| **Recall** | 0.00000 | 0.03931 | **0.04862** |
| **F1-Score** | 0.00000 | 0.07234 | **0.08851** |
| **Đã hiệu chuẩn (Is Calibrated)** | False | **True** | **True** |
| **Vượt Brier cơ sở** | False | **True** | **True** |
| **Đạt mục tiêu ECE $\le 0.05$** | False | **True** | **True** |

---

## 2. XỬ LÝ SAI LỆCH VÀ PHÂN LOẠI CHỈ SỐ CAO BẤT THƯỜNG TRONG BẢN THẢO G9

### 2.1. Phát Hiện Sai Lệch trong Bản Thảo Khóa Luận (G9 Draft Discrepancy)
Trong tệp bản thảo khóa luận cũ `remediation_evidence/G9_thesis/03_THESIS_DRAFT.md`:
- Xuất hiện các số liệu như: ROC-AUC $= 0.778$ (Inbound), ROC-AUC $= 0.795$ (Outbound), Accuracy $= 0.845$, F1 $= 0.528$, Brier $= 0.106$.

### 2.2. Kết Quả Kiểm Toán Độc Lập
1. **Truy vết mảng dự báo:** Không tìm thấy bất kỳ mảng dự báo nhị phân (`predictions.parquet`, `predictions.csv`), script kiểm định holdout hay nhật ký huấn luyện nào sinh ra các con số ROC-AUC $0.778$ và $0.795$ trên tập kiểm thử độc lập 2023.
2. **Nguồn gốc khả dĩ:** Các số liệu này là kết quả đánh giá trên tập huấn luyện (In-Sample Training / Overfitting) của một bản thử nghiệm ban đầu khi chưa áp dụng rào chắn rò rỉ thời gian $T-2\text{h}$, hoặc là số liệu giữ chỗ (placeholder) được đưa vào bản nháp mà chưa qua đối soát G3.
3. **Phán quyết khoa học chính thức:**
   - Toàn bộ các số liệu ROC-AUC $\approx 0.78 - 0.80$ trong bản nháp cũ chính thức bị phân loại là **`UNVERIFIED / DEPRECATED` (CHƯA ĐƯỢC XÁC MINH & BỊ BÃI BỎ)**.
   - Bản thảo khóa luận chính thức bắt buộc phải sử dụng các số liệu đã được kiểm chứng của G3: ROC-AUC $= 0.64289$, PR-AUC $= 0.32916$, Brier $= 0.15637$, ECE $= 0.01192$.
   - **Giải thích khoa học trung thực:** Trong dự báo độ trễ hàng không với rào chắn thông tin nghiêm ngặt tại thời điểm $T-2\text{h}$ trước khi khởi hành (chỉ sử dụng thông tin lịch bay và đặc trưng lịch sử của hãng/sân bay, không được dùng dữ liệu trễ chuyến bay đến chưa hoàn thành), mức ROC-AUC $\approx 0.643$ và PR-AUC tăng từ $0.206$ lên $0.329$ phản ánh đúng thực tế khó khăn của bài toán trễ hàng không, thể hiện tính liêm chính học thuật cao của tác giả khóa luận.

---

## 3. XÁC MINH DỮ LIỆU TÍCH HỢP CHUỖI QUAY ĐẦU G4 (DUAL-CORE FLIGHT TURNS)

Trong thí nghiệm tích hợp dữ liệu thật Thanksgiving 2023 tại Sân bay Atlanta (`native_dual_core_g4_pilot`):
- **Tập dữ liệu đầu vào:** $200$ chặng bay độc lập (100 chặng đến inbound + 100 chặng đi outbound).
- **Thực trạng dữ liệu mở BTS TranStats:** Bảng dữ liệu mở của Cục Thống kê Vận tải Hoa Kỳ (BTS) đối với các chuyến bay công khai không bao gồm cột số hiệu đăng ký máy bay thực tế (`TAIL_NUM`).

### 3.1. Phân Biệt Ba Khái Niệm Trọng Tâm
Hệ thống xác lập ranh giới học thuật rõ ràng giữa 3 khái niệm:
1. **Chặng bay (Flight Legs):** Tổng cộng $200$ chặng ($100$ inbound $+ 100$ outbound).
2. **Cặp quay đầu xác thực theo số hiệu đuôi (Verified Tail Rotations):** Đúng **$0$ cặp**. Hệ thống tuân thủ nguyên tắc liêm chính dữ liệu: Không tự bịa đặt số hiệu đuôi máy bay (`TAIL_NUM`) khi dữ liệu gốc không cung cấp.
3. **Cặp quay đầu suy diễn theo suy nghiệm (Inferred Turn Matches):** 
   - Khi chạy ở chế độ gán đơn lẻ (`native_dual_core_g4_pilot`): Hệ thống tạo ra $200$ turn đơn lẻ (single-leg turns), $0$ cặp ghép.
   - Khi kích hoạt thuật toán suy diễn heuristic (`native_dual_core_g4_pilot_inferred`): Thuật toán ghép được **$59$ cặp quay đầu suy diễn** giữa các chuyến bay cùng hãng hàng không có khoảng cách thời gian từ $45$ đến $120$ phút, còn lại $41$ chuyến đến và $41$ chuyến đi đơn lẻ (tổng cộng $141$ lượt chiếm dụng cổng).

> [!IMPORTANT]
> **Quy tắc phát biểu trong khóa luận:**
> Khóa luận không được phát biểu "hệ thống đã tối ưu hóa 200 vòng quay đầu máy bay đã xác thực", mà phải phát biểu chính xác: *"Hệ thống đã xử lý 200 chặng bay thực tế, trong đó bao gồm 200 lượt điều phối độc lập (Single-Leg Mode) hoặc 59 cặp quay đầu suy diễn logic và 82 chặng đơn lẻ (Inferred Mode) do CSDL mở không cung cấp số hiệu đuôi tàu bay."*
