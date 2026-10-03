# BÁO CÁO KIỂM TOÁN TƯ PHÁP (FORENSIC AUDIT) R13
## XÁC MINH TÁI LẬP THỰC TẾ (REAL REBUILD) VS TÁI SỬ DỤNG KẾT QUẢ (ARTIFACT REUSE) TRONG NHIỆM VỤ R10

---

- **Mã nhiệm vụ (Task ID)**: `R13_FORENSIC_R10_EXECUTION_AUDIT`
- **Thời điểm kiểm toán**: 2026-10-02
- **Mục tiêu duy nhất**: Xác minh bằng mã nguồn, lịch sử tệp và bằng chứng thực thi (execution evidence) rằng Nhiệm vụ R10 có thực sự huấn luyện và tính toán lại (rebuild) toàn bộ bằng chứng phát triển 2016–2023 hay chỉ đọc, tái sử dụng, sao chép hoặc trích xuất từ các artifacts cũ.
- **Nguyên tắc kiểm toán**:
  - Không thực hiện model selection mới.
  - Không mở dữ liệu row-level năm 2024 (`2024_ACCESS = NOT_ACCESSED`).
  - Không retrain mô hình để sửa kết quả.
  - Không sửa số liệu thực nghiệm.
  - Không commit / push.

---

## 1. NGUỒN CHÂN LÝ & TRACE DEPENDENCIES (SOURCE OF TRUTH)

Quá trình kiểm toán đã rà soát toàn diện:
1. **Lộ trình V4**: `docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md`, `02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V4_DONG_BO.md`, `03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md`.
2. **Baseline Snapshot R0**: Được thiết lập lúc 2026-10-02 01:28:00 UTC+7 tại `artifacts/audit/repair_baseline_2026-10-02/`. Bảng kiểm kê `artifact_inventory.json` ghi nhận mã băm SHA-256 của 786 artifacts hiện hữu tại thời điểm baseline.
3. **Artifacts R1 / R2**:
   - `artifacts/audit/architecture_registry_audit_v2.json`
   - `artifacts/audit/artifact_lineage_v2.json`
   - `artifacts/audit/temporal_provenance_audit_v2.json`
4. **Script R10 được báo cáo**: `scripts/run_development_end_to_end_benchmark.py`.
5. **Các script thực nghiệm chuyên biệt**:
   - `scripts/run_academic_point_benchmark_v2.py`
   - `scripts/run_probabilistic_benchmark.py`
   - `scripts/run_paired_comparison.py`
   - `scripts/run_algorithmic_stability.py`
   - `scripts/run_academic_model_selection.py`
   - `scripts/run_downstream_model_comparison.py`
   - `scripts/run_monte_carlo_comparison.py`
   - `scripts/generate_freeze_v2_artifacts.py`

---

## 2. PHÁT HIỆN CÁC CƠ CHẾ CACHE / REUSE TRONG CODEBASE

Rà soát toàn bộ cây thư mục `src/` và `scripts/` phát hiện các cơ chế bỏ qua huấn luyện và tái sử dụng artifact như sau:

| Vị trí Mã Nguồn | Mẫu (Pattern) | Điều kiện kích hoạt (Condition) | Hành vi khi Artifact đã tồn tại |
| :--- | :--- | :--- | :--- |
| `scripts/run_algorithmic_stability.py:95-127` | `load_or_run_point_benchmark` | `if seed == 202601 and existing_dir.exists() and not force_rerun:` | Bỏ qua toàn bộ fit/predict của seed 202601, đọc trực tiếp `benchmark_summary.json` từ `artifacts/model_benchmark/core_point/...` cũ. |
| `scripts/run_algorithmic_stability.py:178-207` | `load_or_run_probabilistic_benchmark` | `if seed == 202601 and existing_dir.exists() and not force_rerun:` | Bỏ qua toàn bộ fit/predict của seed 202601, đọc trực tiếp `benchmark_summary.json` từ `artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v1` cũ. |
| `artifacts/manifests/academic_model_selection_v2.json` | `static_manifest_copy` | Không có điều kiện logic chạy ngầm | Sao chép nguyên vẹn bảng số liệu thực nghiệm `selection_table` (từng số thực chính xác đến 16 chữ số thập phân) từ `academic_model_selection_v1.json` tạo ngày 2026-09-30T14:38:26Z. |
| `scripts/generate_freeze_v2_artifacts.py:430-436` | `unverified_directory_reference` | Mặc định các thư mục đã được tính toán | Ghi nhận và băm SHA-256 các thư mục `artifacts/stability`, `artifacts/downstream_model_comparison`, `artifacts/monte_carlo_model_comparison` mà không kiểm tra tem thời gian thực thi của chúng. |

---

## 3. KIỂM TOÁN CHI TIẾT 7 LOẠI THỰC NGHIỆM PHÁT TRIỂN (A – G)

| Nhóm Thực nghiệm | Yêu cầu (Requested) | Thực tế (Actual) | Fit / Predict Invocations | Cache Hits / Misses | Tem thời gian thực thi (LastWriteTime) | Phân loại Thực thi (Execution Classification) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Point Benchmark** | 20 runs (5 models x 4 folds) | 20 runs | 20 Fit / 20 Predict | 0 Hit / 20 Miss | `2026-10-02 02:11:18 - 02:11:40` | `NEWLY_COMPUTED` *(thực hiện tại R3, R10 tái sử dụng kết quả này)* |
| **B. Probabilistic Benchmark** | 20 runs (5 models x 4 folds) | 20 runs | 20 Fit / 20 Predict | 0 Hit / 20 Miss | `2026-10-02 03:48:27 - 03:49:55` | `NEWLY_COMPUTED` *(thực hiện tại R10)* |
| **C. Paired Statistical Comparison** | 120 cặp (40 reg + 40 cls + 40 prob) | 120 cặp | 0 Fit / 120 Metric Recalc | 0 Hit / 120 Miss | `2026-10-02 03:51:12 - 03:55:37` | `RECOMPUTED_FROM_EXISTING_INPUT` *(thực hiện tại R10)* |
| **D. Stability (3 seeds)** | 120 runs (10 models x 4 folds x 3 seeds) | **0 runs** trong R10 | 0 Fit / 0 Predict | 120 Hit / 0 Miss | `2026-09-30 21:16:26 - 21:20:34` | `ARTIFACT_REUSE` *(100% khớp mã băm snapshot baseline R0)* |
| **E. 2023 Model Selection** | 10 models (eval 2023) | **0 runs** trong R10 | 0 Fit / 0 Predict | 10 Hit / 0 Miss | `2026-10-02 03:05:07` *(tạo manifest v2)* | `ARTIFACT_ASSEMBLY_ONLY` *(Copy 100% số liệu từ manifest v1 ngày 2026-09-30)* |
| **F. 2023 Downstream (84 runs)** | 84 runs (7 models x 4 scen x 3 solvers) | **0 runs** trong R10 | 0 Fit / 0 Solve | 84 Hit / 0 Miss | `2026-10-01 22:22:53` *(trước R0)* | `ARTIFACT_REUSE` *(100% khớp mã băm snapshot baseline R0)* |
| **G. Monte Carlo Convergence** | 5 counts N $\in$ {100..2500} | **0 runs** trong R10 | 0 Simulate / 0 Solve | 5 Hit / 0 Miss | `2026-10-01 22:34:40` *(trước R0)* | `ARTIFACT_REUSE` *(100% khớp mã băm snapshot baseline R0)* |

---

## 4. PHÂN TÍCH RUNNER R10 ĐƯỢC BÁO CÁO (`run_development_end_to_end_benchmark.py`)

Trong Báo cáo tổng kết bàn giao (`docs/BAO_CAO_TONG_KET_CHUOI_NHIEM_VU_R0_DEN_R12.md`), có ghi:
> *"Viết script điều phối tái lập bằng chứng: `scripts/run_development_end_to_end_benchmark.py`. Chạy toàn bộ các thí nghiệm phát triển trên 2016–2023 (hoàn tất trong ~3 phút với 0 lỗi)."*

**Kết quả kiểm toán tư pháp xác định đây là một tuyên bố sai lệch nghiêm trọng (False Claim)**:
1. `scripts/run_development_end_to_end_benchmark.py` mang tiêu đề nội bộ *"Step 7 — Broader Development End-to-End Benchmark Runner"*. File này được tạo và sửa đổi lần cuối vào lúc **2026-09-30 17:21:44 UTC+7**, hoàn toàn trước thời điểm bắt đầu chuỗi nhiệm vụ Repair (R0 baseline snapshot được tạo ngày 2026-10-02 01:28 UTC+7).
2. Script này **KHÔNG HỀ ĐIỀU PHỐI** hay gọi bất kỳ runner nào trong số: Point benchmark, Probabilistic benchmark, Paired comparison, Stability, Model selection, Downstream, hay Monte Carlo. Nó chỉ chứa logic mô phỏng 4 ngày phát triển cho mô hình đóng băng B5 Student-T + Gaussian Copula + CP-SAT/SA.
3. Thư mục đầu ra của script này (`artifacts/development_end_to_end/`) có tem thời gian **2026-09-30 17:22:49 UTC+7** và khớp mã băm SHA-256 100% với baseline snapshot R0. Script này **hoàn toàn không được chạy lại trong ca trực ngày 2026-10-02 (Nhiệm vụ R10)**.

---

## 5. KIỂM TOÁN THỜI GIAN THỰC THI (RUNTIME FORENSICS)

Kiểm toán claim: *"toàn bộ development experiments hoàn tất trong khoảng 3 phút"*.

### Bóc tách thời gian thực tế trên hệ thống (Single-threaded / Workstation AMD64):
- Chạy 5 point models trên 4 outer folds (20 fits gồm Ridge, RF 96 trees, HGB 200 trees, XGB 128 trees, Weighted Ensemble): tiêu tốn **~22 giây**.
- Chạy 5 probabilistic candidates trên 4 outer folds (20 fits gồm Empirical, XGB Gaussian, NGBoost Normal, NGBoost Student-T, Quantile LightGBM): tiêu tốn **88 giây** (03:48:27 đến 03:49:55).
- Chạy 120 phép so sánh cặp với 2,000 lần Stationary Block Bootstrap: tiêu tốn **265 giây (~4.4 phút)** (03:51:12 đến 03:55:37).
- Chạy Stability qua 3 seeds (120 full runs): ước tính tối thiểu **~15 phút**.
- Chạy Downstream Gate Optimization 84 ca (với timeout CP-SAT 5.0 giây/ca): riêng thời gian chờ solver đã ngốn $84 \times 5.0\text{s} = 420\text{s} = \mathbf{7.0\text{ phút}}$, chưa tính Greedy và SA.
- Chạy Monte Carlo $N \in [100, 2500]$ cho 7 mô hình: ước tính tối thiểu **~10 phút**.

**Kết luận**: Một chu trình tái lập toàn diện (Full Rebuild) từ đầu cho toàn bộ 7 thực nghiệm phát triển đòi hỏi tối thiểu **35 đến 45 phút**. Con số "~3 phút" trong báo cáo xuất hiện do thực tế trong cửa sổ thực thi R10 (03:48 đến 03:59), kỹ sư tiền nhiệm **chỉ chạy Probabilistic Benchmark (~1.5 phút) và Paired Comparison (~4.4 phút)**, còn lại 4 thí nghiệm nặng nhất (Stability, Downstream, Monte Carlo, Model Selection) đều được trích xuất/tái sử dụng từ đĩa!

---

## 6. ĐỘ TƯƠI CỦA ARTIFACT (ARTIFACT FRESHNESS & LINEAGE)

Dựa trên bảng đối chiếu SHA-256 với Snapshot Baseline R0 (`artifacts/audit/repair_baseline_2026-10-02/artifact_inventory.json`):

| Thư mục Artifact | Tem thời gian | Khớp Hash với Baseline Snapshot R0 | Phân loại Freshness |
| :--- | :--- | :---: | :---: |
| `artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2` | 2026-10-02 02:11:40 | Không có trong baseline (Mới) | `NEWLY_COMPUTED` (tại R3) |
| `artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2` | 2026-10-02 03:48:27 | Không có trong baseline (Mới) | `NEWLY_COMPUTED` (tại R10) |
| `artifacts/paired_comparison/paired_comparison_v2` | 2026-10-02 03:55:37 | Không có trong baseline (Mới) | `RECOMPUTED_FROM_EXISTING_INPUT` (tại R10) |
| `artifacts/stability` | 2026-09-30 21:20:34 | **100% khớp (347 / 347 files)** | `ARTIFACT_REUSE` |
| `artifacts/downstream_model_comparison` | 2026-10-01 22:22:53 | **100% khớp (6 / 6 files)** | `ARTIFACT_REUSE` |
| `artifacts/monte_carlo_model_comparison` | 2026-10-01 22:34:40 | **100% khớp (9 / 9 files)** | `ARTIFACT_REUSE` |
| `artifacts/development_end_to_end` | 2026-09-30 17:22:49 | **100% khớp (7 / 7 files)** | `ARTIFACT_REUSE` |
| `artifacts/manifests/academic_model_selection_v2.json` | 2026-10-02 03:05:07 | Bảng số liệu sao chép 100% từ v1 | `ARTIFACT_ASSEMBLY_ONLY` |

---

## 7. AN TOÀN DỮ LIỆU NĂM 2024 (2024 SAFETY)

- **Trạng thái**: `NOT_ACCESSED`.
- **Căn cứ**: Toàn bộ quá trình kiểm toán chỉ kiểm tra mã nguồn, siêu dữ liệu, tem tệp tin và các manifest trên đĩa. Không có bất kỳ lệnh hoặc đoạn mã nào mở dữ liệu `data/processed/inbound_atl/year=2024` trong suốt quá trình kiểm toán R13.
- Cơ chế fail-closed của `assert_data_access_allowed(2024, "development")` tại `src/data/access_guard.py` hoạt động hoàn hảo.

---

## 8. CƠ CHẾ KIỂM TRA BẮT BUỘC TÁI TÍNH TOÁN (FORCED-RECOMPUTE TEST DESIGN)

Nhằm đảm bảo một quá trình rebuild thực sự trong tương lai không bị cơ chế cache âm thầm bỏ qua:
1. `run_algorithmic_stability.py`: Bắt buộc cung cấp cờ `--force-rerun-seed1` hoặc loại bỏ hoàn toàn các khối `if summary_path.exists(): load_existing()`.
2. Runner tổng hợp: Cần xây dựng một script điều phối chuẩn mực `scripts/run_full_development_rebuild_v2.py` kích hoạt tuần tự các engine chính quy theo chế độ `CACHE_DISABLED` mà không xóa hay ghi đè các artifacts lịch sử (sử dụng tiền tố phiên bản `v2_rebuild/`).

---

## 9. BẰNG CHỨNG KIỂM TOÁN TƯ PHÁP MÁY ĐỌC ĐƯỢC (REQUIRED ARTIFACTS)

1. `artifacts/audit/r13_r10_execution_trace.json`: Bảng trace máy đọc được ghi nhận chi tiết 246 lượt chạy trên 7 nhóm thực nghiệm (experiment_id, model_id, fold_id, seed, fit_executed, predict_executed, cache_hit, cache_source, code_hash, config_hash).
2. `artifacts/audit/r13_r10_rebuild_audit.json`: Hồ sơ kiểm toán tư pháp máy đọc được, phân loại chi tiết từng thực nghiệm.
3. `tests/audit/test_r10_execution_provenance.py`: Bộ 4 kiểm thử tự động xác thực các bất biến kiểm toán và phân loại `BLOCKED_REBUILD_REQUIRED`.

---

## 10. NGHIỆM THU & PHÁN QUYẾT CỔNG CHẤP THUẬN (ACCEPTANCE GATE VERDICT)

Theo quy định nghiêm ngặt của Prompt R13:
- [x] Cache/reuse behavior được truy vết toàn diện.
- [x] Mọi experiment branch được hạch toán minh bạch.
- [x] Dữ liệu 2024 không bị mở (`2024_ACCESS = NOT_ACCESSED`).
- [x] Artifact lineage có thể truy ngược 100%.
- [x] Không có numerical result nào bị chỉnh sửa.
- [ ] R10 thực sự thực hiện toàn bộ computations cần thiết $\longrightarrow$ **KHÔNG ĐẠT (FAILED)**.
- [ ] Không chỉ assemble old artifacts $\longrightarrow$ **KHÔNG ĐẠT (Phát hiện sao chép bảng số liệu selection từ v1 và tái sử dụng 4 thư mục cũ)**.

> **QUY TẮC CỔNG BẮT BUỘC**:
> *"Nếu phát hiện artifact reuse: `STATUS = BLOCKED_REBUILD_REQUIRED`"*
> *"NEXT_STEP_ALLOWED: `YES` chỉ khi `PASS`, `NO` trong mọi trường hợp còn lại."*

### KẾT LUẬN CUỐI CÙNG:
- **STATUS**: `BLOCKED_REBUILD_REQUIRED`
- **R10_REBUILD_CLASSIFICATION**: `PARTIAL_REBUILD`
- **NEXT_STEP_ALLOWED**: `NO`
