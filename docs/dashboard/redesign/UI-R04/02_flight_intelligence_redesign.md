# AEOLUS DASHBOARD — UI-R04
# FLIGHT INTELLIGENCE REDESIGN SPECIFICATION & AUDIT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/02_flight_intelligence_redesign.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** Principal ML Research Visualization Engineer, Senior Streamlit Architect  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** COMPLETED & VERIFIED  

---

## 1. MỤC TIÊU & TỔNG QUAN THIẾT KẾ

Trang 02 **Flight Intelligence (Dự báo Trễ & ML)** thể hiện cốt lõi dự báo của Aeolus. Trong các phiên bản ban đầu, trang gặp các vấn đề lớn:
1. **Thiếu vắng chiều cất cánh (Outbound):** Toàn bộ giao diện Tab A chỉ hiển thị dự báo chuyến đến (Inbound), phớt lờ hoàn toàn kiến trúc Dual-Core ML đã phát triển ở giai đoạn P07.
2. **Hardcoded Sample Turns:** Tab B hiển thị 3 đối tượng `AircraftTurnView` bịa đặt cố định (`TURN_DL1024_DL1502`, `TURN_DL0466_DL0764`, `TURN_NK0040_NK0041`) bất kể người dùng chọn kịch bản nào.
3. **Double Buffer Risk:** Cơ chế cộng đệm thời gian vào cửa sổ chiếm dụng cổng có thể bị cộng lặp hai lần nếu không phân tách rõ giữa thời gian dịch vụ tại cổng ($D_{gate\_out}$) và thời điểm giải phóng cổng ($T_{release}$).
4. **Không có Empty State:** Khi kịch bản không ghép cặp (vd: `SCEN_P09_CANONICAL_120`), trang vẫn cố hiển thị các cặp giả thay vì thông báo trung thực.

UI-R04 đã thiết kế lại hoàn toàn cấu trúc 3 Tab của Flight Intelligence.

---

## 2. CẤU TRÚC 3 TAB CHỨC NĂNG

### 2.1. Tab A: Dự báo Trễ Chuyến bay Dual-Core ML
- **Phân tách Chiều bay (Direction Awareness):**
  - Hỗ trợ đầy đủ cả hai chiều: `Hạ cánh (ARR)` từ mô hình NGBoost Student-t và `Cất cánh (DEP)` từ mô hình Certified Point XGBoost.
  - Bộ lọc Chiều bay cho phép xem riêng biệt `Tất cả`, `Hạ cánh (ARR)` hoặc `Cất cánh (DEP)`.
- **Bảo toàn Dấu Trễ Dự báo:**
  - Giữ nguyên các giá trị dự báo đến sớm (âm), ví dụ `-9.06 min`, phản ánh đúng phân phối thực tế của dữ liệu BTS.
  - Phân loại mức rủi ro dựa trên ngưỡng trễ: Sớm/Đúng giờ (<0m), Trễ nhẹ (0-15m), Trễ vừa (15-30m), Trễ nặng (≥30m).
- **Phân phối Xác suất & Quantiles:**
  - Hiển thị xác suất trễ vượt ngưỡng $P(\text{Delay} \ge 15m)$.
  - Trích xuất các phân vị dự báo ($q_{10}, q_{50}, q_{90}$) từ mô hình phân phối xác suất NGBoost Student-t.
- **Biểu đồ Phân phối Độ trễ:** Tích hợp với `create_delay_distribution_figure` hiển thị biểu đồ tần suất trực quan.

### 2.2. Tab B: Động lực học Quay vòng & Hấp thụ Buffer
- **Quy chuẩn Công thức Khoa học P07:**
  $$\begin{aligned}
  D_{gate\_out} &= \max(D_{pred}, A_{pred} + T_{min}) \\
  T_{release} &= D_{gate\_out} + \text{separation\_buffer} \\
  \text{Khoảng chiếm dụng cổng} &= [A_{pred}, T_{release})
  \end{aligned}$$
  *Quy tắc An toàn:* Giãn cách an toàn (`separation_buffer = 15 min`) chỉ được cộng đúng 1 lần vào $T_{release}$, không cộng lặp vào thời gian tàu bay đỗ tại cổng.
- **Loại bỏ Hoàn toàn `sample_turns`:**
  - Dữ liệu lượt quay vòng được tải trực tiếp từ dịch vụ chuẩn `ScenarioService.load_scenario_turns()`.
  - Với kịch bản có 30 cặp quay vòng (`SCEN_P07_DUAL_CORE_30`), người dùng được chọn danh sách 30 cặp quay vòng xác thực từ `turn_pairing_audit.json`.
- **Trạng thái Trống (Empty State) Trung thực:**
  - Khi người dùng đang chọn kịch bản đơn lẻ (như `SCEN_P09_CANONICAL_120`), hệ thống hiển thị card `render_empty_state` giải thích rõ: *"Kịch bản hiện tại chưa ghép cặp lượt bay (Unpaired Scenario)"* và hướng dẫn chuyển sang kịch bản `SCEN_P07_DUAL_CORE_30`.
- **Năm Thẻ KPI Bóc tách Quá trình Quay vòng:**
  1. *Cửa sổ Quay vòng:* Tổng thời gian từ hạ cánh đến cất cánh danh định.
  2. *Đệm Slack Khả dụng:* Thời gian đệm tối đa có thể hấp thụ trễ ($T_{slack} = T_{window} - T_{min}$).
  3. *Slack Đã Hấp thụ:* Mức độ trễ của chuyến đến đã được triệt tiêu mà không làm ảnh hưởng chuyến đi.
  4. *Slack Còn lại:* Dự phòng phát sinh còn lại, cảnh báo rủi ro cao nếu $< 10$ phút.
  5. *Thời lượng Chiếm Cổng:* Tổng thời gian từ $A_{pred}$ đến $T_{release}$ (đã tính đúng 1 lần Buffer).

### 2.3. Tab C: Giải thích Mô hình Học máy bằng TreeSHAP
- **Global Feature Importance:** Biểu đồ thanh ngang hiển thị 8 đặc trưng có giá trị trung bình $|\text{SHAP}|$ lớn nhất từ file `artifacts/models/inbound_arrival/shap_summary/global_importance.csv`.
- **Local Waterfall Attributions:** Phân rã chi tiết từng case study chuyến bay đại diện từ `shap_case_studies.json`, thể hiện cơ chế cộng tính địa phương (Local Accuracy):
  $$f(x) = \phi_0 + \sum_{i=1}^{M} \phi_i(x)$$
- **Bảng Đánh giá Ngoài mẫu (OOF Metrics) trong Research Mode:**
  - Khi bật chế độ *Research Mode*, hệ thống kích hoạt bảng đánh giá kiểm định chéo 5-Fold Stratified CV từ `regression_metrics.csv` với các chỉ số MAE, RMSE, $R^2$.

---

## 3. BẢNG KIỂM TRA TÍNH TOÀN VẸN DỮ LIỆU

| Chỉ tiêu Kiểm định | Yêu cầu Kỹ thuật | Kết quả trong UI-R04 |
| :--- | :--- | :--- |
| **Chiều bay Tab A** | Phải có cả ARR và DEP | Đạt (`{'ARR', 'DEP'}`) |
| **Bảo toàn Dấu Trễ** | Độ trễ âm không bị ép về 0 | Đạt (Trễ trung bình $-9.1$ min) |
| **Zero Target Leakage** | Cấm cột `actual_delay_min` | Đạt (Kiểm định `DataLeakageError`) |
| **Nguồn Cặp Quay vòng** | Nguồn gốc từ artifact P07 | Đạt (Tải từ `turn_pairing_audit.json`) |
| **Empty State Tab B** | Không hiển thị cặp giả khi chưa ghép | Đạt (`unpaired` trả về `[]` và render empty state) |
| **Cộng Đệm Buffer** | Buffer chỉ cộng 1 lần duy nhất | Đạt ($T_{release} = D_{gate\_out} + \text{buffer}$) |
