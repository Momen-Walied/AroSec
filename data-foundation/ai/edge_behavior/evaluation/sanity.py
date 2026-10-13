"""X-IIoTID sanity check (qualitative). NOT validated detection performance."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ai.edge_behavior.features.builder import load_edge_feature_windows
from src.config import get_settings


def _label_windows(dataset_id: str = "x_iiotid") -> pd.DataFrame:
    settings = get_settings()
    path = settings.processed_dir / "labels" / f"{dataset_id}.parquet"
    if not path.exists():
        return pd.DataFrame()
    labels = pd.read_parquet(path)
    labels["event_time"] = pd.to_datetime(labels["event_time"], utc=True)
    return labels


def xiiotid_sanity(scorer, threshold: float, dataset_id: str = "x_iiotid",
                   window: str = "30s") -> dict:
    features = load_edge_feature_windows(dataset_id, window)
    scored = scorer.score_batch(features)
    scored["window_start"] = pd.to_datetime(scored["window_start"], utc=True)

    labels = _label_windows(dataset_id)
    attack_mask = np.zeros(len(scored), dtype=bool)
    lateral_mask = np.zeros(len(scored), dtype=bool)
    if not labels.empty:
        lookup: dict[tuple[str, str], list[int]] = {}
        for i, row in scored.reset_index(drop=True).iterrows():
            lookup.setdefault((row["src_asset_id"], row["dst_asset_id"]), []).append(i)
        for _, lab in labels.iterrows():
            key = (lab.get("src_asset_id"), lab.get("dst_asset_id"))
            for i in lookup.get(key, []):
                ws, we = scored.iloc[i]["window_start"], pd.to_datetime(scored.iloc[i]["window_end"], utc=True)
                if ws <= lab["event_time"] < we:
                    attack_mask[i] = bool(lab.get("is_attack", False))
                    lateral_mask[i] = bool(lab.get("is_lateral_movement", False))

    scores = scored["anomaly_score"].to_numpy()
    result = {
        "rows": len(scored),
        "labelled_attack_windows": int(attack_mask.sum()),
        "labelled_lateral_movement_windows": int(lateral_mask.sum()),
        "threshold": threshold,
    }
    if attack_mask.sum() > 0 and (~attack_mask).sum() > 0:
        from sklearn.metrics import average_precision_score, roc_auc_score

        y = attack_mask.astype(int)
        result["attack_score_mean"] = float(scores[attack_mask].mean())
        result["benign_score_mean"] = float(scores[~attack_mask].mean())
        result["roc_auc"] = float(roc_auc_score(y, scores))
        result["pr_auc"] = float(average_precision_score(y, scores))
        result["attack_alert_rate"] = float((scores[attack_mask] >= threshold).mean())
        result["benign_alert_rate"] = float((scores[~attack_mask] >= threshold).mean())
    return result
