# Tóm tắt các điểm cần tối ưu cho 2 notebook huấn luyện

Áp dụng cho `tabular_classification_notebook.ipynb` và `tabular_regression_notebook.ipynb`
(dữ liệu toàn mạng: ~41.74M dòng Train, ~6.64M Valid, ~6.28M Test).

> Ghi chú: nội dung dựa trên việc đọc code, chưa chạy trên dữ liệu thật. Mọi mức cải thiện tốc độ/RAM cần được đo lại (`time.perf_counter()`, `X.memory_usage().sum()/1e9`).

---

## 1. Hiện trạng: đã làm tốt và chưa xong

**Đã làm tốt**
- Nạp từng file rồi hạ kiểu dữ liệu (float32, int nhỏ), có tham số lấy mẫu.
- Early stopping cho XGBoost/LightGBM; `subsample_freq=1` cho LightGBM.
- LR/Ridge fit trên mẫu con; `gc.collect()` sau mỗi mô hình (classification).
- Thay Stacking K-Fold bằng blending (không còn 9-12 lần huấn luyện lại).

**Chưa xong**

| Vấn đề | Trạng thái |
|---|---|
| Chỉ đọc các cột cần dùng; chế độ `dev` chạy nhanh | Chưa có |
| Copy dữ liệu | Còn: `X_va_arr.copy()`, `X_te_arr.copy()` ở cell blending/export |
| `predict_proba` theo khối | Chưa có (dự đoán 6M dòng một lần) |
| Giải phóng RAM giữa hai bài toán (Đến/Khởi hành) | Chưa: cell sau còn dùng `X_*_arr` |
| Chọn Champion | Vẫn theo Test (ROC-AUC / MAE) → chạm Sealed Holdout |

---

## 2. Cả hai notebook

1. **Lưu dự đoán lúc huấn luyện, không dự đoán lại.** Ghi xác suất/giá trị dự đoán của Valid/Test vào dict ngay sau khi fit; cell blending và export lấy từ dict (bỏ hẳn các `.copy()` và lần `predict` thứ hai).
   ```python
   PRED_CACHE[(task_label, m_type)] = {"val": p_val, "test": p_test}
   ```
2. **Giải phóng RAM sau mỗi bài toán.** Lưu `FEATURE_NAMES` và dự đoán, rồi `del X_tr_*, X_va_*, X_te_*; gc.collect()` trước khi nạp bài toán tiếp theo (Cell 14/16/18 phải chuyển sang dùng cache).
3. **Early stopping trên mẫu con Valid (~1M dòng), không phải toàn bộ 6.6M.**
   - Classification: `eval_metric="auc"` (mặc định hiện là logloss, lệch với `scale_pos_weight` và với chỉ số báo cáo).
   - Regression: `eval_metric="mae"` (hoặc metric khớp mục tiêu).
4. **Dự đoán theo khối** (~1M dòng mỗi lần) cho Valid/Test.
5. **Đường cong học trước khi chạy full:** huấn luyện với 2M, 5M, 10M và toàn bộ dòng, xem AUC/MAE theo thời gian. Nếu đường cong phẳng sau một mốc, không cần chạy 41.7M dòng.
6. **Chọn Champion theo Val**, không theo Test. Test chỉ để báo cáo cuối.
7. **Đọc chỉ các cột cần dùng** (`columns=`), loại sớm cột thời tiết nếu theo Protocol E002; thêm chế độ `dev` (mẫu ~1M, không nạp Test) và `full`.
8. **Dùng chung một `CategoricalDtype`** cho Train/Valid/Test (hợp các giá trị), thay vì `astype("category")` riêng từng tập, để mã khớp nhau.
9. **Dùng số lõi vật lý** cho `n_jobs` thay vì `-1`; nếu có GPU NVIDIA, `device="cuda"` cho XGBoost.
10. **Lấy mẫu ngẫu nhiên** thay vì cắt `X.iloc[:cap]` (cắt đầu sẽ làm lệch theo năm).

---

## 3. Notebook classification

- **CatBoost trên 41.7M dòng** với 3 cột categorical nhiều mức: rất có thể là mô hình chậm và tốn RAM nhất. Huấn luyện trên mẫu 2-3M dòng hoặc bỏ khỏi vòng lặp chính.
- **LR mất các cột số nguyên:** `numeric_cols` chỉ chọn `float32/float64`, nhưng sau hạ kiểu nhiều cột là `int8/int16`. Dùng `pd.api.types.is_numeric_dtype` (và loại các cột categorical).
- **Trọng số lớp không nhất quán:** sqrt SPW (boosting), `balanced` (CatBoost, LR). Chọn một quy ước, hoặc huấn luyện không trọng số rồi calibrate.
- **Blending nên dùng logit** của xác suất làm đầu vào cho meta-learner (LR).
- **Champion là blending:** file `.joblib` hiện chỉ chứa meta-learner, không chạy độc lập. Lưu cả các mô hình cơ sở (`{"base_models":..., "meta":...}`).
- **Xác suất xuất cho CP-SAT chưa calibrate** nếu Champion là mô hình đơn huấn luyện với `scale_pos_weight`; calibrate trên Valid trước khi dùng.
- `LogisticRegression(n_jobs=-1)` không có tác dụng với bài toán nhị phân (lbfgs).

---

## 4. Notebook regression

**Lỗi cần sửa ngay**
- **Cell 14 sẽ lỗi `KeyError`:** `reg_scalers_arrival['xgb']` không tồn tại (dict chỉ có khóa `'ridge'`). XGB cũng được huấn luyện trên dữ liệu chưa scale, nên không được scale trước khi dự đoán.
- **Champion là blending lưu sai file:** khóa trong dict là `'fast_blending'` nhưng tên champion là `'fast_blending_regressor'`. Đoạn fallback lấy khóa đầu tiên (`lgbm`), nên file `.joblib` là LGBM trong khi metadata ghi số của blending.

**Cải thiện hiệu quả**
- Mô hình `'rf'` thật ra là `HistGradientBoostingRegressor` (tự cắt 10% của 41.7M dòng làm validation, chậm, ít khác LGBM/XGB): bỏ hoặc huấn luyện trên mẫu con.
- **Chưa dùng `category` dtype:** mã sân bay/hãng bị coi là số; dùng chung `CategoricalDtype` và `enable_categorical=True` cho XGBoost.
- **Loss và metric lệch nhau:** huấn luyện bằng bình phương sai số nhưng chọn mô hình theo MAE. Thử `objective="regression_l1"` hoặc Huber, và cân nhắc giới hạn (clip) giá trị trễ cực lớn khi huấn luyện.
- Ridge chỉ thấy cột float (cùng vấn đề với LR): dùng `is_numeric_dtype`.
- Bỏ các bản copy ở Cell 14/16; dùng dự đoán đã lưu trong cache.

---

## 5. Thứ tự thực hiện đề xuất

1. Lưu dự đoán vào cache + giải phóng dữ liệu sau mỗi bài toán (chặn OOM).
2. Early stopping trên mẫu con Valid với metric đúng (AUC / MAE).
3. Sửa hai lỗi regression (Cell 14, lưu champion blending).
4. Chọn Champion theo Val; lưu blending kèm mô hình cơ sở.
5. Đường cong học để quyết định có cần chạy toàn bộ 41.7M dòng.
6. Bỏ/giảm CatBoost và HGB; sửa cột số nguyên cho LR/Ridge.
7. Chế độ `dev`/`full`, chỉ đọc cột cần dùng, dự đoán theo khối, dtype categorical chung.

Sau khi làm xong, ghi lại `Fit (s)` và `Val ROC-AUC` (hoặc `Val MAE`) của từng mô hình để đánh giá hiệu quả so với thời gian chờ.
