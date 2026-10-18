# AEOLUS-G10 — DELIVERABLE 07: INDEPENDENT G8/G9 CLAIM AUDIT & CONTRADICTION MATRIX

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Academic Integrity Auditor & Scientific Evidence Lead  
**Scope:** Forensic Cross-Check of Claims in G8 Release Reports and G9 Bachelor Thesis Documents  

---

## 1. MỤC TIÊU VÀ NGUYÊN TẮC KIỂM TOÁN HỌC THUẬT

Kiểm toán viên tiến hành rà soát chéo từng bảng biểu, tuyên bố khoa học và số liệu thực nghiệm được trình bày trong các văn bản của G8 (`11_APPROVED_RESULTS_FOR_THESIS.md`, `08_THESIS_REQUIREMENT_TRACEABILITY.md`) và G9 (`03_THESIS_DRAFT.md`, `04_EXPERIMENT_TABLES_AND_FIGURES.md`, `07_DEFENSE_SLIDE_CONTENT.md`, `11_GATE_REPORT.md`), đối chiếu trực tiếp với các tệp dữ liệu cấp bản ghi (ground-truth artifacts) trong repository.

Mọi tuyên bố khoa học không thể tìm thấy bằng chứng đối ứng trực tiếp trong tệp kết quả thực nghiệm đều bị gán nhãn **`UNSUPPORTED_CLAIM`** hoặc **`FABRICATION`** theo đúng nguyên tắc liêm chính học thuật.

---

## 2. MA TRẬN ĐỐI CHIẾU CÁC TUYÊN BỐ KHOA HỌC CHỦ CHỐT (CLAIM AUDIT MATRIX)

| STT | Tuyên bố trong Khóa luận G9 | Nguồn Dữ liệu Thật trong Artifact | Tình trạng Kiểm toán G10 | Đánh giá & Rủi ro Học thuật |
| :---: | :--- | :--- | :---: | :--- |
| **C-01** | **Outbound Classifier XGBoost đạt ROC-AUC 0.795, F1 0.528, Acc 0.845** (Bảng 5.2 G9) | `outbound_classification_metrics_2023.csv` & Parquet: **ROC-AUC = 0.64289, F1 = 0.08851, Acc = 0.793** | **UNSUPPORTED_CLAIM (NGỤY TẠO SỐ LIỆU)** | **P0 CRITICAL:** Tác giả đã tự nâng khống ROC-AUC từ 0.643 lên 0.795. Số liệu 0.795 hoàn toàn không tồn tại trong repo. |
| **C-02** | **Outbound Logistic đạt ROC-AUC 0.762, Random Forest đạt ROC-AUC 0.779** (Bảng 5.2 G9) | Dữ liệu thật: Logistic đạt **0.61336**. Random Forest **KHÔNG CÓ CHECKPOINT** trong repo. | **UNSUPPORTED_CLAIM (KHÔNG CÓ MÔ HÌNH)** | **P0 CRITICAL:** Tự bịa kết quả cho Random Forest dù mô hình không được huấn luyện. |
| **C-03** | **Outbound Regressor XGBoost đạt MAE 16.40 phút** (Bảng 5.2 G9) | `09_BASELINE_COMPARISON.md`: Departure XGBoost đạt **MAE = 17.6017 phút**, RMSE = 43.0005 phút. | **UNSUPPORTED_CLAIM (SAI SỐ LIỆU)** | **P1 WARNING:** Lấy sai số liệu so với baseline audited report. |
| **C-04** | **Inbound NGBoost đạt MAE 17.60m, RMSE 43.00m; Median đạt MAE 15.60m, RMSE 45.76m** (Bảng 5.1 G9) | `09_BASELINE_COMPARISON.md`: Đây là các con số đo lường trên tập **DEPARTURE POPULATION (Chuyến bay đi)**! | **METHODOLOGICAL MISLABELING (TRÁO ĐỔI DỮ LIỆU)** | **P0 CRITICAL:** Tác giả đã lấy bảng số liệu của Chuyến bay Đi (Departure) và dán nhãn thành Chuyến bay Đến (Inbound NGBoost)! |
| **C-05** | **CP-SAT giải 60 chuyến bay với chi phí 10.0000 trong 0.052 giây** (Bảng 5.3 G9) | `p07_flights_core.csv` có 60 chuyến bay, nhưng kịch bản benchmark chính thức G5 là $N=4, 30, 100, 200, 300$. | **PARTIALLY SUPPORTED** | **P1 WARNING:** Số liệu 10.0000 là kết quả chạy cục bộ trên tệp synthetic 60 chuyến bay, không phản ánh dải benchmark N=200, 300. |
| **C-06** | **Mô phỏng Monte Carlo Mode B2 thực hiện trên 500 kịch bản** (Bảng 5.4 G9) | `simulation_manifest.json` & `scenario_index.csv`: **ĐÚNG 100 KỊCH BẢN** (`n_scenarios: 100`). | **UNSUPPORTED_CLAIM (KHAI KHỐNG MẪU)** | **P0 CRITICAL:** Thực tế chỉ chạy 100 kịch bản nhưng báo cáo 500 kịch bản. |
| **C-07** | **Chi phí Monte Carlo: Mode A 10.0, Mode B1 7.82, Mode B2 12.45, Mode C 6.41** (Bảng 5.4 G9) | `statistical_summary.json`: Mode A = **1.606,43**, Mode B1 = **134,83**, Mode B2 = **147,43**, Mode C2 = **122,43**. | **UNSUPPORTED_CLAIM (NGỤY TẠO CHI PHÍ)** | **P0 CRITICAL:** Toàn bộ cột chi phí trong Bảng 5.4 của G9 là số liệu tự tạo, sai lệch hoàn toàn so với artifact thật! |
| **C-08** | **Tổng số bản ghi dữ liệu BTS ATL: 4.167.269 bản ghi** (Bảng 3.1 G9) | BTS TranStats dữ liệu lịch sử ATL 2016–2024 sau lọc. | **VERIFIED ACCURATE** | Số liệu chính xác và có thể truy xuất. |
| **C-09** | **Tuyên bố đã hoàn thành và nghiệm thu bảo vệ ngày 25/10/2026** (G9 Report 11) | Thời điểm hiện tại là Tháng 10/2026; chưa diễn ra lễ bảo vệ chính thức trước Hội đồng. | **ADMINISTRATIVELY INVALID** | **P1 WARNING:** Tự ý ghi "Đã ký điện tử" và "Nghiệm thu toàn diện" trước khi bảo vệ thật. |
| **C-10** | **Đề tài do 1 sinh viên (Phùng Thế Bảo) thực hiện, mã CNTT-KLCN168** (G9 Cover) | Đề cương chính thức của trường có **3 SINH VIÊN**, mã đề tài chính thức khác, GVHD có tên cụ thể. | **ADMINISTRATIVELY MISMATCHED** | **P0 CRITICAL:** Sai lệch thông tin nhân sự và hành chính so với đề cương chính thức. |

---

## 3. MÂU THUẪN GIỮA MA TRẬN YÊU CẦU CỦA G8 VÀ G9

Báo cáo G8 và Khóa luận G9 có sự xung đột nghiêm trọng về trạng thái thẩm định các yêu cầu của đề cương (Thesis Requirements Traceability):

| Yêu cầu Đề cương | Trạng thái Thẩm định trong Báo cáo G8 (`08_...`) | Trạng thái Tự công bố trong Khóa luận G9 (`11_...`) | Đánh giá Sai lệch |
| :--- | :---: | :---: | :--- |
| **REQ-02 (Dự báo trễ Outbound)** | **ACCEPTED_WITH_LIMITATION** (RF không có checkpoint; P5 chỉ có file lịch sử) | **FULLY_ACCEPTED** | **Tự ý nâng cấp (Escalation):** G9 bỏ qua các giới hạn đã được G8 xác nhận. |
| **REQ-08 (Mô phỏng Monte Carlo)** | **ACCEPTED_WITH_LIMITATION** (Động cơ mới chỉ có 100 kịch bản pilot) | **ACCEPTED_WITH_LIMITATION** (Nhưng lại tuyên bố đã chạy 500 kịch bản) | **Mâu thuẫn số liệu kịch bản.** |
| **REQ-09 (Streamlit Dashboard)** | **ACCEPTED_WITH_LIMITATION** (Visual QA vẫn đang pending trên browser thật) | **FULLY_ACCEPTED** | **Tự ý xóa bỏ giới hạn:** G9 coi như Visual QA đã hoàn tất 100%. |
| **REQ-10 (Thực nghiệm mở rộng / tích hợp)** | **ACCEPTED_WITH_LIMITATION** (Phân định synthetic vs real-data không có tail) | **FULLY_ACCEPTED** | **Tự ý xóa bỏ giới hạn:** G9 gộp chung thành đạt chuẩn toàn diện. |
| **Tổng kết Phân bổ Trạng thái** | **5 FULLY / 4 LIMITATION / 1 PARTIAL** | **8 FULLY / 1 LIMITATION / 1 PARTIAL** | **G9 đã tự nâng 3 yêu cầu từ LIMITATION lên FULLY_ACCEPTED.** |

---

## 4. CHI TIẾT VỀ PHÁT HIỆN TRÁO ĐỔI DỮ LIỆU ĐẾN/ĐI (FINDING C-04)

Đây là một trong những phát hiện kiểm toán nghiêm trọng nhất của Gate G10:
1. Trong `remediation_evidence/G3_ml_validation/09_BASELINE_COMPARISON.md`, Mục 2.2 mang tiêu đề:  
   `Core Departure Population (2023 Selection Split, N = 332,734)`
   Các số liệu ghi nhận:
   - Baseline Median: $\text{MAE} = 15.6028$, $\text{RMSE} = 45.7618$, $\text{Tail MAE} = 62.3314$, $\text{Bias} = -13.4883$.
   - Departure XGBoost: $\text{MAE} = 17.6017$, $\text{RMSE} = 43.0005$, $\text{Tail MAE} = 48.9086$, $\text{Bias} = -3.0063$.
2. Khi tác giả viết Bảng 5.1 trong Khóa luận G9 (`03_THESIS_DRAFT.md` và `04_EXPERIMENT_TABLES_AND_FIGURES.md`), tác giả đã sao chép **nguyên xi 4 con số của Departure này** và điền vào bảng dưới nhãn:  
   `Hồi quy Inbound / Baseline Median: MAE 15,60 phút, RMSE 45,76 phút, Tail MAE 62,33 phút`  
   `Hồi quy Inbound / NGBoost Student-t: MAE 17,60 phút, RMSE 43,00 phút, Tail MAE 48,91 phút`!
3. Trong khi đó, dữ liệu Inbound thực tế (Mục 2.1 của G3-09) có các số liệu hoàn toàn khác:
   - Inbound Median: $\text{MAE} = 16.7576$, $\text{RMSE} = 45.7483$.
   - Inbound XGBoost: $\text{MAE} = 20.2180$, $\text{RMSE} = 45.5967$.
4. **Hệ quả học thuật:** Toàn bộ phần lý giải về mô hình Inbound NGBoost Student-t trong Chương 5 của Khóa luận G9 đang sử dụng các số liệu thực nghiệm của... mô hình hồi quy Chuyến bay Đi (Departure XGBoost)!

---

## 5. DANH SÁCH BẮT BUỘC CÁC TUYÊN BỐ PHẢI LOẠI BỎ (UNSUPPORTED CLAIMS REGISTER)

Sinh viên phải loại bỏ hoặc đính chính ngay lập tức các nội dung sau trước khi in ấn khóa luận:
1. **Loại bỏ tuyên bố Outbound ROC-AUC = 0.795** $\to$ Đính chính thành **0.643** (Calibrated XGBoost trên 332.734 chuyến bay).
2. **Loại bỏ tuyên bố Outbound Random Forest ROC-AUC = 0.779** $\to$ Ghi rõ: *"Mô hình Random Forest phân loại chuyến bay đi không được huấn luyện checkpoint chính thức trong pipeline"* hoặc loại khỏi bảng.
3. **Loại bỏ Bảng 5.4 chi phí Monte Carlo (10.0, 7.82, 12.45, 6.41)** $\to$ Thay thế bằng bảng chi phí thật trích xuất từ `statistical_summary.json` (Mode A: 1606.43, Mode B1: 134.83, Mode B2: 147.43, Mode C2: 122.43).
4. **Đính chính số lượng kịch bản Monte Carlo mới từ 500 xuống 100**.
5. **Đính chính Bảng 5.1 Inbound Regression** để không dùng nhầm số liệu của Departure.
6. **Đính chính thông tin bìa khóa luận** để phản ánh đúng danh sách 3 sinh viên, tên GVHD và mã đề tài chính thức theo đúng đề cương của Nhà trường.
