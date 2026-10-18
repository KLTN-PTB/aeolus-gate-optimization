# AEOLUS-G3 — DELIVERABLE 05: LIMITATIONS AND SCIENTIFIC RISKS

## 1. Explicit Scientific Limitations

To ensure absolute intellectual honesty in the thesis defense, the following limitations must be formally disclosed:

### 1.1 Moderate Discriminative Power of Schedule-Only Pre-Departure Features
- **Empirical Reality:** At prediction cutoff $T-2$h before scheduled pushback, the operational information set contains only scheduled tabular attributes (airline, scheduled departure hour, day of week, scheduled elapsed time, destination airport).
- **Discriminative Performance:** On the 2023 Outbound ATL population ($N = 332,734$ flights, prevalence $20.63\%$):
  - Logistic Regression: $\text{ROC-AUC} = 0.6134$, $\text{PR-AUC} = 0.2938$.
  - XGBoost Classifier: $\text{ROC-AUC} = 0.6429$, $\text{PR-AUC} = 0.3292$.
- **Thesis Guidance:** The thesis must **not** claim near-perfect prediction ($\text{AUC} > 0.85$ or $0.90$). In commercial aviation operations, schedule-only features 2 hours prior to pushback inherently possess moderate discriminative signal due to exogenous tactical factors (ATC ground stops, inbound turn delays, surface congestion) that have not yet occurred at $T-2$h. An $\text{AUC} \approx 0.643$ is consistent with established literature for schedule-only pre-departure prediction.

### 1.2 Mathematical Dichotomy: Median Predictor vs. Machine Learning in Regression
- **The Phenomenon:** On both arrival and departure datasets, predicting the constant sample median ($\hat{y} \equiv -1.0$ or $-8.0$) achieves a lower overall Mean Absolute Error (MAE) than gradient-boosted trees:
  - Arrival: $\text{MAE}_{Median} = 16.76$ min vs $\text{MAE}_{XGBoost} = 20.22$ min.
  - Departure: $\text{MAE}_{Median} = 15.60$ min vs $\text{MAE}_{XGBoost} = 17.60$ min.
- **Scientific Root Cause:** Delay distributions are heavily right-skewed with high zero/negative mass (75–80% of flights are on time or early). The median is the theoretical Bayes optimal predictor for minimizing $L_1$ loss. A constant median predictor predicts that every flight is on time, effectively ignoring all tail risks.
- **Operational Justification for Machine Learning:**
  - In gate optimization, flights that are on time or early **do not cause gate conflicts**. Gate conflicts are caused exclusively by severe delays ($\ge 15$ min, $\ge 60$ min).
  - The constant median predictor has catastrophic tail error: $\text{Tail MAE}_{\ge 15} = 62.33$ min, $\text{Tail MAE}_{\ge 60} = 132.54$ min.
  - In contrast, XGBoost achieves: $\text{Tail MAE}_{\ge 15} = 48.91$ min ($-21.5\%$), $\text{Tail MAE}_{\ge 60} = 117.18$ min ($-11.6\%$), and $\text{RMSE} = 43.00$ min vs $45.76$ min ($-6.0\%$).
  - Therefore, Machine Learning is mandatory for downstream operations because it actively detects high-consequence gate disruption events.

### 1.3 Feasibility Barriers to Flight Chain and Weather Features
- **Flight Chain Features (Branch B):** BTS reporting captures completed flight linkages after the operating day ends. Without a verified schedule publication snapshot available at $T-2$h, utilizing tail number turnaround chains risks lookahead leakage regarding aircraft swap finality.
- **Weather Features (Branch C):** Raw Aeolus weather features represent METAR/ASOS ground station observations measured at flight time, **not** numerical weather forecasts (NWP) issued at $T-2$h. Using actual future weather observations represents severe temporal leakage.
- **Disposition:** Both branches remain classified as `HISTORICAL_EXPLORATORY_ABLATION` and are strictly excluded from certified real-time deployment.

## 2. Risk Matrix & Mitigation

| Identified Risk | Severity | Scientific Mitigation Implemented in G3 |
| :--- | :--- | :--- |
| **Claiming Heuristic Sigmoid is a Calibrated Classifier** | HIGH | Trained true classification baselines; fitted Platt & Isotonic calibrators; verified $\text{ECE} \approx 0.011 \le 0.05$. |
| **Claiming ML Beat Median on All Metrics** | MEDIUM | Fully documented that Median wins on MAE while ML wins on RMSE, Tail MAE, and operational gate conflict mitigation. |
| **Contaminating Evaluation Set with Calibration Fit** | HIGH | Isolated calibration to 2022 development partition; evaluated strictly on 2023 Selection split ($N = 332,734$). |
| **Using 2024 Data for Model Tuning** | CRITICAL | Enforced zero access to Year 2024 data during training, calibration, and threshold selection. |
