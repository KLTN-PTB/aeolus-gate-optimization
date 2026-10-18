# BÁO CÁO CHI TIẾT THỰC HIỆN TRIỂN KHAI — AEOLUS-G1

**Giai đoạn:** AEOLUS-G1 — Data Provenance, Temporal Contracts & Evidence Lineage  
**Thời điểm hoàn thành:** 2026-10-11  
**Môi trường:** Python 3.11.15, Windows 11 x64  
**Nhánh Git:** `remediation/g1-data-provenance-and-temporal-contracts`  

---

## 1. TỔNG QUAN THAY ĐỔI MÃ NGUỒN

Trong phạm vi G1, các thay đổi mã nguồn được thực hiện theo nguyên tắc **tối thiểu, không xâm lấn, tương thích ngược 100% (zero breaking changes)** và tuân thủ các quy tắc an toàn đã đề ra:

| STT | Đường dẫn tập tin | Loại thay đổi | Mục đích & Trách nhiệm kiến trúc |
| :---: | :--- | :---: | :--- |
| 1 | `src/contracts/provenance.py` | Tạo mới | Định nghĩa hệ thống hợp đồng nguồn dữ liệu 6 chiều, các ngoại lệ kiểm soát dòng dữ liệu và các cấu hình provenance chuẩn tắc. |
| 2 | `src/contracts/temporal.py` | Tạo mới | Định nghĩa hợp đồng thông tin thời gian, ranh giới cắt T-2h, cơ chế phát hiện rò rỉ dữ liệu tương lai và xác thực múi giờ ATL. |
| 3 | `dashboard/core/config.py` | Sửa đổi | Chuẩn hóa nhãn provenance của các kịch bản mẫu, khắc phục tình trạng gán nhãn `BTS_OTP_2023_CURATED` cho kịch bản giả lập. |
| 4 | `dashboard/core/contracts.py` | Sửa đổi | Bổ sung các trường provenance tùy chọn vào `ScenarioContext`, `FlightPredictionView`, `SolverRunView` mà không làm thay đổi các trường hiện có. |
| 5 | `dashboard/services/scenario_service.py` | Sửa đổi | Truyền siêu dữ liệu provenance đa chiều vào `ScenarioContext` và bổ sung cơ chế kiểm soát fail-closed `require_real=True`. |
| 6 | `dashboard/adapters/export_adapter.py` | Sửa đổi | Đưa các trường provenance vào bản xuất manifest JSON/CSV và chặn đứng hành vi xuất kịch bản giả lập dưới danh nghĩa `REAL_AEOLUS`. |
| 7 | `tests/test_g1_provenance_and_temporal_contracts.py` | Tạo mới | Bộ kiểm thử chuyên biệt 15 bài test bao phủ toàn bộ ma trận kiểm toán PROV, TIME, COMPAT, FAILCLOSED. |

---

## 2. CHI TIẾT TỪNG THAY ĐỔI THEO TẬP TIN

### 2.1. Tập tin mới: `src/contracts/provenance.py`
- **Các symbols/classes định nghĩa:**
  - `DataOrigin` (Enum): `REAL_AEOLUS`, `REAL_DERIVED`, `SYNTHETIC`, `UNKNOWN`.
  - `PredictionSource` (Enum): `NATIVE_INFERENCE`, `PRECOMPUTED`, `HEURISTIC`, `NONE`, `UNKNOWN`.
  - `PairingSource` (Enum): `VERIFIED_ROTATION`, `INFERRED`, `SYNTHETIC_PAIR`, `UNPAIRED`, `UNKNOWN`.
  - `ScenarioGeneration` (Enum): `HISTORICAL_REPLAY`, `PARAMETRIC_SIMULATION`, `SCALABILITY_GENERATOR`, `UNKNOWN`.
  - `InformationRegime` (Enum): `PRE_OPERATIONAL`, `ONLINE_RECOURSE`, `FULL_FORESIGHT`, `RETROSPECTIVE`, `UNKNOWN`.
  - `EvaluationRegime` (Enum): `DEVELOPMENT`, `SELECTION_2023`, `POST_HOLDOUT_2024`, `SYNTHETIC_TEST`, `UNKNOWN`.
  - `EvidenceProvenance` (dataclass frozen): Chứa 6 chiều phân loại cùng siêu dữ liệu `source_artifact`, `created_at_utc`, `notes`. Cung cấp các thuộc tính `is_synthetic`, `is_real`, `is_verified` và phương thức kiểm tra fail-closed `validate_fail_closed()`.
  - `DataLineageError`, `SilentFallbackError`, `ProvenanceMismatchError`: Các ngoại lệ đặc thù phục vụ cơ chế fail-closed.
  - Các hằng số chuẩn tắc: `CANONICAL_P09_SCALABILITY_PROVENANCE`, `CANONICAL_P07_DUAL_CORE_PROVENANCE`, `CANONICAL_REAL_AEOLUS_PROVENANCE`.
- **Lý do thực hiện:** Tách bạch rõ ràng nguồn gốc vật lý của bản ghi dữ liệu, nguồn gốc dự báo, phương thức ghép cặp và phương pháp sinh kịch bản. Chấm dứt tình trạng chỉ dùng 1 chuỗi string mơ hồ hoặc 1 enum đơn cấp.
- **Tác động:** Cung cấp nền tảng định danh dữ liệu khoa học cho toàn bộ hệ thống từ backend đến dashboard.
- **Kiểm thử nghiệm thu:** `PROV-01`, `PROV-02`, `PROV-03`, `PROV-04`.

### 2.2. Tập tin mới: `src/contracts/temporal.py`
- **Các symbols/functions định nghĩa:**
  - `TemporalPointType` (Enum): Phân loại các mốc thời gian: sự kiện theo lịch, thời điểm cắt dự báo, thời điểm phát hành dự báo, thời điểm khả dụng của đặc trưng, thời điểm ra quyết định, thời điểm quan trắc thực tế.
  - `ensure_utc_datetime(dt, default_tz)`: Chuyển đổi an toàn naive datetime sang timezone-aware UTC dựa trên múi giờ ATL (`America/New_York`).
  - `calculate_prediction_cutoff_utc(scheduled_event_dt, hours_before=2.0)`: Tính toán ranh giới thông tin dự báo chuẩn tắc $T - 2\text{h}$.
  - `validate_feature_temporal_availability(feature_name, available_at_utc, decision_cutoff_utc, allow_unverified=False)`: Kiểm tra tính khả dụng của feature, chủ động bắn `TemporalLeakageError` nếu $T_{\text{available}} > T_{\text{cutoff}}$ và `TemporalUncertaintyError` nếu thiếu mốc thời gian.
  - `is_column_provably_safe_at_cutoff(col_name, direction)`: Tích hợp với `leakage_rules.py` để phân loại và từ chối các cột thực tế (`DEP_TIME`, `ARR_TIME`, `WHEELS_ON`, `TAXI_IN`, v.v.).
  - `OperationalTemporalProfile` (dataclass frozen): Mô hình hóa dòng thời gian vận hành của chuyến bay và xác thực tính nhân quả qua `validate_causality()`.
- **Lý do thực hiện:** Cụ thể hóa ranh giới thông tin $T - 2\text{h}$ thành hợp đồng kiểm tra tự động tại runtime, ngăn chặn triệt để nguy cơ rò rỉ dữ liệu tương lai.
- **Tác động:** Ngăn chặn các đặc trưng tương lai hoặc thiếu dấu thời gian tham gia vào luồng suy luận.
- **Kiểm thử nghiệm thu:** `TIME-01`, `TIME-02`, `TIME-03`, `TIME-04`, `TIME-05`.

### 2.3. Tập tin sửa đổi: `dashboard/core/config.py`
- **Vị trí thay đổi:** Tuple `registered_scenarios` trong class `DashboardConfig`.
- **Nội dung sửa đổi:**
  - Cập nhật kịch bản `SCEN_P09_CANONICAL_120`:
    - `provenance`: Đổi từ `"BTS_OTP_2023_CURATED"` thành `"SCALABILITY_GENERATOR_BTS_2023_DERIVED"`.
    - Giữ `legacy_provenance: "BTS_OTP_2023_CURATED"` để đảm bảo tương thích ngược.
    - Thêm các trường minh bạch: `data_origin: "REAL_DERIVED"`, `scenario_generation: "SCALABILITY_GENERATOR"`, `pairing_source: "UNPAIRED"`, `is_synthetic: "True"`.
  - Cập nhật kịch bản `SCEN_2023_PEAK_01` tương tự.
  - Cập nhật kịch bản `SCEN_P07_DUAL_CORE_30`:
    - Bổ sung `data_origin: "REAL_DERIVED"`, `scenario_generation: "PARAMETRIC_SIMULATION"`, `pairing_source: "SYNTHETIC_PAIR"`, `prediction_source: "NATIVE_INFERENCE"`, `is_synthetic: "True"`.
- **Lý do thực hiện:** Loại bỏ sai lệch nhãn kịch bản đã phát hiện trong quá trình kiểm toán; phản ánh trung thực bản chất dữ liệu là sinh từ bộ tạo mở rộng (scalability generator) chứ không phải lịch bay nguyên bản.
- **Tác động:** Dashboard hiển thị trung thực xuất xứ kịch bản, không gây hiểu lầm cho hội đồng bảo vệ.
- **Kiểm thử nghiệm thu:** `PROV-02`, `PROV-06`.

### 2.4. Tập tin sửa đổi: `dashboard/core/contracts.py`
- **Vị trí thay đổi:** `ScenarioContext`, `FlightPredictionView`, `SolverRunView`.
- **Nội dung sửa đổi:**
  - `ScenarioContext`: Thêm các trường tùy chọn có giá trị mặc định: `data_origin: str = "UNKNOWN"`, `scenario_generation: str = "UNKNOWN"`, `pairing_source: str = "UNKNOWN"`, `prediction_source: str = "NONE"`, `is_synthetic: bool = False`, `evidence_provenance: Optional[EvidenceProvenance] = None`.
  - `FlightPredictionView`: Thêm `data_origin`, `is_synthetic`, `evidence_provenance`.
  - `SolverRunView`: Thêm `data_origin`, `scenario_generation`, `pairing_source`, `is_synthetic`, `evidence_provenance`.
  - Phương thức `to_dict()` của các dataclass tự động tuần tự hóa các trường provenance mới mà không làm ảnh hưởng đến các trường cũ.
- **Lý do thực hiện:** Truyền tải thông tin provenance qua các tầng UI và export mà không làm gãy các view component hiện tại.
- **Tác động:** Giữ nguyên vẹn khả năng tương thích 100% với 359 dashboard tests hiện có.
- **Kiểm thử nghiệm thu:** `COMPAT-01`, `PROV-06`.

### 2.5. Tập tin sửa đổi: `dashboard/services/scenario_service.py`
- **Vị trí thay đổi:** Hàm `get_scenario_context()` và hàm `load_scenario()`.
- **Nội dung sửa đổi:**
  - `get_scenario_context()`: Nạp đầy đủ thông tin từ `config.registered_scenarios`, khởi tạo đối tượng `EvidenceProvenance` và gán vào `ScenarioContext`.
  - `load_scenario()`: Bổ sung tham số keyword `require_real: bool = False`. Nếu caller yêu cầu `require_real=True`, phương thức kiểm tra trực tiếp cấu hình kịch bản; nếu kịch bản là synthetic (`is_synthetic == True`), lập tức ném ngoại lệ `SilentFallbackError`, ngăn chặn hoàn toàn việc âm thầm nạp kịch bản giả lập.
- **Lý do thực hiện:** Thực thi triệt để nguyên lý Fail-Closed (Finding D3 / Task G1.5).
- **Tác động:** Bảo vệ quy trình nghiên cứu học thuật khỏi việc vô tình sử dụng kịch bản nhân tạo thay cho dữ liệu thực khi đánh giá khoa học.
- **Kiểm thử nghiệm thu:** `FAILCLOSED-01`, `PROV-06`.

### 2.6. Tập tin sửa đổi: `dashboard/adapters/export_adapter.py`
- **Vị trí thay đổi:** Hàm `export_assignments_to_csv()` và `export_run_manifest_to_json()`.
- **Nội dung sửa đổi:**
  - `export_assignments_to_csv()`: Bổ sung tham số `claimed_origin: Optional[str] = None`. Bổ sung thuật toán phát hiện kịch bản giả lập dựa trên prefix `SCEN_` hoặc flight keys `S1500-`, `FL_`. Nếu caller cố tình khai báo `claimed_origin="REAL_AEOLUS"` trên kịch bản giả lập, hàm chủ động ném ngoại lệ `ProvenanceMismatchError`. Bổ sung cột `data_origin` vào tệp CSV xuất khẩu.
  - `export_run_manifest_to_json()`: Bổ sung các trường `data_origin`, `scenario_generation`, `pairing_source`, `is_synthetic` vào JSON manifest.
- **Lý do thực hiện:** Ngăn chặn việc xuất kết quả giả mạo nguồn gốc dữ liệu phục vụ báo cáo hoặc công bố khoa học.
- **Tác động:** Bảo toàn tính toàn vẹn của chuỗi bằng chứng (evidence lineage).
- **Kiểm thử nghiệm thu:** `PROV-05`.

---

## 3. BẢO TOÀN TẬP TIN ĐÃ FREEZE

Trong quá trình triển khai, tập tin `src/contracts/__init__.py` được kiểm tra đối chiếu với `artifacts/manifests/system_freeze_manifest_v3.json`. Vì tập tin này nằm trong danh mục đóng băng v3, nhóm kiểm toán đã hoàn nguyên nguyên vẹn tập tin về trạng thái gốc với đầy đủ hash SHA-256 ban đầu (`77f77d2fb467efda742db035fccc4c8e7567cd4ae382c43253116028b1dc0bd9`). Tất cả các import mới đều được trích xuất trực tiếp từ các module độc lập `src.contracts.provenance` và `src.contracts.temporal`, đảm bảo 0 vi phạm nguyên tắc bất biến (Zero Freeze Mutation).
