# AI Node Shadow Integration v1

Extends the Shadow Integration runtime so the **same incoming `CommunicationObservation v0.2`
stream** independently drives an **Edge pipeline** and a **Node pipeline**. No frozen contract
was modified; no datasets were downloaded; **no fusion** and **no remediation** exist.

```
CommunicationObservation v0.2
        │
        ▼  shared event-time runtime (dedupe · watermark · lateness · durable state)
   ┌────┴─────┐
   ▼          ▼
Edge pipeline   Node pipeline
(OnlineEdgeState → EdgeFeatureWindowV2 → Edge Behavior v1 → EdgeAnomalyResultV1)
(OnlineNodeState → NodeFeatureWindowV2 → Node Behavior v1 → NodeAnomalyResultV1)
   └────┬─────┘
        ▼
   Shadow storage (edge/node records separated: intelligence_type = edge | node)
   Metrics · Drift · Review
```

Reuses `ai/shadow/` config, sources, sinks, state stores, metrics, drift, feedback, replay,
lateness, idempotency, and restart recovery. Only the node online builder, the node model
bundle, and the node analytics are added.

## Project status

```
Data Foundation v0.2:               FROZEN
Edge Behavior Intelligence v1:      COMPLETE
Shadow Integration v1:              COMPLETE / SHADOW-READY
Node Behavior Intelligence v1:      COMPLETE
Node Shadow Integration v1:         COMPLETE / SHADOW-READY
```

## 1. Node online/offline parity (release blocker) — EXACT

| | offline | online | missing/extra | **field mismatches** |
|---|---:|---:|---:|---:|
| Node (`NodeFeatureWindowV2`) | 103,680 | 103,680 | 0 / 0 | **0** |
| Edge (`EdgeFeatureWindowV2`, regression) | 67,885 | 67,885 | 0 / 0 | **0** |

All 21 node fields compared with exact equality (integer counts / sets — no tolerance needed):
outgoing/incoming connection, packet and byte counts; unique outgoing/incoming peers;
new outgoing/incoming peers; unique outgoing/incoming ports; outbound/inbound network- and
app-protocol counts; protocol/port novelty; fan-out/fan-in; relationship-creation count.

## 2. Directional semantics

For every observation, `src_asset_id` updates **OUTBOUND** state and `dst_asset_id` updates
**INBOUND** state (one observation updates two entities). Explicitly tested.

## 3. Event-time, windowing, lateness, duplicates

Same as Edge Shadow v1: 30 s half-open windows, watermark = max `window_end`, finalize when
`window_start + window + lateness < watermark`, lateness quarantined (default 30 s), emitted
results never rewritten. `observation_id` idempotency is applied **once, before either
pipeline mutates state** (central dedupe), so a duplicate cannot double-count edge or node
history or create duplicate windows/results.

## 4. Replay results (full existing UNSW v0.2 stream)

| | value |
|---|---|
| observations | 98,747 |
| edge windows / results | 67,885 / 67,885 |
| node windows / results | 103,680 / 103,680 |
| edge alerts | 566 (rate 0.83%) · 18.2/site/day |
| node alerts | 669 (rate 0.65%) · 21.5/site/day · 0.341/entity/day |
| node severity | CRITICAL 137 · HIGH 28 · MEDIUM 123 · LOW 381 · INFO 103,011 |
| node score p50/p90/p95/p99 | 0.268 / 0.537 / 0.610 / 0.693 |

**signals ≠ incidents** — edge and node alerts are independent signals, never summed.

## 5. Complementarity (analysis only)

| | count | share |
|---|---:|---:|
| both alert | 25 | 2.7% |
| edge only | 413 | 43.8% |
| node only | 504 | 53.5% |

(Percentages are over windows with ≥1 alert; "neither" is 0 by construction.)
Edge alerts per node-alert window: **0.07**; node-alert windows containing ≥1 edge alert:
**4.7%**; edge alerts while node normal: **94.3%**.
Window-level score correlation: **Pearson 0.0038 · Spearman 0.0017** (35,805 windows) — the
two signals are essentially uncorrelated ⇒ **complementary**.
An analysis-only incident-like grouping (node anomaly + related edge anomalies, **no combined
score**) is in `reports/ai/node_shadow_v1/edge_node_complementarity.md`.

## 6. Performance (durable SQLite state + sink)

| metric | edge-only | combined |
|---|---:|---:|
| observations/sec | 5,540 | **2,045** |
| peak RSS (MB) | 3,204.5 | 3,204.5 |
| state DB (MB) | 4.30 | 8.57 |
| sink DB (MB) | 273.75 | 686.96 |

Latencies (ms, per window, combined): edge feature p99 **0.078**, edge inference p99 **0.029**,
node feature p99 **0.063**, node inference p99 **0.013**.
**Regression vs Edge-only Shadow v1 (~6,058 obs/s): ≈ −66%**, dominated by writing 171,565
durable sink records (edge + node) and the second feature/inference pipeline. Informational;
still CPU-practical for edge deployment.

## 7. Drift — DRIFT_NONE

Node drift (PSI/KS vs validation reference) is **DRIFT_NONE** on all tracked metrics
(anomaly score 0.005, fan-out/fan-in/peers/diversity ≈ 0.000, bytes 0.002–0.007).
Observable only — **no auto retraining / recalibration**.

## 8. Failure behaviour (fail-open, component isolation)

| failure | behaviour | network impact |
|---|---|---|
| edge model failure | edge pipeline disabled; node continues | none |
| node model failure | node pipeline disabled; edge continues | none |
| state failure | logged + counted; runtime continues | none |
| sink failure | logged + counted; scoring continues | none |
| schema mismatch | fails fast at startup | none |

## 9. Reproduce

```bash
python -m ai.shadow.reporting.generate_node_shadow_reports   # parity + replay + perf + drift
python -m ai.shadow demo-combined                            # deterministic edge+node demo
python -m pytest tests/ai -q
```

## 10. Final questions

1. **Node parity exact?** Yes.
2. **Mismatches?** **0** (node 103,680; edge 67,885).
3. **Total node windows?** **103,680**.
4. **Node replay alert rate?** **0.65%**.
5. **Node alerts/entity/day?** **0.341**.
6. **Node alerts/site/day?** **21.5**.
7. **Top node reasons?** `PORT_DIVERSITY_CHANGE`, `COMMUNICATION_RATIO_CHANGE`-style
   `COMMUNICATION_RATIO_SHIFT`, `OUTBOUND_VOLUME_DEVIATION`, `INBOUND_VOLUME_DEVIATION`,
   `PROTOCOL_DIVERSITY_CHANGE`, `FAN_OUT_DEVIATION` (by reason presence).
8. **Edge/Node operational correlation?** Pearson **0.0038**, Spearman **0.0017** (≈ zero).
9. **Percentages:** both **2.7%**, edge-only **43.8%**, node-only **53.5%**, neither 0%
   (over alert windows).
10. **Sustainable obs/sec with both pipelines?** **~2,045** (durable state + sink).
11. **Regression vs Edge-only Shadow v1?** **≈ −66%** (5,540 → 2,045 obs/s), sink-write dominated.
12. **Peak RSS?** **3,204.5 MB** (process-wide; includes the full in-memory UNSW observation
    list + both model artifacts; the runtime retains only relationship/asset sets + open windows).
13. **Durable state size?** **8.57 MB** (edge+node) vs 4.30 MB edge-only.
14. **Restart recovery?** Yes — edge and node state persisted together in one `StateStore`;
    peers stay known, counts/peer-sets remain correct, no duplicate windows/results (tested).
15. **Duplicate safety?** Yes — central `observation_id` idempotency before either pipeline
    (tested across both).
16. **Drift status?** **DRIFT_NONE** (observable only).
17. **Can edge continue if node inference fails?** Yes (component isolation; tested).
18. **Can node continue if edge inference fails?** Yes (tested).
19. **Ready for a real Network/Security stream?** Ready as a **read-only shadow** integration:
    frozen-contract ingestion, exact parity for both pipelines, idempotency, restart recovery,
    separate storage, metrics, drift, and complementarity analytics; a broker attaches via
    `ObservationSource`.
20. **What remains provisional?** Edge threshold 0.315 and node threshold 0.719; UNSW
    `dataset_ip_fallback` identity; window-quantized lateness; single-dataset/window validation;
    performance regression magnitude on real hardware; no fusion (by design).

## Scope

No fusion, GNN/Temporal GNN, attack-path, campaign reconstruction, or remediation.
Nothing committed.
