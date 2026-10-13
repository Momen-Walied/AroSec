# Edge vs Node Behavior — Complementarity

> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`.

Thresholds — node 0.719, edge 0.064 (statistical models both sides).

## Equivalent anomaly families (detection rate)

| anomaly family | node v1 | edge v1 | better |
|---|---:|---|---|
| SCN-N01_NEW_PEER_BURST | 1.00 | 1.00 | tie |
| SCN-N02_FAN_OUT_BURST | 1.00 | 1.00 | tie |
| SCN-N03_PROTOCOL_SHIFT | 0.13 | 1.00 | edge |
| SCN-N04_PORT_DIVERSITY_BURST | 0.47 | 1.00 | edge |
| SCN-N05_OUTBOUND_VOLUME_SPIKE | 0.93 | 0.62 | node |
| SCN-N06_PEER_SET_REPLACEMENT | 1.00 | 1.00 | tie |
| SCN-N07_INBOUND_TARGETING | 1.00 | 1.00 | tie |
| SCN-N08_COMPOUND | 1.00 | 1.00 | tie |

## Cross-model correlation (window level)

- windows compared: 7061
- Pearson: 0.0846 · Spearman: 0.1078
- high-node windows that also have high edge: 0.250
- high-edge windows while node normal: 0.978
- high-node windows while edge normal: 0.750

Correlation is descriptive, not causal. Low overlap indicates complementary signals.

