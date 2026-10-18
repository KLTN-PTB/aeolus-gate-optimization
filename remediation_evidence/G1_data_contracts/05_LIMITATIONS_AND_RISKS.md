# GIỚI HẠN KHOA HỌC VÀ ĐÁNH GIÁ RỦI RO — AEOLUS-G1

**Giai đoạn:** AEOLUS-G1 — Data Provenance, Temporal Contracts & Evidence Lineage  
**Thời điểm lập:** 2026-10-11  
**Mục tiêu tài liệu:** Minh bạch hóa các giới hạn khoa học, xác định rõ ranh giới đã được chứng nhận và liệt kê các rủi ro tồn dư cần kiểm soát trong các giai đoạn tiếp theo (G2–G4).

---

## 1. RANH GIỚI ĐÃ ĐƯỢC CHỨNG NHẬN (CERTIFIED BOUNDARIES)

Giai đoạn G1 đã chuẩn hóa và chứng nhận thành công các thành phần sau:
1. **Phân loại nguồn gốc dữ liệu 6 chiều (`EvidenceProvenance`):**
   - Đã chứng nhận cơ chế phân định minh bạch giữa dữ liệu thực nguyên bản (`REAL_AEOLUS`), dữ liệu lấy mẫu dẫn xuất (`REAL_DERIVED`), và dữ liệu giả lập (`SYNTHETIC`).
   - Đã chứng nhận cơ chế Fail-Closed: không cho phép dữ liệu thiếu thông tin được coi là dữ liệu thật.
2. **Hợp đồng thông tin thời gian $T - 2\text{h}$ (`TemporalCutoffContract`):**
   - Đã chứng nhận cơ chế từ chối các thuộc tính vận hành thực tế (`DEP_TIME`, `ARR_TIME`, `WHEELS_ON`, `TAXI_IN`, v.v.).
   - Đã chứng nhận việc chuẩn hóa múi giờ ATL (`America/New_York`) và chuyển đổi UTC đồng nhất.
3. **Tính trung thực của Dashboard và Export:**
   - Kịch bản `SCEN_P09_CANONICAL_120` và `SCEN_2023_PEAK_01` không còn bị gắn nhãn sai là `BTS_OTP_2023_CURATED`; nhãn hiển thị đã được chỉnh thành `SCALABILITY_GENERATOR_BTS_2023_DERIVED`.
   - Cơ chế xuất khẩu dữ liệu (`export_adapter.py`) đã có chốt chặn ngăn việc xuất kịch bản giả lập với nhãn `REAL_AEOLUS`.

> [!IMPORTANT]
> **Tuyệt đối không tuyên bố "Zero Leakage cho toàn bộ kho dữ liệu":**  
> Việc xác thực không rò rỉ (Zero Leakage) tại G1 chỉ được chứng nhận trên các luồng pipeline đã thẩm định (Downstream Scalability Scenario, Native Dual-Core Turnaround, và Dashboard Presentation Flow). Nhóm nghiên cứu không mở rộng kết luận này cho toàn bộ các tập dữ liệu thời tiết thô bên ngoài hoặc các pipeline chưa được audit.

---

## 2. GIỚI HẠN KHOA HỌC TỒN TẠI (SCIENTIFIC LIMITATIONS)

Dự án có các giới hạn nghiên cứu nội tại sau đây cần được công khai minh bạch trong báo cáo khóa luận:

### 2.1. Bản chất của các kịch bản phân bổ cổng (Gate Optimization Scenarios)
- **Kịch bản P09 (120 chuyến, 25 cổng) và Stress Test (1500 chuyến, 50 cổng):**  
  Mặc dù được lấy mẫu từ các chuyến bay thực tế năm 2023 tại sân bay ATL (`DEST == 'ATL'`), các chuyến bay này được gán cổng danh định theo thuật toán xoay vòng (round-robin) và mã chuyến bay giả lập (`S1500-xxxx`). Đây là kịch bản phục vụ kiểm thử ứng suất thuật toán tối ưu (Scalability Stress Testing), **KHÔNG PHẢI** lịch phân bổ cổng thực tế của nhà ga Hartsfield-Jackson Atlanta.
- **Kịch bản P07 Dual-Core Turnaround:**  
  Các giá trị độ trễ đến và đi được dự báo bằng mô hình máy học thực thụ (`NGBoost` và `XGBoost`), nhưng việc liên kết chuyến bay đến và chuyến bay đi thành cặp quay đầu (Turn Pair) được thực hiện thông qua bộ sinh phiên mô phỏng (`SYNTHETIC_PAIR`), không phải là cặp quay đầu vật lý cùng số hiệu đuôi tàu bay (tail number) trích xuất từ dữ liệu khai thác thực tế.

### 2.2. Dữ liệu thời tiết thô (Weather Observation Features)
- Dữ liệu thời tiết thô của Aeolus (`O_TEMP`, `O_WSPD`, `D_TEMP`, v.v.) chưa có bằng chứng độc lập chứng minh thời điểm quan trắc thực tế (point-in-time timestamp) nằm trước mốc cắt $T - 2\text{h}$.
- Theo chính sách của `weather_contract.py` và `leakage_rules.py`, toàn bộ các cột thời tiết này **bị loại bỏ (DROP policy)** khỏi tập đặc trưng huấn luyện và suy luận để đảm bảo tính an toàn học thuật tuyệt đối.

### 2.3. Dữ liệu kiểm định cuối cùng năm 2024 (Sealed Holdout 2024)
- Năm 2024 đã từng được truy cập trong một số đợt hậu kiểm lịch sử của repository. Do đó, năm 2024 không thể được coi là tập holdout "hoàn toàn nguyên vẹn chưa từng tiếp xúc".
- Toàn bộ dữ liệu năm 2024 tiếp tục được niêm phong nghiêm ngặt dưới Protocol V4 và bị cấm sử dụng trong bất kỳ bước tuning hay lựa chọn mô hình nào của đợt remediation này.

---

## 3. RỦI RO KỸ THUẬT VÀ PHƯƠNG ÁN XỬ LÝ CHO CÁC GIAI ĐOẠN TIẾP THEO

| STT | Rủi ro kỹ thuật | Mức độ | Tác động tiềm tàng | Phương án xử lý kiểm soát (Mitigation) |
| :---: | :--- | :---: | :--- | :--- |
| **R-01** | Nguy cơ tái xuất hiện synthetic fallback trong code mới | Vừa | Gây hiểu lầm khi chạy thử nghiệm nghiên cứu | Bắt buộc bật cờ `require_real=True` trong các script nghiên cứu khoa học; áp dụng `SilentFallbackError`. |
| **R-02** | Khác biệt múi giờ khi mở rộng sang sân bay khác ngoài ATL | Thấp | Lệch mốc cắt T-2h nếu không phải Eastern Time | `OperationalTemporalProfile` đã bắt buộc khai báo timezone IANA của sân bay; kiểm tra qua `time_normalization.py`. |
| **R-03** | Mô hình ML yêu cầu các cột không có trong kịch bản tối ưu | Thấp | Lỗi suy luận khi chạy live ML trên kịch bản synthetic | Bộ adapter dự báo đã có kiểm tra target leakage và fallback an toàn sang `PRECOMPUTED` hoặc `SCHEDULE_BASELINE`. |
| **R-04** | Nguy cơ phá vỡ tính đóng băng của các artifact lịch sử | Cao | Mất tính tái lập và vi phạm quy tắc an toàn G0 | Duy trì script đối soát hash tự động qua `04_EVIDENCE_MANIFEST.json` trước và sau mỗi giai đoạn. |

---

## 4. KẾT LUẬN

Các giới hạn và rủi ro trên đã được lập danh mục và kiểm soát ở mức kiến trúc phần mềm. Hệ thống tại G1 đảm bảo tính trung thực khoa học cao nhất, sẵn sàng làm nền tảng vững chắc cho các giai đoạn tiếp theo của đề tài.
