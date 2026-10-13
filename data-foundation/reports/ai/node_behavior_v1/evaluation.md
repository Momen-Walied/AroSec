# Node Behavior v1 — Evaluation (normal test data)

> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`.

| model | alert rate | alerts | alerts/entity/day | alerts/site/day | p50 | p90 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| statistical | 0.0048 | 99 | 0.28 | 15.6 | 0.268 | 0.537 | 0.693 |
| isolation_forest | 0.0140 | 288 | 0.83 | 45.4 | 0.493 | 0.908 | 0.975 |
| autoencoder | 0.0121 | 250 | 0.72 | 39.4 | 0.495 | 0.768 | 0.991 |

## Score drift (daily mean)

| model | mean of daily mean | std | max daily alert rate |
|---|---:|---:|---:|
| statistical | 0.2917 | 0.0090 | 0.0155 |
| isolation_forest | 0.5539 | 0.0151 | 0.0454 |
| autoencoder | 0.5578 | 0.0079 | 0.0332 |

