# Evaluation Plan

## Metrics

- **Ranking (link/next-edge):** MRR, Hits@1/5/10, Recall@K.
- **Anomaly ranking:** PR-AUC, ROC-AUC, Precision@K, Recall@K, NDCG where meaningful.
- **Operational:** false signals/entity/day, false signals/site/day, latency, memory, model size.
- **Synthetic structural:** scenario detection rate and score uplift vs the non-graph floor.

## Reporting rules

- Metrics reported **separately by cold-start category** (see readiness.md); aggregates may not hide cold-start failure.
- Metrics reported **per split** (train/validation/test), never pooled.
- Comparisons always: Edge-only vs graph heuristic vs (future) temporal GNN.

