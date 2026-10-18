# AEOLUS-G10 — DELIVERABLE 09: RAW COMMAND EXECUTION & AUTOMATED TEST LOGS

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Operations Research Verification Engineer & Principal Software Auditor  
**Format:** Verbatim Command Invocations, Terminal Outputs, and Pytest Diagnostics  

---

## 1. REPOSITORY GIT STATUS & REVISION LOGS

### 1.1. Lệnh Kiểm tra Nhánh và Commit HEAD
```powershell
PS D:\Study\Code\Python\Aelous> git status
On branch remediation/g7-regression
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   dashboard/adapters/export_adapter.py
	modified:   dashboard/core/config.py
	modified:   dashboard/core/contracts.py
	modified:   dashboard/services/scenario_service.py
	modified:   scripts/run_native_dual_core_pipeline.py
	modified:   src/contracts/__init__.py
	modified:   src/contracts/turn_contracts.py
	modified:   src/data/pairing_validator.py
	modified:   src/simulation/dual_prediction_turn.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	artifacts/remediation/benchmarks/g5_fair_benchmark/
	artifacts/remediation/monte_carlo_remediated/
	artifacts/remediation/native_dual_core_g4_pilot/
	artifacts/remediation/native_dual_core_g4_pilot_greedy/
	artifacts/remediation/native_dual_core_g4_pilot_hybrid/
	artifacts/remediation/native_dual_core_g4_pilot_inferred/
	artifacts/remediation/outbound_classification/
	audit_exports/
	remediation_evidence/
	scripts/merge_remediation_evidence.py
	scripts/run_g2_monte_carlo_remediation.py
	scripts/run_g5_fair_benchmark.py
	scripts/train_outbound_classifiers_g3.py
	scripts/verify_reproducibility_g7.py
	src/contracts/provenance.py
	src/contracts/temporal.py
	src/data/canonical_time.py
	src/data/real_data_loader.py
	src/simulation/monte_carlo_engine_v2.py
	src/simulation/verified_pairing.py
	tests/test_g1_provenance_and_temporal_contracts.py
	tests/test_g2_monte_carlo_causality.py
	tests/test_g3_ml_validation.py
	tests/test_g4_native_e2e.py
	tests/test_g5_solver_correctness.py
	tests/test_g6_dashboard_integrity.py
	tests/test_g7_scientific_invariants.py

no changes added to commit (use "git add" and/or "git commit -a")
```

### 1.2. Lệnh Kiểm tra Lịch sử Commit
```powershell
PS D:\Study\Code\Python\Aelous> git log -n 5 --oneline
c95caef feat: integrate native dual-core, ML validation, Monte Carlo engine and operational dashboard
223f0dd feat(p06): CP-SAT formulation optimization, oracle parity, and independent verification
8cf96b9 docs(certification): complete e2e benchmarks, audit report and P10 simulation certification
bd70ca8 feat(optimization): integrate dual turn engine, adapter and sweep-line cp-sat solver
aa4c19d feat(ml): implement fold-safe departure preprocessing, point and probabilistic models
```

---

## 2. G3 PREDICTION-LEVEL RECOMPUTATION LOGS

### 2.1. Lệnh Tái tính toán Toàn diện từ tệp Parquet
```powershell
PS D:\Study\Code\Python\Aelous> python -c "
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss, confusion_matrix, precision_recall_fscore_support

df = pd.read_parquet('artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet')
y_true = df['y_true'].values

print('N:', len(y_true))
print('Positives:', int(y_true.sum()))
print('Prevalence:', y_true.mean())

for col in ['prob_constant', 'prob_logistic_raw', 'prob_logistic_calibrated', 'prob_xgboost_raw', 'prob_xgboost_calibrated']:
    probs = df[col].values
    roc_auc = roc_auc_score(y_true, probs)
    pr_auc = average_precision_score(y_true, probs)
    brier = brier_score_loss(y_true, probs)
    ll = log_loss(y_true, np.clip(probs, 1e-15, 1 - 1e-15))
    
    # 10 bins ECE
    bins = np.linspace(0.0, 1.0, 11)
    bin_indices = np.digitize(probs, bins) - 1
    bin_indices = np.clip(bin_indices, 0, 9)
    ece = 0.0
    for b in range(10):
        mask = (bin_indices == b)
        cnt = np.sum(mask)
        if cnt > 0:
            conf = np.mean(probs[mask])
            acc = np.mean(y_true[mask])
            ece += (cnt / len(y_true)) * abs(acc - conf)
            
    # Confusion matrix at 0.5
    y_pred = (probs >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
    
    print(f'=== {col} ===')
    print(f'ROC-AUC: {roc_auc:.5f}, PR-AUC: {pr_auc:.5f}, Brier: {brier:.5f}, LogLoss: {ll:.5f}, ECE: {ece:.5f}')
    print(f'TP: {tp}, FP: {fp}, TN: {tn}, FN: {fn}, Prec: {prec:.5f}, Rec: {rec:.5f}, F1: {f1:.5f}')
"
```

**Kết quả Kết xuất Đầu ra:**
```text
N: 332734
Positives: 68628
Prevalence: 0.20625484621349185

=== prob_constant ===
ROC-AUC: 0.50000, PR-AUC: 0.20625, Brier: 0.16776, LogLoss: 0.52382, ECE: 0.06360
TP: 0, FP: 0, TN: 264106, FN: 68628, Prec: 0.00000, Rec: 0.00000, F1: 0.00000

=== prob_logistic_raw ===
ROC-AUC: 0.61343, PR-AUC: 0.29708, Brier: 0.16196, LogLoss: 0.51062, ECE: 0.05507
TP: 286, FP: 315, TN: 263791, FN: 68342, Prec: 0.47587, Rec: 0.00417, F1: 0.00826

=== prob_logistic_calibrated ===
ROC-AUC: 0.61336, PR-AUC: 0.29381, Brier: 0.15892, LogLoss: 0.49534, ECE: 0.01047
TP: 2698, FP: 3265, TN: 260841, FN: 65930, Prec: 0.45246, Rec: 0.03931, F1: 0.07234

=== prob_xgboost_raw ===
ROC-AUC: 0.64289, PR-AUC: 0.32916, Brier: 0.15891, LogLoss: 0.50072, ECE: 0.05644
TP: 2618, FP: 2423, TN: 261683, FN: 66010, Prec: 0.51934, Rec: 0.03815, F1: 0.07107

=== prob_xgboost_calibrated ===
ROC-AUC: 0.64289, PR-AUC: 0.32915, Brier: 0.15637, LogLoss: 0.48800, ECE: 0.01192
TP: 3337, FP: 3437, TN: 260669, FN: 65291, Prec: 0.49262, Rec: 0.04862, F1: 0.08851
```

---

## 3. PYTEST RAW DIAGNOSTICS TRÊN 4 BÀI TEST THẤT BẠI

### 3.1. Test 1: `test_registry_integration_retrieval`
```text
_____________________ test_registry_integration_retrieval _____________________

    def test_registry_integration_retrieval() -> None:
        """Verify that all core and legacy models can be retrieved and have required benchmark spec fields."""
        models = list_models()
        assert len(models) >= 10
    
        for spec in models:
            assert spec.model_id
            assert spec.family
>           assert spec.task in {ModelTask.CORE_ARRIVAL.value, ModelTask.AUXILIARY_DEPARTURE.value}
E           AssertionError: assert 'core_departure' in {'auxiliary_departure', 'core_arrival'}
E            +  where 'core_departure' = ModelSpec(model_id='departure_linear_baseline_v1', ... task='core_departure').task

tests\benchmark\test_model_registry.py:33: AssertionError
```

### 3.2. Test 2 & 3: `test_guard_v3_verifies_all_frozen_files` & `test_guard_v3_authorizes_clean_post_holdout_access`
```text
_____________ test_guard_v3_verifies_all_frozen_files __________________________

    def test_guard_v3_verifies_all_frozen_files(guard_v3: FinalEvaluationGuardV2) -> None:
        """Verify that guard validates all frozen files across categories A-W without error."""
>       res = guard_v3.verify_freeze_manifest()

tests\test_r22_system_freeze_v3.py:90: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src\evaluation\final_evaluation_guard_v2.py:160: in verify_freeze_manifest
>                   raise FinalEvaluationGuardV2Error(
                        f"Integrity hash mismatch in category '{cat_name}' for {rel_path}: "
                        f"expected {expected_hash}, got {actual_hash}. "
                        "Unfrozen source or config changes detected. Evaluation is BLOCKED."
                    )
E                   src.evaluation.final_evaluation_guard_v2.FinalEvaluationGuardV2Error: Integrity hash mismatch in category 'A_data_contracts' for src\data\leakage_rules.py: expected a52e264199e953c51a1393842b847c85f907b161363c3915b9ae7658bf40b929, got 29521ee18130dd5dc2d95f1cb7fbd1997a8ffb943d81da2b865433df9c5f9cdf. Unfrozen source or config changes detected. Evaluation is BLOCKED.
```

### 3.3. Test 4: `test_r22_freeze_manifest_integrity`
```text
_____________________ test_r22_freeze_manifest_integrity ______________________

    def test_r22_freeze_manifest_integrity():
        """Verify system_freeze_manifest_v3.json contents, category counts, and hashes."""
...
>               assert actual_file_sha == expected_hash, f"Frozen hash mismatch on {fpath_str}: {actual_file_sha} != {expected_hash}"
E               AssertionError: Frozen hash mismatch on src\optimization\domain.py: 7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580 != 678d841262ee26415789f8a00c86a42374205ada7c420b9a7f2cd6ed808c92d3
E               assert '7e2101388729...b3adde78ea580' == '678d841262ee...cd6ed808c92d3'

tests\test_r27_certification_hardening.py:266: AssertionError
```

---

## 4. XÁC THỰC MÃ BĂM SHA-256 CHECKPOINT ĐÓNG BĂNG
```powershell
PS D:\Study\Code\Python\Aelous> python -c "
import hashlib, pathlib
for p in [
    'artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib',
    'artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib',
    'artifacts/remediation/outbound_classification/models/outbound_xgboost_calibrated_v1.joblib',
    'data/processed/p07_flights_core.csv'
]:
    f = pathlib.Path(p)
    h = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else 'MISSING'
    print(f'{p}: {h}')
"
```
**Kết quả Kết xuất Đầu ra:**
```text
artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib: e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f
artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib: e483df5fd03ce4d0eefe7b431fc289b6804589c62eda17b48fb8051849f4f6e1
artifacts/remediation/outbound_classification/models/outbound_xgboost_calibrated_v1.joblib: 73ef9da305886d34e9e1bb939a9ceae0b686259021e1dbdfa79d0be18b01e1ff
data/processed/p07_flights_core.csv: 5a5c689d70fa7e2a9b3488f572aeb41d3b377b78a0a9fb9cf6cf87d3e41c4115
```
Các mã băm mô hình trên đĩa khớp 100% với các mã băm được khai báo trong manifest kiểm toán.
