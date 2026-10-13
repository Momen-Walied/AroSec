"""Signal representation + extraction from shadow Edge/Node anomaly results."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Signal:
    signal_id: str
    signal_type: str            # "edge" | "node"
    window_start: datetime
    window_end: datetime
    score: float
    severity: str
    reason_codes: tuple[str, ...]
    asset_ids: tuple[str, ...]
    relationship_id: str | None
    result_ref: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id, "signal_type": self.signal_type,
            "window_start": self.window_start.isoformat(), "window_end": self.window_end.isoformat(),
            "score": self.score, "severity": self.severity,
            "reason_codes": list(self.reason_codes), "asset_ids": list(self.asset_ids),
            "relationship_id": self.relationship_id, "result_ref": self.result_ref,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Signal:
        return cls(signal_id=d["signal_id"], signal_type=d["signal_type"],
                   window_start=datetime.fromisoformat(d["window_start"]),
                   window_end=datetime.fromisoformat(d["window_end"]), score=float(d["score"]),
                   severity=d["severity"], reason_codes=tuple(d["reason_codes"]),
                   asset_ids=tuple(d["asset_ids"]), relationship_id=d.get("relationship_id"),
                   result_ref=d["result_ref"], evidence_refs=tuple(d["evidence_refs"]))


def _reason_codes(result) -> tuple[str, ...]:
    return tuple(sorted({r.code for r in result.reasons}))


def edge_signals(records: list, threshold: float) -> list[Signal]:
    out: list[Signal] = []
    for r in records:
        if r.intelligence_type != "edge" or r.anomaly_result.anomaly_score < threshold:
            continue
        fw, ar = r.feature_window, r.anomaly_result
        sid = f"sig:edge:{fw.relationship_id}:{fw.window_start.isoformat()}"
        out.append(Signal(
            signal_id=sid, signal_type="edge", window_start=fw.window_start, window_end=fw.window_end,
            score=float(ar.anomaly_score), severity=str(ar.severity), reason_codes=_reason_codes(ar),
            asset_ids=tuple(sorted({fw.src_asset_id, fw.dst_asset_id})),
            relationship_id=fw.relationship_id, result_ref=sid, evidence_refs=tuple(ar.evidence_refs)))
    return out


def node_signals(records: list, threshold: float) -> list[Signal]:
    out: list[Signal] = []
    for r in records:
        if r.intelligence_type != "node" or r.anomaly_result.anomaly_score < threshold:
            continue
        fw, ar = r.feature_window, r.anomaly_result
        sid = f"sig:node:{fw.asset_id}:{fw.window_start.isoformat()}"
        out.append(Signal(
            signal_id=sid, signal_type="node", window_start=fw.window_start, window_end=fw.window_end,
            score=float(ar.anomaly_score), severity=str(ar.severity), reason_codes=_reason_codes(ar),
            asset_ids=(fw.asset_id,), relationship_id=None, result_ref=sid,
            evidence_refs=tuple(ar.evidence_refs)))
    return out


def all_signals(edge_records: list, node_records: list, edge_threshold: float,
                node_threshold: float) -> list[Signal]:
    signals = edge_signals(edge_records, edge_threshold) + node_signals(node_records, node_threshold)
    return sorted(signals, key=lambda s: (s.window_start, s.signal_type, s.signal_id))
