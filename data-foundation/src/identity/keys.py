"""Stable identity resolution and deterministic key builders.

Identity precedence (strongest first): MAC > hostname > dataset device name > IP.
An IP-only key is provisional (``identity_method = ip_only`` / ``dataset_derived``)
and carries low ``identity_confidence``; it is never treated as permanent identity.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass

from src.schemas.base import IdentityMethod, SourceDataset


def is_usable_host_ip(value: str | None) -> bool:
    if value is None:
        return False
    try:
        addr = ipaddress.ip_address(str(value).strip())
    except ValueError:
        return False
    if addr.is_unspecified or addr.is_loopback or addr.is_multicast or addr.is_link_local or addr.is_reserved:
        return False
    return str(addr) != "255.255.255.255"


DATASET_KEYS: dict[str, str] = {
    SourceDataset.CICAPT_IIOT.value: "cicapt",
    SourceDataset.X_IIOTID.value: "xiiotid",
    SourceDataset.UNSW_IOTRAFFIC.value: "unsw",
    SourceDataset.EDGE_IIOTSET.value: "edge",
    SourceDataset.CICIOT2023.value: "ciciot",
    SourceDataset.SYNTHETIC.value: "synth",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def dataset_key(dataset_source: str) -> str:
    return DATASET_KEYS.get(str(dataset_source), str(dataset_source).split("_")[0][:8])


def slug(value: str) -> str:
    return _SLUG_RE.sub("-", str(value).strip().lower()).strip("-")


@dataclass(frozen=True)
class AssetIdentity:
    asset_id: str
    identity_method: IdentityMethod
    identity_confidence: float


def resolve_asset_identity(
    dataset_source: str,
    *,
    mac: str | None = None,
    hostname: str | None = None,
    device_name: str | None = None,
    ip: str | None = None,
    fallback_key: str | None = None,
) -> AssetIdentity:
    ds = dataset_key(dataset_source)

    if mac:
        key = "mac-" + slug(mac.replace(":", "").replace("-", ""))
        return AssetIdentity(f"asset:{ds}:{key}", IdentityMethod.MAC_PINNED, 0.95)

    if hostname:
        return AssetIdentity(f"asset:{ds}:host-{slug(hostname)}", IdentityMethod.HOSTNAME, 0.80)

    if device_name:
        return AssetIdentity(
            f"asset:{ds}:dev-{slug(device_name)}", IdentityMethod.DATASET_DERIVED, 0.70
        )

    if ip:
        return AssetIdentity(f"asset:{ds}:{ip}", IdentityMethod.IP_ONLY, 0.30)

    if fallback_key:
        return AssetIdentity(
            f"asset:{ds}:{slug(fallback_key)}", IdentityMethod.DATASET_DERIVED, 0.40
        )

    raise ValueError("cannot resolve asset identity without at least one of mac/hostname/device_name/ip")


def make_edge_id(
    src_asset_id: str,
    dst_asset_id: str,
    relationship_type: str,
    network_protocol: str | None = None,
) -> str:
    proto = (network_protocol or "NA").upper()
    return f"edge:{src_asset_id}|{dst_asset_id}|{relationship_type}|{proto}"


def make_event_id(event_type: str, timestamp_iso: str, *identity_parts: str) -> str:
    raw = "|".join([event_type, timestamp_iso, *[str(p) for p in identity_parts]])
    return "evt:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
