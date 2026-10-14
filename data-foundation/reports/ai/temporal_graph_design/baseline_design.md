# Non-GNN Baseline Design

Graph-aware, non-neural baselines computed on the causal graph at `as_of`. These set the minimum bar a temporal GNN must beat; none require training and none see the future.

| heuristic | directed-temporal sense | note |
|---|---|---|
| frequency | prior observation count of (u,v) | strongest on repeats |
| recency | 1/(1+seconds since last (u,v)) | reactivation signal |
| source_destination_frequency | (u→v) share of u's history | source-specific |
| preferential_attachment | deg(u)·deg(v) | hub bias (careful on a star) |
| common_neighbors | peers shared by u,v | structural |
| jaccard | shared / union peers | structural |
| adamic_adar | Σ 1/log deg over shared peers | structural, degree-weighted |
| peer_overlap | shared / min(deg) | peer-set overlap |
| degree_deviation | |deg(u)−deg(v)| | role asymmetry |
| structural_novelty | v ∉ neighbours(u) | new-peer indicator |

## Measured on the real data (next-edge ranking, temporal-safe negatives)

| heuristic | MRR | Hits@1 | Hits@5 |
|---|---|---|---|
| frequency | 1.000 | 1.00 | 1.00 |
| recency | 1.000 | 1.00 | 1.00 |
| source_destination_frequency | 1.000 | 1.00 | 1.00 |
| preferential_attachment | 1.000 | 1.00 | 1.00 |
| common_neighbors | 0.998 | 1.00 | 1.00 |
| jaccard | 0.998 | 1.00 | 1.00 |
| adamic_adar | 0.998 | 1.00 | 1.00 |
| peer_overlap | 0.998 | 1.00 | 1.00 |
| degree_deviation | 0.226 | 0.07 | 0.07 |
| structural_novelty | 0.221 | 0.07 | 0.07 |

> 2999 queries; negatives per positive: 5; negative categories: {'random_non_edge': 14975, 'hard': 18, 'new_peer': 2}.

**Finding (critical):** with easy negatives every heuristic reaches MRR ≈ 1.0, and with peer-group ('hard') negatives the neighbourhood heuristics become *anti-correlated* on this star graph (a true leaf→hub edge shares fewer peers than a false leaf→leaf edge). Next-edge ranking is therefore **degenerate** on the current graph — see task_comparison.md.

