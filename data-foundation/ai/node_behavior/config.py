"""Node Behavior v1 configuration: feature schema + interpretable components."""
from __future__ import annotations

NODE_FEATURE_SCHEMA_VERSION = "node_features_v1"

# Model feature columns (derived from NodeFeatureWindowV2 facts).
NODE_FEATURE_COLUMNS: list[str] = [
    # outbound volume
    "log_out_conn", "log_out_bytes", "log_out_packets",
    # inbound volume
    "log_in_conn", "log_in_bytes", "log_in_packets",
    # direction balance
    "out_in_conn_ratio", "out_in_bytes_ratio",
    # peers / fan
    "log_out_peers", "log_in_peers", "log_fan_out", "log_fan_in",
    # novelty / change
    "log_new_out_peers", "log_new_in_peers", "peer_set_change_rate", "log_rel_creation",
    # ports
    "log_out_ports", "log_in_ports", "log_port_novelty",
    # protocols
    "out_protocols", "in_protocols", "protocol_novelty_count", "app_protocol_diversity",
]

# Interpretable components -> reason codes (weights sum to 1.0).
COMPONENTS: dict[str, dict] = {
    "NEW_PEER_BURST": {"weight": 0.15, "features": ["log_new_out_peers", "peer_set_change_rate"]},
    "FAN_OUT_DEVIATION": {"weight": 0.12, "features": ["log_out_peers", "log_fan_out"]},
    "FAN_IN_DEVIATION": {"weight": 0.12, "features": ["log_in_peers", "log_fan_in"]},
    "PROTOCOL_DIVERSITY_CHANGE": {"weight": 0.12,
                                  "features": ["out_protocols", "in_protocols",
                                               "protocol_novelty_count", "app_protocol_diversity"]},
    "PORT_DIVERSITY_CHANGE": {"weight": 0.10,
                              "features": ["log_out_ports", "log_in_ports", "log_port_novelty"]},
    "OUTBOUND_VOLUME_DEVIATION": {"weight": 0.12,
                                  "features": ["log_out_conn", "log_out_bytes", "log_out_packets"]},
    "INBOUND_VOLUME_DEVIATION": {"weight": 0.12,
                                 "features": ["log_in_conn", "log_in_bytes", "log_in_packets"]},
    "RELATIONSHIP_CREATION_BURST": {"weight": 0.05, "features": ["log_rel_creation"]},
    "PEER_SET_CHANGE": {"weight": 0.05, "features": ["log_new_in_peers"]},
    "COMMUNICATION_RATIO_SHIFT": {"weight": 0.05,
                                  "features": ["out_in_conn_ratio", "out_in_bytes_ratio"]},
}

REASON_CODES = list(COMPONENTS)
