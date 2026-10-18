# AEOLUS-G12A — DELIVERABLE 01: BASELINE INVENTORY & SAFETY SNAPSHOT

---

**Task Identifier:** `AEOLUS-G12A` — Causal Online Recourse Remediation & Scientific Verification  
**Auditor & Implementation Role:** Senior Operations Research Engineer, Causal Simulation Engineer, Python Software Architect, Scientific Verification Engineer  
**Date & Timestamp:** 2026-10-12T17:05:00+07:00  
**Repository Working Directory:** `D:\Study\Code\Python\Aelous`  
**Active Branch:** `remediation/g7-regression`  
**Base Commit SHA:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`  
**Working Tree Status:** Pre-Remediation Working Tree Verified & Snapshotted  

---

## 1. MỤC TIÊU VÀ NGUYÊN TẮC AN TOÀN TUYỆT ĐỐI (NON-NEGOTIABLE SAFETY RULES)

Trước khi tiến hành sửa đổi bất kỳ tệp mã nguồn nào trong hệ thống, kỹ sư thực hiện rà soát và thiết lập hàng rào an toàn theo đúng các quy tắc bắt buộc:

1. **Không sửa đổi Checkpoint ML và Raw Data:** Giữ nguyên toàn bộ tệp mô hình trong `artifacts/` và dữ liệu trong `data/raw/`.
2. **Bảo tồn tuyệt đối các Artifacts đã đóng băng:**
   - `artifacts/remediation/monte_carlo/` (P09 Frozen Baseline — TUYỆT ĐỐI KHÔNG GHI ĐÈ).
   - `artifacts/remediation/benchmarks/` (G5 Fair Benchmark Frozen — KHÔNG GHI ĐÈ).
   - `artifacts/remediation/native_dual_core_g4_pilot/` (G4 Frozen — KHÔNG GHI ĐÈ).
   - `audit_exports/` (G10 & G11 Packages — KHÔNG XÓA, KHÔNG SỬA ĐỔI).
3. **Bảo vệ Lịch sử Git:** Không thực hiện bất kỳ lệnh `git commit`, `git push`, `git reset`, `git clean -fd`, `git checkout .`, `git rebase` nào.
4. **Bảo tồn Working Tree Uncommitted:** Xuất snapshot toàn bộ diff hiện tại vào `remediation_evidence/G12A_causal_online_recourse/baseline_snapshot.patch` để sẵn sàng phục hồi bất kỳ lúc nào.
5. **Không sửa đổi Trọng số Hàm mục tiêu:** Giữ nguyên các tham số chuẩn của `GateOptimizationConfig` (reassignment=100.0, overflow=500.0, conflict=10000.0, buffer=15 phút).
6. **Không sửa đổi Independent Verifier:** Hàm `verify_hard_constraints_independently()` tại `src/optimization/domain.py` giữ nguyên làm trọng tài độc lập tuyệt đối.
7. **Không tự ý chạy 500 Scenarios Monte Carlo:** Tuân thủ quy trình kiểm chuẩn 2 bước: Thí điểm 20 kịch bản trước, nếu đạt mới mở rộng lên 100 kịch bản.

---

## 2. KIỂM KÊ TRẠNG THÁI WORKING TREE TRƯỚC SỬA ĐỔI (PRE-REMEDIATION INVENTORY)

### 2.1. Danh mục 9 tệp theo dõi đang có thay đổi chưa commit (Tracked Modified Files)
| STT | Tệp | Kích thước | Trạng thái |
| :---: | :--- | :---: | :---: |
| 1 | `dashboard/adapters/export_adapter.py` | 13.844 bytes | Modified (G6) |
| 2 | `dashboard/core/config.py` | 8.899 bytes | Modified (G6) |
| 3 | `dashboard/core/contracts.py` | 12.355 bytes | Modified (G6) |
| 4 | `dashboard/services/scenario_service.py` | 15.244 bytes | Modified (G6) |
| 5 | `scripts/run_native_dual_core_pipeline.py` | 19.388 bytes | Modified (G4) |
| 6 | `src/contracts/__init__.py` | 822 bytes | Modified (G1) |
| 7 | `src/contracts/turn_contracts.py` | 4.275 bytes | Modified (G4) |
| 8 | `src/data/pairing_validator.py` | 20.122 bytes | Modified (G4) |
| 9 | `src/simulation/dual_prediction_turn.py` | 21.178 bytes | Modified (G4) |

Toàn văn diff của 9 tệp trên đã được sao lưu toàn vẹn tại:  
`remediation_evidence/G12A_causal_online_recourse/baseline_snapshot.patch` (SHA-256: `9f2b8004b3cf4e0d4a9ec00dbb63604b9c10ec3f64c676239121d55655519db8`).

---

## 3. PHẠM VI MÃ NGUỒN CẦN SỬA ĐỔI TRONG G12A

Các tệp được phép sửa đổi trong phạm vi nhiệm vụ G12A:
1. `src/simulation/monte_carlo_engine_v2.py`:
   - Thiết kế lại ranh giới dữ liệu giữa `SimulationWorld` và `DecisionPolicy`.
   - Remediate `evaluate_mode_b2_rolling_online_recourse()` để loại bỏ hoàn toàn việc đọc `precomputed_gate_out_min` khi ra quyết định tiếp nhận.
   - Hiện thực hóa hợp đồng `lock_horizon_minutes`.
   - Kiểm soát sức chứa hữu hạn của bãi đỗ xa (`remote_capacity`).
2. `tests/test_g12a_causal_online_recourse.py`:
   - Tạo bộ kiểm thử độc lập gồm 14 tiêu chuẩn toán học nghiêm ngặt (CAUSAL-01 đến CAUSAL-14).
3. `scripts/run_g12a_causal_pilot.py`:
   - Kịch bản thực thi thí điểm 20 và 100 kịch bản đối chứng A/B1/B2/C1/C2 mà không ghi đè artifact cũ.

Mọi sửa đổi sẽ được ghi nhận chi tiết tại các Deliverables tiếp theo.
