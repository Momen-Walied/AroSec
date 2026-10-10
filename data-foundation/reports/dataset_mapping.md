# Dataset Mapping

How each external dataset maps onto the v0.1 contracts. Column mappings marked
**(verified)** were confirmed by inspecting the actual downloaded files; others are
from official documentation and will be confirmed when the gated files are provided.

Canonical target tables: `Asset`, `CommunicationEdge`, `GraphEvent`, `AttackLabel`,
`Campaign`, `NodeFeatureWindow`, `EdgeFeatureWindow` (see
`docs/CYBER_GRAPH_DATA_CONTRACT_V0.1.md`).

---

## CICAPT-IIoT 2024 `cicapt_iiot`

Access: registration form (manual). Adapter `src/datasets/cicapt.py`.

| External artifact | External fields | Canonical target | Notes |
|---|---|---|---|
| Network CSV (pcap2csv output) | timestamp, src/dst IP, src/dst port, protocol, length | `RawObservation` → `CommunicationEdge` | column names resolved via `src/datasets/columns.py` aliases |
| `Attack_info.csv` | attack time, PID, category (tactic), technique | `AttackLabel` + `Campaign` | label-only observations; campaign `phase2` |
| Provenance CSV (nodes) | 32-digit node id, node type (Process/Artifact/file/dir/socket/link) | `Asset` (extra) | `asset_type=process` for Process nodes |
| Provenance CSV (edges) | Used / WasGeneratedBy / WasTriggeredBy / WasDerivedFrom | *not mapped to COMMUNICATES_WITH in v0.1* | provenance edges are not network facts; retained in interim |

Status: **MANUAL_DOWNLOAD_REQUIRED**. A synthetic CICAPT-shaped fixture
(`tests/fixtures/cicapt_scenario.csv`) drives the end-to-end demo.

---

## X-IIoTID 2021 `x_iiotid`

Access: IEEE DataPort / Kaggle login (manual). Adapter `src/datasets/xiiotid.py`.
Schema below **(verified)** against the CC BY 4.0 Zenodo derivative (1,672 rows, 68 columns).

| External column | Canonical field |
|---|---|
| `Timestamp` (epoch) / `Date` | `RawObservation.timestamp` |
| `Scr_IP`, `Scr_port` | `src_ip`, `src_port` |
| `Des_IP`, `Des_port` | `dst_ip`, `dst_port` |
| `Protocol` | `network_protocol` (upper) |
| `Service` | `application_protocol` (upper) |
| `Scr_bytes` / `Des_bytes` | `bytes_out` / `bytes_in` |
| `Scr_pkts` + `Des_pkts` (else `total_packet`) | `packet_count` |
| `class1` | `AttackLabel.original_label` |
| `class2` | `AttackLabel.original_sub_label` |
| `class3` | binary attack/benign decision |

Label levels: `class3` = binary (Normal/Attack), `class2` = sub-category (9 families),
`class1` = sub-subcategory (18 attack names + Normal).

---

## UNSW-IoTraffic 2025 `unsw_iotraffic`

Access: open (Dryad; anti-bot challenge). Adapter `src/datasets/unsw_iotraffic.py`.
Schema below **(verified)** against the downloaded `flows.zip` (4,944,068 rows, 27 device files).

| External column | Canonical field |
|---|---|
| `time` | `RawObservation.timestamp` (parsed as UTC datetime) |
| `srcIp`, `dstIp` | `src_ip`, `dst_ip` |
| `srcPort`, `dstPort` | `src_port`, `dst_port` |
| `ipProto` (6/17/1/2) | `network_protocol` (TCP/UDP/ICMP/IGMP) |
| `protocol` | `application_protocol` (dns/ntp/http/tls/... ) |
| `srcPayloadSize` / `dstPayloadSize` | `bytes_out` / `bytes_in` |
| `srcNumPackets` + `dstNumPackets` | `packet_count` |
| `srcMac`, `dstMac` | `src_mac`, `dst_mac` — **all `null` in practice** → identity is IP-based |

No labels (normal-behaviour dataset). Device identity (`DeviceName_DeviceMAC`) is in the
filename; because MACs are null in the flows it is not attachable to endpoints in v0.1.

---

## Secondary / optional

| Dataset | Adapter | Access |
|---|---|---|
| Edge-IIoTset | `src/datasets/edge_iiotset.py` (generic CSV) | Kaggle login; not downloaded |
| CICIoT2023 | `src/datasets/ciciot2023.py` (generic CSV) | UNB registration; not downloaded |

Both use `canonicalize_flow_frame` so a provided CSV auto-maps by column aliases.

---

## Unified label mapping

`src/normalization/label_map.py`. MITRE technique IDs are mapped directly; otherwise
keyword rules apply. Anything unrecognized → `attack_category=unknown` with
`original_label` preserved (never silently dropped).

| External label (example) | attack_category | attack_stage | is_lateral_movement |
|---|---|---|---|
| `Lateral Movement` / `T1021` | lateral_movement | lateral_movement | true |
| `Discovery` / `Reconnaissance` / `T1016` | discovery | discovery | false |
| `Credential Access` / `T1552` | credential_access | credential_access | false |
| `Command and Control` / `T1105` | command_and_control | command_and_control | false |
| `Collection` / `T1005` | collection | collection | false |
| `Exfiltration` / `T1041` | exfiltration | exfiltration | false |
| `Persistence` / `T1546` | persistence | persistence | false |
| `Defence Evasion` / `T1036` | defense_evasion | defense_evasion | false |
| `DDoS` | ddos | impact | false |
| `DoS` | dos | impact | false |
| `MitM` | mitm | collection | false |
| `SQL injection` / `XSS` | injection | execution | false |
| `benign` / `Normal` | benign | unknown | false |
| *(unrecognized)* | unknown | unknown | false |

---

## v0.2 mapping (authoritative)

v0.2 keeps the same `RawObservation` adapter contract; only shared normalization changes.
Every adapter feeds `TwoPhaseResolver` → `canonical_records` → v0.2 tables.

| v0.1 target | v0.2 target | Change |
|---|---|---|
| `Asset` | `Asset` (+ `identity_evidence`, `evidence_id`, `source_record_id`) | adds identity evidence |
| — | `AssetIdentifierObservation` | new: time-bounded identity bindings |
| `CommunicationEdge` | `CommunicationRelationship` + `CommunicationObservation` | split + lossless proto/port |
| `EdgeFeatureWindow` | `EdgeFeatureWindowV2` | + distributions, observed ports, novelty counts/ratios |
| `GraphEvent` | `GraphEvent` (+ new types) | IDENTITY_BINDING_*/RELATIONSHIP_*/COMMUNICATION_OBSERVED |

Column → v0.2 field for the three worked datasets is unchanged at the adapter boundary
(`src/datasets/*`), because adapters emit `RawObservation` only.

