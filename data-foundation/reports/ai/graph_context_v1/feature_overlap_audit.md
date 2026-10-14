# Feature Overlap Audit (graph features vs existing Edge/Node features)

Goal: guarantee incremental graph information, not renamed Node/Edge features. Each graph feature is correlated (Pearson, causally aligned) with the existing local features; |r| ≥ 0.9 ⇒ DUPLICATE, 0.7–0.9 ⇒ DERIVED, else NEW GRAPH INFORMATION.

| graph feature | closest existing | pearson | classification |
|---|---|---|---|
| destination_neighbor_set_change | edge.historical_connection_count | -0.255 | NEW GRAPH INFORMATION |
| target_structural_novelty | edge.historical_connection_count | -0.193 | NEW GRAPH INFORMATION |
| destination_peer_set_novelty | edge.historical_connection_count | -0.152 | NEW GRAPH INFORMATION |
| local_new_edge_rate | edge.protocol_novelty_count | 0.13 | NEW GRAPH INFORMATION |
| local_degree_change_rate | edge.src_unique_peer_count | -0.12 | NEW GRAPH INFORMATION |
| source_neighbor_set_change | edge.src_unique_peer_count | -0.101 | NEW GRAPH INFORMATION |
| source_peer_set_novelty | edge.src_unique_peer_count | -0.075 | NEW GRAPH INFORMATION |
| source_neighbor_similarity | None | 0.0 | NEW GRAPH INFORMATION |
| destination_neighbor_similarity | None | 0.0 | NEW GRAPH INFORMATION |
| causal_jaccard | None | 0.0 | NEW GRAPH INFORMATION |
| causal_adamic_adar | None | 0.0 | NEW GRAPH INFORMATION |

- NEW: 11 · DERIVED: 0 · DUPLICATE: 0
- DUPLICATE/DERIVED features are excluded from the combined score (only the `NEW GRAPH INFORMATION` families contribute).

