"""Run all Node Behavior v1 experiments and emit reports.

    python -m ai.node_behavior.training.run_experiments
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.features.builder import FEATURE_COLUMNS as EDGE_COLS
from ai.edge_behavior.features.builder import build_feature_matrix
from ai.experiments.registry import record_experiment
from ai.node_behavior.evaluation.correlation import entity_edge_alignment, window_correlation
from ai.node_behavior.evaluation.edge_vs_node import compare as edge_vs_node_compare
from ai.node_behavior.evaluation.metrics import alert_summary, score_drift, temporal_stability
from ai.node_behavior.evaluation.reporting import write_reports
from ai.node_behavior.evaluation.scenarios import build_node_scenario_frames
from ai.node_behavior.inference.scorer import NodeBehaviorScorer
from ai.node_behavior.training.train import feature_config, train_all
from src.config import PROJECT_ROOT

REPORTS_DIR = PROJECT_ROOT / "reports" / "ai" / "node_behavior_v1"
MODELS = ("statistical", "isolation_forest", "autoencoder")


def _edge_test_scored(dataset: str, window: str, t_val_end: pd.Timestamp):
    path = PROJECT_ROOT / "data" / "processed" / "v2" / "edge_features" / f"{dataset}_{window}.parquet"
    df = pd.read_parquet(path)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df = df[df["window_start"] > t_val_end].copy()
    model = BaseEdgeModel.load(PROJECT_ROOT / "ai/edge_behavior/artifacts/edge_behavior/edge-stat-v1/model.joblib")
    cal = json.loads((PROJECT_ROOT / "ai/edge_behavior/artifacts/edge_behavior/edge-stat-v1/calibration.json").read_text())
    X = build_feature_matrix(df)[EDGE_COLS].to_numpy(dtype=float)
    scored = df[["relationship_id", "window_start"]].copy()
    scored["anomaly_score"] = np.clip(model.score(X), 0, 1)
    return scored, float(cal["threshold"])


def run(dataset: str = "unsw_iotraffic", window: str = "30s", n_scenarios: int = 300) -> dict:
    results = train_all(dataset, window)
    data = results["_data"]
    t_val_end = pd.Timestamp(data["boundaries"]["validation"][1])
    node_test_windows = [w for w in data["windows"] if pd.Timestamp(w.window_start) > t_val_end]

    scorers, scored, thresholds = {}, {}, {}
    for m in MODELS:
        scorers[m] = NodeBehaviorScorer(results[m]["model"], results[m]["statistical"],
                                        results[m]["calibration"], feature_config())
        scored[m] = scorers[m].score_batch(node_test_windows)
        thresholds[m] = results[m]["calibration"]["threshold"]

    stability = {m: temporal_stability(scored[m], thresholds[m]) for m in MODELS}
    alerts = {m: alert_summary(scored[m], thresholds[m]) for m in MODELS}
    drift = {m: score_drift(stability[m]) for m in MODELS}

    frames = build_node_scenario_frames(node_test_windows, n_scenarios, seed=42)
    scenario = {}
    for m in MODELS:
        scenario[m] = {}
        for name, wins in frames.items():
            s = scorers[m].score_batch(wins)["anomaly_score"].to_numpy()
            scenario[m][name] = {"detection_rate": float((s >= thresholds[m]).mean()),
                                 "median_score": float(np.median(s))}

    edge_scored, edge_thr = _edge_test_scored(dataset, window, t_val_end)
    node_sel = "statistical"  # interpretable reference for correlation
    correlation = window_correlation(edge_scored, scored[node_sel], edge_thr, thresholds[node_sel])
    alignment = entity_edge_alignment(edge_scored, scored[node_sel], edge_thr, thresholds[node_sel])

    evn = edge_vs_node_compare(scorers["statistical"], thresholds["statistical"],
                               dataset=dataset, window=window, node_test_windows=node_test_windows,
                               n=n_scenarios, seed=7)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_id": dataset, "window": window,
        "boundaries": data["boundaries"],
        "_feature_columns": feature_config()["feature_columns"],
        "models": {m: {"model_version": results[m]["model"].model_version,
                       "threshold": thresholds[m], "calibration": results[m]["calibration"],
                       "normal_test": results[m]["normal_test"], "performance": results[m]["performance"],
                       "artifact_dir": results[m]["artifact_dir"],
                       "artifact_size_bytes": results[m]["artifact_size_bytes"],
                       "scenario": scenario[m], "alerts": alerts[m], "score_drift": drift[m]}
                   for m in MODELS},
        "correlation": correlation, "alignment": alignment, "edge_vs_node": evn,
        "stability_tables": {m: stability[m].to_dict(orient="records") for m in MODELS},
    }
    record_experiment({
        "experiment_id": "EXP-N-001..004",
        "model_type": "node_behavior_v1_suite",
        "dataset_version": f"{dataset}:v0.2:{window}",
        "feature_schema_version": feature_config()["feature_schema_version"],
        "train_time_range": data["boundaries"]["train"],
        "validation_time_range": data["boundaries"]["validation"],
        "test_time_range": data["boundaries"]["test"],
        "metrics": {m: results[m]["normal_test"] for m in MODELS},
        "threshold": thresholds, "random_seed": 42,
    })
    write_reports(payload, REPORTS_DIR)
    return payload


def main() -> None:
    payload = run()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "results.json").write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({
        "models": list(payload["models"]),
        "alert_rate": {m: round(payload["models"][m]["normal_test"]["alert_rate"], 4) for m in MODELS},
        "correlation_pearson": payload["correlation"].get("pearson"),
        "reports_dir": str(REPORTS_DIR),
    }, indent=2))


if __name__ == "__main__":
    main()
