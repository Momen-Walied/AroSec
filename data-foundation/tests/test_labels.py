"""Label taxonomy + mapping tests (unknown preservation)."""
from __future__ import annotations

from src.normalization import pipeline
from src.normalization.label_map import map_label
from src.schemas.base import AttackCategory


def test_lateral_movement_mapping():
    m = map_label("Lateral Movement", "Lateral Movement")
    assert m.category == AttackCategory.LATERAL_MOVEMENT
    assert m.is_lateral_movement is True


def test_ddos_mapping():
    assert map_label("DDoS").category == AttackCategory.DDOS
    assert map_label("DoS").category == AttackCategory.DOS


def test_mitre_technique_mapping():
    m = map_label("T1021")
    assert m.category == AttackCategory.LATERAL_MOVEMENT
    assert m.technique == "T1021"


def test_benign_mapping():
    assert map_label("benign").category == AttackCategory.BENIGN
    assert map_label("Normal").category == AttackCategory.BENIGN


def test_unknown_label_preserved_not_forced():
    m = map_label("zzz_unmapped_label")
    assert m.category == AttackCategory.UNKNOWN
    assert m.confidence == 0.0


def test_build_labels_preserves_original(scenario_bundle, scenario_source):
    assets = pipeline.build_assets(scenario_bundle, scenario_source)
    labels = pipeline.build_labels(scenario_bundle, assets, scenario_source)
    attacks = [lbl for lbl in labels if lbl.is_attack]
    assert attacks
    assert all(lbl.original_label is not None for lbl in attacks)
    assert any(lbl.is_lateral_movement for lbl in attacks)
    assert all(lbl.campaign_id == "c1" for lbl in attacks)
