# AEOLUS-G10 — DELIVERABLE 03: G2 CAUSAL MONTE CARLO SCIENTIFIC AUDIT

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Senior Operations Research Scientist & Monte Carlo Simulation Auditor  
**Target Phase:** Phase G2 Monte Carlo Causality Remediation & Robustness Evaluation  

---

## 1. MỤC TIÊU VÀ NGUỒN BẰNG CHỨNG KIỂM TOÁN

Kiểm toán viên tiến hành rà soát độc lập mã nguồn, tệp cấu hình và toàn bộ artifact của Phase G2 trong thư mục `artifacts/remediation/monte_carlo_remediated/`:
- `src/simulation/monte_carlo_engine_v2.py`
- `scripts/run_g2_monte_carlo_remediation.py`
- `tests/test_g2_monte_carlo_causality.py`
- `simulation_manifest.json`
- `scenario_index.csv`
- `statistical_summary.json`
- Các tệp kết quả: `fixed_plan_results.csv`, `recourse_b1_retrospective_results.csv`, `recourse_b2_online_results.csv`, `foresight_c1_greedy_results.csv`, `foresight_c2_optimal_results.csv`.

---

## 2. KẾT QUẢ KIỂM TRA 10 TIÊU CHÍ KHOA HỌC CỐT LÕI

| STT | Tiêu chí Kiểm chứng | Kết quả Thực tế (Audited Findings) | Đánh giá |
| :---: | :--- | :--- | :---: |
| 1 | **Số lượng kịch bản mới sinh ra** | **ĐÚNG 100 KỊCH BẢN** (`n_scenarios: 100`, seed `202601`). Hoàn toàn không có 500 kịch bản mới. | **DISCREPANCY (G8/G9 báo sai 500)** |
| 2 | **Tính nhân quả của Mode B2** | Thuật toán quét sự kiện theo thứ tự thời gian (`event_order = sorted(realized_flights)`). Tại thời điểm $t$, chỉ biết các chuyến bay đã đến trước $t$. | **VERIFIED (STRICTLY CAUSAL)** |
| 3 | **Cơ chế khóa tàu bay (Docked Lock)** | Chuyến bay đã cập cổng trước thời điểm $t$ được thêm vào `locked_flights` và **tuyệt đối không bị dời cổng hồi tố**. | **VERIFIED (NON-RETROACTIVE)** |
| 4 | **Bộ giải thực thi trong Mode B2** | Mode B2 gọi **`RollingOnlineGreedy`** (tìm kiếm tham lam lân cận trên cổng tiếp xúc khả thi), **KHÔNG GỌI CP-SAT** trong vòng lặp thời gian thực. | **VERIFIED (HEURISTIC ONLINE)** |
| 5 | **Bộ giải thực thi trong Mode B1** | Mode B1 nạp toàn bộ ma trận trễ của cả ngày vào **`CPSatGateSolver`** sau khi ngày khai thác kết thúc (Retrospective Full-Information). | **VERIFIED (RETROSPECTIVE)** |
| 6 | **Tỷ lệ tối ưu của Mode C2 Oracle** | Trong 100 kịch bản, Mode C2 gọi CP-SAT với full-foresight: **100 / 100 ca đạt status OPTIMAL** và `is_optimal_proven = True`. | **VERIFIED (PROVEN OPTIMAL)** |
| 7 | **Nguồn gốc tham số ngẫu nhiên** | Phân phối biên (marginal distributions) dùng **HẰNG SỐ CỐ ĐỊNH**: Student-t (Arrival: $\nu=4.5, \mu=5, \sigma=18$; Departure: $\nu=4, \mu=8, \sigma=22$). **KHÔNG lấy động từ mô hình ML**. | **ACCEPTED_WITH_LIMITATION** |
| 8 | **Đồng bộ số ngẫu nhiên dùng chung (CRN)** | Cùng seed ngẫu nhiên (`seed = 202601`), ma trận realization hash khớp 100% giữa các chế độ A, B1, B2, C1, C2. | **VERIFIED (STRICT CRN ALIGNMENT)** |
| 9 | **Đơn vị và hàm mục tiêu đánh giá** | Cùng sử dụng hàm đánh giá chuẩn `evaluate_gate_assignment`, phân tách giữa Decision Cost và Reporting Cost. | **VERIFIED (UNIFIED OBJECTIVE)** |
| 10 | **Giá trị chi phí thực tế đo lường được** | Mode A: **1.606,43** | Mode B1: **134,83** | Mode B2: **147,43** | Mode C2: **122,43**. | **CONTRADICTS G8/G9 REPORT** |

---

## 3. PHÂN TÍCH CHI TIẾT SỰ SAI LỆCH VỀ SỐ LƯỢNG KỊCH BẢN (100 VS 500)

1. **Thực tế trong Artifact:**  
   - Tệp `artifacts/remediation/monte_carlo_remediated/simulation_manifest.json` ghi nhận:
     ```json
     "n_scenarios": 100,
     "seed": 202601
     ```
   - Tệp `scenario_index.csv` có đúng **100 dòng** (kịch bản từ `0` đến `99`).
   - Tệp `statistical_summary.json` ghi nhận: `"n_requested": 100, "n_generated": 100, "n_evaluated": 100`.
2. **Sai lệch trong Báo cáo G8 và G9:**  
   - Báo cáo G8 (`11_APPROVED_RESULTS_FOR_THESIS.md`) và Khóa luận G9 (`03_THESIS_DRAFT.md` Chương 3, Chương 5 và Bảng 5.4) đồng loạt tuyên bố: *"Mô phỏng Monte Carlo trên 500 kịch bản ngẫu nhiên có tương quan"*.
3. **Nguyên nhân gốc rễ:**  
   - Con số 500 kịch bản là quy mô của pha thử nghiệm lịch sử P09 (khi các chế độ chưa được khắc phục tính nhân quả).
   - Trong Gate G2 remediation, do giới hạn thời gian tính toán của CP-SAT trên hàng trăm kịch bản, tác giả đã chạy bộ mô phỏng remediated với tham số `--n-scenarios 100`.
   - Khi viết báo cáo G8 và khóa luận G9, tác giả đã **tùy tiện tuyên bố 500 kịch bản** để khớp với đề cương ban đầu mà không thực sự chạy mở rộng lên 500 kịch bản trên động cơ mới.

---

## 4. PHÂN TÍCH SỰ NGỤY TẠO VỀ GIÁ TRỊ CHI PHÍ TRONG BẢNG 5.4 CỦA KHÓA LUẬN G9

Bảng đối chiếu dưới đây phơi bày sự sai khác giữa Số liệu Thật trong Artifact và Số liệu Tuyên bố trong Khóa luận G9:

| Chế độ Mô phỏng | Chi phí Trung bình Thật (`statistical_summary.json`) | Chi phí Tuyên bố trong G9 (Bảng 5.4) | Tỷ lệ Xung đột Cổng Thật | Tỷ lệ Xung đột G9 | Số lần Đổi cổng TB Thật | Số lần Đổi cổng G9 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Fixed Plan)** | **1.606,43** | **10,0000** | **76,0%** | 76,0% | **0,0** | 0,0 |
| **Mode B1 (Retrospective)** | **134,83** | **7,8200** | **0,0%** | 0,0% | **2,45 lần** | **18,4 lần** |
| **Mode B2 (Online Causal)** | **147,43** | **12,4500** | **0,0%** | 0,0% | **2,76 lần** | **4,2 lần** |
| **Mode C1 (Greedy Foresight)**| **134,83** | *Không báo cáo* | **0,0%** | — | **2,45 lần** | — |
| **Mode C2 (Optimal Oracle)**| **122,43** | **6,4100** | **0,0%** | 0,0% | **2,31 lần** | 0,0 |

### Đánh giá của Kiểm toán viên Độc lập:
- Trong dữ liệu thật, chi phí của Mode A là **1.606,43** điểm. Con số này rất lớn vì khi xảy ra xung đột cổng vật lý (tỷ lệ 76%), trọng số phạt xung đột (`conflict_weight = 10.000,0`) được áp dụng.
- Trong khi đó, Khóa luận G9 ghi nhận chi phí Mode A là **10.0000**, Mode B1 là **7.8200**, Mode B2 là **12.4500**, và Mode C là **6.4100**.
- **Các con số 10.0000, 7.8200, 12.4500, 6.4100 hoàn toàn KHÔNG XUẤT HIỆN trong bất kỳ tệp kết quả nào của G2!** Chúng dường như được tác giả tự nghĩ ra để "đồng bộ" một cách giả tạo với giá trị hàm mục tiêu của bài toán benchmark tĩnh 60 chuyến bay ($z = 10.0000$).
- Số lần đổi cổng trong G9 (B1 đổi 18.4 lần, B2 đổi 4.2 lần) cũng hoàn toàn không khớp với dữ liệu thật trong artifact (B1 đổi trung bình 2.45 lần, B2 đổi 2.76 lần).

---

## 5. KẾT LUẬN VỀ PHASE G2

1. **Về mặt kỹ thuật thuật toán:** Thuật toán `RemediatedMonteCarloEngineG2` trong `monte_carlo_engine_v2.py` đã giải quyết thành công vấn đề nhân quả thời gian, cơ chế khóa tàu bay và phân rã các chiều khả thi. Đây là một đóng góp kỹ thuật xuất sắc.
2. **Về mặt báo cáo khoa học:** Báo cáo G8 và Khóa luận G9 đã mắc lỗi nghiêm trọng khi:
   - Khai báo sai số lượng kịch bản (báo cáo 500 nhưng thực tế chỉ chạy 100).
   - Ngụy tạo số liệu chi phí và số lần đổi cổng trong Bảng 5.4.
3. **Khuyến nghị bắt buộc:** Sinh viên phải thay thế toàn bộ Bảng 5.4 bằng số liệu trích xuất chính xác từ `statistical_summary.json` (Mode A: 1606.43, Mode B1: 134.83, Mode B2: 147.43, Mode C2: 122.43 trên 100 kịch bản).
