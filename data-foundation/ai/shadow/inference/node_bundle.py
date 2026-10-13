"""Node model bundle loader with strict validation (regeneration-only artifacts).

Selected production candidate: ``node-stat-v1`` (threshold provisional). The runtime never
downloads or retrains; it fails clearly on a missing/incompatible bundle.
"""
from __future__ import annotations

import json
from pathlib import Path

from ai.node_behavior.config import NODE_FEATURE_SCHEMA_VERSION
from ai.node_behavior.inference.scorer import NodeBehaviorScorer


class NodeModelBundleError(RuntimeError):
    pass


def load_node_scorer(artifact_dir: Path, identity_map: dict | None = None) -> NodeBehaviorScorer:
    artifact_dir = Path(artifact_dir)
    required = ["model.joblib", "statistical.joblib", "calibration.json", "feature_config.json"]
    missing = [f for f in required if not (artifact_dir / f).exists()]
    if missing:
        raise NodeModelBundleError(f"node model artifact incomplete at {artifact_dir}: missing {missing}")
    try:
        scorer = NodeBehaviorScorer.from_artifact(artifact_dir, identity_map=identity_map)
    except Exception as exc:  # noqa: BLE001
        raise NodeModelBundleError(f"failed to load node model bundle {artifact_dir}: {exc}") from exc

    schema = scorer.feature_config.get("feature_schema_version")
    if schema != NODE_FEATURE_SCHEMA_VERSION:
        raise NodeModelBundleError(
            f"node feature schema mismatch: bundle={schema} code={NODE_FEATURE_SCHEMA_VERSION}")
    if getattr(scorer.model, "model_version", None) != scorer.model_version:
        raise NodeModelBundleError("node model version mismatch between artifact and scorer")
    if not scorer.calibration.get("severity_thresholds"):
        raise NodeModelBundleError("node model calibration missing severity_thresholds")
    json.loads((artifact_dir / "calibration.json").read_text())  # parse check
    return scorer
