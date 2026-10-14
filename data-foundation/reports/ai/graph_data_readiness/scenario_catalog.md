# Controlled Scenario Catalogue (LAB-G01..G12)

| id | name | expected label | expectedness | duration (min) | entities |
|---|---|---|---|---|---|
| LAB-G01 | Legitimate new peer | normal_role_consistent_new_edge | EXPECTED | 30 | engineering_ws, plc_02 |
| LAB-G02 | Role-consistent new device | normal_role_consistent_new_edge | EXPECTED | 45 | plc_03, historian |
| LAB-G03 | Role-inconsistent new peer | role_inconsistent_new_edge | UNUSUAL | 20 | camera_01, engineering_ws |
| LAB-G04 | Fan-out burst | fanout_burst | UNUSUAL | 15 | asset_x |
| LAB-G05 | Inbound convergence | inbound_convergence | UNUSUAL | 15 | asset_y |
| LAB-G06 | Peer-set replacement | peer_set_replacement | UNUSUAL | 30 | asset_z |
| LAB-G07 | Local topology rewiring | topology_rewiring | UNUSUAL | 30 | plc_01, plc_02, broker |
| LAB-G08 | Cross-zone relationship | cross_zone_communication | UNUSUAL | 20 | camera_02, plc_03 |
| LAB-G09 | Temporal chain | chain_formation | UNUSUAL | 20 | asset_a, asset_b, asset_c |
| LAB-G10 | Multi-node structural change | topology_rewiring | UNUSUAL | 30 | group_1 |
| LAB-G11 | Device replacement / identity change | expected_structural_transition | EXPECTED | 45 | plc_02_old, plc_02_new |
| LAB-G12 | Legitimate maintenance window | expected_structural_transition | EXPECTED | 60 | jump_host |

## Hard controls

| unusual | control | pairs with |
|---|---|---|
| camera -> engineering_ws | camera -> nvr | LAB-G03 |
| plc -> arbitrary_iot | plc -> historian | LAB-G03 |
| cross-zone camera -> plc | cross-zone camera -> nvr (allowed path) | LAB-G08 |

## Replication

- ≥ **3** instances per key scenario across: distinct source nodes, distinct destination nodes, different times, different topology regions.
- Avoid learning a specific asset id: vary source/destination/timing/region.

