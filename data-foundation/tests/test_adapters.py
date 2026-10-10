"""Adapter contract + real-data smoke tests."""
from __future__ import annotations

import pytest

from src.datasets.registry import get_adapter, load_registry


def test_registry_has_all_datasets():
    ids = load_registry().ids()
    assert set(ids) == {"cicapt_iiot", "x_iiotid", "unsw_iotraffic", "edge_iiotset", "ciciot2023"}


def test_adapter_contract_methods():
    adapter = get_adapter("cicapt_iiot")
    for method in ("inspect", "download", "validate_raw", "load_raw",
                   "normalize_assets", "normalize_edges", "normalize_labels",
                   "normalize_campaigns", "generate_graph_events", "normalize"):
        assert callable(getattr(adapter, method))


def test_cicapt_synthetic_scenario():
    from src.datasets.cicapt import CicaptAdapter

    adapter = CicaptAdapter(synthetic=True)
    nd = adapter.normalize(30)
    ids = {a.asset_id for a in nd.assets}
    assert "asset:cicapt:host-cam-01" in ids
    assert "asset:cicapt:host-nvr-01" in ids
    assert "asset:cicapt:host-eng-pc-03" in ids
    assert "asset:cicapt:host-plc-07" in ids

    def edge(src, dst):
        return [e for e in nd.edges if e.src_asset_id.endswith(src) and e.dst_asset_id.endswith(dst)]

    assert edge("cam-01", "eng-pc-03")[0].is_new_peer is True
    assert edge("eng-pc-03", "plc-07")[0].is_new_peer is True
    assert edge("cam-01", "nvr-01")[0].is_new_peer is True  # first in fixture
    assert len(nd.campaigns) == 1
    assert any(lbl.is_lateral_movement for lbl in nd.labels)


def test_cicapt_manual_download_status():
    result = get_adapter("cicapt_iiot").download("sample")
    assert result.status == "MANUAL_DOWNLOAD_REQUIRED"
    assert "cicapt" in result.notes.lower() or "form" in result.notes.lower()


@pytest.mark.parametrize("dataset_id", ["unsw_iotraffic", "x_iiotid"])
def test_real_datasets_if_present(dataset_id):
    adapter = get_adapter(dataset_id)
    validation = adapter.validate_raw()
    if not any(name == "flows_dir_exists" and ok for name, ok, _ in validation.checks) and \
       not any(name == "csv_present" and ok for name, ok, _ in validation.checks):
        pytest.skip(f"{dataset_id} raw data not present")
    bundle = adapter.load_raw()
    assert bundle.observations
    obs = bundle.observations[0]
    assert obs.timestamp is not None


def test_xiiotid_lateral_movement_labels_present():
    adapter = get_adapter("x_iiotid")
    if not adapter._csv_candidates():
        pytest.skip("x_iiotid not present")
    nd = adapter.normalize(30)
    assert any(lbl.is_lateral_movement for lbl in nd.labels)
    assert any(lbl.attack_category == "unknown" for lbl in nd.labels)
