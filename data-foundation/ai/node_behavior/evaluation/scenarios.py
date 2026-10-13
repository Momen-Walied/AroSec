"""Deterministic synthetic node-anomaly scenarios (EVALUATION ONLY; never trained on)."""
from __future__ import annotations

import numpy as np

from ai.node_behavior.features.schema import NodeFeatureWindowV2

SCENARIOS = [
    "SCN-N01_NEW_PEER_BURST",
    "SCN-N02_FAN_OUT_BURST",
    "SCN-N03_PROTOCOL_SHIFT",
    "SCN-N04_PORT_DIVERSITY_BURST",
    "SCN-N05_OUTBOUND_VOLUME_SPIKE",
    "SCN-N06_PEER_SET_REPLACEMENT",
    "SCN-N07_INBOUND_TARGETING",
    "SCN-N08_COMPOUND",
]


def _perturb(row: dict, scenario: str, rng: np.random.Generator) -> dict:
    r = dict(row)
    out_peers = max(int(r.get("unique_outgoing_peers", 1)), 1)
    out_conn = max(int(r.get("outgoing_connection_count", 1)), 1)

    if scenario == "SCN-N01_NEW_PEER_BURST":
        r["new_outgoing_peer_count"] = 20
        r["unique_outgoing_peers"] = out_peers + 20
        r["fan_out"] = r["unique_outgoing_peers"]
        r["relationship_creation_count"] = int(r.get("relationship_creation_count", 0)) + 20
    elif scenario == "SCN-N02_FAN_OUT_BURST":
        r["unique_outgoing_peers"] = max(out_peers, 5) * 6
        r["fan_out"] = r["unique_outgoing_peers"]
        r["new_outgoing_peer_count"] = 2
        r["unique_outgoing_ports"] = int(r.get("unique_outgoing_ports", 1)) + 4
    elif scenario == "SCN-N03_PROTOCOL_SHIFT":
        r["outbound_protocol_count"] = int(r.get("outbound_protocol_count", 1)) + 2
        r["protocol_novelty_count"] = int(r.get("protocol_novelty_count", 0)) + 2
        r["outbound_app_protocol_count"] = int(r.get("outbound_app_protocol_count", 1)) + 2
    elif scenario == "SCN-N04_PORT_DIVERSITY_BURST":
        r["unique_outgoing_ports"] = 25
        r["port_novelty_count"] = 25
    elif scenario == "SCN-N05_OUTBOUND_VOLUME_SPIKE":
        mult = float(rng.choice([10.0, 20.0]))
        r["outgoing_connection_count"] = int(out_conn * mult)
        r["outgoing_packet_count"] = int(r.get("outgoing_packet_count", 0) * mult)
        r["outgoing_bytes"] = int(r.get("outgoing_bytes", 0) * mult)
    elif scenario == "SCN-N06_PEER_SET_REPLACEMENT":
        r["new_outgoing_peer_count"] = out_peers
        r["relationship_creation_count"] = int(r.get("relationship_creation_count", 0)) + out_peers
        r["outgoing_connection_count"] = out_conn  # volume similar
    elif scenario == "SCN-N07_INBOUND_TARGETING":
        in_peers = max(int(r.get("unique_incoming_peers", 1)), 1)
        r["unique_incoming_peers"] = in_peers + 20
        r["new_incoming_peer_count"] = 20
        r["fan_in"] = r["unique_incoming_peers"]
        r["incoming_connection_count"] = int(r.get("incoming_connection_count", 1)) + 20
    elif scenario == "SCN-N08_COMPOUND":
        r["new_outgoing_peer_count"] = 20
        r["unique_outgoing_peers"] = out_peers + 20
        r["fan_out"] = r["unique_outgoing_peers"]
        r["relationship_creation_count"] = int(r.get("relationship_creation_count", 0)) + 20
        r["outbound_protocol_count"] = int(r.get("outbound_protocol_count", 1)) + 2
        r["protocol_novelty_count"] = int(r.get("protocol_novelty_count", 0)) + 2
        r["unique_outgoing_ports"] = 25
        r["port_novelty_count"] = 25
        r["outgoing_bytes"] = int(r.get("outgoing_bytes", 0) * 20)
        r["outgoing_connection_count"] = int(out_conn * 20)
    return r


def build_node_scenario_frames(test_windows: list[NodeFeatureWindowV2], n_per_scenario: int = 300,
                               seed: int = 42) -> dict[str, list[NodeFeatureWindowV2]]:
    rng = np.random.default_rng(seed)
    base = [w.model_dump() for w in test_windows]
    if len(base) > n_per_scenario:
        idx = sorted(rng.choice(len(base), size=n_per_scenario, replace=False))
        base = [base[i] for i in idx]
    frames: dict[str, list[NodeFeatureWindowV2]] = {}
    for scenario in SCENARIOS:
        frames[scenario] = [NodeFeatureWindowV2(**{k: v for k, v in _perturb(dict(b), scenario, rng).items()
                                                   if k != "schema_version"}) for b in base]
    return frames
