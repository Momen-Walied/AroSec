"""Report + contract-document generation.

Field tables are produced by introspecting the pydantic contracts (single source
of truth) and merging curated definitions/examples keyed by ``Model.field``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

from src.config import get_settings
from src.datasets.registry import load_registry
from src.schemas import (
    Asset,
    AttackLabel,
    Campaign,
    CommunicationEdge,
    EdgeFeatureWindow,
    GraphEvent,
    NodeFeatureWindow,
)
from src.schemas.v2 import (
    AssetIdentifierObservation,
    CommunicationObservation,
    CommunicationRelationship,
    EdgeFeatureWindowV2,
)
from src.validation.checks import edge_quality_extras, render_data_quality_md, validate_dataset_dir

CONTRACT_MODELS: list[type[BaseModel]] = [
    Asset, CommunicationEdge, GraphEvent, AttackLabel, Campaign, EdgeFeatureWindow, NodeFeatureWindow,
]

CONTRACT_MODELS_V2: list[type[BaseModel]] = [
    Asset, AssetIdentifierObservation, CommunicationRelationship, CommunicationObservation,
    EdgeFeatureWindowV2, GraphEvent, AttackLabel, Campaign,
]

V2_FIELD_META: dict[str, dict[str, str]] = {
    "AssetIdentifierObservation.asset_id": {"definition": "Owning asset.", "source": "resolver", "example": "asset:unsw:192.168.1.240", "notes": "time-bounded binding."},
    "AssetIdentifierObservation.identifier_type": {"definition": "Identifier kind.", "source": "resolver", "example": "ip", "notes": "mac/ip/hostname/device_id/serial/other."},
    "AssetIdentifierObservation.identifier_value": {"definition": "Identifier value.", "source": "raw", "example": "192.168.1.240", "notes": ""},
    "AssetIdentifierObservation.valid_from": {"definition": "Binding start.", "source": "observed", "example": "2016-09-30T19:30:02Z", "notes": "UTC."},
    "AssetIdentifierObservation.valid_to": {"definition": "Binding end.", "source": "observed", "example": "2016-10-31T23:46:30Z", "notes": "UTC."},
    "AssetIdentifierObservation.evidence_source": {"definition": "Provenance.", "source": "adapter", "example": "unsw_iotraffic:flows", "notes": ""},
    "AssetIdentifierObservation.confidence": {"definition": "Binding confidence.", "source": "derived", "example": "0.4", "notes": "mac 0.9, ip 0.4."},
    "AssetIdentifierObservation.evidence_id": {"definition": "Evidence ref.", "source": "adapter", "example": None, "notes": "optional."},
    "AssetIdentifierObservation.source_record_id": {"definition": "Source record ref.", "source": "adapter", "example": None, "notes": "never fabricated."},
    "AssetIdentifierObservation.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "unsw_iotraffic", "notes": ""},

    "CommunicationRelationship.relationship_id": {"definition": "Stable logical edge id (window-independent).", "source": "derived", "example": "rel:asset:a|asset:b|COMMUNICATES_WITH", "notes": "does not depend on window."},
    "CommunicationRelationship.src_asset_id": {"definition": "Source asset.", "source": "resolver", "example": "asset:unsw:192.168.1.240", "notes": ""},
    "CommunicationRelationship.dst_asset_id": {"definition": "Destination asset.", "source": "resolver", "example": "asset:unsw:23.23.189.20", "notes": ""},
    "CommunicationRelationship.relationship_type": {"definition": "Graph relationship.", "source": "fixed", "example": "COMMUNICATES_WITH", "notes": "facts only."},
    "CommunicationRelationship.first_seen": {"definition": "First observation of the relationship.", "source": "derived", "example": "2016-09-30T19:30:00Z", "notes": "UTC."},
    "CommunicationRelationship.last_seen": {"definition": "Last observation of the relationship.", "source": "derived", "example": "2016-10-31T23:46:30Z", "notes": "UTC."},
    "CommunicationRelationship.total_observation_count": {"definition": "Distinct time windows observed.", "source": "derived", "example": "12", "notes": "distinct window_start values."},
    "CommunicationRelationship.total_connection_count": {"definition": "Total connections ever.", "source": "derived", "example": "540", "notes": "sum across observations."},
    "CommunicationRelationship.direction": {"definition": "Observed direction.", "source": "derived", "example": "outbound", "notes": ""},
    "CommunicationRelationship.evidence_sources": {"definition": "Provenance.", "source": "adapter", "example": "[\"unsw_iotraffic:flows\"]", "notes": ""},
    "CommunicationRelationship.evidence_id": {"definition": "Evidence ref.", "source": "adapter", "example": None, "notes": "optional."},
    "CommunicationRelationship.source_record_id": {"definition": "Source record ref.", "source": "adapter", "example": None, "notes": "optional."},
    "CommunicationRelationship.confidence": {"definition": "Fact confidence.", "source": "derived", "example": "1.0", "notes": ""},
    "CommunicationRelationship.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "unsw_iotraffic", "notes": ""},

    "CommunicationObservation.observation_id": {"definition": "Deterministic observation id.", "source": "derived", "example": "obs:9ba381741a54d7e6e74c", "notes": "over rel/window/proto/app/ports."},
    "CommunicationObservation.relationship_id": {"definition": "FK to relationship.", "source": "derived", "example": "rel:...", "notes": ""},
    "CommunicationObservation.src_asset_id": {"definition": "Source asset.", "source": "resolver", "example": "asset:...", "notes": ""},
    "CommunicationObservation.dst_asset_id": {"definition": "Destination asset.", "source": "resolver", "example": "asset:...", "notes": ""},
    "CommunicationObservation.window_start": {"definition": "Window start.", "source": "derived", "example": "2016-09-30T19:30:00Z", "notes": "UTC, half-open."},
    "CommunicationObservation.window_end": {"definition": "Window end.", "source": "derived", "example": "2016-09-30T19:30:30Z", "notes": "exclusive."},
    "CommunicationObservation.network_protocol": {"definition": "L3/L4 protocol.", "source": "raw", "example": "TCP", "notes": "part of the identity; never collapsed."},
    "CommunicationObservation.application_protocol": {"definition": "L7 protocol.", "source": "raw", "example": "TLS", "notes": "part of the identity; never collapsed."},
    "CommunicationObservation.src_port": {"definition": "Source port.", "source": "raw", "example": "51240", "notes": "never collapsed."},
    "CommunicationObservation.dst_port": {"definition": "Destination port.", "source": "raw", "example": "443", "notes": "never collapsed (no min())."},
    "CommunicationObservation.connection_count": {"definition": "Connections in this bucket.", "source": "raw", "example": "2", "notes": "fact."},
    "CommunicationObservation.packet_count": {"definition": "Packets in this bucket.", "source": "raw", "example": "40", "notes": "fact."},
    "CommunicationObservation.bytes_out": {"definition": "Out bytes.", "source": "raw", "example": "1200", "notes": ""},
    "CommunicationObservation.bytes_in": {"definition": "In bytes.", "source": "raw", "example": "300", "notes": ""},
    "CommunicationObservation.direction": {"definition": "Direction.", "source": "derived", "example": "bidirectional", "notes": ""},
    "CommunicationObservation.evidence_source": {"definition": "Provenance.", "source": "adapter", "example": "unsw_iotraffic:flows", "notes": ""},
    "CommunicationObservation.evidence_id": {"definition": "Evidence ref.", "source": "adapter", "example": None, "notes": "optional."},
    "CommunicationObservation.source_record_id": {"definition": "Source record ref.", "source": "adapter", "example": None, "notes": "optional."},
    "CommunicationObservation.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "unsw_iotraffic", "notes": ""},

    "EdgeFeatureWindowV2.relationship_id": {"definition": "Relationship ref.", "source": "derived", "example": "rel:...", "notes": ""},
    "EdgeFeatureWindowV2.src_asset_id": {"definition": "Source asset.", "source": "derived", "example": "asset:...", "notes": ""},
    "EdgeFeatureWindowV2.dst_asset_id": {"definition": "Destination asset.", "source": "derived", "example": "asset:...", "notes": ""},
    "EdgeFeatureWindowV2.window_start": {"definition": "Window start.", "source": "derived", "example": "2016-09-30T19:30:00Z", "notes": ""},
    "EdgeFeatureWindowV2.window_end": {"definition": "Window end.", "source": "derived", "example": "2016-09-30T19:30:30Z", "notes": ""},
    "EdgeFeatureWindowV2.connections_count": {"definition": "Connections in window.", "source": "derived", "example": "4", "notes": "fact."},
    "EdgeFeatureWindowV2.packet_count": {"definition": "Packets in window.", "source": "derived", "example": "80", "notes": "fact."},
    "EdgeFeatureWindowV2.outbound_bytes": {"definition": "Out bytes.", "source": "derived", "example": "2400", "notes": ""},
    "EdgeFeatureWindowV2.inbound_bytes": {"definition": "In bytes.", "source": "derived", "example": "600", "notes": ""},
    "EdgeFeatureWindowV2.protocol_distribution": {"definition": "Connections per network protocol.", "source": "derived", "example": "{TCP:3,UDP:1}", "notes": "denominator = connections_count."},
    "EdgeFeatureWindowV2.application_protocol_distribution": {"definition": "Connections per app protocol.", "source": "derived", "example": "{TLS:2,DNS:1}", "notes": "denominator = connections_count."},
    "EdgeFeatureWindowV2.observed_destination_ports": {"definition": "Distinct dst ports.", "source": "derived", "example": "[53,443,445]", "notes": "sorted; lossless."},
    "EdgeFeatureWindowV2.observed_source_ports": {"definition": "Distinct src ports.", "source": "derived", "example": "[51240]", "notes": "sorted."},
    "EdgeFeatureWindowV2.unique_destination_ports": {"definition": "Number of distinct dst ports.", "source": "derived", "example": "3", "notes": ""},
    "EdgeFeatureWindowV2.unique_source_ports": {"definition": "Number of distinct src ports.", "source": "derived", "example": "1", "notes": ""},
    "EdgeFeatureWindowV2.relationship_age_seconds": {"definition": "Age at window_start.", "source": "derived", "example": "86400.0", "notes": "no leakage."},
    "EdgeFeatureWindowV2.historical_connection_count": {"definition": "Connections strictly before window.", "source": "derived", "example": "12", "notes": "no leakage."},
    "EdgeFeatureWindowV2.new_peer": {"definition": "First window of the relationship.", "source": "derived", "example": "true", "notes": "no leakage."},
    "EdgeFeatureWindowV2.src_unique_peer_count": {"definition": "Distinct dst peers before window.", "source": "derived", "example": "2", "notes": "no leakage."},
    "EdgeFeatureWindowV2.src_new_peer_count": {"definition": "New dst peers in window.", "source": "derived", "example": "1", "notes": "no leakage."},
    "EdgeFeatureWindowV2.protocol_novelty_count": {"definition": "Protocols in window not seen before on the relationship.", "source": "derived", "example": "1", "notes": "no leakage."},
    "EdgeFeatureWindowV2.protocol_novelty_ratio": {"definition": "novelty_count / distinct protocols in window.", "source": "derived", "example": "1.0", "notes": "denominator = distinct protocols in window."},
    "EdgeFeatureWindowV2.port_novelty_count": {"definition": "Dst ports in window not seen before on the relationship.", "source": "derived", "example": "19", "notes": "no leakage."},
    "EdgeFeatureWindowV2.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "unsw_iotraffic", "notes": ""},
}


FIELD_META: dict[str, dict[str, str]] = {
    "Asset.asset_id": {"definition": "Stable identity. Never a bare IP.", "source": "identity resolver", "example": "asset:cicapt:mac-44650d56ccd3", "notes": "Precedence MAC>hostname>device>ip."},
    "Asset.asset_type": {"definition": "Node kind.", "source": "dataset / inference", "example": "camera", "notes": "unknown if not evidenced."},
    "Asset.asset_type_confidence": {"definition": "Confidence in asset_type.", "source": "derived", "example": "0.0", "notes": "0 unless evidenced."},
    "Asset.ip_addresses": {"definition": "Observed IPs.", "source": "flows", "example": "[10.0.0.21]", "notes": "IP is an observation, not identity."},
    "Asset.mac_addresses": {"definition": "Observed MACs.", "source": "flows", "example": "[44:65:0d:56:cc:d3]", "notes": "Often null (e.g. UNSW)."},
    "Asset.hostname": {"definition": "Host/device name.", "source": "dataset", "example": "cam-01", "notes": "null if absent."},
    "Asset.vendor": {"definition": "Vendor.", "source": "dataset", "example": None, "notes": "never fabricated."},
    "Asset.vlan_id": {"definition": "VLAN.", "source": "dataset", "example": None, "notes": "null in v0.1 unless explicit."},
    "Asset.subnet": {"definition": "Subnet.", "source": "dataset", "example": None, "notes": "null in v0.1 unless explicit."},
    "Asset.criticality": {"definition": "Business criticality.", "source": "manual", "example": "unknown", "notes": "not inferred in v0.1."},
    "Asset.first_seen": {"definition": "Earliest observation.", "source": "flows", "example": "2024-03-01T02:13:00Z", "notes": "UTC."},
    "Asset.last_seen": {"definition": "Latest observation.", "source": "flows", "example": "2024-03-02T02:16:00Z", "notes": "UTC."},
    "Asset.identity_confidence": {"definition": "Identity strength.", "source": "resolver", "example": "0.95", "notes": "ip_only=0.30."},
    "Asset.identity_method": {"definition": "How identity was derived.", "source": "resolver", "example": "mac_pinned", "notes": "dataset_derived/ip_only are provisional."},
    "Asset.evidence_sources": {"definition": "Provenance of the record.", "source": "adapter", "example": "[\"unsw_iotraffic:flows\"]", "notes": "always preserved."},
    "Asset.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},

    "CommunicationEdge.edge_id": {"definition": "Stable edge key.", "source": "derived", "example": "edge:asset:a|asset:b|COMMUNICATES_WITH|TCP", "notes": "over src,dst,relationship,protocol."},
    "CommunicationEdge.src_asset_id": {"definition": "Initiator asset.", "source": "resolver", "example": "asset:cicapt:host-cam-01", "notes": ""},
    "CommunicationEdge.dst_asset_id": {"definition": "Responder asset.", "source": "resolver", "example": "asset:cicapt:host-nvr-01", "notes": ""},
    "CommunicationEdge.relationship_type": {"definition": "Graph relationship.", "source": "fixed", "example": "COMMUNICATES_WITH", "notes": "only fact-based types."},
    "CommunicationEdge.direction": {"definition": "Direction.", "source": "derived", "example": "outbound", "notes": ""},
    "CommunicationEdge.network_protocol": {"definition": "L3/L4 protocol.", "source": "flows", "example": "TCP", "notes": ""},
    "CommunicationEdge.application_protocol": {"definition": "L7 protocol.", "source": "flows", "example": "SMB", "notes": "null if none."},
    "CommunicationEdge.src_port": {"definition": "Initiator port.", "source": "flows", "example": "51240", "notes": ""},
    "CommunicationEdge.dst_port": {"definition": "Responder port.", "source": "flows", "example": "445", "notes": ""},
    "CommunicationEdge.window_start": {"definition": "Aggregation window start.", "source": "derived", "example": "2024-03-02T02:14:00Z", "notes": "UTC."},
    "CommunicationEdge.window_end": {"definition": "Aggregation window end.", "source": "derived", "example": "2024-03-02T02:14:30Z", "notes": "UTC."},
    "CommunicationEdge.connection_count": {"definition": "Connections in window.", "source": "flows", "example": "2", "notes": "fact."},
    "CommunicationEdge.packet_count": {"definition": "Packets in window.", "source": "flows", "example": "63", "notes": "fact."},
    "CommunicationEdge.bytes_out": {"definition": "Initiator->responder bytes.", "source": "flows", "example": "11300", "notes": "fact."},
    "CommunicationEdge.bytes_in": {"definition": "Responder->initiator bytes.", "source": "flows", "example": "3000", "notes": "fact."},
    "CommunicationEdge.first_seen": {"definition": "Pair first ever seen (<= window).", "source": "derived", "example": "2024-03-01T02:13:00Z", "notes": "no leakage."},
    "CommunicationEdge.last_seen": {"definition": "Latest seen up to this window.", "source": "derived", "example": "2024-03-02T02:14:20Z", "notes": "no leakage."},
    "CommunicationEdge.historical_connection_count": {"definition": "Connections strictly before window.", "source": "derived", "example": "5", "notes": "no leakage."},
    "CommunicationEdge.is_new_peer": {"definition": "First window this pair appears.", "source": "derived", "example": "true", "notes": "no leakage."},
    "CommunicationEdge.evidence_sources": {"definition": "Provenance.", "source": "adapter", "example": "[\"cicapt_iiot:network\"]", "notes": ""},
    "CommunicationEdge.confidence": {"definition": "Fact confidence.", "source": "derived", "example": "1.0", "notes": ""},
    "CommunicationEdge.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},

    "GraphEvent.event_id": {"definition": "Deterministic event key.", "source": "derived", "example": "evt:1a2b3c...", "notes": ""},
    "GraphEvent.timestamp": {"definition": "Event time.", "source": "derived", "example": "2024-03-02T02:14:00Z", "notes": "UTC."},
    "GraphEvent.event_type": {"definition": "Event kind.", "source": "derived", "example": "EDGE_ADDED", "notes": "ASSET_ADDED/EDGE_UPDATED/..."},
    "GraphEvent.asset_id": {"definition": "Asset ref (asset events).", "source": "derived", "example": "asset:cicapt:host-cam-01", "notes": ""},
    "GraphEvent.edge_id": {"definition": "Edge ref (edge events).", "source": "derived", "example": "edge:...", "notes": ""},
    "GraphEvent.src_asset_id": {"definition": "Edge source ref.", "source": "derived", "example": "asset:...", "notes": ""},
    "GraphEvent.dst_asset_id": {"definition": "Edge dest ref.", "source": "derived", "example": "asset:...", "notes": ""},
    "GraphEvent.graph_version": {"definition": "Monotonic version.", "source": "derived", "example": "12", "notes": "enables point-in-time view."},
    "GraphEvent.evidence_source": {"definition": "Provenance.", "source": "adapter", "example": "cicapt_iiot:network", "notes": ""},
    "GraphEvent.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},

    "AttackLabel.is_attack": {"definition": "Attack vs benign.", "source": "dataset", "example": "true", "notes": ""},
    "AttackLabel.attack_category": {"definition": "Unified category.", "source": "label map", "example": "lateral_movement", "notes": "unknown if unmapped."},
    "AttackLabel.attack_stage": {"definition": "MITRE-style stage.", "source": "label map", "example": "lateral_movement", "notes": ""},
    "AttackLabel.technique": {"definition": "Technique id/name.", "source": "dataset", "example": "T1021", "notes": "preserved when present."},
    "AttackLabel.is_lateral_movement": {"definition": "Lateral-movement flag.", "source": "label map", "example": "true", "notes": ""},
    "AttackLabel.campaign_id": {"definition": "Campaign ref.", "source": "dataset", "example": "campaign:cicapt_iiot:phase2", "notes": "null if none."},
    "AttackLabel.ground_truth_confidence": {"definition": "Mapping confidence.", "source": "label map", "example": "0.95", "notes": "<1 signals uncertainty."},
    "AttackLabel.original_label": {"definition": "Raw source label.", "source": "dataset", "example": "Lateral Movement", "notes": "always preserved."},
    "AttackLabel.original_sub_label": {"definition": "Raw sub-label.", "source": "dataset", "example": "Reconnaissance", "notes": "always preserved."},
    "AttackLabel.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "x_iiotid", "notes": ""},
    "AttackLabel.src_asset_id": {"definition": "Label source ref.", "source": "derived", "example": "asset:...", "notes": ""},
    "AttackLabel.dst_asset_id": {"definition": "Label dest ref.", "source": "derived", "example": "asset:...", "notes": ""},
    "AttackLabel.edge_id": {"definition": "Label edge ref.", "source": "derived", "example": None, "notes": ""},
    "AttackLabel.event_time": {"definition": "Label time.", "source": "dataset", "example": "2024-03-02T02:14:00Z", "notes": ""},

    "Campaign.campaign_id": {"definition": "Campaign key.", "source": "derived", "example": "campaign:cicapt_iiot:phase2", "notes": ""},
    "Campaign.start_time": {"definition": "Campaign start.", "source": "dataset", "example": None, "notes": "UTC."},
    "Campaign.end_time": {"definition": "Campaign end.", "source": "dataset", "example": None, "notes": "UTC."},
    "Campaign.entry_asset_id": {"definition": "Entry asset.", "source": "dataset", "example": None, "notes": "only if labeled."},
    "Campaign.affected_asset_ids": {"definition": "Affected assets.", "source": "dataset", "example": "[]", "notes": ""},
    "Campaign.observed_path": {"definition": "Ordered path steps.", "source": "derived", "example": "[]", "notes": "typed steps."},
    "Campaign.attack_stages": {"definition": "Observed stages.", "source": "dataset", "example": "[\"discovery\"]", "notes": ""},
    "Campaign.probable_target_asset_id": {"definition": "Probable target.", "source": "ground truth", "example": None, "notes": "null unless labeled."},
    "Campaign.probable_objective": {"definition": "Probable objective.", "source": "ground truth", "example": None, "notes": "NO inference in v0.1."},
    "Campaign.ground_truth_available": {"definition": "Ground truth present.", "source": "dataset", "example": "true", "notes": ""},
    "Campaign.confidence": {"definition": "Confidence.", "source": "derived", "example": "1.0", "notes": ""},
    "Campaign.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},

    "EdgeFeatureWindow.src_asset_id": {"definition": "Edge source.", "source": "derived", "example": "asset:...", "notes": ""},
    "EdgeFeatureWindow.dst_asset_id": {"definition": "Edge dest.", "source": "derived", "example": "asset:...", "notes": ""},
    "EdgeFeatureWindow.window_start": {"definition": "Window start.", "source": "derived", "example": "2024-03-02T02:14:00Z", "notes": ""},
    "EdgeFeatureWindow.window_end": {"definition": "Window end.", "source": "derived", "example": "2024-03-02T02:14:30Z", "notes": ""},
    "EdgeFeatureWindow.connections_count": {"definition": "Connections in window.", "source": "derived", "example": "2", "notes": "fact."},
    "EdgeFeatureWindow.packet_count": {"definition": "Packets in window.", "source": "derived", "example": "63", "notes": "fact."},
    "EdgeFeatureWindow.outbound_bytes": {"definition": "Out bytes.", "source": "derived", "example": "11300", "notes": ""},
    "EdgeFeatureWindow.inbound_bytes": {"definition": "In bytes.", "source": "derived", "example": "3000", "notes": ""},
    "EdgeFeatureWindow.unique_destination_ports": {"definition": "Distinct dst ports in window.", "source": "derived", "example": "1", "notes": "approx (min-port rows)."},
    "EdgeFeatureWindow.edge_age_seconds": {"definition": "Age at window_start.", "source": "derived", "example": "86400.0", "notes": "no leakage."},
    "EdgeFeatureWindow.historical_connection_count": {"definition": "Connections before window.", "source": "derived", "example": "5", "notes": "no leakage."},
    "EdgeFeatureWindow.new_peer": {"definition": "First-ever pair window.", "source": "derived", "example": "true", "notes": "no leakage."},
    "EdgeFeatureWindow.src_unique_peer_count": {"definition": "Distinct peers before window.", "source": "derived", "example": "1", "notes": "no leakage."},
    "EdgeFeatureWindow.src_new_peer_count": {"definition": "New peers discovered in window.", "source": "derived", "example": "1", "notes": "no leakage."},
    "EdgeFeatureWindow.protocol_novelty": {"definition": "Protocol first seen for pair.", "source": "derived", "example": "true", "notes": "no leakage."},
    "EdgeFeatureWindow.time_of_day_frequency": {"definition": "Share of history at this hour.", "source": "derived", "example": "0.0", "notes": "no leakage."},
    "EdgeFeatureWindow.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},

    "NodeFeatureWindow.asset_id": {"definition": "Asset.", "source": "derived", "example": "asset:...", "notes": ""},
    "NodeFeatureWindow.window_start": {"definition": "Window start.", "source": "derived", "example": "2024-03-02T02:14:00Z", "notes": ""},
    "NodeFeatureWindow.window_end": {"definition": "Window end.", "source": "derived", "example": "2024-03-02T02:14:30Z", "notes": ""},
    "NodeFeatureWindow.connection_count": {"definition": "Outbound connections in window.", "source": "derived", "example": "2", "notes": ""},
    "NodeFeatureWindow.unique_destination_ips": {"definition": "Distinct dest IPs.", "source": "derived", "example": "1", "notes": ""},
    "NodeFeatureWindow.unique_destination_assets": {"definition": "Distinct dest assets.", "source": "derived", "example": "1", "notes": ""},
    "NodeFeatureWindow.new_peer_count": {"definition": "New peers this window.", "source": "derived", "example": "1", "notes": "no leakage."},
    "NodeFeatureWindow.unique_destination_ports": {"definition": "Distinct dest ports.", "source": "derived", "example": "1", "notes": ""},
    "NodeFeatureWindow.outbound_bytes": {"definition": "Out bytes.", "source": "derived", "example": "11300", "notes": ""},
    "NodeFeatureWindow.inbound_bytes": {"definition": "In bytes.", "source": "derived", "example": "3000", "notes": ""},
    "NodeFeatureWindow.packet_count": {"definition": "Packets.", "source": "derived", "example": "63", "notes": ""},
    "NodeFeatureWindow.fan_out": {"definition": "Distinct dest assets in window.", "source": "derived", "example": "1", "notes": ""},
    "NodeFeatureWindow.protocol_count": {"definition": "Distinct protocols.", "source": "derived", "example": "1", "notes": ""},
    "NodeFeatureWindow.dns_query_rate": {"definition": "DNS conns per second.", "source": "derived", "example": "0.0", "notes": "null if no port info."},
    "NodeFeatureWindow.failed_connection_ratio": {"definition": "Failed conn ratio.", "source": "derived", "example": None, "notes": "null in v0.1 (not available)."},
    "NodeFeatureWindow.dataset_source": {"definition": "Originating dataset.", "source": "adapter", "example": "cicapt_iiot", "notes": ""},
}


def _type_str(annotation: object) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))
    args = ", ".join(_type_str(a) for a in get_args(annotation))
    return f"{getattr(origin, '__name__', origin)}[{args}]"


def _field_table(model: type[BaseModel]) -> str:
    lines = ["| Field | Type | Required? | Definition | Source | Example | Notes |", "|---|---|---|---|---|---|---|"]
    for name, field in model.model_fields.items():
        meta = FIELD_META.get(f"{model.__name__}.{name}") or V2_FIELD_META.get(f"{model.__name__}.{name}", {})
        example = meta.get("example")
        example = "`null`" if example is None else f"`{example}`"
        lines.append(
            f"| `{name}` | {_type_str(field.annotation)} | "
            f"{'yes' if field.is_required() else 'no'} | {meta.get('definition','-')} | "
            f"{meta.get('source','-')} | {example} | {meta.get('notes','')} |"
        )
    return "\n".join(lines)


def generate_contract_md(out_path: Path) -> Path:
    parts = [
        "# Cyber Graph Data Contract v0.1",
        "",
        "Normative contract for the Vigilance temporal cyber graph. Implemented as strict",
        "pydantic v2 models in `src/schemas/` (`extra='forbid'`). This document is generated",
        "from those models — the models are the source of truth.",
        "",
        "## Global rules",
        "",
        "- Timestamps are UTC. Missing values are `null`; nothing is fabricated.",
        "- `asset_id` is stable and is never a bare IP.",
        "- `CommunicationEdge` carries FACTS only. AI scores are FORBIDDEN here",
        "  (`attack_probability`, `lateral_movement_probability`, `edge_anomaly_score`, `malicious_probability`).",
        "- Novelty/history features use observations strictly before the window (no future leakage).",
        "- Unknown external labels become `attack_category=unknown` and keep `original_label`.",
        "",
    ]
    for model in CONTRACT_MODELS:
        parts.append(f"## {model.__name__}")
        if model.__doc__:
            parts.append("")
            parts.append(model.__doc__.strip())
        parts.append("")
        parts.append(_field_table(model))
        parts.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def generate_schema_spec_md(out_path: Path) -> Path:
    parts = ["# Schema Specification v0.1", "", "Summary of the seven contracts and their key invariants.", ""]
    invariants = {
        "Asset": "asset_id != bare IP; MAC>hostname>device>IP identity precedence.",
        "CommunicationEdge": "FACTS only; forbidden AI fields rejected; window/first/last ordering enforced.",
        "GraphEvent": "Append-only; monotonic graph_version; event_type requires matching refs.",
        "AttackLabel": "is_attack consistent with attack_category; original labels preserved.",
        "Campaign": "No inferred objective/target when ground_truth_available is false.",
        "EdgeFeatureWindow": "All history fields computed strictly before window_start.",
        "NodeFeatureWindow": "Outbound-centric aggregates; leakage-safe novelty fields.",
    }
    parts.append("| Contract | Fields | Key invariants |")
    parts.append("|---|---:|---|")
    for model in CONTRACT_MODELS:
        parts.append(f"| {model.__name__} | {len(model.model_fields)} | {invariants.get(model.__name__,'')} |")
    parts.append("")
    parts.append("See `docs/CYBER_GRAPH_DATA_CONTRACT_V0.1.md` for the full field tables.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def generate_registry_md(out_path: Path) -> Path:
    registry = load_registry()
    settings = get_settings()
    manifest = {}
    manifest_path = settings.processed_dir / "build_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")).get("builds", {})
    lines = ["# Dataset Registry", "", f"_Generated {datetime.now(UTC).isoformat()}_", ""]
    lines.append("| dataset | year | access | status | pcap | flows | labels | stages | lateral | provenance | time | size |")
    lines.append("|---|---:|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|---|")
    for ds in registry.ids():
        r = registry.get(ds)
        def b(x):
            return "Y" if x is True else ("~" if x == "partial" else "N")
        lines.append(
            f"| {r.dataset_id} | {r.year or '-'} | {r.download_access or '-'} | {r.status} | "
            f"{b(r.contains_pcap)} | {b(r.contains_flows)} | {b(r.contains_labels)} | {b(r.contains_attack_stage)} | "
            f"{b(r.contains_lateral_movement)} | {b(r.contains_provenance)} | {r.time_information_quality or '-'} | {r.estimated_download_size or '-'} |"
        )
    lines.append("")
    lines.append("## Build manifest (normalized outputs)")
    lines.append("")
    if manifest:
        lines.append("| dataset:window | raw obs | assets | edges | labels | campaigns | events | node feats | edge feats |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for key, entry in sorted(manifest.items()):
            lines.append(
                f"| {key} | {entry.get('raw_observation_count',0)} | {entry.get('assets',0)} | {entry.get('edges',0)} | "
                f"{entry.get('labels',0)} | {entry.get('campaigns',0)} | {entry.get('events',0)} | "
                f"{entry.get('node_features',0)} | {entry.get('edge_features',0)} |"
            )
    else:
        lines.append("_No builds yet. Run `python -m src.cli datasets normalize --all`._")
    v2_manifest_path = settings.processed_dir / "v2" / "build_manifest_v2.json"
    lines.append("")
    lines.append("## v0.2 build manifest (authoritative)")
    lines.append("")
    if v2_manifest_path.exists():
        v2 = json.loads(v2_manifest_path.read_text(encoding="utf-8")).get("builds", {})
        lines.append("| dataset:window | raw | assets | bindings | relationships | observations | pair-windows | events |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for key, entry in sorted(v2.items()):
            lines.append(
                f"| {key} | {entry.get('observations_raw',0)} | {entry.get('assets',0)} | "
                f"{entry.get('identity_bindings',0)} | {entry.get('relationships',0)} | "
                f"{entry.get('communication_observations',0)} | {entry.get('edge_feature_windows',0)} | "
                f"{entry.get('events',0)} |"
            )
    else:
        lines.append("_No v0.2 builds yet. Run `python -m src.cli build-v2 --all`._")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def generate_data_quality_md(out_path: Path) -> Path:
    from src.normalization import io
    from src.schemas import AttackLabel, CommunicationEdge

    settings = get_settings()
    registry = load_registry()
    extras: dict[str, dict] = {}
    from src.validation.checks import ValidationReport

    merged = ValidationReport()
    for ds in registry.ids():
        r = validate_dataset_dir(ds, settings)
        merged.tables.extend(r.tables)
        merged.schema_errors.extend(r.schema_errors)
        edges, labels = [], []
        for path in sorted((settings.processed_dir / "communication_edges").glob(f"{ds}_edges_*.parquet")):
            edges = io.frame_to_models(io.read_parquet(path), CommunicationEdge)
        lp = settings.processed_dir / "labels" / f"{ds}.parquet"
        if lp.exists():
            labels = io.frame_to_models(io.read_parquet(lp), AttackLabel)
        if r.tables:
            extras[ds] = edge_quality_extras(edges, labels)
    md = render_data_quality_md(merged, extras)
    v2_dir = settings.processed_dir / "v2"
    if v2_dir.exists():
        from src.validation.checks import _table_quality

        md += "\n## v0.2 tables (authoritative)\n\n"
        md += "| table | rows | duplicate rows | max null % |\n|---|---:|---:|---:|\n"
        for sub in ("assets", "asset_identifiers", "relationships", "communication_observations",
                    "edge_features", "graph_events"):
            for path in sorted((v2_dir / sub).glob("*.parquet")):
                df = io.read_parquet(path)
                q = _table_quality(f"{sub}/{path.stem}", df,
                                   ["first_seen", "last_seen", "window_start", "window_end", "timestamp"])
                max_null = max(q.null_pct.values()) if q.null_pct else 0.0
                md += f"| {q.name} | {q.rows} | {q.duplicate_rows} | {max_null} |\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    return out_path


def generate_contract_v2_md(out_path: Path) -> Path:
    parts = [
        "# Cyber Graph Data Contract v0.2",
        "",
        "Authoritative temporal-cyber-graph contract. Additive over v0.1 (v0.1 remains",
        "available; see `docs/V0.1_TO_V0.2_MIGRATION.md`). Generated from the pydantic models",
        "in `src/schemas/` — the models are the source of truth.",
        "",
        "## Global rules",
        "",
        "- Timestamps are UTC. Missing values are `null`; nothing is fabricated.",
        "- `CommunicationObservation` is LOSSLESS for (network_protocol, application_protocol,",
        "  src_port, dst_port) — distinct protocols/ports are never collapsed.",
        "- `CommunicationRelationship` is the persistent logical edge; `relationship_id` is",
        "  window-independent and stable.",
        "- `AssetIdentifierObservation` binds identifiers to assets for a time interval; IP reuse",
        "  over disjoint intervals does NOT merge unrelated devices.",
        "- `IDENTITY_BINDING_EXPIRED` is emitted only when the same identifier is next bound to a",
        "  DIFFERENT asset (identifier handover) — not at mere last-seen.",
        "- `CommunicationEdge` (v0.1) is retained as a compatibility view and is LOSSY.",
        "- Novelty/history features use observations strictly before the window (no leakage).",
        "",
    ]
    for model in CONTRACT_MODELS_V2:
        parts.append(f"## {model.__name__}")
        if model.__doc__:
            parts.append("")
            parts.append(model.__doc__.strip())
        parts.append("")
        parts.append(_field_table(model))
        parts.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def generate_v0_2_validation_md(out_path: Path) -> Path:
    from src.validation.checks_v2 import validate_v2_dataset

    settings = get_settings()
    registry = load_registry()
    rows = []
    for ds in registry.ids():
        if (settings.processed_dir / "v2" / "assets" / f"{ds}.parquet").exists():
            rows.append(validate_v2_dataset(ds, "30s", settings))
    lines = ["# v0.2 Validation", ""]
    if not rows:
        lines.append("_No v0.2 builds yet. Run `python -m src.cli build-v2 --all`._")
    else:
        lines.append("| dataset | assets | bindings | relationships | observations | pair-windows | "
                     "multi-proto % | multi-port % | ports lost under v0.1 | leakage | schema errors |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            lines.append(
                f"| {r['dataset_id']} | {r['tables'].get('assets', 0)} | {r['tables'].get('asset_identifiers', 0)} | "
                f"{r['tables'].get('relationships', 0)} | {r['tables'].get('observations', 0)} | {r.get('pair_windows', 0)} | "
                f"{r.get('pct_multi_protocol_pair_windows', 0)} | {r.get('pct_multi_port_pair_windows', 0)} | "
                f"{r.get('ports_lost_under_v01', 0)} | {r.get('temporal_leakage_violations', 0)} | "
                f"{len(r.get('schema_errors', []))} |"
            )
        lines.append("")
        lines.append("## Identity-method distribution")
        for r in rows:
            lines.append(f"### {r['dataset_id']}")
            for method, count in sorted(r.get("identity_method_distribution", {}).items()):
                lines.append(f"- {method}: {count}")
            lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def generate_all() -> list[Path]:
    settings = get_settings()
    reports = settings.reports_dir
    docs = settings.processed_dir.parent.parent / "docs"
    outputs = [
        generate_registry_md(reports / "dataset_registry.md"),
        generate_schema_spec_md(reports / "schema_specification.md"),
        generate_data_quality_md(reports / "data_quality.md"),
        generate_contract_md(docs / "CYBER_GRAPH_DATA_CONTRACT_V0.1.md"),
        generate_contract_v2_md(docs / "CYBER_GRAPH_DATA_CONTRACT_V0.2.md"),
        generate_v0_2_validation_md(reports / "v0.2_validation.md"),
    ]
    return outputs
