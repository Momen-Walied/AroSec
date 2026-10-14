# AI Temporal Graph Intelligence v1 — Design & Benchmark (Phase 4A)

**Status:** design + dataset benchmark + non-GNN baselines + evaluation harness. **No neural
model is trained or implemented.** Frozen Data Foundation v0.2 and the Edge/Node/Episode
intelligence contracts are untouched.

**Central question:** *Does temporal graph context provide measurable information beyond the
existing Edge Behavior and Node Behavior intelligence?* This phase builds the benchmark that
can prove or reject that hypothesis — it does not assume a GNN will win.

Companion documents:
- `docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md` — leakage threat model (classes A–H).
- `reports/ai/temporal_graph_design/*` — audit, statistics, tasks, samples, splits, negatives,
  baselines, model review, ablation, evaluation, readiness.

---

## 1. The graph we actually have (audit)

Inspect, not aspiration. Today's production graph is **homogeneous**:

- **Node** — asset / communication entity (`asset:*`). Identity is provisional
  (`dataset_ip_fallback`; no MAC/vendor/VLAN/subnet for UNSW).
- **Persistent edge** — `CommunicationRelationship` (src→dst communication pair).
- **Temporal edge observation** — `CommunicationObservation` → `EdgeFeatureWindowV2`.
- **Derived entity facts** — `NodeFeatureWindowV2`; **context** — `EdgeAnomalyResultV1`,
  `NodeAnomalyResultV1`, `BehavioralEpisodeV1`.

Measured (UNSW v0.2, 30 s): **63 nodes, 74 directed edges, 67,885 edge-windows, 98,747
observations, 31.2 days.** Density **0.019**; one connected component; 24/74 reciprocal. A
single gateway owns ~99.6% of edge-windows → the graph is effectively a **star**, and the
**2-hop neighborhood of any node is the whole graph**. Only **74 new edges** ever appear.

**A. Current Temporal Asset Communication Graph** (implemented) vs **B. Future heterogeneous
Cyber Knowledge Graph** (services, VLANs, subnets, users, processes, applications,
vulnerabilities, reachability — **not available today**). Phase 4A designs for A and keeps the
contract open for B.

## 2. Graph state — `TemporalGraphSampleV1`

Versioned AI-layer contract (`ai/graph_intelligence/contracts.py`) describing, at time `T`:
visible nodes, causal edges (`causal_event_ids`), causal node facts, causal edge features,
temporal deltas (`as_of`, `target_delta_s`, `neighborhood_span_s`), identity quality, `split`,
and `cold_start_category`. It **references** causal members rather than embedding a framework
tensor, so the canonical data stays framework-independent.

Representation options considered: (i) one snapshot, (ii) snapshot sequence, (iii) temporal
event stream, (iv) target-centered temporal subgraph. **Recommended: (iv) ego/local temporal
subgraph** built on a canonical **(iii) event stream** store — see §5.

## 3. Leakage model

Full threat model in `docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md`: future-edge leakage,
full-graph-construction leakage, node/edge feature leakage, neighbor-aggregation leakage,
negative-sampling leakage, normalization leakage, and **episode leakage** — each with an
enforcement mechanism and a regression test.

## 4. Candidate tasks (evaluated)

| task | question | ground truth | verdict |
|---|---|---|---|
| **A** next-edge / link prediction | which relationship appears next? | self-supervised | **degenerate here** |
| **B** graph-context edge anomaly | is this edge transition unusual given neighborhood? | scenarios + normal-test | **PRIMARY v1** |
| **C** graph-context node anomaly | does structure improve on Node v1? | scenarios + normal-test | later track |
| **D** temporal subgraph deviation | is the local subgraph transition unusual? | scenarios | later track |
| **E** next-relationship transition | "what happens next?" | self-supervised | later track |

**Why A is not primary:** on this star graph, next-edge ranking is trivial — with easy negatives
*frequency, recency, preferential-attachment, source-frequency, degree-deviation* all reach
**MRR ≈ 1.0**; with peer-group ("hard") negatives the neighbourhood heuristics become
**anti-correlated** (a true leaf→hub edge shares fewer peers than a false leaf→leaf edge). A
cannot discriminate models today.

**Why B is first:** it directly answers the central question, has a frozen baseline (Edge
Behavior v1) and an established evaluation pattern (synthetic scenarios + normal-test
false-signal rate), and it degrades gracefully to an honest null result.

## 5. Sample types (assessment)

| option | memory | streaming | leakage | explainability | verdict |
|---|---|---|---|---|---|
| A full snapshot | low | poor | high | medium | rejected |
| B snapshot sequence | high | poor | high | medium | rejected |
| C temporal event stream | lowest | best | lowest | high | **canonical store** |
| D ego temporal subgraph | low | good | low | high | **recommended sample** |

## 6. Local subgraph extraction

- **Hop count: 1** (2-hop = whole graph; recorded as ablation only).
- **Lookback: 1 h** (provisional). Probe: 5 m→~7 edges, 30 m→~13, 1 h→~17, 6 h→~27,
  24 h→~33 (~half the whole graph). 1 h captures the recent decision-relevant neighborhood.
- **max_neighbors 64, max_events 512**, deterministic recency truncation.
- Causal only: events in `[T − lookback, T)`, hop ball on the causal adjacency.

## 7. Dataset builder

`ai/graph_intelligence/data/builder.py` (framework-independent): consumes frozen/derived v0.2
tables and writes `nodes.parquet`, `events.parquet`, `samples.parquet`, `targets.parquet`,
`metadata.json`. Sort order `(window_start, event_id)`; deterministic ids
(`gte:`/`tgs:`/`tgt:`); versioned metadata with split boundaries and feature versions. No PyG/DGL
objects are persisted. **67,885 samples** generated from UNSW v0.2.

## 8. Train / validation / test

Chronological **60/20/20** over target `as_of`, reusing the Edge/Node Behavior boundaries. No
random graph split. **History carries forward** (TRAIN → VALIDATION → TEST), parameters frozen
at each boundary — realistic online evaluation. Normalization is TRAIN-only.

## 9. Cold start

Categories: `KNOWN_NODE_KNOWN_EDGE`, `KNOWN_NODE_NEW_EDGE`, `NEW_NODE_KNOWN_NETWORK`,
`NEW_NODE_NEW_EDGE`. On UNSW the distribution is dominated by known/known (new edges are rare),
so **cold-start metrics must be reported separately**, never averaged away.

## 10. Negative sampling

Temporal-safe categories (strongest first): `hard` (shared peer), `temporally_plausible`
(peer-of-peer), `new_peer` (active non-neighbor), `random_non_edge`. A negative must be
not-observed-before AND not-observed-within-horizon (leakage class F). Deterministic RNG seeded
per target.

## 11. Non-GNN baselines

Ten graph heuristics (`ai/graph_intelligence/baselines/heuristics.py`): frequency, recency,
source-destination frequency, preferential attachment, common neighbors, Jaccard, Adamic-Adar,
peer overlap, degree deviation, structural novelty. These are the **minimum bar**; existing Edge
Behavior v1 / Node Behavior v1 / Episode metrics are the *product* baselines for TASK B.

## 12. Synthetic structural scenarios

`SCN-G01..G08` (new edge, fan-out burst, chain formation, local rewiring, inbound convergence,
structurally-normal new edge, structurally-unusual edge, compound change). **Evaluation only**;
never called attacks, never mixed into training.

## 13. Ablation design

No-graph floor → +1-hop → +2-hop → +temporal order → +edge features → +node features → lookback
sweep {5 m, 30 m, 1 h, 6 h, 24 h}, all reported by cold-start category.

## 14. Candidate model review (no implementation)

| family | temporal | directed | edge feats | inductive | CPU | complexity |
|---|---|---|---|---|---|---|
| TGN | event-native | yes | yes | strong | medium | medium-high |
| TGAT | event-native | yes | yes | strong | medium | high |
| DyRep | event-stream | yes | limited | good | medium | high |
| GraphSAGE (snapshot) | snapshots | weak | no | good | good | low |
| GAT (snapshot) | snapshots | weak | no | good | good | medium |
| HGT | snapshots | yes | limited | good | high | very high |

**HGT is not justified** (homogeneous graph). Snapshot models discard event time and edge
features. If the task is event-stream temporal edge anomaly, **TGN** fits best (TGAT as the
attention variant). Recommendation is **conditional** (§17).

## 15. Metrics

Ranking: MRR, Hits@1/5/10, Recall@K. Anomaly: PR-AUC, ROC-AUC, Precision@K, Recall@K, NDCG.
Operational: false signals/entity/day, false signals/site/day, latency, memory, model size.
Synthetic: scenario detection rate, score uplift vs the non-graph floor.

## 16. Product-level acceptance criterion (proposed)

A temporal graph model is adopted **only if all** hold:
- **A.** meaningful improvement over Edge/Node + graph heuristics on TASK B;
- **B.** improvement specifically on the structural scenarios where existing models are weak;
- **C.** acceptable CPU/memory cost (CPU-first, no GPU requirement);
- **D.** stable chronological generalization (no split-specific collapse);
- **E.** no unacceptable increase in false signals/entity/day.
The numeric thresholds are to be **proposed after** the non-GNN bar is measured on TASK B
(Phase 4A establishes the bar; it does not fix the gate numbers yet, per "propose quantitative
gates after examining baseline behavior").

## 17. Behavioral Episodes & Attack-Path boundary

- Episodes are **retrospective context only**; they are never an input to a graph sample
  (leakage class H). Legitimate: evaluation grouping, target selection after closure,
  downstream reasoning. Illegitimate: feeding future episode structure into earlier predictions.
- **Temporal connectivity is not causality.** No entry point, lateral movement, attacker,
  victim, objective, or attack stage is inferred. `A → B → C` proves nothing about compromise.

## 18. Final answers

1. **Current production graph:** homogeneous asset-communication graph (63 nodes, 74 directed
   edges, 67,885 edge-windows) — a single-hub star.
2. **Homogeneous or heterogeneous?** Homogeneous today; heterogeneous is *future* (B).
3. **Recommended primary task:** **TASK B — graph-context edge anomaly**.
4. **Why first:** directly tests incremental value vs Edge v1; measurable via scenarios +
   normal-test; unlike A it is not degenerate on this graph.
5. **Recommended sample representation:** ego/local temporal subgraph over a canonical event stream.
6. **Snapshot / sequence / event stream / ego subgraph?** **Ego temporal subgraph** (on an event stream).
7. **Recommended lookback:** **1 h** (provisional; 6 h/24 h as ablations).
8. **Recommended hop count:** **1** (2-hop collapses to the whole graph).
9. **How many samples from UNSW:** **67,885** (one per edge-window).
10. **Nodes / relationships / temporal events:** 63 nodes, 74 relationships, 67,885 edge events
    (98,747 observations).
11. **Degree / neighborhood:** out-degree p50 1 / p90 61 / max 61 (mean 5.3); 1-hop p50 1 /
    max 62; **2-hop = 62 (full graph)**.
12. **Cold-start categories & proportions:** mostly `KNOWN_NODE_KNOWN_EDGE`; new-edge and
    new-node buckets exist but are small (only 74 new edges ever).
13. **Recommended negative sampling:** temporal-safe, peer-group-weighted (`hard` /
    `temporally_plausible`) with `random_non_edge` controls.
14. **Strongest non-GNN baselines:** frequency, recency, source-destination frequency (for
    repeats); common-neighbors/Jaccard/Adamic-Adar/peer-overlap for structure.
15. **Edge/Node weaknesses graph context could improve:** peer-set changes, fan-out/fan-in
    bursts, coordinated relation changes, structural anomalies that single-edge novelty misses.
16. **Most appropriate GNN family for Phase 4B:** **TGN** (event-stream), TGAT as attention variant.
17. **Why:** event-native (preserves time + edge features), directed, inductive via memory, CPU-plausible.
18. **Unnecessarily complex today:** HGT (graph is homogeneous); snapshot GraphSAGE/GAT are
    simply the wrong shape (no event time).
19. **Major leakage risks:** future edges, full-graph construction, neighbor aggregation,
    negative-sampling future positives, normalization on all data, episode hindsight.
20. **Enough data to justify GNN now?** **Not yet.** The topology is star-like and tiny; the
    correct next step is to run the non-GNN bar on TASK B and proceed to Phase 4B only if the
    graph-context signal is real (and ideally on a richer graph).
21. **Quantitative gate for adoption:** §16 — improvement on TASK B *and* on structural
    scenarios, with acceptable CPU/memory and no false-signal increase (thresholds set after the
    baseline is measured).
22. **Impossible without attack/campaign ground truth:** attack/no-attack labels, attack stage,
    lateral-movement truth, campaign membership, attacker/victim, "did graph context detect a
    real attack" — all of this requires labeled traffic we do not have for UNSW.

## 19. Scope discipline

No GNN/TGN/TGAT/GraphSAGE/GAT/HGT/R-GCN/GAE/graph-transformer implementation or training; no
attack-path, attack-stage, campaign, incident-engine, or remediation work; no new datasets; no
commit/push/tag. Runtime data stays read-only.
