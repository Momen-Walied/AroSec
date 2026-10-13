# AI Node Behavior Intelligence v1

Entity-behavior anomaly detection built **above** the frozen `CYBER_GRAPH_DATA_CONTRACT_V0.2`.
No frozen contract files were modified; no new datasets were downloaded.

**Question answered:** *Given all communication behavior associated with entity A and all
history strictly before time T, how unusual is A's behavior at T?*

> **Terminology.** This is **entity (communication-entity) behavior anomaly** — **not**
> validated device anomaly and **not** attack detection. UNSW identities are
> `dataset_ip_fallback` (source MACs are null).

## Project status

```
Data Foundation v0.2:               FROZEN
Edge Behavior Intelligence v1:      COMPLETE
Shadow Integration v1:              COMPLETE / SHADOW-READY
Node Behavior Intelligence v1:      COMPLETE (not yet shadow-integrated)
```

## 1. Audit → why V2

The v0.1 `NodeFeatureWindow` is **outbound-centric**: it has outbound peers/ports/fan-out and
`outbound_bytes`, but **no inbound behavior** (no incoming peers, fan-in, inbound
protocol/port diversity), no peer-set change rate and no relationship-creation rate, and its
`dns_query_rate`/`failed_connection_ratio` are unavailable in the source data.

**Conclusion: V2 required.** `NodeFeatureWindowV2` (AI layer) models both directions
symmetrically and adds novelty/change features. See `reports/ai/node_behavior_v1/feature_design.md`.

## 2. Features (`node_features_v1`)

Facts (`NodeFeatureWindowV2`): outgoing/incoming connection, packet, byte counts; unique
outgoing/incoming peers; new outgoing/incoming peers; unique outgoing/incoming ports;
outbound/inbound network- and app-protocol counts; protocol/port novelty; fan-out/fan-in;
relationship-creation count. Derived model features (23) apply `log1p` and ratios
(`out_in_conn_ratio`, `out_in_bytes_ratio`, `peer_set_change_rate`).

Components (interpretable, mapped to reason codes): `NEW_PEER_BURST`, `FAN_OUT_DEVIATION`,
`FAN_IN_DEVIATION`, `PROTOCOL_DIVERSITY_CHANGE`, `PORT_DIVERSITY_CHANGE`,
`OUTBOUND_VOLUME_DEVIATION`, `INBOUND_VOLUME_DEVIATION`, `RELATIONSHIP_CREATION_BURST`,
`PEER_SET_CHANGE`, `COMMUNICATION_RATIO_SHIFT`.

## 3. Causality & split

All history/novelty fields use only windows **strictly before** the current window; scalers
fit on TRAIN only; thresholds from VALIDATION only; TEST untouched until evaluation.
Chronological split **reuses Edge Behavior's boundaries**:

| split | rows | time range |
|---|---:|---|
| train | 62,311 | 2016-09-30 19:30 → 2016-10-19 15:45 |
| validation | 20,735 | 2016-10-19 15:45 → 2016-10-25 15:27 |
| test | 20,634 | 2016-10-25 15:28 → 2016-10-31 23:46 |

103,680 node-windows across 63 entities.

## 4. Results (normal test data)

| model | threshold | test alert rate | alerts/entity/day | alerts/site/day | p50 | p99 | ms/row | size |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **statistical** | 0.719 | **0.48%** | 0.28 | 15.6 | 0.268 | 0.693 | 0.0001 | 6 KB |
| isolation_forest | 0.969 | 1.40% | 0.83 | 45.4 | 0.493 | 0.975 | 0.0054 | 4.8 MB |
| autoencoder | 0.984 | 1.21% | 0.72 | 39.4 | 0.495 | 0.991 | 0.0002 | 41 KB |

## 5. Synthetic scenarios (detection rate at calibrated threshold)

| scenario | statistical | isolation_forest | autoencoder |
|---|---:|---:|---:|
| SCN-N01 NEW_PEER_BURST | 1.00 | 0.80 | 1.00 |
| SCN-N02 FAN_OUT_BURST | 1.00 | 0.43 | 1.00 |
| SCN-N03 PROTOCOL_SHIFT | 0.12 | 0.10 | 0.14 |
| SCN-N04 PORT_DIVERSITY_BURST | 0.48 | 0.11 | 1.00 |
| SCN-N05 OUTBOUND_VOLUME_SPIKE | 0.96 | 0.73 | 0.64 |
| SCN-N06 PEER_SET_REPLACEMENT | 1.00 | 0.23 | 0.01 |
| SCN-N07 INBOUND_TARGETING | 1.00 | 0.37 | 1.00 |
| SCN-N08 COMPOUND | 1.00 | 1.00 | 1.00 |

## 6. Edge vs Node (statistical, like-for-like) + correlation

| anomaly family | node v1 | edge v1 | better |
|---|---:|---|---|
| NEW_PEER_BURST | 1.00 | 1.00 | tie |
| FAN_OUT_BURST | 1.00 | 1.00 | tie |
| PROTOCOL_SHIFT | 0.13 | 1.00 | **edge** |
| PORT_DIVERSITY_BURST | 0.47 | 1.00 | **edge** |
| OUTBOUND_VOLUME_SPIKE | 0.93 | 0.62 | **node** |
| PEER_SET_REPLACEMENT | 1.00 | 1.00 | tie |
| INBOUND_TARGETING | 1.00 | 1.00 | tie |
| COMPOUND | 1.00 | 1.00 | tie |

Window-level cross-model correlation: **Pearson 0.085 · Spearman 0.108**; of high-node
windows 75% have normal edge, and 97.8% of edge alerts occur while node is normal
(19 overlapping windows vs 859 edge-only and 57 node-only). **Low correlation ⇒ complementary
signals.** (Descriptive, not causal.)

## 7. Reproduce

```bash
python -m ai.node_behavior.training.run_experiments     # trains + writes reports/ai/node_behavior_v1/
python -m pytest tests/ai/node_behavior -q
```
Artifacts: `ai/node_behavior/artifacts/node_behavior/{node-stat-v1,node-iforest-v1,node-ae-v1}/`.

## 8. Final questions

1. **NodeFeatureWindow sufficient?** **No** — V2 required (inbound behavior + change features).
2. **Best model?** **Statistical** (best detection + calibration 0.48% at ~1% target,
   interpretable, 6 KB). Isolation Forest is well-calibrated but weaker; the AE adds
   PORT_DIVERSITY detection only.
3. **Does the Autoencoder add meaningful value?** **No** — not better overall; **rejected**
   (it only wins PORT_DIVERSITY_BURST).
4. **Proposed shadow threshold?** **0.719** for the statistical model — **provisional**
   (validation-derived at a ~1% target; recalibrate in deployment).
5. **Alerts/entity/day?** **0.28** (statistical); IForest 0.83, AE 0.72.
6. **Alerts/site/day?** **15.6** (statistical); IForest 45.4, AE 39.4.
7. **Reliably detected?** NEW_PEER_BURST, FAN_OUT_BURST, PEER_SET_REPLACEMENT,
   INBOUND_TARGETING, COMPOUND, and OUTBOUND_VOLUME_SPIKE.
8. **Difficult?** PROTOCOL_SHIFT (0.12) and PORT_DIVERSITY_BURST (0.48) at node level.
9. **Where node beats edge?** **OUTBOUND_VOLUME_SPIKE** (0.93 vs 0.62); node natively
   represents **PEER_SET_REPLACEMENT** and **INBOUND_TARGETING** as entity-level patterns
   that edge sees only as generic new edges.
10. **Where edge beats node?** **PROTOCOL_SHIFT** (1.00 vs 0.13) and **PORT_DIVERSITY_BURST**
    (1.00 vs 0.47) — per-relationship protocol/port novelty is sharp at edge, diluted at node.
11. **Correlation?** Pearson **0.085**, Spearman **0.108** — very low (complementary).
12. **Complementary value justifies a separate component?** **Yes** — 75% of high-node windows
    have normal edge, and 97.8% of edge alerts occur while node is normal.
13. **CPU edge suitable?** **Yes** — sub-millisecond inference, ≤4.8 MB artifacts, no GPU.
14. **Identity limitations?** UNSW is `dataset_ip_fallback` ⇒ **entity behavior**, not device
    behavior; identity_method/confidence preserved in `NodeAnomalyResultV1`.
15. **Ready for shadow integration?** **Yes** (deterministic features, versioned schema,
    portable artifacts, explicit schema checks). A Node Shadow Runtime is the next step and
    was **not** built in this phase.

## Scope

No GNN/Temporal GNN, no attack-path, no campaign reconstruction, no remediation, no
node–edge fusion (intentionally deferred). Nothing was committed.
