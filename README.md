# Aeolus Gate Optimization

Kiến trúc nghiên cứu: **Predict -> Simulate -> Optimize -> Dashboard** trên dữ liệu Aeolus 2016–2024.

- Tabular là dữ liệu core. Flight Chain đã nhận quyết định Week-2 `NO_GO`: raw files vẫn được giữ read-only, nhưng Chain không tham gia core pipeline hoặc Week-6 ablation.
- Raw Tabular nằm tại `data/raw/tabular/<year>/`; raw Flight Chain optional nằm tại `data/raw/chain/<year>/`. Cả hai là read-only và không được commit lên Git.
- ATL là hub thí nghiệm. Gate và Aircraft Turn là lớp mô phỏng synthetic, không phải gate operation thật tại ATL.
- Prediction cut-off core: `T = CRS_DEP_TIME - 2h`.
- 2024 là final holdout và không được dùng trong development.
- Ba roadmap V3 nằm tại `docs/roadmap/`.
- Raw dataset không được commit lên Git.
