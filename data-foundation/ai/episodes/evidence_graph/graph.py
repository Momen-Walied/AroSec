"""Small structured evidence graph for an episode (analyst explanations; NOT a GNN)."""
from __future__ import annotations

from ai.episodes.contracts.behavioral_episode import BehavioralEpisodeV1
from ai.episodes.correlator.signals import Signal


def build_evidence_graph(episode: BehavioralEpisodeV1, signal_lookup: dict[str, Signal]) -> dict:
    ids = list(episode.edge_signal_ids) + list(episode.node_signal_ids)
    signals = []
    for sid in ids:
        s = signal_lookup.get(sid)
        if s is None:
            continue
        signals.append({
            "signal_id": s.signal_id, "type": s.signal_type, "assets": list(s.asset_ids),
            "relationship": s.relationship_id, "score": s.score, "reasons": list(s.reason_codes),
        })
    edges = []
    for rel in episode.relationship_ids:
        parts = rel.split("|")
        if len(parts) >= 2:
            src = parts[0].replace("rel:", "", 1)
            dst = parts[1]
            edges.append({"from": src, "to": dst, "relationship_id": rel})
    return {
        "episode_id": episode.episode_id,
        "episode_type": "behavioral",
        "assets": list(episode.involved_asset_ids),
        "relationships": list(episode.relationship_ids),
        "edges": edges,
        "signals": signals,
        "evidence_families": list(episode.evidence_families),
        "evidence_strength": str(episode.evidence_strength),
    }
