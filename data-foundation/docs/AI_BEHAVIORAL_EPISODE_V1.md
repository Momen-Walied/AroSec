# AI Behavioral Episode Intelligence v1

Deterministic temporal evidence correlation over independent Edge/Node anomaly signals.
Built above the frozen `CYBER_GRAPH_DATA_CONTRACT_V0.2`; no frozen contract or model result
contract changed; no datasets downloaded.

**Question answered:** *Given independent `EdgeAnomalyResultV1` and `NodeAnomalyResultV1`
signals over time, which signals belong to the same coherent behavioral episode?*

> **Terminology.** A **Behavioral Episode** is a temporally and relationally coherent group of
> anomaly signals. It is **NOT** an attack, incident, campaign, or compromise, and carries no
> attacker/victim/objective/attack-path semantics. Correlation does not prove causality.

## Project status

```
Data Foundation v0.2:               FROZEN
Edge Behavior Intelligence v1:      COMPLETE
Shadow Integration v1:              COMPLETE / SHADOW-READY
Node Behavior Intelligence v1:      COMPLETE
Node Shadow Integration v1:         COMPLETE / SHADOW-READY
Behavioral Episode Intelligence v1: COMPLETE
```

## 1. Correlation model

Signals (alerts only) are processed **chronologically**. Two signals join the same episode
only if they are:

* **temporally close** — inactivity from the previous signal's `window_end` to the next
  `window_start` ≤ `correlation_gap_seconds`; and
* **relationally connected** — share an asset (covers edge↔node same entity, two edges sharing
  an endpoint, and relationship endpoints).

An episode cannot extend more than `max_episode_duration_seconds` from its start (bounds
percolation). Active episodes that become connected are merged deterministically (oldest start
wins; tie-break by `episode_id`). `episode_id = sha1(start_time | first_signal_id)`.
**No score fusion; no ML; no attack taxonomy.**

## 2. Evidence families (reason-code → family)

`PEER_NOVELTY` (NEW_PEER, NEW_PEER_BURST, RELATIONSHIP_CREATION_BURST), `TOPOLOGY_SPREAD`
(FAN_OUT/FAN_IN_DEVIATION), `PROTOCOL_CHANGE` (PROTOCOL_NOVELTY / PROTOCOL_DIVERSITY_CHANGE /
APP_PROTOCOL_NOVELTY), `PORT_CHANGE` (PORT_NOVELTY / PORT_DIVERSITY / PORT_DIVERSITY_CHANGE),
`TRAFFIC_VOLUME` (TRAFFIC_VOLUME_DEVIATION, OUTBOUND/INBOUND_VOLUME_DEVIATION),
`DIRECTIONAL_CHANGE` (COMMUNICATION_RATIO_SHIFT), `PEER_SET_CHANGE`, `OTHER`. This prevents
highly correlated reason codes from being double-counted as independent evidence.

## 3. Evidence strength rubric

* `WEAK` — one signal, or a single family with few signals.
* `MODERATE` — ≥2 families, or both signal types, or ≥3 signals.
* `STRONG` — both Edge **and** Node signals **and** ≥2 evidence families.

Severity = highest signal severity (operational importance); strength = amount/diversity of
evidence. Neither is an attack probability.

## 4. Replay results (existing UNSW v0.2 shadow outputs; gap 60 s)

| | value |
|---|---|
| edge signals | 566 |
| node signals | 669 |
| total signals | 1,235 |
| episodes | 633 |
| episodes/site/day | 20.3 |
| signal compression ratio | 1.95 |
| signals/episode mean / median / p95 | 1.95 / 1.0 / 5.0 |
| edge-only / node-only / mixed | 34.9% / 45.8% / 19.3% |
| evidence strength | WEAK 478 · MODERATE 33 · STRONG 122 |
| severity | CRITICAL 55 · HIGH 51 · MEDIUM 226 · LOW 299 · INFO 2 |
| top evidence families | TRAFFIC_VOLUME 832 · PROTOCOL_CHANGE 738 · TOPOLOGY_SPREAD 711 · DIRECTIONAL_CHANGE 458 · PORT_CHANGE 424 · PEER_NOVELTY 160 · PEER_SET_CHANGE 70 |

**Compression is modest on UNSW** because the dataset is mostly normal with sparse, largely
uncorrelated alerts (mean ≈1.4 signals/episode). Denser, related campaigns would compress more.

## 5. Correlation gap sensitivity

| gap (s) | episodes | episodes/day | compression | p95 duration (s) | mixed % |
|---:|---:|---:|---:|---:|---:|
| 30 | 651 | 20.9 | 1.90 | 90 | 18.9 |
| 60 | 633 | 20.3 | 1.95 | 60 | 2.1 |
| 120 | 599 | 19.2 | 2.06 | 180 | 20.5 |
| 300 | 528 | 17.0 | 2.34 | 390 | 22.9 |

Sensitivity is **mild** (episode count varies ~±7% across 30–300 s). Recommended default:
**60 s** — balances temporal locality, coherence, and compression; 300 s raises p95 duration to
330 s (over-merge risk) and 30 s over-fragments.

## 6. Synthetic scenarios (gap 60 s)

| scenario | episodes | strength |
|---|---:|---|
| SCN-E01 SAME_ENTITY_BURST | 1 | STRONG |
| SCN-E02 CHAIN | 1 | WEAK |
| SCN-E03 UNRELATED_SIMULTANEOUS | 2 | WEAK, WEAK |
| SCN-E04 SAME_ENTITY_LARGE_GAP | 2 | WEAK, WEAK |
| SCN-E05 NODE_EDGE_SUPPORT | 1 | STRONG |
| SCN-E06 ALERT_STORM | 1 | MODERATE |
| SCN-E07 PERCOLATION_STRESS | 2 | MODERATE, WEAK |
| SCN-E08 TWO_ACTIVE_MERGE | 1 | MODERATE |

## 7. False-merge testing

| case | episodes | merged? |
|---|---:|---|
| same timestamp only | 2 | no |
| same severity only | 2 | no |
| same reason code only | 2 | no |
| unrelated simultaneous | 2 | no |
| positive control (connected) | 1 | yes |

Proximity alone does **not** merge; only temporal **and** relational connection does. **0 false
merges.**

## 8. Reproduce

```bash
python -m ai.episodes.evaluation.run_experiments   # correlates UNSW shadow signals + reports
python -m pytest tests/ai/episodes -q
```

## 9. Final questions

1. **Edge signals?** 566.
2. **Node signals?** 669.
3. **Total signals?** **1,235**.
4. **Behavioral Episodes?** **633** (gap 60 s).
5. **Episodes/site/day?** 20.3.
6. **Compression ratio?** **1.95**.
7. **Median / p95 signals/episode?** 1.0 / 5.0.
8. **Median / p95 assets/episode?** 1.0 / 1.0 (most episodes are single-entity).
9. **Edge-only %?** 34.9%.
10. **Node-only %?** 45.8%.
11. **Mixed Edge+Node %?** 19.3%.
12. **Recommended gap?** **60 s**.
13. **Why?** Balances temporal locality, coherence, and compression; 300 s inflates p95
    duration to 330 s (over-merge risk) while 30 s over-fragments; all gaps give similar
    volume, so the more local default is preferred.
14. **Sensitivity?** Mild — 651→528 episodes across 30→300 s (compression 1.90→2.34).
15. **False merges?** **0** in deterministic synthetic tests.
16. **Percolation bounded how?** `max_episode_duration_seconds` (600 s) caps extension from
    the start; SCN-E07 (13-signal chain over ~13 min) splits into 2 bounded episodes.
17. **Evidence-strength distribution?** WEAK 478 · MODERATE 33 · STRONG 122.
18. **Most common families?** TRAFFIC_VOLUME, PROTOCOL_CHANGE, TOPOLOGY_SPREAD,
    DIRECTIONAL_CHANGE, PORT_CHANGE.
19. **Throughput/latency?** **~72,600 signals/sec**, 0.0138 ms/signal (CPU).
20. **Useful enough to keep?** **Yes** — it deterministically, explainably, and
    evidence-preservingly groups signals into smaller, temporally bounded, relationally
    coherent episodes, with a structured evidence graph and machine summary. Compression is
    modest on mostly-normal UNSW but the layer is correct and ready to add value as signal
    density rises.
21. **Limitations preventing "attack/incident"?** No ground truth; correlation ≠ causality;
    entity-level `dataset_ip_fallback` identity; provisional thresholds inherited from Edge/Node;
    behavioral episodes are explicitly **not** incidents; no attack taxonomy.
22. **Streaming-suitable?** **Yes** — chronological single pass, bounded active state, only
    past signals decide membership (future only closes episodes).

## Scope

No fusion, GNN/Temporal GNN, attack-path, campaign reconstruction, attack taxonomy, or
remediation. Nothing committed.

> **Correction (Phase 3.5).** A node score→window attribution bug in batched node scoring
> (fixed in Phase 3.5) changed the standalone reference from 857 to **633 episodes**; all
> figures above reflect the corrected runtime. Full detail: `docs/AI_BEHAVIORAL_EPISODE_V1_ERRATA.md`.
> The published tag `ai-behavioral-episode-v1` is immutable and is **not** moved or rewritten.
