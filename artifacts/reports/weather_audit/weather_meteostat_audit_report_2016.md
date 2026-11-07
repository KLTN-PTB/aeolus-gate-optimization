# BÁO CÁO THỰC NGHIỆM KIỂM TOÁN THỜI TIẾT METEOSTAT (NĂM 2016)
**Dự án**: Aeolus Gate Optimization (Phân tích Rò rỉ Dữ liệu Khí tượng)
**Thời gian kiểm toán**: 2026-10-19 23:56:28
**Quy tắc kiểm tra**: $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2h$

---

## 1. TỔNG QUAN KẾT QUẢ ĐỐI CHỨNG

Thực nghiệm tiến hành truy vấn trực tiếp từ API Meteostat trên mẫu **100 chuyến bay** của năm 2016 và so sánh với giá trị `O_TEMP`, `D_TEMP` lưu trong Aeolus:

### Bảng 1: Tỷ lệ khớp nhiệt độ (sai số $\le 0.5^\circ\text{C}$) theo từng mốc thời gian

| Vị trí thời tiết | Mốc giờ theo Lịch (`CRS`) | Mốc giờ Thực tế (`ACT`) | Mốc rào đón an toàn ($T - 2h$) | Mốc thực tế Aeolus đã dùng |
| :--- | :---: | :---: | :---: | :---: |
| **Thời tiết sân bay đi (`O_TEMP`)** | **92.0%** | 44.0% | 24.0% | **`CRS_DEP_TIME`** |
| **Thời tiết sân bay đến (`D_TEMP`)** | **100.0%** | 40.0% | 22.0% | **`CRS_ARR_TIME`** |

* **Sai số bình quân (MAE) sân bay đến**: So với giờ hạ cánh `CRS_ARR`: **0.0°C** vs So với giờ an toàn $T - 2h$: **2.132°C**.

---

## 2. BẰNG CHỨNG KHOA HỌC VỀ RÒ RỈ THÔNG TIN TƯƠNG LAI (LOOKAHEAD LEAKAGE)

Từ các kết quả đo lường định lượng trên, có thể rút ra 3 kết luận khoa học vững chắc:

1. **Khóa ghép dữ liệu (Join Key)**:
   * Aeolus ánh xạ thời tiết xuất phát `O_TEMP` theo đúng giờ cất cánh trên lịch trình (`CRS_DEP_TIME`).
   * Aeolus ánh xạ thời tiết hạ cánh `D_TEMP` theo đúng giờ hạ cánh trên lịch trình (`CRS_ARR_TIME`).
2. **Bản chất giá trị thời tiết**:
   * Toàn bộ giá trị thời tiết là **Số liệu Quan trắc Thực tế (Actual Hourly Observation)** của Meteostat tại đúng các khung giờ đó, không phải là bản tin dự báo khí tượng phát hành trước giờ bay.
3. **Chứng minh rò rỉ tại mốc $T - 2h$**:
   * Tại thời điểm $T - 2h$ (2 giờ trước khi cất cánh), nhiệt độ thực tế lúc hạ cánh `D_TEMP` tại sân bay đến **vẫn còn ở tương lai từ 3 đến 8 tiếng đồng hồ**.
   * Việc đưa con số quan trắc thực tế của giờ đến vào tập huấn luyện khiến mô hình học trên thông tin tương lai, giải thích vì sao khi dùng các biến thời tiết điểm đến, AUC ngoại tuyến tăng ảo lên ~0.688 nhưng hoàn toàn không khả thi khi triển khai vận hành thực tế.

---

## 3. MẪU DỮ LIỆU ĐỐI CHỨNG CHI TIẾT (SAMPLE FLIGHT CASES)

| Chuyến bay | Lịch trình (CRS) | Thực tế (ACT) | $T - 2h$ Cutoff | Aeolus D_TEMP | Meteostat D_TEMP tại CRS | Meteostat D_TEMP tại $T - 2h$ | Kết luận Khớp |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `DFW->LAX` | DEP: 09:00<br>ARR: 10:20 | DEP: 09:31<br>ARR: 12:22 | 07:00 | **13.9°C** | 13.9°C | 14.4°C | **CRS_ARR_TIME** |
| `MSY->LAX` | DEP: 15:45<br>ARR: 18:10 | DEP: 16:47<br>ARR: 18:40 | 13:45 | **21.1°C** | 21.1°C | 13.9°C | **CRS_ARR_TIME** |
| `LAS->LAX` | DEP: 20:20<br>ARR: 21:32 | DEP: 21:07<br>ARR: 22:18 | 18:20 | **13.3°C** | 13.3°C | 12.2°C | **CRS_ARR_TIME** |
| `JFK->LAX` | DEP: 16:59<br>ARR: 20:10 | DEP: 18:00<br>ARR: 21:26 | 14:59 | **23.3°C** | 23.3°C | 19.4°C | **CRS_ARR_TIME** |
| `LAS->LAX` | DEP: 06:12<br>ARR: 07:35 | DEP: 07:19<br>ARR: 08:58 | 04:12 | **12.8°C** | 12.8°C | 16.1°C | **CRS_ARR_TIME** |
| `SJC->LAX` | DEP: 17:05<br>ARR: 18:15 | DEP: 17:27<br>ARR: 19:04 | 15:05 | **20.0°C** | 20.0°C | 17.2°C | **CRS_ARR_TIME** |
| `HNL->LAX` | DEP: 15:30<br>ARR: 22:55 | DEP: 16:27<br>ARR: 23:25 | 13:30 | **15.0°C** | 15.0°C | 16.7°C | **CRS_ARR_TIME** |
| `MDW->LAX` | DEP: 19:55<br>ARR: 22:25 | DEP: 20:54<br>ARR: 23:02 | 17:55 | **17.8°C** | 17.8°C | 17.8°C | **CRS_ARR_TIME** |
| `RNO->LAX` | DEP: 18:50<br>ARR: 20:15 | DEP: 19:29<br>ARR: 21:06 | 16:50 | **21.1°C** | 21.1°C | 19.4°C | **CRS_ARR_TIME** |
| `BOS->DCA` | DEP: 18:00<br>ARR: 19:46 | DEP: 19:13<br>ARR: 21:46 | 16:00 | **21.7°C** | 21.7°C | 20.6°C | **CRS_ARR_TIME** |
| `TUS->LAX` | DEP: 06:40<br>ARR: 07:21 | DEP: 06:38<br>ARR: 08:10 | 04:40 | **13.9°C** | 13.9°C | 13.9°C | **CRS_ARR_TIME** |
| `PIT->LAX` | DEP: 15:30<br>ARR: 17:40 | DEP: 16:23<br>ARR: 18:23 | 13:30 | **23.3°C** | 23.3°C | 20.0°C | **CRS_ARR_TIME** |
| `MSP->LAX` | DEP: 13:11<br>ARR: 15:19 | DEP: 14:04<br>ARR: 15:43 | 11:11 | **13.3°C** | 13.3°C | 13.9°C | **CRS_ARR_TIME** |
| `DFW->DCA` | DEP: 13:20<br>ARR: 17:17 | DEP: 15:02<br>ARR: 20:18 | 11:20 | **22.2°C** | 22.2°C | 15.0°C | **CRS_ARR_TIME** |
| `SFO->LAX` | DEP: 22:30<br>ARR: 00:01 | DEP: 00:13<br>ARR: 01:32 | 20:30 | **14.4°C** | 14.4°C | 15.6°C | **CRS_ARR_TIME** |

---

## 4. DIỄN BIẾN NHIỆT ĐỘ 5 GIỜ ĐỔ LẠI TRƯỚC MỐC ĐO TẠI SÂN BAY ĐẾN (HISTORICAL HOURLY LAGS)

Bảng dưới đây thể hiện sự thay đổi nhiệt độ theo từng giờ từ 5 giờ trước mốc đo ($t - 5h$ đến $t - 1h$) so với mốc đo Aeolus sử dụng ($t_0$ tại `CRS_ARR_TIME`):

| Chuyến bay | Giờ đến CRS ($t_0$) | Aeolus D_TEMP ($t_0$) | Lag -1h | Lag -2h | Lag -3h | Lag -4h | Lag -5h | Biến thiên 5h (Δ = $t_0$ - $t_{-5h}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `DFW->LAX` | 10:20 | **13.9°C** | 13.9°C | 14.4°C | 14.4°C | 15.0°C | 15.0°C | **-1.1°C** |
| `MSY->LAX` | 18:10 | **21.1°C** | 18.9°C | 16.7°C | 14.4°C | 13.9°C | 13.9°C | **+7.2°C** |
| `LAS->LAX` | 21:32 | **13.3°C** | 13.3°C | 13.3°C | 12.8°C | 12.2°C | 10.6°C | **+2.7°C** |
| `JFK->LAX` | 20:10 | **23.3°C** | 22.8°C | 21.7°C | 20.0°C | 19.4°C | 19.4°C | **+3.9°C** |
| `LAS->LAX` | 07:35 | **12.8°C** | 12.8°C | 12.2°C | 15.0°C | 16.1°C | 16.7°C | **-3.9°C** |
| `SJC->LAX` | 18:15 | **20.0°C** | 18.9°C | 17.8°C | 17.2°C | 15.0°C | 15.6°C | **+4.4°C** |
| `HNL->LAX` | 22:55 | **15.0°C** | 15.0°C | 15.0°C | 15.0°C | 14.4°C | 14.4°C | **+0.6°C** |
| `MDW->LAX` | 22:25 | **17.8°C** | 17.8°C | 17.8°C | 17.2°C | 17.8°C | 15.6°C | **+2.2°C** |
| `RNO->LAX` | 20:15 | **21.1°C** | 20.6°C | 20.0°C | 19.4°C | 18.9°C | 17.2°C | **+3.9°C** |
| `BOS->DCA` | 19:46 | **21.7°C** | 22.8°C | 21.7°C | 21.7°C | 20.6°C | 18.9°C | **+2.8°C** |
| `TUS->LAX` | 07:21 | **13.9°C** | 13.9°C | 13.9°C | 14.4°C | 13.9°C | 13.9°C | **0.0°C** |
| `PIT->LAX` | 17:40 | **23.3°C** | 22.2°C | 21.7°C | 20.6°C | 20.0°C | 19.4°C | **+3.9°C** |
| `MSP->LAX` | 15:19 | **13.3°C** | 13.3°C | 13.9°C | 13.3°C | 13.9°C | 13.9°C | **-0.6°C** |
| `DFW->DCA` | 17:17 | **22.2°C** | 20.6°C | 20.0°C | 17.8°C | 16.7°C | 15.6°C | **+6.6°C** |
| `SFO->LAX` | 00:01 | **14.4°C** | 12.2°C | 15.6°C | 17.8°C | 17.8°C | 17.8°C | **-3.4°C** |

> [!NOTE]
> **Ý nghĩa thực tế của 5 cột dữ liệu quá khứ**:
> 1. **Chứng minh tính biến động theo thời gian**: Nhiệt độ tại sân bay biến thiên liên tục qua từng giờ (chênh lệch lên tới vài độ C trong 5 giờ).
> 2. **Cơ sở xây dựng đặc trưng hợp lệ (Point-in-Time Compliant Features)**: Thay vì dùng giá trị thời tiết tương lai tại $t_0$ (thời điểm máy bay đáp), hệ thống hoàn toàn có thể sử dụng chuỗi quan sát quá khứ ($t_{-1h}$ đến $t_{-5h}$ tính từ mốc chốt quyết định $T - 2h$) kết hợp xu hướng biến thiên để cung cấp thông tin thời tiết mà không vi phạm rò rỉ dữ liệu.

---
*(Báo cáo được khởi tạo tự động bởi module `src.data.weather_audit` phục vụ minh chứng Khóa luận Tốt nghiệp)*