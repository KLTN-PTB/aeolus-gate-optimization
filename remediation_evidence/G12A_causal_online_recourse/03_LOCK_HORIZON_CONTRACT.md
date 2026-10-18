# AEOLUS-G12A — DELIVERABLE 03: LOCK HORIZON OPERATIONAL CONTRACT & RECOURSE PROTOCOL

---

**Task Identifier:** `AEOLUS-G12A` — Causal Online Recourse Remediation  
**Auditor & Implementation Role:** Senior Operations Research Engineer, Aviation Operations Lead  
**Date:** 2026-10-12  
**Document Classification:** OPERATIONAL CONTRACT & RECOURSE PROTOCOL SPECIFICATION  

---

## 1. VẤN ĐỀ ĐẶT RA VỀ THAM SỐ `lock_horizon_minutes`

Trong giai đoạn kiểm toán G10 và G11, tham số `lock_horizon_minutes: int = 45` đã bị phát hiện là mã chết (unused dead code). Hơn nữa, việc áp dụng máy móc quy tắc:
$$\text{"Chỉ những chuyến bay có } T_{\text{arr}} > t + 45 \text{ mới được phép điều chuyển"}$$
sẽ dẫn đến thảm họa logic: Khi một chuyến bay hạ cánh tại epoch $t$ ($T_{\text{arr}} = t < t + 45$) và phát hiện cổng đỗ của nó bị chiếm bởi một tàu bay trễ, quy tắc trên sẽ cấm điều chuyển chính chuyến bay đang hạ cánh, khiến toàn bộ cơ chế recourse bị tê liệt và dẫn đến tai nạn kẹt cổng trên thực địa.

Bản hợp đồng vận hành này giải quyết triệt để bài toán bằng cách phân tách rõ ràng giữa **Khóa Vật lý (Physical Docking Lock)**, **Khóa Cam kết Điều hành (Operational Commitment Window)**, và **Cơ chế Điều chuyển Khẩn cấp (Emergency Recourse Exception)**.

---

## 2. QUY CHUẨN BA CẤP ĐỘ KHÓA TRONG ĐIỀU ĐỘ SÂN BAY

```
                       DÒNG THỜI GIAN VẬN HÀNH (OPERATIONAL TIMELINE)
   Quá khứ / Đã cập cổng     |                     Tương lai gần              |  Tương lai xa
   s <= t                    |                  t < s <= t + H_lock           |  s > t + H_lock
-----------------------------+------------------------------------------------+-------------------->
 [CẤP 1: KHÓA VẬT LÝ]        | [CẤP 2: KHÓA CAM KẾT (COMMITMENT WINDOW)]     | [CẤP 3: LINH HOẠT]
 - Tàu bay đã đỗ tại cổng    | - Tàu bay sắp hạ cánh trong 45 phút            | - Kế hoạch sơ bộ
 - TUYỆT ĐỐI KHÔNG ĐIỀU CHUYỂN | - Cổng đỗ đã gửi cho mặt đất và hành khách     | - Có thể tái phân
 - Không được dời tàu đã đỗ   | - ĐƯỢC BẢO VỆ: Cấm chuyến khác cướp cổng       |   bổ ở các vòng sau
                             | - NGOẠI LỆ: Nếu chính cổng bị kẹt -> RECOURSE  |
```

### 2.1. Cấp độ 1: Khóa Vật lý (Physical Docking Lock)
- **Áp dụng:** Toàn bộ tàu bay đã hạ cánh và đang chiếm cổng tại thời điểm $t$ ($T_{\text{arr}} \le t$ và chưa rời cổng).
- **Quy tắc:** Tàu bay đang trả/đón khách và tiếp nhiên liệu không thể bị kéo đi (No Towing Policy). Cổng đỗ của chúng bị khóa cứng.
- **Bất biến:** Danh sách `locked_flights` bảo toàn tính bất biến của các chuyến bay đã cập cổng.

### 2.2. Cấp độ 2: Khóa Cam kết Điều hành (Operational Commitment Window: $H_{\text{lock}} = 45$ phút)
- **Áp dụng:** Các chuyến bay có giờ đến dự kiến nằm trong khoảng $t < T_{\text{arr}}^{\text{est}} \le t + H_{\text{lock}}$.
- **Bối cảnh vận hành:** Trong vòng 45 phút trước khi đến, vị trí cổng đỗ đã được thông báo cho phi hành đoàn, bộ phận bốc xếp hành lý, xe thang và hành khách nối chuyến.
- **Quy tắc bảo vệ:** Khi một chuyến bay khác cần tìm cổng thay thế tại epoch $t$, các cổng đã được gán cho chuyến bay trong khung cam kết này **ĐƯỢC BẢO VỆ NGHIÊM NGẶT**:
  - Không được chọn cổng ứng viên nếu khoảng chiếm dụng của chuyến bay đến $[t, \hat{T}_{\text{dep}} + \text{buffer}]$ bị chồng lấn với cửa sổ của chuyến bay đã cam kết.
  - Điều này ngăn chặn việc "chữa cháy cho chuyến này bằng cách cướp cổng của chuyến sắp hạ cánh trong 20 phút nữa".

### 2.3. Cấp độ 3: Ngoại lệ Điều chuyển Khẩn cấp (Emergency Recourse Exception)
- **Áp dụng:** Chính chuyến bay đang hạ cánh tại thời điểm $t$ ($T_{\text{arr}} = t$).
- **Điều kiện kích hoạt:** Nếu cổng ban đầu $g_{\text{curr}}$ của chuyến bay đang hạ cánh bị tàu bay khác chiếm dụng (Physical Conflict):
  - Đây là sự cố an toàn đường lăn (Taxiway Blockage).
  - Hệ thống **BẮT BUỘC KÍCH HOẠT ĐIỀU CHUYỂN KHẨN CẤP (EMERGENCY RECOURSE)** cho chuyến bay này, đưa nó sang một cổng tiếp xúc khả dụng khác hoặc bãi đỗ xa (Remote Stand).

---

## 3. THUẬT TOÁN CHỌN CỔNG ĐIỀU CHUYỂN (CAUSAL RECOURSE SELECTION PROTOCOL)

Tại epoch $t$, khi chuyến bay $f_{\text{curr}}$ hạ cánh:
1. **Kiểm tra Cổng Kế hoạch ($g_{\text{planned}}$):**
   - Nếu $g_{\text{planned}}$ đang có tàu bay đỗ thực tế tại $t$: $\rightarrow$ **XUNG ĐỘT VẬT LÝ**. Kích hoạt Recourse.
   - Nếu $g_{\text{planned}}$ không có tàu bay đỗ tại $t$:
     - Tính thời gian chiếm dụng ước tính: $\hat{W}_{\text{curr}} = [t, \hat{T}_{\text{dep}|t}(f_{\text{curr}}) + \text{buf}]$.
     - Kiểm tra các chuyến bay đã cam kết trên $g_{\text{planned}}$ trong $[t, t + H_{\text{lock}}]$.
     - Nếu không chồng lấn $\rightarrow$ Giữ nguyên $g_{\text{planned}}$, tàu bay cập cổng an toàn.
     - Nếu chồng lấn $\rightarrow$ Kích hoạt Recourse để tránh tắc nghẽn dây chuyền.
2. **Tìm kiếm Cổng Tiếp xúc Khả dụng (Contact Gate Search):**
   - Quét danh sách các cổng tiếp xúc $g \in \mathcal{G}_{\text{contact}}$ theo thứ tự ưu tiên:
     - Điều kiện 1: Tương thích loại tàu bay ($f_{\text{curr}}.\text{aircraft\_type} \in g.\text{allowed\_types}$).
     - Điều kiện 2: Cổng $g$ không có tàu bay đỗ vật lý tại $t$.
     - Điều kiện 3: Khoảng $\hat{W}_{\text{curr}}$ không giao cắt với bất kỳ chuyến bay nào đã cam kết trên cổng $g$ trong khoảng $[t, t + H_{\text{lock}}]$.
     - Điều kiện 4: Khoảng $\hat{W}_{\text{curr}}$ không giao cắt với chuyến bay theo lịch xa hơn trừ khi chuyến bay xa hơn được chuyển giao thành công.
   - Nếu tìm thấy cổng $g^*$ thỏa mãn $\rightarrow$ Điều chuyển $f_{\text{curr}}$ sang $g^*$.
3. **Phân bổ vào Bãi đỗ Xa (Finite Remote Stand Fallback):**
   - Nếu không có cổng tiếp xúc nào thỏa mãn:
     - Kiểm tra sức chứa bãi đỗ xa tức thời: $\text{current\_remote\_usage}(t) < \text{finite\_remote\_capacity}$.
     - Nếu còn chỗ $\rightarrow$ Điều chuyển $f_{\text{curr}}$ ra bãi đỗ xa (`REMOTE`).
     - Nếu bãi đỗ xa đã đầy $\rightarrow$ Ghi nhận trạng thái **`UNASSIGNED / NO_CAPACITY`**, không ngụy tạo kết quả khả thi.

---

## 4. BẢNG KHẢ NĂNG KIỂM CHỨNG CỦA HỢP ĐỒNG (TESTABILITY MATRIX)

| Tình huống Kiểm chứng | Kỳ vọng Hành vi của Thuật toán | Tiêu chuẩn Đánh giá |
| :--- | :--- | :---: |
| Chuyến bay đến tại $t$, cổng kế hoạch trống và không trùng cam kết | Giữ nguyên cổng, không phát sinh chi phí điều chuyển. | **PASS** |
| Chuyến bay đến tại $t$, cổng kế hoạch bị tàu bay khác đỗ tại $t$ | Kích hoạt Emergency Recourse, đổi sang cổng tiếp xúc trống hoặc remote. | **PASS** |
| Cổng ứng viên có chuyến bay cam kết lúc $t + 30$ ($< t + 45$) | Bị TỪ CHỐI không được gán, bảo vệ chuyến cam kết. | **PASS (H_lock Enforcement)** |
| Thay đổi $H_{\text{lock}}$ từ $45$ xuống $15$ khi có chuyến lúc $t + 30$ | Cổng ứng viên trở nên HỢP LỆ vì chuyến kia nằm ngoài $H_{\text{lock}}=15$. | **PASS (Demonstrable Impact)** |
| Bãi đỗ xa đã đầy tải (`usage == capacity`) | Từ chối gán remote stand, báo lỗi thiếu sức chứa rõ ràng. | **PASS (Finite Capacity)** |
