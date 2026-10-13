"""Evaluation metrics for Edge Behavior v1."""
from __future__ import annotations

import numpy as np
import pandas as pd


def temporal_stability(scored: pd.DataFrame, threshold: float) -> pd.DataFrame:
    df = scored.copy()
    df["date"] = pd.to_datetime(df["window_start"], utc=True).dt.date
    df["alert"] = df["anomaly_score"] >= threshold
    daily = df.groupby("date").agg(
        rows=("anomaly_score", "size"),
        alerts=("alert", "sum"),
        score_mean=("anomaly_score", "mean"),
        score_p95=("anomaly_score", lambda s: float(np.percentile(s, 95))),
    ).reset_index()
    daily["alert_rate"] = daily["alerts"] / daily["rows"]
    return daily


def alert_summary(scored: pd.DataFrame, threshold: float) -> dict:
    df = scored.copy()
    df["alert"] = df["anomaly_score"] >= threshold
    span_days = max(
        (pd.to_datetime(df["window_start"], utc=True).max()
         - pd.to_datetime(df["window_start"], utc=True).min()).total_seconds() / 86400.0, 1e-9)
    n_alert = int(df["alert"].sum())
    return {
        "rows": len(df),
        "alerts": n_alert,
        "alert_rate": float(n_alert / len(df)) if len(df) else 0.0,
        "span_days": span_days,
        "alerts_per_day": float(n_alert / span_days),
        "alerts_per_asset_per_day": float(n_alert / max(df["src_asset_id"].nunique(), 1) / span_days),
        "alerts_per_relationship_per_day": float(n_alert / max(df["relationship_id"].nunique(), 1) / span_days),
    }


def score_drift(daily: pd.DataFrame) -> dict:
    if daily.empty:
        return {"mean_of_daily_mean": 0.0, "std_of_daily_mean": 0.0}
    return {
        "mean_of_daily_mean": float(daily["score_mean"].mean()),
        "std_of_daily_mean": float(daily["score_mean"].std(ddof=0)),
        "max_daily_alert_rate": float(daily["alert_rate"].max()),
    }
