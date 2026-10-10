"""Validation + data-quality metrics over normalized v0.1 tables."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from src.config import Settings, get_settings
from src.normalization import io
from src.schemas import Asset, AttackLabel, Campaign, CommunicationEdge, GraphEvent


@dataclass
class TableQuality:
    name: str
    rows: int
    null_pct: dict[str, float]
    duplicate_rows: int
    time_min: str | None = None
    time_max: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    tables: list[TableQuality] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.schema_errors


def _table_quality(name: str, df: pd.DataFrame, time_cols: list[str]) -> TableQuality:
    null_pct = {c: round(float(df[c].isna().mean()) * 100, 2) for c in df.columns}
    try:
        duplicates = int(df.duplicated().sum())
    except TypeError:
        duplicates = int(df.astype(str).duplicated().sum())
    tmin = tmax = None
    for col in time_cols:
        if col in df.columns and df[col].notna().any():
            series = pd.to_datetime(df[col], utc=True, errors="coerce")
            tmin = str(series.min())
            tmax = str(series.max())
            break
    return TableQuality(name=name, rows=len(df), null_pct=null_pct, duplicate_rows=duplicates,
                        time_min=tmin, time_max=tmax)


def validate_dataset_dir(dataset_id: str, settings: Settings | None = None) -> ValidationReport:
    settings = settings or get_settings()
    processed = settings.processed_dir
    report = ValidationReport()

    model_by_kind = {
        "assets": Asset,
        "labels": AttackLabel,
        "campaigns": Campaign,
        "graph_events": GraphEvent,
    }
    for subdir, model in model_by_kind.items():
        directory = processed / subdir
        for path in sorted(directory.glob(f"{dataset_id}*.parquet")):
            df = io.read_parquet(path)
            report.tables.append(_table_quality(f"{subdir}/{path.stem}", df, ["first_seen", "last_seen", "timestamp", "start_time", "end_time", "event_time"]))
            try:
                io.frame_to_models(df, model)
            except Exception as exc:  # noqa: BLE001 - report contract violations as text
                report.schema_errors.append(f"{path.name}: {exc}")

    for path in sorted((processed / "communication_edges").glob(f"{dataset_id}_edges_*.parquet")):
        df = io.read_parquet(path)
        report.tables.append(_table_quality(path.stem, df, ["window_start", "window_end"]))
        try:
            io.frame_to_models(df, CommunicationEdge)
        except Exception as exc:  # noqa: BLE001
            report.schema_errors.append(f"{path.name}: {exc}")
    return report


def edge_quality_extras(edges: list[CommunicationEdge], labels: list[AttackLabel]) -> dict:
    label_dist = Counter((lbl.attack_category, lbl.is_attack) for lbl in labels)
    pairs = {(e.src_asset_id, e.dst_asset_id, e.network_protocol, e.window_start) for e in edges}
    return {
        "unique_edges": len({e.edge_id for e in edges}),
        "unique_edge_pairs_proto_window": len(pairs),
        "new_peer_edges": sum(1 for e in edges if e.is_new_peer),
        "protocols": len({e.network_protocol for e in edges if e.network_protocol}),
        "time_order_violations": sum(1 for e in edges if e.window_start > e.window_end or e.first_seen > e.last_seen),
        "attack_labels": sum(1 for lbl in labels if lbl.is_attack),
        "benign_labels": sum(1 for lbl in labels if not lbl.is_attack),
        "lateral_movement_labels": sum(1 for lbl in labels if lbl.is_lateral_movement),
        "unknown_category_labels": sum(1 for lbl in labels if lbl.attack_category == "unknown"),
        "label_distribution": {f"{k[0]}|attack={k[1]}": v for k, v in label_dist.most_common()},
    }


def render_data_quality_md(report: ValidationReport, extras_by_dataset: dict[str, dict]) -> str:
    lines = ["# Data Quality Report", ""]
    lines.append(f"- validation_ok: **{report.ok}**")
    if report.schema_errors:
        lines.append("")
        lines.append("## Schema errors")
        for err in report.schema_errors:
            lines.append(f"- `{err}`")
    lines.append("")
    lines.append("## Tables")
    lines.append("| table | rows | duplicate rows | time min | time max | max null % |")
    lines.append("|---|---:|---:|---|---|---:|")
    for t in report.tables:
        max_null = max(t.null_pct.values()) if t.null_pct else 0.0
        lines.append(f"| {t.name} | {t.rows} | {t.duplicate_rows} | {t.time_min or '-'} | {t.time_max or '-'} | {max_null} |")
    lines.append("")
    for dataset_id, extras in extras_by_dataset.items():
        lines.append(f"## {dataset_id}")
        for key, value in extras.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    return "\n".join(lines)
