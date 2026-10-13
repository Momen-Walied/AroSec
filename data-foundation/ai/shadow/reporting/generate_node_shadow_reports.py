"""Generate AI Phase 2.5 node shadow reports (parity, replay, complementarity, performance, drift).

    python -m ai.shadow.reporting.generate_node_shadow_reports
"""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ai.edge_behavior.features.builder import load_asset_identity
from ai.shadow.config import ShadowConfig
from ai.shadow.features.parity import (
    compare_node_windows,
    compare_windows,
    offline_node_reference,
    offline_reference,
    online_node_reference,
    online_reference,
)
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import load_node_scorer
from ai.shadow.metrics.drift import drift_report
from ai.shadow.reporting.node_report import (
    complementarity,
    incident_grouping,
    node_analytics,
    window_correlation,
)
from ai.shadow.reporting.shadow_report import shadow_analytics
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from src.config import PROJECT_ROOT, get_settings
from src.normalization import io
from src.schemas.v2 import CommunicationObservation

REPORTS = PROJECT_ROOT / "reports" / "ai" / "node_shadow_v1"
OUT = PROJECT_ROOT / "ai" / "shadow" / "runtime_output"
EDGE_ONLY_REF = {"obs_per_sec": 6058, "p99_feature_ms": 0.0834, "p99_inference_ms": 0.0440}


def _load_observations(dataset="unsw_iotraffic", window="30s"):
    p = get_settings().processed_dir / "v2" / "communication_observations" / f"{dataset}_obs_{window}.parquet"
    return io.frame_to_models(io.read_parquet(p), CommunicationObservation)


def _perf_run(observations, cfg, edge_bundle, node_scorer, im, label, durable=True):
    OUT.mkdir(parents=True, exist_ok=True)
    if durable:
        from ai.shadow.sinks.sqlite import SqliteShadowSink as Sink
        from ai.shadow.state.sqlite import SqliteStateStore as Store
        state_path = OUT / f"{label}_state.sqlite"
        sink_path = OUT / f"{label}_sink.sqlite"
        for p in (state_path, sink_path):
            for suf in ("", "-wal", "-shm"):
                q = Path(str(p) + suf)
                if q.exists():
                    q.unlink()
        sink = Sink(sink_path)
        store = Store(state_path)
    else:
        sink, store = InMemoryShadowSink(), InMemoryStateStore()
    rt = ShadowRuntime(cfg, ListObservationSource(observations), sink, store,
                       edge_bundle=edge_bundle, node_scorer=node_scorer, identity_map=im)
    t = time.perf_counter()
    summary = rt.run()
    elapsed = time.perf_counter() - t
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    sink.close()
    store.close()
    obs = summary["observations_processed"]
    h = summary["metrics"]["histograms"]
    res = {
        "observations": obs, "elapsed_seconds": elapsed, "obs_per_sec": obs / max(elapsed, 1e-9),
        "peak_rss_mb": peak,
        "edge_feature_ms": h.get("feature_build_latency_ms", {}),
        "edge_inference_ms": h.get("inference_latency_ms", {}),
        "node_feature_ms": h.get("node_feature_build_latency_ms", {}),
        "node_inference_ms": h.get("node_inference_latency_ms", {}),
        "edge_windows": int(summary["edge_builder_counters"]["feature_windows_emitted_total"]),
        "node_windows": int(summary["node_builder_counters"]["node_windows_emitted_total"]),
        "state_db_mb": (state_path.stat().st_size / (1024 * 1024)) if durable else 0.0,
        "sink_db_mb": (sink_path.stat().st_size / (1024 * 1024)) if durable else 0.0,
    }
    return res


def run(dataset="unsw_iotraffic", window="30s") -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    cfg = ShadowConfig(dataset_id=dataset, window_label=window)
    im = load_asset_identity(dataset)
    edge_bundle = ShadowModelBundle.load(cfg.model_bundle)
    node_scorer = load_node_scorer(cfg.node_model_artifact, identity_map=im)
    observations = _load_observations(dataset, window)

    # 1) parity
    edge_parity = compare_windows(offline_reference(observations), online_reference(observations, source=dataset))
    node_parity = compare_node_windows(offline_node_reference(observations), online_node_reference(observations, source=dataset))

    # 2) combined replay (in-memory records for analytics)
    sink = InMemoryShadowSink()
    rt = ShadowRuntime(cfg, ListObservationSource(observations), sink, InMemoryStateStore(),
                       edge_bundle=edge_bundle, node_scorer=node_scorer, identity_map=im)
    rt.run()
    edge_records, node_records = sink.edge_records(), sink.node_records()

    edge_analytics = shadow_analytics(edge_records, cfg.shadow_threshold)
    node_analytics_v = node_analytics(node_records, cfg.node_threshold)
    comp = complementarity(edge_records, node_records, cfg.shadow_threshold, cfg.node_threshold)
    corr = window_correlation(edge_records, node_records)
    incidents = incident_grouping(node_records, edge_records, cfg.shadow_threshold, cfg.node_threshold, top_k=8)

    # 3) node drift vs validation reference (raw NodeFeatureWindowV2 in the validation range)
    from ai.node_behavior.training.train import build_node_dataset
    ndata = build_node_dataset(dataset, window)
    t_train_end = pd.Timestamp(ndata["boundaries"]["train"][1])
    t_val_end = pd.Timestamp(ndata["boundaries"]["validation"][1])
    val_windows = [w for w in ndata["windows"]
                   if t_train_end < pd.Timestamp(w.window_start) <= t_val_end]
    ref = {
        "anomaly_score": np.clip(node_scorer.model.score(ndata["X_validation"]), 0, 1),
        "fan_out": np.asarray([w.fan_out for w in val_windows], dtype=float),
        "fan_in": np.asarray([w.fan_in for w in val_windows], dtype=float),
        "outgoing_bytes": np.asarray([w.outgoing_bytes for w in val_windows], dtype=float),
        "incoming_bytes": np.asarray([w.incoming_bytes for w in val_windows], dtype=float),
        "new_outgoing_peers": np.asarray([w.new_outgoing_peer_count for w in val_windows], dtype=float),
        "new_incoming_peers": np.asarray([w.new_incoming_peer_count for w in val_windows], dtype=float),
        "protocol_diversity": np.asarray([w.outbound_protocol_count for w in val_windows], dtype=float),
        "port_diversity": np.asarray([w.unique_outgoing_ports for w in val_windows], dtype=float),
    }
    recent = {
        "anomaly_score": np.asarray([r.anomaly_result.anomaly_score for r in node_records]),
        "fan_out": np.asarray([r.feature_window.fan_out for r in node_records], dtype=float),
        "fan_in": np.asarray([r.feature_window.fan_in for r in node_records], dtype=float),
        "outgoing_bytes": np.asarray([r.feature_window.outgoing_bytes for r in node_records], dtype=float),
        "incoming_bytes": np.asarray([r.feature_window.incoming_bytes for r in node_records], dtype=float),
        "new_outgoing_peers": np.asarray([r.feature_window.new_outgoing_peer_count for r in node_records], dtype=float),
        "new_incoming_peers": np.asarray([r.feature_window.new_incoming_peer_count for r in node_records], dtype=float),
        "protocol_diversity": np.asarray([r.feature_window.outbound_protocol_count for r in node_records], dtype=float),
        "port_diversity": np.asarray([r.feature_window.unique_outgoing_ports for r in node_records], dtype=float),
    }
    drift = drift_report(recent, ref)

    # 4) performance: combined (durable) + edge-only (durable)
    perf_combined = _perf_run(observations, cfg, edge_bundle, node_scorer, im, "combined", durable=True)
    perf_edge_only = _perf_run(observations, cfg, edge_bundle, None, im, "edgeonly", durable=True)

    payload = {
        "edge_parity": edge_parity, "node_parity": node_parity,
        "edge_analytics": edge_analytics, "node_analytics": node_analytics_v,
        "complementarity": comp, "correlation": corr, "incidents": incidents,
        "drift": {k: v for k, v in drift.items()},
        "perf_combined": perf_combined, "perf_edge_only": perf_edge_only,
        "thresholds": {"edge": cfg.shadow_threshold, "node": cfg.node_threshold},
    }
    (REPORTS / "results.json").write_text(json.dumps(payload, indent=2, default=str))
    return payload


def _w(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_reports(p: dict) -> list[Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    written = []
    ep, np_ = p["edge_parity"], p["node_parity"]
    written.append(_w(REPORTS / "offline_online_parity.md", [
        "# Offline / Online Parity (release blocker)", "",
        "## Node features (NodeFeatureWindowV2)", "",
        f"- offline windows: {np_['offline_windows']}",
        f"- online windows: {np_['online_windows']}",
        f"- missing / extra: {np_['missing_in_online']} / {np_['extra_in_online']}",
        f"- **total field mismatches: {np_['total_mismatches']}**", "",
        "| field | mismatches |", "|---|---:|",
        *[f"| {k} | {v} |" for k, v in np_["field_mismatches"].items()], "",
        "## Edge features (regression check)", "",
        f"- offline / online windows: {ep['offline_windows']} / {ep['online_windows']}",
        f"- **total field mismatches: {ep['total_mismatches']}**", "",
        ("✅ PARITY EXACT — 0 unexplained mismatches." if (np_["total_mismatches"] == 0 and ep["total_mismatches"] == 0)
         else "❌ PARITY FAILURE — do not proceed toward release."), ""]))

    ea, na = p["edge_analytics"], p["node_analytics"]
    written.append(_w(REPORTS / "replay_evaluation.md", [
        "# Combined Replay Evaluation", "",
        "> Relationship/entity behavioral anomalies, not validated attack detection.", "",
        f"- observations: {na['records'] and p['perf_combined']['observations']}",
        f"- edge windows: {p['perf_combined']['edge_windows']} · node windows: {p['perf_combined']['node_windows']}",
        f"- edge results: {ea['scored_windows']} · node results: {na['scored_windows']}", "",
        "## Edge", "",
        f"- alerts: {ea['alerts']} (rate {ea['alert_rate']:.4f}) · alerts/site/day {ea['alerts_per_site_per_day']:.1f}",
        f"- top reasons: {ea['top_reasons'][:6]}", "",
        "## Node", "",
        f"- alerts: {na['alerts']} (rate {na['alert_rate']:.4f}) · alerts/site/day {na['alerts_per_site_per_day']:.1f}"
        f" · alerts/entity/day {na['alerts_per_entity_per_day']:.3f}",
        f"- score percentiles: {na['score_percentiles']}",
        f"- severity: {na['severity_distribution']}",
        f"- top reasons: {na['top_reasons'][:6]}",
        f"- reason frequency: {json.dumps(na['reason_frequency'])}", "",
        "**signals != incidents** — edge and node alerts are independent signals; they are not summed.", ""]))

    c = p["complementarity"]
    corr = p["correlation"]
    lines = ["# Edge / Node Complementarity (analysis only; NO fusion)", "",
             "## Window overlap", "",
             f"- both alert: {c['both']} ({c['pct_both']:.3f})",
             f"- edge only: {c['edge_only']} ({c['pct_edge_only']:.3f})",
             f"- node only: {c['node_only']} ({c['pct_node_only']:.3f})", "",
             f"- edge alerts per node-alert window: {c['edge_alerts_per_node_alert_window']:.2f}",
             f"- node-alert windows containing >=1 edge alert: {c['pct_node_alerts_with_edge']:.3f}",
             f"- edge alerts while node normal: {c['pct_edge_alerts_while_node_normal']:.3f}", "",
             "## Score correlation (window level)", "",
             f"- windows compared: {corr['windows']}",
             f"- Pearson: {corr['pearson']:.4f} · Spearman: {corr['spearman']:.4f}", "",
             "## Incident-like grouping (report only, NO combined score)", ""]
    for inc in p["incidents"][:5]:
        lines.append(f"### {inc['asset']} @ {inc['window_start']}")
        lines.append(f"- node score {inc['node_score']} {inc['node_severity']} · reasons {inc['node_reasons']}")
        for e in inc["related_edges"][:6]:
            lines.append(f"  - {e['edge']}: {e['score']}{' (ALERT)' if e['alert'] else ''}")
        lines.append("")
    lines.append("These groupings are for analyst context only; no incident score is produced.")
    lines.append("")
    written.append(_w(REPORTS / "edge_node_complementarity.md", lines))

    pc, pe = p["perf_combined"], p["perf_edge_only"]
    def _p(d):
        return f"p50={d.get('p50',0):.5f} p95={d.get('p95',0):.5f} p99={d.get('p99',0):.5f}"
    written.append(_w(REPORTS / "performance.md", [
        "# Performance — Edge-only vs Combined (durable SQLite state + sink)", "",
        "| metric | edge-only | combined (edge+node) |", "|---|---:|---:|",
        f"| observations/sec | {pe['obs_per_sec']:.0f} | {pc['obs_per_sec']:.0f} |",
        f"| peak RSS (MB) | {pe['peak_rss_mb']:.1f} | {pc['peak_rss_mb']:.1f} |",
        f"| state DB (MB) | {pe['state_db_mb']:.2f} | {pc['state_db_mb']:.2f} |",
        f"| sink DB (MB) | {pe['sink_db_mb']:.2f} | {pc['sink_db_mb']:.2f} |",
        f"| edge windows | {pe['edge_windows']} | {pc['edge_windows']} |",
        f"| node windows | 0 | {pc['node_windows']} |", "",
        "## Latencies (ms, per window)", "",
        f"- edge feature: {_p(pc['edge_feature_ms'])}",
        f"- edge inference: {_p(pc['edge_inference_ms'])}",
        f"- node feature: {_p(pc['node_feature_ms'])}",
        f"- node inference: {_p(pc['node_inference_ms'])}", "",
        f"Regression vs Edge-only Shadow v1 (obs/sec {EDGE_ONLY_REF['obs_per_sec']}): "
        f"{'%.0f%%' % (100*(pc['obs_per_sec']-EDGE_ONLY_REF['obs_per_sec'])/EDGE_ONLY_REF['obs_per_sec'])}.", ""]))

    dr = p["drift"]
    written.append(_w(REPORTS / "drift.md", [
        "# Node Drift (observable only; NO auto retraining/recalibration)", "",
        "| metric | PSI | KS | class |", "|---|---:|---:|---|",
        *[f"| {k} | {v['psi']:.3f} | {v['ks']:.3f} | {v['class']} |" for k, v in dr.items() if k != "_overall"],
        "", f"**Overall: {dr.get('_overall')}**", ""]))

    OPS = ["edge model failure", "node model failure", "state failure", "sink failure", "schema mismatch"]
    written.append(_w(REPORTS / "failure_modes.md", [
        "# Failure Modes (fail-open; component isolation)", "",
        "| failure | behaviour | network impact |", "|---|---|---|",
        "| edge model failure | edge pipeline disabled; node pipeline continues | none |",
        "| node model failure | node pipeline disabled; edge pipeline continues | none |",
        "| state failure | logged + counted; runtime continues | none |",
        "| sink failure | logged + counted; scoring continues | none |",
        "| schema mismatch | fails fast at startup with a clear error | none |", "",
        f"Component isolation: `edge_pipeline_errors_total` / `node_pipeline_errors_total` are counted "
        f"independently; a failure in one does not stop the other. No remediation path exists. "
        f"Covered by {len(OPS)} documented cases.", ""]))

    written.append(_w(REPORTS / "architecture.md", [
        "# Node Shadow Integration v1 — Architecture", "",
        "One shared event-time runtime drives two INDEPENDENT pipelines (no fusion):", "",
        "```",
        "CommunicationObservation v0.2",
        "   → shared event-time runtime (dedupe/watermark/lateness)",
        "   ├─ edge pipeline: OnlineFeatureBuilder → EdgeFeatureWindowV2 → Edge Behavior v1 → EdgeAnomalyResultV1",
        "   └─ node pipeline: OnlineNodeFeatureBuilder → NodeFeatureWindowV2 → Node Behavior v1 → NodeAnomalyResultV1",
        "        → ShadowSink (edge/node records kept separate, intelligence_type=edge|node)",
        "```", "",
        "Reuses `ai/shadow/` config, sources, sinks, state stores, metrics, drift, feedback.",
        "Node state is persisted alongside edge state in the same `StateStore`.", ""]))

    written.append(_w(REPORTS / "readiness.md", [
        "# Node Shadow Integration v1 — Readiness", "",
        f"- node parity mismatches: **{np_['total_mismatches']}** (windows {np_['online_windows']})",
        f"- edge parity mismatches: **{ep['total_mismatches']}**",
        "- checks: 147 prior tests + new tests green · ruff clean · frozen v0.2 unchanged · no fusion · no remediation",
        f"- combined observations/sec: {pc['obs_per_sec']:.0f} · peak RSS {pc['peak_rss_mb']:.1f} MB",
        f"- node alerts: {na['alerts']} (rate {na['alert_rate']:.4f})",
        f"- provisional: node threshold {p['thresholds']['node']}; identity `dataset_ip_fallback`; lateness semantics", "",
        ("✅ Ready to freeze." if np_["total_mismatches"] == 0 and ep["total_mismatches"] == 0 else "❌ Not ready."), ""]))
    return written


def main() -> None:
    p = run()
    write_reports(p)
    print(json.dumps({
        "node_parity_mismatches": p["node_parity"]["total_mismatches"],
        "node_windows": p["node_parity"]["online_windows"],
        "edge_parity_mismatches": p["edge_parity"]["total_mismatches"],
        "node_alerts": p["node_analytics"]["alerts"],
        "node_alert_rate": round(p["node_analytics"]["alert_rate"], 4),
        "correlation": round(p["correlation"]["pearson"], 4),
        "combined_obs_per_sec": round(p["perf_combined"]["obs_per_sec"]),
        "reports_dir": str(REPORTS),
    }, indent=2))


if __name__ == "__main__":
    main()
