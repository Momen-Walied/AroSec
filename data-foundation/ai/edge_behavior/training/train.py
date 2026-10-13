"""Train, calibrate, package, and record Edge Behavior v1 experiments."""
from __future__ import annotations

import json
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ai.edge_behavior.baselines import (
    AutoencoderEdgeModel,
    IsolationForestEdgeModel,
    StatisticalEdgeModel,
)
from ai.edge_behavior.calibration import calibrate
from ai.edge_behavior.config import load_config
from ai.edge_behavior.features.builder import (
    FEATURE_COLUMNS,
    build_feature_matrix,
    feature_config,
    load_edge_feature_windows,
)
from ai.edge_behavior.training.split import ChronologicalSplit
from ai.experiments.registry import record_experiment

ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent / "artifacts" / "edge_behavior"


def build_dataset(dataset_id: str = "unsw_iotraffic", window: str = "30s") -> dict:
    raw = load_edge_feature_windows(dataset_id, window)
    raw = raw.sort_values("window_start", kind="mergesort").reset_index(drop=True)
    matrix = build_feature_matrix(raw)
    cfg = load_config()["split"]
    n = len(raw)
    n_train = int(n * cfg["train"])
    n_val = int(n * cfg["validation"])
    t_train_end = raw.iloc[n_train - 1]["window_start"]
    t_val_end = raw.iloc[n_train + n_val - 1]["window_start"]

    def _label(series: pd.Series) -> np.ndarray:
        return np.where(series <= t_train_end, "train",
                        np.where(series <= t_val_end, "validation", "test"))

    raw["_split"] = _label(raw["window_start"])
    matrix["_split"] = _label(matrix["window_start"])
    raw_train = raw[raw["_split"] == "train"].copy()
    raw_val = raw[raw["_split"] == "validation"].copy()
    raw_test = raw[raw["_split"] == "test"].copy()

    boundaries = {
        "time_col": "window_start",
        "fractions": {"train": cfg["train"], "validation": cfg["validation"], "test": cfg["test"]},
        "train": (raw_train["window_start"].min().isoformat(), raw_train["window_start"].max().isoformat()),
        "validation": (raw_val["window_start"].min().isoformat(), raw_val["window_start"].max().isoformat()),
        "test": (raw_test["window_start"].min().isoformat(), raw_test["window_start"].max().isoformat()),
        "n_total": n, "n_train": len(raw_train), "n_validation": len(raw_val), "n_test": len(raw_test),
    }
    split = ChronologicalSplit(train=raw_train, validation=raw_val, test=raw_test, boundaries=boundaries)

    def _X(label: str) -> np.ndarray:
        return matrix[matrix["_split"] == label][FEATURE_COLUMNS].to_numpy(dtype=float)

    return {
        "raw": raw,
        "matrix": matrix,
        "split": split,
        "X_train": _X("train"),
        "X_validation": _X("validation"),
        "X_test": _X("test"),
    }


def _normal_test_metrics(scores: np.ndarray, frame: pd.DataFrame, threshold: float) -> dict:
    alerts = scores >= threshold
    n = len(scores)
    n_alert = int(alerts.sum())
    days = max((frame["window_start"].max() - frame["window_start"].min()).total_seconds() / 86400.0, 1e-9)
    n_assets = frame["src_asset_id"].nunique()
    n_rel = frame["relationship_id"].nunique()
    return {
        "rows": n,
        "score_mean": float(np.mean(scores)) if n else 0.0,
        "score_p50": float(np.percentile(scores, 50)) if n else 0.0,
        "score_p90": float(np.percentile(scores, 90)) if n else 0.0,
        "score_p99": float(np.percentile(scores, 99)) if n else 0.0,
        "alerts": n_alert,
        "alert_rate": float(n_alert / n) if n else 0.0,
        "alerts_per_day": float(n_alert / days),
        "alerts_per_asset_per_day": float(n_alert / max(n_assets, 1) / days),
        "alerts_per_relationship_per_day": float(n_alert / max(n_rel, 1) / days),
    }


def _latency_and_memory(model, X: np.ndarray) -> dict:
    tracemalloc.start()
    t0 = time.perf_counter()
    _ = model.score(X)
    elapsed = time.perf_counter() - t0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    per_row_ms = (elapsed / max(len(X), 1)) * 1000.0
    return {
        "inference_seconds_total": elapsed,
        "inference_ms_per_row": per_row_ms,
        "peak_memory_mb": peak / (1024 * 1024),
    }


def package_artifact(name: str, model, statistical: StatisticalEdgeModel, calibration: dict,
                     metrics: dict, manifest: dict) -> Path:
    out = ARTIFACTS_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    model.save(out / "model.joblib")
    statistical.save(out / "statistical.joblib")
    (out / "feature_config.json").write_text(json.dumps(feature_config(), indent=2))
    (out / "calibration.json").write_text(json.dumps(calibration, indent=2))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out


def train_single(model_name: str, data: dict, dataset_id: str, window: str) -> dict:
    cfg = load_config()
    statistical = StatisticalEdgeModel(cfg).fit(data["X_train"])
    if model_name == "statistical":
        model = statistical
    elif model_name == "isolation_forest":
        model = IsolationForestEdgeModel(cfg).fit(data["X_train"])
    elif model_name == "autoencoder":
        model = AutoencoderEdgeModel(cfg).fit(data["X_train"])
    else:
        raise ValueError(f"unknown model {model_name}")

    model.calibrate_normalization(data["X_validation"])
    val_scores = np.clip(model.score(data["X_validation"]), 0.0, 1.0)
    test_scores = np.clip(model.score(data["X_test"]), 0.0, 1.0)
    calib = calibrate(val_scores, cfg)
    normal = _normal_test_metrics(test_scores, data["split"].test, calib["threshold"])
    perf = _latency_and_memory(model, data["X_test"])

    version = getattr(model, "model_version", model_name)
    manifest = {
        "model_version": version,
        "dataset_id": dataset_id,
        "window": window,
        "feature_schema_version": feature_config()["feature_schema_version"],
        "split_boundaries": data["split"].boundaries,
        "train_time_range": data["split"].boundaries["train"],
        "validation_time_range": data["split"].boundaries["validation"],
        "test_time_range": data["split"].boundaries["test"],
        "random_seed": cfg.get("random_seed"),
        "trained_at": datetime.now(UTC).isoformat(),
    }
    metrics = {"normal_test": normal, "calibration": calib, "performance": perf}
    artifact_dir = package_artifact(version, model, statistical, calib, metrics, manifest)
    size_bytes = sum(p.stat().st_size for p in artifact_dir.glob("*"))

    record = {
        "experiment_id": f"EXP-{model_name}",
        "model_type": version,
        "dataset_version": f"{dataset_id}:v0.2:{window}",
        "feature_schema_version": feature_config()["feature_schema_version"],
        "train_time_range": manifest["train_time_range"],
        "validation_time_range": manifest["validation_time_range"],
        "test_time_range": manifest["test_time_range"],
        "hyperparameters": _hyperparams(model_name, cfg),
        "metrics": {"normal_test": normal, "performance": perf},
        "threshold": calib["threshold"],
        "artifact_path": str(artifact_dir),
        "artifact_size_bytes": size_bytes,
        "random_seed": cfg.get("random_seed"),
    }
    record_experiment(record)
    return {"model": model, "statistical": statistical, "calibration": calib,
            "metrics": metrics, "manifest": manifest, "artifact_dir": str(artifact_dir),
            "artifact_size_bytes": size_bytes, "test_scores": test_scores,
            "val_scores": val_scores, "record": record}


def _hyperparams(model_name: str, cfg: dict) -> dict:
    if model_name == "statistical":
        return {"z_clip": cfg["statistical"]["z_clip"], "components": list(cfg["statistical"]["components"])}
    if model_name == "isolation_forest":
        return dict(cfg["isolation_forest"])
    return dict(cfg["autoencoder"])


def train_all(dataset_id: str = "unsw_iotraffic", window: str = "30s") -> dict:
    data = build_dataset(dataset_id, window)
    results = {}
    for name in ("statistical", "isolation_forest", "autoencoder"):
        results[name] = train_single(name, data, dataset_id, window)
    results["_data"] = data
    return results
