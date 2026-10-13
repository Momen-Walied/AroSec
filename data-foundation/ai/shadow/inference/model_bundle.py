"""Shadow model bundle: loads the selected Edge Behavior v1 fusion and validates it.

Selected production candidate: validation-weighted Statistical + Isolation Forest fusion.
The Autoencoder is NOT part of the v1 runtime. Model binaries are regeneration-only and
must be produced locally (see docs/AI_SHADOW_INTEGRATION_V1.md); the runtime never
downloads or retrains them.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.baselines.statistical import StatisticalEdgeModel
from ai.edge_behavior.calibration import severity_for
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION
from src.config import PROJECT_ROOT

BUNDLE_VERSION = "shadow-fusion-v1"


class ModelBundleError(RuntimeError):
    pass


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


class ShadowModelBundle:
    def __init__(self, spec: dict, components: list[tuple[str, BaseEdgeModel, float]],
                 statistical: StatisticalEdgeModel) -> None:
        self.spec = spec
        self.components = components
        self.statistical = statistical
        self.feature_schema_version = spec["feature_schema_version"]
        self.calibration = spec["calibration"]
        self.severity_thresholds = self.calibration.get("severity_thresholds", {})
        self.threshold = float(self.calibration.get("threshold", 0.5))
        self.model_version = spec.get("bundle_version", BUNDLE_VERSION)

    @classmethod
    def load(cls, bundle_path: Path) -> ShadowModelBundle:
        path = _resolve(bundle_path)
        if not path.exists():
            raise ModelBundleError(f"model bundle not found: {path}")
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise ModelBundleError(
                f"feature schema mismatch: bundle={spec.get('feature_schema_version')} "
                f"code={FEATURE_SCHEMA_VERSION}")

        components: list[tuple[str, BaseEdgeModel, float]] = []
        statistical: StatisticalEdgeModel | None = None
        for comp in spec["components"]:
            artifact = _resolve(comp["artifact"])
            model_path = artifact / "model.joblib"
            if not model_path.exists():
                raise ModelBundleError(
                    f"model artifact missing: {model_path}. Regenerate it (see docs).")
            model = BaseEdgeModel.load(model_path)
            if getattr(model, "model_version", None) != comp["model_version"]:
                raise ModelBundleError(
                    f"model version mismatch: artifact={getattr(model, 'model_version', None)} "
                    f"expected={comp['model_version']}")
            components.append((comp["name"], model, float(comp["weight"])))
            if comp["name"] == spec.get("reason_component", "statistical"):
                statistical = StatisticalEdgeModel.load(artifact / "statistical.joblib")
        if statistical is None:
            raise ModelBundleError("reason component not found in bundle")
        if not spec.get("calibration", {}).get("severity_thresholds"):
            raise ModelBundleError("bundle calibration missing severity_thresholds")
        return cls(spec, components, statistical)

    def score(self, X: np.ndarray) -> np.ndarray:
        total = sum(w for _, _, w in self.components) or 1.0
        acc = np.zeros(X.shape[0])
        for _name, model, w in self.components:
            acc += (w / total) * np.clip(model.score(X), 0.0, 1.0)
        return np.clip(acc, 0.0, 1.0)

    def severity(self, score: float) -> str:
        return severity_for(float(score), self.severity_thresholds)

    def explain(self, X: np.ndarray, row: int) -> dict:
        return {
            "reasons": self.statistical.reasons_for(X, row),
            "feature_contributions": self.statistical.feature_contributions(X, row),
        }

    def explain_batch(self, X: np.ndarray) -> tuple[list[list[dict]], list[dict]]:
        return self.statistical.explain_batch(X)


def build_bundle(out_path: Path, stat_weight: float = 0.603, if_weight: float = 0.397,
                 target_alert_rate: float = 0.01) -> Path:
    """Regenerate the fusion bundle JSON from the two Phase-1 artifacts + validation split."""
    from ai.edge_behavior.training.train import build_dataset

    stat_art = "ai/edge_behavior/artifacts/edge_behavior/edge-stat-v1"
    if_art = "ai/edge_behavior/artifacts/edge_behavior/edge-iforest-v1"
    stat = StatisticalEdgeModel.load(_resolve(stat_art) / "model.joblib")
    iforest = BaseEdgeModel.load(_resolve(if_art) / "model.joblib")

    data = build_dataset("unsw_iotraffic", "30s")
    X_val = data["X_validation"]
    fused_val = np.clip(stat_weight * np.clip(stat.score(X_val), 0, 1)
                        + if_weight * np.clip(iforest.score(X_val), 0, 1), 0, 1)
    total = stat_weight + if_weight
    fused_val = fused_val / total

    threshold = float(np.quantile(fused_val, 1 - target_alert_rate))
    rates = {"INFO": 1.0, "LOW": target_alert_rate, "MEDIUM": target_alert_rate / 2,
             "HIGH": target_alert_rate / 5, "CRITICAL": target_alert_rate / 20}
    sev = {k: (float(np.quantile(fused_val, 1 - r)) if r < 1 else 0.0) for k, r in rates.items()}
    prev = -1.0
    for k in ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        sev[k] = max(sev[k], prev)
        prev = sev[k]

    spec = {
        "bundle_version": BUNDLE_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "reason_component": "statistical",
        "components": [
            {"name": "statistical", "artifact": stat_art, "model_version": "edge-stat-v1", "weight": stat_weight},
            {"name": "isolation_forest", "artifact": if_art, "model_version": "edge-iforest-v1", "weight": if_weight},
        ],
        "calibration": {"threshold": threshold, "target_alert_rate": target_alert_rate,
                        "severity_thresholds": sev},
        "feature_columns": list(FEATURE_COLUMNS),
        "note": "Provisional shadow threshold. Recalibrate during shadow deployment.",
    }
    out_path = _resolve(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return out_path
