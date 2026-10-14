# Graph Feature Analysis

Descriptive statistics of the causal graph features (all targets):

| feature | mean | std | min | max |
|---|---|---|---|---|
| target_structural_novelty | 0.074 | 0.262 | 0.0 | 1.0 |
| source_peer_set_novelty | 0.255 | 0.115 | 0.0 | 1.0 |
| destination_peer_set_novelty | 0.057 | 0.231 | 0.0 | 1.0 |
| source_neighbor_set_change | 0.415 | 0.109 | 0.0 | 1.0 |
| destination_neighbor_set_change | 0.131 | 0.335 | 0.0 | 1.0 |
| local_degree_change_rate | 0.4 | 0.174 | 0.0 | 1.895 |
| local_new_edge_rate | 0.0 | 0.0 | 0.0 | 0.005 |
| source_neighbor_similarity | 0.0 | 0.0 | 0.0 | 0.0 |
| destination_neighbor_similarity | 0.0 | 0.0 | 0.0 | 0.0 |
| causal_jaccard | 0.0 | 0.0 | 0.0 | 0.0 |
| causal_adamic_adar | 0.0 | 0.0 | 0.0 | 0.0 |

## Family behaviour on TEST

- Novelty family drives alerts on new structural edges; change family on neighborhood churn; low-similarity family on edges with little shared structure.

> Neighbourhood heuristics are **anti-correlated** with re-activation on this star graph (a true leaf→hub repeat shares fewer peers than a false leaf→leaf pair), so graph scores are most meaningful for *new / structurally-changing* edges, not repeats.

