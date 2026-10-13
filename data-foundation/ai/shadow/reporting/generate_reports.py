"""Generate the data-driven Shadow Integration v1 reports.

    python -m ai.shadow.reporting.generate_reports
"""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

import numpy as np

from ai.edge_behavior.features.builder import load_asset_identity
from ai.shadow.config import ShadowConfig
from ai.shadow.features.parity import compare_windows, offline_reference, online_reference
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.metrics.drift import drift_report
from ai.shadow.reporting.shadow_report import render_markdown, shadow_analytics
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from src.config import get_settings
from src.normalization import io
from src.schemas.base import SourceDataset
from src.schemas.v2 import CommunicationObservation

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "ai" / "shadow_v1"


def _load_observations(dataset: str, window: str) -> list[CommunicationObservation]:
    path = get_settings().processed_dir / "v2" / "communication_observations" / f"{dataset}_obs_{window}.parquet"
    return io.frame_to_models(io.read_parquet(path), CommunicationObservation)


def _reference(bundle: ShadowModelBundle) -> dict:
    from ai.edge_behavior.training.train import build_dataset

    data = build_dataset("unsw_iotraffic", "30s")
    val = data["split"].validation
    return {
        "anomaly_score": bundle.score(data["X_validation"]),
        "connections_count": val["connections_count"].to_numpy(dtype=float),
        "outbound_bytes": val["outbound_bytes"].to_numpy(dtype=float),
        "fan_out": val["src_new_peer_count"].to_numpy(dtype=float),
        "new_peer_rate": val["new_peer"].astype(float).to_numpy(),
        "protocol_novelty_rate": val["protocol_novelty_count"].to_numpy(dtype=float),
        "port_novelty_rate": val["port_novelty_count"].to_numpy(dtype=float),
    }


def generate(dataset: str = "unsw_iotraffic", window: str = "30s") -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    cfg = ShadowConfig(dataset_id=dataset, window_label=window)
    bundle = ShadowModelBundle.load(cfg.model_bundle)
    observations = _load_observations(dataset, window)

    # ---- parity ----
    t = time.perf_counter()
    off = offline_reference(observations, SourceDataset(dataset))
    on = online_reference(observations, source=dataset)
    parity = compare_windows(off, on)
    parity["seconds"] = time.perf_counter() - t
    (REPORTS / "offline_online_parity.md").write_text(_parity_md(parity))

    # ---- replay ----
    sink = InMemoryShadowSink()
    t = time.perf_counter()
    runtime = ShadowRuntime(cfg, ListObservationSource(observations), sink,
                            InMemoryStateStore(), bundle, identity_map=load_asset_identity(dataset))
    summary = runtime.run()
    elapsed = time.perf_counter() - t
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0)  # MB (macOS bytes)
    analytics = shadow_analytics(sink.records, cfg.shadow_threshold)
    (REPORTS / "replay_evaluation.md").write_text(render_markdown(analytics, "Shadow Replay Evaluation"))

    # ---- performance ----
    counters = summary["metrics"]["counters"]
    perf = {
        "observations": summary["observations_processed"],
        "feature_windows": int(runtime.builder.counters["feature_windows_emitted_total"]),
        "elapsed_seconds": elapsed,
        "observations_per_sec": summary["observations_processed"] / max(elapsed, 1e-9),
        "feature_windows_per_sec": runtime.builder.counters["feature_windows_emitted_total"] / max(elapsed, 1e-9),
        "feature_latency_ms": summary["metrics"]["histograms"].get("feature_build_latency_ms", {}),
        "inference_latency_ms": summary["metrics"]["histograms"].get("inference_latency_ms", {}),
        "peak_memory_mb": peak,
        "duplicates": int(runtime.builder.counters["observations_duplicate_total"]),
        "late": int(runtime.builder.counters["observations_late_total"]),
        "rejected": int(counters.get("malformed_observations_total", 0)),
    }
    (REPORTS / "performance.md").write_text(_performance_md(perf))

    # ---- drift ----
    reference = _reference(bundle)
    recent_scores = np.asarray([r.anomaly_result.anomaly_score for r in sink.records])
    recent = {
        "anomaly_score": recent_scores,
        "connections_count": np.asarray([r.feature_window.connections_count for r in sink.records], dtype=float),
        "outbound_bytes": np.asarray([r.feature_window.outbound_bytes for r in sink.records], dtype=float),
        "fan_out": np.asarray([r.feature_window.src_new_peer_count for r in sink.records], dtype=float),
        "new_peer_rate": np.asarray([1.0 if r.feature_window.new_peer else 0.0 for r in sink.records]),
        "protocol_novelty_rate": np.asarray([float(r.feature_window.protocol_novelty_count) for r in sink.records]),
        "port_novelty_rate": np.asarray([float(r.feature_window.port_novelty_count) for r in sink.records]),
    }
    drift = drift_report(recent, reference)
    (REPORTS / "drift_baseline.md").write_text(_drift_md(drift, reference["anomaly_score"], recent_scores))

    return {"parity": parity, "analytics": analytics, "performance": perf, "drift": drift}


def _parity_md(parity: dict) -> str:
    lines = ["# Offline / Online Feature Parity", "",
             "Comparison of `build_edge_features_v2` (offline) vs `OnlineFeatureBuilder` (online)",
             "over the same chronological CommunicationObservation sequence.", "",
             f"- offline windows: {parity['offline_windows']}",
             f"- online windows: {parity['online_windows']}",
             f"- missing in online: {parity['missing_in_online']}",
             f"- extra in online: {parity['extra_in_online']}",
             f"- **total field mismatches: {parity['total_mismatches']}**",
             f"- comparison time: {parity.get('seconds', 0):.1f}s", "",
             "## Field mismatch counts", "", "| field | mismatches |", "|---|---:|"]
    for field, count in parity["field_mismatches"].items():
        lines.append(f"| {field} | {count} |")
    lines += ["", "Intentional difference (documented): `relationship_age_seconds` uses the first",
              "observed *window_start* online (CommunicationObservation carries window boundaries,",
              "not raw packet timestamps). Against the windowed offline reference it matches exactly;",
              "against training-time features the offset is bounded by one window (0 for the first window).", ""]
    return "\n".join(lines) + "\n"


def _performance_md(perf: dict) -> str:
    def row(d):
        if not d:
            return "n/a"
        return f"p50={d['p50']:.4f} p95={d['p95']:.4f} p99={d['p99']:.4f} ms"
    return "\n".join([
        "# Shadow Performance (CPU-only, no GPU)", "",
        f"- observations processed: {perf['observations']}",
        f"- feature windows emitted: {perf['feature_windows']}",
        f"- elapsed: {perf['elapsed_seconds']:.1f}s",
        f"- **observations/sec: {perf['observations_per_sec']:.0f}**",
        f"- feature windows/sec: {perf['feature_windows_per_sec']:.0f}",
        f"- feature-build latency: {row(perf['feature_latency_ms'])}",
        f"- inference latency: {row(perf['inference_latency_ms'])}",
        f"- peak RSS (includes in-memory evaluation sink holding all records): {perf['peak_memory_mb']:.1f} MB",
        f"- duplicates: {perf['duplicates']} · late: {perf['late']} · rejected: {perf['rejected']}", "",
    ])


def _drift_md(drift: dict, ref_scores: np.ndarray, recent_scores: np.ndarray) -> str:
    lines = ["# Drift Baseline (metrics only; no automatic retraining)", "",
             "PSI (population stability index) of recent replay vs the training/validation reference.",
             "PSI thresholds: warning >= 0.10, high >= 0.25.", "",
             f"- reference score n={len(ref_scores)} mean={float(np.mean(ref_scores)):.3f}",
             f"- recent score n={len(recent_scores)} mean={float(np.mean(recent_scores)):.3f}", "",
             "| metric | PSI | KS | class |", "|---|---:|---:|---|"]
    for name, d in drift.items():
        if name == "_overall":
            continue
        lines.append(f"| {name} | {d['psi']:.3f} | {d['ks']:.3f} | {d['class']} |")
    lines += ["", f"**Overall: {drift.get('_overall', 'n/a')}**", "",
              "Limitations: PSI/KS compare aggregate distributions and cannot attribute drift to a",
              "cause; the reference is the UNSW sample. No retraining is triggered.", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    result = generate()
    print(json.dumps({
        "parity_total_mismatches": result["parity"]["total_mismatches"],
        "parity_windows": result["parity"]["offline_windows"],
        "replay_alerts": result["analytics"]["alerts"],
        "replay_alert_rate": result["analytics"]["alert_rate"],
        "observations_per_sec": round(result["performance"]["observations_per_sec"], 1),
        "drift_overall": result["drift"]["_overall"],
        "reports_dir": str(REPORTS),
    }, indent=2))


if __name__ == "__main__":
    main()
