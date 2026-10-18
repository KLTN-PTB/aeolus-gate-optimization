# BÁO CÁO KIỂM TOÁN 06: KIỂM TOÁN GIAO DIỆN BẢNG ĐIỀU KHIỂN VÀ ĐỐI SOÁT PHẠM VI KIỂM THỬ (DASHBOARD & TEST AUDIT)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Principal Software Architect, Thesis Quality Assurance Lead  

---

## 1. Kiểm toán Giao diện Bảng điều khiển Vận hành Streamlit (Dashboard Forensic Audit)

Hệ thống Dashboard được thiết kế theo kiến trúc hiện đại, phân tách rõ ràng giữa Presentation Mode (Chế độ Thuyết trình báo cáo) và Research Mode (Chế độ Nghiên cứu chuyên sâu), gồm 5 trang nghiệp vụ chính:

### 1.1. Chi tiết Kiểm toán 5 Trang Nghiệp vụ

1. **Trang 01: Đài Kiểm soát Không lưu (Control Tower):**
   * *Nguồn dữ liệu:* Đọc trực tiếp từ kịch bản chọn lọc `BTS_OTP_2023_CURATED` và manifest vận hành.
   * *Nội dung:* Hiển thị thanh ngữ cảnh (Context Bar), 4 thẻ KPI đồng bộ (Tổng chuyến, Cổng hoạt động, Đỉnh concourse, Sức khỏe solver), biểu đồ sóng trễ đến (Inbound Delay Wave), và biểu đồ mức sử dụng cổng theo concourse (T, A, Remote).
   * *Xác minh:* Không có số liệu hardcode giả lập. Dữ liệu synthetic được gắn nhãn minh bạch.

2. **Trang 02: Tình báo Chuyến bay Hai Lõi (Flight Intelligence):**
   * *Nguồn dữ liệu:* Hợp đồng dự báo `StandardizedPredictionRecord`, kết quả suy luận hai lõi và tệp SHAP `global_importance.json`.
   * *Nội dung:* Tab A (Phân phối dự báo đến & đi), Tab B (Động lực học luân chuyển máy bay với đệm kỹ thuật 45 phút và giãn cách 15 phút), Tab C (Biểu đồ tầm quan trọng đặc trưng TreeSHAP toàn cục và case study cục bộ).
   * *Xác minh:* Tiêu đề biểu đồ sạch (đã loại bỏ mã nội bộ `CHART-03`), hiển thị hãng hàng không thật (Delta, United, Southwest).

3. **Trang 03: Vận hành Cổng đỗ & Biểu đồ Master Gantt (Gate Operations):**
   * *Nguồn dữ liệu:* `OptimizationResult` từ solver và `ConstraintDiagnostic` từ bộ kiểm chứng độc lập.
   * *Nội dung:* Không gian làm việc Master Gantt toàn màn hình (`width="stretch"`), trục Y phân nhóm theo Concourse T, A, Remote, Apron Overflow; bộ lọc concourse kèm số lượng cổng động; ngăn kéo Flight Inspector chi tiết.
   * *Xác minh:* Nút "Chạy Phân Cổng CP-SAT" đòi hỏi người dùng click chủ động, tuyệt đối **không tự ý giải (unsolicited solve)** khi vừa mở trang hoặc khi đổi bộ lọc. Huy hiệu kiểm chứng độc lập hiển thị rõ ràng số lượng xung đột ($0$ với nghiệm tối ưu).

4. **Trang 04: Phòng Thí nghiệm Tối ưu hóa (Optimization Lab):**
   * *Nguồn dữ liệu:* `aggregate_metrics.json` và kết quả chạy đa bộ giải.
   * *Nội dung:* Bảng so sánh 4 bộ giải (Greedy, CP-SAT, SA, Hybrid), phân tách rạch ròi giữa Chi phí Quyết định ($J_{\text{decision}}$) và Chi phí Báo cáo ($J_{\text{reporting}}$), đường biên Pareto Frontier (Chi phí vs Thời gian), đường cong mở rộng quy mô CP-SAT đến 1.500 chuyến bay.
   * *Xác minh:* Bộ giải Greedy và SA được gắn nhãn đúng là `FEASIBLE (HEURISTIC)`, không tự xưng là `OPTIMAL`.

5. **Trang 05: Phòng Thí nghiệm Độ bền vững (Robustness Lab):**
   * *Nguồn dữ liệu:* `artifacts/remediation/monte_carlo/` (500 kịch bản ngẫu nhiên).
   * *Nội dung:* So sánh phân phối chi phí Mode A (Fixed Plan), Mode B (Recourse) và Mode C (Oracle); phân tích rủi ro đuôi (CVaR-90, CVaR-95); phân tích kiểm định bắt cặp Paired Difference; hộp kiểm tra Research Inspector.
   * *Xác minh:* Mode C được gắn nhãn cảnh báo bắt buộc `KHÔNG THỂ TRIỂN KHAI THỰC TẾ (NON_DEPLOYABLE)` do giả định biết trước tương lai.

### 1.2. Trạng thái Thẩm định Thị giác (Visual QA Status)
* **Kiểm thử Tự động Headless (`AppTest`):** **100% PASSED** (359 bài kiểm tra bao phủ tất cả các trang, widget, luồng trạng thái session_state và bộ chuyển đổi adapter).
* **Kiểm thử Thị giác trên Trình duyệt Người thật (Human Browser Visual Inspection):**
  * Danh sách 40 tiêu chí kiểm tra trực quan (`docs/dashboard/redesign/UI-R08/05_visual_acceptance.md`) đã được soạn thảo chi tiết.
  * Tuy nhiên, trong môi trường dòng lệnh không có giao diện đồ họa GUI/Browser đang mở, kiểm toán tuyên bố trạng thái chính thức là: **`VISUAL_QA_BLOCKED / PENDING_BROWSER_DEMO`**.
  * **Quy tắc Kiểm toán:** Tuyệt đối không tự tuyên bố "Browser Visual PASS" khi chỉ mới chạy qua AppTest không ném exception.

---

## 2. Đối soát Phạm vi và Số lượng Kiểm thử (Test Scope Reconciliation)

Trong các báo cáo của dự án xuất hiện nhiều con số thống kê kiểm thử khác nhau: **1.216 tests (báo cáo P14)**, **359 dashboard tests**, **89 P07–P09 tests**, **65 OR/scalability tests**, **40 UI-R08 tests**, và **tổng 513 tests (báo cáo UI-R08)**.

Kiểm toán đã phân tích cấu hình `pytest.ini` và chạy lệnh thu thập kiểm thử thực tế (`pytest --collect-only`) để giải mã hoàn toàn các con số này:

### 2.1. Bản đồ Phân rã Test Suites Thực tế

```
Tổng số kiểm thử thu thập trong toàn bộ Repository: 1.990 TESTS
├── [A] Test Suites Hoạt động Hiện hành (Active Certified Suites):
│   ├── Bộ kiểm thử Giao diện Dashboard (tests/dashboard/): 359 tests
│   │   ├── Kiểm thử Cơ sở & Nền tảng (test_foundation.py): 78 tests
│   │   ├── Kiểm thử Dịch vụ & Cache (test_services.py): 35 tests
│   │   ├── Kiểm thử Thành phần UI (test_ui_components.py): 34 tests
│   │   ├── Kiểm thử Vận hành Cổng (test_gate_operations.py): 42 tests
│   │   ├── Kiểm thử Lab & Robustness (test_lab_and_robustness.py): 38 tests
│   │   ├── Kiểm thử Các Vòng Tái thiết kế (test_ui_r01 -> r07): 67 tests
│   │   └── Kiểm thử Nghiệm thu R08 (test_ui_r08_final_acceptance.py): 40 tests (Trùng khớp 40 AC)
│   │   └── Kiểm thử Nghiệm thu Tổng hợp (test_final_acceptance.py): 25 tests
│   │       └── [Lưu ý: 40 tests R08 + 25 tests Final = 65 Acceptance tests]
│   ├── Bộ kiểm thử Remediation Mới (P07, P08, P09): 89 tests
│   │   ├── P07 Native Dual-Core (test_native_dual_core_pipeline_p07.py): 30 tests
│   │   ├── P08 ML Validation & SHAP (test_ml_research_validation_p08.py): 28 tests
│   │   └── P09 Monte Carlo Robustness (test_monte_carlo_robustness_p09.py): 31 tests
│   └── Các bộ kiểm thử Nghiên cứu Lịch sử từ P01 đến P14: ~1.542 tests
│       (Bao gồm mô hình điểm, mô hình xác suất, kiểm toán rò rỉ, Optuna HPO, kiểm toán schema...)
└── [B] Bộ kiểm thử Lịch sử Đã Cho Nghỉ hưu (Retired Historical Guards): 18 tests
    (Được loại trừ trong pytest.ini vì gắn liền với manifest phiên bản cũ v1, v2)
```

### 2.2. Giải mã Con số 513 Tests trong Báo cáo UI-R08
* Khi các kỹ sư thực hiện nghiệm thu vòng UI-R08, lệnh thực thi được chạy là:
  $$\text{pytest tests/dashboard (359) } + \text{tests/P07-P09 (89) } + \text{tests/acceptance/scalability (65)} = \mathbf{513\text{ tests}}$$
* **Kết luận Pháp y:** Con số **513 tests** là **tổng số lượt kiểm thử trong phiên nghiệm thu tích hợp liên module**, trong đó 65 bài kiểm tra nghiệm thu đã được tính trùng trong thư mục `tests/dashboard/`.
* Tương tự, con số **1.216 tests** trong báo cáo P14 là ảnh chụp trạng thái kiểm thử tại thời điểm nghiệm thu pha P14 (trước khi bổ sung các bài kiểm tra P01–P06 OR-Tools, P07–P09 và 359 bài kiểm tra Dashboard). Hiện tại toàn bộ kho lưu trữ có **1.990 bài kiểm tra độc lập**.

---

## 3. Các Phát hiện Kiểm toán Trọng yếu (Findings Register for Dashboard & Tests)

### FINDING-P2-03: Kiểm thử Bảng điều khiển Mới Dừng lại ở Tầng Headless AppTest, Chưa Hoàn tất Human Visual QA trên Browser Thật
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Để đáp ứng yêu cầu nghiệm thu sản phẩm phần mềm khóa luận, ứng dụng Dashboard phải được kiểm tra thực tế trên trình duyệt web, đảm bảo độ co giãn màn hình, độ tương phản và không bị lỗi tràn chữ.
* **Observed:** 359 bài test đều là kiểm thử headless thông qua thư viện `streamlit.testing.v1.AppTest`. Báo cáo nghiệm thu `UI-R08/05_visual_acceptance.md` ghi rõ trạng thái `PARTIAL / VISUAL_QA_PENDING`.
* **Impact:** Tiềm ẩn rủi ro phát sinh lỗi hiển thị nhỏ về font chữ, màu sắc hoặc tỷ lệ khung hình khi chiếu trên máy chiếu hội đồng nếu chưa chạy thử qua trình duyệt thực tế trước buổi bảo vệ.
* **Proposed Resolution:** Sinh viên cần thực hiện một buổi chạy thử trực tiếp trên trình duyệt máy tính (`streamlit run dashboard/app.py`), chụp ảnh màn hình minh chứng thực tế và tích hợp vào tài liệu bảo vệ.
* **Confidence:** `HIGH`
