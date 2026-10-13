"""Render Edge Behavior v1 markdown reports from the experiment payload."""
from __future__ import annotations

from pathlib import Path

DISCLAIMER = (
    "> **Terminology.** This component detects *behavioural anomalies in temporal "
    "communication relationships*. On UNSW-IoTraffic (no attack labels) these are "
    "**relationship anomalies**, not proven attacks. UNSW identities are "
    "`dataset_ip_fallback` (source MACs are null), so results are **communication-entity "
    "anomalies**, not device anomalies. No claim of lateral-movement / malware detection is made."
)


def _fmt(v, nd=4):
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def write_reports(payload: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    models = payload["models"]
    fusion = payload["fusion"]
    s = payload["split"]["boundaries"]

    # experiment_summary.md
    lines = ["# Edge Behavior v1 — Experiment Summary", "", DISCLAIMER, "",
             f"- dataset: `{payload['dataset_id']}` v0.2 `{payload['window']}`",
             f"- feature schema: `{models['statistical']['model_version']}` family",
             f"- split (chronological): train {s['train']} · validation {s['validation']} · test {s['test']}",
             f"- rows: train {payload['split']['train_rows']} / validation "
             f"{payload['split']['validation_rows']} / test {payload['split']['test_rows']}",
             "", "## Models", "",
             "| model | version | threshold | artifact size | val alert rate |",
             "|---|---|---:|---:|---:|"]
    for m, d in models.items():
        lines.append(f"| {m} | {d['model_version']} | {_fmt(d['threshold'],3)} | "
                     f"{d['artifact_size_bytes']//1024} KB | {_fmt(d['calibration']['validation_alert_rate'])} |")
    lines += ["", "## Fusion (validation-weighted)", "",
              "| model | weight |", "|---|---:|"]
    for m, w in fusion["weights"].items():
        lines.append(f"| {m} | {_fmt(w,3)} |")
    lines += ["", f"fusion threshold: {_fmt(fusion['threshold'],3)}", ""]
    written.append(_write(out_dir / "experiment_summary.md", lines))

    # evaluation.md
    lines = ["# Edge Behavior v1 — Evaluation (normal test data)", "", DISCLAIMER, "",
             "## Normal-test alert behaviour (test split, no attack labels)", "",
             "| model | alert rate | alerts | alerts/day | alerts/asset/day | alerts/rel/day | p50 | p90 | p99 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m, d in models.items():
        n = d["normal_test"]
        lines.append(f"| {m} | {_fmt(n['alert_rate'])} | {n['alerts']} | {_fmt(n['alerts_per_day'],1)} | "
                     f"{_fmt(n['alerts_per_asset_per_day'],2)} | {_fmt(n['alerts_per_relationship_per_day'],3)} | "
                     f"{_fmt(n['score_p50'],3)} | {_fmt(n['score_p90'],3)} | {_fmt(n['score_p99'],3)} |")
    lines += ["", f"Fusion: alert rate {_fmt(fusion['alerts']['alert_rate'])}, "
                  f"{_fmt(fusion['alerts']['alerts_per_day'],1)} alerts/day, "
                  f"{_fmt(fusion['alerts']['alerts_per_asset_per_day'],2)} alerts/asset/day.", "",
              "## Temporal stability (score drift)", "",
              "| model | mean of daily mean | std of daily mean | max daily alert rate |",
              "|---|---:|---:|---:|"]
    for m, d in models.items():
        dr = d["score_drift"]
        lines.append(f"| {m} | {_fmt(dr['mean_of_daily_mean'],4)} | {_fmt(dr['std_of_daily_mean'],4)} | "
                     f"{_fmt(dr['max_daily_alert_rate'],4)} |")
    lines += ["", "> The statistical model's higher test alert rate reflects genuine behavioural "
                  "novelty/drift in the test period (new peers/ports), not a labelling error. "
                  "UNSW test traffic is normal, so these are *novelty* alerts.", ""]

    dod = payload.get("dod", {})
    if dod:
        lines += ["## Definition-of-Done demonstration", "",
                  "Synthetic relationship windows (CAM-01 is a camera, NVR-01 a recorder, "
                  "ENG-PC-03 an engineering workstation):", ""]
        for label, d in dod.items():
            reasons = ", ".join(f"{r['code']}({_fmt(r['contribution'],3)})" for r in d["reasons"]) or "-"
            lines.append(f"- **{label}** → fused_score={_fmt(d['fused_score'],3)}, severity={d['severity']}, "
                         f"reasons: {reasons}")
        lines.append("")
    written.append(_write(out_dir / "evaluation.md", lines))

    # synthetic_scenarios.md
    lines = ["# Edge Behavior v1 — Synthetic Scenario Stress Test", "", DISCLAIMER, "",
             "Deterministic perturbations applied to TEST rows (evaluation only; never in training).",
             "", "## Detection rate by scenario (score >= calibrated threshold)", "",
             "| scenario | statistical | isolation_forest | autoencoder | fusion |",
             "|---|---:|---:|---:|---:|"]
    scen = list(models["statistical"]["scenario_test"].keys())
    for sc in scen:
        row = [f"| {sc} "]
        for m in ("statistical", "isolation_forest", "autoencoder"):
            row.append(f"| {_fmt(models[m]['scenario_test'][sc]['detection_rate'],2)} ")
        row.append(f"| {_fmt(fusion['scenario_test'][sc]['detection_rate'],2)} |")
        lines.append("".join(row))
    lines += ["", "## Median score by scenario", "",
              "| scenario | statistical | isolation_forest | autoencoder |",
              "|---|---:|---:|---:|"]
    for sc in scen:
        lines.append(f"| {sc} | {_fmt(models['statistical']['scenario_test'][sc]['median_score'],3)} | "
                     f"{_fmt(models['isolation_forest']['scenario_test'][sc]['median_score'],3)} | "
                     f"{_fmt(models['autoencoder']['scenario_test'][sc]['median_score'],3)} |")
    lines.append("")
    written.append(_write(out_dir / "synthetic_scenarios.md", lines))

    # xiiotid_sanity_check.md
    lines = ["# Edge Behavior v1 — X-IIoTID Sanity Check", "",
             "> **Sanity check only.** X-IIoTID here is the 1,672-row CC BY 4.0 derivative. "
             "It is NOT representative of the full 820,834-row dataset and its 77 "
             "lateral-movement examples are far too few for a reliable benchmark. "
             "The scorer is trained on UNSW (normal) and applied out-of-domain. "
             "Do NOT present these numbers as validated detection performance.", "",
             "| model | rows | attack windows | attack mean | benign mean | ROC-AUC | PR-AUC | attack alert rate | benign alert rate |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m, d in payload["xiiotid_sanity"].items():
        if "error" in d:
            lines.append(f"| {m} | - | - | - | - | - | - | - | ({d['error']}) |")
            continue
        lines.append(f"| {m} | {d['rows']} | {d['labelled_attack_windows']} | "
                     f"{_fmt(d.get('attack_score_mean',0),3)} | {_fmt(d.get('benign_score_mean',0),3)} | "
                     f"{_fmt(d.get('roc_auc',0),3)} | {_fmt(d.get('pr_auc',0),3)} | "
                     f"{_fmt(d.get('attack_alert_rate',0),3)} | {_fmt(d.get('benign_alert_rate',0),3)} |")
    lines.append("")
    written.append(_write(out_dir / "xiiotid_sanity_check.md", lines))

    # edge_deployment_benchmark.md
    lines = ["# Edge Behavior v1 — Edge Deployment Benchmark", "", DISCLAIMER, "",
             "CPU-only inference (no GPU). Latency measured as mean per-row batch scoring.",
             "", "| model | inference ms/row | total s (test) | peak memory MB | artifact size KB |",
             "|---|---:|---:|---:|---:|"]
    for m, d in models.items():
        p = d["performance"]
        lines.append(f"| {m} | {_fmt(p['inference_ms_per_row'],5)} | {_fmt(p['inference_seconds_total'],3)} | "
                     f"{_fmt(p['peak_memory_mb'],2)} | {d['artifact_size_bytes']//1024} |")
    lines.append("")
    written.append(_write(out_dir / "edge_deployment_benchmark.md", lines))
    return written


def _write(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
