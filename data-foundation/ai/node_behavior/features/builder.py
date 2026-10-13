"""Offline causal NodeFeatureWindowV2 builder + model feature matrix."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from ai.node_behavior.features.schema import NodeFeatureWindowV2
from src.schemas.base import SourceDataset
from src.schemas.v2 import CommunicationObservation

KEY_COLUMNS = ["asset_id", "window_start", "window_end", "dataset_source"]


def _new_agg() -> dict:
    return {
        "out_conn": 0, "in_conn": 0, "out_packets": 0, "in_packets": 0,
        "out_bytes": 0, "in_bytes": 0,
        "out_peers": set(), "in_peers": set(),
        "out_ports": set(), "in_ports": set(),
        "out_protos": set(), "in_protos": set(),
        "out_apps": set(), "in_apps": set(),
    }


def build_node_feature_windows_v2(observations: list[CommunicationObservation],
                                  source: SourceDataset | None = None) -> list[NodeFeatureWindowV2]:
    by_window: dict[datetime, list[CommunicationObservation]] = defaultdict(list)
    for o in observations:
        by_window[o.window_start].append(o)

    seen: dict[str, dict] = {}
    out: list[NodeFeatureWindowV2] = []

    for wstart in sorted(by_window):
        rows = by_window[wstart]
        aggs: dict[str, dict] = defaultdict(_new_agg)
        for o in rows:
            src = aggs[o.src_asset_id]
            src["out_conn"] += o.connection_count
            src["out_packets"] += o.packet_count
            src["out_bytes"] += o.bytes_out
            src["in_bytes"] += o.bytes_in
            src["out_peers"].add(o.dst_asset_id)
            src["out_protos"].add(o.network_protocol or "NA")
            if o.application_protocol:
                src["out_apps"].add(o.application_protocol)
            if o.dst_port is not None:
                src["out_ports"].add(o.dst_port)

            dst = aggs[o.dst_asset_id]
            dst["in_conn"] += o.connection_count
            dst["in_packets"] += o.packet_count
            dst["in_bytes"] += o.bytes_out
            dst["out_bytes"] += o.bytes_in
            dst["in_peers"].add(o.src_asset_id)
            dst["in_protos"].add(o.network_protocol or "NA")
            if o.application_protocol:
                dst["in_apps"].add(o.application_protocol)
            if o.dst_port is not None:
                dst["in_ports"].add(o.dst_port)

        window_end = rows[0].window_end
        src_ds = source or SourceDataset(rows[0].dataset_source)
        for asset in sorted(aggs):
            a = aggs[asset]
            st = seen.get(asset)
            if st is None:
                st = {"out_peers": set(), "in_peers": set(), "protos": set(), "ports": set()}
                seen[asset] = st
            window_protos = a["out_protos"] | a["in_protos"]
            window_ports = a["out_ports"] | a["in_ports"]
            new_out = a["out_peers"] - st["out_peers"]
            new_in = a["in_peers"] - st["in_peers"]
            out.append(NodeFeatureWindowV2(
                asset_id=asset, window_start=wstart, window_end=window_end,
                outgoing_connection_count=a["out_conn"], incoming_connection_count=a["in_conn"],
                outgoing_packet_count=a["out_packets"], incoming_packet_count=a["in_packets"],
                outgoing_bytes=a["out_bytes"], incoming_bytes=a["in_bytes"],
                unique_outgoing_peers=len(a["out_peers"]), unique_incoming_peers=len(a["in_peers"]),
                new_outgoing_peer_count=len(new_out), new_incoming_peer_count=len(new_in),
                unique_outgoing_ports=len(a["out_ports"]), unique_incoming_ports=len(a["in_ports"]),
                outbound_protocol_count=len(a["out_protos"]), inbound_protocol_count=len(a["in_protos"]),
                outbound_app_protocol_count=len(a["out_apps"]), inbound_app_protocol_count=len(a["in_apps"]),
                protocol_novelty_count=len(window_protos - st["protos"]),
                port_novelty_count=len(window_ports - st["ports"]),
                fan_out=len(a["out_peers"]), fan_in=len(a["in_peers"]),
                relationship_creation_count=len(new_out) + len(new_in),
                dataset_source=src_ds,
            ))

        for asset in aggs:
            a = aggs[asset]
            st = seen[asset]
            st["out_peers"] |= a["out_peers"]
            st["in_peers"] |= a["in_peers"]
            st["protos"] |= (a["out_protos"] | a["in_protos"])
            st["ports"] |= (a["out_ports"] | a["in_ports"])

    out.sort(key=lambda w: (w.window_start, w.asset_id))
    return out


def build_node_feature_matrix(windows: list[NodeFeatureWindowV2]) -> pd.DataFrame:
    df = pd.DataFrame([w.model_dump() for w in windows])
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df["window_end"] = pd.to_datetime(df["window_end"], utc=True)
    for c in ("dataset_source",):
        if c in df.columns:
            df[c] = df[c].astype(str)
    df = df.sort_values(["asset_id", "window_start"], kind="mergesort").reset_index(drop=True)

    out_conn = df["outgoing_connection_count"].to_numpy(dtype=float)
    in_conn = df["incoming_connection_count"].to_numpy(dtype=float)
    out_bytes = df["outgoing_bytes"].to_numpy(dtype=float)
    in_bytes = df["incoming_bytes"].to_numpy(dtype=float)
    out_peers = df["unique_outgoing_peers"].to_numpy(dtype=float)
    in_peers = df["unique_incoming_peers"].to_numpy(dtype=float)
    new_out = df["new_outgoing_peer_count"].to_numpy(dtype=float)
    new_in = df["new_incoming_peer_count"].to_numpy(dtype=float)
    out_ports = df["unique_outgoing_ports"].to_numpy(dtype=float)
    in_ports = df["unique_incoming_ports"].to_numpy(dtype=float)
    out_app = df["outbound_app_protocol_count"].to_numpy(dtype=float)
    in_app = df["inbound_app_protocol_count"].to_numpy(dtype=float)

    feats = pd.DataFrame({
        "asset_id": df["asset_id"].to_numpy(),
        "window_start": df["window_start"].to_numpy(),
        "log_out_conn": np.log1p(out_conn),
        "log_out_bytes": np.log1p(out_bytes),
        "log_out_packets": np.log1p(df["outgoing_packet_count"].to_numpy(dtype=float)),
        "log_in_conn": np.log1p(in_conn),
        "log_in_bytes": np.log1p(in_bytes),
        "log_in_packets": np.log1p(df["incoming_packet_count"].to_numpy(dtype=float)),
        "out_in_conn_ratio": np.log1p(out_conn / (in_conn + 1.0)),
        "out_in_bytes_ratio": np.log1p(out_bytes / (in_bytes + 1.0)),
        "log_out_peers": np.log1p(out_peers),
        "log_in_peers": np.log1p(in_peers),
        "log_fan_out": np.log1p(out_peers),
        "log_fan_in": np.log1p(in_peers),
        "log_new_out_peers": np.log1p(new_out),
        "log_new_in_peers": np.log1p(new_in),
        "peer_set_change_rate": new_out / (out_peers + 1.0),
        "log_rel_creation": np.log1p(df["relationship_creation_count"].to_numpy(dtype=float)),
        "log_out_ports": np.log1p(out_ports),
        "log_in_ports": np.log1p(in_ports),
        "log_port_novelty": np.log1p(df["port_novelty_count"].to_numpy(dtype=float)),
        "out_protocols": df["outbound_protocol_count"].to_numpy(dtype=float),
        "in_protocols": df["inbound_protocol_count"].to_numpy(dtype=float),
        "protocol_novelty_count": df["protocol_novelty_count"].to_numpy(dtype=float),
        "app_protocol_diversity": np.maximum(out_app, in_app),
    })
    return feats
