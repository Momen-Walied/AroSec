"""Neo4j CSV export (nodes.csv / relationships.csv).

Temporal properties (first_seen, last_seen, window_*) are retained on edges so
the graph stays time-aware downstream.
"""
from __future__ import annotations

import csv
from pathlib import Path

from src.schemas import Asset, CommunicationEdge

NODE_HEADER = [
    "id:ID", ":LABEL", "asset_id", "asset_type", "identity_method",
    "identity_confidence", "ip_addresses", "mac_addresses", "hostname",
    "first_seen", "last_seen", "dataset_source",
]
REL_HEADER = [
    ":START_ID", ":END_ID", ":TYPE", "edge_id", "network_protocol",
    "application_protocol", "connection_count", "packet_count", "bytes_out",
    "bytes_in", "window_start", "window_end", "first_seen", "last_seen",
    "historical_connection_count", "is_new_peer",
]


def export_neo4j_csv(
    assets: list[Asset],
    edges: list[CommunicationEdge],
    out_dir: Path,
    prefix: str | None = None,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}_" if prefix else ""
    nodes_path = out_dir / f"{stem}nodes.csv"
    rels_path = out_dir / f"{stem}relationships.csv"

    with open(nodes_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(NODE_HEADER)
        for a in assets:
            writer.writerow([
                a.asset_id, "Asset", a.asset_id, a.asset_type, a.identity_method,
                a.identity_confidence, "|".join(a.ip_addresses), "|".join(a.mac_addresses),
                a.hostname or "", a.first_seen.isoformat() if a.first_seen else "",
                a.last_seen.isoformat() if a.last_seen else "", a.dataset_source,
            ])

    with open(rels_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(REL_HEADER)
        for e in edges:
            writer.writerow([
                e.src_asset_id, e.dst_asset_id, e.relationship_type, e.edge_id,
                e.network_protocol or "", e.application_protocol or "",
                e.connection_count, e.packet_count, e.bytes_out, e.bytes_in,
                e.window_start.isoformat(), e.window_end.isoformat(),
                e.first_seen.isoformat(), e.last_seen.isoformat(),
                e.historical_connection_count, str(e.is_new_peer).lower(),
            ])
    return nodes_path, rels_path
