"""Edge Behavior feature preparation (v1).

Deterministic, versioned, and strictly causal: every derived feature at window W
uses only information from windows strictly before W. Operates on the FROZEN
v0.2 ``EdgeFeatureWindowV2`` table and produces a derived ML matrix — it never
mutates v0.2 data.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import get_settings

FEATURE_SCHEMA_VERSION = "edge_features_v1"

WELL_KNOWN_PORTS: frozenset[int] = frozenset({
    20, 21, 22, 23, 25, 53, 67, 68, 69, 80, 110, 123, 137, 138, 139, 143, 161, 162, 179,
    443, 445, 514, 515, 554, 587, 636, 993, 995, 1080, 1194, 1433, 1521, 1701, 1723, 1883,
    1900, 2049, 2082, 2083, 3306, 3389, 47808, 5060, 5061, 5222, 5353, 5432, 5683, 6379,
    8080, 8443, 8883, 9100, 50000,
})

KEY_COLUMNS = [
    "relationship_id", "src_asset_id", "dst_asset_id", "window_start", "window_end",
    "dataset_source",
]

FEATURE_COLUMNS: list[str] = [
    # volume
    "log_connections", "log_packets", "log_out_bytes", "log_in_bytes", "out_in_ratio",
    # ports
    "log_unique_dst_ports", "log_unique_src_ports", "port_novelty_count",
    "port_entropy", "port_wellknown_fraction", "port_privileged_fraction",
    # network protocols
    "n_protocols", "protocol_entropy", "dominant_protocol_share",
    "protocol_novelty_count", "protocol_novelty_ratio",
    # application protocols
    "n_app_protocols", "app_protocol_entropy", "app_protocol_novelty_count",
    # peer / fan-out
    "new_peer", "log_src_unique_peers", "log_src_new_peers", "fan_out_ratio",
    # age / history
    "log_relationship_age", "log_historical_conn",
]


def _entropy(counts: list[float]) -> float:
    total = float(sum(counts))
    if total <= 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * math.log(p) for p in probs))


def _decode_map(value: object) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): float(v) for k, v in value.items()}
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return {str(k): float(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _decode_ports(value: object) -> list[int]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            return [int(v) for v in parsed] if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
    return []


def load_edge_feature_windows(dataset_id: str = "unsw_iotraffic", window: str = "30s",
                              processed_dir: Path | None = None) -> pd.DataFrame:
    settings = get_settings()
    base = processed_dir or (settings.processed_dir / "v2" / "edge_features")
    path = base / f"{dataset_id}_{window}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"v0.2 edge features not found: {path}. Run `build-v2` first.")
    df = pd.read_parquet(path)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df["window_end"] = pd.to_datetime(df["window_end"], utc=True)
    return df


def load_asset_identity(dataset_id: str = "unsw_iotraffic",
                        processed_dir: Path | None = None) -> dict[str, dict]:
    settings = get_settings()
    base = processed_dir or (settings.processed_dir / "v2" / "assets")
    path = base / f"{dataset_id}.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return {
        str(r["asset_id"]): {
            "identity_method": str(r["identity_method"]),
            "identity_confidence": float(r["identity_confidence"]),
        }
        for _, r in df.iterrows()
    }


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic causal feature matrix from an EdgeFeatureWindowV2 frame."""
    work = df.copy()
    work["window_start"] = pd.to_datetime(work["window_start"], utc=True)
    work = work.sort_values(["relationship_id", "window_start"], kind="mergesort").reset_index(drop=True)

    proto_maps = work["protocol_distribution"].map(_decode_map)
    app_maps = work["application_protocol_distribution"].map(_decode_map)
    dst_ports = work["observed_destination_ports"].map(_decode_ports)

    n_protocols = proto_maps.map(len)
    proto_entropy = proto_maps.map(lambda m: _entropy(list(m.values())))
    proto_total = proto_maps.map(lambda m: float(sum(m.values())))
    dominant_share = [
        (max(m.values()) / total) if total > 0 else 0.0
        for m, total in zip(proto_maps, proto_total, strict=False)
    ]
    n_app = app_maps.map(len)
    app_entropy = app_maps.map(lambda m: _entropy(list(m.values())))

    def _frac(ports: list[int], predicate) -> float:
        if not ports:
            return 0.0
        return sum(1 for p in ports if predicate(p)) / len(ports)

    port_entropy = dst_ports.map(lambda ps: _entropy([1.0] * len(ps)))
    wellknown_frac = dst_ports.map(lambda ps: _frac(ps, lambda p: p in WELL_KNOWN_PORTS))
    privileged_frac = dst_ports.map(lambda ps: _frac(ps, lambda p: p < 1024))

    app_novelty = _causal_app_protocol_novelty(work, app_maps)

    features = pd.DataFrame({
        "relationship_id": work["relationship_id"].to_numpy(),
        "window_start": work["window_start"].to_numpy(),
        "log_connections": np.log1p(work["connections_count"].to_numpy(dtype=float)),
        "log_packets": np.log1p(work["packet_count"].to_numpy(dtype=float)),
        "log_out_bytes": np.log1p(work["outbound_bytes"].to_numpy(dtype=float)),
        "log_in_bytes": np.log1p(work["inbound_bytes"].to_numpy(dtype=float)),
        "out_in_ratio": np.log1p(
            work["outbound_bytes"].to_numpy(dtype=float)
            / (work["inbound_bytes"].to_numpy(dtype=float) + 1.0)
        ),
        "log_unique_dst_ports": np.log1p(work["unique_destination_ports"].to_numpy(dtype=float)),
        "log_unique_src_ports": np.log1p(work["unique_source_ports"].to_numpy(dtype=float)),
        "port_novelty_count": np.log1p(work["port_novelty_count"].to_numpy(dtype=float)),
        "port_entropy": port_entropy.to_numpy(dtype=float),
        "port_wellknown_fraction": wellknown_frac.to_numpy(dtype=float),
        "port_privileged_fraction": privileged_frac.to_numpy(dtype=float),
        "n_protocols": n_protocols.to_numpy(dtype=float),
        "protocol_entropy": proto_entropy.to_numpy(dtype=float),
        "dominant_protocol_share": np.asarray(dominant_share, dtype=float),
        "protocol_novelty_count": work["protocol_novelty_count"].to_numpy(dtype=float),
        "protocol_novelty_ratio": work["protocol_novelty_ratio"].fillna(0.0).to_numpy(dtype=float),
        "n_app_protocols": n_app.to_numpy(dtype=float),
        "app_protocol_entropy": app_entropy.to_numpy(dtype=float),
        "app_protocol_novelty_count": np.asarray(app_novelty, dtype=float),
        "new_peer": work["new_peer"].astype(float).to_numpy(),
        "log_src_unique_peers": np.log1p(work["src_unique_peer_count"].to_numpy(dtype=float)),
        "log_src_new_peers": np.log1p(work["src_new_peer_count"].to_numpy(dtype=float)),
        "fan_out_ratio": (
            work["src_new_peer_count"].to_numpy(dtype=float)
            / (work["src_unique_peer_count"].to_numpy(dtype=float) + 1.0)
        ),
        "log_relationship_age": np.log1p(work["relationship_age_seconds"].fillna(0.0).to_numpy(dtype=float)),
        "log_historical_conn": np.log1p(work["historical_connection_count"].to_numpy(dtype=float)),
    })

    key_cols = [c for c in KEY_COLUMNS if c in work.columns]
    meta = work[key_cols].copy()
    meta["window_start"] = pd.to_datetime(meta["window_start"], utc=True)
    return meta.merge(features, on=["relationship_id", "window_start"], how="left")


def _causal_app_protocol_novelty(work: pd.DataFrame, app_maps: pd.Series) -> list[int]:
    seen: dict[str, set[str]] = {}
    out: list[int] = []
    for rel, apps in zip(work["relationship_id"].to_numpy(), app_maps, strict=False):
        prior = seen.setdefault(rel, set())
        current = set(apps.keys())
        out.append(len(current - prior))
        prior |= current
    return out


def feature_config() -> dict:
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns": list(FEATURE_COLUMNS),
        "well_known_ports": sorted(WELL_KNOWN_PORTS),
        "transforms": {
            "log1p": [c for c in FEATURE_COLUMNS if c.startswith("log_")],
            "ratio": ["out_in_ratio", "fan_out_ratio", "dominant_protocol_share",
                      "protocol_novelty_ratio"],
        },
        "causality": "all derived features use windows strictly before the current window",
    }
