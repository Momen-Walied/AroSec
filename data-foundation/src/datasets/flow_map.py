"""Map a canonicalized flow frame to :class:`RawObservation` records."""
from __future__ import annotations

import pandas as pd

from src.datasets.base import RawObservation

_NA = {"", "*", "null", "nan", "none", "-", "unknown"}
_IP_PROTO = {1: "ICMP", 2: "IGMP", 6: "TCP", 17: "UDP", 58: "ICMPV6"}


def _text(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return None if text.lower() in _NA else text


def _int(value: object) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def _timestamp(value: object):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC").to_pydatetime()
    text = str(value).strip()
    if text.lower() in _NA:
        return None
    try:
        return pd.to_datetime(float(text), unit="s", utc=True).to_pydatetime()
    except (ValueError, TypeError):
        pass
    parsed = pd.to_datetime(text, utc=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def _proto(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return _IP_PROTO.get(int(float(text)), f"IP-{int(float(text))}")
    except (ValueError, TypeError):
        return text.upper()


def canonical_frame_to_observations(df: pd.DataFrame, evidence_source: str = "raw") -> list[RawObservation]:
    out: list[RawObservation] = []
    for row in df.to_dict(orient="records"):
        ts = _timestamp(row.get("time"))
        if ts is None:
            continue
        packets = _int(row.get("packets"))
        if packets is None:
            packets = (_int(row.get("packets_out")) or 0) + (_int(row.get("packets_in")) or 0)
        out.append(
            RawObservation(
                timestamp=ts,
                src_ip=_text(row.get("src_ip")),
                dst_ip=_text(row.get("dst_ip")),
                src_mac=_text(row.get("src_mac")),
                dst_mac=_text(row.get("dst_mac")),
                src_port=_int(row.get("src_port")),
                dst_port=_int(row.get("dst_port")),
                network_protocol=_proto(row.get("protocol")),
                application_protocol=(_text(row.get("app_protocol")) or "") or None,
                bytes_out=_int(row.get("bytes_out")) or 0,
                bytes_in=_int(row.get("bytes_in")) or 0,
                packet_count=max(packets or 0, 0),
                src_hostname=_text(row.get("src_hostname")),
                dst_hostname=_text(row.get("dst_hostname")),
                src_device=_text(row.get("src_device")),
                dst_device=_text(row.get("dst_device")),
                original_label=_text(row.get("label")),
                original_sub_label=_text(row.get("sub_label")),
                campaign_key=_text(row.get("campaign")),
                evidence_source=evidence_source,
            )
        )
    return out
