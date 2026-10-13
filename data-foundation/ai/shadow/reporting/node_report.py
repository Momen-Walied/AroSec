"""Node shadow analytics + edge/node complementarity (analysis only; NO fusion)."""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd


def node_analytics(node_records: list, threshold: float, site: str = "replay_site") -> dict:
    n = len(node_records)
    if n == 0:
        return {"records": 0}
    wins = [r.feature_window for r in node_records]
    scores = np.asarray([r.anomaly_result.anomaly_score for r in node_records])
    span = max((max(w.window_start for w in wins) - min(w.window_start for w in wins)).total_seconds() / 86400.0, 1e-9)
    n_entities = len({w.asset_id for w in wins})
    severity = Counter(str(r.anomaly_result.severity) for r in node_records)
    reasons = Counter()
    for r in node_records:
        for reason in r.anomaly_result.reasons:
            reasons[reason.code] += 1
    alerts = int((scores >= threshold).sum())
    return {
        "records": n, "span_days": span, "site": site,
        "scored_windows": n, "scored_windows_per_day": n / span,
        "alerts": alerts, "alert_rate": alerts / n,
        "alerts_per_site_per_day": alerts / span,
        "alerts_per_entity_per_day": alerts / max(n_entities, 1) / span,
        "score_percentiles": {p: float(np.percentile(scores, int(p[1:]))) for p in ("p50", "p90", "p95", "p99")},
        "severity_distribution": dict(severity),
        "top_reasons": reasons.most_common(10),
        "reason_frequency": {c: reasons.get(c, 0) / n for c in (
            "FAN_OUT_DEVIATION", "FAN_IN_DEVIATION", "NEW_PEER_BURST", "PEER_SET_CHANGE",
            "RELATIONSHIP_CREATION_BURST", "PROTOCOL_DIVERSITY_CHANGE", "PORT_DIVERSITY_CHANGE",
            "OUTBOUND_VOLUME_DEVIATION", "INBOUND_VOLUME_DEVIATION", "COMMUNICATION_RATIO_SHIFT")},
        "unique_entities": n_entities,
    }


def _win(ts) -> pd.Timestamp:
    return pd.Timestamp(ts)


def complementarity(edge_records: list, node_records: list, edge_threshold: float,
                    node_threshold: float) -> dict:
    edge_alert_windows: dict = defaultdict(int)
    for r in edge_records:
        if r.anomaly_result.anomaly_score >= edge_threshold:
            edge_alert_windows[_win(r.feature_window.window_start)] += 1
    node_alert_windows: set = set()
    for r in node_records:
        if r.anomaly_result.anomaly_score >= node_threshold:
            node_alert_windows.add(_win(r.feature_window.window_start))

    all_windows = set(edge_alert_windows) | node_alert_windows
    e_set = set(edge_alert_windows)
    both = e_set & node_alert_windows
    edge_only = e_set - node_alert_windows
    node_only = node_alert_windows - e_set
    total = max(len(all_windows), 1)
    edge_alerts_per_node_window = (
        float(np.mean([edge_alert_windows[w] for w in node_alert_windows])) if node_alert_windows else 0.0)
    node_alerts_with_edge = len(both) / max(len(node_alert_windows), 1)
    edge_alerts_while_node_normal = len(edge_only) / max(len(e_set), 1)
    return {
        "both": len(both), "edge_only": len(edge_only), "node_only": len(node_only),
        "pct_both": len(both) / total, "pct_edge_only": len(edge_only) / total,
        "pct_node_only": len(node_only) / total,
        "pct_neither": 0.0,
        "edge_alerts_per_node_alert_window": edge_alerts_per_node_window,
        "pct_node_alerts_with_edge": node_alerts_with_edge,
        "pct_edge_alerts_while_node_normal": edge_alerts_while_node_normal,
    }


def window_correlation(edge_records: list, node_records: list) -> dict:
    e = pd.Series({_win(r.feature_window.window_start): r.anomaly_result.anomaly_score for r in edge_records})
    n = pd.Series({_win(r.feature_window.window_start): r.anomaly_result.anomaly_score for r in node_records})
    e = e.groupby(level=0).max()
    n = n.groupby(level=0).max()
    joined = pd.concat([e.rename("edge"), n.rename("node")], axis=1).dropna()
    if len(joined) < 2:
        return {"windows": len(joined), "pearson": 0.0, "spearman": 0.0}
    ev, nv = joined["edge"].to_numpy(), joined["node"].to_numpy()
    def _pear(a, b):
        return float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else 0.0
    return {"windows": int(len(joined)), "pearson": _pear(ev, nv),
            "spearman": _pear(pd.Series(ev).rank().to_numpy(), pd.Series(nv).rank().to_numpy())}


def incident_grouping(node_records: list, edge_records: list, edge_threshold: float,
                      node_threshold: float, top_k: int = 10) -> list[dict]:
    """Analysis-only view: node anomaly + related edge anomalies. NO combined score."""
    by_window_edge: dict = defaultdict(list)
    for r in edge_records:
        by_window_edge[_win(r.feature_window.window_start)].append(r)
    node_alerts = sorted((r for r in node_records if r.anomaly_result.anomaly_score >= node_threshold),
                         key=lambda r: -r.anomaly_result.anomaly_score)[:top_k]
    out = []
    for r in node_alerts:
        asset = r.feature_window.asset_id
        w = _win(r.feature_window.window_start)
        related = []
        for e in by_window_edge.get(w, []):
            fw = e.feature_window
            if fw.src_asset_id == asset or fw.dst_asset_id == asset:
                related.append({"edge": f"{fw.src_asset_id.split(':')[-1]}->{fw.dst_asset_id.split(':')[-1]}",
                                "score": round(e.anomaly_result.anomaly_score, 3),
                                "alert": e.anomaly_result.anomaly_score >= edge_threshold})
        out.append({
            "asset": asset,
            "window_start": w.isoformat(),
            "node_score": round(r.anomaly_result.anomaly_score, 3),
            "node_severity": str(r.anomaly_result.severity),
            "node_reasons": [x.code for x in r.anomaly_result.reasons],
            "related_edges": related,
        })
    return out
