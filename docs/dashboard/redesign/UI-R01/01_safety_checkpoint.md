# UI-R01 — 01. PRE-MODIFICATION SAFETY CHECKPOINT REPORT

## 1. MỤC TIÊU & NGUYÊN TẮC BẢO TOÀN

Báo cáo này ghi nhận toàn bộ hiện trạng kỹ thuật của repository Aeolus Gate Optimization trước khi thực hiện bất kỳ sửa đổi nào trong Phase **UI-R01 v2.0**.
Nguyên tắc bất biến: **Inspect → Verify → Backup Gate → Reproduce → Minimal Fix → Tests → Regression → Report → STOP**.

Tuyệt đối không sửa backend nghiên cứu (`src/models`, `src/optimization`, `src/simulation`), không huấn luyện lại ML, không chạy Optuna, không chạy lại benchmark 1.500 chuyến bay, không chạy lại Monte Carlo 500 nếu chưa cho phép, không thực hiện các lệnh Git phá hủy (`git reset --hard`, `git clean -fd`, `git checkout --`, `git stash`).

---

## 2. HIỆN TRẠNG REPOSITORY & MÔI TRƯỜNG KỸ THUẬT

| Thông số | Giá trị ghi nhận |
| :--- | :--- |
| **Repository Root** | `D:\Study\Code\Python\Aelous` |
| **Current Branch** | `development/scalability-1500x50` |
| **HEAD Commit** | `223f0dd` |
| **Working Tree State** | Dirty (pre-existing untracked files & modified files từ P09.5/P10) |
| **Python Version** | Python 3.11.15 (AMD64) |
| **Virtualenv Path** | `D:\Study\Code\Python\Aelous\.venv` |
| **Operating System** | Windows 10/11 x64 |
| **Streamlit Version** | 1.65.0 |
| **Plotly Version** | 7.1.0 |
| **OR-Tools Version** | 9.15.6755 |
| **Pytest Version** | 9.1.1 |
| **Dashboard Entrypoint** | `dashboard/app.py` |

---

## 3. INVENTORY TẬP TIN THAY ĐỔI & BẢN SAO DỰ PHÒNG (BACKUP GATE)

### 3.1. Danh mục các tập tin thuộc phạm vi sửa đổi UI-R01
Chỉ các tập tin adapter, visualizer, view contracts, validation và dashboard pages sau đây được phép chạm vào:

1. `dashboard/core/contracts.py`
2. `dashboard/core/validation.py`
3. `dashboard/adapters/prediction_adapter.py`
4. `dashboard/adapters/monte_carlo_adapter.py`
5. `dashboard/components/context_bar.py`
6. `dashboard/visualizers/robustness_charts.py`
7. `dashboard/pages/page_01_control_tower.py`
8. `dashboard/pages/page_02_flight_intelligence.py`
9. `dashboard/pages/page_04_optimization_lab.py`
10. `dashboard/pages/page_05_robustness_lab.py`
11. `tests/dashboard/test_ui_r01_data_integrity.py` (tạo mới)

### 3.2. Xác minh Bản sao Dự phòng Độc lập (Backup Verification)
Trước khi chỉnh sửa bất kỳ dòng code nào, toàn bộ thư mục `dashboard/` đã được sao lưu toàn vẹn sang thư mục dự phòng độc lập:
- **Đường dẫn sao lưu:** `D:\Study\Code\Python\Aelous\backup\ui_r01_pre_modification_backup`
- **Số lượng file sao lưu:** 160 files
- **Tổng dung lượng:** 1,492,432 bytes
- **Phương thức:** Copy đệ quy không move/xóa file nguồn.
- **Đối chiếu SHA-256 Checksum trước sửa đổi:**
  - `app.py`: `82f9392e21e90ef811634b3ffaa04ad37ae967a5b3999990ce4a33cb245c127d`
  - `contracts.py`: `77c4495574345377f093a8d9a42533ef333e6ca49ea28e8d89e5772aa796cb19`
  - `prediction_adapter.py`: `73e8ce7db95fec7dbf2be80a6b1626f2982d6da6bf8e1b09b0b4bce0702d1a3a`
  - `monte_carlo_adapter.py`: `a04ae05d7b5f13470ff4db9d5d9c2409895085ae1ea972eebc0c804ee933a362`
  - `context_bar.py`: `9f6760dd186c3d5a49449f8eb785ea8eec612d765893be81a3d922bc300438cf`
  - `robustness_charts.py`: `b25c34cb2c0a905a5a1f2fbb08d1f7e0fc298dae4c76b97b0a7ddbf1e6f3b067`
  - `page_01_control_tower.py`: `c791337b19ce4113e31ae95066c8ef8be0bbcfab9dfc82fa08035bc8ee4f5536`
  - `page_02_flight_intelligence.py`: `ea3a29875b48135e69e71029c716b677a83d47dcfa83ddca2395b28e53997dbb`
  - `page_04_optimization_lab.py`: `87fe7fa4c2da22cba2e6ee547b744d03da0492cb3bc4049fc13c321481d9600e`
  - `page_05_robustness_lab.py`: `b2daeeec62be72c67efaa490eb991583d73507d91cb6840656bc5c2921b06ba5`

Tất cả SHA-256 giữa file nguồn và bản sao dự phòng đã được xác minh trùng khớp 100%.

---

## 4. BASELINE REPRODUCIBILITY & TEST GATES TRƯỚC SỬA ĐỔI

Trước khi sửa đổi:
- **Dashboard Pytest Suite:** 123 tests đã chạy và PASS (100%).
- **P07–P09 Pipeline Pytest Suite:** 89 tests đã chạy và PASS (100%).
- **Tổng số tests baseline:** 212 tests pass.
- **Streamlit App Execution:** Không phát sinh runtime exception trên bất kỳ trang nào.

Cổng an toàn tiền sửa đổi (Pre-Modification Safety Gate) được chứng nhận: **ĐẠT (PASS)**.
