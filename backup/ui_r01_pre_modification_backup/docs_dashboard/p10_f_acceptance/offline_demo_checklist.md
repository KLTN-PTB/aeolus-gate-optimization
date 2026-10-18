# BẢNG KIỂM TRA ĐÓNG GÓI CHẠY OFFLINE — PHASE P10-F
## Offline Demo Packaging & Preflight Checklist

---

## 1. YÊU CẦU ĐỘC LẬP MẠNG (ZERO INTERNET DEPENDENCY AUDIT)

| Thành phần | Cơ chế Offline | Kiểm tra Xác nhận | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Streamlit Core** | Toàn bộ tệp static JavaScript / CSS được đóng gói nội bộ trong thư viện Python | Chạy trong chế độ Airplane mode | **PASS** |
| **Plotly Visualizers** | Tích hợp sẵn trong Python package, xuất HTML qua iframe cục bộ | Không tải CDN ngoài từ cdn.plot.ly | **PASS** |
| **Google OR-Tools** | Thư viện C++ wrapper compiled tĩnh trong Python virtualenv | Solver CP-SAT chạy 100% offline | **PASS** |
| **Mô hình ML (Inference)** | Tải tệp mô hình đã huấn luyện từ thư mục cục bộ `artifacts/` | Không gọi bất kỳ cloud API nào | **PASS** |
| **Dữ liệu Demo** | Đóng gói sẵn kịch bản chuẩn 120 chuyến bay và các tệp benchmark CSV/Parquet | Không yêu cầu tải dataset BTS raw | **PASS** |

---

## 2. BẢNG KIỂM TRA TRƯỚC KHI KHỞI ĐỘNG (PREFLIGHT CHECKLIST)

Thực hiện lệnh kiểm tra toàn diện trước buổi bảo vệ khóa luận:

```powershell
# Chạy script kiểm tra sự hiện diện của toàn bộ artifact và checkpoint
.\.venv\Scripts\python.exe -c "
from dashboard.services.preflight_service import PreflightService
report = PreflightService().run_preflight_check()
print('Preflight Ready:', report['is_ready'])
print('Checked Artifacts:', len(report['artifact_status']))
"
```

### Danh sách các tệp bắt buộc có mặt trên đĩa:
- [x] `artifacts/remediation/benchmarks/solver_runs.csv`
- [x] `artifacts/remediation/cp_sat/formulation_comparison.json`
- [x] `artifacts/remediation/cp_sat/scalability_results.csv`
- [x] `artifacts/remediation/monte_carlo/statistical_summary.json`
- [x] `artifacts/remediation/monte_carlo/fixed_plan_results.csv`
- [x] `artifacts/remediation/monte_carlo/recourse_results.csv`
- [x] `artifacts/remediation/monte_carlo/oracle_results.csv`
- [x] `artifacts/remediation/ml_validation/regression_metrics.csv`
- [x] `artifacts/remediation/ml_validation/shap_outputs/global_importance.csv`
- [x] `artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json`
- [x] `requirements-dashboard.txt`
- [x] `README_DASHBOARD.md`

---

## 3. HƯỚNG DẪN KHỞI CHẠY OFFLINE TẠI BUỔI BẢO VỆ (1-CLICK STARTUP)

### Trên Windows (PowerShell / Command Prompt):
```powershell
# 1. Di chuyển vào thư mục dự án
cd D:\Study\Code\Python\Aelous

# 2. Khởi chạy ứng dụng Streamlit trên localhost
.\.venv\Scripts\streamlit.exe run dashboard/app.py --server.port 8501 --server.headless true
```
Trình duyệt sẽ tự động mở tại địa chỉ: `http://localhost:8501`.

### Hướng dẫn khôi phục nhanh nếu xảy ra sự cố (Recovery Steps):
1. **Nếu cổng 8501 bị chiếm dụng:** Thêm tham số `--server.port 8502`.
2. **Nếu giao diện bị lưu cache cũ:** Nhấn `Ctrl + F5` trên trình duyệt để tải lại trang trắng.
3. **Nếu terminal báo thiếu gói:** Chạy `pip install -r requirements-dashboard.txt`.
