"""Online (incremental) EdgeFeatureWindowV2 builder.

Maintains causal state so that, given the same chronological CommunicationObservation
sequence, it reproduces the offline ``build_edge_features_v2`` output.

Semantics mirrored exactly from ``src/normalization/build_v2.py``:
  * per (relationship, window) aggregation with protocol/app-protocol distributions
    keyed by connection_count, distinct observed src/dst ports
  * history fields (historical_connection_count, new_peer, src_unique_peer_count,
    src_new_peer_count, protocol_novelty_*, port_novelty_count) use only windows
    strictly before the current window
  * window-level state is updated AFTER all relationships of that window are emitted

Intentional difference (documented): ``relationship_age_seconds`` uses the first
observed *window_start* as the relationship's first_seen, because CommunicationObservation
carries window boundaries (not raw packet timestamps). The training-time offline builder
used the raw first packet time; the difference is bounded by one window and is 0 for the
first window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.schemas.base import SourceDataset, ensure_utc
from src.schemas.v2 import CommunicationObservation, EdgeFeatureWindowV2


@dataclass
class _Agg:
    src: str
    dst: str
    conn: int = 0
    packets: int = 0
    out: int = 0
    inb: int = 0
    proto: dict[str, int] = field(default_factory=dict)
    app: dict[str, int] = field(default_factory=dict)
    dst_ports: set[int] = field(default_factory=set)
    src_ports: set[int] = field(default_factory=set)


class OnlineFeatureBuilder:
    def __init__(self, window_seconds: int = 30, allowed_lateness_seconds: int = 5,
                 dedupe_capacity: int = 500_000, dataset_source: str = "unsw_iotraffic") -> None:
        self.window_seconds = window_seconds
        self.allowed_lateness_seconds = allowed_lateness_seconds
        self.dedupe_capacity = dedupe_capacity
        self.dataset_source = dataset_source

        self.rel_state: dict[str, dict] = {}
        self.src_state: dict[str, dict] = {}
        self.buffers: dict[str, dict[str, _Agg]] = {}
        self.watermark: datetime | None = None
        self.finalized: list[str] = []
        self._seen: dict[str, None] = {}
        # transient per-emitted-window context for the scorer (app-protocol novelty)
        self.window_context: dict[tuple[str, str], dict] = {}

        self.counters = {
            "observations_received_total": 0,
            "observations_duplicate_total": 0,
            "observations_late_total": 0,
            "feature_windows_emitted_total": 0,
        }

    # ------------------------------------------------------------------ #
    def add(self, obs: CommunicationObservation) -> list[EdgeFeatureWindowV2]:
        self.counters["observations_received_total"] += 1
        oid = obs.observation_id
        if oid in self._seen:
            self.counters["observations_duplicate_total"] += 1
            return []

        wstart = ensure_utc(obs.window_start)
        wend = ensure_utc(obs.window_end)
        if self.watermark is not None and (wstart + timedelta(seconds=self.window_seconds + self.allowed_lateness_seconds)) < self.watermark:
            self.counters["observations_late_total"] += 1
            return []

        self._remember(oid)
        if self.watermark is None or wend > self.watermark:
            self.watermark = wend

        key = wstart.isoformat()
        buf = self.buffers.setdefault(key, {})
        agg = buf.get(obs.relationship_id)
        if agg is None:
            agg = _Agg(src=obs.src_asset_id, dst=obs.dst_asset_id)
            buf[obs.relationship_id] = agg
        agg.conn += obs.connection_count
        agg.packets += obs.packet_count
        agg.out += obs.bytes_out
        agg.inb += obs.bytes_in
        agg.proto[obs.network_protocol or "NA"] = agg.proto.get(obs.network_protocol or "NA", 0) + obs.connection_count
        if obs.application_protocol:
            agg.app[obs.application_protocol] = agg.app.get(obs.application_protocol, 0) + obs.connection_count
        if obs.dst_port is not None:
            agg.dst_ports.add(obs.dst_port)
        if obs.src_port is not None:
            agg.src_ports.add(obs.src_port)

        self._ensure_rel(obs.relationship_id, wstart)
        return self._finalize_ready()

    def flush(self) -> list[EdgeFeatureWindowV2]:
        out: list[EdgeFeatureWindowV2] = []
        for key in sorted(self.buffers):
            out.extend(self._finalize_window(key))
        return out

    # ------------------------------------------------------------------ #
    def _ensure_rel(self, rel: str, wstart: datetime) -> None:
        st = self.rel_state.get(rel)
        if st is None:
            self.rel_state[rel] = {
                "first_seen": wstart.isoformat(),
                "protocols": [],
                "app_protocols": [],
                "dst_ports": [],
                "hist_conn": 0,
                "window_seen": False,
                "obs_count": 0,
            }

    def _finalize_ready(self) -> list[EdgeFeatureWindowV2]:
        ready = [
            k for k in self.buffers
            if self.watermark is not None
            and (datetime.fromisoformat(k) + timedelta(seconds=self.window_seconds + self.allowed_lateness_seconds)) < self.watermark
        ]
        out: list[EdgeFeatureWindowV2] = []
        for key in sorted(ready):
            out.extend(self._finalize_window(key))
        return out

    def _finalize_window(self, key: str) -> list[EdgeFeatureWindowV2]:
        buf = self.buffers.pop(key, None)
        if not buf:
            return []
        wstart = datetime.fromisoformat(key)
        window_end = wstart + timedelta(seconds=self.window_seconds)
        rels = sorted(buf)

        window_new_peers: dict[str, set[str]] = {}
        for rel in rels:
            agg = buf[rel]
            if agg.dst not in self.src_state.get(agg.src, {}).get("peers_set", set()):
                window_new_peers.setdefault(agg.src, set()).add(agg.dst)

        emitted: list[EdgeFeatureWindowV2] = []
        for rel in rels:
            agg = buf[rel]
            st = self.rel_state[rel]
            protocols_seen = set(st["protocols"])
            ports_seen = set(st["dst_ports"])
            window_protos = set(agg.proto)
            novelty = window_protos - protocols_seen
            port_novelty = agg.dst_ports - ports_seen
            distinct = len(window_protos) or 1
            first_seen = datetime.fromisoformat(st["first_seen"])
            prior_app = set(st["app_protocols"])
            app_novelty = len(set(agg.app) - prior_app)
            self.window_context[(key, rel)] = {
                "prior_app_protocols": sorted(prior_app),
                "app_protocol_novelty_count": app_novelty,
            }
            emitted.append(EdgeFeatureWindowV2(
                relationship_id=rel, src_asset_id=agg.src, dst_asset_id=agg.dst,
                window_start=wstart, window_end=window_end,
                connections_count=agg.conn, packet_count=agg.packets,
                outbound_bytes=agg.out, inbound_bytes=agg.inb,
                protocol_distribution=dict(agg.proto),
                application_protocol_distribution=dict(agg.app),
                observed_destination_ports=sorted(agg.dst_ports),
                observed_source_ports=sorted(agg.src_ports),
                unique_destination_ports=len(agg.dst_ports),
                unique_source_ports=len(agg.src_ports),
                relationship_age_seconds=max((wstart - first_seen).total_seconds(), 0.0),
                historical_connection_count=st["hist_conn"],
                new_peer=not st["window_seen"],
                src_unique_peer_count=len(self.src_state.get(agg.src, {}).get("peers_set", set())),
                src_new_peer_count=len(window_new_peers.get(agg.src, set())),
                protocol_novelty_count=len(novelty),
                protocol_novelty_ratio=len(novelty) / distinct,
                port_novelty_count=len(port_novelty),
                dataset_source=SourceDataset(self.dataset_source),
            ))

        for rel in rels:
            agg = buf[rel]
            st = self.rel_state[rel]
            peers = self.src_state.setdefault(agg.src, {"peers": [], "peers_set": set()})
            if agg.dst not in peers["peers_set"]:
                peers["peers_set"].add(agg.dst)
                peers["peers"].append(agg.dst)
            for p in agg.proto:
                if p not in st["protocols"]:
                    st["protocols"].append(p)
            for a in agg.app:
                if a not in st["app_protocols"]:
                    st["app_protocols"].append(a)
            for dp in agg.dst_ports:
                if dp not in st["dst_ports"]:
                    st["dst_ports"].append(dp)
            st["hist_conn"] += agg.conn
            st["window_seen"] = True
            st["obs_count"] += 1

        self.finalized.append(key)
        if len(self.finalized) > 10_000:
            self.finalized = self.finalized[-5_000:]
        self.counters["feature_windows_emitted_total"] += len(emitted)
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
            "rel_state": self.rel_state,
            "src_state": {k: {"peers": v["peers"]} for k, v in self.src_state.items()},
            "buffers": {
                k: {rel: {
                    "src": a.src, "dst": a.dst, "conn": a.conn, "packets": a.packets,
                    "out": a.out, "inb": a.inb, "proto": a.proto, "app": a.app,
                    "dst_ports": sorted(a.dst_ports), "src_ports": sorted(a.src_ports),
                } for rel, a in rels.items()}
                for k, rels in self.buffers.items()
            },
            "watermark": self.watermark.isoformat() if self.watermark else None,
            "finalized": self.finalized[-5_000:],
            "seen_obs": list(self._seen.keys()),
            "counters": self.counters,
        }

    @classmethod
    def from_state(cls, state: dict) -> OnlineFeatureBuilder:
        b = cls(state["window_seconds"], state["allowed_lateness_seconds"],
                dataset_source=state.get("dataset_source", "unsw_iotraffic"))
        b.rel_state = state["rel_state"]
        b.src_state = {
            k: {"peers": v["peers"], "peers_set": set(v["peers"])}
            for k, v in state["src_state"].items()
        }
        b.buffers = {
            k: {rel: _Agg(
                src=a["src"], dst=a["dst"], conn=a["conn"], packets=a["packets"],
                out=a["out"], inb=a["inb"], proto=dict(a["proto"]), app=dict(a["app"]),
                dst_ports=set(a["dst_ports"]), src_ports=set(a["src_ports"]))
                for rel, a in rels.items()}
            for k, rels in state["buffers"].items()
        }
        b.watermark = datetime.fromisoformat(state["watermark"]) if state["watermark"] else None
        b.finalized = state["finalized"]
        b._seen = {oid: None for oid in state["seen_obs"]}
        b.counters = state["counters"]
        return b
