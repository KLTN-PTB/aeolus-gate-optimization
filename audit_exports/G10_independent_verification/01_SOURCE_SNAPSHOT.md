# AEOLUS-G10 — DELIVERABLE 01: EXACT SOURCE CODE SNAPSHOT & ENVIRONMENT STATE

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Independent Principal Software Auditor, ML Scientific Reviewer, Operations Research Verification Engineer  
**Audit Mode:** Strictly Read-Only Audit (No modifications to source, config, tests, or frozen artifacts)  

---

## 1. REPOSITORY IDENTIFICATION & GIT REVISION STATUS

| Property | Value | Audit Verification Status |
| :--- | :--- | :---: |
| **Repository Root** | `D:\Study\Code\Python\Aelous` | **VERIFIED** |
| **Active Git Branch** | `remediation/g7-regression` | **VERIFIED** |
| **HEAD Commit SHA** | `c95caef53808a561b1a7d3a5a09399cc52f754f5` | **VERIFIED (BASELINE G0 SHA)** |
| **Commit Message** | `feat: integrate native dual-core, ML validation, Monte Carlo engine and operational dashboard` | **VERIFIED** |
| **Author Date** | Sun Oct 11 08:34:57 2026 +0700 | **VERIFIED** |
| **Working Tree State** | **DIRTY (9 Modified Tracked Files, 23 Untracked Source/Test/Artifact Paths)** | **AUDITED & DOCUMENTED** |

---

## 2. ANSWERING THE CORE MANDATORY QUESTION

> **Question: Source mới hiện đang nằm ở branch/commit nào?**

### Official Independent Auditor Verdict:
**Mã nguồn mới (kết quả remediation G1–G9) HIỆN KHÔNG NẰM Ở BẤT KỲ COMMIT NÀO TRONG LỊCH SỬ GIT.**
- **HEAD Commit** của nhánh `remediation/g7-regression` hiện tại vẫn đang trỏ chính xác vào commit cơ sở **`c95caef53808a561b1a7d3a5a09399cc52f754f5`** (đây là commit từ trước khi bắt đầu chuỗi nhiệm vụ remediation G1–G9).
- Toàn bộ các cải tiến, sửa lỗi, hợp đồng kiểm toán và thuật toán mới phát triển trong các giai đoạn G1 đến G9 đang tồn tại **thuần túy dưới dạng thay đổi chưa commit trên Working Tree (Uncommitted Working Tree State)**, bao gồm:
  1. **9 tệp mã nguồn được theo dõi đã bị chỉnh sửa (Modified Tracked Files)** nhưng chưa được `git add` hay `git commit`.
  2. **23 tệp/thư mục mã nguồn, kịch bản, bộ kiểm thử và bằng chứng mới (Untracked Files)** nằm rải rác trong cây thư mục làm việc mà chưa được đưa vào kiểm soát phiên bản Git.
- **Rủi ro vận hành nghiêm trọng (Release Identity Failure):** Việc Báo cáo G8 (`remediation_evidence/G8_scientific_release/10_RELEASE_READINESS.md`) tuyên bố phát hành chính thức hệ thống dưới mã commit `c95caef53808a561b1a7d3a5a09399cc52f754f5` là **HOÀN TOÀN SAI LỆCH VỀ QUẢN TRỊ CẤU HÌNH (CONFIGURATION MANAGEMENT MISREPRESENTATION)**. Nếu một kỹ sư khác checkout commit `c95caef5...`, họ sẽ nhận được mã nguồn gốc G0 chứ không có bất kỳ logic nào của G1–G9!
- Để định danh chính xác snapshot mã nguồn hiện tại mà không vi phạm nguyên tắc kiểm toán ("Không commit chỉ để tạo SHA mới"), kiểm toán viên đã thiết lập **Bảng kê băm tập tin (File Manifest with SHA-256)** tại Mục 3 và xuất toàn văn git patch tại `audit_exports/working_tree_git_diff.patch`.

---

## 3. INVENTORY CÁC TỆP MÃ NGUỒN ĐÃ SỬA ĐỔI VÀ CHƯA THEO DÕI

### 3.1. Danh mục 9 tệp theo dõi bị chỉnh sửa trên Working Tree (Modified Tracked Files)

| STT | Đường dẫn Tệp | Kích thước | SHA-256 Hiện tại (Working Tree) | Mô tả Thay đổi Logic |
| :---: | :--- | :---: | :--- | :--- |
| 1 | `dashboard/adapters/export_adapter.py` | 13,8 KB | `82f254e4f2081d69d0739818813470cefe6ff4e86fc70c1ca0db708b1a8d1678` | Bổ sung metadata provenance và chuẩn hóa trường xuất dữ liệu UI |
| 2 | `dashboard/core/config.py` | 8,9 KB | `28e6704169542718e801b7e6ee54dfdb44da75cb57077e600539f1c79a941f17` | Cập nhật cấu hình hiển thị, default scenario và visual flags |
| 3 | `dashboard/core/contracts.py` | 12,4 KB | `049bf328909848e02d6be902b4fcb5df92c90666014b2d354dc59c4033c5e2a2` | Tích hợp các ràng buộc thời gian và schema kiểm toán cho dashboard |
| 4 | `dashboard/services/scenario_service.py` | 15,2 KB | `0b58e77c8e9d3d3a0e6783c8a983e8bc1a43ffb44bc6173003b1e9e7f5263654` | Nạp scenario từ dữ liệu thực tế và hỗ trợ Presentation mode |
| 5 | `scripts/run_native_dual_core_pipeline.py`| 19,4 KB | `b3e34b4198c8942b08a9018485fec1ef1087cfc166cb0131422709e992150fe1` | Runner chính tích hợp Dual-Core ML và native gate allocation |
| 6 | `src/contracts/__init__.py` | 1,2 KB | `25bc4d5b2c7f55171df42f7416973f766348c4cfb57fc6a29be8a8c3e8006ce6` | Xuất khẩu các contracts `provenance` và `temporal` |
| 7 | `src/contracts/turn_contracts.py` | 14,1 KB | `d9e03d35d0859c2941dfaa07a3c7ef2339d22ae2499d217983c2715003c20067` | Định nghĩa hợp đồng quay đầu chu trình tàu bay (turnaround) |
| 8 | `src/data/pairing_validator.py` | 18,7 KB | `ebef4ea28bbf1277a875a6c3f15ec236b223f05db1721590453c076f8ebaa9da` | Bộ quy tắc thẩm định hợp lệ của các cặp chuyến bay |
| 9 | `src/simulation/dual_prediction_turn.py` | 16,3 KB | `7480a4a821e2c9438ea233b86064ae0a30b5034c56894c256220807b1981ff9e` | Tích hợp dự báo trễ đến và trễ đi vào chu trình tàu bay |

### 3.2. Danh mục các tệp mã nguồn và kiểm thử mới (Untracked Files)

| STT | Đường dẫn Tệp Untracked | Phân loại | Kích thước | SHA-256 Checksum |
| :---: | :--- | :---: | :---: | :--- |
| 1 | `src/contracts/provenance.py` | Source / Contract | 14,2 KB | `6a858ffdbb6531c7757ee92a7e4b2d355efba99bfbe01c38e932462e783818e3` |
| 2 | `src/contracts/temporal.py` | Source / Contract | 11,8 KB | `8b19688dfca7ba05e19747209670eb477813a36db577eb05ea6bfd15767fe53a` |
| 3 | `src/data/canonical_time.py` | Source / Data | 10,5 KB | `a8f5c353381a171d43a67d0257361adce6cb70144f84f09d5718dfd7d2948bb6` |
| 4 | `src/data/real_data_loader.py` | Source / Data | 15,3 KB | `4f8812c3f592d3fecbd4bfa6c2b17a14fceee819ff6dcb8c202ba4ff063fbf91` |
| 5 | `src/simulation/monte_carlo_engine_v2.py`| Source / Simulation | 33,1 KB | `2fca3936932b1d0343a4e9b9c97b8ebf4b1e56a4220b22dfa03bf577b819f04d` |
| 6 | `src/simulation/verified_pairing.py` | Source / Simulation | 16,9 KB | `70868f74a0c8702b369dbca0ef6df1c8b36e8fa48cce604db0c0df4a5f6498cf` |
| 7 | `scripts/run_g2_monte_carlo_remediation.py`| Script / Runner | 12,1 KB | `9c8a98b28481ff250aa951759bc430e70ba711099684138e0787e914041d51a6` |
| 8 | `scripts/run_g5_fair_benchmark.py` | Script / Benchmark | 13,2 KB | `4e19b5963f92dfefc64ff3fec02d8495f2694a5009da029b300ea1e0db0bdf81` |
| 9 | `scripts/train_outbound_classifiers_g3.py`| Script / Training | 16,8 KB | `2ba74a382d56c429c3132cf05085e334dfc4a04d5ae8074d6f46990ae09be887` |
| 10 | `scripts/verify_reproducibility_g7.py`| Script / Test | 9,4 KB | `bcf22a559e21711e59c04961b78292f7d54070da820e505870f7cfcbce081d6a` |
| 11 | `tests/test_g1_provenance_and_temporal_contracts.py`| Test Suite G1 | 18,2 KB | `b680782fa3becc0892095f4e66da18f3a3889154f85e49c719e7829b3cf0b89b` |
| 12 | `tests/test_g2_monte_carlo_causality.py`| Test Suite G2 | 27,7 KB | `4a00ec64ef0cfb3f9ff7911664eeae847e13ce6e300d8d2f7823f0331002dfbc` |
| 13 | `tests/test_g3_ml_validation.py` | Test Suite G3 | 21,3 KB | `dc145b5305141b71457df0724810842db6cf47e9282367d30f7895f573bfdbb0` |
| 14 | `tests/test_g4_native_e2e.py` | Test Suite G4 | 22,5 KB | `a9f5d3fe8f35f3b7ce2b834e56578a10738d2aa236f0b4d45d3faad52a8ef4bc` |
| 15 | `tests/test_g5_solver_correctness.py` | Test Suite G5 | 24,1 KB | `041ee2aaefd2f592fe58cf58dc2c54483c66fce4f40f35a0f671239c0e2553cf` |
| 16 | `tests/test_g6_dashboard_integrity.py` | Test Suite G6 | 23,8 KB | `3690d5bcff9638b975e54d3ca34c4f93ee7c0da98e219fb09a1ff088f1ae9fba` |
| 17 | `tests/test_g7_scientific_invariants.py`| Test Suite G7 | 25,6 KB | `c2884aeb7ecf7b49d638ba4c95f191b7d59045dbb69c733355d9921daea5fc8a` |

---

## 4. ĐÁNH GIÁ MÔI TRƯỜNG PHỤ THUỘC & TÍNH KHẢ THI TÁI LẬP

### 4.1. Thông số Môi trường Runtime
- **Hệ điều hành:** Microsoft Windows 11 Enterprise (win32)
- **Phiên bản Python:** Python `3.11.15` (trong môi trường ảo `D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`)
- **Bộ giải Tối ưu hóa:** Google OR-Tools v9.8.3296 (CP-SAT Engine)
- **Thư viện Học máy:** scikit-learn `1.3.2`, XGBoost `2.0.3`, NGBoost `0.4.2`, SciPy `1.11.4`, NumPy `1.26.4`
- **Thư viện Trực quan hóa & Web:** Streamlit `1.31.1`, Plotly `5.18.0`
- **Khung Kiểm thử:** pytest `9.1.1`, pluggy `1.6.0`, anyio `4.15.1`

### 4.2. Cấu hình `.gitignore` và Tệp Bị loại trừ
Tệp `.gitignore` hiện tại bảo vệ đúng các thư mục dữ liệu lớn:
- Bỏ qua `.venv/`, `__pycache__/`, `.pytest_cache/`
- Bỏ qua các tệp raw dataset lớn hàng GB trong `data/raw/`
- Tuy nhiên, tệp `working_tree_git_diff.patch` (63,4 KB) lưu trữ đầy đủ diff của toàn bộ 9 tệp theo dõi bị sửa đổi, cho phép tái lập chính xác 100% trạng thái mã nguồn trên bất kỳ máy trạm nào mà không cần tạo commit giả mạo.

---

## 5. KẾT LUẬN VỀ SOURCE SNAPSHOT

1. Hệ thống đã tích hợp đầy đủ mã nguồn từ G1 đến G9 trong working tree, nhưng **chưa được đóng gói thành Git commit hay Git tag chính thức**.
2. Khi bàn giao cho bên đánh giá độc lập (ChatGPT/Hội đồng), **phải gửi kèm toàn bộ diff patch và cây thư mục untracked**, không được chỉ dẫn mã commit `c95caef53808a561b1a7d3a5a09399cc52f754f5` vì đó chỉ là mã của phiên bản G0 ban đầu.
