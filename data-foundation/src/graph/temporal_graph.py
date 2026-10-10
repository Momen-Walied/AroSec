"""Temporal cyber-graph prototype + the required query set.

Pure-Python (no Neo4j dependency). Nodes are assets, edges are time-windowed
communication facts, and point-in-time views come from the append-only event log.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from src.schemas import Asset, AttackLabel, CommunicationEdge, GraphEvent
from src.schemas.base import GraphEventType


class TemporalGraph:
    def __init__(
        self,
        assets: list[Asset],
        edges: list[CommunicationEdge],
        events: list[GraphEvent] | None = None,
        labels: list[AttackLabel] | None = None,
    ) -> None:
        self.assets = {a.asset_id: a for a in assets}
        self.edges = edges
        self.events = events or []
        self.labels = labels or []
        self._adj: dict[str, list[CommunicationEdge]] = defaultdict(list)
        for edge in edges:
            self._adj[edge.src_asset_id].append(edge)

    # 1 ----------------------------------------------------------------- #
    def neighbors_during(self, asset_id: str, t1: datetime, t2: datetime) -> list[str]:
        peers: set[str] = set()
        for edge in self.edges:
            if edge.window_start < t1 or edge.window_start > t2:
                continue
            if edge.src_asset_id == asset_id:
                peers.add(edge.dst_asset_id)
            elif edge.dst_asset_id == asset_id:
                peers.add(edge.src_asset_id)
        return sorted(peers)

    # 2 ----------------------------------------------------------------- #
    def new_relationships(self, t1: datetime, t2: datetime) -> list[CommunicationEdge]:
        return [
            e for e in self.edges
            if e.is_new_peer and t1 <= e.first_seen <= t2
        ]

    # 3 ----------------------------------------------------------------- #
    def sources_with_many_new_peers(self, min_new_peers: int = 3) -> list[tuple[str, int]]:
        counts: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            if edge.is_new_peer:
                counts[edge.src_asset_id] += 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [(src, n) for src, n in ranked if n >= min_new_peers]

    # 4 ----------------------------------------------------------------- #
    def novel_edges(self, source: str | None = None) -> list[CommunicationEdge]:
        return [e for e in self.edges if e.is_new_peer and (source is None or e.src_asset_id == source)]

    # 5 ----------------------------------------------------------------- #
    def campaign_sequence(self, campaign_id: str) -> list[CommunicationEdge]:
        target_asset_ids = {
            label.src_asset_id for label in self.labels if label.campaign_id == campaign_id and label.src_asset_id
        }
        return sorted(
            (e for e in self.edges if e.src_asset_id in target_asset_ids),
            key=lambda e: e.window_start,
        )

    # 6 ----------------------------------------------------------------- #
    def paths_between(
        self,
        src_asset_id: str,
        dst_asset_id: str,
        t1: datetime | None = None,
        t2: datetime | None = None,
        max_depth: int = 6,
    ) -> list[list[str]]:
        def ok(edge: CommunicationEdge) -> bool:
            if t1 is not None and edge.window_start < t1:
                return False
            if t2 is not None and edge.window_start > t2:
                return False
            return True

        results: list[list[str]] = []
        queue: deque[list[str]] = deque([[src_asset_id]])
        while queue:
            path = queue.popleft()
            if len(path) > max_depth:
                continue
            node = path[-1]
            if node == dst_asset_id and len(path) > 1:
                results.append(path)
                continue
            for edge in self._adj.get(node, []):
                if not ok(edge) or edge.dst_asset_id in path:
                    continue
                queue.append(path + [edge.dst_asset_id])
        return results

    # 7 ----------------------------------------------------------------- #
    def snapshot(self, t: datetime) -> dict[str, list[str]]:
        version = -1
        for event in self.events:
            if event.timestamp <= t:
                version = max(version, event.graph_version)
        active_assets: set[str] = set()
        active_edges: set[str] = set()
        removed: set[str] = set()
        for event in self.events:
            if event.graph_version > version:
                break
            if event.event_type == GraphEventType.ASSET_ADDED and event.asset_id:
                active_assets.add(event.asset_id)
            elif event.event_type == GraphEventType.EDGE_ADDED and event.edge_id:
                active_edges.add(event.edge_id)
            elif event.event_type == GraphEventType.EDGE_REMOVED and event.edge_id:
                removed.add(event.edge_id)
        return {
            "graph_version": [str(version)],
            "assets": sorted(active_assets),
            "edges": sorted(active_edges - removed),
        }

    # 8 ----------------------------------------------------------------- #
    def lateral_movement_nodes(self) -> list[str]:
        nodes: set[str] = set()
        for label in self.labels:
            if label.is_lateral_movement:
                if label.src_asset_id:
                    nodes.add(label.src_asset_id)
                if label.dst_asset_id:
                    nodes.add(label.dst_asset_id)
        return sorted(nodes)

    # convenience ------------------------------------------------------- #
    def edge_rows(self) -> list[dict]:
        return [
            {
                "edge_id": e.edge_id,
                "src_asset_id": e.src_asset_id,
                "dst_asset_id": e.dst_asset_id,
                "network_protocol": e.network_protocol,
                "application_protocol": e.application_protocol,
                "window_start": e.window_start.isoformat(),
                "window_end": e.window_end.isoformat(),
                "connection_count": e.connection_count,
                "packet_count": e.packet_count,
                "bytes_out": e.bytes_out,
                "bytes_in": e.bytes_in,
                "first_seen": e.first_seen.isoformat(),
                "last_seen": e.last_seen.isoformat(),
                "historical_connection_count": e.historical_connection_count,
                "is_new_peer": e.is_new_peer,
            }
            for e in self.edges
        ]
