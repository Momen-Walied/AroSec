"""Schema contract tests."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.schemas import (
    Asset,
    AttackLabel,
    Campaign,
    CommunicationEdge,
    EdgeFeatureWindow,
    GraphEvent,
)
from src.schemas.base import AttackCategory, GraphEventType, SourceDataset

UTC = UTC
T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)
T1 = datetime(2024, 3, 2, 2, 14, 0, tzinfo=UTC)


def test_asset_requires_namespaced_id():
    with pytest.raises(ValidationError):
        Asset(asset_id="10.0.0.21", ip_addresses=["10.0.0.21"], dataset_source=SourceDataset.SYNTHETIC)


def test_asset_rejects_bare_ip_id():
    with pytest.raises(ValidationError):
        Asset(asset_id="10.0.0.21", dataset_source=SourceDataset.SYNTHETIC)


def test_asset_mac_normalized_and_ip_deduped():
    a = Asset(asset_id="asset:synth:mac-aabbccddeeff", ip_addresses=["10.0.0.5", "10.0.0.5"],
              mac_addresses=["AA-BB-CC-DD-EE-FF"], dataset_source=SourceDataset.SYNTHETIC)
    assert a.ip_addresses == ["10.0.0.5"]
    assert a.mac_addresses == ["aa:bb:cc:dd:ee:ff"]


def test_asset_temporal_order_enforced():
    with pytest.raises(ValidationError):
        Asset(asset_id="asset:synth:x", dataset_source=SourceDataset.SYNTHETIC,
              first_seen=T1, last_seen=T0)


def test_asset_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        Asset(asset_id="asset:synth:x", dataset_source=SourceDataset.SYNTHETIC, bogus=1)


def test_edge_rejects_ai_fields():
    with pytest.raises(ValidationError):
        CommunicationEdge(
            edge_id="edge:a|b|COMMUNICATES_WITH|TCP", src_asset_id="asset:synth:a",
            dst_asset_id="asset:synth:b", window_start=T0, window_end=T1,
            first_seen=T0, last_seen=T1, dataset_source=SourceDataset.SYNTHETIC,
            attack_probability=0.9,
        )


def test_edge_window_order_enforced():
    with pytest.raises(ValidationError):
        CommunicationEdge(
            edge_id="edge:a|b|COMMUNICATES_WITH|TCP", src_asset_id="asset:synth:a",
            dst_asset_id="asset:synth:b", window_start=T1, window_end=T0,
            first_seen=T0, last_seen=T1, dataset_source=SourceDataset.SYNTHETIC,
        )


def test_edge_negative_counters_rejected():
    with pytest.raises(ValidationError):
        CommunicationEdge(
            edge_id="edge:a|b|COMMUNICATES_WITH|TCP", src_asset_id="asset:synth:a",
            dst_asset_id="asset:synth:b", window_start=T0, window_end=T1,
            first_seen=T0, last_seen=T1, dataset_source=SourceDataset.SYNTHETIC,
            bytes_out=-5,
        )


def test_label_consistency():
    with pytest.raises(ValidationError):
        AttackLabel(is_attack=True, attack_category=AttackCategory.BENIGN,
                    dataset_source=SourceDataset.SYNTHETIC)
    with pytest.raises(ValidationError):
        AttackLabel(is_attack=False, attack_category=AttackCategory.DOS,
                    dataset_source=SourceDataset.SYNTHETIC)


def test_campaign_no_inferred_objective_without_ground_truth():
    with pytest.raises(ValidationError):
        Campaign(campaign_id="campaign:x:y", ground_truth_available=False,
                 probable_objective="steal data", dataset_source=SourceDataset.SYNTHETIC)


def test_campaign_allows_null_objective():
    c = Campaign(campaign_id="campaign:x:y", ground_truth_available=False,
                 dataset_source=SourceDataset.SYNTHETIC)
    assert c.probable_objective is None


def test_graph_event_requires_refs():
    with pytest.raises(ValidationError):
        GraphEvent(event_id="evt:abc", timestamp=T0, event_type=GraphEventType.EDGE_ADDED,
                   dataset_source=SourceDataset.SYNTHETIC)
    evt = GraphEvent(event_id="evt:abc", timestamp=T0, event_type=GraphEventType.ASSET_ADDED,
                     asset_id="asset:synth:a", dataset_source=SourceDataset.SYNTHETIC)
    assert evt.event_type == "ASSET_ADDED"


def test_edge_rejects_future_last_seen():
    with pytest.raises(ValidationError):
        CommunicationEdge(
            edge_id="edge:a|b|COMMUNICATES_WITH|TCP", src_asset_id="asset:synth:a",
            dst_asset_id="asset:synth:b", window_start=T0, window_end=T1,
            first_seen=T0, last_seen=datetime(2024, 3, 2, 3, 0, tzinfo=UTC),
            dataset_source=SourceDataset.SYNTHETIC,
        )


def test_feature_window_no_negative():
    with pytest.raises(ValidationError):
        EdgeFeatureWindow(src_asset_id="asset:synth:a", dst_asset_id="asset:synth:b",
                          window_start=T0, window_end=T1, connections_count=-1,
                          dataset_source=SourceDataset.SYNTHETIC)
