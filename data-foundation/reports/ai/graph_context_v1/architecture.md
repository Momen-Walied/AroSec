# Graph-Context Edge Anomaly v1 — Architecture

Independent, non-neural, causal graph-context intelligence for edge anomaly. **Not fused** with Edge Behavior. No attack semantics.

Pipeline:
```
CommunicationObservation v0.2
  → EdgeFeatureWindowV2 (frozen-derived, causal)
  → TemporalEdgeEvent stream (Phase 4A builder)
  → causal graph state at T  [T-lookback, T)
  → GraphContextEdgeFeaturesV1 (1-hop, 1h; families A–F)
  → family z-scores (novelty · change · low_similarity)
  → GraphContextAnomalyResultV1.graph_context_score  (independent)
```

- Feature families: ['novelty', 'change', 'low_similarity'].
- Normalization fit on TRAIN; threshold on VALIDATION; TEST never used for fitting.
- Hub classification is structural (causal degree ≥ p95), never a hardcoded asset id.

