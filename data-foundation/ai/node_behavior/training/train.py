"""Train, calibrate, package, and record Node Behavior v1 experiments."""
from __future__ import annotations

import json
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ai.edge_behavior.calibration import calibrate
from ai.experiments.registry import record_experiment
from ai.node_behavior.baselines import (
    AutoencoderNodeModel,
    IsolationForestNodeModel,
    StatisticalNodeModel,
)
from ai.node_behavior.config import COMPONENTS, NODE_FEATURE_COLUMNS, NODE_FEATURE_SCHEMA_VERSION
from ai.node_behavior.features.builder import (
    build_node_feature_matrix,
    build_node_feature_windows_v2,
)
from src.config import get_settings
from src.normalization import io
from src.schemas.v2 import CommunicationObservation

ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent / "artifacts" / "node_behavior"
SEED = 42


def feature_config() -> dict:
    return {
        "feature_schema_version": NODE_FEATURE_SCHEMA_VERSION,
        "feature_columns": list(NODE_FEATURE_COLUMNS),
        "components": {k: v["features"] for k, v in COMPONENTS.items()},
        "causality": "all history/novelty fields use windows strictly before the current window",
    }


def _load_observations(dataset: str, window: str) -> list[CommunicationObservation]:
    path = get_settings().processed_dir / "v2" / "communication_observations" / f"{dataset}_obs_{window}.parquet"
    exact = f"{dataset}_obs_{window}.parquet"
    if not path.exists():
        alt = get_settings().processed_dir / "v2" / "communication_observations" / exact
        path = alt
    return io.frame_to_models(io.read_parquet(path), CommunicationObservation)


def _edge_boundaries(dataset: str, window: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Reuse Edge Behavior's chronological boundaries so comparisons are meaningful."""
    from ai.edge_behavior.training.train import build_dataset

    data = build_dataset(dataset, window)
    b = data["split"].boundaries
    return pd.Timestamp(b["train"][1]), pd.Timestamp(b["validation"][1])


def build_node_dataset(dataset: str = "unsw_iotraffic", window: str = "30s") -> dict:
    observations = _load_observations(dataset, window)
    windows = build_node_feature_windows_v2(observations)
    matrix = build_node_feature_matrix(windows)
    t_train_end, t_val_end = _edge_boundaries(dataset, window)
    ws = matrix["window_start"]
    matrix["_split"] = np.where(ws <= t_train_end, "train", np.where(ws <= t_val_end, "validation", "test"))
    train = matrix[matrix["_split"] == "train"].copy()
    val = matrix[matrix["_split"] == "validation"].copy()
    test = matrix[matrix["_split"] == "test"].copy()

    def X(frame):
        return frame[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)

    boundaries = {
        "time_col": "window_start",
        "train": (train["window_start"].min().isoformat(), train["window_start"].max().isoformat()),
        "validation": (val["window_start"].min().isoformat(), val["window_start"].max().isoformat()),
        "test": (test["window_start"].min().isoformat(), test["window_start"].max().isoformat()),
        "n_total": len(matrix), "n_train": len(train), "n_validation": len(val), "n_test": len(test),
    }
    return {"matrix": matrix, "windows": windows, "boundaries": boundaries,
            "train": train, "validation": val, "test": test,
            "X_train": X(train), "X_validation": X(val), "X_test": X(test)}


def _normal_test_metrics(scores: np.ndarray, frame: pd.DataFrame, threshold: float) -> dict:
    alerts = scores >= threshold
    n = len(scores)
    days = max((pd.to_datetime(frame["window_start"], utc=True).max()
               - pd.to_datetime(frame["window_start"], utc=True).min()).total_seconds() / 86400.0, 1e-9)
    n_entities = frame["asset_id"].nunique()
    n_alert = int(alerts.sum())
    return {
        "rows": n,
        "score_mean": float(np.mean(scores)) if n else 0.0,
        "score_p50": float(np.percentile(scores, 50)) if n else 0.0,
        "score_p90": float(np.percentile(scores, 90)) if n else 0.0,
        "score_p99": float(np.percentile(scores, 99)) if n else 0.0,
        "alerts": n_alert,
        "alert_rate": n_alert / n if n else 0.0,
        "alerts_per_day": n_alert / days,
        "alerts_per_entity_per_day": n_alert / max(n_entities, 1) / days,
        "alerts_per_site_per_day": n_alert / days,
        "entities": n_entities,
    }


def _perf(model, X: np.ndarray) -> dict:
    tracemalloc.start()
    t0 = time.perf_counter()
    model.score(X)
    elapsed = time.perf_counter() - t0
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"inference_seconds_total": elapsed,
            "inference_ms_per_row": (elapsed / max(len(X), 1)) * 1000.0,
            "peak_memory_mb": peak / (1024 * 1024)}


def train_single(name: str, data: dict, dataset: str, window: str) -> dict:
    statistical = StatisticalNodeModel().fit(data["X_train"])
    if name == "statistical":
        model = statistical
    elif name == "isolation_forest":
        model = IsolationForestNodeModel(seed=SEED).fit(data["X_train"])
    elif name == "autoencoder":
        model = AutoencoderNodeModel(seed=SEED).fit(data["X_train"])
    else:
        raise ValueError(name)

    model.calibrate_normalization(data["X_validation"])
    val_scores = np.clip(model.score(data["X_validation"]), 0, 1)
    test_scores = np.clip(model.score(data["X_test"]), 0, 1)
    calib = calibrate(val_scores)  # uses default config target alert rate
    normal = _normal_test_metrics(test_scores, data["test"], calib["threshold"])
    perf = _perf(model, data["X_test"])

    version = model.model_version
    out = ARTIFACTS_ROOT / version
    out.mkdir(parents=True, exist_ok=True)
    model.save(out / "model.joblib")
    statistical.save(out / "statistical.joblib")
    (out / "feature_config.json").write_text(json.dumps(feature_config(), indent=2))
    (out / "calibration.json").write_text(json.dumps(calib, indent=2))
    manifest = {"model_version": version, "dataset_id": dataset, "window": window,
                "feature_schema_version": NODE_FEATURE_SCHEMA_VERSION,
                "train_time_range": data["boundaries"]["train"],
                "validation_time_range": data["boundaries"]["validation"],
                "test_time_range": data["boundaries"]["test"],
                "random_seed": SEED, "trained_at": datetime.now(UTC).isoformat()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    metrics = {"normal_test": normal, "calibration": calib, "performance": perf}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    size_bytes = sum(p.stat().st_size for p in out.glob("*"))

    record_experiment({
        "experiment_id": f"EXP-N-{name}",
        "model_type": version, "dataset_version": f"{dataset}:v0.2:{window}",
        "feature_schema_version": NODE_FEATURE_SCHEMA_VERSION,
        "train_time_range": manifest["train_time_range"],
        "validation_time_range": manifest["validation_time_range"],
        "test_time_range": manifest["test_time_range"],
        "hyperparameters": {"model": name, "seed": SEED},
        "metrics": {"normal_test": normal, "performance": perf},
        "threshold": calib["threshold"], "artifact_path": str(out),
        "artifact_size_bytes": size_bytes, "random_seed": SEED,
    })
    return {"model": model, "statistical": statistical, "calibration": calib, "metrics": metrics,
            "normal_test": normal, "performance": perf, "manifest": manifest,
            "artifact_dir": str(out), "artifact_size_bytes": size_bytes,
            "test_scores": test_scores, "val_scores": val_scores, "test_frame": data["test"]}


def train_all(dataset: str = "unsw_iotraffic", window: str = "30s") -> dict:
    data = build_node_dataset(dataset, window)
    results = {name: train_single(name, data, dataset, window)
               for name in ("statistical", "isolation_forest", "autoencoder")}
    results["_data"] = data
    return results
