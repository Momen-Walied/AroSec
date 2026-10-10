"""Column alias resolution for tabular datasets.

Datasets name the same concept differently (``src_ip`` vs ``Scr_IP`` vs
``Source IP``). This maps a source frame onto canonical field names so adapters
stay thin and no dataset-specific column name leaks into shared graph code.
"""
from __future__ import annotations

import pandas as pd

ALIASES: dict[str, list[str]] = {
    "time": ["time", "timestamp", "ts", "datetime", "date_time", "start_time", "flow_start"],
    "src_ip": ["src_ip", "srcip", "source_ip", "scr_ip", "src_ip_addr", "ip.src", "srcaddr", "saddress"],
    "dst_ip": ["dst_ip", "dstip", "destination_ip", "des_ip", "dst_ip_addr", "ip.dst", "dstaddr", "daddress"],
    "src_port": ["src_port", "srcport", "source_port", "scr_port", "sport", "sp"],
    "dst_port": ["dst_port", "dstport", "destination_port", "des_port", "dport", "dp"],
    "protocol": ["protocol", "proto", "ip_proto", "ipProto", "network_protocol"],
    "app_protocol": ["service", "app_protocol", "application_protocol", "application"],
    "src_mac": ["src_mac", "srcmac", "source_mac", "smac"],
    "dst_mac": ["dst_mac", "dstmac", "destination_mac", "dmac"],
    "bytes_out": ["bytes_out", "src_bytes", "srcbytes", "scr_bytes", "out_bytes", "orig_bytes", "sbytes"],
    "bytes_in": ["bytes_in", "dst_bytes", "dstbytes", "des_bytes", "in_bytes", "resp_bytes", "dbytes"],
    "packets": ["packets", "packet_count", "total_packet", "tot_pkts", "pkts", "total_packets"],
    "packets_out": ["src_pkts", "src_packets", "scr_pkts", "orig_pkts", "spkts"],
    "packets_in": ["dst_pkts", "dst_packets", "des_pkts", "resp_pkts", "dpkts"],
    "label": ["label", "class", "attack", "attack_type", "category", "class1", "class3", "type", "target"],
    "sub_label": ["sub_label", "subcategory", "sub_category", "class2", "subclass", "attack_subtype"],
    "campaign": ["campaign", "campaign_id", "session", "session_id", "apt_id"],
    "src_hostname": ["src_hostname", "src_host", "source_host", "src_name"],
    "dst_hostname": ["dst_hostname", "dst_host", "destination_host", "dst_name"],
    "src_device": ["src_device", "src_device_name", "device", "device_name"],
    "dst_device": ["dst_device", "dst_device_name"],
}


def _norm(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def resolve(df: pd.DataFrame, canonical: str) -> str | None:
    lookup = {_norm(c): c for c in df.columns}
    for alias in ALIASES.get(canonical, []):
        if _norm(alias) in lookup:
            return lookup[_norm(alias)]
    if _norm(canonical) in lookup:
        return lookup[_norm(canonical)]
    return None


def canonicalize_flow_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rename recognized columns to canonical names; drop unrecognized columns."""
    rename: dict[str, str] = {}
    used: set[str] = set()
    for canonical in ALIASES:
        actual = resolve(df, canonical)
        if actual is not None and actual not in rename and canonical not in used:
            rename[actual] = canonical
            used.add(canonical)
    out = df.rename(columns=rename)
    return out[[c for c in out.columns if c in used]]
