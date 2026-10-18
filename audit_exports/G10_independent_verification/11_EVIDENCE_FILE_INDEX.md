# AEOLUS-G10 — DELIVERABLE 11: EVIDENCE FILE INDEX & PACKAGE INVENTORY

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Independent Principal Software Auditor & Technical Evidence Archivist  
**Target Package:** G10 Independent Verification Deliverables & Audit Package  

---

## 1. MỤC LỤC TOÀN BỘ CÁC BÁO CÁO KIỂM TOÁN G10 TẠI `audit_exports/G10_independent_verification/`

| STT | Tên Tệp Báo cáo G10 | Mô tả Tóm tắt Nội dung | Trạng thái |
| :---: | :--- | :--- | :---: |
| **01** | [`01_SOURCE_SNAPSHOT.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/01_SOURCE_SNAPSHOT.md) | Định danh chính xác vị trí mã nguồn mới: HEAD commit `c95caef...` (G0 baseline) và toàn bộ thay đổi G1–G9 nằm ở working tree chưa commit. Danh mục 9 tệp modified và 23 tệp untracked. | **HOÀN TẤT** |
| **02** | [`02_G3_METRIC_RECOMPUTATION.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/02_G3_METRIC_RECOMPUTATION.md) | Tái tính toán từ dữ liệu dự báo cấp bản ghi (Parquet). Khẳng định ECE thực là 0.01192, prevalence là 20.63%, ROC-AUC là 0.643. Phân tích lỗi tài liệu trong G3-08 và ngụy tạo ROC-AUC 0.795 trong G9. | **HOÀN TẤT** |
| **03** | [`03_G2_CAUSAL_MONTE_CARLO_AUDIT.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/03_G2_CAUSAL_MONTE_CARLO_AUDIT.md) | Thẩm định tính nhân quả Mode B2. Khẳng định thực tế chỉ có 100 kịch bản mới (không có 500 kịch bản). Phơi bày sự sai khác giữa chi phí thật (Mode A: 1606.43, B2: 147.43) và chi phí tự tạo trong G9 (10.0, 12.45). | **HOÀN TẤT** |
| **04** | [`04_G4_REAL_DATA_E2E_AUDIT.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/04_G4_REAL_DATA_E2E_AUDIT.md) | Kiểm tra run manifest pilot 200 chuyến bay Thanksgiving 2023. Khẳng định có đúng 0 verified rotations do thiếu `TAIL_NUM`. Phân biệt 5 cấp độ: real legs, verified turns, inferred turns, synthetic gates. | **HOÀN TẤT** |
| **05** | [`05_G5_HYBRID_DISCREPANCY.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/05_G5_HYBRID_DISCREPANCY.md) | Giải thích tường tận nguyên nhân Hybrid có chi phí cao hơn CP-SAT tại N=200, 300: do cơ chế chia đôi thời gian tính toán (cp_ratio=0.5) làm Stage 1 CP-SAT bị ngắt sớm hoặc phải kích hoạt fallback. | **HOÀN TẤT** |
| **06** | [`06_G7_FAILURE_ROOT_CAUSES.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/06_G7_FAILURE_ROOT_CAUSES.md) | Điều tra nguyên nhân gốc rễ của 4 test failures trong bộ test tổng thể 2.117 tests: xuất phát từ sự sai lệch mã băm so với manifest đóng băng lịch sử R22 và assertion cũ của task registry. | **HOÀN TẤT** |
| **07** | [`07_G8_G9_CLAIM_CONTRADICTIONS.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/07_G8_G9_CLAIM_CONTRADICTIONS.md) | Bảng ma trận đối chiếu toàn diện các điểm mâu thuẫn giữa G8, G9 và artifact thực tế. Phát hiện tráo đổi bảng số liệu Departure sang Inbound. Danh mục các tuyên bố bắt buộc phải loại bỏ khỏi khóa luận. | **HOÀN TẤT** |
| **08** | [`08_CURRENT_RELEASE_READINESS.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/08_CURRENT_RELEASE_READINESS.md) | Đánh giá 6 trụ cột sẵn sàng phát hành. Xác định 4 rào cản ngăn chặn release chính thức: release identity bẩn, 4 test failures, visual QA pending, thiếu định dạng in ấn .docx/.pptx. | **HOÀN TẤT** |
| **09** | [`09_RAW_COMMAND_AND_TEST_LOG.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/09_RAW_COMMAND_AND_TEST_LOG.md) | Toàn văn nhật ký lệnh thực thi, stack trace của pytest, kết quả tính toán Parquet và kiểm tra SHA-256 các checkpoint mô hình. | **HOÀN TẤT** |
| **10** | [`10_FINAL_INDEPENDENT_VERDICT.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/10_FINAL_INDEPENDENT_VERDICT.md) | Kết luận kiểm toán độc lập chính thức. Phân loại P0/P1/P2. Danh mục phân định rõ các số liệu an toàn được phép dùng và các số liệu độc hại bắt buộc phải thanh lọc. | **HOÀN TẤT** |
| **11** | [`11_EVIDENCE_FILE_INDEX.md`](file:///D:/Study/Code/Python/Aelous/audit_exports/G10_independent_verification/11_EVIDENCE_FILE_INDEX.md) | Bản danh mục tổng hợp toàn bộ các tệp bằng chứng và gói tệp tin đính kèm G10. | **TÀI LIỆU NÀY** |

---

## 2. DANH MỤC CÁC TỆP PHỤ TRỢ VÀ TỆP BẰNG CHỨNG ĐÓNG GÓI

1. **`audit_exports/working_tree_git_diff.patch`** (63,4 KB):  
   Toàn văn bản vá git chứa đầy đủ các thay đổi chưa commit trên working tree so với baseline `c95caef...`.
2. **`audit_exports/G10_independent_verification/evidence_manifest.json`**:  
   Tệp kê khai mã băm SHA-256 của toàn bộ 11 báo cáo kiểm toán G10 và các tệp mã nguồn, artifact liên quan.
3. **`audit_exports/G10_independent_verification/AEOLUS_G10_VERIFICATION_PACKAGE.zip`**:  
   Gói nén ZIP độc lập chứa đầy đủ toàn bộ bằng chứng G10 để chuyển giao cho ChatGPT hoặc Hội đồng thẩm định độc lập.
