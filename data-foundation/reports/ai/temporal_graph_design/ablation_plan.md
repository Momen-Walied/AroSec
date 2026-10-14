# Graph-Context Ablation Plan

Future experiments must isolate *which* context helps. Each row is a controlled variant of the same model:

1. model WITHOUT graph context (edge-local features only) — the floor.
2. + 1-hop neighbours.
3. + 2-hop neighbours (expected to collapse to the full graph here).
4. + temporal order / event-time deltas.
5. + edge features (novelty/history).
6. + node features.
7. + causal lookback sweep {5 m, 30 m, 1 h, 6 h, 24 h}.

Report MRR / PR-AUC / scenario detection per variant, **by cold-start category**, and the delta vs the non-graph floor. The adoption gate (evaluation_plan.md) applies to the best graph variant, not to the union.

