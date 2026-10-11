# UI-R05: Solver & Independent Verifier Integration

## 1. Nguyên Tắc An Toàn Thực Thi (Execution Safety Principles)
1. **Không Tự Động Giải Ngầm (Zero Implicit Solving):**
   - Khi người dùng điều hướng vào trang 03, thay đổi bộ lọc, trượt thanh zoom, chọn chuyến bay, hoặc mở Research Inspector, hệ thống **tuyệt đối không kích hoạt solver**.
   - Khi chưa nhấn nút tối ưu hóa hoặc chưa có checkpoint, trang 03 luôn hiển thị Kế hoạch Danh định Gốc (Nominal Plan) cùng trạng thái `CHƯA PHÂN BỔ (IDLE)`.
2. **Kích Hoạt Tường Minh (Explicit User Action):**
   - Lệnh giải chỉ được thực thi khi người dùng nhấn nút `⚡ TỐI ƯU HÓA NGAY (RUN SOLVER)`.
3. **Ngưỡng An Toàn Quy Mô (Size Limit Safety Guard):**
   - Bộ giải tương tác trực tiếp chỉ tiếp nhận các kịch bản có số lượng chuyến bay $N \le 150$.
   - Các kịch bản lớn hơn (ví dụ mega-hub 1500 chuyến bay) phải được xử lý ngoại tuyến và nạp qua precomputed artifacts, tránh làm treo trình duyệt hoặc quá tải CPU máy chủ.

## 2. Các Bộ Giải Hỗ Trợ & Chính Sách Dự Phòng (Fallback Policy)
- **CP-SAT (Sparse Interval):** Giải mô hình quy hoạch nguyên ràng buộc chính xác, sử dụng các biến khoảng rời rạc hóa.
- **Deterministic Greedy:** Thuật toán tham lam tất định ưu tiên cổng theo trọng số và thời gian đến.
- **Hybrid (Greedy + CP-SAT):** Khởi tạo lời giải khả thi bằng Greedy trước khi tối ưu hóa cục bộ với CP-SAT.
- **Chính sách Fallback minh bạch:** Nếu CP-SAT chạm ngưỡng timeout hoặc gặp sự cố mô hình và phải chuyển sang Greedy fallback, cờ `fallback_used` được ghi nhận rõ ràng vào `SolverRunView` và hiển thị huy hiệu cảnh báo trên giao diện, không ngụy tạo kết quả thành CP-SAT thuần túy.

## 3. Tích Hợp Kiểm Chứng Ràng Buộc Độc Lập (Independent Verification)
Nhằm tuân thủ chuẩn liêm chính khoa học của Aeolus, bộ giải không có quyền tự chứng nhận tính hợp lệ của chính nó. Mọi lời giải phải được thẩm định độc lập bởi `verify_hard_constraints_independently` (`src/optimization/evaluation.py`):

```python
diag = verify_hard_constraints_independently(
    flights=flights,
    gates=gates,
    assignments=raw_result.assignments,
)
```

Trình kiểm chứng thẩm tra độc lập 4 nhóm ràng buộc cứng:
1. **Gán duy nhất (Uniqueness):** 100% chuyến bay được phân vào đúng một vị trí đỗ hợp lệ.
2. **Xung đột không gian - thời gian (Non-overlap):** 0 cặp chuyến bay nào có khoảng nửa mở $[A_{pred}, T_{release})$ giao nhau trên cổng tiếp xúc có capacity = 1.
3. **Đệm giãn cách tối thiểu (Separation buffer):** 100% khoảng trống giữa các lượt đỗ liên tiếp trên cùng một cổng $\ge \Delta_{buffer}$.
4. **Sức chứa bãi đỗ từ xa (Remote capacity):** Số chuyến bay đỗ đồng thời tại bãi đỗ từ xa không vượt quá sức chứa $K$.

## 4. Ánh Xạ Trạng Thái Trung Thực (Honest Status Mapping)
> [!IMPORTANT]
> Hệ thống nghiêm cấm việc gắn nhãn `OPTIMAL` cho lời giải chưa được chứng minh tối ưu toàn cục.

| Bộ giải / Thuật toán | Điều kiện Toán học | Trạng thái Hiển thị | Huy hiệu Giao diện |
| :--- | :--- | :--- | :--- |
| **CP-SAT** | Gap = 0.0, Chứng minh tối ưu | `OPTIMAL` / `OPTIMAL_PROVEN` | `aeolus-badge-optimal` ("TỐI ƯU TUYỆT ĐỐI") |
| **CP-SAT** | Tìm thấy lời giải khả thi nhưng chưa chứng minh tối ưu | `FEASIBLE` / `FEASIBLE_FOUND` | `aeolus-badge-success` ("KHẢ THI (FEASIBLE)") |
| **Greedy / Heuristic** | Tìm thấy lời giải hợp lệ (0 vi phạm) | `FEASIBLE` / `HEURISTIC_STOP` | `aeolus-badge-info` ("KHẢ THI (GREEDY)") |
| **Mọi bộ giải** | Tồn tại $\ge 1$ vi phạm ràng buộc cứng | `INVALID` / `INFEASIBLE` | `aeolus-badge-error` ("VI PHẠM RÀNG BUỘC") |
| **Chưa chạy** | Không có run trong session hiện tại | `IDLE` / `NOT_RUN` | `aeolus-badge-neutral` ("CHƯA PHÂN BỔ") |
| **Tham số thay đổi** | Draft config khác Executed config | `STALE_RESULT` | `aeolus-badge-warning` ("KẾT QUẢ ĐÃ CŨ") |
