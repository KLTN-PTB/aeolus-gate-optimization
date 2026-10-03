TÀI LIỆU BÀN GIAO KIẾN TRÚC PHẦN MỀM & KỸ THUẬT HỆ THỐNG        
                                                                   
  ## DỰ ÁN: AEOLUS GATE OPTIMIZATION RESEARCH PLATFORM             
                                                                   
  Dành cho Kỹ sư Phần mềm / Kỹ sư Nghiên cứu tiếp nhận dự án       
  ──────                                                           
  ## 1. TỔNG QUAN & CÔNG NGHỆ SỬ DỤNG                              
                                                                   
  ### 1.1. Mục đích chính của dự án                                
                                                                   
  Aeolus Gate Optimization là một nền tảng nghiên cứu và tối ưu hóa
  toán học tích hợp học máy xác suất (Probabilistic Machine        
  Learning + Stochastic Combinatorial Optimization).               
                                                                   
  Hệ thống giải quyết bài toán cốt lõi: Gán cổng tàu bay tại sân   
  bay quốc tế Hartsfield–Jackson Atlanta (KATL) dưới điều kiện bất 
  định thời gian thực (Airport Gate Assignment Problem - AGAP under
  Uncertainty).                                                    
                                                                   
  Hệ thống hoạt động theo chu trình khép kín:                      
                                                                   
    Predict (T - 2h) ⟶ Dependence Sampling (Copula) ⟶ Synthesize   
  Turns ⟶ Gate Optimization (CP-SAT/SA) ⟶ Independent Verification 
                                                                   
  #### Nguyên tắc nghiên cứu bất biến (Fail-Closed Protocol):      
                                                                   
  1. Điểm cắt thông tin nghiêm ngặt (T - 2h): Mọi dự báo về chuyến 
  bay đến (DEST=ATL) chỉ được sử dụng thông tin có sẵn tại thời    
  điểm T - 2 giờ trước giờ khởi hành dự kiến (CRS_DEP_TIME - 2h).  
  Tuyệt đối không dùng thời gian khởi hành thực tế (DEP_DELAY), trễ
  đến thực tế (ARR_DELAY), hay thời tiết chưa được kiểm toán nguồn 
  gốc thời gian.                                                   
  2. Dữ liệu thô bất biến (Raw Data Immutability): Toàn bộ dữ liệu 
  gốc trong data/raw/ là bất biến (Read-only, 0% sửa đổi).         
  3. Phân chia thời gian & Cách ly tập kiểm định:                  
      • 2016–2022: Huấn luyện nếp cuộn mở rộng (Expanding-window   
      Rolling Folds 1–4) và huấn luyện tiền đóng băng (Stage 10    
      Full System Freeze).                                         
      • 2023: Tập dữ liệu phát triển độc lập dùng cho Model        
      Selection và Benchmark mở rộng.                              
      • 2024: Tập kiểm định cuối cùng (FINAL_HOLDOUT), đã mở trong 
      lịch sử dự án, trạng thái hiện tại là POST_HOLDOUT_STABILIZED.
      Tuyệt đối không dùng năm 2024 để huấn luyện, căn chỉnh, hay  
      tinh chỉnh tham số bộ giải.                                  
                                                                   
  ──────                                                           
  ### 1.2. Danh mục Công nghệ, Thư viện & Cơ sở Dữ liệu            
                                                                   
  Dự án vận hành trên môi trường Python 3.11 độc lập (tại .venv).  
  Các thư viện chính được cố định phiên bản chặt chẽ:              
                                                                   
   Phân hệ chức n… │ Thư viện / Côn… │ Phiên bản │ Vai trò kỹ thu…
  ─────────────────┼─────────────────┼───────────┼─────────────────
   Môi trường thực │ Python          │  3.11.15  │ Runtime engine
   thi             │                 │           │ chính của toàn
                   │                 │           │ bộ codebase
   Quy hoạch & Tối │ Google OR-Tools │ 9.15.6755 │ Bộ giải chính
   ưu hóa          │                 │           │ xác
                   │                 │           │ CPSatGateSolver
                   │                 │           │ (Constraint
                   │                 │           │ Programming /
                   │                 │           │ SAT)
                   │ SciPy           │  1.17.1   │ Đại số tuyến
                   │                 │           │ tính, phân phối
                   │                 │           │ xác suất, chiếu
                   │                 │           │ phổ PSD, và
                   │                 │           │ HiGHS MILP
   Mô hình hóa Xác │ NGBoost         │  0.5.11   │ Natural
   suất & ML       │                 │           │ Gradient
                   │                 │           │ Boosting phân
                   │                 │           │ phối Student-T
                   │                 │           │ (B5_ngboost_stu
                   │                 │           │ dent_t)
                   │ PyTorch         │  2.14.0   │ Thử nghiệm mạng
                   │                 │           │ nơ-ron phân
                   │                 │           │ phối (Mixture
                   │                 │           │ Density
                   │                 │           │ Networks - MDN)
                   │ LightGBM        │   4.7.0   │ Hồi quy phân vị
                   │                 │           │ (Quantile
                   │                 │           │ Regression) và
                   │                 │           │ phân loại trễ
                   │                 │           │ baseline
                   │ XGBoost         │   3.2.0   │ Mô hình
                   │                 │           │ Gradient
   Dữ liệu Cột │ Parquet      │           │ Đọc/ghi dữ liệu lịch
               │ (PyArrow)    │           │ bay và kết quả kịch
               │              │           │ bản
               │ Pandas       │   2.3.3   │ Thao tác bảng dữ liệu
               │              │           │ chuyến bay, lịch trình
               │              │           │ và tham số
               │ NumPy        │   2.2.6   │ Tính toán ma trận hiệp
               │              │           │ phương sai, đại số ma
               │              │           │ trận, vector hóa
   Kiểm thử &  │ PyTest       │   9.1.1   │ Framework tự động kiểm
   Tiện ích    │              │           │ định 6 phân tầng
               │              │           │ (115/115 tests PASS)
               │ PyYAML       │   6.0.3   │ Phân tích cú pháp cấu
               │              │           │ hình
               │ Psutil       │   7.2.2   │ Giám sát bộ nhớ RAM và
               │              │           │ thời gian thực thi
               │              │           │ thuật toán
                                                                   
  │ Note                                    
  │ Hệ cơ sở dữ liệu: Dự án không sử dụng RDBMS truyền thống       
  │ (PostgreSQL, MySQL) mà sử dụng kiến trúc File-Based Immutable  
  │ Data Lake dựa trên chuẩn tệp Parquet (cho tập dữ liệu lớn hàng 
  │ chục triệu dòng) và JSON/JSONL (cho các artifacts, manifests,  
  │ audit traces và mã băm SHA-256).                               
  ──────                                                           
  ## 2. CẤU TRÚC THƯ MỤC (DIRECTORY STRUCTURE)                     
                                                                   
  Dưới đây là cây thư mục kiến trúc tối giản của dự án:            
                                                                   
    Aeolus/                                                        
    ├── artifacts/                           # Kho lưu trữ hiện vật
  kiểm toán & kết quả nghiên cứu                                   
    │   ├── audit/                           # Manifests kiểm toán 
  kỹ thuật (Steps 1–6)                                             
    │   ├── development_end_to_end/          # Kết quả đối sánh E2E
  trên dữ liệu 2023 (Step 7)                                       
    │   ├── final_code_audit/                # Báo cáo kiểm định   
  toàn diện 6 test suites                                          
    │   └── manifests/                       # Khóa trạng thái các 
  giai đoạn (Stages 0–11)                                          
    ├── data/                                # Quản lý dữ liệu phân
  tầng bất biến                                                    
    │   ├── raw/                             # DỮ LIỆU THÔ BẤT BIẾN
  (BTS On-Time Performance 2016-2024)                              
    │   ├── processed/                       # Dữ liệu đã làm sạch 
  & Chuỗi xoay vòng máy bay (48M dòng)                             
    │   └── simulation/                      # Không gian đệm kịch 
  bản mô phỏng                                                     
    ├── docs/                                # Tài liệu đặc tả giao
  thức & Báo cáo kỹ thuật                                          
    │   ├── Aeolus_Probabilistic_Core_Arrival_Protocol.md  # Đặc tả
  giao thức xác suất (Stages 0-11)                                 
    │   ├── BAO_CAO_TIEN_TRINH_VA_KET_QUA_STEP_1_DEN_STEP_7.md #   
  Báo cáo chi tiết 7 bước tối ưu                                   
    │   └── BAO_CAO_TONG_KET_PHASE_E_F_G_H_OPTIMIZATION.md     #   
  Báo cáo tổng thể tối ưu hóa                                      
    ├── scripts/                             # Các kịch bản chạy   
  pipeline, benchmark và audit                                     
    │   ├── run_development_end_to_end_benchmark.py       #        
  Pipeline E2E khép kín chuẩn (Step 7)                             
    │   ├── run_final_code_audit.py                        # Kịch  
  bản chạy toàn bộ 115 tests                                       
    │   ├── run_phase_f_time_limited_sa_benchmark.py       #       
  Benchmark Simulated Annealing (Step 3)                           
    │   └── run_phase_g_timeline_semantics_audit.py        # Kiểm  
  toán ngữ nghĩa dòng thời gian (Step 6)                           
    ├── src/                                 # MÃ NGUỒN CỐT LÕI    
  (CORE SOURCE CODE)                                               
    │   ├── audit/                           # Chốt an toàn giao   
  thức, kiểm toán năm & số chiều                                   
    │   ├── data/                            # Nạp dữ liệu, kiểm   
  tra rò rỉ (leakage rules), access guards                         
    │   ├── dependence/                      # Mô hình tương quan  
  Copula & Chiếu phổ ma trận PSD                                   
    │   ├── features/                        # Xây dựng đặc trưng  
  an toàn tại điểm cắt T-2h                                        
    │   ├── models/                          # Các mô hình học máy 
  cơ sở và nhánh xác suất                                          
    │   │   └── probabilistic/               # Phân phối Student-T,
  Mixture Density, Likelihood, Freeze                              
    │   ├── optimization/                    # Động cơ tối ưu hóa  
  gán cổng (AGAP)                                                  
    │   │   ├── config.py                    # Cấu hình tham số và 
  trọng số hàm mục tiêu                                            
    │   │   ├── domain.py                    # Thực thể nghiệp vụ  
  (Flight, Gate, Window, Objective)                                
    │   │   ├── evaluation.py                # Bộ đánh giá mục tiêu
  chung (Common Evaluator)                                         
    │   │   ├── sa/                          # Bộ giải             
  metaheuristic Simulated Annealing                                
    │   │   └── solvers/                     # Bộ giải chính xác   
  CP-SAT & Greedy Heuristic                                        
    │   └── simulation/                      # Mô phỏng dòng thời  
  gian quay đầu & phát hiện xung đột                               
    ├── tests/                               # HỆ THỐNG KIỂM THỬ   
  PHÂN TẦNG (115 TESTS)                                            
    ├── requirements.txt                     # Danh mục thư viện   
  Python bắt buộc                                                  
    └── README.md                            # Hướng dẫn tổng quan 
  dự án                                                            
                                                                   
  ### Chức năng ngắn gọn của từng thư mục lớn:                     
                                                                   
  • src/optimization/: Trái tim thuật toán tối ưu hóa. Cung cấp bộ 
  giải chính xác Google CP-SAT, bộ giải xấp xỉ Simulated Annealing 
  và bộ đánh giá khách quan độc lập.                               
  • src/simulation/: Mô phỏng thực tế vận hành mặt đất, biến đổi độ
  trễ dự báo thành các mốc thời gian chiếm dụng cổng (AircraftTurn),
  và phát hiện xung đột thời gian thực (ConflictDetector).         
  • src/dependence/: Mô hình hóa tương quan không gian - thời gian 
  giữa các chuyến bay cùng ngày bằng Gaussian Copula (D2) và thuật 
  toán chiếu phổ ma trận PSD.                                      
  • src/models/probabilistic/: Khung dự báo phân phối độ trễ tại T -
  2h (Student-T, Normal, Log-Likelihood, CRPS, Calibration).       
  • src/audit/: "Bức tường lửa" bảo vệ tính toàn vẹn nghiên cứu:   
  chặn rò rỉ năm 2024, xác thực vai trò phân vùng dữ liệu, kiểm    
  toán số chiều ma trận.                                           
  • scripts/: Điểm vào (Entrypoints) dạng dòng lệnh cho việc kiểm  
  toán, tái lập thực nghiệm và chạy đối sánh.                      
  • tests/: Bộ kiểm thử hồi quy tự động bảo đảm hệ thống không bị  
  lỗi ngầm.                                                        
  ──────                                                           
  ## 3. BẢN ĐỒ CHỨC NĂNG CỦA FILE (FILE FUNCTIONALITY MAP)         
                                                                   
  Dưới đây là các tệp nguồn cốt lõi mà lập trình viên mới cần nắm  
  vững:                                                            
                                                                   
  ### 3.1. Phân hệ Tối ưu hóa (Optimization Subsystem)             
                                                                   
   Đường dẫn tệp       │ Chức năng / Nhiệm … │ Các Class / Hàm qu…
  ─────────────────────┼─────────────────────┼─────────────────────
   domain.py       │ Định nghĩa toàn bộ thực    │ •
                   │ thể nghiệp vụ (Domain      │ FlightTimeWindow
                   │ Entities) có kiểu dữ liệu  │ : Cửa sổ thời
                   │ chặt chẽ và hàm xác minh   │ gian
                   │ ràng buộc cứng độc lập.    │ $s, e)$, kiểm tr
                   │                            │ a chồng lấn.<br>
                   │                            │ • [`Gate: Cổng
                       │                     │ thích hãng/loại tàu
                       │                     │ bay.• Flight: Thực
                       │                     │ thể chuyến bay đến
                       │                     │ kèm lịch trình và
                       │                     │ mốc giải phóng
                       │                     │ cổng.•
                   │                            │ bay đến kèm lịch
                   │                            │ trình và mốc
                   │                            │ giải phóng
                   │                            │ cổng.•
                   │                            │ ObjectiveBreakdo
                   │                            │ wn: Tách bạch
                   │                            │ chi phí quyết
                   │                            │ định
                   │                            │ (decision_cost)
                   │                            │ và chi phí ngữ
                   │                            │ cảnh ngoại sinh
                   │                            │ (reporting_cost)
                   │                            │ .•
                   │                            │ verify_hard_cons
                   │                            │ traints_independ
                   │                            │ ently(): Kiểm
                   │                            │ tra 100% độc lập
                   │                            │ bên ngoài bộ
                   │                            │ giải (0 xung
                   │                            │ đột, đúng cổng,
                   │                            │ tương thích).
   cp_sat_solver.p │ Bộ giải tối ưu hóa chính   │ •
   y               │ xác dựa trên Google OR-    │ CPSatGateSolver:
                    │ buộc nhị phân.           │ Tạo biến nhị phân
                   │ bài toán gán cổng thành    │ thiết lập mô
                   │ quy hoạch ràng buộc nhị    │ hình CP-SAT.•
                   │ phân.                      │ solve(): Tạo
                   │                            │ biến nhị phân
                   │                            │ x[f, g], thêm
                   │                            │ ràng buộc không
                   │                            │ chồng lấn
                   │                            │ AddNoOverlap,
                   │                            │ nguyên hóa hàm
                   │                            │ mục tiêu và giải
                   │                            │ bài toán.• Trả
                   │                            │ về nghiệm
                   │                            │ OPTIMAL hoặc
                   │                            │ FEASIBLE.
   greedy_solver.p │ Bộ giải tham lam xác định  │ •
   y               │ (Deterministic Greedy      │ DeterministicGre
                   │ Heuristic). Cung cấp       │ edyGateSolver:
                   │ nghiệm khả thi siêu nhanh  │ Sắp xếp chuyến
                   │ (< 2ms) làm warm-start cho │ bay theo thứ tự
                   │ SA hoặc cứu hộ khẩn cấp.   │ thời gian đến,
                   │                            │ gán cổng tiếp
                   │                            │ xúc khả thi đầu
                   │                            │ tiên có khoảng
                   │                            │ đệm nhỏ nhất, tự
                   │                            │ động đẩy sang
             │                          │ và chi phí rủi ro theo
             │                          │ một công thức duy nhất.
  ──────                                                           
  ### 3.2. Phân hệ Mô phỏng & Phụ thuộc Không gian - Thời gian     
  (Simulation & Dependence)                                        
                                                                   
   Đường dẫn tệp   │ Chức năng / Nhiệm vụ chính │ Các Class / Hàm…
  ──────────────────────┼───────────────────────────────┼──────────
   aircraft_turn.py     │ Mô hình hóa chu trình quay    │ •
                        │ đầu của máy bay, chuẩn hóa    │ Aircraft
                        │ dòng thời gian hoạt động từ   │ Turn:
                        │ khi đến tới khi rời cổng.     │ Thực thể
                        │                               │ chuyến
                        │                               │ bay gắn
                        │                               │ với mốc
                        │                               │ thời
                        │                               │ gian vật
                        │                               │ lý.•
                        │                               │ synthesi
                        │                               │ ze_turn(
                        │                               │ ): Thực
                        │                               │ thi công
                        │                               │ thức
                        │                               │ D_{sim}
                        │                               │ =
                        │                               │ max(D_{s
                        │                               │ ched},
                        │                               │ A_{sim}
                         │                               │ =
                         │                               │ max(D_{
                         │                               │ sched},
                         │                               │ A_{sim}
                         │                               │ +
                         │                               │ T_{turn
                         │                               │ }) và
                         │                               │ cộng
                         │                               │ đệm an
                         │                               │ toàn
                   │ cặp chuyến bay va chạm     │
                   │ thời gian và tổng thời     │
                   │ lượng xung đột.            │
   d2_gaussian_cop │ Mô hình liên kết ngẫu      │ •
   ula.py          │ nhiên Gaussian Copula (D2) │ GaussianCopulaJo
                   │ giữa các chuyến bay trong  │ intSampler: Xây
                   │ ngày dựa trên cự ly thời   │ dựng ma trận
                   │ gian và hãng hàng không.   │ tương quan qua
                   │                            │ hàm nhân kernel
                   │                            │ K(i, j), chuyển
                   │                            │ đổi phân phối
                   │                            │ đều qua hàm tích
                   │                            │ phân nghịch đảo
                   │                            │ PIT, và sinh mẫu
                   │                            │ ngẫu nhiên đồng
                   │                            │ thời.
   psd.py          │ Thuật toán chiếu phổ ma    │ •
                   │ trận bán xác định dương    │ validate_and_pro
                   │ (Positive Semi-Definite    │ ject_psd(): Phân
                   │ Spectral Projection).      │ rã trị riêng
                   │                            │ (Eigendecomposit
                   │                            │ ion), cắt bỏ các
                   │                            │ trị riêng âm,
                   │                            │ thiết lập sàn
                   │                            │ giá trị riêng
                   │                            │ λ_{min} ≥ 10⁻⁶,
                   │                            │ chuẩn hóa đường
                   │                            │ chéo 1.0 và tính
                   │                            │ toán sai số méo
                   │                            │ Frobenius.
  ──────                                                           
  ### 3.3. Phân hệ Kiểm toán & Bảo vệ Giao thức (Audit & Guards)   
                                                                   
   Đường dẫn tệp │ Chức năng / Nhiệm vụ … │ Các Class / Hàm quan …
  ───────────────┼────────────────────────┼────────────────────────
   protocol_guar │ "Chốt kiểm soát an     │ •
   ds.py         │ toàn" tự động ngăn     │ validate_dataset_role_
                 │ chặn vi phạm giao thức │ and_years(): Xác thực
                 │ nghiên cứu khoa học.   │ vai trò phân vùng dữ
                 │                        │ liệu theo từng Fold,
                 │                        │ bảo vệ năm 2024 và năm
                 │                        │ tương lai.•
                 │                        │ verify_dependence_dime
                 │                        │ nsion_properties():
                 │                        │ Kiểm toán 8 tính chất
                 │                        │ toán học của ma trận
                 │                        │ Copula cho số chiều d
                 │                        │ ∈ [1, 1500].•
                 │                        │ ProtocolComplianceGuar
                 │                        │ d: Chạy 7 chốt an toàn
                 │                        │ tổng thể.
  ──────                                                           
  ## 4. LUỒNG HOẠT ĐỘNG CHÍNH (CORE WORKFLOW)                      
                                                                   
  Khi hệ thống khởi chạy một chu trình đánh giá toàn diện (End-to- 
  End Execution — ví dụ qua script                                 
  run_development_end_to_end_benchmark.py), luồng dữ liệu và thuật 
  toán vận hành qua 6 giai đoạn tuần tự:                           
                                                                   
  │ Diagram exceeds terminal width (140 > 69 cols)                 
  │ Displayed as code block. Widen terminal to view inline.        
                                                                   
    flowchart TD                                                   
        subgraph S1["1. Data Ingestion & Cutoff T-2h"]             
            Raw["data/raw/ (Inbound DEST=ATL)"] --> Filter["Lọc    
  theo Ngày & Trạm ATL"]                                           
            Filter --> Cutoff["Chốt thời gian: CRS_DEP_TIME -      
  2h\n(Cấm trễ thực tế, cấm weather)"]                             
            Cutoff --> Feats["Trích xuất 11 Approved               
  Features\n(Schedule, Calendar, Route, Carrier)"]                 
        end                                                        
                                                                   
        subgraph S2["2. Probabilistic Delay Forecasting"]          
            Feats --> FrozenModel["B5 Student-T NGBoost (Đã đóng   
  băng)"]                                                          
            FrozenModel --> Params["Tham số phân phối: μ, σ, ν cho 
  từng chuyến bay"]                                                
        end                                                        
                                                                   
        subgraph S3["3. Joint Dependence & Monte Carlo"]           
            Params --> Copula["Gaussian Copula D2 Kernel:\nK(i, j) 
  = f(Δt, cùng hãng)"]                                             
            Copula --> PSD["Chiếu phổ ma trận PSD:\nλ_min >= 1e-6"]
            PSD --> MCSample["Sinh N kịch bản trễ đồng             
  thời\n(Inverse PIT Sampling)"]                                   
        end                                                        
                                                                   
        subgraph S4["4. Aircraft Turn Synthesis"]                  
            MCSample --> Timeline["Tính toán Dòng thời gian:\nA_sim
  = A_sched + Delay\nD_sim = max(D_sched, A_sim + T_turn)\nRelease 
  = D_sim + Buffer (15m)"]                                         
            Timeline --> DomainFlights["Tạo đối tượng Domain       
  Flight\nCửa sổ chiếm dụng [Gate_in, Gate_out)"]                  
        end                                                        
                                                                   
        subgraph S5["5. Gate Assignment Optimization"]             
            DomainFlights --> Greedy["Greedy Baseline\n(Cực nhanh  
  ~1ms)"]                                                          
            DomainFlights --> CPSAT["Exact CP-SAT Solver\n(Tối ưu  
  toàn cục decision_cost)"]                                        
            Greedy --> SAGreedy["SA (Warm-start Greedy)\n(Cải thiện
  nhanh dưới 200ms)"]                                              
            CPSAT --> SACPSAT["SA (CP-SAT Incumbent)\n(Bảo toàn tối
  ưu toàn cục)"]                                                   
        end                                                        
                                                                   
        subgraph S6["6. Verification & Publishing"]                
            SAGreedy & SACPSAT & CPSAT & Greedy --> HardCheck["Kiểm
  tra Ràng buộc Độc lập\n(verify_hard_constraints_independently)"] 
            HardCheck --> Evaluator["Common Evaluator\n(Tính điểm  
  chi phí khách quan)"]                                            
            Evaluator --> Artifacts["Lưu trữ Parquet & JSON        
  Manifests\ntại artifacts/development_end_to_end/"]               
        end                                                        
                                                                   
  ### Diễn giải chi tiết từng bước:                                
                                                                   
  1. Tiếp nhận & Ép quy tắc cắt thông tin (T - 2h):                
      • Đọc dữ liệu lịch bay inbound DEST=ATL.                     
      • Loại bỏ toàn bộ các biến tương lai và dữ liệu rò rỉ. Chỉ   
      giữ lại 11 đặc trưng an toàn đã được phê duyệt trong         
      tabular_features.py.                                         
  2. Dự báo phân phối độ trễ:                                      
      • Nạp mô hình B5_ngboost_student_t đã được đóng băng từ Stage
      10.                                                          
      • Với mỗi chuyến bay i, trích xuất bộ tham số phân phối      
      Student-T gồm: vị trí μᵢ, tỷ lệ σᵢ và bậc tự do νᵢ.          
  3. Mô hình hóa phụ thuộc liên chuyến & Lấy mẫu Monte Carlo:      
      • Xây dựng ma trận tương quan thời gian - hãng bay K(i, j)   
      giữa các cặp chuyến bay hạ cánh cùng ngày.                   
      • Chiếu phổ ma trận bằng validate_and_project_psd để bảo đảm 
      ma trận nửa xác định dương với trị riêng ≥ 10⁻⁶.             
      • Sử dụng Copula Gauss và biến đổi PIT nghịch đảo để lấy mẫu 
      đồng thời N kịch bản trễ.                                    
  4. Tổng hợp chu trình quay đầu tàu bay (Aircraft Turn Synthesis):
      • Áp dụng công thức chuẩn mực: D_{sim} = max(D_{sched},      
      A_{sim} + T_{turn}).                                         
      • Cộng đệm an toàn phân cách B_{buffer} = 15 phút tại thời   
      điểm rời cổng.                                               
      • Chuyển đổi thành các thực thể Flight với cửa sổ thời gian  
      nửa mở $[s, e)$.                                             
  5. Tối ưu hóa phân bổ cổng (Multi-Solver Optimization):          
      • Greedy: Sắp xếp theo thứ tự thời gian vào cổng, gán cổng   
      trống đầu tiên; nếu hết cổng chuyển ra bãi đỗ xa (overflow   
      stand).                                                      
      • CP-SAT: Lập mô hình biến nhị phân x[f, g], thêm ràng buộc  
      cấm trùng lấn AddNoOverlap trên các cổng tiếp xúc, tối ưu hóa
      trực tiếp trên chi phí quyết định (decision_cost).           
      • Simulated Annealing (SA): Nhận nghiệm ban đầu (từ Greedy   
      hoặc CP-SAT), tiến hành các bước nhảy Swap và Reassign, chấp 
      nhận nghiệm theo phân phối Boltzmann, đảm bảo nghiệm tốt nhất
      luôn thỏa mãn 100% ràng buộc cứng.                           
  6. Xác minh độc lập & Xuất bản Artifacts:                        
      • Toàn bộ nghiệm của các bộ giải đều được kiểm tra độc lập   
      qua hàm verify_hard_constraints_independently (đảm bảo tuyệt 
      đối 0 vi phạm xung đột cổng).                                
      • Đánh giá khách quan chi phí qua evaluate_gate_assignment.  
      • Kết quả được ghi nhận vào các tệp Parquet và JSON manifests
      tại artifacts/.                                              
                                                                   
  ──────                                                           
  ## 5. ĐÁNH GIÁ HIỆN TRẠNG & GỢI Ý BƯỚC TIẾP THEO (NEXT STEPS)    
                                                                   
  ### 5.1. Đánh giá hiện trạng Mã nguồn                            
                                                                   
  #### ✅ Các tính năng đã HOÀN THIỆN (Production-Grade / Research-
  Certified):                                                      
                                                                   
  1. Hệ thống Kiểm toán & An toàn Giao thức (100% Certified):      
      • Các chốt an toàn validate_dataset_role_and_years và        
      ProtocolComplianceGuard hoạt động nghiêm ngặt, chặn đứng mọi 
      nguy cơ rò rỉ dữ liệu năm 2024 hay vi phạm temporal folds.   
  2. Bộ giải Tối ưu hóa Toàn cục CP-SAT & Heuristic Greedy (100%   
  Verified):                                                       
      • Tách bạch hoàn toàn chi phí quyết định (decision_cost) và  
      chi phí ngữ cảnh ngoại sinh (reporting_cost).                
      • Đạt 100% tối ưu toàn cục (OPTIMAL) trên 40/40 kịch bản thử 
      nghiệm tại tập phát triển 2023.                              
      • Sai số chi phí giữa CP-SAT và Common Evaluator bằng đúng 0.
      0000.                                                        
  3. Bộ giải Metaheuristic Simulated Annealing (100% Feasible):    
      • Bảo đảm tính đơn điệu (không làm suy giảm nghiệm ban đầu)  
      và 100% khả thi cứng.                                        
      • Chứng minh rõ vai trò: Cứu hộ nhanh trong dải thời gian    
      sub-second (< 200ms) khi CP-SAT bị ngắt giờ.                 
  4. Ngữ nghĩa Dòng thời gian Máy bay (Timeline Semantics):        
      • Chuẩn hóa hoàn hảo giữa thời lượng quay đầu tối thiểu (45m),
      thời lượng đỗ kế hoạch (60m) và khoảng đệm phân cách (15m).  
      Triệt tiêu hoàn toàn lỗi double-counting.                    
  5. Mô hình Tương quan Copula & Chiếu phổ PSD:                    
      • Hỗ trợ số chiều động thích ứng với lưu lượng cao điểm tại  
      KATL (d = 420 đến 500 chuyến bay/ngày).                      
  6. Hệ thống Kiểm thử Phân tầng:                                  
      • Toàn bộ 115 / 115 unit & integration tests đều PASS (100%).
                                                                   
                                                                   
  #### ⚠️ Các tính năng còn DANG DỞ, BOILERPLATE hoặc BỊ KHÓA CÓ   
  CHỦ ĐÍCH:                                                        
                                                                   
  1. Phân hệ Thời tiết Ngoại sinh (Auxiliary Weather Branch):      
      • Hiện trạng: Hợp đồng dữ liệu                               
      weather_point_in_time_contract_v1 đã được thiết lập rất chi  
      tiết trong weather_contract.py, nhưng đang ở trạng thái      
      AUDIT_REQUIRED / enabled=false.                              
      • Lý do: Chưa tìm được nhà cung cấp dữ liệu thời tiết dự báo 
      (METAR/TAF hoặc HRRR) có chứng minh thời gian phát hành tin  
      (publication_time <= cutoff). Sáu trường thời tiết trong dữ  
      liệu thô BTS (O_TEMP, O_PRCP, ...) bị cấm sử dụng vì không rõ
      thời điểm ghi nhận.                                          
  2. Khai thác Chuỗi Tàu bay bằng Transformer (Flight Chain Feature
  Learning):                                                       
      • Hiện trạng: Dữ liệu chuỗi tàu bay                          
      flight_chain_reconstructed_v1 đã tái cấu trúc thành công từ  
      lịch bay (48.3 triệu dòng), nhưng các feature trích xuất từ  
      chuỗi này đang bị khóa BLOCKED_UNTIL_PROVEN.                 
      • Lý do: Chưa có bằng chứng kiểm toán chứng minh phiên bản   
      lịch bay của toàn chuỗi có sẵn tại thời điểm T - 2h mà không 
      bị rò rỉ thông tin cập nhật sau đó.                          
  3. Mô hình Hóa Cổng Nâng cao (Advanced Gate Operational          
  Constraints):                                                    
      • Hiện trạng: Bài toán AGAP hiện tại giả định cổng tiếp xúc  
      có thể tiếp nhận các chuyến bay tương thích hãng/tàu bay và  
      chỉ có 1 bãi đỗ xa chung.                                    
      • Chưa có: Chưa mô hình hóa cổng đa cấu hình MARS (Multiple  
      Aircraft Ramp System — 1 cổng lớn chia thành 2 cổng nhỏ cho  
      tàu thân hẹp), chưa có chi phí dắt kéo tàu bay (towing       
      operations) giữa cổng tiếp xúc và bãi chờ khi thời gian quay 
      đầu quá dài (> 3h).                                          
  4. Lớp Giao diện & Dịch vụ Trực tuyến (API / Serving Layer):     
      • Hiện trạng: Hệ thống hoàn toàn chạy dạng script và thư viện
      Python, chưa có REST API phục vụ thời gian thực hoặc         
      Dashboard trực quan hóa tương tác cho điều hành viên sân bay.
                                                                   
  ──────                                                           
  ### 5.2. Đề xuất 4 Đầu việc Kỹ thuật Tiếp theo cho Lập trình viên
  mới                                                              
                                                                   
  Dưới đây là lộ trình 4 bước hành động cụ thể để tiếp tục phát    
  triển dự án:                                                     
                                                                   
  #### 📌 Đầu việc 1: Xây dựng REST API Microservice (FastAPI      
  Serving Layer)                                                   
                                                                   
  • Mục tiêu: Đưa chu trình tối ưu hóa thành một dịch vụ backend có
  thể gọi qua HTTP.                                                
  • Nhiệm vụ cụ thể:                                               
      • Tạo ứng dụng FastAPI tại src/api/app.py.                   
      • Thiết kế endpoint POST /api/v1/optimize-gates: Tiếp nhận   
      danh sách lịch bay trong ngày (hoặc ngày vận hành D), gọi    
      pipeline sinh mẫu kịch bản Monte Carlo, chạy bộ giải         
      CPSatGateSolver (hoặc SimulatedAnnealingGateSolver tùy theo  
      time_budget_sec), và trả về danh sách gán cổng tối ưu kèm    
      chẩn đoán vi phạm.                                           
      • Viết bộ kiểm thử API test bằng pytest và httpx.            
                                                                   
                                                                   
  #### 📌 Đầu việc 2: Mở rộng Ràng buộc Bài toán AGAP Thực tế (MARS
  Gates & Aircraft Towing)                                         
                                                                   
  • Mục tiêu: Nâng cao độ chân thực trong vận hành sân bay của bộ  
  giải CP-SAT.                                                     
  • Nhiệm vụ cụ thể:                                               
      • Mở rộng class Gate trong src/optimization/domain.py để hỗ  
      trợ cấu hình cổng phụ huynh / cổng con (Parent-Child MARS    
      Gates: ví dụ Cổng F10 có thể tách thành F10A và F10B).       
      • Bổ sung ràng buộc loại trừ lẫn nhau trong CPSatGateSolver: 
      Nếu F10 đang phục vụ tàu thân rộng (Wide-body), thì cả F10A  
      và F10B đều phải khóa.                                       
      • Thêm cơ chế "Kéo dắt máy bay (Towing)": Nếu máy bay đỗ tại 
      cổng > 180 phút, cho phép tách thành 2 chặng (Arrival Gate → 
      Remote Apron Towing → Departure Gate) để giải phóng cổng tiếp
      xúc cho các chuyến bay cao điểm.                             
                                                                   
                                                                   
  #### 📌 Đầu việc 3: Xây dựng Giao diện Điều hành Trực quan       
  (Interactive Gantt Chart Dashboard)                              
                                                                   
  • Mục tiêu: Giúp người vận hành và chuyên gia sân bay quan sát   
  trực quan kế hoạch gán cổng và rủi ro chậm trễ.                  
  • Nhiệm vụ cụ thể:                                               
      • Xây dựng dashboard tương tác bằng Streamlit (hoặc React +  
      Plotly) tại src/dashboard/app.py.                            
      • Hiển thị biểu đồ Gantt phân bổ cổng theo trục thời gian (24
      giờ), tô màu theo hãng hàng không (Carrier) hoặc trạng thái  
      rủi ro.                                                      
      • Trực quan hóa các xung đột tiềm tàng khi người dùng kéo    
      thanh trượt mô phỏng kịch bản trễ thời tiết cực đoan (kết nối
      trực tiếp với kết quả từ artifacts/development_end_to_end/). 
                                                                   
                                                                   
  #### 📌 Đầu việc 4: Kiểm toán Nguồn Dữ liệu Thời tiết Điểm cắt T -
  2h (Weather Ingestion & Audit)                                   
                                                                   
  • Mục tiêu: Mở khóa nhánh nghiên cứu phụ trợ Auxiliary Departure 
  Delay Weather study.                                             
  • Nhiệm vụ cụ thể:                                               
      • Tìm kiếm và tích hợp bộ dữ liệu thời tiết lịch sử có tem   
      thời gian phát hành tin (publication_time), ví dụ: bản tin   
      METAR/TAF lưu trữ từ NOAA NCEI hoặc mô hình HRRR analysis.   
      • Thực hiện kiểm toán nguồn gốc thời gian tuân thủ nghiêm    
      ngặt hợp đồng weather_contract.py (chứng minh                
      publication_time <= CRS_DEP_TIME - 2h).                      
      • Khi bài kiểm toán đạt PASS, kích hoạt nhánh thử nghiệm đối 
      chứng DEP-A (chỉ lịch bay) vs DEP-B (lịch bay + thời tiết    
      điểm cắt) trên mô hình phân loại trễ khởi hành.              
                                                                   
  ──────                                                           
  ### TÓM TẮT DÀNH CHO LẬP TRÌNH VIÊN MỚI                          
                                                                   
  Codebase hiện tại đang ở trạng thái cực kỳ ổn định và chuẩn mực  
  về mặt toán học và an toàn giao thức (115/115 tests PASS, 7/7    
  steps PASS).                                                     
                                                                   
  Khi thực hiện bất kỳ thay đổi nào:                               
                                                                   
  1. Luôn chạy kiểm tra hồi quy:                                   
    & "D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe"       
  scripts/run_final_code_audit.py                                  
                                                                   
  2. Tuyệt đối không chạm vào dữ liệu thô data/raw/.               
  3. Tuyệt đối không mở hoặc sử dụng dữ liệu năm 2024 để huấn luyện
  hoặc căn chỉnh siêu tham số. 