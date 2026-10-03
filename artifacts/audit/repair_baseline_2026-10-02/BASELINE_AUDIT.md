# BÁO CÁO KIỂM TOÁN VÀ ĐÓNG BĂNG BASELINE PHỤC VỤ QUÁ TRÌNH REPAIR
## Repository: `D:\Study\Code\Python\Aelous` — Ngày lập: 2026-10-02
**Mục đích**: Bảo toàn tuyệt đối trạng thái hiện tại của kho mã nguồn, lập snapshot kỹ thuật độc lập và phát hiện bất thường (anomalies) trước khi tiến hành repair. Tuyệt đối không thay đổi phương pháp luận, không sửa mô hình, không can thiệp kết quả, không retrain, không truy cập dòng dữ liệu 2024.

---

## 1. Environment (Môi Trường Thực Thi)

| Thuộc tính | Giá trị ghi nhận |
|---|---|
| **Python Version** | `3.11.15 (main, Mar 10 2026, 18:12:25) [MSC v.1944 64 bit (AMD64)]` |
| **Python Executable** | `D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe` |
| **Hệ Điều Hành** | `Windows 10 Pro` (`Windows-10-10.0.19045-SP0`) |
| **Kiến Trúc Phần Cứng** | `AMD64` (x86_64) |
| **Thư Mục Dự Án** | `D:\Study\Code\Python\Aelous` |

### Danh Mục Phiên Bản Thư Viện Cốt Lõi (Package Versions)

| Package | Phiên bản hiện tại | Vai trò trong dự án |
|---|:---:|---|
| **`numpy`** | `2.2.6` | Tính toán số học mảng ma trận, Monte Carlo latency transformations |
| **`pandas`** | `2.3.3` | Xử lý bảng dữ liệu chuyến bay, phân tích chuỗi thời gian |
| **`pyarrow`** | `25.0.1` | Đọc ghi định dạng Parquet theo phân vùng (partitions) |
| **`scikit-learn`** | `1.9.0` | Hồi quy Ridge, Random Forest, HistGradientBoosting, metrics |
| **`xgboost`** | `3.2.0` | Gradient Boosted Trees cho Core Arrival & Auxiliary Departure |
| **`scipy`** | `1.17.1` | Phân phối thống kê giải tích (`scipy.stats.t`, `ndtr`, kiểm định KS) |
| **`optuna`** | `5.0.0` | Công cụ HPO tự động trên tập phát triển 2016–2022 |
| **`ortools`** | `9.15.6755` | Bộ giải lập trình ràng buộc CP-SAT cho Gate Assignment |
| **`pytest`** | `9.1.1` | Khung kiểm thử tự động toàn diện |
| **`joblib`** | `1.5.3` | Nạp và lưu trữ trọng số mô hình đã đóng băng |

*Chi tiết toàn bộ 90 packages được lưu tại:* [`package_versions.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/package_versions.txt)

---

## 2. Git State (Trạng Thái Kho Mã Nguồn)

| Thuộc tính | Trạng thái ghi nhận |
|---|---|
| **Nhánh hiện tại (Branch)** | `week5-model-parameters-export` |
| **Commit HEAD** | `c99b3e84b403527bcfb0f9612a1e2737c9f63701` |
| **Thông điệp Commit** | `feat: export week 5 tuned model parameters and update test baseline` |
| **Tình trạng Working Tree** | `DIRTY` (Có thay đổi chưa commit) |
| **Staged Files** | `0` files |
| **Unstaged Modified Files** | `13` files |
| **Untracked Items** | `206` files / directories |

### Danh sách 13 file Modified Chưa Commit (Unstaged):
1. [`scripts/run_phase_a_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_a_benchmark.py)
2. [`src/data/preprocessing.py`](file:///D:/Study/Code/Python/Aelous/src/data/preprocessing.py)
3. [`src/data/stratified_loader.py`](file:///D:/Study/Code/Python/Aelous/src/data/stratified_loader.py)
4. [`src/evaluation/__init__.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/__init__.py)
5. [`src/features/refactored_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/refactored_features.py)
6. [`src/features/tabular_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py)
7. [`src/models/baselines.py`](file:///D:/Study/Code/Python/Aelous/src/models/baselines.py)
8. [`src/optimization/__init__.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/__init__.py)
9. [`tests/test_holdout_guard.py`](file:///D:/Study/Code/Python/Aelous/tests/test_holdout_guard.py)
10. [`tests/test_phase_a.py`](file:///D:/Study/Code/Python/Aelous/tests/test_phase_a.py)
11. [`tests/test_refactored_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_refactored_pipeline.py)
12. [`tests/test_tabular_features.py`](file:///D:/Study/Code/Python/Aelous/tests/test_tabular_features.py)
13. [`tests/test_temporal_split.py`](file:///D:/Study/Code/Python/Aelous/tests/test_temporal_split.py)

*Chi tiết toàn bộ trạng thái Git và danh sách Untracked được lưu tại:* [`git_state.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/git_state.txt)

---

## 3. Test Baseline (Kết Quả Kiểm Thử Hiện Tại)

- **Lệnh thực thi**:
  ```bash
  .venv\Scripts\python.exe -m pytest tests/ -k "not integration and not slow"
  ```
- **Thời gian thực hiện**: `2026-10-02T01:21:40+07:00` (Thời lượng: `54.99` giây)
- **Thống kê kết quả**:
  - **Mã thoát (Exit Code)**: `0`
  - **Tổng số tests thu thập**: `860`
  - **Số lượng PASS**: `858`
  - **Số lượng Deselected**: `2`
  - **Số lượng FAILED**: `0`
  - **Số lượng Skipped**: `0`
  - **Số lượng Errors**: `0`
  - **Cảnh báo (Warnings)**: `1` ([`tests/test_phase3_pipeline.py:98`](file:///D:/Study/Code/Python/Aelous/tests/test_phase3_pipeline.py#L98) - Cảnh báo độ co rút phần dư trên trễ cực đoan: shrinkage ratio = 0.2770 < 0.30).

> [!WARNING]
> **LƯU Ý PHƯƠNG PHÁP LUẬN BẮT BUỘC**:
> Việc **858/858 tests PASS** chứng minh tính toàn vẹn kỹ thuật phần mềm (không crash, không sai schema, không vỡ contract), nhưng **TUYỆT ĐỐI KHÔNG** đồng nghĩa với việc phương pháp luận nghiên cứu (methodology) là hoàn toàn đúng hoặc không có điểm cần cải thiện. Test baseline chỉ là căn cứ kỹ thuật để đối chiếu trước và sau repair.

*Chi tiết log kiểm thử được lưu tại:* [`test_baseline.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/test_baseline.txt)

---

## 4. Artifact Inventory (Kiểm Kê Kho Sản Phẩm Đã Tạo)

Tổng cộng có **1,180 files** được lưu trữ trong thư mục [`artifacts/`](file:///D:/Study/Code/Python/Aelous/artifacts/), phân bố theo các phân hệ:

1. **`artifacts/manifests/` (23 files)**:
   - Các manifest cấu hình, đặc trưng, temporal splits và freeze manifest:
     - [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/system_freeze_manifest.json) & `.sha256`
     - [`full_system_freeze_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/full_system_freeze_manifest_v1.json)
     - [`academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json)
     - [`selected_system_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/selected_system_manifest_v1.json)
     - [`feature_manifest_arrival_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/feature_manifest_arrival_v1.json)
     - [`seed_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/seed_manifest_v1.json)
2. **`artifacts/model_benchmark/` (36 files)**:
   - Kết quả benchmark các mô hình điểm Core Point, metrics theo fold và file dự báo Out-of-Fold (OOF).
3. **`artifacts/probabilistic_benchmark/` (12 files)**:
   - Kết quả benchmark 5 ứng viên xác suất (P1–P5) trên 4 rolling folds.
4. **`artifacts/stability/` (98 files)**:
   - Dữ liệu chạy kiểm định độ ổn định qua 3 seed (`202601, 202602, 202603`).
5. **`artifacts/downstream_model_comparison/` (4 files)**:
   - Kết quả 84 lượt đánh giá phân bổ cổng đỗ trên 4 kịch bản năm 2023.
6. **`artifacts/monte_carlo_model_comparison/` (6 files)**:
   - Kịch bản mô phỏng Monte Carlo, ma trận Common Latent Variables và log hội tụ.
7. **`artifacts/paired_comparison/` (3 files)**:
   - Bảng chênh lệch ghép cặp và khoảng tin cậy Stationary Bootstrap 95%.
8. **`artifacts/post_holdout/` (9 files)**:
   - Kết quả đánh giá trên năm 2024 post-holdout, bảng so sánh vận hành, metrics hồi quy biên, phân tích rủi ro và failure accounting.
9. **`artifacts/audit/`**:
   - Các biên bản kiểm toán từ Phase 0 đến Phase 10, cùng snapshot baseline hiện tại.

*Chi tiết kiểm kê toàn bộ artifacts được lưu tại:* [`artifact_inventory.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/artifact_inventory.json)

---

## 5. Hash Inventory (Bảng Mã Băm Xác Thực Deterministic)

Đã khởi tạo bảng băm SHA256 cho toàn bộ **135 file mã nguồn** (`src/`, `scripts/`, `tests/`) và **7 file cấu hình** cốt lõi:

### Bảng Mã Băm Cấu Hình và File Cốt Lõi:

| File Đường Dẫn | SHA256 Checksum | Vai trò |
|---|---|---|
| [`artifacts/manifests/system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/system_freeze_manifest.json) | `edca98f0c3c59828b1478d1b3439b357290e2da1cd5b1a0e69d047e3e98acd66` | Manifest đóng băng Phase 10 |
| [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml) | `e5f82b54c7850fd02f5e32782c63928ccc0ba4238fcae57dbcbfdba9f0f0a114` | Registry trạng thái kiến trúc |
| [`configs/academic_model_selection.yaml`](file:///D:/Study/Code/Python/Aelous/configs/academic_model_selection.yaml) | `4289b046873c0bcdc596321aee8d3bb0ce3632c570e0e61fa2539345f09fdbcf` | Giao thức lựa chọn mô hình 2023 |
| [`configs/seed_registry.yaml`](file:///D:/Study/Code/Python/Aelous/configs/seed_registry.yaml) | `798ecc5abfebb1fb11e0ab6db76962f5e9f78bf516d2f5e64edded6d895f0ff9` | Registry seed cố định |
| [`src/optimization/config.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/config.py) | `0630b8febc47312a107810e81297a19eff9def35e2c19f6c55f79ab64d4b97f0` | Trọng số hàm mục tiêu cổng đỗ |
| [`src/features/tabular_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py) | `33d2e08b37058032764cd6968021542aeca3aa68268bf9525bf878e217234418` | Hợp đồng 11 approved predictors |
| [`src/models/registry.py`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py) | `25992d1fb70ff55d120af6f330f536361d4748fdbd57c0d8a1427e53f0da07a1` | Authoritative Model Catalog |
| [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py) | `341a3b60c7a531a51e6517c12518fb87182bc0ea76c7e8dc41c9001b2df39695` | Hợp đồng phân phối xác suất |
| [`src/evaluation/downstream_comparison.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison.py) | `4990ad7cae864db8ab80006c79617417fde1080cc4f502e89df0edefa23efe57` | Engine so sánh vận hành cổng |
| [`src/evaluation/monte_carlo_comparison.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py) | `5092a95589f73497b50a392a90a4518bbc65db14f35f5c9a8677f9bd82bd758f` | Engine mô phỏng Monte Carlo |

*Chi tiết toàn bộ mã băm mã nguồn và cấu hình được lưu tại:*
- [`source_hashes.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/source_hashes.json)
- [`config_hashes.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/config_hashes.json)

---

## 6. Existing Research-State Anomalies (Phát Hiện Bất Thường Hiện Tại)

> [!IMPORTANT]
> **NGUYÊN TẮC KIỂM TOÁN**: Mục này **CHỈ PHÁT HIỆN VÀ GHI NHẬN DỰA TRÊN MÃ NGUỒN**, tuyệt đối không tự ý sửa đổi code trong task này.

### Bảng Phân Loại Bất Thường

| Mã ID | Phân loại | Mức độ | Tóm tắt hiện tượng | File bằng chứng |
|---|---|:---:|---|---|
| **`ANOMALY_01`** | Model Catalog Divergence | **WARNING** | Khác biệt giữa danh mục 7 mô hình Core trong V4 Week 5 và 5 mô hình Point trong Academic Benchmark. `arrival_weighted_ensemble_v1` bị ghi `downstream_eligible: false` trong `current_state.yaml` nhưng thực tế được chạy downstream trong `downstream_comparison.py`. | [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml), [`src/evaluation/downstream_comparison.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison.py) |
| **`ANOMALY_02`** | Model Naming / Heritage | **WARNING** | Mô hình NGBoost Student-T tồn tại dưới 3 định danh khác nhau: `b5_ngboost_student_t` trong `registry.py`, `P4_ngboost_student_t` trong `candidate_interfaces.py`, và `SYS_B5_ngboost_student_t...` trong manifest. | [`src/models/registry.py`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py), [`src/models/probabilistic/candidate_interfaces.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/candidate_interfaces.py) |
| **`ANOMALY_03`** | Manifest Duplication | **WARNING** | Tồn tại đồng thời 2 freeze manifests: `full_system_freeze_manifest_v1.json` (27/09) và `system_freeze_manifest.json` (01/10). Các file code khác nhau trỏ tới các manifest khác nhau (`access_guard.py` trỏ manifest mới, `final_holdout.py` trỏ manifest cũ). | [`artifacts/manifests/full_system_freeze_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/full_system_freeze_manifest_v1.json), [`artifacts/manifests/system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/system_freeze_manifest.json) |
| **`ANOMALY_04`** | Post-Holdout Duplication | **WARNING** | Tồn tại 2 bộ kết quả đánh giá 2024: `final_holdout_2024_evaluation_v1.json` (27/09) và `post_holdout_evaluation_manifest.json` (01/10) với các thiết lập kịch bản và đường dẫn khác nhau. | [`artifacts/manifests/final_holdout_2024_evaluation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/final_holdout_2024_evaluation_v1.json), [`artifacts/post_holdout/post_holdout_evaluation_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout/post_holdout_evaluation_manifest.json) |
| **`ANOMALY_05`** | Data Access Exposure | **BLOCKER** | Có 3 scripts chứa mã nguồn có khả năng quét và đọc dữ liệu mức dòng năm 2024: `final_holdout.py`, `run_probabilistic_stage11_final_holdout.py`, và `run_post_holdout_evaluation.py`. Nếu vô tình kích hoạt trong quá trình repair, dữ liệu 2024 có thể bị đọc. | [`src/models/probabilistic/final_holdout.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/final_holdout.py), [`scripts/run_post_holdout_evaluation.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_post_holdout_evaluation.py) |
| **`ANOMALY_06`** | Heuristic Approximation | **WARNING** | Metric Student-T CRPS trong `final_holdout.py` và `run_post_holdout_evaluation.py` được tính bằng công thức gần đúng heuristic: `np.mean(np.abs(y - mu)) * 0.78` thay vì tích phân giải tích hoặc kernel CRPS chính xác. | [`src/models/probabilistic/final_holdout.py#L338`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/final_holdout.py#L338), [`scripts/run_post_holdout_evaluation.py#L247`](file:///D:/Study/Code/Python/Aelous/scripts/run_post_holdout_evaluation.py#L247) |
| **`ANOMALY_07`** | Selection Source of Truth | **WARNING** | Hai manifest lựa chọn mô hình độc lập tồn tại với nhà vô địch khác nhau: `selected_system_manifest_v1.json` chọn `SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula`, trong khi `academic_model_selection_v1.json` chọn Linear Ridge và P5 Quantile. | [`artifacts/manifests/selected_system_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/selected_system_manifest_v1.json), [`artifacts/manifests/academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json) |
| **`ANOMALY_08`** | Working Tree Dirty | **INFO** | Kho mã nguồn đang ở trạng thái chưa commit 13 file sửa đổi và 206 file untracked. Mọi thay đổi đều được bảo tồn nguyên vẹn. | [`git_state.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/repair_baseline_2026-10-02/git_state.txt) |

---

## 7. 2024 Access Status (Tình Trạng Truy Cập Dữ Liệu Năm 2024)

- **Vị trí vật lý của dữ liệu 2024**:
  - `data/processed/inbound_atl/year=2024/part-00012.parquet`
  - `data/processed/inbound_atl/year=2024/part-00013.parquet`
  - Tổng số chuyến bay ghi nhận: **309,165 chuyến** trên 335 ngày bay trong năm 2024.
- **Trạng thái Access Guard**:
  - `assert_data_access_allowed(2024, "development")` -> BỊ CHẶN TUYỆT ĐỐI (`DataAccessDenied`).
  - `assert_data_access_allowed(2024, "hpo")` -> BỊ CHẶN TUYỆT ĐỐI (`DataAccessDenied`).
  - `assert_data_access_allowed(2024, "final_evaluation")` -> Được cấp phép khi có freeze manifest.
- **Cam kết thực thi trong task này**:
  - **KHÔNG CÓ BẤT KỲ DÒNG DỮ LIỆU NÀO CỦA NĂM 2024 ĐƯỢC TRUY CẬP, BIẾN ĐỔI HOẶC ĐÁNH GIÁ TRONG TASK SNAPSHOT NÀY.**

---

## 8. User Changes Preserved (Bảo Tồn Thay Đổi Của Người Dùng)

- Toàn bộ **13 file modified** của người dùng được giữ nguyên trạng:
  - Tuyệt đối không thực hiện `git checkout -- .`, `git reset`, `git clean`.
  - Không sửa bất kỳ dòng code nào trong `src/data/preprocessing.py`, `src/features/tabular_features.py`, hay các test guards.
- Toàn bộ các file tài liệu và cấu hình chưa commit được bảo toàn 100%.

---

## 9. BLOCKERS Detected (Các Điểm Chặn Nghiên Cứu & Khắc Phục)

1. **`ANOMALY_05` — Khả năng kích hoạt nhầm code đọc 2024**:
   - **Tác động**: Trong quá trình repair tiếp theo, nếu một lệnh kiểm thử hay kịch bản gọi nhầm `final_holdout.py` hoặc `run_post_holdout_evaluation.py`, dữ liệu mức dòng 2024 có thể bị nạp.
   - **Quy tắc chặn (Blocker Rule)**: Bất kỳ tác vụ repair, refactor hay train lại mô hình nào trong các giai đoạn sau **BẮT BUỘC PHẢI KHÓA CHẶT (ISOLATE)** 3 script này, chỉ được phép chạy trên tập 2016–2022 và 2023 development.

---

## 10. Files NOT Modified (Danh Mục Các File Tuyệt Đối Không Can Thiệp)

1. **Dữ liệu thô**: `data/raw/**` (Bất biến).
2. **Dữ liệu chuẩn hóa**: `data/processed/**` (Không ghi đè hoặc sinh lại).
3. **Trọng số mô hình lịch sử**: `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` và `artifacts/models/**`.
4. **Các manifest lịch sử**: `artifacts/manifests/*.json` (Giữ nguyên vẹn mã băm).
5. **Toàn bộ mã nguồn cốt lõi**: `src/**` (Không sửa logic, không sửa contract).
6. **Toàn bộ cấu hình hệ thống**: `configs/**` (Không sửa tham số, không sửa seed).
7. **Toàn bộ các file kiểm thử**: `tests/**` (Không sửa test để ép pass).
