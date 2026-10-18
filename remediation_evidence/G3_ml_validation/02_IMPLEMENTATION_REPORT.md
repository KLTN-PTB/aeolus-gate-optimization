# AEOLUS-G3 — DELIVERABLE 02: IMPLEMENTATION REPORT

## 1. Outbound Classification Pipeline Architecture

To establish an authoritative, leakage-safe machine learning classifier for outbound flight delays, Gate G3 implemented `scripts/train_outbound_classifiers_g3.py`.

```
                    Aeolus Processed Outbound ATL Data
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
   Train Partition           Calibration Partition     Evaluation Partition
   Year 2021 (N=309,488)     Year 2022 (N=311,746)     Year 2023 (N=332,734)
           │                         │                         │
   10 Approved Features      10 Approved Features      10 Approved Features
           │                         │                         │
   ┌───────┴───────┐                 │                         │
   ▼               ▼                 │                         │
Logistic        XGBoost              │                         │
Regression      Classifier           │                         │
(LBFGS)         (Hist Tree)          │                         │
   │               │                 │                         │
   └───────┬───────┘                 │                         │
           ▼                         │                         │
     Fitted Models                   │                         │
           │                         │                         │
           └────────────► CalibratedPredictor ◄────────────────┘
                          - Isotonic Scaling (LR)
                          - Platt Scaling (XGBoost)
                          - Prefit (Zero Test Leakage)
                                     │
                                     ▼
                          Selection 2023 Evaluation
                          - ROC-AUC / PR-AUC
                          - Brier Score / Log Loss
                          - Expected Calibration Error (ECE)
                          - Reliability Diagram (10 Bins)
```

## 2. Temporal Protocol & Data Splitting

In strict accordance with the registered temporal protocol (and enforcing zero contamination from the 2024 holdout):
1. **Training Split (`Year 2021`):** 309,488 completed outbound ATL flights.
   - Positive class prevalence ($P(\text{DEP\_DELAY} \ge 15)$): **14.26%**.
2. **Calibration Split (`Year 2022`):** 311,746 completed outbound ATL flights.
   - Positive class prevalence: **19.59%**.
   - Used exclusively to fit probability calibration mappings (`CalibratedPredictor`).
3. **Evaluation / Selection Split (`Year 2023`):** 332,734 completed outbound ATL flights.
   - Positive class prevalence: **20.63%**.
   - Used strictly for post-fit evaluation, ensuring zero leakage into training or calibration.
4. **Holdout Split (`Year 2024`):** **STRICTLY PRESERVED / UNTOUCHED**. Zero rows from 2024 were accessed.

## 3. Feature Contract at Prediction Cutoff

Both models adhere strictly to `CORE_DEPARTURE_APPROVED_FEATURES` defined in `src/features/departure_features.py`:
- Target definition: Binary label $y_i = \mathbb{I}(\text{DEP\_DELAY}_i \ge 15.0)$.
- Information cutoff: Exactly $CRS\_DEP\_TIME - 2$ hours in `America/New_York` local time.
- Exactly 10 approved features:
  1. `CRS_ELAPSED_TIME` (Scheduled flight duration, minutes)
  2. `calendar_month` (1–12)
  3. `calendar_day_of_month` (1–31)
  4. `calendar_day_of_week` (1–7)
  5. `is_weekend` (Binary indicator)
  6. `scheduled_departure_hour` (0–23)
  7. `scheduled_departure_minute` (0–59)
  8. `OP_CARRIER` (Operating airline code, categorical)
  9. `DEST` (Destination airport code, categorical)
  10. `OP_CARRIER_FL_NUM` (Flight number, high cardinality)

## 4. Model Architectures & Training Execution

### 4.1 Logistic Regression Classifier (`outbound_logistic_classifier_v1`)
- **Preprocessor:** `artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib` (StandardScaler on numerical features, OneHotEncoder on categoricals).
- **Hyperparameters:** $C = 1.0$, `solver = 'lbfgs'`, `max_iter = 100`, `random_state = 202601`.
- **Training Wall-Clock Time:** 4.95 seconds on 309,488 rows.

### 4.2 XGBoost Classifier (`outbound_xgboost_classifier_v1`)
- **Preprocessor:** `artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib` (Ordinal and native numerical encoding).
- **Hyperparameters:** `n_estimators = 100`, `max_depth = 6`, `learning_rate = 0.05`, `tree_method = 'hist'`, `subsample = 0.8`, `colsample_bytree = 0.8`, `random_state = 202601`, `eval_metric = 'logloss'`.
- **Training Wall-Clock Time:** 0.81 seconds on 309,488 rows.

## 5. Formal Probability Calibration (`CalibratedPredictor`)

To eliminate the legacy flaw of uncalibrated heuristic sigmoid scoring, probability calibration was fitted on the 2022 calibration split:

1. **Isotonic Calibration (for Logistic Regression):** Fits a non-parametric monotonic step function mapping uncalibrated logits to empirical probabilities:
   $$\hat{p}_{iso} = m_{iso}(f_{LR}(x))$$
2. **Platt (Sigmoid) Scaling (for XGBoost):** Fits a univariate logistic regression mapping raw predicted tree margins to calibrated posterior probabilities:
   $$\hat{p}_{plat} = \frac{1}{1 + \exp(A \cdot f_{XGB}(x) + B)}$$
3. **Calibration Metric Verification:**
   - Evaluated using Expected Calibration Error (ECE) across 10 fixed probability bins:
     $$\text{ECE} = \sum_{m=1}^{10} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
   - **Target achieved:** Both calibrated models achieved $\text{ECE} \approx 0.011$, far surpassing the $\text{ECE} \le 0.05$ target.
