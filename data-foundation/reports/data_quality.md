# Data Quality Report

- validation_ok: **True**

## Tables
| table | rows | duplicate rows | time min | time max | max null % |
|---|---:|---:|---|---|---:|
| assets/cicapt_iiot | 6 | 0 | 2024-03-01 02:13:00+00:00 | 2024-03-02 02:16:00+00:00 | 100.0 |
| labels/cicapt_iiot | 8 | 0 | 2024-03-01 02:13:00+00:00 | 2024-03-02 02:16:00+00:00 | 100.0 |
| campaigns/cicapt_iiot | 1 | 0 | - | - | 100.0 |
| graph_events/cicapt_iiot | 15 | 0 | 2024-03-01 02:13:00+00:00 | 2024-03-02 02:16:00+00:00 | 100.0 |
| cicapt_iiot_edges_30s | 9 | 0 | 2024-03-01 02:13:00+00:00 | 2024-03-02 02:16:00+00:00 | 0.0 |
| assets/x_iiotid | 29 | 0 | 2019-09-04 23:44:53+00:00 | 2020-02-24 00:22:04+00:00 | 100.0 |
| labels/x_iiotid | 728 | 0 | 2019-09-04 23:44:53+00:00 | 2020-03-07 04:31:45+00:00 | 100.0 |
| graph_events/x_iiotid | 1147 | 0 | 2019-09-04 23:44:30+00:00 | 2020-03-07 04:31:30+00:00 | 97.47 |
| x_iiotid_edges_30s | 1118 | 0 | 2019-09-04 23:44:30+00:00 | 2020-03-07 04:31:30+00:00 | 0.0 |
| x_iiotid_edges_30s_from_v2 | 1118 | 0 | 2019-09-04 23:44:30+00:00 | 2020-03-07 04:31:30+00:00 | 100.0 |
| assets/unsw_iotraffic | 63 | 0 | 2016-09-30 19:30:02.820351+00:00 | 2016-10-27 23:14:55.673513+00:00 | 100.0 |
| graph_events/unsw_iotraffic | 77165 | 0 | 2016-09-30 19:30:00+00:00 | 2016-10-31 23:46:30+00:00 | 99.92 |
| unsw_iotraffic_edges_30s | 77102 | 0 | 2016-09-30 19:30:00+00:00 | 2016-10-31 23:46:30+00:00 | 34.63 |
| unsw_iotraffic_edges_30s_from_v2 | 77102 | 0 | 2016-09-30 19:30:00+00:00 | 2016-10-31 23:46:30+00:00 | 100.0 |

## cicapt_iiot
- unique_edges: 6
- unique_edge_pairs_proto_window: 9
- new_peer_edges: 6
- protocols: 1
- time_order_violations: 0
- attack_labels: 6
- benign_labels: 2
- lateral_movement_labels: 4
- unknown_category_labels: 0
- label_distribution: {'lateral_movement|attack=True': 4, 'benign|attack=False': 2, 'discovery|attack=True': 1, 'command_and_control|attack=True': 1}

## x_iiotid
- unique_edges: 35
- unique_edge_pairs_proto_window: 1118
- new_peer_edges: 29
- protocols: 3
- time_order_violations: 0
- attack_labels: 701
- benign_labels: 27
- lateral_movement_labels: 77
- unknown_category_labels: 47
- label_distribution: {'dos|attack=True': 235, 'discovery|attack=True': 183, 'credential_access|attack=True': 91, 'lateral_movement|attack=True': 77, 'exfiltration|attack=True': 54, 'unknown|attack=True': 47, 'benign|attack=False': 27, 'injection|attack=True': 13, 'mitm|attack=True': 1}

## unsw_iotraffic
- unique_edges: 79
- unique_edge_pairs_proto_window: 77102
- new_peer_edges: 75
- protocols: 3
- time_order_violations: 0
- attack_labels: 0
- benign_labels: 0
- lateral_movement_labels: 0
- unknown_category_labels: 0
- label_distribution: {}

## v0.2 tables (authoritative)

| table | rows | duplicate rows | max null % |
|---|---:|---:|---:|
| assets/cicapt_iiot | 6 | 0 | 100.0 |
| assets/unsw_iotraffic | 63 | 0 | 100.0 |
| assets/x_iiotid | 29 | 0 | 100.0 |
| asset_identifiers/cicapt_iiot | 10 | 0 | 100.0 |
| asset_identifiers/unsw_iotraffic | 63 | 0 | 100.0 |
| asset_identifiers/x_iiotid | 29 | 0 | 100.0 |
| relationships/cicapt_iiot | 6 | 0 | 100.0 |
| relationships/unsw_iotraffic | 74 | 0 | 100.0 |
| relationships/x_iiotid | 29 | 0 | 100.0 |
| communication_observations/cicapt_iiot_obs_30s | 13 | 0 | 100.0 |
| communication_observations/unsw_iotraffic_obs_30s | 98747 | 0 | 100.0 |
| communication_observations/x_iiotid_obs_30s | 1566 | 0 | 100.0 |
| edge_features/cicapt_iiot_30s | 9 | 0 | 0.0 |
| edge_features/unsw_iotraffic_30s | 67885 | 0 | 0.0 |
| edge_features/x_iiotid_30s | 1118 | 0 | 0.0 |
| graph_events/cicapt_iiot | 39 | 0 | 66.67 |
| graph_events/unsw_iotraffic | 197593 | 0 | 99.94 |
| graph_events/x_iiotid | 3176 | 0 | 98.17 |
