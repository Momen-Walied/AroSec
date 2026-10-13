# Offline / Online Feature Parity

Comparison of `build_edge_features_v2` (offline) vs `OnlineFeatureBuilder` (online)
over the same chronological CommunicationObservation sequence.

- offline windows: 67885
- online windows: 67885
- missing in online: 0
- extra in online: 0
- **total field mismatches: 0**
- comparison time: 2.8s

## Field mismatch counts

| field | mismatches |
|---|---:|
| connections_count | 0 |
| packet_count | 0 |
| outbound_bytes | 0 |
| inbound_bytes | 0 |
| protocol_distribution | 0 |
| application_protocol_distribution | 0 |
| observed_destination_ports | 0 |
| observed_source_ports | 0 |
| unique_destination_ports | 0 |
| unique_source_ports | 0 |
| relationship_age_seconds | 0 |
| historical_connection_count | 0 |
| new_peer | 0 |
| src_unique_peer_count | 0 |
| src_new_peer_count | 0 |
| protocol_novelty_count | 0 |
| protocol_novelty_ratio | 0 |
| port_novelty_count | 0 |

Intentional difference (documented): `relationship_age_seconds` uses the first
observed *window_start* online (CommunicationObservation carries window boundaries,
not raw packet timestamps). Against the windowed offline reference it matches exactly;
against training-time features the offset is bounded by one window (0 for the first window).

