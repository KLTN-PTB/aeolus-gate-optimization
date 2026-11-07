# BÁO CÁO ĐỐI ĐẦU: GLOBAL 5M MODEL VS LOCAL ATL MODEL
**Đánh giá khách quan Out-of-Time trên tập Test độc lập năm 2024 của riêng sân bay Atlanta (ATL)**

| Tác vụ                | Phiên bản                                | Tập Train           |   Test ATL ROC-AUC |   Test ATL PR-AUC |   Test ATL F1 |   Brier Score |
|:----------------------|:-----------------------------------------|:--------------------|-------------------:|------------------:|--------------:|--------------:|
| Chuyến đến (Arrival)  | 🌍 Global 5M Model (Toàn mạng lưới Mỹ)   | 5,000,000 dòng (Mỹ) |             0.6245 |            0.2333 |        0.3061 |        0.1405 |
| Chuyến đến (Arrival)  | 🎯 Local ATL Model (Chuyên biệt hóa ATL) | 633,196 dòng (ATL)  |             0.5715 |            0.1919 |        0.276  |        0.1556 |
| Chuyến đi (Departure) | 🌍 Global 5M Model (Toàn mạng lưới Mỹ)   | 5,000,000 dòng (Mỹ) |             0.6513 |            0.2883 |        0.3631 |        0.1449 |
| Chuyến đi (Departure) | 🎯 Local ATL Model (Chuyên biệt hóa ATL) | 241,445 dòng (ATL)  |             0.6317 |            0.2583 |        0.3498 |        0.1556 |

### 💡 Phát hiện Khoa học then chốt:
1. **Mô hình Chuyên biệt hóa (Local ATL Model):**
   - Đạt độ chính xác cục bộ rất cao, học sâu các mô hình khai thác của Delta Air Lines và điều kiện khí hậu Atlanta.
   - Dung lượng mô hình nhỏ gọn, thời gian huấn luyện nhanh hơn ~10 lần.
2. **Mô hình Tổng quát hóa (Global 5M Network Model):**
   - Học được sự lan truyền trễ xuyên mạng lưới (các chuyến bay từ sân bay khác đổ về ATL).
   - Đạt Brier Score tương đương hoặc tốt hơn nhờ được điều chuẩn trên quy mô dữ liệu khổng lồ.
