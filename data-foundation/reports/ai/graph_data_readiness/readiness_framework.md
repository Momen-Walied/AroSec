# Readiness Framework

Transparent, framework-independent validators that decide whether a dataset may be used for Temporal GNN research. Dimensions are reported individually (never hidden in one opaque score); each is PASS / WARN / FAIL, and **every critical dimension must PASS** for the entry gate to open.

| dimension | critical | rule (summary) |
|---|---|---|
| STRUCTURAL_DIVERSITY | yes | hub dominance, independent neighbourhoods, 2-hop gain, node count |
| TEMPORAL_DIVERSITY | yes | relationship births, inactivity transitions |
| IDENTITY_QUALITY | yes | identity level ≥ L2 |
| GROUND_TRUTH_QUALITY | yes | expected + unusual structural ground truth present |
| GROUND_TRUTH_PROVENANCE | yes | independent source (never the anomaly outputs) |
| NON_HUB_COVERAGE | yes | non-hub target edges ≥ 100 |
| NEW_EDGE_COVERAGE | yes | new-edge events ≥ 50 |
| COLD_START_COVERAGE | yes | new-node samples ≥ 20 |
| ROLE_DIVERSITY | yes | role + zone metadata present |
| ROLE_GENERALIZATION | yes | ≥ 3 independent assets per key role (hold-out) |
| SCENARIO_REPLICATION | yes | ≥ 3 instances/scenario, ≥ 8 scenarios |
| SPLIT_QUALITY | yes | independent topology regions to hold out |
| TWO_HOP_CONTEXT | yes | 2-hop adds local (>0.5) but not whole-graph (<80% of nodes) context |
| DATASET_INTEGRITY | yes | dataset id/version/capture id/checksums recorded |

Thresholds: {"min_nodes": 20, "hub_dominance_fail": 0.5, "hub_dominance_warn": 0.3, "min_independent_neighbourhoods_fail": 2, "min_independent_neighbourhoods_warn": 4, "two_hop_min_gain_fail": 0.5, "non_hub_edges_fail": 100, "non_hub_edges_warn": 500, "new_edges_fail": 50, "new_edges_warn": 200, "temporal_births_fail": 50, "inactivity_fail": 10, "identity_min_level": 2, "cold_start_fail": 20, "replication_min": 3, "min_scenarios": 8}

