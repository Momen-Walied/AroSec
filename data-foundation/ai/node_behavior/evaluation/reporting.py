"""Render Node Behavior v1 reports from the experiment payload."""
from __future__ import annotations

from pathlib import Path

from ai.node_behavior.features.schema import NodeFeatureWindowV2

DISCLAIMER = (
    "> **Terminology.** Entity (communication-entity) behavior anomaly — **not** validated "
    "device anomaly and **not** attack detection. UNSW identities are `dataset_ip_fallback`."
)


def _f(v, nd=3):
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def write_reports(payload: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    models = payload["models"]
    written: list[Path] = []

    # feature_design.md
    lines = ["# Node Behavior v1 — Feature Design", "", DISCLAIMER, "",
             "## Audit of the existing `NodeFeatureWindow`", "",
             "The v0.1 `NodeFeatureWindow` is **outbound-centric**: it has `connection_count`, "
             "`unique_destination_assets`, `new_peer_count`, `unique_destination_ports`, "
             "`fan_out`, `outbound_bytes`, `protocol_count` — but **no inbound behavior** "
             "(no incoming peers/fan-in, no inbound protocol/port diversity, no peer-set change "
             "or relationship-creation rate). `dns_query_rate` and `failed_connection_ratio` are "
             "unavailable in the source data (null).", "",
             "**Conclusion: V2 required.** `NodeFeatureWindowV2` (AI layer, above the frozen "
             "contract) models both directions symmetrically and adds novelty/change features.", "",
             "## NodeFeatureWindowV2 fields", "", "| field | type |", "|---|---|"]
    for name, field in NodeFeatureWindowV2.model_fields.items():
        lines.append(f"| `{name}` | {getattr(field.annotation, '__name__', field.annotation)} |")
    lines += ["", "## Model features (node_features_v1)", "",
              ", ".join(f"`{c}`" for c in payload.get("_feature_columns", [])) or
              "(see `ai/node_behavior/config.py`)", "",
              "Causality: peers/protocols/ports novelty use only windows strictly before the "
              "current window; scalers fit on TRAIN only; thresholds from VALIDATION only.", ""]
    written.append(_w(out_dir / "feature_design.md", lines))

    # experiment_summary.md
    b = payload["boundaries"]
    lines = ["# Node Behavior v1 — Experiment Summary", "", DISCLAIMER, "",
             f"- dataset: `{payload['dataset_id']}` v0.2 `{payload['window']}`",
             f"- split (chronological, aligned with Edge Behavior): train {b['train']} · "
             f"validation {b['validation']} · test {b['test']}",
             f"- rows: train {b['n_train']} / validation {b['n_validation']} / test {b['n_test']}",
             "", "| model | version | threshold | val alert rate | test alert rate | artifact size |",
             "|---|---|---:|---:|---:|---:|"]
    for m, d in models.items():
        lines.append(f"| {m} | {d['model_version']} | {_f(d['threshold'])} | "
                     f"{_f(d['calibration']['validation_alert_rate'],4)} | "
                     f"{_f(d['normal_test']['alert_rate'],4)} | {d['artifact_size_bytes']//1024} KB |")
    lines.append("")
    written.append(_w(out_dir / "experiment_summary.md", lines))

    # evaluation.md
    lines = ["# Node Behavior v1 — Evaluation (normal test data)", "", DISCLAIMER, "",
             "| model | alert rate | alerts | alerts/entity/day | alerts/site/day | p50 | p90 | p99 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m, d in models.items():
        n = d["normal_test"]
        lines.append(f"| {m} | {_f(n['alert_rate'],4)} | {n['alerts']} | "
                     f"{_f(n['alerts_per_entity_per_day'],2)} | {_f(n['alerts_per_site_per_day'],1)} | "
                     f"{_f(n['score_p50'])} | {_f(n['score_p90'])} | {_f(n['score_p99'])} |")
    lines += ["", "## Score drift (daily mean)", "",
              "| model | mean of daily mean | std | max daily alert rate |", "|---|---:|---:|---:|"]
    for m, d in models.items():
        dr = d["score_drift"]
        lines.append(f"| {m} | {_f(dr['mean_of_daily_mean'],4)} | {_f(dr['std_of_daily_mean'],4)} | "
                     f"{_f(dr['max_daily_alert_rate'],4)} |")
    lines.append("")
    written.append(_w(out_dir / "evaluation.md", lines))

    # synthetic_scenarios.md
    lines = ["# Node Behavior v1 — Synthetic Scenario Response", "", DISCLAIMER, "",
             "Deterministic perturbations applied to TEST node windows (evaluation only).", "",
             "| scenario | statistical | isolation_forest | autoencoder |",
             "|---|---:|---:|---:|"]
    scen = list(models["statistical"]["scenario"].keys())
    for sc in scen:
        lines.append(f"| {sc} | "
                     + " | ".join(_f(models[m]["scenario"][sc]["detection_rate"], 2)
                                  for m in ("statistical", "isolation_forest", "autoencoder"))
                     + " |")
    lines.append("")
    written.append(_w(out_dir / "synthetic_scenarios.md", lines))

    # edge_vs_node.md
    evn = payload["edge_vs_node"]
    corr = payload["correlation"]
    lines = ["# Edge vs Node Behavior — Complementarity", "", DISCLAIMER, "",
             f"Thresholds — node {_f(evn['thresholds']['node'])}, edge {_f(evn['thresholds']['edge'])} "
             "(statistical models both sides).", "",
             "## Equivalent anomaly families (detection rate)", "",
             "| anomaly family | node v1 | edge v1 | better |", "|---|---:|---|---|"]
    for nscen, d in evn["comparison"].items():
        nd, ed = d["node_detection"], d["edge_detection"]
        better = "node" if nd > ed + 0.05 else ("edge" if ed > nd + 0.05 else "tie")
        lines.append(f"| {nscen} | {_f(nd,2)} | {_f(ed,2)} | {better} |")
    lines += ["", "## Cross-model correlation (window level)", "",
              f"- windows compared: {corr.get('windows')}",
              f"- Pearson: {_f(corr.get('pearson', 0),4)} · Spearman: {_f(corr.get('spearman', 0),4)}",
              f"- high-node windows that also have high edge: {_f(corr.get('pct_high_node_with_high_edge',0),3)}",
              f"- high-edge windows while node normal: {_f(corr.get('pct_high_edge_while_node_normal',0),3)}",
              f"- high-node windows while edge normal: {_f(corr.get('pct_high_node_while_edge_normal',0),3)}", "",
              "Correlation is descriptive, not causal. Low overlap indicates complementary signals.", ""]
    written.append(_w(out_dir / "edge_vs_node.md", lines))

    # performance.md
    lines = ["# Node Behavior v1 — Performance (CPU-only)", "",
             "| model | ms/row | total s (test) | peak MB | artifact KB |", "|---|---:|---:|---:|---:|"]
    for m, d in models.items():
        p = d["performance"]
        lines.append(f"| {m} | {_f(p['inference_ms_per_row'],5)} | {_f(p['inference_seconds_total'],3)} | "
                     f"{_f(p['peak_memory_mb'],2)} | {d['artifact_size_bytes']//1024} |")
    lines.append("")
    written.append(_w(out_dir / "performance.md", lines))

    # limitations.md
    lines = ["# Node Behavior v1 — Limitations", "",
             "- **Identity:** UNSW entities are `dataset_ip_fallback` (source MACs null) → results "
             "are **entity/relationship behavior anomalies**, not device anomalies.",
             "- **No attack labels:** evaluation is temporal-stability + synthetic-scenario + "
             "correlation based; no supervised detection performance is claimed.",
             "- **Packet direction:** `packet_count` is flow-total and assigned by initiator side "
             "(splitting packets by direction is not available).",
             "- **Drift:** thresholds are validation-derived; UNSW shows period drift.",
             "- **Scope:** no GNN, no attack-path, no campaign reconstruction, no remediation; "
             "node/edge fusion not built (intentionally deferred).", ""]
    written.append(_w(out_dir / "limitations.md", lines))
    return written


def _w(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
