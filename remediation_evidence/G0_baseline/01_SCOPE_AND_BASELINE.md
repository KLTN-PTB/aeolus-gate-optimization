# AEOLUS-G0: BÁO CÁO PHẠM VI VÀ THIẾT LẬP BASELINE HỆ THỐNG (SCOPE & BASELINE SPECIFICATION)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin — *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"*  
**Giai đoạn:** AEOLUS-G0 — Baseline, Source Preservation & Rollback Gate  
**Thời điểm thực hiện:** 2026-10-11T16:31:00+07:00  
**Vai trò:** Principal Software Architect, Git Safety Engineer, Scientific Reproducibility Auditor  
**Nguyên tắc G0:** READ-ONLY / NON-DESTRUCTIVE (Tuyệt đối không sửa mã nguồn nghiệp vụ, không commit/push, không can thiệp tệp đã đóng băng).

---

## 1. Nguồn Sự thật Kho lưu trữ (Git Baseline & Repository Truth)

Kiểm toán an toàn Git xác nhận trạng thái thực tế của kho lưu trữ:

* **Đường dẫn Kho lưu trữ (Repository Root):** `D:\Study\Code\Python\Aelous`
* **Nhánh Hiện hành (Current Branch):** `feature/dashboard-and-remediation-p07-p09`
* **Mã băm Commit HEAD (Full HEAD SHA):** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
* **Thông điệp Commit HEAD:** `feat: integrate native dual-core, ML validation, Monte Carlo engine and operational dashboard`
* **Trạng thái Working Tree:**
  * Tệp đã chỉnh sửa (Modified): `0`
  * Tệp đã xóa (Deleted): `0`
  * Tệp trong vùng chờ (Staged): `0`
  * Tệp/Thư mục chưa theo dõi (Untracked): `audit_exports/` (chứa kết quả kiểm toán độc lập phiên trước) và `remediation_evidence/` (thư mục xuất tài liệu G0 hiện tại).
  * **Trạng thái mã nguồn nghiệp vụ:** `100% CLEAN` (Hoàn toàn nguyên vẹn).
* **Nhánh Theo dõi Từ xa (Remote Tracking):** `origin/feature/dashboard-and-remediation-p07-p09`
  * Đồng bộ: Local và Remote hoàn toàn khớp nhau (Up to date).
* **Chính sách `.gitignore` Hiện hành:**
  * Loại trừ an toàn môi trường ảo (`.venv/`, `.venv310_backup_20260826/`).
  * Loại trừ dữ liệu thô và dữ liệu lớn (`/data/`, `*.parquet`, `*.joblib`, `*.pkl`, `results/**`).
  * Loại trừ thư mục sao lưu tạm thời cục bộ (`backup/`).
  * Bảo toàn các manifest tái lập (`!artifacts/manifests/**`).

---

## 2. Môi trường Thực thi và Phiên bản Thư viện (Environment Inventory)

Hệ thống được xác nhận chạy trên môi trường ảo Python cô lập:

* **Hệ điều hành:** Windows 10/11 (Build 19045, AMD64 Architecture).
* **Trình thông dịch Python (Python Executable):** `D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`
* **Phiên bản Python:** Python 3.11.15 (MSC v.1944 64 bit).
* **Bảng Phiên bản Các Thư viện Cốt lõi (Verified Library Versions):**

| Tên Thư viện | Phiên bản Thực tế | Vai trò Hệ thống |
| :--- | :---: | :--- |
| `ortools` | **9.15.6755** | Động cơ tối ưu hóa Google CP-SAT (C++ native solver) |
| `scikit-learn` | **1.9.0** | Pipeline tiền xử lý, Ridge, Linear baselines, Metrics |
| `xgboost` | **3.2.0** | Mô hình tăng cường độ dốc điểm cho Inbound và Outbound |
| `lightgbm` | **4.7.0** | Mô hình cây quyết định bổ trợ |
| `ngboost` | **0.5.11** | Mô hình hồi quy phân phối Student-T tự nhiên (P4 Arrival) |
| `optuna` | **5.0.0** | Khung tối ưu hóa siêu tham số Bayesian TPE |
| `streamlit` | **1.65.0** | Khung ứng dụng Web Dashboard vận hành |
| `plotly` | **7.1.0** | Thư viện trực quan hóa Master Gantt, Pareto và Violin |
| `pandas` | **2.3.3** | Xử lý khung dữ liệu cấu trúc |
| `numpy` | **2.2.6** | Tính toán ma trận và đại số tuyến tính |
| `scipy` | **1.17.1** | Thống kê phân phối xác suất và kiểm định giả thuyết |
| `pyarrow` | **25.0.1** | Đọc/ghi định dạng tệp Parquet phân vùng lớn |
| `torch` | **2.14.0+cpu** | Backend xử lý tensor cho dữ liệu chuỗi bay |
| `shap` | **0.51.0** | Thuật toán giải thích mô hình cây TreeSHAP |
| `pytest` | **9.1.1** | Khung kiểm thử tự động toàn diện |

---

## 3. Cấu trúc và Phạm vi Phân hệ Hệ thống (System Architecture Scope)

Hệ thống `aeolus-gate-optimization` bao gồm 7 phân hệ chính được phân định ranh giới rõ ràng:

1. **Phân hệ Dữ liệu & Rào chắn Thời gian (`src/data/`, `src/features/`):**
   * Quản lý dữ liệu lịch sử BTS 2016–2024.
   * Rào chắn thời gian tại mốc $T-2\text{h}$ (`CRS_DEP_TIME - 2 hours`) đảm bảo nguyên tắc Zero-Leakage: loại trừ 100% cột thời gian thực tế (`ARR_TIME`, `DEP_TIME`, `TAXI_IN`, `TAXI_OUT`, `CANCELLED`...).
2. **Phân hệ Mô hình Học máy (`src/models/`, `src/hpo/`):**
   * Quản lý mô hình điểm (Ridge, RF, XGBoost) và mô hình phân phối xác suất (NGBoost Student-T).
   * Phân tách 3 vai trò: Role A (Point Champion), Role B (Marginal Quantile Champion), Role C (Continuous Simulation Engine).
3. **Phân hệ Luân chuyển Tàu bay (`src/contracts/`, `src/simulation/`):**
   * Định nghĩa giao ước dữ liệu lượt bay (`FlightLeg`, `TurnPair`, `DualAircraftTurn`).
   * Thực thi quy tắc đệm phân cách 15 phút (`buffer_min = 15`) và thời gian quay vòng tối thiểu 45 phút (`min_turnaround_min = 45`).
4. **Phân hệ Bộ giải Phân bổ Cổng đỗ (`src/optimization/`):**
   * Triển khai 4 thuật toán: Deterministic Greedy, Google OR-Tools CP-SAT (Interval Formulation), Simulated Annealing (SA), và Hybrid (CP-SAT + SA).
   * Quản lý sức chứa hữu hạn cổng từ xa ($K = 5$) qua `AddCumulative`.
   * Bộ kiểm chứng độc lập (`verify_hard_constraints_independently`).
5. **Phân hệ Đánh giá Độ bền vững Monte Carlo (`src/simulation/monte_carlo_engine_p09.py`):**
   * 500 kịch bản ngẫu nhiên dưới mô hình phụ thuộc Gaussian Copula ($\rho = 0.45$).
   * 3 chế độ đánh giá: Mode A (Fixed Plan), Mode B (Reactive Recourse), Mode C (Oracle Foresight).
6. **Phân hệ Bảng điều khiển Vận hành (`dashboard/`):**
   * Giao diện Streamlit 5 trang: Control Tower, Flight Intelligence, Gate Operations (Master Gantt), Optimization Lab, Robustness Lab.
   * Hỗ trợ Presentation Mode và Research Mode.
7. **Phân hệ Kiểm thử & Bằng chứng (`tests/`, `artifacts/`):**
   * 1.990 bài kiểm tra thu thập trong toàn repository.
   * Lưu trữ các checkpoint mô hình đóng băng, kết quả benchmark và manifest kiểm toán.

---

## 4. Ranh giới An toàn Bắt buộc cho Giai đoạn G0 (Safety Boundaries)

* Không chỉnh sửa mã nguồn nghiệp vụ trong `src/`, `dashboard/`, `scripts/`, `configs/`.
* Không tạo lại số liệu từ trí nhớ; mọi kết luận phải có bằng chứng từ mã lệnh thực thi.
* Không ghi đè các artifact đã đóng băng trong `artifacts/`.
* Mọi tài liệu và báo cáo chỉ được lưu trong `remediation_evidence/G0_baseline/`.
