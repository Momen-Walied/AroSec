"""Deterministic synthetic anomaly scenarios (EVALUATION ONLY).

Perturbations are applied to v0.2 EdgeFeatureWindowV2 rows sampled from the TEST
split. They are never mixed into training. Each scenario is labelled explicitly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

UNSEEN_PROTOCOL = "SCP"
UNSEEN_APP_PROTOCOL = "XPROTO"
UNSEEN_PORT = 65535

SCENARIOS = [
    "SCN-001_NEW_PEER",
    "SCN-002_NEW_PORT",
    "SCN-003_NEW_PROTOCOL",
    "SCN-004_FAN_OUT_BURST",
    "SCN-005_TRAFFIC_VOLUME_SPIKE",
    "SCN-006_COMPOUND",
]


def _base_rows(test_df: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    if len(test_df) <= n:
        return test_df.copy()
    idx = rng.choice(len(test_df), size=n, replace=False)
    return test_df.iloc[sorted(idx)].copy()


def _perturb(row: dict, scenario: str, rng: np.random.Generator, k: int) -> dict:
    r = dict(row)
    nproto = max(len(r.get("protocol_distribution", {}) or {"TCP": 1}), 1)

    if scenario == "SCN-001_NEW_PEER":
        r["dst_asset_id"] = f"asset:synth:unseen-{k}"
        r["relationship_id"] = f"rel:{r['src_asset_id']}|{r['dst_asset_id']}|COMMUNICATES_WITH"
        r["new_peer"] = True
        r["historical_connection_count"] = 0
        r["relationship_age_seconds"] = 0.0
        r["src_new_peer_count"] = int(r.get("src_unique_peer_count", 0)) + 1
    elif scenario == "SCN-002_NEW_PORT":
        r["observed_destination_ports"] = [UNSEEN_PORT]
        r["unique_destination_ports"] = 1
        r["port_novelty_count"] = 1
    elif scenario == "SCN-003_NEW_PROTOCOL":
        r["protocol_distribution"] = {UNSEEN_PROTOCOL: int(r.get("connections_count", 1))}
        r["application_protocol_distribution"] = {UNSEEN_APP_PROTOCOL: int(r.get("connections_count", 1))}
        r["protocol_novelty_count"] = nproto
        r["protocol_novelty_ratio"] = 1.0
    elif scenario == "SCN-004_FAN_OUT_BURST":
        r["src_new_peer_count"] = 20
        r["src_unique_peer_count"] = max(int(r.get("src_unique_peer_count", 0)), 3) + 20
    elif scenario == "SCN-005_TRAFFIC_VOLUME_SPIKE":
        mult = float(rng.choice([10.0, 20.0]))
        for f in ("connections_count", "packet_count", "outbound_bytes", "inbound_bytes"):
            r[f] = int(r.get(f, 0) * mult)
    elif scenario == "SCN-006_COMPOUND":
        r["dst_asset_id"] = f"asset:synth:unseen-{k}"
        r["relationship_id"] = f"rel:{r['src_asset_id']}|{r['dst_asset_id']}|COMMUNICATES_WITH"
        r["new_peer"] = True
        r["historical_connection_count"] = 0
        r["relationship_age_seconds"] = 0.0
        r["src_new_peer_count"] = int(r.get("src_unique_peer_count", 0)) + 20
        r["observed_destination_ports"] = [UNSEEN_PORT]
        r["port_novelty_count"] = 1
        r["protocol_distribution"] = {UNSEEN_PROTOCOL: int(r.get("connections_count", 1))}
        r["protocol_novelty_count"] = nproto
        r["protocol_novelty_ratio"] = 1.0
    return r


def build_scenario_frames(test_df: pd.DataFrame, n_per_scenario: int = 300,
                          seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    base = _base_rows(test_df, n_per_scenario, rng)
    frames: dict[str, pd.DataFrame] = {}
    for scenario in SCENARIOS:
        rows = []
        for k, (_idx, row) in enumerate(base.iterrows()):
            rows.append(_perturb(dict(row), scenario, rng, k))
        frames[scenario] = pd.DataFrame(rows)
    return frames
