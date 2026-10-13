"""Production-like shadow benchmark: durable SQLite state + durable SQLite sink.

No in-memory accumulation of inference records. Writes a report and prints a summary.

    python -m ai.shadow.reporting.benchmark
"""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from ai.edge_behavior.features.builder import load_asset_identity
from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.sqlite import SqliteShadowSink
from ai.shadow.sources.replay import ReplayObservationSource
from ai.shadow.state.sqlite import SqliteStateStore

OUT_DIR = Path(__file__).resolve().parents[3] / "ai" / "shadow" / "runtime_output"
REPORTS = Path(__file__).resolve().parents[3] / "reports" / "ai" / "shadow_v1"


def _mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024) if path.exists() else 0.0


def run(dataset: str = "unsw_iotraffic", window: str = "30s") -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state_path = OUT_DIR / "benchmark_state.sqlite"
    sink_path = OUT_DIR / "benchmark_shadow.sqlite"
    for p in (state_path, sink_path, Path(str(sink_path) + "-wal"), Path(str(sink_path) + "-shm")):
        if p.exists():
            p.unlink()

    cfg = ShadowConfig(dataset_id=dataset, window_label=window,
                       state_backend="sqlite", state_path=state_path,
                       sink_backend="sqlite", sink_path=sink_path)
    bundle = ShadowModelBundle.load(cfg.model_bundle)
    source = ReplayObservationSource(dataset, window)
    runtime = ShadowRuntime(cfg, source, SqliteShadowSink(sink_path), SqliteStateStore(state_path),
                            bundle, identity_map=load_asset_identity(dataset))

    t = time.perf_counter()
    summary = runtime.run()
    elapsed = time.perf_counter() - t
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0)

    runtime.sink.close()
    runtime.state_store.close()

    obs = summary["observations_processed"]
    windows = int(runtime.builder.counters["feature_windows_emitted_total"])
    return {
        "observations": obs,
        "feature_windows": windows,
        "elapsed_seconds": elapsed,
        "observations_per_sec": obs / max(elapsed, 1e-9),
        "peak_rss_mb": peak_mb,
        "state_db_mb": _mb(state_path),
        "sink_db_mb": _mb(sink_path),
        "feature_latency_ms": summary["metrics"]["histograms"].get("feature_build_latency_ms", {}),
        "inference_latency_ms": summary["metrics"]["histograms"].get("inference_latency_ms", {}),
        "duplicates": int(runtime.builder.counters["observations_duplicate_total"]),
        "late": int(runtime.builder.counters["observations_late_total"]),
    }


def _md(b: dict) -> str:
    def row(d):
        return f"p50={d.get('p50',0):.4f} p95={d.get('p95',0):.4f} p99={d.get('p99',0):.4f} ms"
    return "\n".join([
        "# Shadow Production-like Benchmark (durable state + durable sink)", "",
        "Durable `SqliteStateStore` + `SqliteShadowSink`; no in-memory accumulation of records.", "",
        f"- observations: {b['observations']}",
        f"- feature windows: {b['feature_windows']}",
        f"- elapsed: {b['elapsed_seconds']:.1f}s",
        f"- **observations/sec: {b['observations_per_sec']:.0f}**",
        f"- **peak RSS: {b['peak_rss_mb']:.1f} MB**",
        f"- SQLite state DB: {b['state_db_mb']:.2f} MB",
        f"- SQLite shadow sink DB: {b['sink_db_mb']:.2f} MB",
        f"- feature latency: {row(b['feature_latency_ms'])}",
        f"- inference latency: {row(b['inference_latency_ms'])}",
        f"- duplicates: {b['duplicates']} · late: {b['late']}", "",
        "Note: peak RSS includes the replay source (the full v0.2 observation frame loaded from",
        "Parquet) and the loaded model artifacts. In a live deployment the source is streamed and",
        "the sink writes to disk; the runtime itself retains only relationship/source sets and",
        "open-window buffers.", "",
    ])


def main() -> None:
    b = run()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "production_benchmark.md").write_text(_md(b), encoding="utf-8")
    print(json.dumps(b, indent=2))


if __name__ == "__main__":
    main()
