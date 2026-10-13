"""Behavioral Episode v1 configuration: evidence families, gaps, rubric.

Deterministic, explainable correlation — NO ML, NO score fusion, NO attack taxonomy.
"""
from __future__ import annotations

# reason code -> evidence family (edge AND node codes)
EVIDENCE_FAMILIES: dict[str, str] = {
    # peer novelty / relationship creation
    "NEW_PEER": "PEER_NOVELTY",
    "NEW_PEER_BURST": "PEER_NOVELTY",
    "RELATIONSHIP_CREATION_BURST": "PEER_NOVELTY",
    # topology spread
    "FAN_OUT_DEVIATION": "TOPOLOGY_SPREAD",
    "FAN_IN_DEVIATION": "TOPOLOGY_SPREAD",
    # protocol
    "PROTOCOL_NOVELTY": "PROTOCOL_CHANGE",
    "PROTOCOL_DIVERSITY_CHANGE": "PROTOCOL_CHANGE",
    "APP_PROTOCOL_NOVELTY": "PROTOCOL_CHANGE",
    # port
    "PORT_NOVELTY": "PORT_CHANGE",
    "PORT_DIVERSITY": "PORT_CHANGE",
    "PORT_DIVERSITY_CHANGE": "PORT_CHANGE",
    # traffic volume
    "TRAFFIC_VOLUME_DEVIATION": "TRAFFIC_VOLUME",
    "OUTBOUND_VOLUME_DEVIATION": "TRAFFIC_VOLUME",
    "INBOUND_VOLUME_DEVIATION": "TRAFFIC_VOLUME",
    # directional
    "COMMUNICATION_RATIO_SHIFT": "DIRECTIONAL_CHANGE",
    # peer set
    "PEER_SET_CHANGE": "PEER_SET_CHANGE",
}
DEFAULT_FAMILY = "OTHER"

EVIDENCE_FAMILY_ORDER = [
    "PEER_NOVELTY", "TOPOLOGY_SPREAD", "PROTOCOL_CHANGE", "PORT_CHANGE",
    "TRAFFIC_VOLUME", "DIRECTIONAL_CHANGE", "PEER_SET_CHANGE", "OTHER",
]

CORRELATION_GAPS_SECONDS = [30, 60, 120, 300]
DEFAULT_CORRELATION_GAP_SECONDS = 60
DEFAULT_MAX_EPISODE_DURATION_SECONDS = 600  # caps episode percolation

SEVERITY_ORDER = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def family_for(reason_code: str) -> str:
    return EVIDENCE_FAMILIES.get(reason_code, DEFAULT_FAMILY)


def families_for(reason_codes: list[str]) -> list[str]:
    seen = {family_for(r) for r in reason_codes}
    return [f for f in EVIDENCE_FAMILY_ORDER if f in seen]
