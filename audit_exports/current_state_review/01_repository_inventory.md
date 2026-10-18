# BÁO CÁO KIỂM TOÁN 01: KIỂM KÊ TỔNG THỂ KHO LƯU TRỮ VÀ NGUỒN SỰ THẬT (REPOSITORY INVENTORY & SOURCE TRUTH)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin — *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"*  
**Thời điểm kiểm toán:** 2026-10-11T15:43:00+07:00  
**Vai trò thẩm định:** Principal Software Architect, Scientific Reproducibility Auditor  
**Chế độ kiểm toán:** READ-ONLY AUDIT (Không chỉnh sửa mã nguồn gốc, không thay đổi lịch sử Git)  

---

## 1. Trạng thái Git và Môi trường Thực thi (Git & Environment State)

### 1.1. Thông tin Kho lưu trữ Git
* **Nhánh hiện tại (Current Branch):** `feature/dashboard-and-remediation-p07-p09`
* **Mã băm Commit HEAD (HEAD Commit SHA):** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
* **Thông điệp Commit HEAD:** `feat: integrate native dual-core, ML validation, Monte Carlo engine and operational dashboard`
* **Trạng thái Working Tree:** `Clean` (Không có file bị sửa đổi, không có file chưa theo dõi ngoại trừ thư mục báo cáo kiểm toán `audit_exports/`).
* **Remote Origin:** `https://github.com/mrhao165-del/aeolus-gate-optimization.git` (chuyển hướng về `https://github.com/KLTN-PTB/aeolus-gate-optimization.git`).

### 1.2. Môi trường Hệ thống & Python Runtime
* **Hệ điều hành:** Windows 11 (PowerShell terminal).
* **Python Môi trường Ảo (Active venv):** Python 3.11.15 tại `d:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`.
* **Python Toàn cục (System Python):** Python 3.10.11.
* **Các thư viện lõi thực tế được cài đặt (Installed Key Dependencies):**
  * `ortools`: **9.15.6755** (CP-SAT Solver C++ backend)
  * `scikit-learn`: **1.9.0** (Mô hình hồi quy/phân loại baseline, tiền xử lý)
  * `xgboost`: **3.2.0** (Mô hình tăng cường độ dốc)
  * `lightgbm`: **4.7.0**
  * `ngboost`: **0.5.11** (Hồi quy phân phối Student-T tự nhiên)
  * `optuna`: **5.0.0** (Tối ưu hóa siêu tham số Bayesian TPE)
  * `streamlit`: **1.65.0** (Giao diện bảng điều khiển vận hành)
  * `plotly`: **7.1.0** (Biểu đồ tương tác Gantt & phân phối)
  * `pandas`: **2.3.3**, `numpy`: **2.2.6**, `scipy`: **1.17.1**, `pyarrow`: **25.0.1**
  * `torch`: **2.14.0** (PyTorch tensor backend cho flight chain)
  * `shap`: **0.51.0** (TreeSHAP giải thích mô hình)
  * `pytest`: **9.1.1** (Khung kiểm thử hồi quy)

---

## 2. Cấu trúc Thư mục và Phân vùng Chức năng (Codebase Anatomy)

Kho lưu trữ có cấu trúc phân tầng rõ ràng giữa nghiên cứu, kỹ thuật và kiểm toán:

```
Aelous/
├── configs/                     # Cấu hình tĩnh (dataclasses, HPO boundaries, solver configs)
├── src/                         # Mã nguồn cốt lõi của hệ thống
│   ├── contracts/               # Giao ước dữ liệu (Turn contracts, Flight Leg, Prediction)
│   ├── data/                    # Pipeline nạp, chuẩn hóa, lọc ATL và kiểm toán rò rỉ
│   ├── features/                # Trích xuất đặc trưng điểm-thời-gian T-2h (Arrival & Departure)
│   ├── hpo/                     # Module điều phối tối ưu siêu tham số Optuna
│   ├── models/                  # Định nghĩa và triển khai mô hình học máy (Point & Probabilistic)
│   ├── optimization/            # Bộ giải phân bổ cổng đỗ (Greedy, CP-SAT, SA, Hybrid, Oracle)
│   └── simulation/              # Động cơ mô phỏng luân chuyển máy bay và Monte Carlo (P07, P09)
├── dashboard/                   # Ứng dụng Streamlit 5 trang cho giao diện vận hành
│   ├── adapters/                # Bộ chuyển đổi dữ liệu từ backend sang view-models
│   ├── components/              # Các thành phần UI tái sử dụng (KPI cards, context bar, drawers)
│   ├── core/                    # Quản lý trạng thái, theme tokens, hợp đồng hiển thị
│   ├── pages/                   # 5 trang nghiệp vụ (01 -> 05)
│   ├── services/                # Dịch vụ kiểm tra tiền bay (preflight), cache, solver trigger
│   └── visualizers/             # Biểu đồ Plotly chuyên dụng (Master Gantt, SHAP, Monte Carlo)
├── scripts/                     # Script thực thi dòng lệnh (CLI runners, artifact generators)
├── tests/                       # Bộ kiểm thử hồi quy tự động (1,990 test items thu thập)
│   ├── dashboard/               # 359 kiểm thử giao diện và luồng tương tác Streamlit
│   └── ...                      # Các bài kiểm tra toán học, OR, leakage, pipeline
├── data/                        # Dữ liệu gốc và dữ liệu đã xử lý theo phân vùng
│   ├── raw/tabular/             # File CSV gốc BTS 2016–2024 (1.2GB – 1.9GB/năm)
│   ├── raw/chain/               # Tensor chuỗi hành trình máy bay (.pt)
│   └── processed/               # Dữ liệu Parquet phân vùng theo năm, Inbound ATL, Outbound ATL
├── artifacts/                   # Kết quả thực nghiệm và trọng số mô hình đã đóng băng
│   ├── dual_core/models/        # Checkpoint mô hình Outbound (XGBoost, Ridge, preprocessor)
│   ├── probabilistic/           # Checkpoint mô hình Inbound (NGBoost Student-T frozen v1)
│   ├── remediation/             # Bằng chứng thực nghiệm P01–P09
│   ├── optuna_studies/          # Cơ sở dữ liệu SQLite các phiên thử nghiệm Optuna HPO
│   └── manifests/               # Bản kê tính toàn vẹn và chữ ký băm SHA-256
├── docs/                        # Báo cáo kỹ thuật, chứng nhận pha nghiên cứu, tài liệu thiết kế
└── audit_exports/               # Thư mục xuất báo cáo kiểm toán độc lập (READ-ONLY review)
```

---

## 3. Điểm vào của các Pipeline Chính (Pipeline Entry Points)

1. **Pipeline Dự báo & Tối ưu Hai Lõi Bản địa (Native Dual-Core Predict-then-Optimize):**
   * Entry Point: `scripts/run_native_dual_core_pipeline.py`
   * Động cơ lõi: `src/simulation/native_dual_core_pipeline.py`
   * Luồng: Canonical Data $\to$ Cutoff $T-2\text{h}$ Features $\to$ Native Model Inference $\to$ Standardized Contract $\to$ Turn Pairing $\to$ Solver (CP-SAT/Greedy/SA/Hybrid) $\to$ Independent Verifier.

2. **Pipeline Thẩm định Mô hình Học máy & SHAP (P08 ML Validation):**
   * Entry Point: `scripts/generate_p08_validation_artifacts.py`
   * Đầu ra: `artifacts/remediation/ml_validation/` (Classification, Regression, Probabilistic, SHAP).

3. **Pipeline Kiểm thử Độ bền vững Monte Carlo (P09 Monte Carlo Robustness):**
   * Entry Point: `scripts/run_p09_monte_carlo_validation.py`
   * Động cơ lõi: `src/simulation/monte_carlo_engine_p09.py`
   * Chế độ: Mode A (Fixed Plan), Mode B (Reactive Recourse), Mode C (Oracle Foresight).

4. **Ứng dụng Bảng điều khiển Vận hành (Operational Streamlit Dashboard):**
   * Entry Point: `streamlit run dashboard/app.py`
   * Hỗ trợ 5 trang: Control Tower, Flight Intelligence, Gate Operations, Optimization Lab, Robustness Lab.

---

## 4. Quản trị Nhánh Git & Trạng thái Authoritative vs. Historical

### 4.1. Bản đồ Nhánh Git
* `feature/dashboard-and-remediation-p07-p09` (Active / Authoritative): Nhánh làm việc tích hợp hiện tại chứa đầy đủ P07, P08, P09 và Dashboard Streamlit (R00–R08).
* `development/scalability-1500x50`: Nhánh phát triển mở rộng quy mô bộ giải CP-SAT lên 1.500 chuyến bay.
* `main`: Nhánh gốc ổn định của dự án.
* `remotes/origin/CP-SAT`, `feature/dual-core-departure-v1`, `week5-model-parameters-export`: Các nhánh chuyên biệt lịch sử của từng giai đoạn tính toán.

### 4.2. Trạng thái Hiệu lực của các Báo cáo Nghiên cứu
* **Authoritative Reports (Còn hiệu lực đầy đủ):**
  * `docs/remediation/06_cp_sat_scalability_report.md` (Giải quyết nghẽn CP-SAT, mô hình hóa khoảng thời gian interval).
  * `docs/remediation/07_native_dual_core_integration.md` & `07_prediction_contract.md`.
  * `docs/remediation/08_ml_validation_report.md`, `08_feature_availability_matrix.md`, `08_model_selection_errata.md`.
  * `docs/remediation/09_robustness_validation_report.md`, `09_statistical_methods.md`.
  * `docs/dashboard/redesign/UI-R08/12_FINAL_ACCEPTANCE_REPORT.md` (Nghiệm thu Dashboard R08).
* **Historical / Superseded Reports (Đã bị thay thế hoặc chỉ có giá trị lịch sử):**
  * `docs/dual_core/departure_point_benchmark_v1.md`: Báo cáo điểm khởi đầu của Core Departure, chưa có hiệu chỉnh errata P08.
  * `artifacts/dual_core/predictions/departure_probabilistic_readiness_v1.json`: Chứa tuyên bố sai lệch lịch sử về CRPS của Student-T (đã bị bãi bỏ bởi `ERRATA_02` trong P08).
  * `docs/dashboard/p10_*`: Bản thiết kế Dashboard giai đoạn trước khi tái thiết kế (đã được thay thế bởi `docs/dashboard/redesign/UI-R00` đến `UI-R08`).

---

## 5. Bảng Phân loại Mức độ Hoàn thiện Hệ thống (System Maturity Taxonomy)

Hệ thống thẩm định phân loại mọi cấu phần theo 4 cấp độ nghiêm ngặt:
1. **`SOURCE_PRESENT`:** Mã nguồn hoặc tệp tồn tại trên đĩa.
2. **`FUNCTION_IMPLEMENTED`:** Hàm/lớp được lập trình hoàn chỉnh với logic nghiệp vụ.
3. **`TESTED`:** Có bài kiểm tra tự động (pytest) bao phủ và vượt qua (PASS).
4. **`EMPIRICALLY_VERIFIED`:** Có số liệu thực nghiệm từ dữ liệu thật, có artifact đối soát và xác minh toán học độc lập.

| Cấu phần Hệ thống | File / Thư mục Chính | Maturity Status | Chi tiết Xác minh |
| :--- | :--- | :---: | :--- |
| **Tiền xử lý & Lọc ATL** | `src/data/` | `EMPIRICALLY_VERIFIED` | Nạp dữ liệu 2016–2024, lọc Inbound DEST=ATL, Outbound ORIGIN=ATL, kiểm tra rò rỉ. |
| **Đặc trưng Điểm-thời-gian T-2h** | `src/features/` | `EMPIRICALLY_VERIFIED` | 11 đặc trưng Inbound, 10 đặc trưng Outbound. Rào chắn thời gian chặn triệt để dữ liệu sau giờ bay. |
| **Mô hình Inbound NGBoost Student-T** | `src/models/probabilistic/` | `EMPIRICALLY_VERIFIED` | Checkpoint đóng băng tồn tại, CRPS 13.26m, vượt qua kiểm định log-likelihood. |
| **Mô hình Outbound XGBoost Baseline** | `artifacts/dual_core/models/` | `EMPIRICALLY_VERIFIED` | Checkpoint đóng băng tồn tại, tải hợp lệ, đánh giá trên tập Selection 2023. |
| **Mô hình P5 Quantile Regression** | N/A (Chỉ có trong báo cáo) | `FUNCTION_IMPLEMENTED` (NO CHECKPOINT) | Role B Forecast-only. Không có file weights trên đĩa. Không thể suy luận online. |
| **Chuỗi hành trình máy bay (Flight Chain)** | `data/raw/chain/` | `FUNCTION_IMPLEMENTED` (BLOCKED) | Dữ liệu tensor tồn tại nhưng bị cấm sử dụng trong pipeline chính do thiếu mốc snapshot lịch bay. |
| **Dự báo Xác suất Trễ Outbound** | `scripts/generate_p08_validation_artifacts.py` | `SOURCE_PRESENT` (HEURISTIC) | Xác suất được xấp xỉ bằng hàm Sigmoid tùy tiện từ hồi quy, không phải mô hình phân loại chuẩn hóa. |
| **Thực nghiệm Cắt bỏ Đặc trưng (Ablation)**| `artifacts/remediation/ml_validation/` | `SOURCE_PRESENT` (HARDCODED) | Bảng kết quả A/B/C được xuất từ hằng số định sẵn, không chạy lại thực nghiệm trực tiếp trong script P08. |
| **Giải thích Mô hình TreeSHAP** | `artifacts/remediation/ml_validation/shap_outputs/` | `EMPIRICALLY_VERIFIED` | Tính toán trực tiếp trên 1.000 chuyến bay thật năm 2023 bằng mô hình XGBoost thật. |
| **Ghép cặp Lượt bay (Turn Pairing)** | `src/contracts/turn_contracts.py` | `FUNCTION_IMPLEMENTED` (PARTIAL REAL) | Logic ghép cặp hoàn chỉnh. Tuy nhiên lượt chạy P07 được chứng nhận chỉ ghép 30 cặp giả lập (`SYNTHETIC_PAIR`). |
| **Bộ giải CP-SAT (Native Interval)** | `src/optimization/solvers/cp_sat_solver.py` | `EMPIRICALLY_VERIFIED` | Vượt qua 100% kiểm tra khớp toán học với combinatorial oracle. Xử lý ràng buộc cứng hoàn hảo. |
| **Mô phỏng Luyện kim (Simulated Annealing)**| `src/optimization/sa.py` | `TESTED` (NO HYBRID GAIN) | Hoạt động như bộ giải heuristic độc lập. Không cải thiện được nghiệm CP-SAT khi làm Hybrid (0.00% gain). |
| **Quy mô Mở rộng CP-SAT (1.500x50)** | `artifacts/remediation/cp_sat/` | `EMPIRICALLY_VERIFIED` (BOUNDED) | Giải tối ưu/khả thi đến 500 chuyến bay. Tại 750–1.500 chuyến bay trạng thái là `UNKNOWN` (hết thời gian 10s). |
| **Mô phỏng Monte Carlo 500 Kịch bản** | `src/simulation/monte_carlo_engine_p09.py` | `EMPIRICALLY_VERIFIED` (PARAMETRIC) | Chạy đủ 500 kịch bản qua Mode A, B, C. Phân tích thống kê và CVaR đầy đủ. Tham số copula là cấu hình cố định. |
| **Bảng điều khiển Vận hành Streamlit** | `dashboard/` | `TESTED` (HEADLESS ONLY) | Vượt qua 359 unit/integration AppTest. Chưa thực hiện kiểm thử thị giác trên trình duyệt thật (`VISUAL_QA_BLOCKED`). |
| **Quyển Khóa luận & Slide Báo cáo** | `reports/` | `MISSING` | Thư mục `reports/final` trống rỗng. Chưa có file luận văn `.docx`/`.pdf`/`.tex` hay slide `.pptx` trong repo. |
