# Cyber Graph Data Contract v0.2

Authoritative temporal-cyber-graph contract. Additive over v0.1 (v0.1 remains
available; see `docs/V0.1_TO_V0.2_MIGRATION.md`). Generated from the pydantic models
in `src/schemas/` — the models are the source of truth.

## Global rules

- Timestamps are UTC. Missing values are `null`; nothing is fabricated.
- `CommunicationObservation` is LOSSLESS for (network_protocol, application_protocol,
  src_port, dst_port) — distinct protocols/ports are never collapsed.
- `CommunicationRelationship` is the persistent logical edge; `relationship_id` is
  window-independent and stable.
- `AssetIdentifierObservation` binds identifiers to assets for a time interval; IP reuse
  over disjoint intervals does NOT merge unrelated devices.
- `IDENTITY_BINDING_EXPIRED` is emitted only when the same identifier is next bound to a
  DIFFERENT asset (identifier handover) — not at mere last-seen.
- `CommunicationEdge` (v0.1) is retained as a compatibility view and is LOSSY.
- Novelty/history features use observations strictly before the window (no leakage).

## Asset

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `asset_id` | str | yes | Stable identity. Never a bare IP. | identity resolver | `asset:cicapt:mac-44650d56ccd3` | Precedence MAC>hostname>device>ip. |
| `asset_type` | AssetType | no | Node kind. | dataset / inference | `camera` | unknown if not evidenced. |
| `asset_type_confidence` | float | no | Confidence in asset_type. | derived | `0.0` | 0 unless evidenced. |
| `ip_addresses` | list[str] | no | Observed IPs. | flows | `[10.0.0.21]` | IP is an observation, not identity. |
| `mac_addresses` | list[str] | no | Observed MACs. | flows | `[44:65:0d:56:cc:d3]` | Often null (e.g. UNSW). |
| `hostname` | UnionType[str, NoneType] | no | Host/device name. | dataset | `cam-01` | null if absent. |
| `vendor` | UnionType[str, NoneType] | no | Vendor. | dataset | `null` | never fabricated. |
| `vlan_id` | UnionType[int, NoneType] | no | VLAN. | dataset | `null` | null in v0.1 unless explicit. |
| `subnet` | UnionType[str, NoneType] | no | Subnet. | dataset | `null` | null in v0.1 unless explicit. |
| `criticality` | Criticality | no | Business criticality. | manual | `unknown` | not inferred in v0.1. |
| `first_seen` | UnionType[datetime, NoneType] | no | Earliest observation. | flows | `2024-03-01T02:13:00Z` | UTC. |
| `last_seen` | UnionType[datetime, NoneType] | no | Latest observation. | flows | `2024-03-02T02:16:00Z` | UTC. |
| `identity_confidence` | float | no | Identity strength. | resolver | `0.95` | ip_only=0.30. |
| `identity_method` | IdentityMethod | no | How identity was derived. | resolver | `mac_pinned` | dataset_derived/ip_only are provisional. |
| `identity_evidence` | list[str] | no | - | - | `null` |  |
| `evidence_sources` | list[str] | no | Provenance of the record. | adapter | `["unsw_iotraffic:flows"]` | always preserved. |
| `evidence_id` | UnionType[str, NoneType] | no | - | - | `null` |  |
| `source_record_id` | UnionType[str, NoneType] | no | - | - | `null` |  |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |

## AssetIdentifierObservation

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `asset_id` | str | yes | Owning asset. | resolver | `asset:unsw:192.168.1.240` | time-bounded binding. |
| `identifier_type` | IdentifierType | yes | Identifier kind. | resolver | `ip` | mac/ip/hostname/device_id/serial/other. |
| `identifier_value` | str | yes | Identifier value. | raw | `192.168.1.240` |  |
| `valid_from` | UnionType[datetime, NoneType] | no | Binding start. | observed | `2016-09-30T19:30:02Z` | UTC. |
| `valid_to` | UnionType[datetime, NoneType] | no | Binding end. | observed | `2016-10-31T23:46:30Z` | UTC. |
| `evidence_source` | str | yes | Provenance. | adapter | `unsw_iotraffic:flows` |  |
| `confidence` | float | no | Binding confidence. | derived | `0.4` | mac 0.9, ip 0.4. |
| `evidence_id` | UnionType[str, NoneType] | no | Evidence ref. | adapter | `null` | optional. |
| `source_record_id` | UnionType[str, NoneType] | no | Source record ref. | adapter | `null` | never fabricated. |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `unsw_iotraffic` |  |

## CommunicationRelationship

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `relationship_id` | str | yes | Stable logical edge id (window-independent). | derived | `rel:asset:a|asset:b|COMMUNICATES_WITH` | does not depend on window. |
| `src_asset_id` | str | yes | Source asset. | resolver | `asset:unsw:192.168.1.240` |  |
| `dst_asset_id` | str | yes | Destination asset. | resolver | `asset:unsw:23.23.189.20` |  |
| `relationship_type` | RelationshipType | no | Graph relationship. | fixed | `COMMUNICATES_WITH` | facts only. |
| `first_seen` | datetime | yes | First observation of the relationship. | derived | `2016-09-30T19:30:00Z` | UTC. |
| `last_seen` | datetime | yes | Last observation of the relationship. | derived | `2016-10-31T23:46:30Z` | UTC. |
| `total_observation_count` | int | no | Distinct time windows observed. | derived | `12` | distinct window_start values. |
| `total_connection_count` | int | no | Total connections ever. | derived | `540` | sum across observations. |
| `direction` | Direction | no | Observed direction. | derived | `outbound` |  |
| `evidence_sources` | list[str] | no | Provenance. | adapter | `["unsw_iotraffic:flows"]` |  |
| `evidence_id` | UnionType[str, NoneType] | no | Evidence ref. | adapter | `null` | optional. |
| `source_record_id` | UnionType[str, NoneType] | no | Source record ref. | adapter | `null` | optional. |
| `confidence` | float | no | Fact confidence. | derived | `1.0` |  |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `unsw_iotraffic` |  |

## CommunicationObservation

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `observation_id` | str | yes | Deterministic observation id. | derived | `obs:9ba381741a54d7e6e74c` | over rel/window/proto/app/ports. |
| `relationship_id` | str | yes | FK to relationship. | derived | `rel:...` |  |
| `src_asset_id` | str | yes | Source asset. | resolver | `asset:...` |  |
| `dst_asset_id` | str | yes | Destination asset. | resolver | `asset:...` |  |
| `window_start` | datetime | yes | Window start. | derived | `2016-09-30T19:30:00Z` | UTC, half-open. |
| `window_end` | datetime | yes | Window end. | derived | `2016-09-30T19:30:30Z` | exclusive. |
| `network_protocol` | UnionType[str, NoneType] | no | L3/L4 protocol. | raw | `TCP` | part of the identity; never collapsed. |
| `application_protocol` | UnionType[str, NoneType] | no | L7 protocol. | raw | `TLS` | part of the identity; never collapsed. |
| `src_port` | UnionType[int, NoneType] | no | Source port. | raw | `51240` | never collapsed. |
| `dst_port` | UnionType[int, NoneType] | no | Destination port. | raw | `443` | never collapsed (no min()). |
| `connection_count` | int | no | Connections in this bucket. | raw | `2` | fact. |
| `packet_count` | int | no | Packets in this bucket. | raw | `40` | fact. |
| `bytes_out` | int | no | Out bytes. | raw | `1200` |  |
| `bytes_in` | int | no | In bytes. | raw | `300` |  |
| `direction` | Direction | no | Direction. | derived | `bidirectional` |  |
| `evidence_source` | str | no | Provenance. | adapter | `unsw_iotraffic:flows` |  |
| `evidence_id` | UnionType[str, NoneType] | no | Evidence ref. | adapter | `null` | optional. |
| `source_record_id` | UnionType[str, NoneType] | no | Source record ref. | adapter | `null` | optional. |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `unsw_iotraffic` |  |

## EdgeFeatureWindowV2

Wide, leakage-safe edge features per (relationship, window).

    Distribution denominators:
      * protocol_distribution[p] / application_protocol_distribution[a]
          -> share is value / connections_count (this window).
      * protocol_novelty_ratio = protocol_novelty_count / distinct protocols in window.
    All history/novelty fields use observations STRICTLY before window_start.

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `relationship_id` | str | yes | Relationship ref. | derived | `rel:...` |  |
| `src_asset_id` | str | yes | Source asset. | derived | `asset:...` |  |
| `dst_asset_id` | str | yes | Destination asset. | derived | `asset:...` |  |
| `window_start` | datetime | yes | Window start. | derived | `2016-09-30T19:30:00Z` |  |
| `window_end` | datetime | yes | Window end. | derived | `2016-09-30T19:30:30Z` |  |
| `connections_count` | int | no | Connections in window. | derived | `4` | fact. |
| `packet_count` | int | no | Packets in window. | derived | `80` | fact. |
| `outbound_bytes` | int | no | Out bytes. | derived | `2400` |  |
| `inbound_bytes` | int | no | In bytes. | derived | `600` |  |
| `protocol_distribution` | dict[str, int] | no | Connections per network protocol. | derived | `{TCP:3,UDP:1}` | denominator = connections_count. |
| `application_protocol_distribution` | dict[str, int] | no | Connections per app protocol. | derived | `{TLS:2,DNS:1}` | denominator = connections_count. |
| `observed_destination_ports` | list[int] | no | Distinct dst ports. | derived | `[53,443,445]` | sorted; lossless. |
| `observed_source_ports` | list[int] | no | Distinct src ports. | derived | `[51240]` | sorted. |
| `unique_destination_ports` | int | no | Number of distinct dst ports. | derived | `3` |  |
| `unique_source_ports` | int | no | Number of distinct src ports. | derived | `1` |  |
| `relationship_age_seconds` | UnionType[float, NoneType] | no | Age at window_start. | derived | `86400.0` | no leakage. |
| `historical_connection_count` | int | no | Connections strictly before window. | derived | `12` | no leakage. |
| `new_peer` | bool | no | First window of the relationship. | derived | `true` | no leakage. |
| `src_unique_peer_count` | int | no | Distinct dst peers before window. | derived | `2` | no leakage. |
| `src_new_peer_count` | int | no | New dst peers in window. | derived | `1` | no leakage. |
| `protocol_novelty_count` | int | no | Protocols in window not seen before on the relationship. | derived | `1` | no leakage. |
| `protocol_novelty_ratio` | UnionType[float, NoneType] | no | novelty_count / distinct protocols in window. | derived | `1.0` | denominator = distinct protocols in window. |
| `port_novelty_count` | int | no | Dst ports in window not seen before on the relationship. | derived | `19` | no leakage. |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `unsw_iotraffic` |  |

## GraphEvent

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `event_id` | str | yes | Deterministic event key. | derived | `evt:1a2b3c...` |  |
| `timestamp` | datetime | yes | Event time. | derived | `2024-03-02T02:14:00Z` | UTC. |
| `event_type` | GraphEventType | yes | Event kind. | derived | `EDGE_ADDED` | ASSET_ADDED/EDGE_UPDATED/... |
| `asset_id` | UnionType[str, NoneType] | no | Asset ref (asset events). | derived | `asset:cicapt:host-cam-01` |  |
| `edge_id` | UnionType[str, NoneType] | no | Edge ref (edge events). | derived | `edge:...` |  |
| `observation_id` | UnionType[str, NoneType] | no | - | - | `null` |  |
| `src_asset_id` | UnionType[str, NoneType] | no | Edge source ref. | derived | `asset:...` |  |
| `dst_asset_id` | UnionType[str, NoneType] | no | Edge dest ref. | derived | `asset:...` |  |
| `graph_version` | int | no | Monotonic version. | derived | `12` | enables point-in-time view. |
| `evidence_source` | str | no | Provenance. | adapter | `cicapt_iiot:network` |  |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |

## AttackLabel

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `is_attack` | bool | yes | Attack vs benign. | dataset | `true` |  |
| `attack_category` | AttackCategory | no | Unified category. | label map | `lateral_movement` | unknown if unmapped. |
| `attack_stage` | AttackStage | no | MITRE-style stage. | label map | `lateral_movement` |  |
| `technique` | UnionType[str, NoneType] | no | Technique id/name. | dataset | `T1021` | preserved when present. |
| `is_lateral_movement` | bool | no | Lateral-movement flag. | label map | `true` |  |
| `campaign_id` | UnionType[str, NoneType] | no | Campaign ref. | dataset | `campaign:cicapt_iiot:phase2` | null if none. |
| `ground_truth_confidence` | float | no | Mapping confidence. | label map | `0.95` | <1 signals uncertainty. |
| `original_label` | UnionType[str, NoneType] | no | Raw source label. | dataset | `Lateral Movement` | always preserved. |
| `original_sub_label` | UnionType[str, NoneType] | no | Raw sub-label. | dataset | `Reconnaissance` | always preserved. |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `x_iiotid` |  |
| `src_asset_id` | UnionType[str, NoneType] | no | Label source ref. | derived | `asset:...` |  |
| `dst_asset_id` | UnionType[str, NoneType] | no | Label dest ref. | derived | `asset:...` |  |
| `edge_id` | UnionType[str, NoneType] | no | Label edge ref. | derived | `null` |  |
| `event_time` | UnionType[datetime, NoneType] | no | Label time. | dataset | `2024-03-02T02:14:00Z` |  |

## Campaign

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `campaign_id` | str | yes | Campaign key. | derived | `campaign:cicapt_iiot:phase2` |  |
| `start_time` | UnionType[datetime, NoneType] | no | Campaign start. | dataset | `null` | UTC. |
| `end_time` | UnionType[datetime, NoneType] | no | Campaign end. | dataset | `null` | UTC. |
| `entry_asset_id` | UnionType[str, NoneType] | no | Entry asset. | dataset | `null` | only if labeled. |
| `affected_asset_ids` | list[str] | no | Affected assets. | dataset | `[]` |  |
| `observed_path` | list[ObservedPathStep] | no | Ordered path steps. | derived | `[]` | typed steps. |
| `attack_stages` | list[AttackStage] | no | Observed stages. | dataset | `["discovery"]` |  |
| `probable_target_asset_id` | UnionType[str, NoneType] | no | Probable target. | ground truth | `null` | null unless labeled. |
| `probable_objective` | UnionType[str, NoneType] | no | Probable objective. | ground truth | `null` | NO inference in v0.1. |
| `ground_truth_available` | bool | no | Ground truth present. | dataset | `true` |  |
| `confidence` | float | no | Confidence. | derived | `1.0` |  |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |
