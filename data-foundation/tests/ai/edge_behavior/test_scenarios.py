"""Synthetic scenario detection tests (statistical baseline)."""
from __future__ import annotations

from ai.edge_behavior.baselines.statistical import StatisticalEdgeModel
from ai.edge_behavior.calibration import calibrate
from ai.edge_behavior.evaluation.scenarios import build_scenario_frames
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix
from tests.ai.edge_behavior._helpers import make_frame


def _normal_frame(n=400):
    df = make_frame(n)
    df["new_peer"] = False
    df["protocol_novelty_count"] = 0
    df["protocol_novelty_ratio"] = 0.0
    df["port_novelty_count"] = 0
    df["src_new_peer_count"] = 0
    df["connections_count"] = 2
    df["packet_count"] = 20
    df["outbound_bytes"] = 640
    df["inbound_bytes"] = 600
    df["historical_connection_count"] = 100
    df["relationship_age_seconds"] = 3600.0
    df["src_unique_peer_count"] = 3
    df["unique_destination_ports"] = 1
    df["unique_source_ports"] = 1
    df["observed_destination_ports"] = [[443]] * len(df)
    df["observed_source_ports"] = [[50000]] * len(df)
    df["protocol_distribution"] = [{"TCP": 2}] * len(df)
    df["application_protocol_distribution"] = [{}] * len(df)
    return df


def _detection_rate(model, threshold, frame):
    X = build_feature_matrix(frame)[FEATURE_COLUMNS].to_numpy(dtype=float)
    return float((model.score(X) >= threshold).mean())


def test_novelty_scenarios_detected():
    normal = _normal_frame()
    X = build_feature_matrix(normal)[FEATURE_COLUMNS].to_numpy(dtype=float)
    model = StatisticalEdgeModel().fit(X)
    threshold = calibrate(model.score(X))["threshold"]
    frames = build_scenario_frames(normal.tail(120).reset_index(drop=True), 120, seed=7)

    for scenario in ("SCN-001_NEW_PEER", "SCN-002_NEW_PORT",
                     "SCN-003_NEW_PROTOCOL", "SCN-004_FAN_OUT_BURST",
                     "SCN-006_COMPOUND"):
        rate = _detection_rate(model, threshold, frames[scenario])
        assert rate >= 0.8, f"{scenario} detection rate too low: {rate}"


def test_normal_rows_low_scores():
    normal = _normal_frame()
    X = build_feature_matrix(normal)[FEATURE_COLUMNS].to_numpy(dtype=float)
    model = StatisticalEdgeModel().fit(X)
    assert float(model.score(X).max()) <= 0.05
