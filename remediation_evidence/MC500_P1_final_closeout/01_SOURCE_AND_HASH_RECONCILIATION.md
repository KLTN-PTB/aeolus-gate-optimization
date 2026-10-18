# AEOLUS-MC500-P1: SOURCE IDENTITY & HASH RECONCILIATION AUDIT

**Date:** 2026-10-12  
**Auditor:** Scientific Reproducibility Engineer & Python Integration Verification Engineer  
**Sprint:** AEOLUS-MC500-P1-CLOSEOUT  
**Git Branch:** `remediation/g7-regression`  
**HEAD Commit:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`  
**Status:** **PASSED / AUTHORITATIVE SOURCE RECONCILED & FROZEN**

---

## 1. Executive Summary

Báo cáo kiểm toán độc lập đã phát hiện sự sai lệch giữa mã băm SHA-256 hiển thị trên terminal output, văn bản thuyết minh ban đầu (`01_SAFETY_AND_SOURCE.md`), và manifest kỹ thuật (`09_EVIDENCE_MANIFEST.json`), cũng như việc ba tệp mã nguồn mới quan trọng chưa được theo dõi bởi Git (`untracked`) dẫn đến việc bị thiếu trong `working_tree.patch`.

Kiểm toán viên đã tiến hành:
1. Tính toán lại SHA-256 trực tiếp từ working tree trên đĩa vật lý cho toàn bộ các tệp lõi.
2. Điều tra nguyên nhân gốc rễ (root cause) của hiện tượng mismatch thông qua lịch sử sửa đổi và dấu vết thời gian.
3. Thực hiện sửa lỗi tối thiểu tại `SimulationExecutionLedger.compute_rates()` và bổ sung kiểm thử đối kháng `LEDGER-21` theo quy trình TDD nghiêm ngặt (Failing test trước, PASS sau).
4. Đồng bộ hóa toàn bộ mã băm trên working tree, runner manifest, và pilot artifacts, đảm bảo tính nhất quán 100%.

---

## 2. Authoritative Source Identity & SHA-256 Comparison Matrix

Bảng đối chiếu toàn diện mã băm SHA-256 giữa các nguồn dữ liệu:

| Tệp Mã Nguồn / Cấu hình | SHA-256 (01_SAFETY Draft) | SHA-256 (09_MANIFEST Ban đầu) | SHA-256 (Working Tree Hiện hành sau Sửa) | Kích thước (Bytes) | Git Status |
|---|---|---|---|:---:|:---:|
| `src/simulation/monte_carlo_engine_v2.py` | `6ab89d34346743c7b3967d022a10df7ddba3a79f1dbfb445f14e5ad0808aee0c` | `45abb2d7c938dd2a5b91782bb00d2a6c5202ed6af64339fa136664f31508175f` | `49a78ecbac8313240c54713d7c30e11da9ce1b15243a959e6c314ee045208cf4` | 69,029 | `??` (Untracked) |
| `scripts/run_g2_monte_carlo_remediation.py` | `0d8c01d41c10706692bbdaecf53995f573c5cf0f19504a5bf4955f1ff9791485` | `d2b6d2e154a98a30b6f9f610782af146ee465f7c7a8c9850bf932b3e6834aa3d` | `d2b6d2e154a98a30b6f9f610782af146ee465f7c7a8c9850bf932b3e6834aa3d` | 32,912 | `??` (Untracked) |
| `tests/test_mc500_ledger_runner_integration.py` | `48419ba282fa2f96cf157d079979b9087c24f60faae13554035aa32a26c483d9` | `9b315c536d348a5b2d2ff478d6f3ac418a39aa04d7349629605f1ee7e329f41a` | `b9adebec36364a8eba9a843ec4956f38ea6856da3789bcdba1736b95ac8f5737` | 19,965 | `??` (Untracked) |
| `tests/test_g12b_r1_contract_integrity.py` | `44bf48bbf6d14cca1b41efe86a7fe2b4c3382047b8d8acc9b999f5d57d879c70` | `44bf48bbf6d14cca1b41efe86a7fe2b4c3382047b8d8acc9b999f5d57d879c70` | `44bf48bbf6d14cca1b41efe86a7fe2b4c3382047b8d8acc9b999f5d57d879c70` | 34,183 | `??` (Untracked) |
| `src/optimization/solvers/hybrid_solver.py` | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | 19,049 | Modified (`M`) |
| `src/optimization/sa/annealer.py` | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | 12,933 | Modified (`M`) |
| `src/optimization/solvers/cp_sat_solver.py` | `88c668895b215841e163638083b035abacc68027b0bc7fe70515a38711c7bad0` | `88c668895b215841e163638083b035abacc68027b0bc7fe70515a38711c7bad0` | `88c668895b215841e163638083b035abacc68027b0bc7fe70515a38711c7bad0` | 28,820 | Tracked |
| `src/optimization/solvers/greedy_solver.py` | `db750e91a6ecca0692548018d4e4e18a47c73198fcf73dede2824c8533837abc` | `db750e91a6ecca0692548018d4e4e18a47c73198fcf73dede2824c8533837abc` | `db750e91a6ecca0692548018d4e4e18a47c73198fcf73dede2824c8533837abc` | 10,004 | Tracked |
| `src/optimization/domain.py` | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | 61,431 | Tracked |
| `src/optimization/config.py` | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | 5,953 | Tracked |

---

## 3. Giải thích Nguyên nhân Gốc rễ của Hash Mismatch

Qua phân tích nhật ký thời gian và tệp bằng chứng thực tế:
1. **Lý do sai lệch giữa `01_SAFETY_AND_SOURCE.md` và `09_EVIDENCE_MANIFEST.json`:**
   - Trong quá trình phát triển sprint MC500-P1, kiểm toán viên đã tạo tài liệu an toàn `01_SAFETY_AND_SOURCE.md` vào thời điểm mã nguồn đang ở trạng thái bản thảo trung gian (`6ab89d34...`, `0d8c01d4...`, `48419ba2...`).
   - Sau đó, kiểm toán viên bổ sung thêm các kiểm thử đối kháng và hoàn thiện logic đóng gói khiến mã nguồn thay đổi thành bản ổn định (`45abb2d...`, `d2b6d2e...`, `9b315c5...`).
   - Tệp `09_EVIDENCE_MANIFEST.json` được sinh tự động bằng script sau khi chạy pilot và đóng gói, nên đã ghi nhận đúng mã băm ổn định. Tuy nhiên, bảng Markdown tại `01_SAFETY_AND_SOURCE.md` được soạn thảo thủ công và không được cập nhật lại, dẫn đến tình trạng không thống nhất.

2. **Lý do các tệp lõi bị thiếu trong `working_tree.patch`:**
   - `working_tree.patch` được tạo bằng lệnh tiêu chuẩn `git diff`.
   - Ba tệp `src/simulation/monte_carlo_engine_v2.py`, `scripts/run_g2_monte_carlo_remediation.py`, và `tests/test_mc500_ledger_runner_integration.py` là các tệp mới tạo hoàn toàn trong nhánh khắc phục, thuộc trạng thái `Untracked (??)`.
   - `git diff` mặc định chỉ kết xuất thay đổi của các tệp đã được theo dõi (`Tracked`). Do đó, bản vá cũ không chứa nội dung của ba tệp cốt lõi này.
   - **Biện pháp xử lý triệt để:** Gói kiểm chứng cuối cùng `AEOLUS_MC500_P1_FINAL_REVIEW_PACKAGE.zip` đóng gói trực tiếp mã nguồn đầy đủ của toàn bộ các tệp untracked, không phụ thuộc vào `working_tree.patch` làm phương tiện lưu trữ duy nhất.

---

## 4. Phân tích Thay đổi sau Pilot và Tác động Runtime/Logic

Trong quá trình đóng closeout này, kiểm toán viên đã thực hiện hai thay đổi tối thiểu:
1. **Sửa mẫu số tính tỷ lệ lỗi trong `SimulationExecutionLedger.compute_rates()`:**
   - Thay đổi: Đặt `evaluation_failure_rate.denominator` trỏ tới `acc["n_expected_evaluations"]` (55 slots cho N=5, 220 slots cho N=20) thay vì `acc["n_generated"]` (5 hoặc 20 realizations).
   - Tác động: **Không ảnh hưởng đến runtime hoặc logic tối ưu hóa.** Quá trình sinh kịch bản ngẫu nhiên, các quyết định điều phối cổng, và giá trị hàm mục tiêu không hề bị thay đổi. Chỉ có duy nhất trường `denominator` trong bản tóm tắt json được điều chỉnh đúng với hợp đồng thiết kế.
2. **Bổ sung kiểm thử `LEDGER-21` vào `tests/test_mc500_ledger_runner_integration.py`:**
   - Bổ sung ca kiểm thử tiêm lỗi giả lập 1 slot thất bại trên 55 slot mong đợi để bảo vệ bất biến mẫu số.

Do mã nguồn engine thay đổi hash (từ `45abb2d...` sang `49a78ec...`), toàn bộ hai pilot $N=5$ (cả Run 1 và Replay Run 2) và $N=20$ đã được **tái thực thi (re-run) hoàn toàn** bằng chính mã nguồn working tree cuối cùng. Kết quả tái lập xác nhận:
- Mọi giá trị mục tiêu, trạng thái khả thi, và mã băm kịch bản **trùng khớp 100% bit-for-bit** với kết quả pilot trước đó.
- Mã băm engine trong `simulation_manifest.json` của cả N=5 và N=20 giờ đây **khớp 100%** với `src/simulation/monte_carlo_engine_v2.py` hiện hành.
- Mọi mẫu số hạch toán trong `execution_ledger_summary.json` được định dạng chính xác.
