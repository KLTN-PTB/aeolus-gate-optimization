# AEOLUS DASHBOARD — UI-R04
# AIRCRAFT TURN CONTRACT & BUFFER AUDIT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/04_aircraft_turn_contract.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** Aircraft Turn Domain Specialist, Optimization Operations Engineer  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** VERIFIED & PASSED  

---

## 1. MỤC TIÊU VÀ BỐI CẢNH NGHIÊN CỨU

Một lượt quay vòng máy bay (Aircraft Turnaround) liên kết một chặng bay đến (Inbound Leg) và một chặng bay đi (Outbound Leg) được thực hiện bởi cùng một tàu bay vật lý. 

Trong thiết kế nghiên cứu giai đoạn P07 của Aeolus, mô hình hóa thời gian quay vòng phải thỏa mãn các nguyên lý vật lý hàng không:
1. **Thời gian phục vụ mặt đất tối thiểu ($T_{min}$):** Tàu bay cần một khoảng thời gian nhất định (thường là 45 phút đối với dòng tàu bay thân hẹp như A320/B737) để hành khách xuống tàu, bốc dỡ hành lý, tiếp nhiên liệu, dọn dẹp vệ sinh và đón khách mới.
2. **Thời điểm tàu rời cổng thực tế ($D_{gate\_out}$):**
   $$D_{gate\_out} = \max(D_{pred}, A_{pred} + T_{min})$$
   Trong đó $A_{pred}$ là thời điểm hạ cánh dự báo và $D_{pred}$ là thời điểm cất cánh dự báo.
3. **Thời điểm giải phóng cổng an toàn ($T_{release}$):**
   $$T_{release} = D_{gate\_out} + \text{separation\_buffer}$$
   Trong đó `separation_buffer` là thời gian đệm giải phóng cổng an toàn để máy bay lùi (push-back) và dọn sạch vệt bánh trước khi máy bay kế tiếp tiến vào cổng.

---

## 2. QUY TẮC BẢO TOÀN BUFFER DUY NHẤT (NO DOUBLE-COUNTING)

### 2.1. Nguy cơ Cộng đệm Trùng lặp
Nếu lập trình viên thiếu cẩn trọng, công thức có thể vô tình cộng đệm hai lần:
- Lần 1: Cộng buffer vào thời gian đỗ (Dwell time) để tính thời điểm rời cổng: $D_{gate\_out} + \text{buffer}$.
- Lần 2: Tiếp tục cộng buffer khi kiểm tra khoảng thời gian trống để phân cổng cho chuyến tiếp theo: $T_{release} = (D_{gate\_out} + \text{buffer}) + \text{buffer}$.

Sai lầm này sẽ làm thổi phồng nhu cầu cổng thêm 15 phút cho mỗi chuyến bay, dẫn đến việc giải thuật báo quá tải giả (False Over-Capacity) và buộc nhiều chuyến bay ra bãi đỗ xa một cách không cần thiết.

### 2.2. Kiểm định Tính toán Thực tế trên Bộ dữ liệu P07
Trong file `turn_pairing_audit.json`:
- Ví dụ Cặp quay vòng `TURN_0001`:
  - $A_{pred} = 882$ (Phút từ nửa đêm).
  - $T_{min} = 45$ phút $\implies$ Sớm nhất có thể rời cổng $= 882 + 45 = 927$.
  - $D_{ml} = 967$.
  - $D_{gate\_out} = \max(967, 927) = 967$.
  - $\text{Buffer} = 15$ phút.
  - $T_{release} = 967 + 15 = 982$.
  - Thời lượng chiếm cổng $= 982 - 882 = 100$ phút.
- **Kết quả Kiểm tra:** Toàn bộ 30 cặp quay vòng đều tuân thủ chính xác công thức này. Buffer chỉ được tính đúng 1 lần vào $T_{release}$ (`test_r04_t20 PASSED`).

---

## 3. LOẠI BỎ TOÀN BỘ DỮ LIỆU GIẢ LẬP & LỐI TẮT

### 3.1. Loại bỏ Lối tắt `len(flights) // 2`
- Trước UI-R04, trang Control Tower tự tiện hiển thị số cặp quay vòng bằng `len(flights) // 2`.
- Trong kịch bản `SCEN_P09_CANONICAL_120`, đây là tập hợp 120 chuyến bay đến độc lập (`is_paired = False`). Việc báo "60 Cặp quay vòng" là hoàn toàn sai lệch thực tế.
- Trong UI-R04: `load_scenario_turns("SCEN_P09_CANONICAL_120")` trả về danh sách rỗng `[]`, và giao diện hiển thị trung thực `N/A (Chưa ghép cặp)`.

### 3.2. Loại bỏ Biến `sample_turns`
- Toàn bộ danh sách `sample_turns` (chứa các mã `TURN_DL1024_DL1502`, `TURN_DL0466_DL0764`, `TURN_NK0040_NK0041`) đã bị xóa sổ khỏi `page_02_flight_intelligence.py`.
- Nếu kịch bản có dữ liệu ghép cặp (như `SCEN_P07_DUAL_CORE_30`), danh sách cặp quay vòng hiển thị từ nguồn dữ liệu thật `turn_pairing_audit.json`.
- Nếu kịch bản không có dữ liệu ghép cặp, hệ thống kích hoạt Empty State rõ ràng.
