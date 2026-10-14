# Temporal Graph Leakage Model

Graph ML leaks future information more subtly than tabular ML: a point-in-time snapshot is
easy to build from the *whole* graph by accident, and message passing can pull a future
neighbor across a split boundary. This document is the threat model and the enforcement
contract for Temporal Graph Intelligence v1. It mirrors the existing v0.2 temporal-leakage
discipline (`python -m src.cli validate-v2` → `temporal_leakage_violations = 0`).

**Core rule:** a sample at `as_of = T` may use only information with event time `< T`.
The canonical event stream is sorted by `(window_start, event_id)`; everything a sample
references is drawn from events strictly before `T`.

## Threat model

### A. Future edge leakage
- **Risk:** at `T`, the adjacency includes a relationship first observed after `T`.
- **Prevention:** samples reference `causal_event_ids` drawn only from
  `[T − lookback, T)` (strictly `< T`). The target edge-window itself is excluded.
- **Test:** `test_no_future_edges_referenced`.

### B. Full-graph construction leakage
- **Risk:** build the whole 31-day graph, then split rows by time; neighbors/features still
  encode the future.
- **Prevention:** the graph is rebuilt **per target** from the causal slice; splits partition
  the *query times*, never the graph. History carries forward (online), but no sample can see
  an edge dated at/after its own `as_of`.
- **Test:** `test_no_future_neighbors`, `test_samples_chronologically_ordered`.

### C. Node feature leakage
- **Risk:** node features at `T` include information observed after `T`.
- **Prevention:** node features are derived from the causal event slice (degree, recent peers,
  new-peer counts) — never from the full-history materialization. When materialized
  `NodeFeatureWindowV2` is joined, only rows with `window_start < T` are eligible.
- **Test:** causal-slice invariants in `test_causal_neighborhood_extraction_only_past`.

### D. Edge feature leakage
- **Risk:** novelty/history features computed with hindsight.
- **Prevention:** the frozen `EdgeFeatureWindowV2` builder already guarantees history/novelty
  use observations strictly before `window_start`; the graph builder copies those fields
  verbatim and never recomputes them with future data.

### E. Neighbor aggregation leakage
- **Risk:** message passing includes a neighbor that only existed in the future.
- **Prevention:** the hop ball is computed on the causal adjacency only; `neighbor_node_ids`
  is a subset of the causal slice endpoints.
- **Test:** `test_no_future_neighbors`.

### F. Negative-sampling leakage
- **Risk:** a pair sampled as "negative" at `T` becomes a real edge soon after.
- **Prevention:** a negative must be (a) not observed before `T`, and (b) not observed within
  `(T, T + horizon]`. Rule (b) is the temporal-safety guard.
- **Nuance:** for strict *next-edge* prediction, a pair that becomes positive within the
  horizon is a **future positive**, so labelling it negative **is** label leakage — excluded.
- **Test:** `test_negative_sampling_temporal_safe`.

### G. Normalization leakage
- **Risk:** a scaler/mean/std is fit on all splits.
- **Prevention:** `TrainOnlyStandardizer` is fit on TRAIN only and merely applied to
  VALIDATION/TEST.
- **Test:** `test_train_only_fitting_differs_from_full_fit`.

### H. Episode leakage
- **Risk:** a completed future `BehavioralEpisodeV1` is used to predict a graph state that
  occurred before the episode completed.
- **Prevention:** episodes are **not** an input to any graph sample. `TemporalGraphSampleV1`
  carries no episode fields (tested). Episodes may be used only for *retrospective* grouping /
  target selection **after** closure, never to predict earlier signals.
- **Test:** `test_sample_has_no_episode_fields`.

## Additional boundaries

### Cold-start
New nodes/edges are real in production. Aggregates must not hide them; every metric is
reported by category (`unknown/known` × `new/known edge`). The memory module of any future
temporal model is the inductive mechanism for new nodes.

### Attack-path boundary
Temporal connectivity is **not** causality. `A → B → C` does **not** prove A compromised B
then B compromised C. This phase infers no entry point, lateral movement, attacker, victim,
objective, or attack stage.

### Synthetic scenarios
`SCN-G01..G08` are **evaluation-only** and are never mixed into training or into the
self-supervised objective.

## Enforcement summary

| class | mechanism | test |
|---|---|---|
| A future edge | causal slice `< T` | `test_no_future_edges_referenced` |
| B full-graph | per-target rebuild, split by query time | `test_no_future_neighbors` |
| C node feats | causal derivation / `< T` join | `test_causal_neighborhood_extraction_only_past` |
| D edge feats | frozen causal builder copied verbatim | (frozen) `validate-v2` |
| E neighbor agg | hop ball on causal adjacency | `test_no_future_neighbors` |
| F negative sampling | not-before AND not-in-horizon | `test_negative_sampling_temporal_safe` |
| G normalization | TRAIN-only fit | `test_train_only_fitting_differs_from_full_fit` |
| H episode | episodes excluded from samples | `test_sample_has_no_episode_fields` |
