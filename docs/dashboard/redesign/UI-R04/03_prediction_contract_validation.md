# AEOLUS DASHBOARD — UI-R04
# PREDICTION DATA CONTRACT & ZERO-LEAKAGE AUDIT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/03_prediction_contract_validation.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** Principal Data Contract Auditor, Research Integrity Specialist  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** VERIFIED & PASSED  

---

## 1. MỤC TIÊU KIỂM ĐỊNH

Hợp đồng dữ liệu dự báo (`FlightPredictionView`) là ranh giới bất biến ngăn chặn sự can thiệp của dữ liệu rò rỉ (Target Leakage) vào các thuật toán tối ưu phân cổng. Trong giai đoạn lập kế hoạch (Pre-departure Gate Assignment Planning), người điều phối và thuật toán tối ưu chỉ được phép quan sát:
1. Thông tin lịch danh định (Scheduled Times, Flight Numbers, Tail/Aircraft Types).
2. Dự báo độ trễ từ mô hình học máy (Predicted Arrival/Departure Delay).
3. Các thông số phân phối và độ bất định của dự báo (Quantiles, P(Delay $\ge$ 15m)).

Mọi nhãn trễ thực tế trong tương lai (Actual Historical Delays) đều bị **nghiêm cấm tuyệt đối**.

---

## 2. ĐẶC TẢ HỢP ĐỒNG `FlightPredictionView`

```python
@dataclass(frozen=True)
class FlightPredictionView:
    flight_id: str
    carrier: str = "N/A"
    origin: str = "N/A"
    destination: str = "N/A"
    sched_arr_time_min: Optional[int] = None
    predicted_arr_delay_min: float = 0.0
    lower_bound_delay_min: Optional[float] = None
    upper_bound_delay_min: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_category: RiskCategory = RiskCategory.LOW
    top_shap_features: Dict[str, float] = field(default_factory=dict)
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    schema_version: str = "1.0"
    flight_direction: str = "ARR"
    prediction_model: Optional[str] = None
    prediction_cutoff_utc: Optional[str] = None
    probability_delay_15: Optional[float] = None
    predictive_quantiles: Dict[str, float] = field(default_factory=dict)
    scheduled_time_min: Optional[int] = None
    predicted_time_min: Optional[int] = None
```

### Các Thuộc tính Mở rộng trong UI-R04:
- `flight_direction`: Chuỗi định danh `"ARR"` (Chuyến bay đến) hoặc `"DEP"` (Chuyến bay đi).
- `prediction_model`: Tên mô hình tạo ra dự báo (vd: `b5_ngboost_student_t` hoặc `departure_certified_point_v1`).
- `prediction_cutoff_utc`: Mốc thời gian cutoff đặc trưng tính toán để chứng minh không sử dụng dữ liệu sau giờ cất/hạ cánh.
- `probability_delay_15`: Xác suất xảy ra độ trễ $\ge 15$ phút, thuộc khoảng $[0.0, 1.0]$.
- `predictive_quantiles`: Phân vị dự báo từ phân phối xác suất ($q_{10}, q_{50}, q_{90}$).
- `effective_scheduled_time_min` & `effective_predicted_time_min`: Properties an toàn hỗ trợ tính toán thời gian độc lập cho cả chuyến đến và chuyến đi.

---

## 3. AUDIT RÒ RỈ DỮ LIỆU (ZERO DATA LEAKAGE AUDIT)

Hệ thống bảo vệ của `ScientificValidator.check_prediction_data_leakage()` kiểm soát nghiêm ngặt danh sách các cột bị cấm:
```python
FORBIDDEN_ACTUAL_DELAY_COLUMNS = {
    "actual_delay_min",
    "actual_arr_delay",
    "actual_dep_delay",
    "arr_delay",
    "dep_delay",
    "arr_delay_new",
    "dep_delay_new",
    "delay_actual",
    "actual_delay",
    "target_actual",
}
```

### Kết quả Kiểm định Thực tế:
- Khi đưa vào một dòng dữ liệu có chứa cột `actual_delay_min`, hệ thống lập tức ném ra ngoại lệ `DataLeakageError` và dừng thực thi (`test_r04_t16 PASSED`).
- Toàn bộ 60 bản ghi dự báo trong file `artifacts/remediation/native_dual_core/predictions_sample.csv` đã được quét tự động: **0 cột bị cấm xuất hiện trong bảng hiển thị**.

---

## 4. KẾT LUẬN & ĐÁNH GIÁ CHẤP THUẬN

Hợp đồng dữ liệu `FlightPredictionView` đã hoàn thành mục tiêu mở rộng cho kiến trúc Dual-Core ML mà vẫn bảo toàn 100% khả năng tương thích ngược với các test kiểm thử của UI-R01 và UI-R02.
