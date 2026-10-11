# Research Inspector Specification & Academic Audit Panel

**Document ID:** `AEOLUS-P10-A-INSPECTOR-09`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target Component:** Global Collapsible Inspector (`src/dashboard/components/research_inspector.py`)  

---

## 1. Executive Summary & Purpose

The **Research Inspector** is an omnipresent, expandable audit drawer available across all five pages of the Aeolus application. It serves as the primary instrument of academic integrity, giving thesis committee members and research software auditors instantaneous access to system provenance, mathematical formulations, model checksums, solver seeds, and reproducibility manifests.

> [!CAUTION] Security & Environment Path Sanitization Policy
> To maintain professional deployment standards and protect developer privacy:
> 1. **Zero Absolute Paths:** Absolute host Windows filesystem paths (e.g., `D:\Study\Code\Python\Aelous\...`) MUST NEVER be exposed in the UI.
> 2. **Relative Project Roots:** All artifact locations must be normalized to clean project-relative paths (e.g., `artifacts/remediation/monte_carlo/fixed_plan_results.csv`).
> 3. **Zero Secrets:** No internal system credentials or environment tokens shall appear in inspector outputs.

---

## 2. Inspector Visual Layout & Interaction Architecture

The Research Inspector is implemented as a sticky bottom expander on every page:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ▼ 🔍 RESEARCH INSPECTOR — KIỂM TOÁN HỆ THỐNG & NGUYÊN BẢN HỌC THUẬT (PROVENANCE) [Phiên bản: P09-Locked]│
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────────────────────────┐ │
│ │ 1. NGUỒN GỐC DỮ LIỆU & ML│ │ 2. MÔ HÌNH HÓA TOÁN HỌC  │ │ 3. CẤU HÌNH BỘ GIẢI & PHẦN CỨNG          │ │
│ │ • Hub: ATL (Atlanta)     │ │ • Hàm mục tiêu: v4.2     │ │ • Bộ giải: OR-Tools CP-SAT v9.15         │ │
│ │ • Dataset: BTS OTP 2023  │ │ • w_pref: 10.0 (Đổi cổng)│ │ • Dạng mô hình: sparse_interval          │ │
│ │ • 2024 Holdout: NIÊM PHONG│ │ • w_remote: 200.0 (Xa)   │ │ • Luồng tính toán: 8 workers             │ │
│ │ • XGBoost Model: In/Out  │ │ • w_conflict: 1000.0     │ │ • Giới hạn thời gian: 30.0s              │ │
│ │ • Checksum: a9f8e2...    │ │ • Đệm an toàn: 15 phút   │ │ • Random Seed: 42 (Cố định tái lập)     │ │
│ └──────────────────────────┘ └──────────────────────────┘ └──────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. TRẠNG THÁI KIỂM CHỨNG TOÁN HỌC ĐỘC LẬP (VERIFIER CHECKPOINT):                                       │
│    ✓ Không có chuyến bay trùng cổng (0 spatial conflicts)                                              │
│    ✓ 100% chuyến bay tuân thủ giãn cách 15 phút (0 buffer violations)                                  │
│    ✓ Mã băm kịch bản hiện tại: SHA256-4b2190cd7e...                                                    │
│    ✓ Tệp lưu vết artifact: artifacts/remediation/native_dual_core/optimization_result.json             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [📋 Sao chép Toàn bộ Manifest dưới dạng JSON]   [📥 Tải về Hồ sơ Bàn giao Kỹ thuật P10-00 (ZIP)]       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Schema & Manifest Fields

The Inspector renders a standardized JSON manifest compiled from session state and artifact metadata:

```json
{
  "audit_version": "AEOLUS-P10-AUDIT-v1",
  "system_timestamp_utc": "2026-10-09T17:15:00Z",
  "provenance": {
    "airport_hub": "ATL",
    "data_source": "Bureau of Transportation Statistics (BTS) On-Time Performance 2023",
    "holdout_seal_status": "SEALED_2024_ISOLATED",
    "scenario_id": "SCEN_P09_CANONICAL_120",
    "scenario_hash": "sha256-4b2190cd7ef34...",
    "flight_count": 120,
    "gate_count": 25,
    "remote_capacity": 1
  },
  "machine_learning": {
    "arrival_delay_model": "xgboost_inbound_v3.2",
    "departure_delay_model": "xgboost_outbound_v3.2",
    "model_artifact_path": "artifacts/models/inbound_arrival/",
    "shap_importance_artifact": "artifacts/remediation/ml_validation/shap_outputs/global_importance.csv"
  },
  "operations_research": {
    "solver_engine": "ortools_cpsat_9.15.6755",
    "formulation_type": "sparse_interval",
    "objective_function": "min 10*reassign + 200*remote + 1000*conflict",
    "buffer_time_minutes": 15,
    "random_seed": 42,
    "threads_allocated": 8,
    "independent_verifier": "src/optimization/evaluation.py::verify_hard_constraints_independently",
    "verification_passed": true,
    "violations_detected": 0
  },
  "scientific_disclaimers": {
    "finding_d1": "Mode A feasibility (0.0%) reflects strict static schedule mismatch; physical space-time collision rate is 74.8%.",
    "finding_d2": "Mode B recourse and Mode C oracle achieve numerical parity on canonical 120 flights because initial plan has zero reassignments and both modes utilize deterministic greedy re-solving."
  }
}
```

---

## 4. UI Visibility & Presentation Modes
- **In Presentation Mode:** The Inspector is collapsed by default (`expanded=False`) at the bottom of the page with a clean muted status header. It does not obstruct the flow of the presentation unless intentionally toggled by the speaker.
- **In Research Mode:** The Inspector remains prominent and includes a **"📋 Sao chép Manifest JSON"** button, allowing instant copying of complete reproducibility metadata to the user's clipboard.
