# AEOLUS-G0: KẾ HOẠCH VÀ QUY TRÌNH PHỤC HỒI AN TOÀN (ROLLBACK & PRESERVATION PLAN)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Giai đoạn:** AEOLUS-G0 — Baseline, Source Preservation & Rollback Gate  
**Thời điểm thực hiện:** 2026-10-11T16:33:00+07:00  
**Vai trò:** Git Safety Engineer, Principal Software Architect  

---

## 1. Mốc Phục hồi Nền tảng (Anchor Baseline)

Mọi hoạt động điều chỉnh (remediation) trong các giai đoạn tiếp theo (G1, G2...) phải được neo giữ chắc chắn vào điểm phục hồi nền tảng:

* **Mã băm Commit Neo giữ (Base Anchor Commit):**
  $$\mathbf{c95caef53808a561b1a7d3a5a09399cc52f754f5}$$
* **Nhánh Làm việc Hiện hành:** `feature/dashboard-and-remediation-p07-p09`
* **Cam kết Bảo toàn:** Tệp kê khai `04_EVIDENCE_MANIFEST.json` lưu giữ đầy đủ mã băm SHA-256 của 25 tệp artifact quan trọng làm thước đo đối soát trước và sau mọi can thiệp kỹ thuật.

---

## 2. Chiến lược Phân nhánh Điều chỉnh An toàn (Branching Strategy)

Để đảm bảo không bao giờ làm ô nhiễm nhánh chính hoặc làm mất mát dữ liệu khi có sự cố:
1. **Không can thiệp trực tiếp trên nhánh gốc:**
   Trước khi bắt đầu bất kỳ sửa đổi nghiệp vụ nào, phải tạo nhánh chuyên trách:
   ```bash
   git checkout -b remediation/g1-scientific-alignment c95caef53808a561b1a7d3a5a09399cc52f754f5
   ```
2. **Phạm vi tệp được phép sửa đổi theo từng giai đoạn:**
   * *Giai đoạn G1 (Khoa học & Mô hình):* Chỉ được phép sửa đổi các script tạo artifact và báo cáo khoa học (ví dụ: `scripts/generate_p08_validation_artifacts.py`, `docs/remediation/`). Cấm sửa đổi cấu trúc giải thuật solver CP-SAT lõi đã đóng băng.
   * *Giai đoạn G2 (Văn bản Khóa luận):* Chỉ tạo tệp mới trong `reports/final/` và `reports/slides/`. Cấm sửa đổi mã nguồn Python.

---

## 3. Quy trình Phục hồi Từng Tệp và Từng Commit (Non-Destructive Rollback Procedures)

### 3.1. Phục hồi Từng Tệp Riêng lẻ (Single File Rollback)
Nếu một tệp nguồn bị chỉnh sửa lỗi hoặc làm suy giảm kết quả kiểm thử, thực hiện khôi phục chính xác tệp đó về trạng thái G0 mà không làm ảnh hưởng đến các tệp khác:
```bash
# Khôi phục tệp về trạng thái commit neo giữ c95caef
git checkout c95caef53808a561b1a7d3a5a09399cc52f754f5 -- <đường_dẫn_tệp>
```

### 3.2. Phục hồi Toàn bộ Nhánh về Trạng thái G0 (Full Branch Rollback)
Nếu toàn bộ đợt điều chỉnh gặp trục trặc hệ thống:
```bash
# 1. Chuyển về nhánh an toàn c95caef
git checkout feature/dashboard-and-remediation-p07-p09

# 2. Xóa nhánh remediation bị lỗi mà không ảnh hưởng nhánh chính
git branch -D remediation/g1-scientific-alignment
```

### 3.3. Quy trình Đối soát Toàn vẹn Checksum Artifact Trước & Sau
Trước và sau mỗi đợt can thiệp kỹ thuật, chạy script kiểm tra đối soát với `04_EVIDENCE_MANIFEST.json`:
```python
import hashlib, json
with open("remediation_evidence/G0_baseline/04_EVIDENCE_MANIFEST.json") as f:
    manifest = json.load(f)

for item in manifest["verified_model_checkpoints"]:
    current_hash = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    assert current_hash == item["sha256"], f"CẢNH BÁO: Checkpoint {item['path']} bị biến đổi!"
```

---

## 4. Bằng chứng Xác thực Kịch bản Rollback Giả lập (Sandbox Simulation Evidence)

Kiểm toán viên đã tiến hành thử nghiệm giả lập kịch bản rollback trong môi trường sandbox cô lập tại `remediation_evidence/G0_baseline/sandbox/`:
1. Tạo tệp giả lập trạng thái gốc $V_1$ $\to$ Tính SHA-256 ($H_1$).
2. Mô phỏng sửa đổi gây đột biến sang trạng thái $V_2$ $\to$ Tính SHA-256 ($H_2 \ne H_1$).
3. Thực hiện quy trình Rollback phục hồi về $V_1$ $\to$ Tính SHA-256 ($H_3$).
4. **Kết quả quan sát thực tế:** $H_1 == H_3: \mathbf{True}$ (Khôi phục toàn vẹn 100% từng byte dữ liệu).
5. Xóa bỏ thư mục sandbox an toàn, không để lại rác trong kho lưu trữ.
