"""Shared normalization pipeline.

Turns a dataset-specific :class:`~src.datasets.base.RawBundle` into validated
v0.1 contracts. All logic here is dataset-agnostic; adapters only parse.

Temporal integrity: edge/window rows are produced in ascending time order and
every derived "history" field (``historical_connection_count``, ``is_new_peer``,
global ``first_seen``) is computed strictly from observations at or before the
current window — never from the future.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from src.datasets.base import RawBundle, RawObservation
from src.identity.keys import (
    is_usable_host_ip,
    make_edge_id,
    make_event_id,
    resolve_asset_identity,
    slug,
)
from src.normalization.label_map import map_label
from src.schemas import Asset, AttackLabel, Campaign, CommunicationEdge, GraphEvent
from src.schemas.attack_label import AttackLabel as _AttackLabelType  # noqa: F401 (re-export clarity)
from src.schemas.base import (
    AttackStage,
    Direction,
    GraphEventType,
    RelationshipType,
    SourceDataset,
)


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self._parent.setdefault(key, key)

    def find(self, key: str) -> str:
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[key] != root:
            self._parent[key], key = root, self._parent[key]
        return root

    def union(self, a: str, b: str) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


class _Resolver:
    """Maps endpoint tokens to stable asset ids and carries per-asset attributes."""

    def __init__(self) -> None:
        self.uf = _UnionFind()
        self.component_attr: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: {"mac": set(), "host": set(), "dev": set(), "ip": set(), "evidence": set()}
        )
        self.component_time: dict[str, dict[str, datetime]] = defaultdict(dict)
        self.root_to_asset_id: dict[str, str] = {}
        self.token_to_root: dict[str, str] = {}

    @staticmethod
    def _token(method: str, value: str) -> str:
        return f"{method}:{value.strip().lower()}"

    def observe(self, ob: RawObservation) -> None:
        for side in ("src", "dst"):
            mac = getattr(ob, f"{side}_mac")
            host = getattr(ob, f"{side}_hostname")
            dev = getattr(ob, f"{side}_device")
            ip = getattr(ob, f"{side}_ip")
            if not is_usable_host_ip(ip):
                ip = None
            tokens: list[tuple[str, str]] = []
            if mac:
                tokens.append(("mac", str(mac)))
            if host:
                tokens.append(("host", str(host)))
            if dev:
                tokens.append(("dev", str(dev)))
            if ip:
                tokens.append(("ip", str(ip)))
            if not tokens:
                continue
            keys = [self._token(m, v) for m, v in tokens]
            for k in keys:
                self.uf.add(k)
            for k in keys[1:]:
                self.uf.union(keys[0], k)

    def finalize(self, bundle: RawBundle, source: SourceDataset) -> None:
        anchor_attr: dict[str, dict[str, set[str]]] = {}
        anchor_time: dict[str, dict[str, datetime]] = {}

        def slot(store: dict, key: str, factory):
            if key not in store:
                store[key] = factory()
            return store[key]

        for ob in bundle.observations:
            self.observe(ob)
            for side in ("src", "dst"):
                ip = getattr(ob, f"{side}_ip")
                if not is_usable_host_ip(ip):
                    ip = None
                host = getattr(ob, f"{side}_hostname")
                dev = getattr(ob, f"{side}_device")
                mac = getattr(ob, f"{side}_mac")
                anchor = None
                for m, v in (("mac", mac), ("host", host), ("dev", dev), ("ip", ip)):
                    if v:
                        anchor = self._token(m, v)
                        break
                if anchor is None:
                    continue
                attr = slot(anchor_attr, anchor,
                            lambda: {"mac": set(), "host": set(), "dev": set(), "ip": set(), "evidence": set()})
                if mac:
                    attr["mac"].add(str(mac))
                if host:
                    attr["host"].add(str(host))
                if dev:
                    attr["dev"].add(str(dev))
                if ip:
                    attr["ip"].add(str(ip))
                attr["evidence"].add(ob.evidence_source)
                times = slot(anchor_time, anchor, dict)
                if "first" not in times or ob.timestamp < times["first"]:
                    times["first"] = ob.timestamp
                if "last" not in times or ob.timestamp > times["last"]:
                    times["last"] = ob.timestamp

        for anchor, attr in anchor_attr.items():
            root = self.uf.find(anchor)
            merged = self.component_attr[root]
            for field in ("mac", "host", "dev", "ip", "evidence"):
                merged[field] |= attr[field]
            times = anchor_time[anchor]
            rt = self.component_time[root]
            if "first" not in rt or times["first"] < rt["first"]:
                rt["first"] = times["first"]
            if "last" not in rt or times["last"] > rt["last"]:
                rt["last"] = times["last"]

        for root in list(self.component_attr):
            attr = self.component_attr[root]
            ident = resolve_asset_identity(
                source.value,
                mac=min(attr["mac"]) if attr["mac"] else None,
                hostname=min(attr["host"]) if attr["host"] else None,
                device_name=min(attr["dev"]) if attr["dev"] else None,
                ip=min(attr["ip"]) if attr["ip"] else None,
            )
            self.root_to_asset_id[root] = ident.asset_id

        for token in self.uf._parent:
            root = self.uf.find(token)
            if root in self.root_to_asset_id:
                self.token_to_root[token] = root

    def asset_id_for(self, *, mac: str | None, host: str | None, dev: str | None, ip: str | None) -> str | None:
        for m, v in (("mac", mac), ("host", host), ("dev", dev), ("ip", ip)):
            if v:
                root = self.token_to_root.get(self._token(m, str(v)))
                if root is not None:
                    return self.root_to_asset_id.get(root)
        return None

    def asset_ident_for(self, root: str):
        attr = self.component_attr[root]
        return resolve_asset_identity(
            self._source_value,
            mac=min(attr["mac"]) if attr["mac"] else None,
            hostname=min(attr["host"]) if attr["host"] else None,
            device_name=min(attr["dev"]) if attr["dev"] else None,
            ip=min(attr["ip"]) if attr["ip"] else None,
        )

    _source_value: str = "synthetic"


def _resolve(bundle: RawBundle, source: SourceDataset) -> tuple[list[Asset], _Resolver]:
    resolver = _Resolver()
    resolver._source_value = source.value
    resolver.finalize(bundle, source)

    assets: list[Asset] = []
    for root, attr in resolver.component_attr.items():
        asset_id = resolver.root_to_asset_id.get(root)
        if asset_id is None:
            continue
        ident = resolver.asset_ident_for(root)
        times = resolver.component_time[root]
        assets.append(
            Asset(
                asset_id=asset_id,
                ip_addresses=sorted(attr["ip"]),
                mac_addresses=sorted(attr["mac"]),
                hostname=min(attr["host"]) if attr["host"] else None,
                identity_method=ident.identity_method,
                identity_confidence=ident.identity_confidence,
                first_seen=times.get("first"),
                last_seen=times.get("last"),
                evidence_sources=sorted(attr["evidence"]),
                dataset_source=source,
            )
        )

    by_id = {a.asset_id: a for a in assets}
    for extra in bundle.extra_assets:
        if extra.asset_id in by_id:
            existing = by_id[extra.asset_id]
            merged_ips = sorted(set(existing.ip_addresses) | set(extra.ip_addresses))
            merged_macs = sorted(set(existing.mac_addresses) | set(extra.mac_addresses))
            existing.ip_addresses = merged_ips
            existing.mac_addresses = merged_macs
        else:
            assets.append(extra)

    assets.sort(key=lambda a: a.asset_id)
    return assets, resolver


def _resolver_for(bundle: RawBundle, source: SourceDataset) -> tuple[list[Asset], _Resolver]:
    cached = getattr(bundle, "_resolved_cache", None)
    if cached is not None and cached[0] == source.value:
        return cached[1]
    result = _resolve(bundle, source)
    bundle._resolved_cache = source.value, result
    return result


def build_assets(bundle: RawBundle, source: SourceDataset) -> list[Asset]:
    assets, _ = _resolver_for(bundle, source)
    return assets


def _floor_window(ts: datetime, seconds: int) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = ts - epoch
    floored = int(delta.total_seconds() // seconds) * seconds
    return epoch + timedelta(seconds=floored)


def build_edges(
    bundle: RawBundle,
    assets: list[Asset],
    source: SourceDataset,
    window_seconds: int = 30,
) -> list[CommunicationEdge]:
    _, resolver = _resolver_for(bundle, source)

    groups: dict[tuple[str, str, str, datetime], dict[str, object]] = {}
    for ob in bundle.observations:
        src_id = resolver.asset_id_for(
            mac=ob.src_mac, host=ob.src_hostname, dev=ob.src_device, ip=ob.src_ip
        )
        dst_id = resolver.asset_id_for(
            mac=ob.dst_mac, host=ob.dst_hostname, dev=ob.dst_device, ip=ob.dst_ip
        )
        if not src_id or not dst_id or src_id == dst_id:
            continue
        proto = (ob.network_protocol or "NA").upper()
        wstart = _floor_window(ob.timestamp, window_seconds)
        key = (src_id, dst_id, proto, wstart)
        g = groups.get(key)
        if g is None:
            g = {
                "conn": 0, "packets": 0, "out": 0, "in": 0,
                "first": ob.timestamp, "last": ob.timestamp,
                "app_protos": set(), "src_ports": set(), "dst_ports": set(),
            }
            groups[key] = g
        g["conn"] = int(g["conn"]) + ob.connection_count
        g["packets"] = int(g["packets"]) + ob.packet_count
        g["out"] = int(g["out"]) + ob.bytes_out
        g["in"] = int(g["in"]) + ob.bytes_in
        g["first"] = min(g["first"], ob.timestamp)  # type: ignore[arg-type]
        g["last"] = max(g["last"], ob.timestamp)    # type: ignore[arg-type]
        if ob.application_protocol:
            g["app_protos"].add(ob.application_protocol)  # type: ignore[union-attr]
        if ob.src_port is not None:
            g["src_ports"].add(ob.src_port)  # type: ignore[union-attr]
        if ob.dst_port is not None:
            g["dst_ports"].add(ob.dst_port)  # type: ignore[union-attr]

    rows = sorted(
        (
            (src_id, dst_id, proto, wstart, g)
            for (src_id, dst_id, proto, wstart), g in groups.items()
        ),
        key=lambda r: (r[3], r[0], r[1], r[2]),
    )

    pair_first_seen: dict[tuple[str, str], datetime] = {}
    for src_id, dst_id, _proto, wstart, g in rows:
        pair = (src_id, dst_id)
        first = g["first"]
        assert isinstance(first, datetime)
        candidate = min(wstart, first)
        if pair not in pair_first_seen or candidate < pair_first_seen[pair]:
            pair_first_seen[pair] = candidate

    running_conn: dict[tuple[str, str], int] = defaultdict(int)
    running_last_seen: dict[tuple[str, str], datetime] = {}
    seen_pair_window: dict[tuple[str, str], bool] = {}

    edges: list[CommunicationEdge] = []
    index = 0
    while index < len(rows):
        src_id, dst_id, _proto, wstart, g = rows[index]
        pair = (src_id, dst_id)
        group_last = g["last"]
        assert isinstance(group_last, datetime)
        end = index
        while (
            end < len(rows)
            and rows[end][0] == src_id
            and rows[end][1] == dst_id
            and rows[end][3] == wstart
        ):
            row_last = rows[end][4]["last"]
            assert isinstance(row_last, datetime)
            group_last = max(group_last, row_last)
            end += 1

        window_end = wstart + timedelta(seconds=window_seconds)
        historical = running_conn[pair]
        is_new = not seen_pair_window.get(pair, False)
        first_seen_global = pair_first_seen[pair]
        prev_last = running_last_seen.get(pair)
        last_seen_global = max(prev_last, group_last) if prev_last else group_last

        group_conn = 0
        for k in range(index, end):
            _s, _d, proto_k, _ws, gk = rows[k]
            app_set = sorted(gk["app_protos"])  # type: ignore[arg-type]
            app_proto = app_set[0] if app_set else None
            bytes_out = int(gk["out"])
            bytes_in = int(gk["in"])
            if bytes_out > 0 and bytes_in > 0:
                direction = Direction.BIDIRECTIONAL
            elif bytes_in > 0:
                direction = Direction.INBOUND
            else:
                direction = Direction.OUTBOUND
            edges.append(
                CommunicationEdge(
                    edge_id=make_edge_id(src_id, dst_id, RelationshipType.COMMUNICATES_WITH.value, proto_k),
                    src_asset_id=src_id,
                    dst_asset_id=dst_id,
                    relationship_type=RelationshipType.COMMUNICATES_WITH,
                    direction=direction,
                    network_protocol=proto_k,
                    application_protocol=app_proto,
                    src_port=min(gk["src_ports"]) if gk["src_ports"] else None,  # type: ignore[arg-type]
                    dst_port=min(gk["dst_ports"]) if gk["dst_ports"] else None,  # type: ignore[arg-type]
                    window_start=wstart,
                    window_end=window_end,
                    connection_count=int(gk["conn"]),
                    packet_count=int(gk["packets"]),
                    bytes_out=bytes_out,
                    bytes_in=bytes_in,
                    first_seen=first_seen_global,
                    last_seen=last_seen_global,
                    historical_connection_count=historical,
                    is_new_peer=is_new,
                    evidence_sources=[f"{source.value}:raw"],
                    confidence=1.0,
                    dataset_source=source,
                )
            )
            group_conn += int(gk["conn"])

        running_conn[pair] += group_conn
        running_last_seen[pair] = last_seen_global
        seen_pair_window[pair] = True
        index = end

    edges.sort(key=lambda e: (e.window_start, e.src_asset_id, e.dst_asset_id, e.network_protocol or ""))
    return edges


def build_labels(
    bundle: RawBundle,
    assets: list[Asset],
    source: SourceDataset,
) -> list[AttackLabel]:
    _, resolver = _resolver_for(bundle, source)

    attack_rows: dict[tuple, AttackLabel] = {}
    benign_rows: dict[tuple[str, str], AttackLabel] = {}

    for ob in bundle.observations:
        if ob.original_label is None or str(ob.original_label).strip() == "":
            continue
        src_id = resolver.asset_id_for(
            mac=ob.src_mac, host=ob.src_hostname, dev=ob.src_device, ip=ob.src_ip
        )
        dst_id = resolver.asset_id_for(
            mac=ob.dst_mac, host=ob.dst_hostname, dev=ob.dst_device, ip=ob.dst_ip
        )
        mapping = map_label(ob.original_label, ob.original_sub_label)
        is_attack = mapping.category.value != "benign"

        if is_attack:
            bucket = int(ob.timestamp.timestamp())
            key = (src_id, dst_id, ob.original_label, ob.original_sub_label, bucket)
            if key in attack_rows:
                continue
            attack_rows[key] = AttackLabel(
                is_attack=True,
                attack_category=mapping.category,
                attack_stage=mapping.stage,
                technique=mapping.technique,
                is_lateral_movement=mapping.is_lateral_movement,
                campaign_id=ob.campaign_key,
                ground_truth_confidence=mapping.confidence,
                original_label=str(ob.original_label),
                original_sub_label=ob.original_sub_label,
                dataset_source=source,
                src_asset_id=src_id,
                dst_asset_id=dst_id,
                event_time=ob.timestamp,
            )
        else:
            key = (src_id or "?", dst_id or "?")
            existing = benign_rows.get(key)
            if existing is None:
                benign_rows[key] = AttackLabel(
                    is_attack=False,
                    attack_category="benign",
                    attack_stage="unknown",
                    technique=None,
                    is_lateral_movement=False,
                    campaign_id=None,
                    ground_truth_confidence=mapping.confidence,
                    original_label=str(ob.original_label),
                    original_sub_label=ob.original_sub_label,
                    dataset_source=source,
                    src_asset_id=src_id,
                    dst_asset_id=dst_id,
                    event_time=ob.timestamp,
                )

    labels = list(attack_rows.values()) + list(benign_rows.values())
    labels.sort(key=lambda lab: (lab.event_time or datetime.min.replace(tzinfo=UTC), lab.is_attack))
    return labels


def build_campaigns(
    bundle: RawBundle,
    assets: list[Asset],
    source: SourceDataset,
) -> list[Campaign]:
    _, resolver = _resolver_for(bundle, source)
    campaigns: list[Campaign] = []

    for seed in bundle.campaign_seeds:
        entry = resolver.asset_id_for(
            mac=None, host=seed.entry_asset_key, dev=seed.entry_asset_key, ip=seed.entry_asset_key
        )
        affected: list[str] = []
        for key in seed.affected_asset_keys:
            aid = resolver.asset_id_for(mac=None, host=None, dev=key, ip=key)
            if aid and aid not in affected:
                affected.append(aid)

        stages: list[AttackStage] = []
        for raw_stage in seed.stage_labels:
            stage = map_label(raw_stage).stage
            if stage not in stages:
                stages.append(stage)

        target = None
        objective = None
        if seed.ground_truth_available:
            if seed.probable_target_asset_key:
                target = resolver.asset_id_for(
                    mac=None, host=None, dev=seed.probable_target_asset_key, ip=seed.probable_target_asset_key
                )
            objective = seed.probable_objective

        campaigns.append(
            Campaign(
                campaign_id=f"campaign:{slug(source.value)}:{slug(seed.campaign_id_source)}",
                start_time=seed.start_time,
                end_time=seed.end_time,
                entry_asset_id=entry,
                affected_asset_ids=affected,
                observed_path=[],
                attack_stages=stages,
                probable_target_asset_id=target,
                probable_objective=objective,
                ground_truth_available=seed.ground_truth_available,
                confidence=1.0 if seed.ground_truth_available else 0.5,
                dataset_source=source,
            )
        )
    return campaigns


def build_graph_events(
    assets: list[Asset],
    edges: list[CommunicationEdge],
    source: SourceDataset,
) -> list[GraphEvent]:
    staged: list[tuple[datetime, int, GraphEvent]] = []
    order = {
        GraphEventType.ASSET_ADDED: 0,
        GraphEventType.IDENTITY_UPDATED: 1,
        GraphEventType.ASSET_UPDATED: 2,
        GraphEventType.EDGE_ADDED: 3,
        GraphEventType.EDGE_UPDATED: 4,
        GraphEventType.EDGE_REMOVED: 5,
    }

    for asset in assets:
        if asset.first_seen is None:
            continue
        ts = asset.first_seen
        event = GraphEvent(
            event_id=make_event_id(GraphEventType.ASSET_ADDED.value, ts.isoformat(), asset.asset_id),
            timestamp=ts,
            event_type=GraphEventType.ASSET_ADDED,
            asset_id=asset.asset_id,
            evidence_source=(asset.evidence_sources[0] if asset.evidence_sources else "normalization"),
            dataset_source=source,
        )
        staged.append((ts, order[GraphEventType.ASSET_ADDED], event))

    pair_first: dict[tuple[str, str], datetime] = {}
    for edge in edges:
        pair = (edge.src_asset_id, edge.dst_asset_id)
        pair_first[pair] = min(pair_first.get(pair, edge.first_seen), edge.first_seen)

    for edge in edges:
        pair = (edge.src_asset_id, edge.dst_asset_id)
        is_first_window = edge.window_start <= pair_first[pair]
        if is_first_window:
            etype = GraphEventType.EDGE_ADDED
            ts = edge.first_seen
        else:
            etype = GraphEventType.EDGE_UPDATED
            ts = edge.window_start
        event = GraphEvent(
            event_id=make_event_id(etype.value, ts.isoformat(), edge.edge_id),
            timestamp=ts,
            event_type=etype,
            edge_id=edge.edge_id,
            src_asset_id=edge.src_asset_id,
            dst_asset_id=edge.dst_asset_id,
            evidence_source=(edge.evidence_sources[0] if edge.evidence_sources else "normalization"),
            dataset_source=source,
        )
        staged.append((ts, order[etype], event))

    staged.sort(key=lambda item: (item[0], item[1], item[2].event_id))
    events: list[GraphEvent] = []
    for version, (_ts, _o, event) in enumerate(staged):
        event.graph_version = version
        events.append(event)
    return events
