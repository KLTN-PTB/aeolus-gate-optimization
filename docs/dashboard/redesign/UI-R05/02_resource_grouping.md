# UI-R05: Resource Grouping & Resolution of ISSUE-R00-07

## 1. Vấn đề Nguyên phát (Root Cause Analysis: ISSUE-R00-07)
Trong phiên bản tiền đề (baseline audit UI-R00), hàm trích xuất concourse trong `assignment_adapter.py` và `gantt_chart.py` xử lý như sau:
```python
clean_gate = gate_id.replace("GATE_", "")
if clean_gate.startswith("REMOTE"):
    concourse = "REMOTE"
elif clean_gate.startswith("T"):
    concourse = "T"
elif clean_gate.startswith("A"):
    concourse = "A"
```
Khi kịch bản chứa vị trí đỗ dạng `APRON_01` hoặc `GATE_APRON_01`, chuỗi `clean_gate` bắt đầu bằng chữ cái `A`. Hệ quả là `clean_gate.startswith("A")` trả về `True`, khiến vị trí bãi đỗ tràn `APRON_01` bị xếp sai lệch hoàn toàn vào **Concourse A (Cổng tiếp xúc nhà ga)**.

Điều này dẫn đến:
1. Chuyến bay đỗ ở Apron xuất hiện dưới danh nghĩa cổng tiếp xúc nhà ga Concourse A trên biểu đồ Gantt.
2. Bộ lọc Concourse A hiển thị sai cả các chuyến bay đỗ bãi tràn.
3. Số lượng cổng của Concourse A bị đếm sai.

## 2. Quy Tắc Phân Loại Mới Chuẩn Hóa
Quy tắc phân loại mới được triển khai đồng bộ trên toàn bộ hệ thống (`assignment_adapter.py`, `gantt_chart.py`, `page_03_gate_operations.py`):

```python
clean_gate = upper_gate.replace("GATE_", "")
if clean_gate.startswith("REMOTE") or clean_gate.startswith("STAND"):
    concourse = "REMOTE"
elif clean_gate.startswith("APRON") or clean_gate.startswith("OVERFLOW") or clean_gate.startswith("OVF") or resource_type == "UNBOUNDED_OVERFLOW_APRON":
    concourse = "OVERFLOW"
elif clean_gate.startswith("T"):
    concourse = "T"
elif clean_gate.startswith("A"):
    concourse = "A"
elif clean_gate.startswith("G_") or clean_gate.startswith("G"):
    digits = "".join([ch for ch in clean_gate if ch.isdigit()])
    if digits:
        try:
            concourse = "T" if int(digits) <= 10 else "A"
        except ValueError:
            concourse = "T"
    else:
        concourse = "UNKNOWN_GROUP"
else:
    concourse = "UNKNOWN_GROUP"
```

### Các nhóm tài nguyên chính:
1. **Concourse T (Contact Gate):**
   - Loại tài nguyên: `GateResourceType.CONTACT_GATE`
   - Sức chứa: $C = 1$
   - Vị trí: Cổng tiếp xúc vật lý thuộc nhà ga T (Terminal T).
2. **Concourse A (Contact Gate):**
   - Loại tài nguyên: `GateResourceType.CONTACT_GATE`
   - Sức chứa: $C = 1$
   - Vị trí: Cổng tiếp xúc vật lý thuộc nhà ga A (Terminal A).
3. **Bãi đỗ từ xa (Finite Remote Stand):**
   - Loại tài nguyên: `GateResourceType.FINITE_REMOTE_STAND`
   - Sức chứa: Hữu hạn $C = K$ ($K \ge 1$, có thể là pooled capacity ví dụ $K=2$).
   - Vị trí: Bãi đỗ xa yêu cầu xe buýt đưa đón hành khách.
4. **Bãi đỗ tràn lý thuyết (Unbounded Overflow Apron):**
   - Loại tài nguyên: `GateResourceType.UNBOUNDED_OVERFLOW_APRON`
   - Sức chứa: $C = \infty$ (vô hạn, dùng làm fallback toán học để bảo đảm tính khả thi của mô hình phân cổng).
   - Vị trí: Không phải cổng tiếp xúc nhà ga.

## 3. Ngữ Nghĩa Kiểm Soát Sức Chứa (Capacity Enforcement)
- **Cổng tiếp xúc ($C = 1$):** Không cho phép bất kỳ 2 chuyến bay nào có khoảng chiếm dụng nửa mở $[A_{pred}, T_{release})$ giao nhau.
- **Bãi đỗ từ xa ($C = K$):** Cho phép tối đa $K$ chuyến bay đồng thời đỗ tại cùng một cụm bãi đỗ. Nếu có $K+1$ chuyến bay đồng thời, hệ thống phát hiện vi phạm sức chứa ngay lập tức.
- **Bãi đỗ tràn ($C = \infty$):** Cho phép số lượng chuyến bay tùy ý mà không kích hoạt vi phạm xung đột không gian.
