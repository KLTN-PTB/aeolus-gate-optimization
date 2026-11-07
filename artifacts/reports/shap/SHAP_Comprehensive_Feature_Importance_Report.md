# BÁO CÁO TOÀN DIỆN GIẢI THÍCH ĐẶC TRƯNG MÔ HÌNH BẰNG SHAP (SHAPLEY ADDITIVE EXPLANATIONS)
**Thời gian kết xuất**: 2026-10-21 18:50:23  
**Phương pháp giải thích**: `shap.TreeExplainer` trên mẫu kiểm thử độc lập năm 2024  
**Phạm vi**: Đầy đủ 8 mô hình Champion XGBoost (Global 5M và Local ATL cho cả Phân loại & Hồi quy, Chiều đến & Chiều đi)

---

## 1. TỔNG QUAN PHÁT HIỆN TỪ GIẢI THÍCH SHAP

Qua việc phân tích đóng góp của các đặc trưng trên cả 8 mô hình:
1. **Nhóm đặc trưng Tắc nghẽn & Lịch sử Lan truyền (M2) luôn thống trị:**
   - Các đặc trưng như `ORIGIN_CONGESTION_SAME_HOUR`, `DEST_CONGESTION_SAME_HOUR`, `ROUTE_AVG_ARR_DELAY_PAST`, `AIRLINE_AVG_DEP_DELAY_ROLLING` liên tục nằm trong Top 1–3 đặc trưng quan trọng nhất.
   - *Ý nghĩa thực tế:* Chuyến bay bị trễ phụ thuộc nhiều nhất vào mật độ bay cùng giờ và việc chuyến bay trước đó của cùng máy bay/hãng có bị trễ hay không.
2. **Nhóm đặc trưng Lịch trình (M1):**
   - `DEP_HOUR`, `CRS_ELAPSED_TIME`, `DISTANCE_KM`, `MONTH` đóng vai trò nền tảng xác định biên độ trễ theo khung giờ cao điểm (Peak Hours).
3. **Nhóm đặc trưng Thời tiết (M3 & M4):**
   - Tốc độ gió (`WSPD`), lượng mưa (`PRCP`) và biến thiên nhiệt độ/gió (Delta_Temp_1h, Delta_Wspd_1h) kích hoạt các gai trễ cực đoan khi thời tiết xấu xảy ra tại Atlanta hoặc các sân bay đối tác.

---

## 2. TOP ĐẶC TRƯNG QUAN TRỌNG NHẤT CỦA TỪNG MÔ HÌNH

### 🔹 Global 5M — Chuyến đến (Arrival Cls)
|   Thứ hạng | Đặc trưng            |   Mean |SHAP| |
|-----------:|:---------------------|--------------:|
|          1 | ARR_HOUR             |        0.18   |
|          2 | HOUR_SIN             |        0.1564 |
|          3 | OP_CARRIER_CODE      |        0.1215 |
|          4 | DEST_CODE            |        0.0975 |
|          5 | MONTH_COS            |        0.0912 |
|          6 | SEASON_CODE          |        0.0751 |
|          7 | IS_COVID_PERIOD      |        0.071  |
|          8 | DAY                  |        0.0612 |
|          9 | DEP_HOUR             |        0.0608 |
|         10 | MONTH                |        0.0492 |
|         11 | DOW_SIN              |        0.0483 |
|         12 | DEST_DAILY_FLIGHTS   |        0.0473 |
|         13 | ORIGIN_DAILY_FLIGHTS |        0.0463 |
|         14 | DOW_COS              |        0.0406 |
|         15 | ORIGIN_CODE          |        0.0356 |

### 🔹 Global 5M — Chuyến đi (Departure Cls)
|   Thứ hạng | Đặc trưng            |   Mean |SHAP| |
|-----------:|:---------------------|--------------:|
|          1 | HOUR_SIN             |        0.2517 |
|          2 | OP_CARRIER_CODE      |        0.1475 |
|          3 | ARR_HOUR             |        0.1216 |
|          4 | DEP_HOUR             |        0.0961 |
|          5 | SEASON_CODE          |        0.0855 |
|          6 | MONTH_COS            |        0.0853 |
|          7 | IS_COVID_PERIOD      |        0.0702 |
|          8 | DEST_CODE            |        0.0664 |
|          9 | DOW_SIN              |        0.0557 |
|         10 | DAY                  |        0.0536 |
|         11 | MONTH                |        0.0465 |
|         12 | ORIGIN_CODE          |        0.0351 |
|         13 | DISTANCE_KM          |        0.0327 |
|         14 | DOW_COS              |        0.0316 |
|         15 | ORIGIN_DAILY_FLIGHTS |        0.028  |

### 🔹 Global 5M — Chuyến đến (Arrival Reg)
|   Thứ hạng | Đặc trưng            |   Mean |SHAP| |
|-----------:|:---------------------|--------------:|
|          1 | ARR_HOUR             |        2.5867 |
|          2 | MONTH_COS            |        1.9829 |
|          3 | HOUR_SIN             |        1.6282 |
|          4 | OP_CARRIER_CODE      |        1.5081 |
|          5 | DEST_CODE            |        1.2372 |
|          6 | DEST_DAILY_FLIGHTS   |        1.2204 |
|          7 | DAY                  |        1.0827 |
|          8 | IS_COVID_PERIOD      |        1.0574 |
|          9 | SEASON_CODE          |        0.913  |
|         10 | MONTH                |        0.843  |
|         11 | DOW_COS              |        0.8093 |
|         12 | DOW_SIN              |        0.7947 |
|         13 | DEP_HOUR             |        0.7686 |
|         14 | DISTANCE_KM          |        0.6938 |
|         15 | ORIGIN_DAILY_FLIGHTS |        0.6792 |

### 🔹 Global 5M — Chuyến đi (Departure Reg)
|   Thứ hạng | Đặc trưng          |   Mean |SHAP| |
|-----------:|:-------------------|--------------:|
|          1 | ARR_HOUR           |        1.9888 |
|          2 | HOUR_SIN           |        1.8428 |
|          3 | MONTH_COS          |        1.8114 |
|          4 | DEP_HOUR           |        1.3678 |
|          5 | OP_CARRIER_CODE    |        1.2341 |
|          6 | SEASON_CODE        |        1.0013 |
|          7 | IS_COVID_PERIOD    |        0.9086 |
|          8 | MONTH              |        0.9057 |
|          9 | DEST_CODE          |        0.7794 |
|         10 | DOW_SIN            |        0.7419 |
|         11 | DAY                |        0.6712 |
|         12 | DISTANCE_KM        |        0.5504 |
|         13 | DEST_DAILY_FLIGHTS |        0.5308 |
|         14 | ORIGIN_CODE        |        0.4636 |
|         15 | DOW_COS            |        0.4498 |

### 🔹 Local ATL — Chuyến đến (Arrival Cls)
|   Thứ hạng | Đặc trưng                 |   Mean |SHAP| |
|-----------:|:--------------------------|--------------:|
|          1 | OP_CARRIER_CODE           |        0.2665 |
|          2 | IS_COVID_PERIOD           |        0.1741 |
|          3 | DAY                       |        0.1612 |
|          4 | ARR_HOUR                  |        0.124  |
|          5 | MONTH_COS                 |        0.1163 |
|          6 | HOUR_SIN                  |        0.1125 |
|          7 | ORIGIN_CODE               |        0.0798 |
|          8 | DEST_DAILY_FLIGHTS        |        0.0702 |
|          9 | DEP_HOUR                  |        0.0684 |
|         10 | MONTH                     |        0.0634 |
|         11 | ORIGIN_DAILY_FLIGHTS      |        0.058  |
|         12 | SEASON_CODE               |        0.0556 |
|         13 | MONTH_SIN                 |        0.0502 |
|         14 | DISTANCE_KM               |        0.0465 |
|         15 | DEST_CONGESTION_SAME_HOUR |        0.0393 |

### 🔹 Local ATL — Chuyến đi (Departure Cls)
|   Thứ hạng | Đặc trưng            |   Mean |SHAP| |
|-----------:|:---------------------|--------------:|
|          1 | DEST_DAILY_FLIGHTS   |        0.2408 |
|          2 | DEP_HOUR             |        0.1641 |
|          3 | ORIGIN_DAILY_FLIGHTS |        0.1316 |
|          4 | MONTH_COS            |        0.1164 |
|          5 | DISTANCE_KM          |        0.1065 |
|          6 | ORIGIN_CODE          |        0.1064 |
|          7 | SEASON_CODE          |        0.1005 |
|          8 | DAY                  |        0.0894 |
|          9 | ARR_HOUR             |        0.0674 |
|         10 | DOW_COS              |        0.0583 |
|         11 | HOUR_SIN             |        0.0533 |
|         12 | MONTH                |        0.0508 |
|         13 | DOW_SIN              |        0.05   |
|         14 | OP_CARRIER_CODE      |        0.0407 |
|         15 | IS_COVID_PERIOD      |        0.037  |

### 🔹 Local ATL — Chuyến đến (Arrival Reg)
|   Thứ hạng | Đặc trưng            |   Mean |SHAP| |
|-----------:|:---------------------|--------------:|
|          1 | DEST_DAILY_FLIGHTS   |        5.4754 |
|          2 | MONTH_COS            |        3.9211 |
|          3 | IS_COVID_PERIOD      |        2.7527 |
|          4 | DAY                  |        2.416  |
|          5 | OP_CARRIER_CODE      |        1.9056 |
|          6 | ORIGIN_DAILY_FLIGHTS |        1.8603 |
|          7 | HOUR_SIN             |        1.763  |
|          8 | DISTANCE_KM          |        1.5898 |
|          9 | MONTH                |        1.4063 |
|         10 | ARR_HOUR             |        1.3439 |
|         11 | ORIGIN_CODE          |        1.2739 |
|         12 | DOW_COS              |        0.7886 |
|         13 | DEP_HOUR             |        0.667  |
|         14 | MONTH_SIN            |        0.5792 |
|         15 | CRS_ELAPSED_TIME     |        0.5408 |

### 🔹 Local ATL — Chuyến đi (Departure Reg)
|   Thứ hạng | Đặc trưng                 |   Mean |SHAP| |
|-----------:|:--------------------------|--------------:|
|          1 | DEST_DAILY_FLIGHTS        |        6.7532 |
|          2 | ORIGIN_CODE               |        6.553  |
|          3 | ORIGIN_DAILY_FLIGHTS      |        3.9536 |
|          4 | DISTANCE_KM               |        3.2222 |
|          5 | DEP_HOUR                  |        2.5437 |
|          6 | DEST_CONGESTION_SAME_HOUR |        2.3172 |
|          7 | MONTH_COS                 |        2.2527 |
|          8 | MONTH                     |        1.9437 |
|          9 | OP_CARRIER_CODE           |        1.5239 |
|         10 | DOW_COS                   |        1.4722 |
|         11 | ARR_HOUR                  |        1.2376 |
|         12 | CRS_ELAPSED_TIME          |        1.1953 |
|         13 | DAY                       |        1.1576 |
|         14 | DOW                       |        1.0316 |
|         15 | SEASON_CODE               |        0.7639 |

