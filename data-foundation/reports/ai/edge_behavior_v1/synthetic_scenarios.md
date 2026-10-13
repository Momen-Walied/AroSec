# Edge Behavior v1 — Synthetic Scenario Stress Test

> **Terminology.** This component detects *behavioural anomalies in temporal communication relationships*. On UNSW-IoTraffic (no attack labels) these are **relationship anomalies**, not proven attacks. UNSW identities are `dataset_ip_fallback` (source MACs are null), so results are **communication-entity anomalies**, not device anomalies. No claim of lateral-movement / malware detection is made.

Deterministic perturbations applied to TEST rows (evaluation only; never in training).

## Detection rate by scenario (score >= calibrated threshold)

| scenario | statistical | isolation_forest | autoencoder | fusion |
|---|---:|---:|---:|---:|
| SCN-001_NEW_PEER | 1.00 | 1.00 | 0.63 | 1.00 |
| SCN-002_NEW_PORT | 1.00 | 0.16 | 0.14 | 0.54 |
| SCN-003_NEW_PROTOCOL | 1.00 | 0.04 | 1.00 | 0.65 |
| SCN-004_FAN_OUT_BURST | 1.00 | 0.69 | 0.24 | 1.00 |
| SCN-005_TRAFFIC_VOLUME_SPIKE | 0.81 | 0.43 | 0.82 | 0.60 |
| SCN-006_COMPOUND | 1.00 | 1.00 | 1.00 | 1.00 |

## Median score by scenario

| scenario | statistical | isolation_forest | autoencoder |
|---|---:|---:|---:|
| SCN-001_NEW_PEER | 0.470 | 0.802 | 1.000 |
| SCN-002_NEW_PORT | 0.101 | 0.650 | 1.000 |
| SCN-003_NEW_PROTOCOL | 0.126 | 0.644 | 1.000 |
| SCN-004_FAN_OUT_BURST | 0.139 | 0.727 | 1.000 |
| SCN-005_TRAFFIC_VOLUME_SPIKE | 0.081 | 0.691 | 1.000 |
| SCN-006_COMPOUND | 0.645 | 0.829 | 1.000 |

