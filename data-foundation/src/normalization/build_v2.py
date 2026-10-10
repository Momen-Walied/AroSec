"""Data Foundation v0.2 build pipeline (additive; v0.1 untouched).

Produces the authoritative graph representation:
  assets + asset_identifier_observations + communication_relationships
  + communication_observations (lossless proto/port) + edge_feature_windows_v2
  + graph_events_v2.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import WINDOW_SECONDS, Settings, get_settings
from src.datasets.base import RawBundle
from src.datasets.registry import get_adapter
from src.identity.resolver_v2 import TwoPhaseResolver
from src.normalization import io
from src.normalization.pipeline import _floor_window
from src.schemas import GraphEvent
from src.schemas.asset import Asset
from src.schemas.base import Direction, GraphEventType, RelationshipType, SourceDataset
from src.schemas.v2 import (
    AssetIdentifierObservation,
    CommunicationObservation,
    CommunicationRelationship,
    EdgeFeatureWindowV2,
)

REL = RelationshipType.COMMUNICATES_WITH.value


def _obs_id(rel: str, wstart: datetime, proto: str | None, app: str | None,
            sport: int | None, dport: int | None) -> str:
    raw = "|".join([rel, wstart.isoformat(), proto or "", app or "",
                    "" if sport is None else str(sport), "" if dport is None else str(dport)])
    return "obs:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _direction(out_bytes: int, in_bytes: int) -> Direction:
    if out_bytes > 0 and in_bytes > 0:
        return Direction.BIDIRECTIONAL
    if in_bytes > 0:
        return Direction.INBOUND
    return Direction.OUTBOUND


def canonical_records(bundle: RawBundle, resolver: TwoPhaseResolver, source: SourceDataset) -> list[dict]:
    records: list[dict] = []
    for ob in bundle.observations:
        src = resolver.asset_id_for(mac=ob.src_mac, host=ob.src_hostname, dev=ob.src_device,
                                    ip=ob.src_ip, ts=ob.timestamp)
        dst = resolver.asset_id_for(mac=ob.dst_mac, host=ob.dst_hostname, dev=ob.dst_device,
                                    ip=ob.dst_ip, ts=ob.timestamp)
        if not src or not dst or src == dst:
            continue
        proto = (ob.network_protocol or "NA").upper()
        app = ob.application_protocol
        if app is None or str(app).strip().lower() in {"", "null", "nan", "none", "*", "-"}:
            app = None
        else:
            app = str(app).strip()
        records.append({
            "src": src, "dst": dst, "ts": ob.timestamp,
            "network_protocol": proto,
            "application_protocol": app,
            "src_port": ob.src_port, "dst_port": ob.dst_port,
            "bytes_out": ob.bytes_out, "bytes_in": ob.bytes_in,
            "packet_count": ob.packet_count, "connection_count": ob.connection_count,
            "evidence_source": ob.evidence_source,
        })
    return records


def build_relationships(records: list[dict], source: SourceDataset,
                        window_seconds: int = 30) -> list[CommunicationRelationship]:
    agg: dict[tuple[str, str], dict] = {}
    for r in records:
        key = (r["src"], r["dst"])
        a = agg.get(key)
        if a is None:
            a = {"first": r["ts"], "last": r["ts"], "conn": 0, "windows": set(), "out": 0, "in": 0,
                 "evidence": set()}
            agg[key] = a
        a["conn"] += r["connection_count"]
        a["out"] += r["bytes_out"]
        a["in"] += r["bytes_in"]
        a["windows"].add(_floor_window(r["ts"], window_seconds))
        if r["ts"] < a["first"]:
            a["first"] = r["ts"]
        if r["ts"] > a["last"]:
            a["last"] = r["ts"]
        a["evidence"].add(r["evidence_source"])

    rels: list[CommunicationRelationship] = []
    for (src, dst), a in agg.items():
        rels.append(CommunicationRelationship(
            relationship_id=f"rel:{src}|{dst}|{REL}",
            src_asset_id=src, dst_asset_id=dst, relationship_type=REL,
            first_seen=a["first"], last_seen=a["last"],
            total_observation_count=len(a["windows"]),
            total_connection_count=a["conn"],
            direction=_direction(a["out"], a["in"]),
            evidence_sources=sorted(a["evidence"]),
            dataset_source=source,
        ))
    rels.sort(key=lambda r: r.relationship_id)
    return rels


def build_observations(records: list[dict], source: SourceDataset,
                       window_seconds: int) -> list[CommunicationObservation]:
    groups: dict[tuple, dict] = {}
    for r in records:
        wstart = _floor_window(r["ts"], window_seconds)
        rel = f"rel:{r['src']}|{r['dst']}|{REL}"
        key = (rel, r["src"], r["dst"], wstart, r["network_protocol"],
               r["application_protocol"], r["src_port"], r["dst_port"])
        g = groups.get(key)
        if g is None:
            g = {"conn": 0, "packets": 0, "out": 0, "in": 0, "evidence": set()}
            groups[key] = g
        g["conn"] += r["connection_count"]
        g["packets"] += r["packet_count"]
        g["out"] += r["bytes_out"]
        g["in"] += r["bytes_in"]
        g["evidence"].add(r["evidence_source"])

    obs: list[CommunicationObservation] = []
    for (rel, src, dst, wstart, proto, app, sport, dport), g in groups.items():
        obs.append(CommunicationObservation(
            observation_id=_obs_id(rel, wstart, proto, app, sport, dport),
            relationship_id=rel, src_asset_id=src, dst_asset_id=dst,
            window_start=wstart, window_end=wstart + timedelta(seconds=window_seconds),
            network_protocol=proto, application_protocol=app,
            src_port=sport, dst_port=dport,
            connection_count=g["conn"], packet_count=g["packets"],
            bytes_out=g["out"], bytes_in=g["in"],
            direction=_direction(g["out"], g["in"]),
            evidence_source=sorted(g["evidence"])[0] if g["evidence"] else "normalization",
            dataset_source=source,
        ))
    obs.sort(key=lambda o: (o.window_start, o.relationship_id, o.network_protocol or "",
                            o.dst_port if o.dst_port is not None else -1))
    return obs


def build_edge_features_v2(
    relationships: list[CommunicationRelationship],
    observations: list[CommunicationObservation],
    source: SourceDataset,
) -> list[EdgeFeatureWindowV2]:
    rel_first = {r.relationship_id: r.first_seen for r in relationships}
    by_window: dict[datetime, list[CommunicationObservation]] = defaultdict(list)
    for o in observations:
        by_window[o.window_start].append(o)
    windows = sorted(by_window)

    seen_peers: dict[str, set[str]] = defaultdict(set)
    rel_protocols: dict[str, set[str]] = defaultdict(set)
    rel_ports: dict[str, set[int]] = defaultdict(set)
    rel_cum_conn: dict[str, int] = defaultdict(int)
    rel_window_seen: dict[str, bool] = {}

    out: list[EdgeFeatureWindowV2] = []
    for wstart in windows:
        rows = by_window[wstart]
        window_end = rows[0].window_end

        by_rel: dict[str, list[CommunicationObservation]] = defaultdict(list)
        for o in rows:
            by_rel[o.relationship_id].append(o)

        window_new_peers: dict[str, set[str]] = defaultdict(set)
        for o in rows:
            if o.dst_asset_id not in seen_peers[o.src_asset_id]:
                window_new_peers[o.src_asset_id].add(o.dst_asset_id)

        for rel, rel_rows in by_rel.items():
            src = rel_rows[0].src_asset_id
            dst = rel_rows[0].dst_asset_id
            proto_dist: dict[str, int] = defaultdict(int)
            app_dist: dict[str, int] = defaultdict(int)
            dports: set[int] = set()
            sports: set[int] = set()
            for o in rel_rows:
                p = o.network_protocol or "NA"
                proto_dist[p] += o.connection_count
                if o.application_protocol:
                    app_dist[o.application_protocol] += o.connection_count
                if o.dst_port is not None:
                    dports.add(o.dst_port)
                if o.src_port is not None:
                    sports.add(o.src_port)

            window_protos = set(proto_dist)
            novelty = window_protos - rel_protocols[rel]
            port_novelty = dports - rel_ports[rel]
            distinct_protos = len(window_protos) or 1
            first = rel_first[rel]
            out.append(EdgeFeatureWindowV2(
                relationship_id=rel, src_asset_id=src, dst_asset_id=dst,
                window_start=wstart, window_end=window_end,
                connections_count=sum(o.connection_count for o in rel_rows),
                packet_count=sum(o.packet_count for o in rel_rows),
                outbound_bytes=sum(o.bytes_out for o in rel_rows),
                inbound_bytes=sum(o.bytes_in for o in rel_rows),
                protocol_distribution=dict(proto_dist),
                application_protocol_distribution=dict(app_dist),
                observed_destination_ports=sorted(dports),
                observed_source_ports=sorted(sports),
                unique_destination_ports=len(dports),
                unique_source_ports=len(sports),
                relationship_age_seconds=max((wstart - first).total_seconds(), 0.0),
                historical_connection_count=rel_cum_conn[rel],
                new_peer=not rel_window_seen.get(rel, False),
                src_unique_peer_count=len(seen_peers[src]),
                src_new_peer_count=len(window_new_peers.get(src, set())),
                protocol_novelty_count=len(novelty),
                protocol_novelty_ratio=len(novelty) / distinct_protos,
                port_novelty_count=len(port_novelty),
                dataset_source=source,
            ))

        for rel, rel_rows in by_rel.items():
            for o in rel_rows:
                seen_peers[o.src_asset_id].add(o.dst_asset_id)
                rel_protocols[rel].add(o.network_protocol or "NA")
                if o.dst_port is not None:
                    rel_ports[rel].add(o.dst_port)
            rel_cum_conn[rel] += sum(o.connection_count for o in rel_rows)
            rel_window_seen[rel] = True

    out.sort(key=lambda f: (f.window_start, f.relationship_id))
    return out


def build_events_v2(
    assets: list[Asset],
    bindings: list[AssetIdentifierObservation],
    relationships: list[CommunicationRelationship],
    observations: list[CommunicationObservation],
    source: SourceDataset,
) -> list[GraphEvent]:
    order = {
        GraphEventType.ASSET_ADDED: 0,
        GraphEventType.ASSET_UPDATED: 1,
        GraphEventType.IDENTITY_BINDING_ADDED: 2,
        GraphEventType.IDENTITY_BINDING_EXPIRED: 3,
        GraphEventType.RELATIONSHIP_ADDED: 4,
        GraphEventType.RELATIONSHIP_UPDATED: 5,
        GraphEventType.COMMUNICATION_OBSERVED: 6,
    }
    staged: list[tuple[datetime, int, GraphEvent]] = []

    def add(ts: datetime, etype: GraphEventType, **kw) -> None:
        staged.append((ts, order[etype], GraphEvent(
            event_id="evt:" + hashlib.sha1(
                "|".join([etype.value, ts.isoformat(), *[str(v) for v in kw.values()]]).encode()
            ).hexdigest()[:20],
            timestamp=ts, event_type=etype, dataset_source=source, **kw)))

    for a in assets:
        if a.first_seen:
            add(a.first_seen, GraphEventType.ASSET_ADDED, asset_id=a.asset_id,
                evidence_source=a.evidence_sources[0] if a.evidence_sources else "identity")

    for b in bindings:
        if b.valid_from:
            add(b.valid_from, GraphEventType.IDENTITY_BINDING_ADDED, asset_id=b.asset_id,
                evidence_source=b.evidence_source)

    by_ident: dict[tuple, list] = defaultdict(list)
    for b in bindings:
        by_ident[(str(b.identifier_type), b.identifier_value)].append(b)
    for ident_rows in by_ident.values():
        ident_rows.sort(key=lambda x: x.valid_from or x.valid_to)
        for prev, nxt in zip(ident_rows, ident_rows[1:], strict=False):
            if prev.asset_id != nxt.asset_id and nxt.valid_from:
                add(nxt.valid_from, GraphEventType.IDENTITY_BINDING_EXPIRED, asset_id=prev.asset_id,
                    evidence_source=prev.evidence_source)

    first_window: dict[str, datetime] = {}
    for o in observations:
        first_window[o.relationship_id] = min(first_window.get(o.relationship_id, o.window_start), o.window_start)

    for r in relationships:
        add(r.first_seen, GraphEventType.RELATIONSHIP_ADDED, edge_id=r.relationship_id,
            src_asset_id=r.src_asset_id, dst_asset_id=r.dst_asset_id,
            evidence_source=r.evidence_sources[0] if r.evidence_sources else "normalization")

    for o in observations:
        if o.window_start > first_window[o.relationship_id]:
            add(o.window_start, GraphEventType.RELATIONSHIP_UPDATED, edge_id=o.relationship_id,
                src_asset_id=o.src_asset_id, dst_asset_id=o.dst_asset_id,
                evidence_source=o.evidence_source)
        add(o.window_start, GraphEventType.COMMUNICATION_OBSERVED, edge_id=o.relationship_id,
            observation_id=o.observation_id, src_asset_id=o.src_asset_id, dst_asset_id=o.dst_asset_id,
            evidence_source=o.evidence_source)

    staged.sort(key=lambda item: (item[0], item[1], item[2].event_id))
    events: list[GraphEvent] = []
    for version, (_ts, _o, event) in enumerate(staged):
        event.graph_version = version
        events.append(event)
    return events


@dataclass
class BuildV2Summary:
    dataset_id: str
    window: str
    observations_raw: int = 0
    assets: int = 0
    identity_bindings: int = 0
    relationships: int = 0
    communication_observations: int = 0
    edge_feature_windows: int = 0
    events: int = 0
    identity_method_distribution: dict[str, int] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _write(models, path: Path, samples: Path | None = None) -> Path:
    io.write_parquet(io.models_to_frame(models), path)
    if samples and models:
        io.write_jsonl(models[:200], samples)
    return path


def build_dataset_v2(dataset_id: str, window: str = "30s", settings: Settings | None = None,
                     synthetic: bool = False) -> BuildV2Summary:
    settings = settings or get_settings()
    window_seconds = WINDOW_SECONDS[window]
    if dataset_id == "cicapt_iiot" and synthetic:
        from src.datasets.cicapt import CicaptAdapter
        adapter = CicaptAdapter(settings=settings, synthetic=True)
    else:
        adapter = get_adapter(dataset_id)

    bundle = adapter.load_raw()
    source = adapter.source
    resolver = TwoPhaseResolver()
    resolved = resolver.resolve(bundle, source)
    records = canonical_records(bundle, resolver, source)

    relationships = build_relationships(records, source, window_seconds)
    observations = build_observations(records, source, window_seconds)
    features = build_edge_features_v2(relationships, observations, source)
    events = build_events_v2(resolved.assets, resolved.bindings, relationships, observations, source)

    method_dist: dict[str, int] = defaultdict(int)
    for a in resolved.assets:
        method_dist[str(a.identity_method)] += 1

    processed = settings.processed_dir / "v2"
    samples = settings.samples_dir
    summary = BuildV2Summary(
        dataset_id=dataset_id, window=window,
        observations_raw=len(records),
        assets=len(resolved.assets),
        identity_bindings=len(resolved.bindings),
        relationships=len(relationships),
        communication_observations=len(observations),
        edge_feature_windows=len(features),
        events=len(events),
        identity_method_distribution=dict(method_dist),
    )

    targets = [
        (resolved.assets, processed / "assets" / f"{dataset_id}.parquet", samples / f"v2_{dataset_id}_assets.jsonl"),
        (resolved.bindings, processed / "asset_identifiers" / f"{dataset_id}.parquet", None),
        (relationships, processed / "relationships" / f"{dataset_id}.parquet", samples / f"v2_{dataset_id}_relationships.jsonl"),
        (observations, processed / "communication_observations" / f"{dataset_id}_obs_{window}.parquet", samples / f"v2_{dataset_id}_observations.jsonl"),
        (features, processed / "edge_features" / f"{dataset_id}_{window}.parquet", None),
        (events, processed / "graph_events" / f"{dataset_id}.parquet", None),
    ]
    for models, path, sample in targets:
        if models:
            _write(models, path, sample)
            summary.outputs.append(str(path.relative_to(settings.processed_dir.parent)))

    manifest = processed / "build_manifest_v2.json"
    data = json.loads(manifest.read_text()) if manifest.exists() else {}
    data.setdefault("builds", {})
    entry = summary.to_dict()
    entry["built_at"] = datetime.now(UTC).isoformat()
    data["builds"][f"{dataset_id}:{window}"] = entry
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(data, indent=2))
    summary.outputs.append(str(manifest.relative_to(settings.processed_dir.parent)))
    return summary
