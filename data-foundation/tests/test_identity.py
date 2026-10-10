"""Identity resolution + key stability tests."""
from __future__ import annotations

from src.identity.keys import make_edge_id, make_event_id, resolve_asset_identity
from src.schemas.base import IdentityMethod


def test_precedence_mac_over_hostname_over_ip():
    ident = resolve_asset_identity("unsw_iotraffic", mac="AA:BB:CC:DD:EE:FF",
                                   hostname="echo", device_name="amazon", ip="10.0.0.5")
    assert ident.identity_method == IdentityMethod.MAC_PINNED
    assert ident.asset_id == "asset:unsw:mac-aabbccddeeff"
    assert ident.identity_confidence >= 0.9


def test_hostname_identity():
    ident = resolve_asset_identity("cicapt_iiot", hostname="CAM-01", ip="10.0.0.21")
    assert ident.identity_method == IdentityMethod.HOSTNAME
    assert ident.asset_id == "asset:cicapt:host-cam-01"


def test_device_identity_is_dataset_derived():
    ident = resolve_asset_identity("unsw_iotraffic", device_name="AmazonEcho")
    assert ident.identity_method == IdentityMethod.DATASET_DERIVED
    assert ident.asset_id == "asset:unsw:dev-amazonecho"


def test_ip_only_identity_is_provisional():
    ident = resolve_asset_identity("unsw_iotraffic", ip="192.168.1.240")
    assert ident.identity_method == IdentityMethod.IP_ONLY
    assert ident.identity_confidence == 0.30
    assert ident.asset_id == "asset:unsw:192.168.1.240"


def test_edge_id_is_deterministic():
    a = make_edge_id("asset:a", "asset:b", "COMMUNICATES_WITH", "tcp")
    b = make_edge_id("asset:a", "asset:b", "COMMUNICATES_WITH", "TCP")
    assert a == b
    assert a.startswith("edge:")


def test_event_id_deterministic():
    assert make_event_id("EDGE_ADDED", "2024-01-01T00:00:00Z", "edge:x") == \
        make_event_id("EDGE_ADDED", "2024-01-01T00:00:00Z", "edge:x")
