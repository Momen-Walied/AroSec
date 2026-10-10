"""Shared test fixtures."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.datasets.base import RawBundle, RawObservation
from src.schemas.base import SourceDataset

T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)


def obs(seconds: float, src: str, dst: str, *, proto: str = "TCP", dst_port: int = 445,
        out: int = 100, inb: int = 50, packets: int = 1, label: str | None = None,
        sub: str | None = None, campaign: str | None = None, app: str | None = None) -> RawObservation:
    return RawObservation(
        timestamp=T0 + timedelta(seconds=seconds),
        src_ip=src, dst_ip=dst, dst_port=dst_port, network_protocol=proto,
        application_protocol=app, bytes_out=out, bytes_in=inb, packet_count=packets,
        original_label=label, original_sub_label=sub, campaign_key=campaign,
    )


@pytest.fixture
def scenario_bundle() -> RawBundle:
    return RawBundle(observations=[
        obs(0, "10.0.0.21", "10.0.0.10", dst_port=554, app="RTSP"),
        obs(10, "10.0.0.21", "10.0.0.10", dst_port=554, app="RTSP"),
        obs(20, "10.0.0.21", "10.0.0.10", dst_port=554, app="RTSP"),
        obs(35, "10.0.0.21", "10.0.0.10", dst_port=554, app="RTSP"),
        obs(60, "10.0.0.21", "10.0.0.33", dst_port=445, app="SMB",
            label="Lateral Movement", sub="Lateral Movement", campaign="c1"),
        obs(80, "10.0.0.33", "10.0.0.7", dst_port=502, app="Modbus",
            label="Lateral Movement", sub="Lateral Movement", campaign="c1"),
    ])


@pytest.fixture
def scenario_source() -> SourceDataset:
    return SourceDataset.SYNTHETIC
