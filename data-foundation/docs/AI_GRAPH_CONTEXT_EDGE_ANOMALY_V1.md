# AI Graph-Context Edge Anomaly v1 (Phase 4B)

**Status:** non-neural, causal, framework-independent graph-context edge-anomaly baseline.
**No GNN is trained or implemented.** Frozen v0.2 and the Edge/Node/Episode contracts are
untouched. Graph context is produced as **independent evidence** and is **never fused** with
Edge Behavior.

Research question: *does causal local temporal graph context improve edge anomaly intelligence
beyond Edge Behavior v1?*

Inputs: Phase 4A `TemporalGraphSampleV1` (event stream), `EdgeFeatureWindowV2`,
`NodeFeatureWindowV2`. Target edge at time `T`, causal 1-hop neighborhood, 1 h lookback. No
completed-episode information is ever used.

Companion artifacts: `docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md`,
`reports/ai/graph_context_v1/*`, contracts `GraphContextEdgeFeaturesV1` and
`GraphContextAnomalyResultV1`.

---

## 1. Method

- **Causal state**: recent `[T−lookback, T)`, baseline `[T−2·lookback, T−lookback)`. No future
  edge/neighbor/degree/frequency ever enters a feature (Phase 4A leakage classes A–H reused).
- **Feature families** (`GraphContextEdgeFeaturesV1`): source structure, destination structure,
  relational structure (peer overlap, Jaccard, Adamic-Adar), local temporal change, structural
  novelty, chain/motif. 11 features feed the score.
- **Scorers**: three interpretable family z-scores — `novelty`, `change`, `low_similarity` —
  combined as their mean mapped through a logistic to `[0,1]`. Normalization fit on **TRAIN**;
  alert threshold chosen on **VALIDATION** only.
- **Hub classification**: structural (causal degree ≥ max(p95, 5)); never a hardcoded asset id.
- **No fusion**: `graph_context_score` is reported beside `EdgeAnomalyResultV1`, not averaged.

## 2. Feature overlap audit

All 11 scored graph features classify as **NEW GRAPH INFORMATION** (none ≥0.9 or ≥0.7 correlated
with any existing Edge/Node local feature). Degree/count features that *could* duplicate Node
Behavior were deliberately kept out of the score. See `feature_overlap_audit.md`.

## 3. Normal-data evaluation (TEST, chronological)

- TEST alert rate: **1.35%** at a validation-calibrated threshold (0.7358).
- Alerts: 183 → **5.87 / site / day**, 0.419 / entity / day, 0.079 / relationship / day.
- Edge Behavior v1 on the same TEST windows: **1.78%** alert rate (its own validation calibration).
- New vs known edge: new **1.87%** vs known **1.30%**.

## 4. Hub bias — total

Every TEST edge-window involves the high-degree gateway: **hub-involved = 100%**,
**non-hub = 0**. The only non-hub dimension that exists is *source*: 13,523 edges have the hub as
source (1.26% alert) and just **53** do not (22.6% alert). There is effectively no non-hub edge
population to validate against — an intrinsic property of the star graph, not a modelling choice.

## 5. Synthetic structural scenarios (vs Edge Behavior)

Edge Behavior's edge-local novelty flags `NEW_PEER` for **every** new edge (proxy 1.0 for all),
so it cannot separate a structurally plausible new edge from an unusual one.

| scenario | graph score | novelty | change | low-sim |
|---|---|---|---|---|
| G01 new edge | 0.903 | 3.22 | 3.49 | 0.00 |
| G02 fan-out | 0.864 | 3.22 | 2.33 | 0.00 |
| G03 chain | 0.713 | 0.40 | 2.33 | 0.00 |
| G04 rewiring | 0.917 | 3.22 | 4.64 | −0.66 |
| G05 inbound | 0.881 | 3.22 | 2.80 | 0.00 |
| **G06 normal new edge** | **0.935** | 4.69 | 4.18 | **−0.89** |
| **G07 unusual edge** | **0.951** | 4.69 | 4.18 | **0.00** |
| G08 compound | 0.930 | 4.69 | 3.07 | 0.00 |

**Finding:** the `low_similarity` family *does* separate G06 (plausible, −0.89) from G07
(unusual, 0.00). The **combined score does not** (0.935 vs 0.951): novelty/change dominate and
behave like Edge novelty. Graph context's incremental structure lives in the **similarity**
family, not the novelty family.

## 6. Complementarity & disagreement

- Edge–Graph: Pearson **−0.032**, Spearman **−0.056** (essentially independent).
- Node–Graph: Pearson **0.008**, Spearman **0.074** (essentially independent).
- Quadrants (TEST): both high 13 · edge-high/graph-low 228 · edge-low/graph-high 170 · both low 13,165.
- Interpretation only; **no example is labelled an attack**.

## 7. Ablations

**Lookback (1-hop):** 5 m → 2.10% alert, G06↔G07 gap 0.033; 30 m → 3.76%, gap 0.021;
**1 h → 1.36% alert, gap 0.016**; 24 h → **31.3% alert**, gap 0.004.
→ **1 h confirmed** (Phase 4A choice): lowest alert rate with a retained scenario gap; 24 h
collapses (whole-graph context).

**Hop:** 1-hop and 2-hop are **identical in every cell** — on a star, 2-hop = 1-hop. **2-hop adds
nothing.**

## 8. Performance (CPU, no GPU)

- Feature generation per target: p50 **0.074 ms**, p95 0.092 ms, **p99 0.161 ms**.
- Scoring: ~0.00004 ms/row. Full generation for all targets ≈ 30 s.
- Framework-independent (no PyG/DGL/torch on the path).

## 9. Final answers

1. **Measurable incremental value?** Partially — graph context is essentially independent of
   Edge (Spearman −0.06) and Node (0.07), and its *similarity* family distinguishes plausible vs
   unusual new edges; but the combined score behaves like edge novelty on new edges.
2. **Best non-GNN baseline?** The graph-context scorer combining novelty/change/**low_similarity**.
3. **Normal TEST alert rate?** **1.35%** (183 alerts).
4. **Alerts/site/day?** **5.87**.
5. **Scenarios improved vs Edge?** Clarity on *similarity*: G06/G07 separation; Edge cannot do it.
6. **Which do not?** G01/G02/G03/G05/G08 combined scores are indistinguishable from G06 (Edge
   already flags them all) — no additive gain there.
7. **Distinguish plausible vs unusual new edge?** The `low_similarity` family yes; the combined
   score only weakly (0.935 vs 0.951).
8. **Edge vs Graph Pearson/Spearman?** −0.032 / −0.056.
9. **Node vs Graph Pearson/Spearman?** 0.008 / 0.074.
10. **How much duplicated from Edge/Node?** Feature audit: 0 of 11 scored features duplicate.
11. **How severe is hub bias?** Total — 100% of TEST edges are hub-involved.
12. **Collapse on non-hub edges?** Cannot be assessed: only 53 non-hub-source edges exist
    (they alert at 22.6% vs 1.26% for hub-source — a large differential on a tiny sample).
13. **Best lookback?** **1 h**.
14. **Does 2-hop add real value?** **No** — identical to 1-hop.
15. **Feature generation p99?** **0.161 ms**.
16. **Scoring p99?** ~0.00004 ms/row (mean).
17. **CPU/memory footprint?** CPU-only, ~tens of seconds full-dataset, small parquet state.
18. **Worth keeping as a permanent component?** **Yes, as independent evidence** — cheap,
    uncorrelated, and it adds a similarity structure Edge/Node lack — but modestly.
19. **Justify Phase 4C neural Temporal GNN?** **NO.**
20. **(if yes)** n/a.
21. **(if no) what is needed first?** A **non-degenerate graph**: a non-star topology with
    meaningful non-hub edges, richer/heterogeneous entities (services, VLANs, users), labelled
    structural ground truth, and more new-edge events. On the current star graph a GNN would
    most likely relearn hub identity (leakage-by-structure) rather than general structure.

## 10. Verdict

The provisional gate (≤1% TEST alert AND improvement over Edge in ≥3 of G04/G05/G07/G08 AND no
hub collapse AND non-duplicated information) is **NOT met**: alert rate is ~1.35%, hub bias is
total, 2-hop is inert, and combined graph context does not out-discriminate Edge on the key
scenarios. **Recommendation: DO NOT BUILD GNN YET.** Keep Graph Context v1 as independent
evidence; revisit neural temporal-graph research only on a richer, non-star graph with structural
ground truth.

## 11. Scope discipline

No GNN/TGN/TGAT/GCN/GAT/GraphSAGE/HGT/R-GCN/GAE/graph-transformer; no attack-path, stage,
incident, campaign, or remediation; no new datasets; no fusion; no commit/push/tag.
