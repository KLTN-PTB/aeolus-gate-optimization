# UI-R05: Filter Specification & Dynamic Inventory Counting

## 1. Ngữ Nghĩa Bộ Lọc Nghiêm Ngặt (Strict Filter Semantics - Task R05-B)
Trong các phiên bản trước, việc lọc thường vấp phải lỗi logic do đánh giá chân trị của danh sách rỗng (`if concourse_filter: ...`). Khi người dùng bỏ chọn toàn bộ checkbox, `concourse_filter` mang giá trị `[]`, dẫn đến biểu thức đánh giá thành `False` và hệ thống vô tình hiển thị toàn bộ thay vì không hiển thị gì.

UI-R05 chuẩn hóa ngữ nghĩa như sau:

| Trạng thái Bộ lọc | Kiểu dữ liệu / Giá trị | Hành vi Kỳ vọng |
| :--- | :--- | :--- |
| **Không áp dụng bộ lọc** | `concourse_filter is None` | Hiển thị tất cả chuyến bay/cổng. |
| **Bỏ chọn toàn bộ** | `concourse_filter == []` | Trả về danh sách rỗng (`[]`), không hiển thị chuyến bay nào. |
| **Chọn một hoặc nhiều** | `concourse_filter == ["T", "A"]` | Chỉ hiển thị các chuyến bay thuộc các concourse đã chọn. |
| **Hãng hàng không** | `carrier_filter in (None, "ALL")` | Hiển thị toàn bộ hãng. Nếu chọn cụ thể (ví dụ `"VN"`), chỉ giữ các chuyến bay của `"VN"`. |
| **Loại tài nguyên** | `res_type in (None, "ALL")` | Hiển thị toàn bộ. Nếu chọn cụ thể, chỉ giữ các chuyến bay có `resource_type` tương ứng. |
| **Giao thoa kết hợp** | Nhiều bộ lọc đồng thời | **Phép giao nghiêm ngặt (Strict AND Intersection)**: Chuyến bay phải thỏa mãn đồng thời tất cả tiêu chí. |

## 2. Công Thức Cửa Sổ Thời Gian Nửa Mở (Half-Open Time Intersection)
Cửa sổ thời gian hiển thị trên Gantt được định nghĩa bởi khoảng $[W_{start}, W_{end})$.

Một chuyến bay có khoảng chiếm dụng cổng $[A_{pred}, T_{release})$ được xem là xuất hiện trong cửa sổ quan sát khi và chỉ khi:
$$[A_{pred}, T_{release}) \cap [W_{start}, W_{end}) \neq \emptyset$$

Điều kiện tương đương trong số học:
$$A_{pred} < W_{end} \quad \text{và} \quad T_{release} > W_{start}$$

> [!WARNING]
> Thuật toán cũ kiểm tra ngây thơ $W_{start} \le A_{pred} \le W_{end}$. Điều này bỏ sót nghiêm trọng những chuyến bay hạ cánh trước $W_{start}$ nhưng có thời gian quay vòng kéo dài qua $W_{start}$ (máy bay vẫn đang chiếm dụng cổng trong khung nhìn). Công thức mới bảo đảm mọi chuyến bay có mặt tại cổng trong khung giờ quan sát đều được vẽ đầy đủ.

## 3. Khắc Phục Đếm Cổng Tĩnh (Resolution of ISSUE-R00-11)
### Vấn đề:
Các nhãn checkbox trong `page_03_gate_operations.py` trước đây bị hardcode:
- `Concourse T (10)`
- `Concourse A (15)`
- `Bãi đỗ từ xa (1)`

Khi người dùng chuyển sang kịch bản `SCEN_P07_DUAL_CORE_30` (chỉ có 5 cổng Concourse A) hoặc `SCEN_2023_PEAK_01` (5 cổng Concourse A), giao diện vẫn hiển thị `Concourse A (15)`, làm sai lệch hoàn toàn nhận thức vận hành của người dùng.

### Giải pháp UI-R05:
Đếm động trực tiếp từ tập hợp `gates` của kịch bản đang hoạt động:
```python
count_t = sum(1 for g in gates if _get_gate_concourse(g) == "T")
count_a = sum(1 for g in gates if _get_gate_concourse(g) == "A")
count_remote = sum(1 for g in gates if _get_gate_concourse(g) == "REMOTE")
count_overflow = sum(1 for g in gates if _get_gate_concourse(g) == "OVERFLOW")
count_unknown = sum(1 for g in gates if _get_gate_concourse(g) == "UNKNOWN_GROUP")
```
Nhãn của từng checkbox hiển thị chính xác số lượng thực tế:
- `Concourse T ({count_t})`
- `Concourse A ({count_a})`
- `Bãi đỗ từ xa ({count_remote})` (chỉ hiển thị nếu `count_remote > 0`)
- `Bãi đỗ tràn ({count_overflow})` (chỉ hiển thị nếu `count_overflow > 0`)
