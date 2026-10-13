# Edge Behavior v1 — Experiment Summary

> **Terminology.** This component detects *behavioural anomalies in temporal communication relationships*. On UNSW-IoTraffic (no attack labels) these are **relationship anomalies**, not proven attacks. UNSW identities are `dataset_ip_fallback` (source MACs are null), so results are **communication-entity anomalies**, not device anomalies. No claim of lateral-movement / malware detection is made.

- dataset: `unsw_iotraffic` v0.2 `30s`
- feature schema: `edge-stat-v1` family
- split (chronological): train ('2016-09-30T19:30:00+00:00', '2016-10-19T15:45:00+00:00') · validation ('2016-10-19T15:45:30+00:00', '2016-10-25T15:27:30+00:00') · test ('2016-10-25T15:28:00+00:00', '2016-10-31T23:46:30+00:00')
- rows: train 40732 / validation 13577 / test 13576

## Models

| model | version | threshold | artifact size | val alert rate |
|---|---|---:|---:|---:|
| statistical | edge-stat-v1 | 0.064 | 8 KB | 0.0113 |
| isolation_forest | edge-iforest-v1 | 0.709 | 8019 KB | 0.0100 |
| autoencoder | edge-ae-v1 | 1.000 | 44 KB | 0.0211 |

## Fusion (validation-weighted)

| model | weight |
|---|---:|
| statistical | 0.603 |
| isolation_forest | 0.397 |

fusion threshold: 0.315

