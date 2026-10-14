# Structural Requirements

A dataset must be structurally **non-degenerate**: multiple local neighborhoods, no single node owning the sample distribution, and actual 2-hop information.

## Required (REQUIRED)
- ≥ 20 nodes; ≥ 2 independent local neighbourhoods (nodes of degree ≥ 2 split into ≥ 2 connected parts).
- top-1 node incident to < 50% of edge-windows (FAIL), < 30% preferred (WARN).
- 2-hop neighbourhood adds > 0.5 nodes on average over 1-hop.
- ≥ 100 non-hub target edges.
## Recommended
- ≥ 4 independent neighbourhoods; degree entropy ≥ 2.0; clustering > 0.
## Optional
- heterogeneity (services/zones) — helpful, not forced.

## Role-holdout feasibility (amendment 1)

A dataset may contain **many nodes and still be unsuitable** for inductive graph evaluation if each role is represented by only one device. Total node count alone must **not** make a dataset appear ready. For every key role participating in train/validation/test generalization, require **≥ 3 independent asset instances** (e.g. Camera-01/02/03, PLC-01/02/03). Fewer instances → ROLE_GENERALIZATION WARN or FAIL depending on whether the planned hold-out is still statistically meaningful.

## Current UNSW measured

```json
{
  "node_count": 63,
  "edge_count": 74,
  "density": 0.018945,
  "weak_components": 1,
  "largest_component_share": 1.0,
  "degree_p50": 1,
  "degree_p90": 1,
  "degree_max": 62,
  "degree_entropy": 0.6654,
  "hub_dominance_top1": 0.5,
  "hub_dominance_top5": 0.7761,
  "hub_node_count": 1,
  "assortativity": -1.0,
  "avg_clustering": 0.0,
  "core_components": 1,
  "core_component_sizes": [
    1
  ],
  "independent_local_neighborhoods": 1,
  "mean_1hop": 1.968,
  "mean_2hop": 62.0,
  "two_hop_minus_one_hop": 60.032,
  "new_edge_count": 74,
  "reappearing_relationships": 50,
  "non_hub_target_edges": 0,
  "non_hub_edge_share": 0.0
}
```

