# Current UNSW Readiness

- **Evaluated package:** `unsw_iotraffic` `v0.2` (capture_id: None)
- Overall: **FAIL** · GNN entry gate: **BLOCKED**
- Identity: L0_ip_only · role coverage 0% · zone coverage 0%
- Clock: PASS (out-of-order 0, missing 0)

| dimension | status | critical | reasons |
|---|---|---|---|
| STRUCTURAL_DIVERSITY | FAIL | True | top-1 node incident to 50.0% of edge-windows; only 1 independent local neighbourhood(s) |
| TEMPORAL_DIVERSITY | WARN | True | - |
| IDENTITY_QUALITY | FAIL | True | identity level L0_ip_only below required L2 |
| GROUND_TRUTH_QUALITY | FAIL | True | no structural ground truth recorded; missing transition types: chain_formation, cross_zone_communication, expected_structural_transition, fanout_burst, inbound_convergence, normal_role_consistent_new_edge, peer_set_replacement, role_inconsistent_new_edge, topology_rewiring, unusual_structural_transition |
| GROUND_TRUTH_PROVENANCE | FAIL | True | no ground truth rows |
| NON_HUB_COVERAGE | FAIL | True | only 0 non-hub target edges |
| NEW_EDGE_COVERAGE | WARN | True | - |
| COLD_START_COVERAGE | PASS | True | - |
| ROLE_DIVERSITY | FAIL | True | no role/zone metadata available |
| ROLE_GENERALIZATION | FAIL | True | no role assignments (cannot test role hold-out) |
| SCENARIO_REPLICATION | FAIL | True | no scenario instances |
| SPLIT_QUALITY | FAIL | True | no independent topology regions to hold out |
| TWO_HOP_CONTEXT | FAIL | True | 2-hop gain 60.032 ~ whole graph (hub collapse, not local context) |
| DATASET_INTEGRITY | WARN | True | missing recommended integrity: capture_id, lab_run_id, generated_at, checksums |

## Why GNN is blocked (derived, not forced)

- top-1 node incident to **50.0%** of edge-windows; top-5 77.6%.
- independent local neighbourhoods: **1**.
- 2-hop minus 1-hop: **60.032** nodes.
- non-hub target edges: **0**.
- new-edge events: **74**.
- new-node samples: **62**.
- structural ground truth: **0**.

