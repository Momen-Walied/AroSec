"""Shared helpers for Edge Behavior tests (fast synthetic v0.2 frames)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd


def make_frame(n: int = 400, seed: int = 0, n_relationships: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = datetime(2024, 3, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        rel = i % n_relationships
        conns = int(rng.integers(1, 5))
        dport = int(rng.choice([443, 53, 554, 123]))
        rows.append({
            "relationship_id": f"rel:asset:synth:s{rel}|asset:synth:d{rel}|COMMUNICATES_WITH",
            "src_asset_id": f"asset:synth:s{rel}",
            "dst_asset_id": f"asset:synth:d{rel}",
            "window_start": t0 + timedelta(seconds=30 * i),
            "window_end": t0 + timedelta(seconds=30 * i + 30),
            "connections_count": conns,
            "packet_count": conns * 10,
            "outbound_bytes": conns * 320,
            "inbound_bytes": conns * 300,
            "protocol_distribution": {"TCP": conns},
            "application_protocol_distribution": {"TLS": conns},
            "observed_destination_ports": [dport],
            "observed_source_ports": [50000 + i],
            "unique_destination_ports": 1,
            "unique_source_ports": 1,
            "relationship_age_seconds": float(30 * i),
            "historical_connection_count": i,
            "new_peer": i < n_relationships,
            "src_unique_peer_count": 1 + (i // n_relationships),
            "src_new_peer_count": 1 if i < n_relationships else 0,
            "protocol_novelty_count": 1 if i < n_relationships else 0,
            "protocol_novelty_ratio": 1.0 if i < n_relationships else 0.0,
            "port_novelty_count": 1 if i < n_relationships else 0,
            "dataset_source": "synthetic",
        })
    return pd.DataFrame(rows)
