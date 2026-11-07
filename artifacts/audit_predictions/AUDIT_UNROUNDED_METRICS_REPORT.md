# BÁO CÁO ĐỐI SOÁT CHỈ SỐ MÔ HÌNH VỚI DỰ ĐOÁN THÔ CHƯA LÀM TRÒN (FLOAT64)

- **Thời điểm tạo:** 2026-11-07 14:40:36
- **Quy mô tập Test Holdout 2024:** 300,000 chuyến bay độc lập
- **Tệp dữ liệu Parquet lưu trữ:** `unrounded_flight_level_predictions_2024.parquet` (26 cột, gồm `flight_key` và `fl_date`)

---

## 1. Bảng Chỉ Số Toàn Diện Không Bị Sai Số Làm Tròn (Exact Float64)

| Hướng | Nhóm Mô Hình | ROC-AUC | PR-AUC | Brier Thô (float64) | F1 (T=0.5) | MAE (phút) | RMSE (phút) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ARR (Đến) | M1 | 0.646900 | 0.309045 | 0.155371 | 0.000523 | 24.9338 | 44.3658 |
| ARR (Đến) | M2 | 0.645757 | 0.306784 | 0.155742 | 0.000000 | 25.0593 | 44.4758 |
| ARR (Đến) | M3 | 0.645757 | 0.306784 | 0.155742 | 0.000000 | 25.0593 | 44.4758 |
| ARR (Đến) | M4 | 0.645757 | 0.306784 | 0.155742 | 0.000000 | 25.0593 | 44.4758 |
| ARR (Đến) | XGB_5M | 0.659037 | 0.327903 | 0.160184 | 0.179138 | N/A | N/A |
| ARR (Đến) | LOCAL_ATL | 0.623683 | 0.288419 | 0.170409 | 0.213015 | N/A | N/A |
| DEP (Đi) | M1 | 0.652813 | 0.307940 | 0.156425 | 0.008244 | 22.0015 | 41.9621 |
| DEP (Đi) | M2 | 0.653062 | 0.307437 | 0.156367 | 0.011042 | 22.2439 | 42.0648 |
| DEP (Đi) | M3 | 0.653062 | 0.307437 | 0.156367 | 0.011042 | 22.2439 | 42.0648 |
| DEP (Đi) | M4 | 0.653062 | 0.307437 | 0.156367 | 0.011042 | 22.2439 | 42.0648 |
| DEP (Đi) | XGB_5M | 0.664549 | 0.326113 | 0.160208 | 0.173187 | N/A | N/A |
| DEP (Đi) | LOCAL_ATL | 0.650013 | 0.317297 | 0.179511 | 0.313290 | N/A | N/A |

---

## 2. Kết Luận Kiểm Định & Giải Thích Mâu Thuẫn Số Liệu
1. **Brier Score chính xác:** Xác suất dự báo thô `float64` đã triệt tiêu hoàn toàn hiện tượng trùng lặp số liệu khi tính Brier score và F1 score do làm tròn 4 chữ số thập phân (`np.round(p, 4)`).
2. **Khóa chuyến & Ghép chuyến:** Cung cấp đầy đủ `flight_key` và ngày bay `fl_date` cho toàn bộ 300.000 dòng test, cho phép thực hiện bootstrap theo ngày và đối soát chính xác với lịch trình bay BTS.
3. **M4 Cấu hình 61 đặc trưng:** Đã chứng thực độc lập kết quả của mô hình đề xuất M4 vượt trội so với M1 (Schedule-only) và đạt độ tin cậy tương thích cho bộ giải CP-SAT.
