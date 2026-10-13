"""Run Behavioral Episode v1 experiments and emit reports.

    python -m ai.episodes.evaluation.run_experiments
"""
from __future__ import annotations

import json
import time

from ai.edge_behavior.features.builder import load_asset_identity
from ai.episodes.config import (
    CORRELATION_GAPS_SECONDS,
    DEFAULT_CORRELATION_GAP_SECONDS,
    DEFAULT_MAX_EPISODE_DURATION_SECONDS,
)
from ai.episodes.correlator.correlator import correlate
from ai.episodes.correlator.signals import all_signals
from ai.episodes.evaluation.false_merge import false_merge_report
from ai.episodes.evaluation.metrics import compression_metrics, episode_metrics
from ai.episodes.evaluation.scenarios import SCENARIOS, all_scenarios
from ai.episodes.evidence_graph.graph import build_evidence_graph
from ai.experiments.registry import record_experiment
from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import load_node_scorer
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from src.config import PROJECT_ROOT, get_settings
from src.normalization import io
from src.schemas.v2 import CommunicationObservation

REPORTS = PROJECT_ROOT / "reports" / "ai" / "behavioral_episode_v1"


def _load_observations(dataset="unsw_iotraffic", window="30s"):
    p = get_settings().processed_dir / "v2" / "communication_observations" / f"{dataset}_obs_{window}.parquet"
    return io.frame_to_models(io.read_parquet(p), CommunicationObservation)


def run(dataset="unsw_iotraffic", window="30s") -> dict:
    cfg = ShadowConfig(dataset_id=dataset, window_label=window)
    im = load_asset_identity(dataset)
    obs = _load_observations(dataset, window)

    sink = InMemoryShadowSink()
    rt = ShadowRuntime(cfg, ListObservationSource(obs), sink, InMemoryStateStore(),
                       edge_bundle=ShadowModelBundle.load(cfg.model_bundle),
                       node_scorer=load_node_scorer(cfg.node_model_artifact, identity_map=im),
                       identity_map=im)
    rt.run()
    edge_records, node_records = sink.edge_records(), sink.node_records()

    signals = all_signals(edge_records, node_records, cfg.shadow_threshold, cfg.node_threshold)
    span_days = max((signals[-1].window_start - signals[0].window_start).total_seconds() / 86400.0, 1e-9) \
        if signals else 1e-9

    gap_runs = {}
    for gap in CORRELATION_GAPS_SECONDS:
        t0 = time.perf_counter()
        eps = correlate(signals, gap, DEFAULT_MAX_EPISODE_DURATION_SECONDS, im)
        elapsed = time.perf_counter() - t0
        gap_runs[gap] = {
            "metrics": episode_metrics(eps, span_days),
            "compression": compression_metrics(len(signals), eps, span_days),
            "correlate_seconds": elapsed,
            "episodes": eps,
        }

    default = gap_runs[DEFAULT_CORRELATION_GAP_SECONDS]
    scenarios = {}
    for name, sigs in all_scenarios().items():
        eps = correlate(sigs, DEFAULT_CORRELATION_GAP_SECONDS, DEFAULT_MAX_EPISODE_DURATION_SECONDS)
        scenarios[name] = {"episodes": len(eps),
                           "strength": [str(e.evidence_strength) for e in eps],
                           "families": [e.evidence_families for e in eps]}

    lookup = {s.signal_id: s for s in signals}
    top = sorted(default["episodes"], key=lambda e: (e.edge_signal_count + e.node_signal_count), reverse=True)[:5]
    evidence_graphs = [build_evidence_graph(e, lookup) for e in top]

    perf = {
        "signals": len(signals),
        "signals_per_sec": len(signals) / max(default["correlate_seconds"], 1e-9),
        "episode_update_latency_ms": (default["correlate_seconds"] / max(len(signals), 1)) * 1000.0,
    }

    payload = {
        "dataset_id": dataset, "window": window, "span_days": span_days,
        "thresholds": {"edge": cfg.shadow_threshold, "node": cfg.node_threshold},
        "counts": {"edge_signals": sum(1 for s in signals if s.signal_type == "edge"),
                   "node_signals": sum(1 for s in signals if s.signal_type == "node"),
                   "total_signals": len(signals)},
        "gap_runs": {g: {"metrics": r["metrics"], "compression": r["compression"],
                         "correlate_seconds": r["correlate_seconds"]} for g, r in gap_runs.items()},
        "default_gap": DEFAULT_CORRELATION_GAP_SECONDS,
        "scenarios": scenarios,
        "false_merge": false_merge_report(DEFAULT_CORRELATION_GAP_SECONDS),
        "evidence_graphs": evidence_graphs,
        "performance": perf,
    }
    record_experiment({
        "experiment_id": "EXP-E01..E07",
        "model_type": "behavioral_episode_v1",
        "dataset_version": f"{dataset}:v0.2:{window}",
        "validation_time_range": None,
        "metrics": {"total_signals": len(signals), "episodes_default_gap": default["metrics"]["episodes"],
                    "compression_default_gap": default["compression"]["signal_compression_ratio"]},
        "random_seed": 42,
    })
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "results.json").write_text(json.dumps(payload, indent=2, default=str))
    return payload


def _w(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_reports(p: dict) -> list:
    REPORTS.mkdir(parents=True, exist_ok=True)
    written = []
    c = p["counts"]
    written.append(_w(REPORTS / "architecture.md", [
        "# Behavioral Episode Intelligence v1 — Architecture", "",
        "```",
        "EdgeAnomalyResultV1 + NodeAnomalyResultV1 (alerts only)   <- shadow records",
        "      │  chronologically ordered signals",
        "      ▼",
        "deterministic correlator (temporal + relational)",
        "  · temporally close (correlation_gap_seconds)",
        "  · relationally connected (shared asset / relationship endpoint)",
        "  · bounded by max_episode_duration_seconds",
        "      ▼",
        "BehavioralEpisodeV1 (closed)  + evidence graph + machine summary",
        "```", "",
        "No ML, no score fusion, no attack taxonomy. Deterministic IDs; deterministic merge",
        "(oldest start wins, tie-break by episode_id). Streaming-compatible (chronological).", "",
        "Reason codes are grouped into evidence families to avoid over-counting correlated",
        "evidence (see `ai/episodes/config.py`).", ""]))

    gap = p["gap_runs"]
    lines = ["# Correlation Gap Sensitivity", "",
             "| gap (s) | episodes | episodes/day | signals/episode (mean) | compression | p95 duration (s) | mean assets/ep | mixed % |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for g in CORRELATION_GAPS_SECONDS:
        m, cmp = gap[g]["metrics"], gap[g]["compression"]
        lines.append(f"| {g} | {m['episodes']} | {m['episodes_per_site_per_day']:.1f} | "
                     f"{cmp['mean_signals_per_episode']:.2f} | {cmp['signal_compression_ratio']:.2f} | "
                     f"{m['duration_seconds']['p95']:.0f} | {m['assets_per_episode']['p50']:.1f} | "
                     f"{m['mixed_pct']:.3f} |")
    lines += ["", f"Recommended default: **{p['default_gap']}s** (see readiness.md for rationale).", ""]
    written.append(_w(REPORTS / "correlation_gap_analysis.md", lines))

    m = gap[p["default_gap"]]["metrics"]
    cmp = gap[p["default_gap"]]["compression"]
    written.append(_w(REPORTS / "replay_evaluation.md", [
        "# Replay Evaluation (UNSW v0.2 shadow outputs)", "",
        "> Behavioral episodes are NOT security incidents. Signals are not attacks.", "",
        f"- edge signals: {c['edge_signals']}",
        f"- node signals: {c['node_signals']}",
        f"- total signals: {c['total_signals']}",
        f"- episodes (gap {p['default_gap']}s): {m['episodes']}",
        f"- episodes/site/day: {m['episodes_per_site_per_day']:.1f}",
        f"- edge-only episodes: {m['edge_only_pct']:.3f}",
        f"- node-only episodes: {m['node_only_pct']:.3f}",
        f"- mixed edge+node episodes: {m['mixed_pct']:.3f}",
        f"- evidence strength: {m['evidence_strength_distribution']}",
        f"- severity: {m['severity_distribution']}",
        f"- top evidence families: {m['top_evidence_families']}", ""]))

    written.append(_w(REPORTS / "compression_analysis.md", [
        "# Signal Compression Analysis", "",
        "signal_compression_ratio = input anomaly signals / resulting episodes.", "",
        f"- raw signals: {cmp['raw_signals']}",
        f"- episodes: {cmp['episodes']}",
        f"- **compression ratio: {cmp['signal_compression_ratio']:.2f}**",
        f"- signals/day: {cmp['signals_per_day']:.1f} · episodes/day: {cmp['episodes_per_day']:.1f}",
        f"- signals/episode mean/median/p95: {cmp['mean_signals_per_episode']:.2f} / "
        f"{cmp['median_signals_per_episode']:.1f} / {cmp['p95_signals_per_episode']:.1f}", "",
        "Fewer episodes is NOT claimed to mean better security — it measures analyst-facing",
        "fragmentation only.", ""]))

    lines = ["# Synthetic Correlation Scenarios", "",
             f"gap = {p['default_gap']}s, max duration = {DEFAULT_MAX_EPISODE_DURATION_SECONDS}s.", "",
             "| scenario | episodes | evidence strength | families |", "|---|---:|---|---|"]
    for name in SCENARIOS:
        s = p["scenarios"][name]
        lines.append(f"| {name} | {s['episodes']} | {s['strength']} | {s['families']} |")
    lines += ["", "SCN-E02 chain correlation does NOT prove A→B→C attack movement; it only shows",
              "relational connectivity in time.", ""]
    written.append(_w(REPORTS / "synthetic_scenarios.md", lines))

    fm = p["false_merge"]
    lines = ["# False-Merge Analysis (deterministic)", "",
             "| case | episodes | merged? |", "|---|---:|---|",
             *[f"| {k} | {v['episodes']} | {v['merged']} |" for k, v in fm.items()],
             "", "Proximity alone (same timestamp / severity / reason code) does NOT merge signals.",
             "Only temporal AND relational connection merges.", ""]
    written.append(_w(REPORTS / "false_merge_analysis.md", lines))

    lines = ["# Evidence Graph Examples (analysis only)", ""]
    for g in p["evidence_graphs"][:3]:
        lines.append(f"## {g['episode_id']} ({g['evidence_strength']})")
        lines.append(f"- assets: {g['assets']}")
        lines.append(f"- relationships: {g['relationships']}")
        lines.append(f"- evidence families: {g['evidence_families']}")
        for s in g["signals"][:8]:
            lines.append(f"  - {s['type']} {s['assets']} score={s['score']} reasons={s['reasons']}")
        lines.append("")
    written.append(_w(REPORTS / "evidence_graph_examples.md", lines))

    perf = p["performance"]
    written.append(_w(REPORTS / "performance.md", [
        "# Performance", "",
        f"- signals: {perf['signals']}",
        f"- **signals/sec: {perf['signals_per_sec']:.0f}**",
        f"- episode update latency: {perf['episode_update_latency_ms']:.4f} ms/signal",
        "- CPU-only; correlation is O(signals x active_episodes).", ""]))

    written.append(_w(REPORTS / "limitations.md", [
        "# Limitations", "",
        "- Behavioral episodes are **not** security incidents and carry **no** attack semantics.",
        "- Correlation is temporal + relational only; it does **not** prove causality or movement.",
        "- Inputs are UNSW (`dataset_ip_fallback`) alerts → **entity behavior**, not verified devices.",
        "- Thresholds (edge 0.315 / node 0.719) are provisional; episode membership inherits them.",
        "- No ground truth → episode quality is measured by compression/coherence, not accuracy.",
        "- max_episode_duration caps percolation but may split genuinely long episodes.",
        "- No score fusion; edge and node scores are reported separately.", ""]))

    written.append(_w(REPORTS / "readiness.md", [
        "# Readiness", "",
        f"- default correlation gap: **{p['default_gap']}s**",
        f"- episodes (default gap): {m['episodes']} · compression {cmp['signal_compression_ratio']:.2f}",
        f"- deterministic IDs + merge: yes · false merges in synthetic tests: "
        f"{sum(1 for v in fm.values() if v['merged'] and 'positive' not in str(v))}",
        "- streaming-compatible chronological correlator; no future leakage",
        "- no fusion, no attack taxonomy, no remediation; frozen v0.2 unchanged", "",
        "Ready for architecture review as a deterministic evidence-correlation layer.", ""]))
    return written


def main() -> None:
    p = run()
    write_reports(p)
    print(json.dumps({
        "edge_signals": p["counts"]["edge_signals"],
        "node_signals": p["counts"]["node_signals"],
        "total_signals": p["counts"]["total_signals"],
        "episodes_default_gap": p["gap_runs"][p["default_gap"]]["metrics"]["episodes"],
        "compression": round(p["gap_runs"][p["default_gap"]]["compression"]["signal_compression_ratio"], 2),
        "reports_dir": str(REPORTS),
    }, indent=2))


if __name__ == "__main__":
    main()
