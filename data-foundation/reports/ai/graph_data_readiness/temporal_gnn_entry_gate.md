# Temporal GNN Entry Gate

Phase 4D may not begin unless **all critical dimensions PASS**.

| requirement | rule |
|---|---|
| STRUCTURAL_DIVERSITY | acceptable hub dominance, >=2 independent local neighbourhoods |
| NON_HUB_COVERAGE | meaningful non-hub target-edge count |
| NEW_EDGE_COVERAGE | enough new-edge events for evaluation |
| TEMPORAL_DIVERSITY | enough structural transitions over time |
| IDENTITY_QUALITY | identity level >= L2 |
| ROLE_DIVERSITY | roles and zones recorded where required by the evaluated task |
| GROUND_TRUTH_QUALITY | expected/unusual ground truth present |
| GROUND_TRUTH_PROVENANCE | independent ground-truth source (never the anomaly outputs) |
| SCENARIO_REPLICATION | >= 3 instances per key scenario + hard controls |
| COLD_START_COVERAGE | new-node categories represented |
| ROLE_GENERALIZATION | >= 3 independent assets per key role for hold-out |
| SPLIT_QUALITY | entity/topology/time holdout evaluation is possible |
| TWO_HOP_CONTEXT | 2-hop adds local (not whole-graph) context |
| DATASET_INTEGRITY | immutable dataset package/version identity recorded |

Current UNSW gate: **BLOCKED**.

