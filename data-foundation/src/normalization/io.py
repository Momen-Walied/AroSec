"""Parquet / JSONL IO for v0.1 contracts.

Contracts serialize to a canonical, column-stable table. Datetimes are stored as
UTC ``datetime64``; list-valued fields stay as arrays; nested model lists
(e.g. ``observed_path``) are JSON-encoded so the schema never drifts.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

import numpy as np
import pandas as pd
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DATETIME_COLUMNS = {
    "window_start", "window_end", "first_seen", "last_seen", "timestamp",
    "start_time", "end_time", "event_time",
}
JSON_ENCODED_COLUMNS = {
    "observed_path",
    "attack_stages",
    "affected_asset_ids",
    "evidence_sources",
    "identity_evidence",
    "protocol_distribution",
    "application_protocol_distribution",
}


def models_to_frame(models: Iterable[BaseModel]) -> pd.DataFrame:
    rows = [m.to_canonical_dict() for m in models]
    df = pd.DataFrame(rows)
    for col in DATETIME_COLUMNS.intersection(df.columns):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce", format="ISO8601")
    for col in JSON_ENCODED_COLUMNS.intersection(df.columns):
        df[col] = df[col].apply(lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v)
    return df


def _scalarize(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return [_scalarize(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_scalarize(v) for v in value.tolist()]
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def frame_to_records(df: pd.DataFrame) -> list[dict]:
    return [{key: _scalarize(value) for key, value in row.items()} for row in df.to_dict(orient="records")]


def write_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")
    return path


def write_jsonl(models: Iterable[BaseModel], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for model in models:
            fh.write(model.canonical_json() + "\n")
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


def frame_to_models(df: pd.DataFrame, model: type[T]) -> list[T]:
    """Rebuild validated contracts from a parquet frame (decodes JSON columns)."""
    records = frame_to_records(df)
    for record in records:
        for col in JSON_ENCODED_COLUMNS:
            value = record.get(col)
            if isinstance(value, str):
                try:
                    record[col] = json.loads(value)
                except json.JSONDecodeError:
                    pass
    return [model(**record) for record in records]


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def save_models(models: list[BaseModel], parquet_path: Path, jsonl_path: Path | None = None) -> Path:
    df = models_to_frame(models)
    write_parquet(df, parquet_path)
    if jsonl_path is not None:
        write_jsonl(models, jsonl_path)
    return parquet_path
