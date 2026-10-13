# Node Behavior v1 — Feature Design

> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`.

## Audit of the existing `NodeFeatureWindow`

The v0.1 `NodeFeatureWindow` is **outbound-centric**: it has `connection_count`, `unique_destination_assets`, `new_peer_count`, `unique_destination_ports`, `fan_out`, `outbound_bytes`, `protocol_count` — but **no inbound behavior** (no incoming peers/fan-in, no inbound protocol/port diversity, no peer-set change or relationship-creation rate). `dns_query_rate` and `failed_connection_ratio` are unavailable in the source data (null).

**Conclusion: V2 required.** `NodeFeatureWindowV2` (AI layer, above the frozen contract) models both directions symmetrically and adds novelty/change features.

## NodeFeatureWindowV2 fields

| field | type |
|---|---|
| `schema_version` | str |
| `asset_id` | str |
| `window_start` | datetime |
| `window_end` | datetime |
| `outgoing_connection_count` | int |
| `incoming_connection_count` | int |
| `outgoing_packet_count` | int |
| `incoming_packet_count` | int |
| `outgoing_bytes` | int |
| `incoming_bytes` | int |
| `unique_outgoing_peers` | int |
| `unique_incoming_peers` | int |
| `new_outgoing_peer_count` | int |
| `new_incoming_peer_count` | int |
| `unique_outgoing_ports` | int |
| `unique_incoming_ports` | int |
| `outbound_protocol_count` | int |
| `inbound_protocol_count` | int |
| `outbound_app_protocol_count` | int |
| `inbound_app_protocol_count` | int |
| `protocol_novelty_count` | int |
| `port_novelty_count` | int |
| `fan_out` | int |
| `fan_in` | int |
| `relationship_creation_count` | int |
| `dataset_source` | SourceDataset |

## Model features (node_features_v1)

`log_out_conn`, `log_out_bytes`, `log_out_packets`, `log_in_conn`, `log_in_bytes`, `log_in_packets`, `out_in_conn_ratio`, `out_in_bytes_ratio`, `log_out_peers`, `log_in_peers`, `log_fan_out`, `log_fan_in`, `log_new_out_peers`, `log_new_in_peers`, `peer_set_change_rate`, `log_rel_creation`, `log_out_ports`, `log_in_ports`, `log_port_novelty`, `out_protocols`, `in_protocols`, `protocol_novelty_count`, `app_protocol_diversity`

Causality: peers/protocols/ports novelty use only windows strictly before the current window; scalers fit on TRAIN only; thresholds from VALIDATION only.

