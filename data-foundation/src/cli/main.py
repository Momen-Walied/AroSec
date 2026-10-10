"""Vigilance Data Foundation CLI.

Examples:
  python -m src.cli datasets inspect
  python -m src.cli datasets download --dataset cicapt_iiot --mode sample
  python -m src.cli datasets normalize --dataset cicapt_iiot
  python -m src.cli build-graph --dataset cicapt_iiot --window 30s
  python -m src.cli validate
  python -m src.cli report
  python -m src.cli demo
"""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.datasets.registry import get_adapter, load_registry

app = typer.Typer(help="Vigilance Data Foundation v0.1")
datasets_app = typer.Typer(help="Dataset operations")
app.add_typer(datasets_app, name="datasets")
console = Console()


@datasets_app.command("inspect")
def datasets_inspect(dataset: str | None = typer.Option(None, "--dataset"), all: bool = typer.Option(False, "--all")) -> None:
    registry = load_registry()
    ids = registry.ids() if all or not dataset else [dataset]
    table = Table(title="Dataset registry")
    table.add_column("dataset_id")
    table.add_column("status")
    table.add_column("access")
    table.add_column("present")
    table.add_column("files", justify="right")
    for ds in ids:
        adapter = get_adapter(ds)
        report = adapter.inspect()
        table.add_row(ds, report.status, registry.get(ds).download_access or "-", str(report.present), str(len(report.files)))
    console.print(table)


@datasets_app.command("download")
def datasets_download(
    dataset: str | None = typer.Option(None, "--dataset"),
    all: bool = typer.Option(False, "--all"),
    mode: str = typer.Option("sample", "--mode"),
) -> None:
    registry = load_registry()
    ids = registry.ids() if all or not dataset else [dataset]
    for ds in ids:
        result = get_adapter(ds).download(mode)
        console.print(f"[bold]{ds}[/bold]: {result.status} fetched={result.fetched} skipped={result.skipped} bytes={result.total if hasattr(result,'total') else result.bytes_total}")
        if result.notes:
            console.print(f"  [dim]{result.notes}[/dim]")


@datasets_app.command("normalize")
def datasets_normalize(
    dataset: str | None = typer.Option(None, "--dataset"),
    all: bool = typer.Option(False, "--all"),
    window: str = typer.Option("30s", "--window"),
) -> None:
    from src.normalization.build import build_dataset

    registry = load_registry()
    ids = registry.ids() if all or not dataset else [dataset]
    for ds in ids:
        try:
            summary = build_dataset(ds, window)
            console.print(json.dumps(summary.to_dict(), indent=2))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{ds}: {exc}[/red]")


@app.command("build-graph")
def build_graph(
    dataset: str | None = typer.Option(None, "--dataset"),
    all: bool = typer.Option(False, "--all"),
    window: str = typer.Option("30s", "--window"),
) -> None:
    from src.normalization.build import build_dataset

    settings = get_settings()
    registry = load_registry()
    ids = registry.ids() if all or not dataset else [dataset]
    for ds in ids:
        if ds == "cicapt_iiot" and not (settings.dataset_raw_dir(ds).exists() and any(settings.dataset_raw_dir(ds).rglob("*.csv"))):
            console.print(f"[yellow]{ds}: no raw files; skipping graph build (manual download required)[/yellow]")
            continue
        try:
            summary = build_dataset(ds, window)
            console.print(f"[green]{ds}[/green]: assets={summary.assets} edges={summary.edges} events={summary.events} node_feats={summary.node_features} edge_feats={summary.edge_features}")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{ds}: {exc}[/red]")


@app.command("validate")
def validate() -> None:
    from src.normalization import io
    from src.schemas import AttackLabel, CommunicationEdge
    from src.validation.checks import edge_quality_extras, validate_dataset_dir

    settings = get_settings()
    registry = load_registry()
    extras: dict[str, dict] = {}
    for ds in registry.ids():
        report = validate_dataset_dir(ds, settings)
        edges, labels = [], []
        for path in sorted((settings.processed_dir / "communication_edges").glob(f"{ds}_edges_*.parquet")):
            edges = io.frame_to_models(io.read_parquet(path), CommunicationEdge)
        label_path = settings.processed_dir / "labels" / f"{ds}.parquet"
        if label_path.exists():
            labels = io.frame_to_models(io.read_parquet(label_path), AttackLabel)
        if report.tables:
            extras[ds] = edge_quality_extras(edges, labels)
        console.print(f"[bold]{ds}[/bold]: tables={len(report.tables)} schema_errors={len(report.schema_errors)}")
        for err in report.schema_errors:
            console.print(f"  [red]{err}[/red]")


@app.command("report")
def report() -> None:
    from src.reports import generate_all
    paths = generate_all()
    for path in paths:
        console.print(f"wrote {path}")


@app.command("demo")
def demo(window: str = typer.Option("30s", "--window")) -> None:
    from src.normalization.build import build_dataset

    console.rule("Synthetic CICAPT-shaped APT scenario")
    summary = build_dataset("cicapt_iiot", window, synthetic=True)
    from src.datasets.cicapt import CicaptAdapter

    nd = CicaptAdapter(synthetic=True).normalize(30)
    from src.graph.temporal_graph import TemporalGraph
    from src.normalization.build_v2 import build_dataset_v2

    graph = TemporalGraph(nd.assets, nd.edges, nd.events, nd.labels)
    v2 = build_dataset_v2("cicapt_iiot", window, synthetic=True)
    console.print(json.dumps({"v0.1": summary.to_dict(), "v0.2": v2.to_dict()}, indent=2))
    console.print("\n[bold]Observed communication sequence:[/bold]")
    for edge in sorted(nd.edges, key=lambda e: (e.window_start, e.first_seen)):
        tag = " [NEW PEER]" if edge.is_new_peer else ""
        console.print(
            f"  {edge.window_start.strftime('%H:%M:%S')} "
            f"{edge.src_asset_id.split(':')[-1]:>10} -> {edge.dst_asset_id.split(':')[-1]:<10} "
            f"{edge.network_protocol or '':<5} {edge.application_protocol or '':<8}{tag}"
        )
    console.rule("Queries")
    if nd.labels:
        lm = graph.lateral_movement_nodes()
        console.print(f"lateral-movement nodes: {lm}")
    console.print("done")


@app.command("build-v2")
def build_v2(
    dataset: str | None = typer.Option(None, "--dataset"),
    all: bool = typer.Option(False, "--all"),
    window: str = typer.Option("30s", "--window"),
) -> None:
    from src.normalization.build_v2 import build_dataset_v2

    settings = get_settings()
    registry = load_registry()
    ids = registry.ids() if all or not dataset else [dataset]
    for ds in ids:
        if ds == "cicapt_iiot" and not any(settings.dataset_raw_dir(ds).rglob("*.csv")):
            console.print(f"[yellow]{ds}: no raw files; skipping v0.2 build[/yellow]")
            continue
        try:
            summary = build_dataset_v2(ds, window)
            console.print(json.dumps(summary.to_dict(), indent=2))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{ds}: {exc}[/red]")


@app.command("validate-v2")
def validate_v2(window: str = typer.Option("30s", "--window")) -> None:
    from src.validation.checks_v2 import validate_v2_dataset

    settings = get_settings()
    registry = load_registry()
    for ds in registry.ids():
        if not (settings.processed_dir / "v2" / "assets" / f"{ds}.parquet").exists():
            continue
        result = validate_v2_dataset(ds, window, settings)
        console.print(json.dumps(result, indent=2))


@app.command("export-v01")
def export_v01(
    dataset: str | None = typer.Option(None, "--dataset"),
    window: str = typer.Option("30s", "--window"),
) -> None:
    from src.compat.v01 import to_v01_edges
    from src.normalization import io
    from src.schemas import CommunicationObservation, CommunicationRelationship
    from src.schemas.base import SourceDataset

    settings = get_settings()
    registry = load_registry()
    ids = registry.ids() if not dataset else [dataset]
    for ds in ids:
        base = settings.processed_dir / "v2"
        rel_p = base / "relationships" / f"{ds}.parquet"
        obs_p = base / "communication_observations" / f"{ds}_obs_{window}.parquet"
        if not rel_p.exists() or not obs_p.exists():
            console.print(f"[yellow]{ds}: no v0.2 data[/yellow]")
            continue
        rels = io.frame_to_models(io.read_parquet(rel_p), CommunicationRelationship)
        obs = io.frame_to_models(io.read_parquet(obs_p), CommunicationObservation)
        edges = to_v01_edges(rels, obs, SourceDataset(ds), int(window.rstrip("s")))
        out = settings.processed_dir / "communication_edges" / f"{ds}_edges_{window}_from_v2.parquet"
        io.write_parquet(io.models_to_frame(edges), out)
        console.print(f"{ds}: wrote {len(edges)} v0.1-compat edges -> {out}")


if __name__ == "__main__":
    app()
