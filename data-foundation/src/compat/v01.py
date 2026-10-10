"""v0.1 compatibility views.

Reproduces the legacy ``CommunicationEdge`` interface from authoritative v0.2
tables. This interface is LOSSY for multi-protocol / multi-port pair-windows
(destination port = min observed; application protocol = lexicographically first)
and is NOT the authoritative graph representation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from src.schemas.base import Direction, RelationshipType, SourceDataset
from src.schemas.communication_edge import CommunicationEdge
from src.schemas.v2 import CommunicationObservation, CommunicationRelationship


def to_v01_edges(
    relationships: list[CommunicationRelationship],
    observations: list[CommunicationObservation],
    source: SourceDataset,
    window_seconds: int = 30,
) -> list[CommunicationEdge]:
    groups: dict[tuple, dict] = {}
    for o in observations:
        proto = o.network_protocol or "NA"
        key = (o.src_asset_id, o.dst_asset_id, proto, o.window_start)
        g = groups.get(key)
        if g is None:
            g = {"conn": 0, "packets": 0, "out": 0, "in": 0, "apps": set(), "dst_ports": set()}
            groups[key] = g
        g["conn"] += o.connection_count
        g["packets"] += o.packet_count
        g["out"] += o.bytes_out
        g["in"] += o.bytes_in
        if o.application_protocol:
            g["apps"].add(o.application_protocol)
        if o.dst_port is not None:
            g["dst_ports"].add(o.dst_port)

    rows = sorted(
        ((src, dst, proto, wstart, g) for (src, dst, proto, wstart), g in groups.items()),
        key=lambda r: (r[3], r[0], r[1], r[2]),
    )

    pair_first_window: dict[tuple[str, str], object] = {}
    for src, dst, _proto, wstart, _g in rows:
        key = (src, dst)
        if key not in pair_first_window or wstart < pair_first_window[key]:
            pair_first_window[key] = wstart

    running_conn: dict[tuple[str, str], int] = defaultdict(int)
    running_last: dict[tuple[str, str], object] = {}
    seen: dict[tuple[str, str], bool] = {}

    edges: list[CommunicationEdge] = []
    index = 0
    while index < len(rows):
        src, dst, _proto, wstart, g = rows[index]
        pair = (src, dst)
        end = index
        group_last = wstart + timedelta(seconds=window_seconds)
        while end < len(rows) and rows[end][0] == src and rows[end][1] == dst and rows[end][3] == wstart:
            group_last = max(group_last, rows[end][3] + timedelta(seconds=window_seconds))
            end += 1
        first_seen = pair_first_window[pair]
        historical = running_conn[pair]
        is_new = not seen.get(pair, False)
        prev = running_last.get(pair)
        last_seen = max(prev, group_last) if prev else group_last

        group_conn = 0
        for k in range(index, end):
            _s, _d, proto_k, _ws, gk = rows[k]
            out = int(gk["out"])
            inn = int(gk["in"])
            if out > 0 and inn > 0:
                direction = Direction.BIDIRECTIONAL
            elif inn > 0:
                direction = Direction.INBOUND
            else:
                direction = Direction.OUTBOUND
            apps = sorted(gk["apps"])
            edges.append(CommunicationEdge(
                edge_id=f"edge:{src}|{dst}|{RelationshipType.COMMUNICATES_WITH.value}|{proto_k}",
                src_asset_id=src, dst_asset_id=dst,
                relationship_type=RelationshipType.COMMUNICATES_WITH,
                direction=direction,
                network_protocol=proto_k,
                application_protocol=apps[0] if apps else None,
                dst_port=min(gk["dst_ports"]) if gk["dst_ports"] else None,
                window_start=wstart, window_end=wstart + timedelta(seconds=window_seconds),
                connection_count=int(gk["conn"]), packet_count=int(gk["packets"]),
                bytes_out=out, bytes_in=inn,
                first_seen=first_seen, last_seen=last_seen,
                historical_connection_count=historical, is_new_peer=is_new,
                evidence_sources=[f"{source.value}:v01compat"],
                dataset_source=source,
            ))
            group_conn += int(gk["conn"])
        running_conn[pair] += group_conn
        running_last[pair] = last_seen
        seen[pair] = True
        index = end

    edges.sort(key=lambda e: (e.window_start, e.src_asset_id, e.dst_asset_id, e.network_protocol or ""))
    return edges
