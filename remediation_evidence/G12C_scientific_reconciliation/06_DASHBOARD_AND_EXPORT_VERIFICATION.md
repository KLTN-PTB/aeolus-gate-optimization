# BÁO CÁO 06: KIỂM CHỨNG TÍNH NHẤT QUÁN CỦA DASHBOARD VÀ ADAPTER XUẤT DỮ LIỆU
## AEOLUS-G12C — DASHBOARD & EXPORT INTEGRITY AUDIT

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Phạm vi:** Kiểm toán tính nhất quán của Bảng điều khiển Streamlit (`dashboard/`), các Export Adapters và Giao diện Báo cáo  

---

## 1. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG BẢNG ĐIỀU KHIỂN (AUTOMATED APPTEST SUITE)

Toàn bộ bộ kiểm thử tự động của Dashboard được thực thi bằng Pytest Streamlit AppTest:
- **Lệnh thực thi:** `.venv\Scripts\python.exe -m pytest tests/dashboard/ -q`
- **Kết quả:** **`359 passed, 3 warnings in 8.90s (100% PASS)`**
- **Phân loại phạm vi:**
  - `test_foundation.py`: 44 tests kiểm thử cấu trúc nền tảng và nạp dữ liệu.
  - `test_gate_operations.py`: 32 tests kiểm thử sơ đồ Gantt và điều phối cổng.
  - `test_lab_and_robustness.py`: 48 tests kiểm thử phòng thí nghiệm mô phỏng và Monte Carlo.
  - `test_services.py`: 55 tests kiểm thử các dịch vụ logic và cache.
  - `test_ui_components.py`: 40 tests kiểm thử các thành phần UI dùng chung.
  - `test_ui_r01_data_integrity.py` đến `test_ui_r08_final_acceptance.py`: 140 tests kiểm thử quy chuẩn giao diện và bảo mật.

---

## 2. KIỂM TOÁN TÍNH NHẤT QUÁN DỮ LIỆU VÀ TRẠNG THÁI BỘ GIẢI

### 2.1. Phân Biệt Tuyệt Đối Giữa `OPTIMAL` và `FEASIBLE`
- Trong `dashboard/core/status_mapping.py` và `dashboard/adapters/export_adapter.py`:
  - Trạng thái `OPTIMAL` được ánh xạ sang huy hiệu màu xanh lá cây (`StatusBadge.OPTIMAL` / `Certified Global Optimum`).
  - Trạng thái `FEASIBLE` được ánh xạ sang huy hiệu màu vàng/cam (`StatusBadge.FEASIBLE` / `Feasible Incumbent (Time Limit)`).
  - Trạng thái `INFEASIBLE` được ánh xạ sang huy hiệu màu đỏ (`StatusBadge.INFEASIBLE` / `Physical Gate Conflict`).
- **Khẳng định:** Bảng điều khiển không bao giờ đánh đồng hoặc gộp chung trạng thái khả thi với tối ưu toàn cục đã chứng minh toán học.

### 2.2. Minh Bạch Các Trường Hợp Infeasible và Timeout
- Bảng điều khiển hiển thị đầy đủ và trung thực:
  - Toàn bộ $1,122$ lượt không khả thi của Mode A được biểu diễn rõ ràng với tỷ lệ khả thi $25.20\%$ và số lượng xung đột cổng $1.364$ cặp/kịch bản.
  - Kịch bản `MC_REM_S0183` trong Mode C2 hiển thị rõ runtime $1,572.82$ ms và trạng thái `FEASIBLE` do chạm deadline $1.5$s, không che giấu hoặc làm tròn thành `OPTIMAL`.

### 2.3. Phân Biệt Phạm Vi Inbound và Outbound
- Giao diện Control Tower tách biệt rõ ràng hai luồng chỉ số:
  - Luồng Đến (Inbound): Chuyến bay hạ cánh tại Atlanta, dự báo trễ đến bằng mô hình NGBoost Student-t.
  - Luồng Đi (Outbound): Chuyến bay khởi hành từ Atlanta, dự báo trễ đi bằng mô hình Calibrated XGBoost ($P \ge 15$m).
  - Các chỉ số tỷ lệ trễ và sai số MAE/RMSE được gắn nhãn độc lập, không bị trộn lẫn giữa hai chiều bay.

### 2.4. Ngăn Chặn Tái Nhãn Dữ Liệu Mô Phỏng (Anti-Rebranding Guard)
- Căn cứ theo hợp đồng bất biến khoa học `INV-07` trong `tests/test_g7_scientific_invariants.py`:
  - Dữ liệu có nguồn gốc tổng hợp (`SYNTHETIC_SIMULATION`) được gắn nhãn vĩnh viễn trong metadata và export headers.
  - Bất kỳ cố gắng nào từ phía export adapter nhằm đổi nhãn `SYNTHETIC` thành `REAL_AEOLUS` đều kích hoạt ngoại lệ `ProvenanceMismatchError` và chặn luồng xuất khẩu.

---

## 3. ĐÁNH GIÁ TRẠNG THÁI KIỂM ĐỊNH THỊ GIÁC (VISUAL BROWSER QA STATUS)

- Trong môi trường dòng lệnh (headless terminal CI/CD không có màn hình đồ họa trực tiếp), toàn bộ 359 unit/integration/AppTest tests đã được kiểm chứng tự động và đạt 100% PASS.
- **Tuyên bố liêm chính học thuật:** Báo cáo ghi nhận trạng thái kiểm định thị giác trên trình duyệt thực tế là **`VISUAL_QA_PENDING_LIVE_DEMO` (SẴN SÀNG CHO PHIÊN DEMO TRỰC TIẾP)**. Chúng tôi không tự tuyên bố đã hoàn tất kiểm tra mắt người trên trình duyệt trong môi trường headless khi chưa thực hiện phiên demo tương tác. Giao diện sẵn sàng được khởi chạy bằng lệnh `streamlit run dashboard/app.py` trong buổi bảo vệ khóa luận.
