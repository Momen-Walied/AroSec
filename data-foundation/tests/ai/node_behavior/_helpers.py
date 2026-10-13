"""Shared helpers for Node Behavior tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.schemas.v2 import CommunicationObservation

T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)


def obs(win: int, src: str, dst: str, *, proto: str = "TCP", app: str | None = "TLS",
        sport: int = 50000, dport: int = 443, conn: int = 1, packets: int = 10,
        out: int = 640, inb: int = 600) -> CommunicationObservation:
    ws = T0 + timedelta(seconds=30 * win)
    return CommunicationObservation(
        observation_id=f"obs:{src}|{dst}|{proto}|{app}|{sport}|{dport}|{win}",
        relationship_id=f"rel:{src}|{dst}|COMMUNICATES_WITH",
        src_asset_id=src, dst_asset_id=dst,
        window_start=ws, window_end=ws + timedelta(seconds=30),
        network_protocol=proto, application_protocol=app,
        src_port=sport, dst_port=dport, connection_count=conn, packet_count=packets,
        bytes_out=out, bytes_in=inb, dataset_source="synthetic",
    )


def by_asset(windows, asset_id, win_index):
    target = T0 + timedelta(seconds=30 * win_index)
    for w in windows:
        if w.asset_id == asset_id and w.window_start == target:
            return w
    raise KeyError((asset_id, win_index))
