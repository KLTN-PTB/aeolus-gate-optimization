# BÁO CÁO PHẠM VI VÀ BASELINE KỸ THUẬT — AEOLUS-G1

**Giai đoạn:** AEOLUS-G1 — Data Provenance, Temporal Contracts & Evidence Lineage  
**Thời điểm thực hiện:** 2026-10-11  
**Vai trò:** Senior Data Architect, ML Data Leakage Auditor, Backend Contract Engineer, Scientific Reproducibility Reviewer  
**Trạng thái cổng tiên quyết (G0):** PASS (Đã xác minh tại `remediation_evidence/G0_baseline/`)  
**Nhánh Git:** `remediation/g1-data-provenance-and-temporal-contracts`  
**Base Commit SHA:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`  

---

## 1. MỤC TIÊU VÀ PHẠM VI THỰC HIỆN G1

Nhiệm vụ trọng tâm của giai đoạn G1 là chuẩn hóa kiến trúc nguồn dữ liệu (Data Provenance), hợp đồng thông tin thời gian (Temporal Information Contract) với ranh giới dự báo $T - 2\text{h}$, kiểm soát nguồn gốc dự báo và chuỗi bằng chứng (Evidence Lineage) trên toàn bộ hệ thống Aeolus Gate Optimization.

### 1.1. Phạm vi được phép (In-Scope)
1. **Kiểm kê luồng dữ liệu toàn diện (Contract & Pipeline Inventory):**
   - Lập bản đồ hành trình dữ liệu từ Raw Data qua Canonical Parquet, Feature Matrix, Checkpoint Inference, Turn Pairing, Optimization Scenario đến Dashboard và Export.
   - Định danh chính xác nguồn gốc vật lý của từng tập dữ liệu (`REAL_AEOLUS`, `REAL_DERIVED`, `SYNTHETIC`).
2. **Thiết kế và triển khai Provenance Contract đa chiều (`src/contracts/provenance.py`):**
   - 6 chiều độc lập: `data_origin`, `prediction_source`, `pairing_source`, `scenario_generation`, `information_regime`, `evaluation_regime`.
   - Cơ chế fail-closed ngăn chặn suy diễn mặc định dữ liệu thiếu thông tin thành dữ liệu thật.
3. **Thiết lập hợp đồng thông tin thời gian (`src/contracts/temporal.py`):**
   - Ranh giới thông tin dự báo nghiêm ngặt $T - 2\text{h}$ (`CRS_ARR_TIME - 2h` cho Arrival và `CRS_DEP_TIME - 2h` cho Departure).
   - Ràng buộc nhân quả: `feature_available_at <= decision_cutoff`.
   - Chuẩn hóa múi giờ ATL (`America/New_York`) và chuyển đổi UTC đồng nhất.
4. **Chuẩn hóa nhãn và siêu dữ liệu Runtime Dashboard:**
   - Sửa sai lệch nhãn trong `dashboard/core/config.py` (loại bỏ việc gán nhãn `BTS_OTP_2023_CURATED` cho kịch bản sinh từ scalability generator).
   - Truyền tải siêu dữ liệu đầy đủ qua `ScenarioService`, `export_adapter`, và các view models.
5. **Cơ chế Fail-Closed:**
   - Chặn đứng mọi hành vi tự động chuyển sang dữ liệu giả lập (synthetic fallback) khi đang ở chế độ yêu cầu dữ liệu thực (`require_real=True`).
   - Ngăn chặn việc xuất khẩu kết quả kịch bản giả lập dưới danh nghĩa dữ liệu thật.
6. **Xây dựng bộ kiểm thử G1 và chạy hồi quy toàn bộ hệ thống.**

### 1.2. Ranh giới bất khả xâm phạm (Out-of-Scope & Safety Rules)
- **TUYỆT ĐỐI KHÔNG** thay đổi thuật toán dự báo ML (XGBoost, NGBoost, Random Forest, Logistic Regression) hoặc thuật toán tối ưu (Greedy, CP-SAT, SA, Hybrid).
- **TUYỆT ĐỐI KHÔNG** sửa đổi nội dung hoặc checksum của 5 model checkpoints và 25 frozen artifacts đã khóa tại G0.
- **TUYỆT ĐỐI KHÔNG** can thiệp vào dataset gốc trong `data/processed/` và dữ liệu cách ly năm 2024.
- **TUYỆT ĐỐI KHÔNG** thực hiện commit hoặc push lên Git remote khi chưa có phê duyệt từ người dùng.
- **TUYỆT ĐỐI KHÔNG** tự ý chuyển sang giai đoạn G2 trước khi G1 được nghiệm thu hoàn tất.

---

## 2. BASELINE KỸ THUẬT TẠI THỜI ĐIỂM BẮT ĐẦU G1

Trước khi tiến hành sửa đổi, toàn bộ baseline kỹ thuật đã được đối soát với báo cáo G0:

| Hạng mục kiểm toán | Giá trị Baseline G0 | Trạng thái tại khởi điểm G1 |
| :--- | :--- | :--- |
| **Git Working Branch** | `remediation/g1-data-provenance-and-temporal-contracts` | Sạch (clean index, tách biệt từ HEAD G0) |
| **Model Checkpoints** | 5 files (`inbound_arrival`, `outbound_departure`) | 100% khớp SHA-256 G0, nạp thử nghiệm joblib PASS |
| **Frozen Artifacts** | 25 files (`manifests`, `metrics`, `studies`, `results`) | 100% khớp SHA-256 G0 (0 sai lệch) |
| **Target Test Suite** | 541 test items thu thập | 541/541 PASS (359 Dashboard, 89 Remediation, 93 Solvers) |
| **Python Runtime** | Python 3.11.15 (Windows 11 x64, venv) | Hoạt động bình thường |

---

## 3. CÁC LỖ HỔNG VÀ SAI LỆCH PROVENANCE ĐÃ XÁC ĐỊNH CẦN REMEDIATION

Qua khảo sát hiện trạng tại Task G1.1, các vấn đề cốt lõi đã được định vị chính xác:

1. **Sai lệch định danh kịch bản trong Dashboard (`dashboard/core/config.py`):**
   - `SCEN_P09_CANONICAL_120` và `SCEN_2023_PEAK_01` được khai báo trong config với `provenance: "BTS_OTP_2023_CURATED"`.
   - Tuy nhiên, trong `dashboard/services/scenario_service.py`, hai kịch bản này được nạp thông qua hàm `generate_scalability_scenario()`. Hàm này lấy mẫu từ Parquet nhưng gán flight keys giả lập (`S1500-xxxx`) và phân bổ cổng tròn (round-robin nominal gates).
   - **Tác động:** Kịch bản sinh theo phương pháp scalability bị ngộ nhận là lịch bay thực tế được tuyển chọn nguyên bản từ BTS OTP. Cần chuẩn hóa thành `data_origin: REAL_DERIVED`, `scenario_generation: SCALABILITY_GENERATOR`.
2. **Kịch bản P07 Dual-Core Turnaround:**
   - Sử dụng dự báo Native ML (`inbound_arrival`, `outbound_departure`), nhưng quá trình ghép cặp tàu bay (Turn Pairing) được thực hiện trong phiên mô phỏng với `pair_type: SYNTHETIC_PAIR`.
   - **Tác động:** Cần ghi nhận minh bạch `pairing_source: SYNTHETIC_PAIR` thay vì để người dùng nhầm lẫn là vòng quay thực tế (verified rotation).
3. **Thiếu cơ chế Fail-Closed khi xuất dữ liệu:**
   - Trong `export_adapter.py`, các hàm xuất CSV và JSON chấp nhận tham số kịch bản mà không đối chiếu tính hợp lệ của nguồn gốc dữ liệu, tiềm ẩn nguy cơ xuất kịch bản giả lập với nhãn `REAL_AEOLUS`.
4. **Ranh giới thông tin dự báo T-2h chưa được mô hình hóa dạng hợp đồng độc lập:**
   - Ranh giới T-2h chỉ nằm rải rác dưới dạng hằng số `PREDICTION_CUTOFF_HOURS = 2` trong `leakage_rules.py` và kiểm tra cục bộ trong `time_normalization.py`, chưa có module hợp đồng độc lập (`temporal.py`) có khả năng thẩm định thời điểm khả dụng của feature tại runtime.

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT TRONG G1

1. **Task G1.2:** Xây dựng module `src/contracts/provenance.py` với cấu trúc taxonomy 6 chiều và class `EvidenceProvenance`.
2. **Task G1.3:** Xây dựng module `src/contracts/temporal.py` với các bộ guard kiểm tra ranh giới nhân quả và tính an toàn của thuộc tính.
3. **Task G1.4:** Tích hợp provenance vào `dashboard/core/config.py`, `dashboard/core/contracts.py`, `dashboard/services/scenario_service.py`, `dashboard/adapters/export_adapter.py`.
4. **Task G1.5:** Triển khai cơ chế fail-closed trong nạp dữ liệu và xuất khẩu.
5. **Kiểm thử hồi quy:** Xây dựng suite `tests/test_g1_provenance_and_temporal_contracts.py` (15 test cases) và chạy xác thực toàn diện không để xảy ra bất kỳ lỗi hồi quy nào.
