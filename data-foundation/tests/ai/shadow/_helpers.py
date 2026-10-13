"""Shared helpers for Shadow Integration tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai.contracts.edge_anomaly_result import (
    AnomalyReason,
    EdgeAnomalyResultV1,
    IdentityQuality,
    Severity,
)
from ai.contracts.shadow_records import ShadowInferenceRecordV1
from src.schemas.base import SourceDataset
from src.schemas.v2 import CommunicationObservation, EdgeFeatureWindowV2

T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)


def obs(win: int, src: str, dst: str, *, proto: str = "TCP", app: str | None = "TLS",
        sport: int | None = 50000, dport: int | None = 443, conn: int = 1,
        packets: int = 10, out: int = 640, inb: int = 600,
        obs_id: str | None = None) -> CommunicationObservation:
    ws = T0 + timedelta(seconds=30 * win)
    oid = obs_id or f"obs:{src}|{dst}|{proto}|{app}|{sport}|{dport}|{win}"
    return CommunicationObservation(
        observation_id=oid,
        relationship_id=f"rel:{src}|{dst}|COMMUNICATES_WITH",
        src_asset_id=src, dst_asset_id=dst,
        window_start=ws, window_end=ws + timedelta(seconds=30),
        network_protocol=proto, application_protocol=app,
        src_port=sport, dst_port=dport,
        connection_count=conn, packet_count=packets,
        bytes_out=out, bytes_in=inb, dataset_source="synthetic",
    )


def sample_sequence() -> list[CommunicationObservation]:
    """Chronological sequence exercising multi-protocol/multi-port + new peers."""
    a = "asset:demo:a"
    b = "asset:demo:b"
    c = "asset:demo:c"
    return [
        obs(0, a, b, proto="TCP", app="TLS", dport=443, sport=50001),
        obs(0, a, b, proto="UDP", app="DNS", dport=53, sport=50002),
        obs(0, a, b, proto="TCP", app="SMB", dport=445, sport=50003),
        obs(1, a, b, proto="TCP", app="TLS", dport=443, sport=50004),
        obs(2, a, c, proto="TCP", app="SMB", dport=445, sport=50005),
        obs(3, a, c, proto="TCP", app="SMB", dport=445, sport=50006),
        obs(4, a, b, proto="TCP", app="TLS", dport=443, sport=50007),
    ]


def make_window(score_conn: int = 1) -> EdgeFeatureWindowV2:
    return EdgeFeatureWindowV2(
        relationship_id="rel:asset:a|asset:b|COMMUNICATES_WITH",
        src_asset_id="asset:a", dst_asset_id="asset:b",
        window_start=T0, window_end=T0 + timedelta(seconds=30),
        connections_count=score_conn, dataset_source=SourceDataset.SYNTHETIC,
    )


def make_record(score: float = 0.5) -> ShadowInferenceRecordV1:
    window = make_window()
    result = EdgeAnomalyResultV1(
        model_version="test", relationship_id=window.relationship_id,
        window_start=window.window_start, window_end=window.window_end,
        anomaly_score=score, severity=Severity.MEDIUM,
        reasons=[AnomalyReason(code="NEW_PEER", contribution=0.5)],
        inference_timestamp=T0,
        identity_quality=IdentityQuality(),
    )
    return ShadowInferenceRecordV1(
        runtime_version="test", received_at=T0, processed_at=T0,
        feature_window=window, anomaly_result=result, processing_latency_ms=1.0,
    )
