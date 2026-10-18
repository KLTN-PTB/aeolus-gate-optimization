# 03. ADVERSARIAL RESOURCE CONSISTENCY & INVARIANT VERIFICATION

**Suite:** `tests/test_mc500_topology_verification.py` (TOPO-01 to TOPO-12)  
**Execution Environment:** Python 3.11.15, Pytest 9.1.1, Windows Platform  
**Methodology:** Strict Test-Driven Development (TDD) — Failing Assertions Verified Before Code Modification  

---

## 1. Test Suite Architecture & Specification

| Test ID | Tên hàm kiểm tra | Mục tiêu kiểm toán & Bất biến khẳng định | Trạng thái trước sửa | Trạng thái sau sửa |
| :--- | :--- | :--- | :---: | :---: |
| **TOPO-01** | `test_topo_01_exactly_25_contact_gates` | Xác nhận sinh đúng 25 cổng tiếp xúc vật lý, mỗi cổng $Cap=1$, `is_overflow=False`. | FAILED (TypeError) | **PASSED** |
| **TOPO-02** | `test_topo_02_total_finite_remote_capacity_equals_five` | Tổng dung lượng vị trí đỗ từ xa hữu hạn đúng bằng 5 (`REMOTE_STAND_01`, $Cap=5$). | FAILED (TypeError) | **PASSED** |
| **TOPO-03** | `test_topo_03_no_unbounded_overflow_apron_when_disallowed` | Không có bãi tràn vô hạn (`UNBOUNDED_OVERFLOW_APRON` hoặc $Cap=\infty$) khi cấu hình cấm apron. | FAILED (TypeError) | **PASSED** |
| **TOPO-04** | `test_topo_04_mode_b2_utilizes_finite_remote_when_contact_full` | Khi 25 cổng tiếp xúc bị chiếm dụng bởi trễ, Mode B2 chuyển chuyến bay tràn sang vị trí đỗ từ xa hữu hạn. | FAILED (No stand) | **PASSED** |
| **TOPO-05** | `test_topo_05_five_concurrent_remote_occupants_accepted` | Đúng 5 tàu bay đồng thời được chấp nhận trên vị trí đỗ từ xa tập trung hữu hạn dung lượng 5. | FAILED (No stand) | **PASSED** |
| **TOPO-06** | `test_topo_06_sixth_concurrent_remote_occupant_rejected` | Tàu bay thứ 6 đồng thời bị từ chối với lý do rõ ràng `NO_CAPACITY_EXHAUSTED` và chuyển thành `UNASSIGNED`. | FAILED (No stand) | **PASSED** |
| **TOPO-07** | `test_topo_07_solvers_and_modes_share_identical_gate_inventory` | Xác minh Greedy, CP-SAT, Hybrid, Mode A, B1, B2, C1, C2 nhận đúng cùng 26 thực thể cổng. | FAILED (TypeError) | **PASSED** |
| **TOPO-08** | `test_topo_08_no_hidden_unbounded_apron_fallback` | Khi đầy cả 25 contact lẫn 5 remote, Mode B2 không lén lút fallback sang bất kỳ bãi tràn vô hạn nào. | FAILED (Assertion) | **PASSED** |
| **TOPO-09** | `test_topo_09_verifier_diagnostics_align_with_b2_feasibility` | Khẳng định chẩn đoán độc lập `verify_hard_constraints_independently()` khớp 100% với trạng thái khả thi của B2. | FAILED (Assertion) | **PASSED** |
| **TOPO-10** | `test_topo_10_solver_battery_regression` | Kiểm tra hồi quy thuật toán: Greedy và CP-SAT giải thành công kịch bản chuẩn 120 chuyến bay trên 25+5. | FAILED (TypeError) | **PASSED** |
| **TOPO-11** | `test_topo_11_mode_b2_non_anticipativity_preserved` | Nhiễu loạn trễ các chuyến bay trong tương lai ngoài lock horizon không làm thay đổi quyết định quá khứ/hiện tại của B2. | FAILED (Assertion) | **PASSED** |
| **TOPO-12** | `test_topo_12_scenario_mc_rem_s0009_resolution` | Phân biệt đối chứng trên kịch bản `MC_REM_S0009`: Trước sửa (topology cũ) = Infeasible; Sau sửa = Feasible. | FAILED (TypeError) | **PASSED** |

---

## 2. Chứng minh Khác biệt Đối chứng trên Kịch bản S0009 (TOPO-12)

Bài kiểm tra `TOPO-12` là hạt nhân chứng minh sự cần thiết và tính chính xác của sửa đổi:

1. **Khi chạy trên Topology Baseline Cũ:**
   ```python
   legacy_contact, legacy_overflow = scenario_to_gates(scen) # Không có finite remote stand
   legacy_gates = legacy_contact + [legacy_overflow]
   res_legacy = evaluate_mode_b2_rolling_online_recourse(..., gates=legacy_gates, ...)
   ```
   - Kết quả: `res_legacy.feasibility.composite_feasible == False`
   - Trạng thái solver: `ONLINE_INFEASIBLE_NO_CAPACITY`
   - Số lượng vị trí từ xa: `res_legacy.remote_count == 0`
   - Chuyến bay bị bỏ rơi: 1 chuyến bay không thể gán cổng.
2. **Khi chạy trên Topology Hiệu chỉnh Mới:**
   ```python
   corr_contact, corr_remote = scenario_to_gates(scen, finite_remote_capacity=5)
   corr_gates = corr_contact + [corr_remote]
   res_corr = evaluate_mode_b2_rolling_online_recourse(..., gates=corr_gates, ...)
   ```
   - Kết quả: `res_corr.feasibility.composite_feasible == True`
   - Trạng thái solver: `ONLINE_FEASIBLE`
   - Số lượng vị trí từ xa: `res_corr.remote_count == 1`
   - Tải từ xa đồng thời: `max_concurrent_remote_usage == 1 <= 5`
   - Chi phí giảm mạnh từ $574.63 \to 384.97$.

---

## 3. Kết quả Kiểm tra Hồi quy Toàn diện (Full Battery Regression)

Sau khi hoàn tất sửa đổi, toàn bộ 13 test suite mục tiêu của dự án được thực thi đồng thời:
```
tests/test_g12a_causal_online_recourse.py
tests/test_g12b_contract_closure.py
tests/test_g12b_hybrid_incumbent.py
tests/test_g12b_r1_contract_integrity.py
tests/test_g1_provenance_and_temporal_contracts.py
tests/test_g2_monte_carlo_causality.py
tests/test_g3_ml_validation.py
tests/test_g4_native_e2e.py
tests/test_g5_solver_correctness.py
tests/test_g6_dashboard_integrity.py
tests/test_g7_scientific_invariants.py
tests/test_mc500_ledger_runner_integration.py
tests/test_mc500_topology_verification.py
```

**Kết quả:**
- **231 passed, 0 failed, 0 skipped** trong $38.58$ giây.
- $100\%$ các bài kiểm tra bảo toàn toán học, bất biến thời gian, mô hình máy học và hợp đồng ledger đều PASS.
