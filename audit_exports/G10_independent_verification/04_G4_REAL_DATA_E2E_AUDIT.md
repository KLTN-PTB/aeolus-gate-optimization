# AEOLUS-G10 — DELIVERABLE 04: G4 REAL-DATA END-TO-END PIPELINE & TURN PAIRING AUDIT

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Senior Aviation Data Engineer & End-to-End Validation Architect  
**Target Phase:** Phase G4 Native Real-Data E2E Pipeline & Verified Pairing Engine  

---

## 1. MỤC TIÊU VÀ NGUỒN BẰNG CHỨNG KIỂM TOÁN

Nhiệm vụ kiểm toán độc lập là đánh giá tính chân thực của đợt thử nghiệm trên dữ liệu thực tế (Real-Data E2E) tại Phase G4, làm rõ các tuyên bố về "Verified Aircraft Turn Pairing" và kiểm tra run manifest của đợt chạy pilot 200 chặng bay:
- Mã nguồn: `src/data/real_data_loader.py`, `src/data/canonical_time.py`, `src/simulation/verified_pairing.py`, `scripts/run_native_dual_core_pipeline.py`.
- Artifact đợt chạy Pilot: `artifacts/remediation/native_dual_core_g4_pilot/` (`run_manifest.json`, `turn_pairing_audit.json`, `optimization_result.json`).
- Artifact đợt chạy Inferred: `artifacts/remediation/native_dual_core_g4_pilot_inferred/` (`run_manifest.json`, `turn_pairing_audit.json`).

---

## 2. DỮ LIỆU KIỂM TOÁN CHI TIẾT TỪ RUN MANIFEST CỦA PILOT 200 FLIGHT LEGS

Bảng dưới đây trích xuất nguyên văn các trường thông số từ `artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json`:

| Trường Thông tin (Manifest Field) | Giá trị Kiểm toán G10 | Diễn giải & Đánh giá |
| :--- | :--- | :--- |
| **Pipeline Identifier** | `NativeDualCorePredictThenOptimizePipeline` | Pipeline tích hợp native |
| **Timestamp (UTC)** | `2026-10-11T10:39:01.114341+00:00` | Phiên chạy thực nghiệm G4 |
| **Input Source / Period** | BTS TranStats ATL (Tháng 11/2023 - Thanksgiving Peak) | Dữ liệu chuyến bay thực tế từ BTS |
| **Raw Flight Legs Processed** | **200 chặng bay** (100 Inbound, 100 Outbound) | 100 chuyến đến ATL, 100 chuyến đi từ ATL |
| **Accepted Flight Legs** | **200 chặng bay** | 0 chặng bị từ chối do lỗi schema |
| **Verified Aircraft Rotations** | **0 (KHÔNG CÓ CẶP QUAY ĐẦU NÀO ĐƯỢC XÁC MINH)** | **`verified_pairs_count: 0`** |
| **Inferred Turnaround Pairs** | **0 (trong pilot run) / 59 (trong inferred run)** | Pilot run không ghép cặp suy diễn |
| **Unmatched Inbound Flights** | **100 chuyến bay** | 100% chuyến đến không tìm được chuyến đi |
| **Unmatched Outbound Flights** | **100 chuyến bay** | 100% chuyến đi không tìm được chuyến đến |
| **Turns Synthesized** | **200 turns** | Toàn bộ 200 chuyến xử lý dưới dạng singleton |
| **Unmatched Dwell Assumption** | `SYNTHETIC_DWELL` (gán dwell giả lập 60 phút) | `occupancy_duration_min = 84` (60m dwell + buffer) |
| **Native Arrival Model ID & SHA** | `b5_ngboost_student_t` (`e7e7462f...`) | Khớp 100% checksum mô hình đóng băng |
| **Native Departure Model ID & SHA** | `departure_certified_point_v1` (`e483df5f...`) | Khớp 100% checksum mô hình đóng băng |
| **Synthetic Fallback Occurred?** | **False (No fallback for flight records)** | Dữ liệu lịch trình là chuyến bay thật BTS |
| **Solver Status & Objective** | `OPTIMAL` (Objective Value: `0.0`) | Giải tối ưu với 30 contact gates, 5 overflow |
| **Runtime** | `1.280,88 ms` (1,28 giây) | Thời gian giải đáp ứng thời gian thực |
| **Independent Verification** | `is_valid: True` (0 hard constraint violations) | Thẩm định độc lập xác nhận nghiệm khả thi |

---

## 3. PHÂN BIỆT BẮT BUỘC GIỮA 5 KHÁI NIỆM TRONG VẬN HÀNH THỰC TẾ

Để bảo vệ tính toàn vẹn học thuật của khóa luận trước hội đồng, sinh viên và nhóm nghiên cứu **BẮT BUỘC PHẢI PHÂN BIỆT RÕ RÀNG 5 KHÁI NIỆM**:

```
+--------------------------------------------------------------------------------------------------+
| 1. CHUYẾN BAY THẬT (Real Flight Legs):                                                           |
|    - 200 chuyến bay được trích xuất từ BTS TranStats năm 2023 với giờ đến/đi thực tế.            |
|    - ĐÃ ĐẠT: Toàn bộ 200 bản ghi lịch trình là dữ liệu hàng không thực tế 100%.                 |
+--------------------------------------------------------------------------------------------------+
| 2. CHU TRÌNH TÀU BAY XÁC THỰC (Verified Real Aircraft Rotations):                                |
|    - Chuỗi hành trình thực tế của cùng MỘT THÂN TÀU BAY VẬT LÝ (cần có số hiệu đuôi TAIL_NUM).    |
|    - CHƯA ĐẠT (0 ROTATIONS): Dữ liệu công khai BTS khuyết thiếu TAIL_NUM.                         |
|    - Số lượng verified rotation thực chất đo lường được là đúng bằng 0!                          |
+--------------------------------------------------------------------------------------------------+
| 3. CHU TRÌNH SUY DIỄN HEURISTIC (Inferred Rotations):                                            |
|    - Các cặp ghép phỏng đoán theo thuật toán dựa trên: cùng hãng, cùng kích cỡ, thời gian 45-180m.|
|    - ĐẠT ĐƯỢC 59 CẶP trong đợt chạy Inferred (118 chặng bay ghép + 82 chặng bay đơn lẻ).         |
+--------------------------------------------------------------------------------------------------+
| 4. HẠ TẦNG CỔNG GIẢ LẬP (Synthetic Gate Infrastructure):                                        |
|    - Dữ liệu BTS không công bố cổng đỗ thực tế của từng chuyến bay.                              |
|    - 30 cổng tiếp xúc và 5 bãi xa trong bài toán được mô hình hóa theo hình học thực tế của Concourse|
|      nhưng các gán ban đầu (nominal gates) là giả lập cấu hình.                                  |
+--------------------------------------------------------------------------------------------------+
| 5. THỰC NGHIỆM MỞ RỘNG GIẢ LẬP (Synthetic Scalability Experiments):                              |
|    - Các kịch bản N=100, 200, 300 trong G5 benchmark sử dụng chuyến bay sinh nhân tạo (synthetic).  |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. KẾT LUẬN KIỂM TOÁN VỀ TUYÊN BỐ "VERIFIED ROTATIONS"

1. **Phát hiện vi phạm học thuật:** Báo cáo G4 và Khóa luận G9 đã sử dụng cụm từ *"Verified Turn Pairing"* và tuyên bố đã nghiệm thu chu trình quay đầu tàu bay trên dữ liệu thực tế. Tuy nhiên, trong toàn bộ kho artifact của repository:
   $$\text{verified\_pairs\_count} = \mathbf{0}$$
2. **Bản chất thực tế của đợt chạy G4 Pilot:**
   - 100 chuyến bay đến và 100 chuyến bay đi từ BTS được nạp vào hệ thống.
   - Do không có số hiệu đuôi tàu bay, module ghép cặp xác thực không thể ghép bất kỳ cặp nào (`verified_pairs_count = 0`).
   - Module xử lý dự phòng đã chuyển đổi toàn bộ 200 chuyến bay này thành **200 chuyến bay đơn lẻ độc lập (singletons)**, gán cho mỗi chuyến một khoảng dừng giả lập danh nghĩa (`SYNTHETIC_DWELL = 60 phút`) để bộ giải CP-SAT phân bổ cổng đỗ.
3. **Trong đợt chạy Inferred:** Khi kích hoạt chế độ suy diễn heuristic (`Inferred Turnaround Mode`), thuật toán đã liên kết được **59 cặp turnaround suy diễn** và 82 chuyến đơn lẻ, nhưng đây là **inferred rotations, TUYỆT ĐỐI KHÔNG PHẢI verified rotations**.
4. **Khuyến nghị bắt buộc:** Trong bản in khóa luận và slide thuyết trình, sinh viên phải công bố chính xác:  
   *"Thực nghiệm dữ liệu thực tế sử dụng 200 chuyến bay BTS Thanksgiving 2023, trong đó bao gồm 59 cặp quay đầu suy diễn heuristic và 82 chuyến bay đơn lẻ. Hệ thống ghi nhận 0 chu trình xác thực theo số hiệu đuôi máy bay do giới hạn dữ liệu công khai của BTS TranStats."*
