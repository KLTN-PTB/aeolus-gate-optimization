# AEOLUS-G0: BÁO CÁO THỰC THI THIẾT LẬP BASELINE (IMPLEMENTATION REPORT)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Giai đoạn:** AEOLUS-G0 — Baseline, Source Preservation & Rollback Gate  
**Thời điểm thực hiện:** 2026-10-11T16:32:00+07:00  
**Tuyên bố Trọng tâm:** **GIAI ĐOẠN NÀY LÀ KIỂM KÊ, THIẾT LẬP CHUẨN VÀ BẢO TOÀN NGUYÊN TRẠNG — TUYỆT ĐỐI KHÔNG CHỈNH SỬA MÃ NGUỒN NGHIỆP VỤ HOẶC DỮ LIỆU ĐÓNG BĂNG.**

---

## 1. Mục tiêu và Nguyên tắc Thực thi

Giai đoạn AEOLUS-G0 được kích hoạt nhằm thiết lập nền tảng kỹ thuật và bằng chứng kiểm toán độc lập vững chắc trước khi bước vào bất kỳ hoạt động khắc phục (remediation) nào tiếp theo.

### Nguyên tắc Bất khả xâm phạm:
1. **Zero Source Mutation:** Không có bất kỳ dòng code nào trong `src/`, `dashboard/`, `scripts/`, `tests/`, `configs/` bị thêm, bớt hoặc chỉnh sửa.
2. **Zero History Alteration:** Không có lệnh `git commit`, `git push`, `git reset`, `git rebase` hay `git checkout` nào làm xáo trộn lịch sử Git.
3. **Zero Destructive Action:** Không xóa bất kỳ tệp dữ liệu thô, checkpoint, tệp sao lưu (backup) hay tệp untracked nào ngoài khu vực cấp phép.
4. **Cô lập Tác vụ:** Toàn bộ bằng chứng và tài liệu của G0 chỉ được xuất vào thư mục mới [remediation_evidence/G0_baseline/](file:///D:/Study/Code/Python/Aelous/remediation_evidence/G0_baseline).

---

## 2. Các Hoạt động Kỹ thuật Đã Hoàn tất trong Giai đoạn G0

### 2.1. Thiết lập Git Baseline (Task G0.1)
* **Xác thực HEAD Commit:** Xác nhận commit HEAD là `c95caef53808a561b1a7d3a5a09399cc52f754f5` trên nhánh `feature/dashboard-and-remediation-p07-p09`.
* **Đối soát Working Tree:** Đảm bảo 100% tệp mã nguồn theo dõi đều sạch (`clean`).
* **Kiểm tra Remote:** Xác nhận nhánh cục bộ đã đồng bộ hoàn toàn với `origin/feature/dashboard-and-remediation-p07-p09` trên GitHub.

### 2.2. Kiểm kê Môi trường & Dependencies (Task G0.2)
* Sử dụng chính xác trình thông dịch môi trường ảo `D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe` (Python 3.11.15).
* Xác định phiên bản thực tế của 14 thư viện lõi (`ortools 9.15.6755`, `xgboost 3.2.0`, `ngboost 0.5.11`, `optuna 5.0.0`, `streamlit 1.65.0`...). Không cài đặt hay nâng cấp bất kỳ gói thư viện nào trong G0.

### 2.3. Bảo toàn & Xác minh Checkpoint Mô hình (Task G0.3)
* Đã tính toán mã băm SHA-256 cho **25 artifact trọng tâm** (gồm 5 checkpoint mô hình, các báo cáo kiểm toán P07, P08, P09, CP-SAT).
* Đã kiểm tra nạp thành công 5/5 checkpoint mô hình và tiền xử lý vào bộ nhớ qua `joblib.load()`:
  * `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`
  * `artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib`
  * `artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib`
  * `artifacts/dual_core/models/departure_ridge_baseline_v1.joblib`
  * `artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib`
* Xác minh tính toàn vẹn của các cơ sở dữ liệu Optuna SQLite trong `artifacts/optuna_studies/`.

### 2.4. Thực thi Bộ Kiểm thử Mục tiêu Baseline (Task G0.4)
* Đã chạy lệnh thu thập kiểm thử: Thu thập chính xác **1.990 bài kiểm tra độc lập** toàn kho lưu trữ.
* Đã chạy thực tế **541 bài kiểm tra mục tiêu** không có tính phá hủy (non-destructive):
  * **359 tests** thuộc `tests/dashboard/` $\to$ **100% PASSED** (9.70s).
  * **89 tests** thuộc P07, P08, P09 (`test_native_dual_core_pipeline_p07.py`, `test_ml_research_validation_p08.py`, `test_monte_carlo_robustness_p09.py`) $\to$ **100% PASSED** (6.46s).
  * **93 tests** thuộc Bộ giải và OR (`test_cp_sat_optimization_p06.py`, `test_optimization_domain.py`, `test_greedy_and_adversarial.py`, `test_sa_hybrid_correctness_p03.py`) $\to$ **100% PASSED** (2.23s).
  * **Tổng cộng thực thi thực tế:** **541 tests PASSED**, **0 tests FAILED**.

### 2.5. Hợp nhất Hồ sơ Vấn đề Baseline (Task G0.5)
* Hợp nhất 11 phát hiện kiểm toán kỹ thuật và phương pháp luận vào Sổ đăng ký Vấn đề Chủ đạo (Master Issue Register).

### 2.6. Xây dựng Kế hoạch và Quy trình Rollback (Task G0.6)
* Thiết lập quy trình phục hồi không phá hủy dựa trên mã băm commit nền tảng `c95caef53808a561b1a7d3a5a09399cc52f754f5`.

---

## 3. Xác nhận Tình trạng Mã nguồn Không Bị Đột biến (Attestation of Zero Mutation)

Kiểm toán viên xác nhận:
* **Số tệp mã nguồn nghiệp vụ bị sửa đổi:** `0`
* **Số tệp artifact đóng băng bị ghi đè:** `0`
* **Số commit phát sinh ngoài quy định:** `0`
* Mọi cấu trúc mã nguồn, logic giải thuật và dữ liệu kiểm toán đã được bảo toàn nguyên trạng trước khi chuyển tiếp sang bất kỳ giai đoạn nào tiếp theo.
