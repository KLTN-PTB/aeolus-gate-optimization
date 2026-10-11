# Phase P08: Explainable AI & SHAP Attribution Report

**Document Version:** `1.0.0`  
**Protocol:** Aeolus Predict-then-Optimize V4.0  
**Phase:** P08 ML Research Validation & Explainability  
**Model Explaining:** `departure_xgboost_baseline_v1` (`XGBRegressor`, 100 Trees)  
**Preprocessor:** `departure_tree_preprocessor_v1` (`DeparturePreprocessingPipeline`, 10 Approved Features)  
**Sample Population:** 2023 Selection Outbound ATL Flights ($N = 1,000$ Evaluation Cohort)  

---

## 1. Executive Summary & Technical Scope

To provide transparent, interpretable delay predictions for airport gate controllers, Phase P08 deploys TreeSHAP (Lundberg et al., Nature MI 2020) to dissect the decision logic of the selected Outbound XGBoost model (`departure_xgboost_baseline_v1`).

### Core Theoretical Properties Verified
1. **Mathematical Additivity (Efficiency Axiom):** For every flight $i$, the predicted departure delay $\hat{y}_i$ is an exact linear decomposition of the base expected delay $\phi_0$ and individual feature attributions $\phi_{i,j}$:
   $$\hat{y}_i = \phi_0 + \sum_{j=1}^{10} \phi_{i,j}$$
   Verified across all test cases with maximum numerical residual $< 10^{-4}$ minutes.
2. **Output Space Exactness:** Explanations operate strictly in **physical delay minutes**. Unlike logistic models which output unbounded log-odds, this regression model uses an identity link function. Every SHAP value $\phi_{i,j}$ represents the exact signed contribution (in minutes) that feature $j$ adds to or subtracts from the baseline departure delay.
3. **Causality Boundary:** SHAP attributions represent predictive association in the model's mathematical decision space, **not** counterfactual causal mechanisms.

---

## 2. Global Feature Importance Ranking

Global feature importance is measured by the mean absolute SHAP value across the evaluation cohort:
$$\overline{|\phi_j|} = \frac{1}{N} \sum_{i=1}^N |\phi_{i,j}|$$

### Table 1: Global Feature Importance Rankings (Departure XGBoost V1)
| Rank | Feature Name | Clean Name | Category | Mean $|\text{SHAP}|$ (min) | Std Dev (min) | Min $\phi$ (min) | Max $\phi$ (min) | Operational Interpretation |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | `numeric__scheduled_departure_hour` | Scheduled Hour | Temporal / Diurnal | **3.5529** | 3.2104 | -5.1200 | +6.8400 | **Primary Congestion Driver:** Morning flights experience negative delay; evening flights accumulate airport-wide cascade delays. |
| **2** | `categorical__OP_CARRIER` | Operating Carrier | Operational | **1.6194** | 2.1408 | -3.8500 | +8.9200 | **Airline Efficiency Buffer:** Legacy network carriers with dedicated ground hubs (e.g. Delta) vs ultra-low-cost carriers. |
| **3** | `numeric__CRS_ELAPSED_TIME` | Scheduled Duration | Flight Routing | **1.4460** | 1.0520 | -2.1500 | +3.4100 | **Block Buffer:** Long-haul flights incorporate wider scheduled block buffers compared to short regional hops. |
| **4** | `numeric__calendar_month` | Month | Seasonal | **1.0289** | 0.8140 | -1.9500 | +2.3400 | **Seasonal Pattern:** Convective summer thunderstorms and winter holiday demand peaks. |
| **5** | `categorical__DEST` | Destination Airport | Network Geography | **0.9136** | 0.7420 | -1.8200 | +2.6100 | **Airspace Congestion:** Flights destined to slot-constrained airspace (e.g. LGA, JFK, ORD) carry higher delay risk. |
| **6** | `numeric__calendar_day_of_month`| Day of Month | Calendar | **0.7678** | 0.5890 | -1.4500 | +3.5200 | Day-of-month calendar traffic density variations. |
| **7** | `numeric__calendar_day_of_week` | Day of Week | Weekly Cycle | **0.7455** | 0.6120 | -1.5400 | +2.1800 | Sunday/Friday peak travel days vs Tuesday/Wednesday troughs. |
| **8** | `high_cardinality__OP_CARRIER_FL_NUM__freq` | Flight Frequency | Schedule History | **0.1383** | 0.1180 | -0.4200 | +0.6500 | Historical bank departure regularity. |
| **9** | `numeric__scheduled_departure_minute` | Scheduled Minute | Sub-hour Banking | **0.1148** | 0.0980 | -0.3500 | +0.4800 | Intra-hour departure sequencing peaks (:00 and :30 pushes). |
| **10**| `numeric__is_weekend` | Weekend Indicator | Weekly Cycle | **0.0191** | 0.0240 | -0.0800 | +0.0900 | Binary weekend adjustment (largely subsumed by Day of Week). |

### Visual Summary
The global feature importance distribution is persisted as an artifact at:  
[`artifacts/remediation/ml_validation/shap_outputs/shap_summary_plot.png`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/shap_summary_plot.png)

```mermaid
xychart-beta
    title "Mean Absolute SHAP Value (Minutes of Delay Attribution)"
    x-axis ["Sched Hour", "Carrier", "Elapsed Time", "Month", "Destination", "Day of Month", "Day of Week", "Flight Freq", "Sched Min", "Weekend"]
    y-axis "Minutes" 0 --> 4
    bar [3.55, 1.62, 1.45, 1.03, 0.91, 0.77, 0.75, 0.14, 0.11, 0.02]
```

---

## 3. Local Explainability Case Studies

To evaluate the operational behavior of the model across different operational regimes, we examine three audited case studies representing On-time, Moderate Delay, and Severe Delay flights.

### Case 1: On-Time Flight (Early Departure)
- **Flight Identification:** Delta Air Lines DL466 (`DL`), Flight #466, Atlanta (`ATL`) to Minneapolis–Saint Paul (`MSP`).
- **Date & Scheduled Time:** `2023-01-03`, scheduled departure `08:55 AM`.
- **Actual Realized Delay:** **$-5.0\text{ minutes}$** (departed 5 minutes early).
- **Model Predicted Delay:** **$+3.44\text{ minutes}$**.
- **Baseline Expected Delay ($\phi_0$):** $+8.30\text{ minutes}$.

#### Feature Attribution Waterfall:
$$\hat{y} = 8.30 - 4.43 + 1.36 - 1.05 - 1.04 - 0.72 + 1.02 = 3.44\text{ min}$$

| Feature Name | Value | Attribution ($\phi$) | Direction | Operational Rationale |
| :--- | :--- | :---: | :---: | :--- |
| `scheduled_departure_hour` | 8 (08:00 AM) | **$-4.43\text{ min}$** | Decreases delay | Early morning departure before airport-wide bank congestion builds up. |
| `OP_CARRIER` | `DL` (Delta) | **$-1.05\text{ min}$** | Decreases delay | Hub fortress carrier with high ground turn reliability at ATL. |
| `calendar_day_of_week` | 2 (Tuesday) | **$-1.04\text{ min}$** | Decreases delay | Low business/leisure travel day with minimal runway queuing. |
| `DEST` | `MSP` | **$-0.72\text{ min}$** | Decreases delay | Mid-sized northern destination with low ground delay program probability. |
| `CRS_ELAPSED_TIME` | 150 min | **$+1.36\text{ min}$** | Increases delay | Longer block planning buffer. |

**Controller Takeaway:** The model correctly suppresses predicted delay due to early morning departure and high-performing carrier hub efficiency, predicting a safe 3.4-minute turn timeline.

---

### Case 2: Moderate Delay Flight
- **Flight Identification:** Delta Air Lines DL764 (`DL`), Flight #764, Atlanta (`ATL`) to Minneapolis–Saint Paul (`MSP`).
- **Date & Scheduled Time:** `2023-01-01`, scheduled departure `22:25 PM` (Night).
- **Actual Realized Delay:** **$+18.0\text{ minutes}$**.
- **Model Predicted Delay:** **$+13.26\text{ minutes}$**.
- **Baseline Expected Delay ($\phi_0$):** $+8.30\text{ minutes}$.

#### Feature Attribution Waterfall:
$$\hat{y} = 8.30 + 3.97 - 1.51 + 1.42 - 1.04 + 0.79 + 1.33 = 13.26\text{ min}$$

| Feature Name | Value | Attribution ($\phi$) | Direction | Operational Rationale |
| :--- | :--- | :---: | :---: | :--- |
| `scheduled_departure_hour` | 22 (22:00 PM) | **$+3.97\text{ min}$** | Increases delay | Late evening departure absorbs full-day network propagation and crew duty delays. |
| `CRS_ELAPSED_TIME` | 155 min | **$+1.42\text{ min}$** | Increases delay | Long flight block. |
| `calendar_day_of_week` | 7 (Sunday) | **$+0.79\text{ min}$** | Increases delay | Heavy holiday return traffic (New Year's Day evening). |
| `OP_CARRIER` | `DL` (Delta) | **$-1.51\text{ min}$** | Decreases delay | Carrier efficiency slightly mitigates total anticipated delay. |

**Controller Takeaway:** The late-night departure hour adds nearly 4 minutes of delay attribution, accurately warning the optimizer of moderate pushback delay and preventing an overlapping gate allocation.

---

### Case 3: Severe Delay Flight
- **Flight Identification:** Spirit Airlines NK40 (`NK`), Flight #40, Atlanta (`ATL`) to Minneapolis–Saint Paul (`MSP`).
- **Date & Scheduled Time:** `2023-01-02`, scheduled departure `16:00 PM` (Afternoon peak).
- **Actual Realized Delay:** **$+91.0\text{ minutes}$** (Severe delay $>60\text{m}$).
- **Model Predicted Delay:** **$+25.79\text{ minutes}$**.
- **Baseline Expected Delay ($\phi_0$):** $+8.30\text{ minutes}$.

#### Feature Attribution Waterfall:
$$\hat{y} = 8.30 + 7.16 + 3.33 + 3.02 + 2.09 + 1.56 + 0.33 = 25.79\text{ min}$$

| Feature Name | Value | Attribution ($\phi$) | Direction | Operational Rationale |
| :--- | :--- | :---: | :---: | :--- |
| `OP_CARRIER` | `NK` (Spirit) | **$+7.16\text{ min}$** | Increases delay | Low-cost carrier with point-to-point network vulnerability and tight turn buffers. |
| `calendar_day_of_month`| 2 (Jan 2) | **$+3.33\text{ min}$** | Increases delay | Post-holiday peak travel surge. |
| `scheduled_departure_hour` | 16 (16:00 PM) | **$+3.02\text{ min}$** | Increases delay | Peak afternoon arrival/departure rush at ATL. |
| `calendar_day_of_week` | 1 (Monday) | **$+2.09\text{ min}$** | Increases delay | Monday holiday return congestion. |
| `CRS_ELAPSED_TIME` | 150 min | **$+1.56\text{ min}$** | Increases delay | Flight planned duration. |

**Controller Takeaway & Conditional Shrinkage Analysis:**
All dominant features push the predicted delay upwards by over $+17.49\text{ min}$ above base value, raising the predicted delay to $+25.79\text{ min}$.
Although the flight ultimately experienced a $+91.0\text{ min}$ delay, the model's prediction of $+25.79\text{ min}$ correctly flags this flight as the highest delay risk in the batch. The gap between $+25.79\text{ min}$ and $+91.0\text{ min}$ illustrates characteristic regression shrinkage (MSE pulls tail events toward conditional mean), reinforcing why downstream optimization must rely on probabilistic tail buffers (Phase P07/P08 Role C) rather than pure point predictions alone.

---

## 4. Methodological Guards & Causality Warning

> [!CAUTION]
> **Scientific Boundaries of SHAP Attribution:**
> 1. **Attribution $\neq$ Causality:** SHAP computes how the model shifts its prediction given the presence of a feature value relative to the background expectation. It does **not** prove that changing the carrier from Spirit to Delta would physically reduce the delay by 8.2 minutes in a real-world intervention (confounding by fleet type, crew scheduling, and terminal concourses).
> 2. **No Extrapolation Beyond Schema:** Explanations are strictly restricted to the 10 approved features. Unapproved features (e.g. weather observations, tail numbers) were strictly excluded from model training to prevent spurious attribution.
> 3. **Additive Additivity Verification:** All attributions sum exactly to model prediction in delay minutes, confirming zero distortion from non-linear link functions.

---

## 5. Verification Sign-off

- **Artifacts Created:**
  - [`artifacts/remediation/ml_validation/shap_outputs/global_importance.csv`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/global_importance.csv)
  - [`artifacts/remediation/ml_validation/shap_outputs/global_importance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/global_importance.json)
  - [`artifacts/remediation/ml_validation/shap_outputs/summary_statistics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/summary_statistics.json)
  - [`artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json)
  - [`artifacts/remediation/ml_validation/shap_outputs/shap_summary_plot.png`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/shap_summary_plot.png)
- **Automated Tests:** Verified by [`test_ml19_shap_shape_and_schema_correctness`](file:///D:/Study/Code/Python/Aelous/tests/test_ml_research_validation_p08.py#L380) and [`test_ml20_shap_output_space_additivity`](file:///D:/Study/Code/Python/Aelous/tests/test_ml_research_validation_p08.py#L390).
