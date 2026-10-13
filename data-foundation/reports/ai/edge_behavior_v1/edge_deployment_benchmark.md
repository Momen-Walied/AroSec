# Edge Behavior v1 — Edge Deployment Benchmark

> **Terminology.** This component detects *behavioural anomalies in temporal communication relationships*. On UNSW-IoTraffic (no attack labels) these are **relationship anomalies**, not proven attacks. UNSW identities are `dataset_ip_fallback` (source MACs are null), so results are **communication-entity anomalies**, not device anomalies. No claim of lateral-movement / malware detection is made.

CPU-only inference (no GPU). Latency measured as mean per-row batch scoring.

| model | inference ms/row | total s (test) | peak memory MB | artifact size KB |
|---|---:|---:|---:|---:|
| statistical | 0.00007 | 0.001 | 5.18 | 8 |
| isolation_forest | 0.00526 | 0.071 | 3.89 | 8019 |
| autoencoder | 0.00024 | 0.003 | 7.87 | 44 |

