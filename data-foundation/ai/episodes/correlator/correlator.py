"""Deterministic, explainable, streaming-compatible behavioral episode correlator.

Signals are processed CHRONOLOGICALLY. An episode is a bounded connected temporal component
of the evidence graph: two signals join the same episode only if they are (A) temporally
close (within ``correlation_gap_seconds``) AND (B) relationally connected (share an asset /
relationship endpoint). An episode cannot extend beyond ``max_episode_duration_seconds`` from
its start, which bounds percolation. NO score fusion; NO attack semantics.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from ai.episodes.config import SEVERITY_ORDER, families_for
from ai.episodes.contracts.behavioral_episode import (
    BehavioralEpisodeV1,
    EpisodeStatus,
    EvidenceStrength,
)
from ai.episodes.correlator.signals import Signal


@dataclass
class _Active:
    episode_id: str
    start_time: datetime
    end_time: datetime
    first_signal_id: str
    signals: list[Signal] = field(default_factory=list)
    asset_ids: set[str] = field(default_factory=set)
    relationship_ids: set[str] = field(default_factory=set)
    reason_codes: set[str] = field(default_factory=set)

    def absorb(self, other: _Active) -> None:
        self.signals.extend(other.signals)
        self.asset_ids |= other.asset_ids
        self.relationship_ids |= other.relationship_ids
        self.reason_codes |= other.reason_codes
        self.end_time = max(self.end_time, other.end_time)


def _episode_id(start_time: datetime, first_signal_id: str) -> str:
    raw = f"{start_time.isoformat()}|{first_signal_id}"
    return "episode:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


class BehavioralEpisodeCorrelator:
    def __init__(self, correlation_gap_seconds: int = 60,
                 max_episode_duration_seconds: int = 600,
                 identity_map: dict | None = None) -> None:
        self.gap = correlation_gap_seconds
        self.max_duration = max_episode_duration_seconds
        self.identity_map = identity_map or {}
        self.active: dict[str, _Active] = {}

    # ------------------------------------------------------------------ #
    def add(self, signal: Signal) -> list[BehavioralEpisodeV1]:
        closed: list[BehavioralEpisodeV1] = []
        for eid in list(self.active):
            ep = self.active[eid]
            if (signal.window_start - ep.end_time).total_seconds() > self.gap:
                closed.append(self._finalize(ep, "timeout"))
                del self.active[eid]

        connected = [
            ep for ep in self.active.values()
            if (ep.asset_ids & set(signal.asset_ids))
            and (signal.window_start - ep.start_time).total_seconds() <= self.max_duration
        ]
        if not connected:
            self._create(signal)
        elif len(connected) == 1:
            self._extend(connected[0], signal)
        else:
            canonical = min(connected, key=lambda e: (e.start_time, e.episode_id))
            for ep in connected:
                if ep is canonical:
                    continue
                canonical.absorb(ep)
                del self.active[ep.episode_id]
            self._extend(canonical, signal)
        return closed

    def flush(self) -> list[BehavioralEpisodeV1]:
        out = [self._finalize(ep, "end_of_stream") for ep in self.active.values()]
        self.active = {}
        return out

    # ------------------------------------------------------------------ #
    def _create(self, signal: Signal) -> None:
        eid = _episode_id(signal.window_start, signal.signal_id)
        ep = _Active(episode_id=eid, start_time=signal.window_start, end_time=signal.window_end,
                     first_signal_id=signal.signal_id)
        self._extend(ep, signal)
        self.active[eid] = ep

    def _extend(self, ep: _Active, signal: Signal) -> None:
        ep.signals.append(signal)
        ep.asset_ids |= set(signal.asset_ids)
        if signal.relationship_id:
            ep.relationship_ids.add(signal.relationship_id)
        ep.reason_codes |= set(signal.reason_codes)
        if signal.window_end > ep.end_time:
            ep.end_time = signal.window_end
        if signal.window_start < ep.start_time:
            ep.start_time = signal.window_start

    def _finalize(self, ep: _Active, close_reason: str) -> BehavioralEpisodeV1:
        edge = [s for s in ep.signals if s.signal_type == "edge"]
        node = [s for s in ep.signals if s.signal_type == "node"]
        families = families_for(sorted(ep.reason_codes))
        signal_types = {s.signal_type for s in ep.signals}
        reasons = sorted(ep.reason_codes)
        evidence_refs: list[str] = []
        for s in ep.signals:
            for ref in s.evidence_refs:
                if ref not in evidence_refs:
                    evidence_refs.append(ref)
        methods: list[str] = []
        confs: list[float] = []
        for a in sorted(ep.asset_ids):
            ident = self.identity_map.get(a, {})
            m = ident.get("identity_method")
            if m and m not in methods:
                methods.append(m)
            c = ident.get("identity_confidence")
            if c is not None:
                confs.append(float(c))
        severity = self._severity(ep.signals)
        strength = self._strength(len(ep.signals), len(families), len(signal_types))
        primary = self._primary_asset(ep, node)
        duration = (ep.end_time - ep.start_time).total_seconds()
        max_edge = max((s.score for s in edge), default=None)
        max_node = max((s.score for s in node), default=None)
        return BehavioralEpisodeV1(
            episode_id=ep.episode_id, start_time=ep.start_time, end_time=ep.end_time,
            duration_seconds=max(duration, 0.0), status=EpisodeStatus.CLOSED,
            involved_asset_ids=sorted(ep.asset_ids), relationship_ids=sorted(ep.relationship_ids),
            edge_signal_ids=sorted(s.signal_id for s in edge),
            node_signal_ids=sorted(s.signal_id for s in node),
            edge_signal_count=len(edge), node_signal_count=len(node),
            max_edge_score=max_edge, max_node_score=max_node,
            signal_reason_codes=reasons, evidence_families=families, evidence_refs=evidence_refs[:50],
            identity_methods=methods, minimum_identity_confidence=(min(confs) if confs else None),
            primary_asset_id=primary, episode_severity=severity, evidence_strength=strength,
            context={"close_reason": close_reason, "signal_types": sorted(signal_types),
                     "correlation_gap_seconds": self.gap, "max_episode_duration_seconds": self.max_duration},
            summary={"episode_type": "behavioral", "summary": {
                "entities": len(ep.asset_ids), "relationships": len(ep.relationship_ids),
                "edge_signals": len(edge), "node_signals": len(node),
                "evidence_families": families}},
            created_at=ep.start_time, closed_at=ep.end_time)

    @staticmethod
    def _severity(signals: list[Signal]) -> str:
        best = "INFO"
        for s in signals:
            if SEVERITY_ORDER.index(s.severity) > SEVERITY_ORDER.index(best):
                best = s.severity
        return best

    @staticmethod
    def _strength(n_signals: int, n_families: int, n_types: int) -> EvidenceStrength:
        if n_signals == 1:
            return EvidenceStrength.WEAK
        if n_families >= 2 and n_types == 2:
            return EvidenceStrength.STRONG
        if n_families >= 2 or n_types == 2 or n_signals >= 3:
            return EvidenceStrength.MODERATE
        return EvidenceStrength.WEAK

    @staticmethod
    def _primary_asset(ep: _Active, node_signals: list[Signal]) -> str | None:
        node_assets = {s.asset_ids[0] for s in node_signals}
        if len(node_assets) == 1:
            return next(iter(node_assets))
        counts: dict[str, int] = {}
        for s in ep.signals:
            if s.signal_type == "edge":
                for a in s.asset_ids:
                    counts[a] = counts.get(a, 0) + 1
        if counts:
            top = max(counts.values())
            winners = sorted(a for a, c in counts.items() if c == top)
            if len(winners) == 1:
                return winners[0]
        return None


def correlate(signals: list[Signal], correlation_gap_seconds: int = 60,
              max_episode_duration_seconds: int = 600,
              identity_map: dict | None = None) -> list[BehavioralEpisodeV1]:
    """Correlate a chronological signal list into closed Behavioral Episodes."""
    corr = BehavioralEpisodeCorrelator(correlation_gap_seconds, max_episode_duration_seconds, identity_map)
    episodes: list[BehavioralEpisodeV1] = []
    for s in sorted(signals, key=lambda x: (x.window_start, x.signal_type, x.signal_id)):
        episodes.extend(corr.add(s))
    episodes.extend(corr.flush())
    episodes.sort(key=lambda e: (e.start_time, e.episode_id))
    return episodes
