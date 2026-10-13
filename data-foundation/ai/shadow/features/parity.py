"""Offline/online EdgeFeatureWindowV2 parity harness.

Offline reference = ``src.normalization.build_v2.build_edge_features_v2`` applied to the
same CommunicationObservation sequence (relationships derived with first_seen = the
relationship's earliest window_start, matching what the online builder can observe).
"""
from __future__ import annotations

from datetime import datetime

from ai.shadow.features.online_builder import OnlineFeatureBuilder
from src.normalization.build_v2 import build_edge_features_v2
from src.schemas.base import SourceDataset
from src.schemas.v2 import CommunicationObservation, CommunicationRelationship, EdgeFeatureWindowV2

COMPARE_FIELDS = [
    "connections_count", "packet_count", "outbound_bytes", "inbound_bytes",
    "protocol_distribution", "application_protocol_distribution",
    "observed_destination_ports", "observed_source_ports",
    "unique_destination_ports", "unique_source_ports",
    "relationship_age_seconds", "historical_connection_count",
    "new_peer", "src_unique_peer_count", "src_new_peer_count",
    "protocol_novelty_count", "protocol_novelty_ratio", "port_novelty_count",
]
FLOAT_TOL = {"relationship_age_seconds": 1e-6, "protocol_novelty_ratio": 1e-9}


def offline_reference(observations: list[CommunicationObservation],
                      source: SourceDataset = SourceDataset.UNSW_IOTRAFFIC) -> list[EdgeFeatureWindowV2]:
    first_seen: dict[str, datetime] = {}
    last_seen: dict[str, datetime] = {}
    src_dst: dict[str, tuple[str, str]] = {}
    for o in observations:
        rel = o.relationship_id
        ws, we = o.window_start, o.window_end
        if rel not in first_seen or ws < first_seen[rel]:
            first_seen[rel] = ws
        if rel not in last_seen or we > last_seen[rel]:
            last_seen[rel] = we
        src_dst[rel] = (o.src_asset_id, o.dst_asset_id)
    relationships = [
        CommunicationRelationship(
            relationship_id=rel, src_asset_id=src_dst[rel][0], dst_asset_id=src_dst[rel][1],
            first_seen=first_seen[rel], last_seen=last_seen[rel],
            dataset_source=source,
        )
        for rel in first_seen
    ]
    return build_edge_features_v2(relationships, observations, source)


def online_reference(observations: list[CommunicationObservation], window_seconds: int = 30,
                     allowed_lateness_seconds: int = 0,
                     source: str = "unsw_iotraffic") -> list[EdgeFeatureWindowV2]:
    builder = OnlineFeatureBuilder(window_seconds, allowed_lateness_seconds,
                                   dataset_source=source)
    ordered = sorted(observations, key=lambda o: (o.window_start, o.observation_id))
    out: list[EdgeFeatureWindowV2] = []
    for o in ordered:
        out.extend(builder.add(o))
    out.extend(builder.flush())
    return out


def _key(w: EdgeFeatureWindowV2) -> tuple[str, str]:
    return (w.window_start.isoformat(), w.relationship_id)


def compare_windows(offline: list[EdgeFeatureWindowV2], online: list[EdgeFeatureWindowV2]) -> dict:
    off = {_key(w): w for w in offline}
    onl = {_key(w): w for w in online}
    report = {
        "offline_windows": len(off),
        "online_windows": len(onl),
        "missing_in_online": len(set(off) - set(onl)),
        "extra_in_online": len(set(onl) - set(off)),
        "field_mismatches": {f: 0 for f in COMPARE_FIELDS},
        "examples": [],
    }
    for key in set(off) & set(onl):
        a, b = off[key], onl[key]
        for f in COMPARE_FIELDS:
            va, vb = getattr(a, f), getattr(b, f)
            if isinstance(va, float) or isinstance(vb, float):
                ok = abs(float(va) - float(vb)) <= FLOAT_TOL.get(f, 1e-9)
            else:
                ok = va == vb
            if not ok:
                report["field_mismatches"][f] += 1
                if len(report["examples"]) < 10:
                    report["examples"].append({"key": key, "field": f, "offline": va, "online": vb})
    report["total_mismatches"] = sum(report["field_mismatches"].values())
    return report


# --------------------------------------------------------------------------- #
# Node Feature parity                                                         #
# --------------------------------------------------------------------------- #
NODE_COMPARE_FIELDS = [
    "outgoing_connection_count", "incoming_connection_count",
    "outgoing_packet_count", "incoming_packet_count",
    "outgoing_bytes", "incoming_bytes",
    "unique_outgoing_peers", "unique_incoming_peers",
    "new_outgoing_peer_count", "new_incoming_peer_count",
    "unique_outgoing_ports", "unique_incoming_ports",
    "outbound_protocol_count", "inbound_protocol_count",
    "outbound_app_protocol_count", "inbound_app_protocol_count",
    "protocol_novelty_count", "port_novelty_count",
    "fan_out", "fan_in", "relationship_creation_count",
]


def offline_node_reference(observations: list[CommunicationObservation]) -> list:
    from ai.node_behavior.features.builder import build_node_feature_windows_v2

    return build_node_feature_windows_v2(observations)


def online_node_reference(observations: list[CommunicationObservation], window_seconds: int = 30,
                          allowed_lateness_seconds: int = 0,
                          source: str = "unsw_iotraffic") -> list:
    from ai.shadow.features.online_node_builder import OnlineNodeFeatureBuilder

    builder = OnlineNodeFeatureBuilder(window_seconds, allowed_lateness_seconds, dataset_source=source)
    ordered = sorted(observations, key=lambda o: (o.window_start, o.observation_id))
    out: list = []
    for o in ordered:
        out.extend(builder.add(o))
    out.extend(builder.flush())
    return out


def _node_key(w) -> tuple[str, str]:
    return (w.window_start.isoformat(), w.asset_id)


def compare_node_windows(offline: list, online: list) -> dict:
    off = {_node_key(w): w for w in offline}
    onl = {_node_key(w): w for w in online}
    report = {"offline_windows": len(off), "online_windows": len(onl),
              "missing_in_online": len(set(off) - set(onl)), "extra_in_online": len(set(onl) - set(off)),
              "field_mismatches": {f: 0 for f in NODE_COMPARE_FIELDS}, "examples": []}
    for key in set(off) & set(onl):
        a, b = off[key], onl[key]
        for f in NODE_COMPARE_FIELDS:
            if getattr(a, f) != getattr(b, f):
                report["field_mismatches"][f] += 1
                if len(report["examples"]) < 10:
                    report["examples"].append({"key": key, "field": f, "offline": getattr(a, f),
                                               "online": getattr(b, f)})
    report["total_mismatches"] = sum(report["field_mismatches"].values())
    return report
