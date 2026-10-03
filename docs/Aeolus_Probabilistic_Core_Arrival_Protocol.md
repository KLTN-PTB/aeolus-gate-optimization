# Aeolus Gate Optimization — Probabilistic Core Arrival Protocol

**Tên phương án:** Probabilistic Core Arrival — Distributional Forecasting  
**Protocol nền:** Research Protocol V4.0 — Dual Prediction Architecture  
**Trạng thái:** Methodology đã chốt để triển khai thực nghiệm  
**Mục tiêu:** Xây dựng và đánh giá một Core Arrival probabilistic head tại thời điểm T−2h, sau đó kiểm tra khả năng đưa predictive distribution vào joint uncertainty, Monte Carlo và gate optimization.

---

## 1. Mục tiêu nghiên cứu

Mục tiêu của nhánh này **không phải** tìm một point estimator có MAE thấp hơn bằng mọi giá.

Các kết quả hiện tại cho thấy point regression trên information set hiện hành có tín hiệu rất yếu: XGBoost tuned đạt regression MAE khoảng 19.4 phút nhưng R² chỉ khoảng 0.0039 trên development OOF 2016–2022; các thử nghiệm robustness/tail cũng ghi nhận prediction collapse ở nhóm severe delay.

Vì vậy, câu hỏi nghiên cứu được khóa lại thành:

> **Với information set cố định tại T−2h, liệu distributional forecasting có cung cấp predictive information hữu ích hơn point forecasting, và lợi ích đó đến từ representation, conditional variance, mixture structure, calibration hay joint dependence?**

MDN là **một candidate implementation**, không phải kết luận đã được chọn trước.

Nếu NGBoost hoặc một probabilistic baseline khác tốt hơn MDN, đó vẫn là một kết quả nghiên cứu hợp lệ.

---

# 2. Protocol và phạm vi bắt buộc

## 2.1. Core Arrival

Population:

- Inbound flights: `DEST = ATL`.
- Prediction cutoff: `CRS_DEP_TIME - 2 hours`.
- Target classification tham chiếu: `y_arr_cls = 1[ARR_DELAY >= 15]`.
- Target regression: `y_arr_reg = ARR_DELAY`, signed minutes.
- Không `abs()`.
- Không clip ground truth.
- Không impute target.
- Không sử dụng Weather trong Core Arrival.
- Không sử dụng `DEP_DELAY`, probability của Departure, actual timestamps/durations hoặc outcome thực tế.
- Chỉ prediction từ Core Arrival được phép đi downstream vào simulation/optimization.

Core feature contract hiện hành gồm 11 predictor:

```text
CRS_ELAPSED_TIME
calendar_year
calendar_month
calendar_day_of_month
calendar_day_of_week
is_weekend
scheduled_departure_hour
scheduled_departure_minute
OP_CARRIER
ORIGIN
OP_CARRIER_FL_NUM
```

Protocol dự án xác định các predictor này theo Schedule + Calendar + Carrier + Route; Weather, actual-operation fields, identifiers và các feature Chain chưa được chứng minh point-in-time safe không được đưa vào Core Arrival.

## 2.2. Temporal protocol

Expanding-window development:

| Fold | Train | Validation |
|---|---|---|
| Fold 1 | 2016–2018 | 2019 |
| Fold 2 | 2016–2019 | 2020 |
| Fold 3 | 2016–2020 | 2021 |
| Fold 4 | 2016–2021 | 2022 |

Vai trò các năm:

- **2016–2022:** rolling development.
- **2023:** one-time selection giữa các candidate/system đã được đóng băng trước đó.
- **2024:** `FINAL_HOLDOUT`, chỉ đánh giá sau full-system freeze.

Không random split.

Mọi statistic, vocabulary, scaler, embedding index và learned preprocessing artifact phải fit riêng trên phần train tương ứng.

---

# 3. Stage 0 — Statistical + Protocol Freeze

Trước khi train bất kỳ candidate nào, phải tạo và khóa `protocol_manifest`.

## 3.1. Xác minh semantics của target

Kiểm tra thực tế:

```text
dtype
unique fractional values
min / max
frequency của fractional values
```

Không suy luận target là discrete chỉ từ tên field.

Nếu dữ liệu là integer-minute, phải kiểm tra thêm khả năng integer hóa/rounding từ nguồn dữ liệu nếu evidence trong data dictionary/source cho phép.

## 3.2. Hai likelihood representation cần được định nghĩa

### Continuous Gaussian mixture

Model latent continuous variable:

```text
Z | X ~ Σ π_k N(μ_k, σ_k²)
```

Likelihood dùng continuous density.

### Discretized Gaussian mixture

Nếu observation semantics phù hợp với quantization/rounding hoặc integer-minute modeling, candidate chính có thể dùng:

```text
P(Y=y | X)
=
Σ_k π_k [
    Φ((y + 0.5 - μ_k)/σ_k)
    -
    Φ((y - 0.5 - μ_k)/σ_k)
]
```

Điều này làm event probability và integer quantile nhất quán ngay từ likelihood.

**Không được code Φ(b)-Φ(a) một cách ngây thơ ở extreme tail.** Phải có numerical-stability implementation cho `log[Φ(b)-Φ(a)]`.

Quantile của discrete distribution phải được xác định bằng cumulative probability:

```text
Q(p) = min{ y : F(y) >= p }
```

không cần root-finding trên một step function.

Continuous và discretized formulation được giữ như hai implementation candidates trong development nhằm kiểm tra sensitivity của observation model; discretized chỉ trở thành primary specification khi target semantics hỗ trợ nó.

## 3.3. Representation manifest

### Time-of-day

Không encode hour và minute riêng.

```text
t = 60 * scheduled_departure_hour
  + scheduled_departure_minute
```

Sau đó:

```text
sin(2πt / 1440)
cos(2πt / 1440)
```

### Calendar cyclic features

```text
calendar_month → sin/cos
calendar_day_of_week → sin/cos
```

### Numeric còn lại

```text
CRS_ELAPSED_TIME
calendar_year
calendar_day_of_month
is_weekend
```

- median imputation;
- StandardScaler;
- fit trên outer-train only.

`calendar_year` vẫn thuộc V1 contract, nhưng sẽ có controlled ablation `with/without` vì dự án đã ghi nhận PSI cao trong V2.

### Categorical

- `OP_CARRIER`
- `ORIGIN`
- `OP_CARRIER_FL_NUM`

Mỗi fold:

```text
train categories
    ↓
assign integer indices
    ↓
reserve dedicated UNKNOWN index
```

Không dùng `-1` hoặc `0` như sentinel mang semantics của tree pipeline cho embedding lookup.

`OP_CARRIER_FL_NUM` được gọi là:

> service/schedule identity

không gọi là aircraft entity/tail identity.

## 3.4. Early stopping protocol

Outer validation không được dùng để chọn epoch.

Ví dụ Fold 1:

```text
outer train = 2016–2018
outer val   = 2019
```

Inner split:

```text
inner train = 2016–2017
inner val   = 2018
```

Quy trình:

```text
1. Fit preprocessing trên inner-train.
2. Train candidate trên inner-train.
3. Chọn best_epoch bằng inner-val.
4. Refit/retrain model từ đầu trên TOÀN BỘ outer-train 2016–2018
   với đúng best_epoch đã chọn.
5. Fit lại toàn bộ scaler/vocabulary/embedding-index trên outer-train.
6. Transform outer-val.
7. Đánh giá outer-val.
```

Không mang model đang train dở ở inner-train trực tiếp sang outer-val.

---

# 4. Stage 1 — Distributional Baselines

Các baseline phải chạy **trước MDN**.

## B1 — Empirical carrier × scheduled-hour distribution

Fit train-only.

Backoff:

```text
carrier × hour
    ↓ insufficient support
carrier
    ↓
global
```

Không dùng validation/future-year statistics.

## B2 — XGBoost mean + cross-fitted residual uncertainty

Point mean:

```text
XGBoost tuned
```

Uncertainty:

```text
OOF predictions trên outer-train
    ↓
residual = y - yhat_OOF
    ↓
estimate sigma
```

Không dùng in-sample residual để ước lượng sigma.

Điều này là chống optimistic residual estimation/resubstitution bias, không gọi là target leakage.

## B3 — NGBoost Normal

Distribution:

```text
Y | X ~ Normal(μ(X), σ(X))
```

`σ(X)` là heteroscedastic.

Đây là probabilistic baseline trực tiếp cạnh tranh với K=1 heteroscedastic neural model.

## B4 — LightGBM Quantile

Không coi đây là full-CDF model mặc định.

Quantiles tối thiểu:

```text
q = 0.025
q = 0.05
q = 0.10
q = 0.25
q = 0.50
q = 0.75
q = 0.90
q = 0.95
q = 0.975
```

Đánh giá:

- pinball loss;
- quantile coverage;
- interval width;
- quantile-crossing rate.

Nếu dùng monotonic rearrangement/isotonic correction hoặc procedure quantile→CDF, phải đăng ký trước và procedure đó trở thành một phần của candidate.

B4 không được đưa trực tiếp vào CRPS comparison trừ khi đã có CDF construction được định nghĩa trước.

## B5 — Heavy-tail candidate (chỉ khi pre-registered)

Không dùng placeholder kiểu:

```text
different loss/config
```

Nếu muốn mở rộng phải chỉ rõ model, ví dụ:

```text
NGBoost Student-T
```

và cấu hình phải được khóa trước.

---

# 5. Stage 2 — Representation Ablation

Mục tiêu:

> Tách contribution của representation khỏi contribution của model family/loss.

Các candidate:

```text
R1: NN-point + frequency-map
R2: NN-point + embedding
```

Có thể thêm low-card one-hot trong controlled ablation:

```text
R0: NN-point + one-hot(low-card)
```

Điều kiện:

- cùng architecture;
- cùng optimizer;
- cùng learning-rate policy;
- cùng batch policy;
- cùng early-stopping policy;
- cùng seed;
- cùng numeric preprocessing;
- chỉ thay representation cần kiểm tra.

Kết luận được phép viết:

> embedding representation outperforms frequency representation

không được nhảy thẳng thành:

> neural network discovers stronger nonlinear signal.

Nếu câu hỏi riêng là contribution của `OP_CARRIER_FL_NUM`, giữ representation của `OP_CARRIER` và `ORIGIN` cố định khi thay flight-number representation.

---

# 6. Stage 3 — Distribution Ablation

Không nhảy thẳng vào K=3.

## 6.1. Ladder bắt buộc

```text
D1: K=1, fixed global sigma
D2: K=1, sigma(x)
D3: K=3 Gaussian mixture
```

K=5 chỉ chạy nếu K=3 đạt tiêu chí mở rộng đã đăng ký trước.

Ladder này tách được:

```text
heteroscedasticity
vs
mixture structure
```

## 6.2. Sigma parameterization

Không sử dụng arbitrary rule:

```text
log_sigma ∈ [-3, 3]
```

và cũng không để sigma hoàn toàn không ràng buộc.

Primary implementation:

```text
sigma = softplus(raw_sigma) + sigma_floor
```

hoặc predict-log-sigma với constraint được định nghĩa rõ.

Phải có:

- sigma floor;
- gradient clipping;
- finite-value checks;
- initialization policy;
- sensitivity test cho sigma constraints.

Lý do giữ sigma floor gồm:

1. numerical stability;
2. tránh variance collapse;
3. tránh nghiệm suy biến của Gaussian-mixture likelihood khi component co variance về 0.

## 6.3. Initialization

Phải khóa:

```text
mixture weight initialization
mean initialization
sigma initialization
random seed
```

Không chỉ dựa vào seed.

Có thể sử dụng quantile-based initial means nếu implementation study xác định cách đó trước.

## 6.4. Architecture v1

Bản v1 ưu tiên đơn giản:

```text
Input
  ↓
Embeddings
  +
Cyclic numeric features
  +
Scaled numeric features
  ↓
Linear 128
  ↓
GELU
  ↓
Linear 64
  ↓
GELU
  ↓
Linear 32
  ↓
Distribution head
```

- Không BatchNorm ở v1.
- Không dropout ở v1.
- Không multi-task classifier ở v1.
- Batch size screening: 1024 / 2048 / 4096; đây là reproducibility/performance check, không phải open-ended HPO.

---

# 7. Stage 4 — MDN Correctness Test Suite

Không dùng 399 test hiện có như bằng chứng rằng MDN đã đúng.

Phải có suite riêng.

## 7.1. Mathematical correctness

Kiểm tra:

```text
Σ π_k = 1
π_k >= 0

finite log-prob
finite gradient

no NaN / Inf

sigma > 0
```

## 7.2. Distribution correctness

```text
CDF monotonic
quantile monotonic
sampling valid
probabilities in [0,1]
```

Nếu target discrete:

```text
Σ_y P(Y=y) ≈ 1
P(Y >= threshold) consistent with CDF
```

## 7.3. Synthetic recovery

Sinh dữ liệu từ một distribution đã biết:

```text
known Gaussian mixture
```

Sau đó:

```text
fit candidate
→ check recovery
```

Không yêu cầu parameter recovery tuyệt đối do label switching; đánh giá distributional recovery.

## 7.4. Permutation-invariant diagnostics

Không gán semantic cố định cho:

```text
component 1
component 2
...
```

Giữ:

```text
component entropy
effective number of components = 1 / Σπ_k²
max component weight
fraction π_k < ε
sigma quantiles
sorted component means
```

---

# 8. Stage 5 — Stability

Screening:

```text
1 fixed seed
```

Finalist:

```text
3 PRE-REGISTERED seeds
```

Ví dụ:

```text
s1, s2, s3
```

phải được ghi vào manifest trước khi mở 2023.

Báo cáo riêng:

### Algorithmic stability

```text
mean ± SD across seeds
successful-run rate
```

### Statistical uncertainty

```text
paired day-level / block bootstrap CI
```

Không dùng seed SD thay cho sampling uncertainty.

## 8.1. Chính sách 3 seed

Phải chọn trước một trong:

```text
A. evaluation-only
B. seed ensemble = average of 3 seed predictions
C. deploy one predetermined seed
```

Nếu sử dụng seed ensemble thì đó là **một candidate riêng**, không được tạo ensemble sau khi nhìn thấy seed variance.

---

# 9. Stage 6 — Forecast Evaluation

## 9.1. Gate A — Calibration

Kiểm tra:

```text
50%
80%
90%
95%
```

prediction interval coverage.

Kèm:

```text
interval width
sharpness
randomized PIT nếu target discrete
```

PIT phải xem:

```text pooled
fold-wise
delay-regime-wise
predicted-risk / uncertainty buckets
```

## 9.2. Gate B — Proper scoring

Full-CDF candidates:

```text
CRPS
NLL / LogScore
```

CRPS là một metric chính quan trọng nhưng không phải “ông vua” tuyệt đối.

B4 quantile-only không được đưa vào bảng CRPS nếu chưa có registered CDF construction.

## 9.3. Gate C — Event probabilities

Các event:

```text
Y >= 15
Y >= 60
Y >= 120
```

Phải đánh giá probability forecast bằng:

```text
Brier score
LogScore
calibration
calibration slope/intercept nếu đủ dữ liệu
```

Không coi giá trị:

```text
P(Y >= k)
```

tự nó là metric.

Nếu target integer và đã xác minh observation semantics, event probability phải nhất quán với discrete likelihood / CDF convention.

## 9.4. Quantile evaluation

```text
pinball q=.90
pinball q=.95
```

và các quantile cần thiết cho intervals.

Kiểm tra:

```text
coverage
width
crossing rate
```

## 9.5. Time robustness

Báo cáo:

```text pooled
Fold 1
Fold 2
Fold 3
Fold 4
year-wise
```

đặc biệt chú ý 2020 vì regime khác biệt rõ.

Không dùng pooled score để giả vờ rằng mọi năm đều đồng nhất.

---

# 10. Uncertainty estimation cho model comparison

Vì flight trong cùng ngày không độc lập hoàn toàn, model comparison không dựa trên naive row-level bootstrap.

Primary comparison:

```text per-flight score difference
↓
aggregate by day
↓
day/block bootstrap
↓
CI của Δ score
```

Đối với CRPS:

\[
\Delta CRPS =
CRPS_{candidate}-CRPS_{baseline}
\]

Đăng ký `δ` trước.

Gate kiểu:

```text lower bound của CI cho improvement > δ
```

có thể được dùng cho practical improvement.

Không được chọn δ sau khi nhìn kết quả.

Pooled/year-wise results vẫn phải báo riêng; CI pooled không thay thế time-heterogeneity analysis.

---

# 11. Stage 6.5 — Candidate Pruning

Không dùng rule arbitrary:

```text top-2
top-3
```

vì số lượng đó là hyperparameter ngầm.

Thay vào đó giữ các candidate:

```text score <= best_score + δ_screen
AND
calibration guard passed
AND
tail guard passed
```

`δ_screen` phải đăng ký trước.

Mục tiêu của stage này chỉ là:

> loại candidate clearly dominated để giảm compute.

Không được loại một candidate chỉ vì marginal score kém nhẹ nếu candidate có đặc tính tail/calibration khác biệt đáng kể.

---

# 12. Stage 7 — Complete System Candidate Construction

Một “candidate” không chỉ là model marginal.

Candidate hoàn chỉnh phải chứa:

```text
candidate_id

feature manifest
representation manifest

marginal model family
model architecture
training policy
weights

calibration object

dependence mechanism
dependence parameters

sampling procedure
Monte Carlo interface

simulation interface

optimization interface

seed policy
```

Không để một component quan trọng “sẽ quyết định sau 2023”.

---

# 13. Joint Dependence Candidate Families

## D0 — Independent baseline

```text
Y_i independently sampled from each marginal
```

D0 là baseline bắt buộc.

## D1 — Scenario / block dependence

Scenario library có thể dùng residual structure từ development nhưng scenario selection chỉ được condition trên information có sẵn trước T−2h, ví dụ:

```text
scheduled flight composition
carrier mix
scheduled time density
season
other planning/schedule variables
```

Không dùng:

```text
actual realized delay
actual cancellation
actual ATC outcome
actual weather outcome
```

để chọn scenario cho ngày đang mô phỏng.

## D2 — Gaussian copula

Giữ như một candidate family, không mặc định thắng.

## D3 — Tail-dependent copula

Chỉ mở nếu diagnostic development cho thấy tail co-exceedance cần model dependence có tail behavior mạnh hơn Gaussian copula.

Không được mở D3 một cách tùy ý sau khi nhìn kết quả.

---

# 14. Requirements cho dependence construction

Không sử dụng correlation matrix cố định `n × n`.

Số flight mỗi ngày thay đổi.

Dependence construction phải:

1. hoạt động với arbitrary daily number of flights;
2. condition được theo observable pre-cutoff covariates;
3. bảo đảm valid joint distribution;
4. nếu dùng Gaussian copula phải đảm bảo correlation matrix positive semidefinite;
5. không tạo double-counting do uncertainty đã có trong marginal.

“Pairwise correlation function” tự nó chưa đủ.

Một construction valid có thể dựa trên latent factor/kernel/covariance construction bảo đảm PSD.

---

# 15. Discrete PIT và Dependence Modeling

Nếu `ARR_DELAY` là discrete:

\[
U = F(Y^-)+V[F(Y)-F(Y^-)]
\]

với:

```text
V ~ Uniform(0,1)
```

Phải cố định hoặc kiểm soát randomization scheme.

Không được lấy một randomization ngẫu nhiên không kiểm soát rồi coi toàn bộ dependence signal là observed truth.

Dependence estimation phải kiểm tra sensitivity với randomized PIT.

Đối với discrete margins, copula representation không unique; vì vậy không được tuyên bố copula “đã giải quyết dependence” chỉ từ công thức.

---

# 16. Không double-count uncertainty

Không được giả định rằng:

```text
marginal MDN variance
+
scenario variance
```

có thể cộng độc lập.

Nếu marginal đã chứa unobserved common-shock uncertainty, việc thêm latent factor/scenario có thể đếm hai lần.

Nếu dùng copula:

```text
marginal CDFs
+
dependence structure
```

được tách về mặt construction, nhưng toàn bộ estimation pipeline vẫn phải được kiểm tra để bảo đảm dependence layer không tái sử dụng uncertainty theo cách gây double-count.

---

# 17. Stage 7.5 — Joint Validation

Joint validation phải hoàn tất **trước 2023 final system selection**.

Các baseline:

```text
D0 Independent
D1 Scenario/block
D2 Gaussian copula
D3 Tail-dependent candidate (nếu preregistered)
```

Đánh giá bằng dữ liệu development 2016–2022.

## Joint diagnostics

So sánh mô hình với historical observations:

```text
pairwise exceedance
P(two flights both severe)
P(N60 >= k)
P(N120 >= k)

number of severe-delay flights per day
max concurrent severe delays

daily total delay
daily aggregate tail
```

Không chỉ kiểm tra marginal calibration.

Một joint model chỉ được giữ nếu reproduce được dependence structure ở mức chấp nhận được.

Nếu dependence candidate fail ở development:

```text reject candidate
```

không sửa tùy ý sau khi đã nhìn 2023.

---

# 18. Stage 8 — 2023 One-Time System Selection

Đây là checkpoint chọn **complete system**, không phải chỉ chọn marginal model.

Quy trình:

```text
2016–2022
    ↓
build candidate systems
    ↓
forecast evaluation
    ↓
joint validation
    ↓
freeze candidate systems
    ↓
2023
    ↓
select ONE complete system
    ↓
no further model/dependence/calibration selection
```

2023 không được dùng để:

- mở architecture mới;
- thử thêm HPO;
- thay seed;
- chọn copula mới;
- thay scenario mechanism;
- thay calibration rule.

2023 chỉ dùng để chọn giữa complete candidates đã được freeze.

---

# 19. Stage 9 — Monte Carlo / Gate Simulation

Sau khi candidate hoàn chỉnh được chọn:

```text
selected marginal
+
selected dependence mechanism
↓
joint flight-delay samples
↓
Monte Carlo
↓
Synthetic Aircraft Turn
↓
Gate Simulation
↓
Greedy / CP-SAT / CP-SAT + SA
```

Không thay model trong giai đoạn này.

## Downstream utility

Đánh giá các chỉ số liên quan đến optimizer/simulation, ví dụ:

```text
gate conflicts
overflow
concurrent occupancy
utilization
risk measures
```

Downstream utility **không phải Gate A/B/C** của forecast evaluation; nó là evaluation layer riêng sau khi joint model đã được xác định.

---

# 20. Joint Model Validation trước khi tin Monte Carlo

Trước khi cho joint model vào CP-SAT:

```text historical day
        ↓
simulate delays
        ↓
compare historical vs simulated
```

Phải kiểm tra:

```text
marginal calibration
+
pairwise dependence
+
co-exceedance
+
daily severe counts
+
daily aggregate tails
```

Nếu joint distribution fail → candidate fail.

Không được vì downstream tiện mà bỏ qua validation.

---

# 21. Stage 10 — FULL SYSTEM FREEZE

Trước khi mở 2024, freeze toàn bộ:

```text feature set
representation
preprocessing
model architecture
weights
training policy
seed(s)
calibration
distribution family
dependence model
dependence parameters
sampling procedure
Monte Carlo configuration
simulation configuration
optimization configuration
```

Tạo một `full_system_freeze_manifest`.

Sau checkpoint này:

```text no retune
no architecture change
no threshold change
no seed change
no scenario change
no calibration change
no dependence change
```

---

# 22. Stage 11 — 2024 FINAL HOLDOUT

2024 chỉ được dùng cho:

```text final evaluation
```

Không được dùng để:

- chọn model;
- chọn hyperparameter;
- thay calibration;
- thay dependence;
- thay Monte Carlo configuration;
- thay optimization configuration.

Nếu phát hiện vấn đề trên 2024:

```text record finding
```

không tự ý sửa rồi báo lại 2024 là final.

---

# 23. Decision Rules cuối cùng

## Forecast-level

Một candidate có thể đi tiếp nếu:

```text
Calibration gate passed
AND
proper scoring không bị dominated
AND
tail/event calibration không thất bại nghiêm trọng
AND
stability acceptable
```

Không bắt buộc một model phải thắng mọi metric.

## Practical improvement

Phải có:

```text preregistered δ
+
day/block bootstrap CI
```

Không dựa chỉ trên mean difference.

## Final tie-break

Nếu có nhiều complete candidates cùng pass gates:

```text chọn CRPS thấp nhất
```

chỉ khi:

- candidate có full CDF;
- tie-break được đăng ký trước;
- không được thêm tiêu chí mới sau khi nhìn kết quả.

---

# 24. Quy tắc cho seed

Seed phải được xem là một phần của experimental protocol.

Ví dụ:

```text screening_seed = S0
finalist_seeds = [S1, S2, S3]
```

Tất cả được khóa trước 2023.

Nếu dùng ensemble 3 seed:

```text seed ensemble = separate candidate
```

không được tạo sau khi xem seed variance.

Báo cáo:

```text successful-run rate
mean ± SD across seeds
day-block bootstrap CI
```

là hai nguồn uncertainty khác nhau.

---

# 25. Quy tắc cho MDN component interpretation

Không được viết:

```text component 1 = on-time
component 2 = mild delay
component 3 = severe delay
```

trừ khi có một post-hoc semantic analysis được định nghĩa riêng.

Component labels có permutation symmetry.

Thay vào đó báo cáo:

```text mixture entropy
effective component count
weight concentration
sorted component means
sigma quantiles
predictive distribution quantiles
```

---

# 26. Các điều KHÔNG được làm

```text
Không random split.

Không fit preprocessing trên validation/future year.

Không đọc 2024 trong quá trình selection.

Không dùng in-sample residual để estimate predictive sigma.

Không gọi frequency-map representation là learned embedding.

Không gọi OP_CARRIER_FL_NUM là aircraft identity.

Không mặc định K=3 vì semantic "on-time/mild/severe".

Không mặc định Gaussian copula.

Không dùng fixed correlation matrix cho mọi daily n.

Không tạo pairwise correlation mà không kiểm tra PSD.

Không gọi P(Y>=k) là một metric hoàn chỉnh.

Không tính CRPS cho quantile-only baseline nếu chưa có CDF.

Không dùng outer validation để early-stop.

Không chọn seed sau khi nhìn kết quả.

Không tạo ensemble sau khi nhìn seed variance.

Không chạy K=5 chỉ vì K=3 hơi kém mà không có rule mở rộng preregistered.

Không thay dependence mechanism sau khi đã xem 2023.

Không tune sau khi mở 2024.

Không dùng actual operational information của ngày đang mô phỏng để chọn scenario.

Không double-count marginal uncertainty và common-shock uncertainty.

---

# 27. Experimental Story cuối cùng

Câu chuyện nghiên cứu phải giữ đúng cấu trúc:

```text
Weak point-regression signal
        ↓
Question:
Does distributional forecasting add value?
        ↓
Representation ablation
        ↓
Heteroscedasticity ablation
        ↓
Mixture ablation
        ↓
Calibration + proper scoring
        ↓
Tail probability evaluation
        ↓
Joint dependence evaluation
        ↓
Monte Carlo / gate utility
        ↓
Final holdout 2024
```

Không biến luận văn thành:

> “Thử nhiều neural network rồi MDN thắng.”

Mục tiêu là xác định **nguồn gốc của predictive value**.

Các kết quả sau đều hợp lệ:

```text
NGBoost > MDN
```

→ probabilistic formulation có ích, MDN không có added value.

```text
K=1 heteroscedastic > K=3
```

→ conditional variance đủ, mixture là overengineering.

```text
K=3 > K=1 > XGBoost
```

→ mixture/distributional structure đóng góp thêm.

```text
marginal tốt nhưng joint model fail
```

→ predictive marginals không đủ cho downstream simulation.

```text
joint model cải thiện simulation
```

→ uncertainty modeling có downstream value thực sự.

---

# 28. Cấu trúc artifact đề xuất

Repository nên có tối thiểu:

```text
artifacts/
├── manifests/
│   ├── probabilistic_protocol_v1.json
│   ├── representation_manifest_v1.json
│   ├── seed_manifest_v1.json
│   ├── distribution_candidate_manifest_v1.json
│   ├── dependence_candidate_manifest_v1.json
│   └── full_system_freeze_manifest_v1.json
│
├── probabilistic/
│   ├── baseline_empirical/
│   ├── xgb_gaussian/
│   ├── ngboost/
│   ├── lightgbm_quantile/
│   └── mdn/
│
├── calibration/
│   ├── coverage/
│   ├── randomized_pit/
│   └── event_calibration/
│
├── dependence/
│   ├── independent/
│   ├── scenario/
│   ├── gaussian_copula/
│   └── tail_copula/
│
└── evaluation/
    ├── forecast_metrics/
    ├── joint_metrics/
    ├── downstream_metrics/
    └── final_holdout_2024/
```

---

# 29. Final Go / No-Go Logic

```text
                 Point prediction weak
                         │
                         ▼
              Distributional candidates
                         │
          ┌──────────────┴──────────────┐
          │                             │
      No useful gain                Useful gain
          │                             │
       Stop MDN                  Compare source of gain
                                        │
                        ┌───────────────┼───────────────┐
                        │               │               │
                   embedding       sigma(x)         mixture
                        │               │               │
                        └───────────────┴───────────────┘
                                        │
                                  calibration
                                        │
                                  tail events
                                        │
                                joint dependence
                                        │
                                 Monte Carlo
                                        │
                                 gate utility
                                        │
                                 full freeze
                                        │
                                  2024 holdout
```

---

# 30. Tuyên bố phương pháp cuối cùng

Phương án này không giả định MDN là mô hình thắng.

Phương án này khóa trước:

1. information set;
2. temporal protocol;
3. representation;
4. preprocessing;
5. validation hierarchy;
6. candidate families;
7. seed policy;
8. calibration methodology;
9. uncertainty comparison;
10. dependence construction;
11. downstream evaluation;
12. final holdout policy.

Do đó kết quả cuối cùng có thể bác bỏ chính MDN mà vẫn hoàn thành đầy đủ câu hỏi nghiên cứu.

**Nguyên tắc trung tâm:**

> **Output distribution is the research requirement; MDN is only one candidate implementation.**

---

## Nguồn nội bộ dùng làm cơ sở

Protocol hiện hành quy định Core Arrival là inbound `DEST=ATL`, dự báo tại `CRS_DEP_TIME - 2 hours`, dùng signed `ARR_DELAY`, không dùng Weather/actual outcomes; 2024 là sealed final holdout và 2023 có vai trò model selection/controlled development. 

Feature contract V1 hiện hành gồm 11 predictor và pipeline yêu cầu preprocessing fit theo train fold; `OP_CARRIER_FL_NUM` hiện là frequency-mapped trong tree/linear pipelines, còn V2 đã ghi nhận cảnh báo drift của `calendar_year`.

Kết quả development hiện tại cho thấy XGBoost tuned có MAE khoảng 19.408 phút, R² khoảng 0.0039; severe-delay diagnostics cho thấy prediction collapse ở nhiều point models và quantile diagnostics cho thấy trade-off mạnh giữa overall accuracy và tail behavior.

