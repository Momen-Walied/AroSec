"""Time-aware two-phase identity resolver (v0.2).

Guarantees:
  * Two-phase: ALL unions run before ANY root is materialized (fixes v0.1
    fragmentation when identifiers co-occur across records).
  * Strong tokens (mac/hostname/device) union transitively by value.
  * IPs are NOT used as a global join key. An IP is attached as a time-bounded
    binding to whichever strong component it co-occurs with; if two distinct
    strong components use the same IP in disjoint time windows, both get their
    own binding and are NOT merged (IP reuse cannot create a permanent entity).
  * IP-only endpoints become ``dataset_ip_fallback`` / ``ip_only_observation`` assets.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from src.datasets.base import RawBundle
from src.identity.keys import dataset_key, is_usable_host_ip, resolve_asset_identity
from src.schemas.asset import Asset
from src.schemas.base import IdentifierType, IdentityMethod, SourceDataset
from src.schemas.v2 import AssetIdentifierObservation

METHOD_CONFIDENCE: dict[IdentityMethod, float] = {
    IdentityMethod.MANUAL_AUTHORITATIVE: 1.0,
    IdentityMethod.MULTI_SIGNAL: 0.90,
    IdentityMethod.MAC_BASED: 0.85,
    IdentityMethod.DHCP_MAC_CORRELATED: 0.75,
    IdentityMethod.DATASET_DEVICE_ID: 0.70,
    IdentityMethod.DATASET_IP_FALLBACK: 0.40,
    IdentityMethod.IP_ONLY_OBSERVATION: 0.25,
    IdentityMethod.UNKNOWN: 0.0,
}


class _UF:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self.parent.setdefault(key, key)

    def find(self, key: str) -> str:
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, a: str, b: str) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


@dataclass
class _Endpoint:
    strong: str | None
    mac: str | None
    host: str | None
    dev: str | None
    ip: str | None
    ts: datetime
    evidence: str
    record_id: str | None


@dataclass
class _Comp:
    mac: set[str] = field(default_factory=set)
    host: set[str] = field(default_factory=set)
    dev: set[str] = field(default_factory=set)
    ip_interval: dict[str, list[datetime]] = field(default_factory=lambda: defaultdict(list))
    evidence: set[str] = field(default_factory=set)
    first: datetime | None = None
    last: datetime | None = None

    def touch(self, ts: datetime) -> None:
        if self.first is None or ts < self.first:
            self.first = ts
        if self.last is None or ts > self.last:
            self.last = ts


@dataclass
class _IpBinding:
    asset_id: str
    valid_from: datetime
    valid_to: datetime
    strong: bool


@dataclass
class ResolvedIdentity:
    assets: list[Asset]
    bindings: list[AssetIdentifierObservation]


class TwoPhaseResolver:
    def __init__(self) -> None:
        self.uf = _UF()
        self.token_root: dict[str, str] = {}
        self.root_asset: dict[str, str] = {}
        self.ip_bindings: dict[str, list[_IpBinding]] = defaultdict(list)
        self.ip_asset: dict[str, str] = {}

    @staticmethod
    def _t(kind: str, value: str) -> str:
        return f"{kind}:{value.strip().lower()}"

    def resolve(self, bundle: RawBundle, source: SourceDataset) -> ResolvedIdentity:
        ds = source.value
        endpoints = self._collect(bundle)
        self._union_strong(endpoints)
        comps: dict[object, _Comp] = defaultdict(_Comp)
        ip_events: dict[str, list[tuple[str | None, datetime]]] = defaultdict(list)

        for ep in endpoints:
            if ep.strong:
                root = self.uf.find(ep.strong)
                comp = comps[("strong", root)]
                if ep.mac:
                    comp.mac.add(ep.mac)
                if ep.host:
                    comp.host.add(ep.host)
                if ep.dev:
                    comp.dev.add(ep.dev)
                comp.evidence.add(ep.evidence)
                comp.touch(ep.ts)
                if ep.ip:
                    ip_events[ep.ip].append((root, ep.ts))
            elif ep.ip:
                ip_events[ep.ip].append((None, ep.ts))

        for ip, events in ip_events.items():
            strong_events = [(root, ts) for root, ts in events if root is not None]
            iponly_events = [ts for root, ts in events if root is None]
            strong_roots = {root for root, _ in strong_events}
            if not strong_roots:
                comp = comps[("ip", ip)]
                for ts in iponly_events:
                    comp.ip_interval[ip].append(ts)
                    comp.touch(ts)
                continue
            intervals: dict[str, tuple[datetime, datetime]] = {}
            for root in strong_roots:
                times = [ts for r, ts in strong_events if r == root]
                comp = comps[("strong", root)]
                for ts in times:
                    comp.ip_interval[ip].append(ts)
                    comp.touch(ts)
                intervals[root] = (min(times), max(times))
            for ts in iponly_events:
                assigned = next((root for root, (f, t) in intervals.items() if f <= ts <= t), None)
                comp = comps[("strong", assigned)] if assigned is not None else comps[("ip", ip)]
                comp.ip_interval[ip].append(ts)
                comp.touch(ts)

        assets: list[Asset] = []
        bindings: list[AssetIdentifierObservation] = []
        for key, comp in comps.items():
            asset_id, method = self._materialize(ds, key, comp)
            self._register(root_key=key, asset_id=asset_id, comp=comp)
            assets.append(self._asset(ds, asset_id, method, comp))
            bindings.extend(self._bindings(ds, asset_id, method, comp))

        assets.sort(key=lambda a: a.asset_id)
        bindings.sort(key=lambda b: (b.asset_id, b.identifier_type, b.identifier_value))
        return ResolvedIdentity(assets=assets, bindings=bindings)

    def _collect(self, bundle: RawBundle) -> list[_Endpoint]:
        out: list[_Endpoint] = []
        for ob in bundle.observations:
            for side in ("src", "dst"):
                ip = getattr(ob, f"{side}_ip")
                if not is_usable_host_ip(ip):
                    ip = None
                mac = getattr(ob, f"{side}_mac") or None
                host = getattr(ob, f"{side}_hostname") or None
                dev = getattr(ob, f"{side}_device") or None
                strong = None
                for kind, value in (("mac", mac), ("host", host), ("dev", dev)):
                    if value:
                        strong = self._t(kind, str(value))
                        break
                if strong is None and ip is None:
                    continue
                out.append(_Endpoint(strong=strong, mac=mac, host=host, dev=dev, ip=ip,
                                     ts=ob.timestamp, evidence=ob.evidence_source,
                                     record_id=None))
        return out

    def _union_strong(self, endpoints: list[_Endpoint]) -> None:
        for ep in endpoints:
            toks = [self._t(kind, str(value)) for kind, value in
                    (("mac", ep.mac), ("host", ep.host), ("dev", ep.dev)) if value]
            for tok in toks:
                self.uf.add(tok)
            for tok in toks[1:]:
                self.uf.union(toks[0], tok)

    def _materialize(self, ds: str, key: object, comp: _Comp) -> tuple[str, IdentityMethod]:
        if key[0] == "ip":
            ip = key[1]
            times = comp.ip_interval.get(ip, [])
            method = IdentityMethod.DATASET_IP_FALLBACK if len(times) >= 2 else IdentityMethod.IP_ONLY_OBSERVATION
            return f"asset:{dataset_key(ds)}:{ip}", method
        has_mac = bool(comp.mac)
        has_dev = bool(comp.host or comp.dev)
        n_ips = sum(1 for v in comp.ip_interval.values() if v)
        if has_mac and has_dev:
            method = IdentityMethod.MULTI_SIGNAL
        elif has_mac and n_ips >= 2:
            method = IdentityMethod.DHCP_MAC_CORRELATED
        elif has_mac:
            method = IdentityMethod.MAC_BASED
        elif has_dev:
            method = IdentityMethod.DATASET_DEVICE_ID
        else:
            method = IdentityMethod.UNKNOWN
        ident = resolve_asset_identity(
            ds,
            mac=min(comp.mac) if comp.mac else None,
            hostname=min(comp.host) if comp.host else None,
            device_name=min(comp.dev) if comp.dev else None,
            ip=min(comp.ip_interval) if comp.ip_interval else None,
        )
        return ident.asset_id, method

    def _register(self, *, root_key: object, asset_id: str, comp: _Comp) -> None:
        if root_key[0] == "strong":
            self.root_asset[root_key[1]] = asset_id
            for tok in self.uf.parent:
                if self.uf.find(tok) == root_key[1]:
                    self.token_root[tok] = root_key[1]
        else:
            self.ip_asset[root_key[1]] = asset_id
        for ip, times in comp.ip_interval.items():
            if not times:
                continue
            self.ip_bindings[ip].append(
                _IpBinding(asset_id=asset_id, valid_from=min(times), valid_to=max(times),
                           strong=root_key[0] == "strong")
            )

    def _asset(self, ds: str, asset_id: str, method: IdentityMethod, comp: _Comp) -> Asset:
        ips = sorted(comp.ip_interval)
        evidence = sorted(comp.evidence) or [f"{ds}:identity"]
        ident_evidence = []
        for mac in sorted(comp.mac):
            ident_evidence.append(f"mac:{mac}")
        for host in sorted(comp.host):
            ident_evidence.append(f"hostname:{host}")
        for dev in sorted(comp.dev):
            ident_evidence.append(f"device:{dev}")
        for ip in ips:
            ident_evidence.append(f"ip:{ip}")
        return Asset(
            asset_id=asset_id,
            ip_addresses=ips,
            mac_addresses=sorted(comp.mac),
            hostname=min(comp.host) if comp.host else None,
            identity_method=method,
            identity_confidence=METHOD_CONFIDENCE.get(method, 0.0),
            identity_evidence=ident_evidence,
            first_seen=comp.first,
            last_seen=comp.last,
            evidence_sources=evidence,
            dataset_source=ds,
        )

    def _bindings(self, ds: str, asset_id: str, method: IdentityMethod,
                  comp: _Comp) -> list[AssetIdentifierObservation]:
        out: list[AssetIdentifierObservation] = []
        evidence = sorted(comp.evidence)[0] if comp.evidence else f"{ds}:identity"
        for mac in sorted(comp.mac):
            out.append(AssetIdentifierObservation(
                asset_id=asset_id, identifier_type=IdentifierType.MAC, identifier_value=mac,
                valid_from=comp.first, valid_to=comp.last, evidence_source=evidence,
                confidence=0.9, dataset_source=ds))
        for host in sorted(comp.host):
            out.append(AssetIdentifierObservation(
                asset_id=asset_id, identifier_type=IdentifierType.HOSTNAME, identifier_value=host,
                valid_from=comp.first, valid_to=comp.last, evidence_source=evidence,
                confidence=0.7, dataset_source=ds))
        for dev in sorted(comp.dev):
            out.append(AssetIdentifierObservation(
                asset_id=asset_id, identifier_type=IdentifierType.DEVICE_ID, identifier_value=dev,
                valid_from=comp.first, valid_to=comp.last, evidence_source=evidence,
                confidence=0.7, dataset_source=ds))
        for ip, times in comp.ip_interval.items():
            if not times:
                continue
            out.append(AssetIdentifierObservation(
                asset_id=asset_id, identifier_type=IdentifierType.IP, identifier_value=ip,
                valid_from=min(times), valid_to=max(times), evidence_source=evidence,
                confidence=0.4, dataset_source=ds))
        return out

    def asset_id_for(self, *, mac: str | None, host: str | None, dev: str | None,
                     ip: str | None, ts: datetime) -> str | None:
        if not is_usable_host_ip(ip):
            ip = None
        for kind, value in (("mac", mac), ("host", host), ("dev", dev)):
            if value:
                root = self.token_root.get(self._t(kind, str(value)))
                if root is not None:
                    return self.root_asset.get(root)
        if ip:
            binds = self.ip_bindings.get(ip, [])
            strong = [b for b in binds if b.strong]
            if strong:
                containing = [b for b in strong if b.valid_from <= ts <= b.valid_to]
                pool = containing or strong
                chosen = min(pool, key=lambda b: (b.valid_to - b.valid_from).total_seconds())
                return chosen.asset_id
            return self.ip_asset.get(ip)
        return None
