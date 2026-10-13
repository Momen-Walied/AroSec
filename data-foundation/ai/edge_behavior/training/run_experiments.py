"""Run all Edge Behavior v1 experiments and emit reports."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ai.edge_behavior.config import load_config
from ai.edge_behavior.evaluation.metrics import alert_summary, score_drift, temporal_stability
from ai.edge_behavior.evaluation.reporting import write_reports
from ai.edge_behavior.evaluation.sanity import xiiotid_sanity
from ai.edge_behavior.evaluation.scenarios import build_scenario_frames
from ai.edge_behavior.features.builder import feature_config
from ai.edge_behavior.inference.scorer import EdgeBehaviorScorer
from ai.edge_behavior.training.train import train_all
from ai.experiments.registry import record_experiment

REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports" / "ai" / "edge_behavior_v1"


def _scorer(result, dataset_id, window) -> EdgeBehaviorScorer:
    return EdgeBehaviorScorer(
        model=result["model"], statistical=result["statistical"],
        calibration=result["calibration"], feature_config=feature_config(),
        manifest=result["manifest"],
    )


def _scenario_report(scorer: EdgeBehaviorScorer, threshold: float, frames: dict) -> dict:
    out = {}
    for name, frame in frames.items():
        scored = scorer.score_batch(frame)
        scores = scored["anomaly_score"].to_numpy()
        out[name] = {
            "detection_rate": float((scores >= threshold).mean()),
            "median_score": float(np.median(scores)),
            "mean_score": float(np.mean(scores)),
        }
    return out


def _fusion(scorer_map: dict, weights: dict, frame: pd.DataFrame) -> np.ndarray:
    total = sum(weights.values()) or 1.0
    acc = np.zeros(len(frame))
    for name, w in weights.items():
        acc += (w / total) * scorer_map[name].score_batch(frame)["anomaly_score"].to_numpy()
    return np.clip(acc, 0.0, 1.0)


def _dod_row(src: str, dst: str, *, new_peer: bool, age_days: float, hist: int,
             fanout_new: int, fanout_uniq: int, ports: list[int], proto: str, app: str,
             conns: int) -> dict:
    from datetime import UTC, datetime

    return {
        "schema_version": "0.1.0",
        "relationship_id": f"rel:{src}|{dst}|COMMUNICATES_WITH",
        "src_asset_id": src, "dst_asset_id": dst,
        "window_start": datetime(2024, 3, 2, 2, 14, 0, tzinfo=UTC),
        "window_end": datetime(2024, 3, 2, 2, 14, 30, tzinfo=UTC),
        "connections_count": conns, "packet_count": conns * 3,
        "outbound_bytes": conns * 800, "inbound_bytes": conns * 200,
        "protocol_distribution": {proto: conns},
        "application_protocol_distribution": {app: conns},
        "observed_destination_ports": ports, "observed_source_ports": [51240],
        "unique_destination_ports": len(ports), "unique_source_ports": 1,
        "relationship_age_seconds": age_days * 86400.0,
        "historical_connection_count": hist,
        "new_peer": new_peer,
        "src_unique_peer_count": fanout_uniq, "src_new_peer_count": fanout_new,
        "protocol_novelty_count": 1 if new_peer else 0,
        "protocol_novelty_ratio": 1.0 if new_peer else 0.0,
        "port_novelty_count": len(ports) if new_peer else 0,
        "dataset_source": "synthetic",
    }


def _dod_demo(scorers: dict, weights: dict, severity_thresholds: dict) -> dict:
    suspicious = _dod_row(
        "asset:cicapt:host-cam-01", "asset:cicapt:host-eng-pc-03", new_peer=True, age_days=0.0,
        hist=0, fanout_new=5, fanout_uniq=61, ports=[445], proto="TCP", app="SMB", conns=2)
    stable = _dod_row(
        "asset:cicapt:host-cam-01", "asset:cicapt:host-nvr-01", new_peer=False, age_days=26.7,
        hist=5531, fanout_new=0, fanout_uniq=61, ports=[554], proto="TCP", app="RTSP", conns=1)

    from ai.edge_behavior.calibration import severity_for

    out = {}
    for label, row in (("suspicious_cam01_to_engpc03", suspicious), ("stable_cam01_to_nvr01", stable)):
        frame = pd.DataFrame([row])
        per_model = {m: float(scorers[m].score_batch(frame)["anomaly_score"].iloc[0]) for m in scorers}
        total = sum(weights.values()) or 1.0
        fused = float(np.clip(sum(weights[m] / total * per_model[m] for m in scorers), 0.0, 1.0))
        result = scorers["statistical"].score_edge(row)
        out[label] = {
            "fused_score": fused,
            "severity": severity_for(fused, severity_thresholds),
            "per_model": per_model,
            "reasons": [{"code": r.code, "contribution": r.contribution} for r in result.reasons],
        }
    return out


def run(dataset_id: str = "unsw_iotraffic", window: str = "30s", n_scenarios: int = 300) -> dict:
    cfg = load_config()
    results = train_all(dataset_id, window)
    data = results["_data"]
    test_df = data["split"].test
    val_df = data["split"].validation

    models = ("statistical", "isolation_forest", "autoencoder")
    scorers = {m: _scorer(results[m], dataset_id, window) for m in models}
    thresholds = {m: results[m]["calibration"]["threshold"] for m in models}

    test_scored = {m: scorers[m].score_batch(test_df) for m in models}
    val_frames = build_scenario_frames(val_df, n_scenarios, seed=cfg["random_seed"])
    test_frames = build_scenario_frames(test_df, n_scenarios, seed=cfg["random_seed"] + 1)

    scenario_val = {m: _scenario_report(scorers[m], thresholds[m], val_frames) for m in models}
    scenario_test = {m: _scenario_report(scorers[m], thresholds[m], test_frames) for m in models}

    stability = {m: temporal_stability(test_scored[m], thresholds[m]) for m in models}
    alerts = {m: alert_summary(test_scored[m], thresholds[m]) for m in models}
    drift = {m: score_drift(stability[m]) for m in models}

    # validation-derived fusion weights over the two best-behaved models
    # (the autoencoder saturates and is excluded from the production fusion).
    fusion_models = ("statistical", "isolation_forest")
    fusion_scorers = {m: scorers[m] for m in fusion_models}
    det = np.array([np.mean([s["detection_rate"] for s in scenario_val[m].values()]) for m in fusion_models])
    exp = np.exp(det - det.max())
    fusion_weights = {m: float(w) for m, w in zip(fusion_models, exp / exp.sum(), strict=False)}
    fusion_val_scores = _fusion(fusion_scorers, fusion_weights, val_df)
    from ai.edge_behavior.calibration import calibrate

    fusion_calib = calibrate(fusion_val_scores, cfg)
    fusion_threshold = fusion_calib["threshold"]
    fusion_severity = fusion_calib["severity_thresholds"]
    fusion_test_scores = _fusion(fusion_scorers, fusion_weights, test_df)
    fusion_scored = test_df[["relationship_id", "src_asset_id", "dst_asset_id",
                             "window_start", "window_end"]].copy()
    fusion_scored["anomaly_score"] = fusion_test_scores
    fusion_alerts = alert_summary(fusion_scored, fusion_threshold)
    fusion_test_scenarios = {}
    for name, frame in test_frames.items():
        s = _fusion(fusion_scorers, fusion_weights, frame)
        fusion_test_scenarios[name] = {"detection_rate": float((s >= fusion_threshold).mean()),
                                       "median_score": float(np.median(s))}

    # X-IIoTID sanity for the best single model (IForest) and statistical
    sanity = {}
    for m in ("statistical", "isolation_forest", "autoencoder"):
        try:
            sanity[m] = xiiotid_sanity(scorers[m], thresholds[m])
        except Exception as exc:  # noqa: BLE001
            sanity[m] = {"error": str(exc)}

    dod = _dod_demo(fusion_scorers, fusion_weights, fusion_severity)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_id": dataset_id,
        "window": window,
        "split": data["split"].summary(),
        "models": {
            m: {
                "model_version": results[m]["model"].model_version,
                "threshold": thresholds[m],
                "calibration": results[m]["calibration"],
                "normal_test": results[m]["metrics"]["normal_test"],
                "performance": results[m]["metrics"]["performance"],
                "artifact_dir": results[m]["artifact_dir"],
                "artifact_size_bytes": results[m]["artifact_size_bytes"],
                "scenario_validation": scenario_val[m],
                "scenario_test": scenario_test[m],
                "alert_summary": alerts[m],
                "score_drift": drift[m],
            } for m in models
        },
        "fusion": {
            "weights": fusion_weights,
            "threshold": fusion_threshold,
            "alerts": fusion_alerts,
            "scenario_test": fusion_test_scenarios,
        },
        "xiiotid_sanity": sanity,
        "dod": dod,
        "stability_tables": {m: stability[m].to_dict(orient="records") for m in models},
    }
    record_experiment({
        "experiment_id": "EXP-001..007",
        "model_type": "edge_behavior_v1_suite",
        "dataset_version": f"{dataset_id}:v0.2:{window}",
        "feature_schema_version": feature_config()["feature_schema_version"],
        "train_time_range": data["split"].boundaries["train"],
        "validation_time_range": data["split"].boundaries["validation"],
        "test_time_range": data["split"].boundaries["test"],
        "metrics": {m: results[m]["metrics"]["normal_test"] for m in models},
        "threshold": {m: thresholds[m] for m in models},
        "fusion_weights": fusion_weights,
        "random_seed": cfg["random_seed"],
    })
    return payload


def main() -> None:
    payload = run()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "results.json").write_text(json.dumps(payload, indent=2, default=str))
    written = write_reports(payload, REPORTS_DIR)
    print(json.dumps({"models": list(payload["models"]),
                      "fusion_weights": payload["fusion"]["weights"],
                      "reports": [str(p) for p in written]}, indent=2))


if __name__ == "__main__":
    main()
