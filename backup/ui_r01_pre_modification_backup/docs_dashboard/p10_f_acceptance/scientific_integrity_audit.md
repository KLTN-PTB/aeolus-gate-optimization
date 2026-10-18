# BÁO CÁO KIỂM TOÁN TÍNH TOÀN VẸN KHOA HỌC — PHASE P10-F
## Scientific Integrity & Research Governance Audit

**Mục tiêu kiểm toán:** Đảm bảo không xảy ra hiện tượng rò rỉ nhãn (data leakage), không tuyên bố quá mức về mặt khoa học (scientific overclaim), không ngụy tạo dữ liệu hay nghiệm số, và bảo lưu nguyên vẹn các phát hiện kiểm toán từ giai đoạn P10-00.

---

## 1. KIỂM SOÁT RÒ RỈ DỮ LIỆU ĐÍCH (ZERO DATA LEAKAGE VERIFICATION)

- **Quy tắc Kiểm tra:** Trong chế độ lập kế hoạch (Planning Mode), người điều hành bay và mô hình phân cổng chỉ được phép nhìn thấy thời gian bay theo lịch trình (`scheduled_time`) và độ trễ dự báo từ ML (`predicted_delay`). Tuyệt đối không được xuất hiện bất kỳ cột độ trễ thực tế nào (`arr_delay`, `dep_delay`, `actual_arr_delay_min`).
- **Triển khai Code:** `ScientificValidator.check_prediction_data_leakage(columns)` được gọi tự động tại mọi cổng tải dữ liệu (`adapt_prediction_row_to_view`, `export_benchmark_to_csv`, `export_assignments_to_csv`).
- **Kết quả Kiểm thử:** Test `test_group_c_02_zero_leakage_in_planning_views` ném ra ngoại lệ `DataLeakageError` thành công khi cố ý đưa nhãn thực tế vào.

---

## 2. BẢO TOÀN 4 ĐIỀU KHOẢN CẢNH BÁO KHOA HỌC (P10-00 ISSUE REGISTER)

### Finding D1: Tỷ lệ Khả thi 0.0% vs Xác suất Xung đột 74.8% trong Mode A
- **Thực tế:** Trong 500 kịch bản mô phỏng giữ nguyên lịch tĩnh, 74.8% số kịch bản phát sinh va chạm vật lý trực tiếp giữa hai tàu bay trên cùng một cổng đỗ.
- **Giải thích khoa học:** Ở 25.2% số kịch bản còn lại, dù không có 2 tàu bay nào đỗ trùng nhau về mặt không gian, nhưng thời gian quay đầu (turnaround) bị trễ đã vi phạm khoảng đệm an toàn 15 phút (`separation buffer`). Do đó, theo định nghĩa toán học nghiêm ngặt về ràng buộc cứng, kế hoạch tĩnh có tỷ lệ khả thi là 0.0%.
- **Bảo toàn giao diện:** Đồ thị và KPI thể hiện tách bạch rõ ràng cả 2 chỉ số này để tránh gây hiểu lầm cho hội đồng phản biện.

### Finding D2: Mean Cost Giống Nhau giữa Mode B và Mode C (130.73 pts)
- **Thực tế:** Cả Mode B (Reactive Recourse) và Mode C (Oracle) đều cho chi phí trung bình bằng đúng 130.73 pts trên 500 kịch bản.
- **Giải thích kỹ thuật:** Tại sân bay Atlanta với 120 chuyến bay thử nghiệm, quỹ cổng đỗ của sân bay đủ rộng và phân phối trễ đủ vừa phải để thuật toán tham lam tái gán cổng theo thời gian thực (Mode B) tìm được phương án tối ưu tương đương với một thực thể biết trước tương lai hoàn hảo (Mode C).
- **Quy chuẩn tuyên bố:** Khóa giao diện không cho phép viết câu "Recourse tương đương Oracle trong mọi trường hợp", mà bắt buộc phải ghi rõ đây là đặc thù của tập kịch bản ATL 120 chuyến.

### Finding D3: Giới hạn Triển khai của Oracle (Non-Deployable Limit)
- **Bản chất:** Mode C sử dụng thông tin độ trễ trong tương lai (phi nhân quả - non-causal). Trong thực tế, không có trung tâm điều hành nào biết trước độ trễ máy bay trước khi cất cánh.
- **Quy chuẩn giao diện:** Mode C được gắn nhãn đỏ `NON-DEPLOYABLE (THEORETICAL BENCHMARK)` trên tất cả các màn hình hiển thị.

### Finding D4: Niêm phong Dữ liệu Kiểm định Độc lập 2024 (Temporal Quarantine)
- **Bản chất:** Toàn bộ quá trình huấn luyện ML và mô phỏng Monte Carlo chỉ sử dụng dữ liệu năm 2023. Tập dữ liệu năm 2024 được niêm phong độc lập (`Quarantined Holdout`) theo Protocol V4.
- **Triển khai Code:** `ScenarioService` lập tức chặn `PermissionError` nếu có yêu cầu tải kịch bản năm 2024.

---

## 3. NGUYÊN TẮC TRUNG THỰC VỀ TÍNH TỐI ƯU TOÁN HỌC

1. **Không False Optimality:**
   - Thuật toán Heuristic (Greedy) và Metaheuristic (Simulated Annealing, Hybrid) chỉ được dán nhãn `FEASIBLE (Heuristic)`. Cờ `is_optimal_proven` bị cưỡng chế bằng `False`.
   - Chỉ duy nhất bộ giải CP-SAT khi chứng minh được `optimality_gap == 0.0%` mới được hiển thị nhãn `OPTIMAL (Proven)`.
2. **Không Bịa đặt Nghiệm ở Quy mô 1,500 Chuyến:**
   - Tại quy mô 1,500 chuyến bay × 50 cổng, CP-SAT vượt quá thời gian cho phép 10 giây mà chưa tìm thấy nghiệm hợp lệ. Trạng thái hiển thị bắt buộc là **`UNKNOWN`**, tuyệt đối không giả mạo thành `FEASIBLE`.
3. **Không Bịa đặt Lịch Bay Chi tiết ở Drill-down Monte Carlo:**
   - Trong giao diện truy vết kịch bản Monte Carlo, hệ thống chỉ hiển thị các chỉ số tổng hợp cấp độ kịch bản (số lần đổi cổng, xung đột, chi phí phạt, mã băm realization). Tuyệt đối không sinh lịch bay giả mạo dạng Gantt khi dữ liệu gốc không lưu trữ.
