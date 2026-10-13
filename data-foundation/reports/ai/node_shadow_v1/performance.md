# Performance — Edge-only vs Combined (durable SQLite state + sink)

| metric | edge-only | combined (edge+node) |
|---|---:|---:|
| observations/sec | 5540 | 2045 |
| peak RSS (MB) | 3204.5 | 3204.5 |
| state DB (MB) | 4.30 | 8.57 |
| sink DB (MB) | 273.75 | 686.96 |
| edge windows | 67885 | 67885 |
| node windows | 0 | 103680 |

## Latencies (ms, per window)

- edge feature: p50=0.06179 p95=0.06983 p99=0.07805
- edge inference: p50=0.01462 p95=0.01569 p99=0.02898
- node feature: p50=0.04597 p95=0.04955 p99=0.06332
- node inference: p50=0.00731 p95=0.00885 p99=0.01340

Regression vs Edge-only Shadow v1 (obs/sec 6058): -66%.

