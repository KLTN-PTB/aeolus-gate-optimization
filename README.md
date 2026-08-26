# Aeolus Gate Optimization

## Reconstructed Schedule Flight Chain

The versioned derived artifact is reconstructed from the full canonical yearly
Tabular partitions, never from raw Flight Chain `.pt` archives. It groups a
service-date schedule context by `source_year`, `FL_DATE`, `OP_CARRIER`, and
`OP_CARRIER_FL_NUM`, then derives a separate inbound-ATL target map. The
resulting `chain_id` is not an aircraft, tail-number, registration, or physical
rotation identifier. The original raw Flight Chain decision remains `NO_GO`.

Run the reconstruction pipeline only through the repository virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/reconstruct_flight_chain.py --years 2016 --max-rows 250000 --output-root data/processed/flight_chain_reconstructed_v1_smoke
```

The production root is `data/processed/flight_chain_reconstructed_v1/`. Full
2016–2023 reconstruction passed with 48,389,162 mapped rows, 100% coverage,
and independent inbound-ATL mapping validation for every year. The derived
artifact is `GO_FOR_ABLATION`, but remains disabled by default and outside the
core pipeline. Development access to 2024 remains blocked.

The reconstruction runtime contract is Python 3.11 or newer. The repository
`.venv` was candidate-tested and promoted on Python 3.11.15 with pandas 2.3.3,
PyArrow 25.0.1, and SQLite 3.50.4. Direct dependencies are pinned in
`requirements.txt`; the resolved environment is recorded in
`artifacts/manifests/reconstruction_python_environment_v1.json`.

The original Aeolus raw Flight Chain `.pt` remains independently
`FINAL — NO_GO`. Approval of the reconstructed schedule context does not
recover physical aircraft rotation and does not imply predictive improvement.

Kiến trúc nghiên cứu: **Predict -> Simulate -> Optimize -> Dashboard** trên dữ liệu Aeolus 2016–2024.

- Tabular là dữ liệu core. Raw Flight Chain `.pt` vẫn `FINAL — NO_GO`, read-only và không tham gia core/ablation; Reconstructed Schedule Flight Chain riêng biệt là `GO_FOR_ABLATION` nhưng vẫn optional và chưa được bật trong core.
- Raw Tabular nằm tại `data/raw/tabular/<year>/`; raw Flight Chain optional nằm tại `data/raw/chain/<year>/`. Cả hai là read-only và không được commit lên Git.
- ATL là hub thí nghiệm. Gate và Aircraft Turn là lớp mô phỏng synthetic, không phải gate operation thật tại ATL.
- Prediction cut-off core: `T = CRS_DEP_TIME - 2h`.
- 2024 là final holdout và không được dùng trong development.
- Ba roadmap V3 nằm tại `docs/roadmap/`.
- Raw dataset không được commit lên Git.
