# AEOLUS-G10 — DELIVERABLE 06: G7 TEST FAILURES ROOT CAUSE ANALYSIS & REMEDIATION ROADMAP

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Principal QA Architect & Scientific Software Verification Specialist  
**Target Scope:** Forensic Root Cause Analysis of 4 Test Failures in Regression Suite  

---

## 1. TỔNG QUAN TÌNH TRẠNG KIỂM THỬ HỒI QUY TOÀN HỆ THỐNG

Khi thực thi toàn bộ bộ kiểm thử tự động của repository bằng `pytest` trong môi trường runtime sạch:
- **Tổng số ca kiểm thử thu thập (Collected items):** **2.117 tests**
- **Số ca kiểm thử đạt (Passed):** **2.113 tests** ($99,81\%$)
- **Số ca kiểm thử thất bại (Failed):** **4 tests** ($0,19\%$)
- **Số ca kiểm thử remediation mới (G1–G7):** **127 / 127 tests PASSED** ($100,0\%$)

> **PHÁT HIỆN KIỂM TOÁN G10:**  
> Trong Báo cáo G7 (`remediation_evidence/G7_regression/06_GATE_REPORT.md`) và Báo cáo G8 (`remediation_evidence/G8_scientific_release/06_GATE_REPORT.md`), tác giả đã tuyên bố hệ thống đạt chuẩn nghiệm thu kiểm thử hồi quy $100\%$. Tuy nhiên, kết luận này dựa trên việc **chỉ chạy tập con 127 bài test remediation mới** (`scripts/verify_reproducibility_g7.py`), trong khi **4 bài test hồi quy trong bộ test tổng thể vẫn đang thất bại (FAIL)**.

Dưới đây là kết quả điều tra nguyên nhân gốc rễ (Root Cause Analysis) của từng ca thất bại:

---

## 2. ĐIỀU TRA CHI TIẾT TỪNG CA THỬ NGHIỆM THẤT BẠI

### 2.1. Ca kiểm thử 1: `test_registry_integration_retrieval`
- **Vị trí tệp kiểm thử:** `tests/benchmark/test_model_registry.py` (Dòng 25–33)
- **Lệnh thực thi:**
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/benchmark/test_model_registry.py -k "test_registry_integration_retrieval" -v
  ```
- **Thông báo lỗi thực tế:**
  ```text
  AssertionError: assert 'core_departure' in {'auxiliary_departure', 'core_arrival'}
  + where 'core_departure' = ModelSpec(model_id='departure_linear_baseline_v1', ... task='core_departure').task
  ```
- **Phân tích Nguyên nhân Gốc rễ (Root Cause):**
  - Trong giai đoạn đầu của dự án, hệ thống chỉ hỗ trợ hai tác vụ: `CORE_ARRIVAL` và `AUXILIARY_DEPARTURE`.
  - Trong quá trình phát triển Phase P03/P08, tác vụ dự báo chuyến bay đi được nâng cấp thành tác vụ cốt lõi chính thức mang tên `ModelTask.CORE_DEPARTURE.value = 'core_departure'`.
  - Mã nguồn Model Registry (`src/models/registry.py`) đã được cập nhật thành công, nhưng bài test hồi quy `test_model_registry.py` vẫn giữ nguyên câu lệnh assert với tập giá trị tĩnh cũ: `assert spec.task in {ModelTask.CORE_ARRIVAL.value, ModelTask.AUXILIARY_DEPARTURE.value}`.
- **Phân loại:** **Active Test Assertion Drift** (Lỗi lạc hậu của câu lệnh assert trong test, không phải lỗi của logic hệ thống).
- **Mức độ Rủi ro Khoa học:** **RẤT THẤP (ZERO ALGORITHMIC RISK)**. Tác vụ `core_departure` hoàn toàn hợp lệ và hoạt động bình thường.
- **Phương án Khắc phục An toàn (Remediation Proposal):**
  Cập nhật dòng 33 của `tests/benchmark/test_model_registry.py` để bổ sung `ModelTask.CORE_DEPARTURE.value` vào tập hợp các task hợp lệ.

---

### 2.2. Ca kiểm thử 2: `test_guard_v3_verifies_all_frozen_files`
- **Vị trí tệp kiểm thử:** `tests/test_r22_system_freeze_v3.py` (Dòng 87–93)
- **Lệnh thực thi:**
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_r22_system_freeze_v3.py -k "test_guard_v3_verifies_all_frozen_files" -v
  ```
- **Thông báo lỗi thực tế:**
  ```text
  FinalEvaluationGuardV2Error: Integrity hash mismatch in category 'A_data_contracts' for src\data\leakage_rules.py:
  expected a52e264199e953c51a1393842b847c85f907b161363c3915b9ae7658bf40b929,
  got 29521ee18130dd5dc2d95f1cb7fbd1997a8ffb943d81da2b865433df9c5f9cdf.
  Unfrozen source or config changes detected. Evaluation is BLOCKED.
  ```
- **Phân tích Nguyên nhân Gốc rễ (Root Cause):**
  - Tệp `configs/system_freeze_manifest_v2.json` được tạo trong Phase R22 lịch sử nhằm đóng băng toàn bộ mã nguồn hợp đồng dữ liệu.
  - Sau đó, trong quá trình tích hợp kiến trúc Dual-Core (Phase P08 / commit `c95caef5...`), tệp `src/data/leakage_rules.py` đã được cập nhật thêm các quy tắc kiểm tra rò rỉ cho chuyến bay đi (departure leakage rules).
  - Do quy định nghiêm ngặt của Phase R22 cấm chỉnh sửa tệp manifest đóng băng đã ban hành, tệp `system_freeze_manifest_v2.json` không được cập nhật mã băm mới của `src/data/leakage_rules.py`.
- **Phân loại:** **Historical Freeze Manifest Integrity Failure** (Lỗi kiểm tra tính toàn vẹn của manifest đóng băng lịch sử).
- **Mức độ Rủi ro Khoa học:** **TRUNG BÌNH (CONFIGURATION GOVERNANCE RISK)**. Module `leakage_rules.py` hoạt động hoàn toàn chính xác theo logic mới, nhưng cơ chế Guard v2 phát hiện mã nguồn đã bị thay đổi so với mốc lịch sử R22.
- **Phương án Khắc phục An toàn (Remediation Proposal):**
  Không được sửa tệp manifest v2 lịch sử. Trong phiên bản phát hành mới (Release V4.1), cần tạo một `system_freeze_manifest_v4.json` chính thức ghi nhận toàn bộ mã băm hiện tại của hệ thống.

---

### 2.3. Ca kiểm thử 3: `test_guard_v3_authorizes_clean_post_holdout_access`
- **Vị trí tệp kiểm thử:** `tests/test_r22_system_freeze_v3.py` (Dòng 95–101)
- **Thông báo lỗi thực tế:**
  ```text
  FinalEvaluationGuardV2Error: Integrity hash mismatch in category 'A_data_contracts' for src\data\leakage_rules.py
  (Lỗi tương tự Ca 2, phát sinh khi gọi self.verify_freeze_manifest())
  ```
- **Phân tích Nguyên nhân Gốc rễ (Root Cause):**
  - Đây là lỗi dây chuyền (Cascading Failure) trực tiếp từ Ca 2. Khi phương thức `assert_evaluation_authorized` được gọi, bước đầu tiên của nó là kiểm tra tính toàn vẹn của manifest v2 thông qua `verify_freeze_manifest()`, và bị chặn đứng tại tệp `src/data/leakage_rules.py`.
- **Phân loại:** **Cascading Failure from Ca 2**.
- **Phương án Khắc phục:** Tương tự Ca 2.

---

### 2.4. Ca kiểm thử 4: `test_r22_freeze_manifest_integrity`
- **Vị trí tệp kiểm thử:** `tests/test_r27_certification_hardening.py` (Dòng 235–270)
- **Lệnh thực thi:**
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_r27_certification_hardening.py -k "test_r22_freeze_manifest_integrity" -v
  ```
- **Thông báo lỗi thực tế:**
  ```text
  AssertionError: Frozen hash mismatch on src\optimization\domain.py:
  7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580 != 678d841262ee26415789f8a00c86a42374205ada7c420b9a7f2cd6ed808c92d3
  ```
- **Phân tích Nguyên nhân Gốc rễ (Root Cause):**
  - Tác giả khi viết bài test `test_r27_certification_hardening.py` đã nhận thức được việc các tệp hợp đồng đã tiến hóa cho Dual-Core, nên đã tạo một danh sách miễn trừ (whitelist):
    ```python
    dual_core_evolved = {
        "src/data/leakage_rules.py",
        "src/models/interfaces.py",
        "src/models/registry.py",
    }
    ```
  - Tuy nhiên, tác giả **ĐÃ BỎ SÓT tệp `src/optimization/domain.py`** khỏi danh sách `dual_core_evolved`. Trong commit `c95caef5...`, `src/optimization/domain.py` đã được bổ sung thêm các trường dữ liệu `GateResourceType` và các ràng buộc chu trình quay đầu. Do đó, mã băm trên đĩa (`7e210138...`) không khớp với mã băm R22 lịch sử (`678d8412...`).
- **Phân loại:** **Incomplete Test Whitelist Defect** (Lỗi thiếu sót trong danh sách miễn trừ của bài test kiểm toán).
- **Mức độ Rủi ro Khoa học:** **RẤT THẤP**.
- **Phương án Khắc phục An toàn (Remediation Proposal):**
  Bổ sung `"src/optimization/domain.py"` và `"src\\optimization\\domain.py"` vào tập hợp `dual_core_evolved` trong `tests/test_r27_certification_hardening.py`.

---

## 3. KẾT LUẬN & ĐÁNH GIÁ CHẤT LƯỢNG PHẦN MỀM

1. **Tính Đúng đắn Thuật toán:** Cả 4 bài test thất bại đều là các bài test kiểm tra tính bất biến của cấu hình lịch sử (manifest integrity tests) hoặc kiểm tra danh mục task cũ. **Không có bất kỳ lỗi nào liên quan đến sai số thuật toán, tràn bộ nhớ hay xung đột ràng buộc tối ưu.**
2. **Tính Trung thực Báo cáo:** Việc Báo cáo G7/G8 tuyên bố pass 100% bằng cách chỉ chạy 127 bài test mới mà không đề cập đến 4 bài test thất bại này là thiếu minh bạch. Báo cáo nghiệm thu cần ghi nhận rõ ràng: *Hệ thống đạt 2.113 / 2.117 tests (99.81%), 4 bài test còn lại là do độ trễ cập nhật của manifest đóng băng lịch sử.*
