"""Shadow analytics from stored inference records (no dashboard)."""
from __future__ import annotations

from collections import Counter

import numpy as np

from ai.contracts.shadow_records import ShadowInferenceRecordV1


def _pct(values: list[float]) -> dict:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    a = np.asarray(values, dtype=float)
    return {p: float(np.percentile(a, int(p[1:]))) for p in ("p50", "p90", "p95", "p99")}


def shadow_analytics(records: list[ShadowInferenceRecordV1], threshold: float,
                     site_name: str = "replay_site") -> dict:
    n = len(records)
    if n == 0:
        return {"records": 0}
    windows = [r.feature_window for r in records]
    scores = [r.anomaly_result.anomaly_score for r in records]
    alerts = [s >= threshold for s in scores]
    span_days = max(
        (max(w.window_start for w in windows) - min(w.window_start for w in windows)).total_seconds() / 86400.0,
        1e-9)
    n_assets = len({w.src_asset_id for w in windows})
    n_rel = len({w.relationship_id for w in windows})

    severity = Counter(str(r.anomaly_result.severity) for r in records)
    reasons = Counter()
    for r in records:
        for reason in r.anomaly_result.reasons:
            reasons[reason.code] += 1
    by_identity: dict[str, list[float]] = {}
    for r in records:
        by_identity.setdefault(str(r.identity_method), []).append(r.anomaly_result.anomaly_score)
    latency = [r.processing_latency_ms for r in records]

    daily_alerts: dict[str, list[int]] = {}
    for r in records:
        day = r.feature_window.window_start.date().isoformat()
        daily_alerts.setdefault(day, []).append(int(r.anomaly_result.anomaly_score >= threshold))
    alert_rate_by_day = {d: float(np.mean(v)) for d, v in sorted(daily_alerts.items())}

    n_alert = int(sum(alerts))
    return {
        "records": n,
        "span_days": span_days,
        "scored_windows": n,
        "scored_windows_per_day": n / span_days,
        "alerts": n_alert,
        "alert_rate": n_alert / n,
        "alerts_per_site_per_day": n_alert / span_days,
        "alerts_per_asset_per_day": n_alert / max(n_assets, 1) / span_days,
        "alerts_per_relationship_per_day": n_alert / max(n_rel, 1) / span_days,
        "score_percentiles": _pct(scores),
        "severity_distribution": dict(severity),
        "top_reasons": reasons.most_common(10),
        "novelty_frequency": {
            code: reasons.get(code, 0) / n
            for code in ("NEW_PEER", "PORT_NOVELTY", "PROTOCOL_NOVELTY",
                         "FAN_OUT_DEVIATION", "TRAFFIC_VOLUME_DEVIATION",
                         "APP_PROTOCOL_NOVELTY")
        },
        "score_by_identity_method": {k: _pct(v) for k, v in by_identity.items()},
        "processing_latency_ms": _pct(latency),
        "alert_rate_by_day": alert_rate_by_day,
        "unique_assets": n_assets,
        "unique_relationships": n_rel,
        "site": site_name,
    }


def render_markdown(analytics: dict, title: str = "Shadow Replay Evaluation") -> str:
    if not analytics.get("records"):
        return f"# {title}\n\n_No records._\n"
    lines = [f"# {title}", "",
             f"- site (synthetic operational framing): `{analytics['site']}`",
             f"- scored windows: {analytics['scored_windows']} over {analytics['span_days']:.2f} days",
             f"- alerts: {analytics['alerts']} (rate {analytics['alert_rate']:.4f})",
             f"- alerts/site/day: {analytics['alerts_per_site_per_day']:.1f}",
             f"- alerts/asset/day: {analytics['alerts_per_asset_per_day']:.2f}",
             f"- alerts/relationship/day: {analytics['alerts_per_relationship_per_day']:.3f}",
             "", "## Score percentiles", "",
             "| p50 | p90 | p95 | p99 |", "|---|---|---|---|",
             "| {p50:.3f} | {p90:.3f} | {p95:.3f} | {p99:.3f} |".format(
                 **analytics["score_percentiles"]), "",
             "## Severity distribution", ""]
    for k, v in sorted(analytics["severity_distribution"].items()):
        lines.append(f"- {k}: {v}")
    lines += ["", "## Top reasons", ""]
    for code, count in analytics["top_reasons"]:
        lines.append(f"- {code}: {count}")
    lines += ["", "## Novelty frequency (share of scored windows)", ""]
    for code, freq in analytics["novelty_frequency"].items():
        lines.append(f"- {code}: {freq:.4f}")
    lines += ["", "## Processing latency (ms)", "",
              "| p50 | p90 | p95 | p99 |", "|---|---|---|---|",
              "| {p50:.3f} | {p90:.3f} | {p95:.3f} | {p99:.3f} |".format(
                  **analytics["processing_latency_ms"]), ""]
    return "\n".join(lines) + "\n"
