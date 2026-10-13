# Node Behavior v1 — Synthetic Scenario Response

> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`.

Deterministic perturbations applied to TEST node windows (evaluation only).

| scenario | statistical | isolation_forest | autoencoder |
|---|---:|---:|---:|
| SCN-N01_NEW_PEER_BURST | 1.00 | 0.80 | 1.00 |
| SCN-N02_FAN_OUT_BURST | 1.00 | 0.43 | 1.00 |
| SCN-N03_PROTOCOL_SHIFT | 0.12 | 0.10 | 0.14 |
| SCN-N04_PORT_DIVERSITY_BURST | 0.48 | 0.11 | 1.00 |
| SCN-N05_OUTBOUND_VOLUME_SPIKE | 0.96 | 0.73 | 0.64 |
| SCN-N06_PEER_SET_REPLACEMENT | 1.00 | 0.23 | 0.01 |
| SCN-N07_INBOUND_TARGETING | 1.00 | 0.37 | 1.00 |
| SCN-N08_COMPOUND | 1.00 | 1.00 | 1.00 |

