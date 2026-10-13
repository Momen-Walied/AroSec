# Node Behavior v1 — Experiment Summary

> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`.

- dataset: `unsw_iotraffic` v0.2 `30s`
- split (chronological, aligned with Edge Behavior): train ('2016-09-30T19:30:00+00:00', '2016-10-19T15:45:00+00:00') · validation ('2016-10-19T15:45:30+00:00', '2016-10-25T15:27:30+00:00') · test ('2016-10-25T15:28:00+00:00', '2016-10-31T23:46:30+00:00')
- rows: train 62311 / validation 20735 / test 20634

| model | version | threshold | val alert rate | test alert rate | artifact size |
|---|---|---:|---:|---:|---:|
| statistical | node-stat-v1 | 0.719 | 0.0109 | 0.0048 | 6 KB |
| isolation_forest | node-iforest-v1 | 0.969 | 0.0100 | 0.0140 | 4843 KB |
| autoencoder | node-ae-v1 | 0.984 | 0.0100 | 0.0121 | 41 KB |

