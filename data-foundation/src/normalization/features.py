"""Leakage-safe temporal feature derivation.

For window ``w`` every field is computed from observations strictly BEFORE
``w.window_start`` (novelty/history) or within ``w`` (aggregate counts). Windows
are processed in ascending order; a window's state is only folded in AFTER its
features are computed, so no future observation can influence a past feature.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from src.schemas import Asset, CommunicationEdge, EdgeFeatureWindow, NodeFeatureWindow
from src.schemas.base import SourceDataset


def _hour(ts: datetime) -> int:
    return ts.hour


def build_edge_features(
    edges: list[CommunicationEdge],
    source: SourceDataset,
) -> list[EdgeFeatureWindow]:
    by_window: dict[datetime, list[CommunicationEdge]] = defaultdict(list)
    for edge in edges:
        by_window[edge.window_start].append(edge)
    windows = sorted(by_window)

    seen_dsts: dict[str, set[str]] = defaultdict(set)
    pair_protocols: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_hour_hist: dict[tuple[str, str], Counter] = defaultdict(Counter)
    pair_cum_conn: dict[tuple[str, str], int] = defaultdict(int)

    out: list[EdgeFeatureWindow] = []
    for window_start in windows:
        rows = by_window[window_start]
        window_end = rows[0].window_end
        window_hour = _hour(window_start)

        window_new_peers: dict[str, int] = defaultdict(int)
        for edge in rows:
            src, dst = edge.src_asset_id, edge.dst_asset_id
            if dst not in seen_dsts[src]:
                window_new_peers[src] += 1

        for edge in rows:
            src, dst = edge.src_asset_id, edge.dst_asset_id
            pair = (src, dst)
            port_values = {e.dst_port for e in rows if e.src_asset_id == src and e.dst_asset_id == dst and e.dst_port is not None}
            history_conn = pair_cum_conn[pair]
            hist_hours = pair_hour_hist[pair]
            hist_total = sum(hist_hours.values())
            tod_freq = (hist_hours.get(window_hour, 0) / hist_total) if hist_total else 0.0
            out.append(
                EdgeFeatureWindow(
                    src_asset_id=src,
                    dst_asset_id=dst,
                    window_start=window_start,
                    window_end=window_end,
                    connections_count=edge.connection_count,
                    packet_count=edge.packet_count,
                    outbound_bytes=edge.bytes_out,
                    inbound_bytes=edge.bytes_in,
                    unique_destination_ports=len(port_values),
                    edge_age_seconds=max((window_start - edge.first_seen).total_seconds(), 0.0),
                    historical_connection_count=history_conn,
                    new_peer=edge.is_new_peer,
                    src_unique_peer_count=len(seen_dsts[src]),
                    src_new_peer_count=window_new_peers.get(src, 0),
                    protocol_novelty=(edge.network_protocol or "NA") not in pair_protocols[pair],
                    time_of_day_frequency=tod_freq,
                    dataset_source=source,
                )
            )

        for edge in rows:
            src, dst = edge.src_asset_id, edge.dst_asset_id
            pair = (src, dst)
            seen_dsts[src].add(dst)
            pair_protocols[pair].add(edge.network_protocol or "NA")
            pair_hour_hist[pair][window_hour] += edge.connection_count
            pair_cum_conn[pair] += edge.connection_count

    out.sort(key=lambda f: (f.window_start, f.src_asset_id, f.dst_asset_id))
    return out


def build_node_features(
    edges: list[CommunicationEdge],
    assets: list[Asset],
    source: SourceDataset,
    window_seconds: int,
) -> list[NodeFeatureWindow]:
    ip_by_asset = {a.asset_id: set(a.ip_addresses) for a in assets}

    by_window: dict[datetime, list[CommunicationEdge]] = defaultdict(list)
    for edge in edges:
        by_window[edge.window_start].append(edge)
    windows = sorted(by_window)

    seen_dsts: dict[str, set[str]] = defaultdict(set)

    out: list[NodeFeatureWindow] = []
    for window_start in windows:
        rows = by_window[window_start]
        window_end = rows[0].window_end

        per_src: dict[str, list[CommunicationEdge]] = defaultdict(list)
        for edge in rows:
            per_src[edge.src_asset_id].append(edge)

        window_new: dict[str, set[str]] = defaultdict(set)
        for src, src_rows in per_src.items():
            for edge in src_rows:
                if edge.dst_asset_id not in seen_dsts[src]:
                    window_new[src].add(edge.dst_asset_id)

        for src, src_rows in per_src.items():
            dst_assets = {e.dst_asset_id for e in src_rows}
            dst_ips: set[str] = set()
            for e in src_rows:
                dst_ips |= ip_by_asset.get(e.dst_asset_id, set())
            dst_ports = {e.dst_port for e in src_rows if e.dst_port is not None}
            protocols = {e.network_protocol for e in src_rows if e.network_protocol}
            dns_conns = sum(e.connection_count for e in src_rows if e.dst_port == 53)
            port_info_available = any(e.dst_port is not None for e in src_rows)
            out.append(
                NodeFeatureWindow(
                    asset_id=src,
                    window_start=window_start,
                    window_end=window_end,
                    connection_count=sum(e.connection_count for e in src_rows),
                    unique_destination_ips=len(dst_ips),
                    unique_destination_assets=len(dst_assets),
                    new_peer_count=len(window_new.get(src, set())),
                    unique_destination_ports=len(dst_ports),
                    outbound_bytes=sum(e.bytes_out for e in src_rows),
                    inbound_bytes=sum(e.bytes_in for e in src_rows),
                    packet_count=sum(e.packet_count for e in src_rows),
                    fan_out=len(dst_assets),
                    protocol_count=len(protocols),
                    dns_query_rate=(dns_conns / window_seconds) if port_info_available else None,
                    failed_connection_ratio=None,
                    dataset_source=source,
                )
            )

        for src, src_rows in per_src.items():
            for edge in src_rows:
                seen_dsts[src].add(edge.dst_asset_id)

    out.sort(key=lambda f: (f.window_start, f.asset_id))
    return out
