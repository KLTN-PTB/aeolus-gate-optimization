# AEOLUS FLIGHT OPERATIONS INTELLIGENCE DASHBOARD
## Hướng Dẫn Vận Hành & Trình Diễn Ứng Dụng Khóa Luận Tốt Nghiệp

**Khóa luận:** Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay  
**Framework:** Python 3.11 | Streamlit 1.40+ | Plotly | Google OR-Tools CP-SAT  
**Chế độ vận hành:** 100% Chạy Offline Độc lập (Airplane Mode Ready)

---

## 1. TỔNG QUAN HỆ THỐNG DASHBOARD

Dashboard Aeolus được thiết kế chuyên biệt cho việc bảo vệ khóa luận và trình diễn vận hành hàng không, tích hợp trọn vẹn mô hình **Predict-then-Optimize**:

Ứng dụng bao gồm **5 trang chức năng** và **2 chế độ hiển thị**:
1. **01 — Control Tower (Trung tâm Chỉ huy):** Tổng quan vận hành ngày bay, lưu lượng 24h, và tỷ lệ đúng giờ dự báo.
2. **02 — Flight Intelligence (Trí tuệ Chuyến bay):** Phân tích trễ âm/dương và giải thích mô hình ML qua SHAP Waterfall.
3. **03 — Gate Operations (Điều hành Cổng đỗ):** Biểu đồ Gantt tương tác, bóc tách xung đột, và demo giải trực tiếp Greedy / CP-SAT.
4. **04 — Optimization Lab (Phòng thí nghiệm Tối ưu):** Đối chuẩn 4 thuật toán, Pareto Frontier, và phân rã thời gian giải.
5. **05 — Robustness Lab (Độ vững Monte Carlo):** Đánh giá 500 kịch bản ngẫu nhiên, kiểm định ghép cặp, và vết hội tụ kỳ vọng.

**Chế độ Hiển thị:**
- **Presentation Mode (Mặc định):** Tối ưu cho hội đồng bảo vệ, tập trung vào trực quan hóa và chỉ số điều hành then chốt.
- **Research Mode:** Mở rộng các bảng kiểm toán chi tiết, thông số mô hình, mã băm kịch bản, và chức năng tải dữ liệu CSV/JSON.

---

## 2. HƯỚNG DẪN KHỞI CHẠY NHANH (1-CLICK STARTUP)

### Dashboard web mới — raw Parquet → dự báo ML → phân cổng

```powershell
.\scripts\start_web_dashboard.ps1 -Setup  # Lần đầu; các lần sau bỏ -Setup
```

Mở **http://127.0.0.1:8000**. Giao diện React theo wireframe, hỗ trợ upload
raw Parquet, chọn ngày ATL, 150/50/20 hoặc số cổng tùy chỉnh, bãi xa hữu hạn,
dự báo arrival/departure thật, Greedy/CP-SAT/Hybrid, Gantt và xuất kết quả.
So sánh bốn thuật toán và Monte Carlo cho file mới có trong các trang thí nghiệm.
Xem [hướng dẫn, schema và giả định](docs/dashboard/WEB_END_TO_END.md).
Dashboard Streamlit bên dưới vẫn được giữ độc lập cho các kịch bản đã đăng ký.

Trên máy mới cần Python 3.11 64-bit và Node.js 22+ (kèm npm). `-Setup` tự tạo
`.venv`, cài thư viện cho cả hai dashboard, kiểm tra model và build giao diện.
Model và dữ liệu demo đã được đóng gói trong Git; không cần tải file riêng.
Sau khi pull bản mới, chạy lại `-Setup` để cập nhật thư viện và frontend.

### Trên Windows (PowerShell / Command Prompt):
```powershell
# 1. Di chuyển vào thư mục dự án
cd D:\Study\Code\Python\Aelous

# 2. Khởi chạy Dashboard
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```
Ứng dụng sẽ tự động mở trên trình duyệt tại địa chỉ: **`http://localhost:8501`**.

### Chạy kịch bản BTS 1.500 lượt đến–đi / 150 cổng

Kịch bản **1.500 lượt đến–đi / 150 cổng** từ BTS ngày 01/07/2026 cũng đã có trên thanh bên:
chọn **ATL 01/07/2026 — 750 đến + 750 đi, 150 cổng**.
Mã kịch bản là `SCEN_2026_07_01_1500_MOVEMENTS_150_GATES`. Gồm 750 lượt đến và 750 lượt đi,
ghép thành 750 lượt quay đầu, dùng đúng 150 cổng hữu hạn. Xem
[mô tả dữ liệu và giả định](docs/dashboard/ATL_20260701_1500_MOVEMENTS_150_GATES.md).

### Chạy kịch bản stress 1.500 chuyến / 50 cổng

Chọn `SCEN_2023_STRESS_1500_50` tại **KỊCH BẢN VẬN HÀNH (ATL)** ở thanh bên,
mở **Gate Operations**, chọn bộ giải rồi nhấn **TỐI ƯU HÓA NGAY (RUN SOLVER)**.
Dashboard nạp trực tiếp `data/simulation/SCEN_2023_STRESS_1500_50.parquet`,
giữ các thời điểm dự báo đã lưu và dựng 50 cổng `G_01`–`G_50` cùng bãi tràn
theo cấu hình hiện có. Kịch bản này được phép giải trực tiếp đến 1.500 chuyến;
ngân sách tìm kiếm CP-SAT mặc định là 30 giây, ngoài thời gian dựng mô hình.
Kết quả được hiển thị trên Gantt và có thể tải xuống bằng CSV/JSON.

---

## 3. KIỂM TRA TRƯỚC KHI BẢO VỆ (PREFLIGHT CHECK)

Trước khi bắt đầu buổi thuyết trình, chạy lệnh kiểm tra tính toàn vẹn của toàn bộ hồ sơ dữ liệu:

```powershell
.\.venv\Scripts\python.exe -c "
from dashboard.services.preflight_service import PreflightService
report = PreflightService().run_preflight_check()
print('Hệ thống sẵn sàng:', report['is_ready'])
print('Số artifact đã kiểm tra:', len(report['artifact_status']))
"
```

---

## 4. CHẠY BỘ KIỂM THỬ TỰ ĐỘNG (AUTOMATED TESTS)

Hệ thống đi kèm bộ kiểm thử tự động toàn diện gồm **212 tests**:

```powershell
# Chạy toàn bộ 123 tests Dashboard
.\.venv\Scripts\python.exe -m pytest tests/dashboard/ -v

# Chạy toàn bộ 89 tests hồi quy Pipeline P07-P09
.\.venv\Scripts\python.exe -m pytest tests/test_native_dual_core_pipeline_p07.py tests/test_ml_research_validation_p08.py tests/test_monte_carlo_robustness_p09.py -v
```

---

## 5. KỊCH BẢN DIỄN TẬP BẢO VỆ (10–12 PHÚT)

Tham khảo chi tiết kịch bản và lời thoại tại:  
👉 [`docs/dashboard/p10_f_acceptance/demo_rehearsal_script.md`](docs/dashboard/p10_f_acceptance/demo_rehearsal_script.md)

1. **Phút 00:00 – 01:30:** Trang 01 — Control Tower: Đặt vấn đề và 4 chỉ số điều hành.
2. **Phút 01:30 – 03:30:** Trang 02 — Flight Intelligence: Độ trễ có dấu và SHAP Waterfall.
3. **Phút 03:30 – 06:00:** Trang 03 — Gate Operations: Biểu đồ Gantt và Live Demo Greedy giải 12 xung đột trong 7.4 ms.
4. **Phút 06:00 – 08:30:** Trang 04 — Optimization Lab: So sánh Pareto 4 thuật toán và giới hạn mở rộng quy mô N=1,500.
5. **Phút 08:30 – 10:30:** Trang 05 — Robustness Lab: Độ vững Monte Carlo qua 500 kịch bản và nhãn Oracle Non-Deployable.
6. **Phút 10:30 – 11:30:** Bật **Research Mode**, mở ngăn **Research Inspector** và trả lời câu hỏi phản biện.

---

## 6. XỬ LÝ SỰ CỐ NHANH (TROUBLESHOOTING)

- **Cổng 8501 bị chiếm:** Khởi chạy với cổng khác:  
  `.\.venv\Scripts\streamlit.exe run dashboard/app.py --server.port 8502`
- **Trình duyệt hiển thị cache cũ:** Nhấn tổ hợp phím `Ctrl + F5` để làm mới hoàn toàn.
- **Màn hình hiển thị cảnh báo stale:** Nhấn nút **🚀 THỰC THI TỐI ƯU CỔNG** trên trang Gate Operations để đồng bộ hóa cấu hình mới nhất.

## Các trang thí nghiệm trên dashboard web

Lịch phân cổng có Gantt, bảng chi tiết và chẩn đoán sức chứa. So sánh thuật toán
chạy Greedy/CP-SAT/SA/Hybrid trên cùng snapshot; Monte Carlo hỗ trợ lịch cố định
và phân cổng lại, chế độ nghiên cứu mặc định 500 kịch bản, dừng và tiếp tục.
Với lần chạy cũ, hãy chạy end-to-end lại một lần để tạo snapshot thí nghiệm.
Xem hướng dẫn đầy đủ tại [WEB_END_TO_END.md](docs/dashboard/WEB_END_TO_END.md).
