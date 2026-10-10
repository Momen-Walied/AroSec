# Cyber Graph Data Contract v0.1

Normative contract for the Vigilance temporal cyber graph. Implemented as strict
pydantic v2 models in `src/schemas/` (`extra='forbid'`). This document is generated
from those models — the models are the source of truth.

## Global rules

- Timestamps are UTC. Missing values are `null`; nothing is fabricated.
- `asset_id` is stable and is never a bare IP.
- `CommunicationEdge` carries FACTS only. AI scores are FORBIDDEN here
  (`attack_probability`, `lateral_movement_probability`, `edge_anomaly_score`, `malicious_probability`).
- Novelty/history features use observations strictly before the window (no future leakage).
- Unknown external labels become `attack_category=unknown` and keep `original_label`.

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

## CommunicationEdge

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `edge_id` | str | yes | Stable edge key. | derived | `edge:asset:a|asset:b|COMMUNICATES_WITH|TCP` | over src,dst,relationship,protocol. |
| `src_asset_id` | str | yes | Initiator asset. | resolver | `asset:cicapt:host-cam-01` |  |
| `dst_asset_id` | str | yes | Responder asset. | resolver | `asset:cicapt:host-nvr-01` |  |
| `relationship_type` | RelationshipType | no | Graph relationship. | fixed | `COMMUNICATES_WITH` | only fact-based types. |
| `direction` | Direction | no | Direction. | derived | `outbound` |  |
| `network_protocol` | UnionType[str, NoneType] | no | L3/L4 protocol. | flows | `TCP` |  |
| `application_protocol` | UnionType[str, NoneType] | no | L7 protocol. | flows | `SMB` | null if none. |
| `src_port` | UnionType[int, NoneType] | no | Initiator port. | flows | `51240` |  |
| `dst_port` | UnionType[int, NoneType] | no | Responder port. | flows | `445` |  |
| `window_start` | datetime | yes | Aggregation window start. | derived | `2024-03-02T02:14:00Z` | UTC. |
| `window_end` | datetime | yes | Aggregation window end. | derived | `2024-03-02T02:14:30Z` | UTC. |
| `connection_count` | int | no | Connections in window. | flows | `2` | fact. |
| `packet_count` | int | no | Packets in window. | flows | `63` | fact. |
| `bytes_out` | int | no | Initiator->responder bytes. | flows | `11300` | fact. |
| `bytes_in` | int | no | Responder->initiator bytes. | flows | `3000` | fact. |
| `first_seen` | datetime | yes | Pair first ever seen (<= window). | derived | `2024-03-01T02:13:00Z` | no leakage. |
| `last_seen` | datetime | yes | Latest seen up to this window. | derived | `2024-03-02T02:14:20Z` | no leakage. |
| `historical_connection_count` | int | no | Connections strictly before window. | derived | `5` | no leakage. |
| `is_new_peer` | bool | no | First window this pair appears. | derived | `true` | no leakage. |
| `evidence_sources` | list[str] | no | Provenance. | adapter | `["cicapt_iiot:network"]` |  |
| `confidence` | float | no | Fact confidence. | derived | `1.0` |  |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |

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

## EdgeFeatureWindow

Per (src,dst) edge behaviour for one aggregation window.

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `src_asset_id` | str | yes | Edge source. | derived | `asset:...` |  |
| `dst_asset_id` | str | yes | Edge dest. | derived | `asset:...` |  |
| `window_start` | datetime | yes | Window start. | derived | `2024-03-02T02:14:00Z` |  |
| `window_end` | datetime | yes | Window end. | derived | `2024-03-02T02:14:30Z` |  |
| `connections_count` | int | no | Connections in window. | derived | `2` | fact. |
| `packet_count` | int | no | Packets in window. | derived | `63` | fact. |
| `outbound_bytes` | int | no | Out bytes. | derived | `11300` |  |
| `inbound_bytes` | int | no | In bytes. | derived | `3000` |  |
| `unique_destination_ports` | int | no | Distinct dst ports in window. | derived | `1` | approx (min-port rows). |
| `edge_age_seconds` | UnionType[float, NoneType] | no | Age at window_start. | derived | `86400.0` | no leakage. |
| `historical_connection_count` | int | no | Connections before window. | derived | `5` | no leakage. |
| `new_peer` | bool | no | First-ever pair window. | derived | `true` | no leakage. |
| `src_unique_peer_count` | int | no | Distinct peers before window. | derived | `1` | no leakage. |
| `src_new_peer_count` | int | no | New peers discovered in window. | derived | `1` | no leakage. |
| `protocol_novelty` | bool | no | Protocol first seen for pair. | derived | `true` | no leakage. |
| `time_of_day_frequency` | UnionType[float, NoneType] | no | Share of history at this hour. | derived | `0.0` | no leakage. |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |

## NodeFeatureWindow

Per-asset behaviour for one aggregation window (outbound-centric).

| Field | Type | Required? | Definition | Source | Example | Notes |
|---|---|---|---|---|---|---|
| `schema_version` | str | no | - | - | `null` |  |
| `asset_id` | str | yes | Asset. | derived | `asset:...` |  |
| `window_start` | datetime | yes | Window start. | derived | `2024-03-02T02:14:00Z` |  |
| `window_end` | datetime | yes | Window end. | derived | `2024-03-02T02:14:30Z` |  |
| `connection_count` | int | no | Outbound connections in window. | derived | `2` |  |
| `unique_destination_ips` | int | no | Distinct dest IPs. | derived | `1` |  |
| `unique_destination_assets` | int | no | Distinct dest assets. | derived | `1` |  |
| `new_peer_count` | int | no | New peers this window. | derived | `1` | no leakage. |
| `unique_destination_ports` | int | no | Distinct dest ports. | derived | `1` |  |
| `outbound_bytes` | int | no | Out bytes. | derived | `11300` |  |
| `inbound_bytes` | int | no | In bytes. | derived | `3000` |  |
| `packet_count` | int | no | Packets. | derived | `63` |  |
| `fan_out` | int | no | Distinct dest assets in window. | derived | `1` |  |
| `protocol_count` | int | no | Distinct protocols. | derived | `1` |  |
| `dns_query_rate` | UnionType[float, NoneType] | no | DNS conns per second. | derived | `0.0` | null if no port info. |
| `failed_connection_ratio` | UnionType[float, NoneType] | no | Failed conn ratio. | derived | `null` | null in v0.1 (not available). |
| `dataset_source` | SourceDataset | yes | Originating dataset. | adapter | `cicapt_iiot` |  |
