"""Helpers for Node Shadow tests (reuse node behavior observations)."""
from __future__ import annotations

from tests.ai.node_behavior._helpers import T0, obs  # noqa: F401


def sample_sequence():
    a, b, c, d = "asset:a", "asset:b", "asset:c", "asset:d"
    return [
        obs(0, a, b, dport=443),
        obs(0, b, a, dport=80),
        obs(1, a, b, dport=443),
        obs(1, a, c, proto="UDP", dport=53),
        obs(2, a, d, dport=445),
    ]
