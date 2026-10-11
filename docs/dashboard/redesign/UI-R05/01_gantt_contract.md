# UI-R05: Interactive Gate Gantt Visual Contract & Temporal Semantics

## 1. Mục tiêu và Phạm vi
Tài liệu này xác lập đặc tả kỹ thuật (Contract) cho biểu đồ **Master Interactive Gantt Chart** (Page 03: Gate Operations), bảo đảm tính toàn vẹn toán học và biểu diễn vận hành hàng không theo chuẩn Aeolus Gate Optimization.

## 2. Hệ Tọa độ Thời gian & Miền Giá trị (Time Domain)
1. **Trục hoành (X-axis):** Thời gian liên tục đo bằng phút tính từ nửa đêm của ngày vận hành gốc ($0 = 00:00$).
2. **Cột mốc giờ địa phương (Tick intervals):** Tự động chia lưới theo bước 60 phút ($06:00, 07:00, \dots, 23:00, +1d\ 00:00, \dots$).
3. **Biểu diễn vượt nửa đêm (Cross-Midnight Continuous Formatting):**
   - Với $m < 1440$: biểu diễn định dạng chuẩn `HH:MM`.
   - Với $m \ge 1440$: biểu diễn định dạng liên tục `+1d HH:MM` (hoặc `+2d HH:MM`), không wrap vòng về 0 một cách mập mờ gây hiểu lầm ngày hôm trước.
   - Hàm chuẩn hóa: `_format_time_clock(m: int) -> str`.

## 3. Bản chất Khoảng Nửa Mở & Định thức Đệm An toàn
Khoảng chiếm dụng cổng của chuyến bay $i$ tuân thủ nghiêm ngặt mô hình khoảng nửa mở (half-open interval):
$$\mathcal{I}_i = [A_{pred}^{(i)}, T_{release}^{(i)})$$

Trong đó:
- $A_{pred}^{(i)}$: Thời điểm máy bay bắt đầu lăn vào vị trí đỗ (Gate-in / Predicted Arrival).
- $D_{gate\_out}^{(i)}$: Thời điểm máy bay kết thúc quay vòng vật lý và đẩy lùi (Pushback / Predicted Departure).
- $T_{release}^{(i)} = D_{gate\_out}^{(i)} + \Delta_{buffer}^{(i)}$: Thời điểm giải phóng cổng hoàn toàn sau khi cộng đệm dọn cổng.
- $\Delta_{buffer}^{(i)}$: Đệm giãn cách an toàn theo hợp đồng vận hành (mặc định 15 phút).

### Quy tắc Toàn vẹn Đệm (Single Buffer Integrity)
> [!IMPORTANT]
> Tuyệt đối không cộng đệm hai lần. Đệm chỉ được cộng đúng một lần vào $T_{release}$. Khoảng đỗ vật lý là $[A_{pred}, D_{gate\_out})$ và khoảng đệm bảo vệ là $[D_{gate\_out}, T_{release})$.

### Định lý Tiếp giáp Không Xung đột (Adjacent Intervals Non-Overlap)
Hai khoảng nửa mở tiếp giáp $\mathcal{I}_1 = [a, b)$ và $\mathcal{I}_2 = [b, c)$ với $a < b < c$ thỏa mãn:
$$\mathcal{I}_1 \cap \mathcal{I}_2 = \emptyset$$
Điều kiện xung đột giữa hai khoảng $[s_1, e_1)$ và $[s_2, e_2)$ là:
$$\max(s_1, s_2) < \min(e_1, e_2)$$
Khi $e_1 = s_2 = b$, ta có $\max(s_1, s_2) = b$ và $\min(e_1, e_2) = b$. Do $b < b$ là Sai, hai chuyến bay tiếp giáp tại cùng một cổng tiếp xúc có capacity = 1 **hoàn toàn hợp lệ và không xung đột**.

## 4. Hệ Thống Mã Hóa Trực Quan (Visual Encoding & Palette)
Biểu đồ Gantt sử dụng hệ màu tương phản cao theo Aeolus Design System:
- **Cổng tiếp xúc danh định gốc (Nominal Contact Gate):** `#00D2FF` (Cyan điện).
- **Cổng tiếp xúc tái phân bổ (Reassigned Contact Gate):** `#E5AD55` (Amber cảnh báo điều phối).
- **Bãi đỗ từ xa / Cổng xa (Remote Stand):** `#A78BFA` (Tím nhạt).
- **Bãi đỗ tràn lý thuyết (Overflow Apron):** `#64748B` (Muted Slate).
- **Phát hiện xung đột không gian - thời gian (Conflict / Collision):** `#E47777` (Crimson error).
- **Khoảng đệm an toàn (Buffer Segment):** Họa tiết sọc chéo mờ hoặc dải màu nhạt tiếp nối sau block quay vòng vật lý.

## 5. Quy tắc Thứ tự Trục Tung (Y-Axis Ordering)
- Các cổng được xếp theo thứ tự phân loại hợp lý: Concourse T $\to$ Concourse A $\to$ Bãi đỗ từ xa $\to$ Bãi đỗ tràn.
- Thứ tự danh mục trên biểu đồ Plotly được đảo ngược (`reversed(gate_ids)`) để cổng đầu tiên ($G\_01$) xuất hiện ở dòng trên cùng của canvas, tránh tình trạng cổng $G\_01$ bị đẩy xuống đáy đồ thị.
