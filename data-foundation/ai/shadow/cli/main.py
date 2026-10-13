"""Shadow Integration v1 CLI.

    python -m ai.shadow replay --dataset unsw_iotraffic --speed max
    python -m ai.shadow parity --dataset unsw_iotraffic
    python -m ai.shadow demo
    python -m ai.shadow report --input <shadow_output.jsonl>
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ai.shadow.config import ShadowConfig
from ai.shadow.features.parity import compare_windows, offline_reference, online_reference
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.reporting.shadow_report import render_markdown, shadow_analytics
from ai.shadow.sinks.jsonl import JsonlShadowSink
from ai.shadow.sinks.sqlite import SqliteShadowSink
from ai.shadow.sources.replay import ReplayObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from ai.shadow.state.sqlite import SqliteStateStore

app = typer.Typer(help="AroSec Shadow Integration v1 (observe/score/explain/record only)")
console = Console()


def _state(cfg: ShadowConfig):
    return SqliteStateStore(cfg.state_path) if cfg.state_backend == "sqlite" else InMemoryStateStore()


def _sink(cfg: ShadowConfig):
    return SqliteShadowSink(cfg.sink_path) if cfg.sink_backend == "sqlite" else JsonlShadowSink(cfg.sink_path)


@app.command("replay")
def replay(
    dataset: str = typer.Option("unsw_iotraffic", "--dataset"),
    window: str = typer.Option("30s", "--window"),
    limit: int | None = typer.Option(None, "--limit"),
    speed: str = typer.Option("max", "--speed", help="max | 1x | 10x ..."),
    state_backend: str = typer.Option("memory", "--state-backend"),
    sink_backend: str = typer.Option("jsonl", "--sink-backend"),
    threshold: float = typer.Option(0.315, "--threshold", help="provisional shadow threshold"),
) -> None:
    cfg = ShadowConfig(dataset_id=dataset, window_label=window, shadow_threshold=threshold,
                       state_backend=state_backend, sink_backend=sink_backend)
    from ai.edge_behavior.features.builder import load_asset_identity
    from ai.shadow.runtime import ShadowRuntime

    source = ReplayObservationSource(dataset, window, limit=limit)
    bundle = ShadowModelBundle.load(cfg.model_bundle)
    runtime = ShadowRuntime(cfg, source, _sink(cfg), _state(cfg), bundle,
                            identity_map=load_asset_identity(dataset))
    if speed != "max":
        console.print(f"[yellow]note: speed={speed} pacing applies only to small demos; "
                      f"historical replay is intended with --speed max[/yellow]")
    t0 = time.perf_counter()
    summary = runtime.run()
    elapsed = time.perf_counter() - t0
    summary["elapsed_seconds"] = elapsed
    summary["observations_per_sec"] = summary["observations_processed"] / max(elapsed, 1e-9)
    console.print(json.dumps({"counters": summary["builder_counters"],
                              "observations_per_sec": round(summary["observations_per_sec"], 1),
                              "metrics": summary["metrics"]["counters"]}, indent=2))
    (Path(cfg.sink_path).parent / "replay_summary.json").write_text(json.dumps(summary, indent=2))


@app.command("parity")
def parity(dataset: str = typer.Option("unsw_iotraffic", "--dataset"),
           window: str = typer.Option("30s", "--window"),
           limit: int | None = typer.Option(None, "--limit")) -> None:
    from src.config import get_settings
    from src.normalization import io
    from src.schemas.base import SourceDataset
    from src.schemas.v2 import CommunicationObservation

    path = get_settings().processed_dir / "v2" / "communication_observations" / f"{dataset}_obs_{window}.parquet"
    df = io.read_parquet(path)
    obs = io.frame_to_models(df, CommunicationObservation)
    if limit:
        obs = obs[:limit]
    off = offline_reference(obs, SourceDataset(dataset))
    on = online_reference(obs, source=dataset)
    report = compare_windows(off, on)
    console.print(json.dumps({k: v for k, v in report.items() if k != "examples"}, indent=2))
    if report["total_mismatches"]:
        console.print(f"[red]PARITY FAILURES: {report['total_mismatches']}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]PARITY OK[/green]")


@app.command("demo")
def demo() -> None:
    from datetime import UTC, datetime, timedelta

    from ai.shadow.runtime import ShadowRuntime
    from ai.shadow.sources.list import ListObservationSource
    from src.schemas.v2 import CommunicationObservation

    t0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)

    def obs(win: int, src: str, dst: str, app: str, dport: int, k: int) -> CommunicationObservation:
        ws = t0 + timedelta(seconds=30 * win)
        return CommunicationObservation(
            observation_id=f"obs:demo-{k}",
            relationship_id=f"rel:{src}|{dst}|COMMUNICATES_WITH",
            src_asset_id=src, dst_asset_id=dst,
            window_start=ws, window_end=ws + timedelta(seconds=30),
            network_protocol="TCP", application_protocol=app,
            src_port=50000 + k, dst_port=dport, connection_count=1, packet_count=10,
            bytes_out=640, bytes_in=600, dataset_source="synthetic",
        )

    cam, nvr, eng3, eng4 = ("asset:demo:cam-01", "asset:demo:nvr-01",
                            "asset:demo:eng-pc-03", "asset:demo:eng-pc-04")
    observations = [
        obs(0, cam, nvr, "TLS", 443, 1),
        obs(1, cam, nvr, "TLS", 443, 2),
        obs(2, cam, eng3, "SMB", 445, 3),
        obs(3, cam, eng4, "SMB", 445, 4),
    ]
    cfg = ShadowConfig(dataset_id="synthetic", window_label="30s",
                       sink_path=Path("reports/ai/shadow_v1/demo_output.jsonl"))
    bundle = ShadowModelBundle.load(cfg.model_bundle)
    sink = JsonlShadowSink(cfg.sink_path)
    runtime = ShadowRuntime(cfg, ListObservationSource(observations), sink, InMemoryStateStore(), bundle)
    runtime.run()
    sink.close()

    table = Table(title="Shadow demo — EdgeAnomalyResultV1")
    for col in ("window", "relationship", "score", "severity", "reasons"):
        table.add_column(col)
    records = [json.loads(line) for line in Path(cfg.sink_path).read_text().splitlines() if line.strip()]
    for r in sorted(records, key=lambda r: r["feature_window"]["window_start"]):
        fw, ar = r["feature_window"], r["anomaly_result"]
        rel = fw["src_asset_id"].split(":")[-1] + "->" + fw["dst_asset_id"].split(":")[-1]
        reasons = ",".join(x["code"] for x in ar["reasons"][:4])
        table.add_row(fw["window_start"][11:19], rel, f"{ar['anomaly_score']:.3f}", ar["severity"], reasons)
    console.print(table)


@app.command("report")
def report(input: Path = typer.Option(..., "--input"),
           threshold: float = typer.Option(0.315, "--threshold"),
           out: Path = typer.Option(None, "--out")) -> None:
    from ai.contracts.shadow_records import ShadowInferenceRecordV1

    records = [ShadowInferenceRecordV1.model_validate_json(line)
               for line in Path(input).read_text().splitlines() if line.strip()]
    analytics = shadow_analytics(records, threshold)
    md = render_markdown(analytics)
    if out:
        Path(out).write_text(md)
        console.print(f"wrote {out}")
    else:
        console.print(md)


if __name__ == "__main__":
    app()
