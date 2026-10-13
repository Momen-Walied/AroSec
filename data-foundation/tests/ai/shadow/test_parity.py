"""Offline/online feature parity tests."""
from __future__ import annotations

from ai.shadow.features.parity import compare_windows, offline_reference, online_reference
from src.schemas.base import SourceDataset
from tests.ai.shadow._helpers import obs, sample_sequence


def test_parity_exact_on_sample_sequence():
    seq = sample_sequence()
    off = offline_reference(seq, SourceDataset.SYNTHETIC)
    on = online_reference(seq, source="synthetic")
    report = compare_windows(off, on)
    assert report["missing_in_online"] == 0
    assert report["extra_in_online"] == 0
    assert report["total_mismatches"] == 0


def test_parity_multiprotocol_multiport_window():
    seq = [
        obs(0, "asset:a", "asset:b", proto="TCP", app="TLS", dport=443, sport=1),
        obs(0, "asset:a", "asset:b", proto="TCP", app="SMB", dport=445, sport=2),
        obs(0, "asset:a", "asset:b", proto="UDP", app="DNS", dport=53, sport=3),
    ]
    off = offline_reference(seq, SourceDataset.SYNTHETIC)
    on = online_reference(seq, source="synthetic")
    assert compare_windows(off, on)["total_mismatches"] == 0


def test_parity_new_peer_and_novelty():
    seq = [
        obs(0, "asset:a", "asset:b", dport=443),
        obs(1, "asset:a", "asset:b", dport=443),
        obs(2, "asset:a", "asset:c", dport=445),  # new peer + new port
    ]
    off = offline_reference(seq, SourceDataset.SYNTHETIC)
    on = online_reference(seq, source="synthetic")
    assert compare_windows(off, on)["total_mismatches"] == 0


def test_parity_out_of_order_input_is_stable():
    seq = sample_sequence()
    shuffled = list(reversed(seq))
    off = offline_reference(seq, SourceDataset.SYNTHETIC)
    # online sorts internally by (window_start, observation_id)
    on = online_reference(shuffled, source="synthetic")
    assert compare_windows(off, on)["total_mismatches"] == 0
