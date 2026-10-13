"""Online (incremental) NodeFeatureWindowV2 builder.

Mirrors ``ai/node_behavior/features/builder.py::build_node_feature_windows_v2`` exactly:
one ``CommunicationObservation`` updates OUTBOUND state for ``src_asset_id`` and INBOUND
state for ``dst_asset_id``; window-level state is updated AFTER all entities of a window are
emitted. Event-time watermark / lateness semantics match the Edge online builder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ai.node_behavior.features.schema import NodeFeatureWindowV2
from src.schemas.base import SourceDataset, ensure_utc
from src.schemas.v2 import CommunicationObservation


@dataclass
class _Agg:
    out_conn: int = 0
    in_conn: int = 0
    out_packets: int = 0
    in_packets: int = 0
    out_bytes: int = 0
    in_bytes: int = 0
    out_peers: set[str] = field(default_factory=set)
    in_peers: set[str] = field(default_factory=set)
    out_ports: set[int] = field(default_factory=set)
    in_ports: set[int] = field(default_factory=set)
    out_protos: set[str] = field(default_factory=set)
    in_protos: set[str] = field(default_factory=set)
    out_apps: set[str] = field(default_factory=set)
    in_apps: set[str] = field(default_factory=set)


class OnlineNodeFeatureBuilder:
    def __init__(self, window_seconds: int = 30, allowed_lateness_seconds: int = 30,
                 dedupe_capacity: int = 500_000, dataset_source: str = "unsw_iotraffic") -> None:
        self.window_seconds = window_seconds
        self.allowed_lateness_seconds = allowed_lateness_seconds
        self.dedupe_capacity = dedupe_capacity
        self.dataset_source = dataset_source

        self.asset_state: dict[str, dict] = {}
        self.buffers: dict[str, dict[str, _Agg]] = {}
        self.watermark: datetime | None = None
        self.finalized: list[str] = []
        self._seen: dict[str, None] = {}
        self.counters = {
            "node_observations_received_total": 0,
            "node_observations_duplicate_total": 0,
            "node_observations_late_total": 0,
            "node_windows_emitted_total": 0,
        }

    # ------------------------------------------------------------------ #
    def add(self, obs: CommunicationObservation) -> list[NodeFeatureWindowV2]:
        self.counters["node_observations_received_total"] += 1
        if obs.observation_id in self._seen:
            self.counters["node_observations_duplicate_total"] += 1
            return []

        wstart = ensure_utc(obs.window_start)
        wend = ensure_utc(obs.window_end)
        if self.watermark is not None and (wstart + timedelta(seconds=self.window_seconds + self.allowed_lateness_seconds)) < self.watermark:
            self.counters["node_observations_late_total"] += 1
            return []

        self._remember(obs.observation_id)
        if self.watermark is None or wend > self.watermark:
            self.watermark = wend

        key = wstart.isoformat()
        buf = self.buffers.setdefault(key, {})
        self._apply(buf.setdefault(obs.src_asset_id, _Agg()), obs, outbound=True)
        self._apply(buf.setdefault(obs.dst_asset_id, _Agg()), obs, outbound=False)
        self._ensure_assets(obs)
        return self._finalize_ready()

    @staticmethod
    def _apply(agg: _Agg, obs: CommunicationObservation, *, outbound: bool) -> None:
        if outbound:
            agg.out_conn += obs.connection_count
            agg.out_packets += obs.packet_count
            agg.out_bytes += obs.bytes_out
            agg.in_bytes += obs.bytes_in
            agg.out_peers.add(obs.dst_asset_id)
            agg.out_protos.add(obs.network_protocol or "NA")
            if obs.application_protocol:
                agg.out_apps.add(obs.application_protocol)
            if obs.dst_port is not None:
                agg.out_ports.add(obs.dst_port)
        else:
            agg.in_conn += obs.connection_count
            agg.in_packets += obs.packet_count
            agg.in_bytes += obs.bytes_out
            agg.out_bytes += obs.bytes_in
            agg.in_peers.add(obs.src_asset_id)
            agg.in_protos.add(obs.network_protocol or "NA")
            if obs.application_protocol:
                agg.in_apps.add(obs.application_protocol)
            if obs.dst_port is not None:
                agg.in_ports.add(obs.dst_port)

    def _ensure_assets(self, obs: CommunicationObservation) -> None:
        for asset in (obs.src_asset_id, obs.dst_asset_id):
            self.asset_state.setdefault(asset, {"out_peers": [], "in_peers": [], "protocols": [], "ports": []})

    def flush(self) -> list[NodeFeatureWindowV2]:
        out: list[NodeFeatureWindowV2] = []
        for key in sorted(self.buffers):
            out.extend(self._finalize_window(key))
        return out

    # ------------------------------------------------------------------ #
    def _finalize_ready(self) -> list[NodeFeatureWindowV2]:
        ready = [
            k for k in self.buffers
            if self.watermark is not None
            and (datetime.fromisoformat(k) + timedelta(seconds=self.window_seconds + self.allowed_lateness_seconds)) < self.watermark
        ]
        out: list[NodeFeatureWindowV2] = []
        for key in sorted(ready):
            out.extend(self._finalize_window(key))
        return out

    def _finalize_window(self, key: str) -> list[NodeFeatureWindowV2]:
        buf = self.buffers.pop(key, None)
        if not buf:
            return []
        wstart = datetime.fromisoformat(key)
        window_end = wstart + timedelta(seconds=self.window_seconds)
        emitted: list[NodeFeatureWindowV2] = []
        for asset in sorted(buf):
            a = buf[asset]
            st = self.asset_state[asset]
            out_peers_seen = set(st["out_peers"])
            in_peers_seen = set(st["in_peers"])
            protos_seen = set(st["protocols"])
            ports_seen = set(st["ports"])
            window_protos = a.out_protos | a.in_protos
            window_ports = a.out_ports | a.in_ports
            new_out = a.out_peers - out_peers_seen
            new_in = a.in_peers - in_peers_seen
            emitted.append(NodeFeatureWindowV2(
                asset_id=asset, window_start=wstart, window_end=window_end,
                outgoing_connection_count=a.out_conn, incoming_connection_count=a.in_conn,
                outgoing_packet_count=a.out_packets, incoming_packet_count=a.in_packets,
                outgoing_bytes=a.out_bytes, incoming_bytes=a.in_bytes,
                unique_outgoing_peers=len(a.out_peers), unique_incoming_peers=len(a.in_peers),
                new_outgoing_peer_count=len(new_out), new_incoming_peer_count=len(new_in),
                unique_outgoing_ports=len(a.out_ports), unique_incoming_ports=len(a.in_ports),
                outbound_protocol_count=len(a.out_protos), inbound_protocol_count=len(a.in_protos),
                outbound_app_protocol_count=len(a.out_apps), inbound_app_protocol_count=len(a.in_apps),
                protocol_novelty_count=len(window_protos - protos_seen),
                port_novelty_count=len(window_ports - ports_seen),
                fan_out=len(a.out_peers), fan_in=len(a.in_peers),
                relationship_creation_count=len(new_out) + len(new_in),
                dataset_source=SourceDataset(self.dataset_source),
            ))

        for asset in sorted(buf):
            a = buf[asset]
            st = self.asset_state[asset]
            for p in a.out_peers:
                if p not in st["out_peers"]:
                    st["out_peers"].append(p)
            for p in a.in_peers:
                if p not in st["in_peers"]:
                    st["in_peers"].append(p)
            for p in (a.out_protos | a.in_protos):
                if p not in st["protocols"]:
                    st["protocols"].append(p)
            for p in (a.out_ports | a.in_ports):
                if p not in st["ports"]:
                    st["ports"].append(p)

        self.finalized.append(key)
        if len(self.finalized) > 10_000:
            self.finalized = self.finalized[-5_000:]
        self.counters["node_windows_emitted_total"] += len(emitted)
        return emitted

    def _remember(self, oid: str) -> None:
        self._seen[oid] = None
        if len(self._seen) > self.dedupe_capacity:
            for _ in range(len(self._seen) - self.dedupe_capacity):
                self._seen.pop(next(iter(self._seen)))

    # ------------------------------------------------------------------ #
    def to_state(self) -> dict:
        return {
            "window_seconds": self.window_seconds,
            "allowed_lateness_seconds": self.allowed_lateness_seconds,
            "dataset_source": self.dataset_source,
            "asset_state": self.asset_state,
            "buffers": {
                k: {asset: {
                    "out_conn": a.out_conn, "in_conn": a.in_conn,
                    "out_packets": a.out_packets, "in_packets": a.in_packets,
                    "out_bytes": a.out_bytes, "in_bytes": a.in_bytes,
                    "out_peers": sorted(a.out_peers), "in_peers": sorted(a.in_peers),
                    "out_ports": sorted(a.out_ports), "in_ports": sorted(a.in_ports),
                    "out_protos": sorted(a.out_protos), "in_protos": sorted(a.in_protos),
                    "out_apps": sorted(a.out_apps), "in_apps": sorted(a.in_apps),
                } for asset, a in assets.items()}
                for k, assets in self.buffers.items()
            },
            "watermark": self.watermark.isoformat() if self.watermark else None,
            "finalized": self.finalized[-5_000:],
            "seen_obs": list(self._seen.keys()),
            "counters": self.counters,
        }

    @classmethod
    def from_state(cls, state: dict) -> OnlineNodeFeatureBuilder:
        b = cls(state["window_seconds"], state["allowed_lateness_seconds"],
                dataset_source=state.get("dataset_source", "unsw_iotraffic"))
        b.asset_state = state["asset_state"]
        b.buffers = {
            k: {asset: _Agg(**{
                "out_conn": a["out_conn"], "in_conn": a["in_conn"],
                "out_packets": a["out_packets"], "in_packets": a["in_packets"],
                "out_bytes": a["out_bytes"], "in_bytes": a["in_bytes"],
                "out_peers": set(a["out_peers"]), "in_peers": set(a["in_peers"]),
                "out_ports": set(a["out_ports"]), "in_ports": set(a["in_ports"]),
                "out_protos": set(a["out_protos"]), "in_protos": set(a["in_protos"]),
                "out_apps": set(a["out_apps"]), "in_apps": set(a["in_apps"]),
            }) for asset, a in assets.items()}
            for k, assets in state["buffers"].items()
        }
        b.watermark = datetime.fromisoformat(state["watermark"]) if state["watermark"] else None
        b.finalized = state["finalized"]
        b._seen = {oid: None for oid in state["seen_obs"]}
        b.counters = state["counters"]
        return b
