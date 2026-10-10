"""Dataset registry: loads ``configs/datasets.yaml`` and resolves adapters."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.config import PROJECT_ROOT, get_settings
from src.datasets.base import DatasetAdapter
from src.schemas.base import DatasetStatus, SourceDataset


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset_id: str
    name: str
    long_name: str | None = None
    year: int | None = None
    official_url: str | None = None
    download_url: str | None = None
    download_access: str | None = None
    license: str | None = None
    license_notes: str | None = None
    automated_download_supported: bool | str | None = None
    manual_download_required: bool | str | None = None
    raw_formats: list[str] = Field(default_factory=list)
    contains_pcap: bool | str | None = None
    contains_flows: bool | str | None = None
    contains_labels: bool | str | None = None
    contains_attack_stage: bool | str | None = None
    contains_lateral_movement: bool | str | None = None
    contains_device_identity: bool | str | None = None
    contains_provenance: bool | str | None = None
    time_information_quality: str | None = None
    estimated_download_size: str | None = None
    local_path: str | None = None
    status: str = DatasetStatus.NOT_CHECKED.value
    priority: int = 99
    notes: str | None = None

    @property
    def source(self) -> SourceDataset:
        return SourceDataset(self.dataset_id)


class Registry:
    def __init__(self, records: dict[str, DatasetRecord]) -> None:
        self.records = records

    def get(self, dataset_id: str) -> DatasetRecord:
        if dataset_id not in self.records:
            raise KeyError(f"unknown dataset_id: {dataset_id!r}. known: {sorted(self.records)}")
        return self.records[dataset_id]

    def ids(self) -> list[str]:
        return sorted(self.records, key=lambda d: self.records[d].priority)

    def by_status(self, status: str) -> list[DatasetRecord]:
        return [r for r in self.records.values() if r.status == status]

    def as_dicts(self) -> list[dict[str, Any]]:
        return [self.records[d].model_dump() for d in self.ids()]


@lru_cache(maxsize=1)
def load_registry(path: str | None = None) -> Registry:
    config_path = PROJECT_ROOT / "configs" / "datasets.yaml" if path is None else None
    source_path = path or (get_settings().configs_dir / "datasets.yaml")
    if config_path is not None and not source_path.exists():
        source_path = config_path
    with open(source_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    records = {r["dataset_id"]: DatasetRecord(**r) for r in data.get("datasets", {}).values()}
    return Registry(records)


def get_adapter(dataset_id: str) -> DatasetAdapter:
    from src.datasets.cicapt import CicaptAdapter
    from src.datasets.ciciot2023 import CICIoT2023Adapter
    from src.datasets.edge_iiotset import EdgeIIoTSetAdapter
    from src.datasets.unsw_iotraffic import UnswIoTrafficAdapter
    from src.datasets.xiiotid import XIIoTIDAdapter

    adapters: dict[str, type[DatasetAdapter]] = {
        "cicapt_iiot": CicaptAdapter,
        "x_iiotid": XIIoTIDAdapter,
        "unsw_iotraffic": UnswIoTrafficAdapter,
        "edge_iiotset": EdgeIIoTSetAdapter,
        "ciciot2023": CICIoT2023Adapter,
    }
    if dataset_id not in adapters:
        raise KeyError(f"no adapter registered for {dataset_id!r}")
    return adapters[dataset_id]()
