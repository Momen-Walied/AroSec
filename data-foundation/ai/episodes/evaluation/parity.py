"""Offline/online Behavioral Episode parity comparison (release blocker)."""
from __future__ import annotations


def compare_episodes(offline: list, online: list) -> dict:
    off = {e.episode_id: e for e in offline}
    onl = {e.episode_id: e for e in online}
    rep = {
        "offline_episodes": len(off), "online_episodes": len(onl),
        "id_mismatches_online_only": len(set(onl) - set(off)),
        "id_mismatches_offline_only": len(set(off) - set(onl)),
        "membership_mismatches": 0, "timestamp_mismatches": 0,
        "evidence_mismatches": 0, "severity_mismatches": 0, "primary_asset_mismatches": 0,
        "duration_mismatches": 0, "identity_mismatches": 0, "examples": [],
    }
    for eid in set(off) & set(onl):
        a, b = off[eid], onl[eid]
        if (set(a.edge_signal_ids) != set(b.edge_signal_ids)
                or set(a.node_signal_ids) != set(b.node_signal_ids)
                or set(a.involved_asset_ids) != set(b.involved_asset_ids)
                or set(a.relationship_ids) != set(b.relationship_ids)):
            rep["membership_mismatches"] += 1
        if (a.start_time != b.start_time) or (a.end_time != b.end_time):
            rep["timestamp_mismatches"] += 1
        if (set(a.evidence_families) != set(b.evidence_families)
                or set(a.signal_reason_codes) != set(b.signal_reason_codes)
                or set(a.evidence_refs) != set(b.evidence_refs)):
            rep["evidence_mismatches"] += 1
        if str(a.episode_severity) != str(b.episode_severity):
            rep["severity_mismatches"] += 1
        if a.primary_asset_id != b.primary_asset_id:
            rep["primary_asset_mismatches"] += 1
        if abs(a.duration_seconds - b.duration_seconds) > 1e-6:
            rep["duration_mismatches"] += 1
        if (set(a.identity_methods) != set(b.identity_methods)
                or a.minimum_identity_confidence != b.minimum_identity_confidence):
            rep["identity_mismatches"] += 1
    rep["total_mismatches"] = (
        rep["id_mismatches_online_only"] + rep["id_mismatches_offline_only"]
        + rep["membership_mismatches"] + rep["timestamp_mismatches"] + rep["evidence_mismatches"]
        + rep["severity_mismatches"] + rep["primary_asset_mismatches"] + rep["duration_mismatches"]
        + rep["identity_mismatches"])
    return rep
