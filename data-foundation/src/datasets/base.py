"""Dataset adapter contract.

Every external dataset implements :class:`DatasetAdapter`. Dataset-specific
parsing lives ONLY in the adapter; all graph/identity/aggregation logic is shared.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from src.config import Settings, get_settings
from src.schemas import Asset, AttackLabel, Campaign, CommunicationEdge, GraphEvent
from src.schemas.base import ContractModel, SourceDataset, ensure_utc


class RawObservation(ContractModel):
    """One atomic, dataset-independent communication observation.

    ``bytes_out``/``bytes_in`` are DIRECTIONAL relative to the initiator
    (out = initiator -> responder).
    """

    timestamp: datetime
    src_ip: str | None = None
    dst_ip: str | None = None
    src_mac: str | None = None
    dst_mac: str | None = None
    src_port: int | None = Field(None, ge=0, le=65535)
    dst_port: int | None = Field(None, ge=0, le=65535)

    network_protocol: str | None = None
    application_protocol: str | None = None

    bytes_out: int = Field(0, ge=0)
    bytes_in: int = Field(0, ge=0)
    packet_count: int = Field(1, ge=0)
    connection_count: int = Field(1, ge=0)

    src_hostname: str | None = None
    dst_hostname: str | None = None
    src_device: str | None = None
    dst_device: str | None = None

    original_label: str | None = None
    original_sub_label: str | None = None
    campaign_key: str | None = None

    evidence_source: str = "raw"

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @property
    def src_identity_key(self) -> str | None:
        return self.src_mac or self.src_hostname or self.src_device or self.src_ip

    @property
    def dst_identity_key(self) -> str | None:
        return self.dst_mac or self.dst_hostname or self.dst_device or self.dst_ip


class CampaignSeed(ContractModel):
    """A campaign as it appears in the source dataset (pre-normalization)."""

    campaign_id_source: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    entry_asset_key: str | None = None
    affected_asset_keys: list[str] = Field(default_factory=list)
    stage_labels: list[str] = Field(default_factory=list)
    probable_target_asset_key: str | None = None
    probable_objective: str | None = None
    ground_truth_available: bool = True

    @field_validator("start_time", "end_time")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)


@dataclass
class RawBundle:
    observations: list[RawObservation] = field(default_factory=list)
    extra_assets: list[Asset] = field(default_factory=list)
    campaign_seeds: list[CampaignSeed] = field(default_factory=list)


@dataclass
class NormalizedData:
    dataset_id: str
    assets: list[Asset] = field(default_factory=list)
    edges: list[CommunicationEdge] = field(default_factory=list)
    labels: list[AttackLabel] = field(default_factory=list)
    campaigns: list[Campaign] = field(default_factory=list)
    events: list[GraphEvent] = field(default_factory=list)
    raw_observation_count: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.assets or self.edges or self.labels or self.campaigns)


@dataclass
class DownloadResult:
    dataset_id: str
    status: str
    fetched: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    bytes_total: int = 0
    notes: str = ""


@dataclass
class RawValidationResult:
    dataset_id: str
    ok: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))
        self.ok = self.ok and passed


@dataclass
class InspectionReport:
    dataset_id: str
    status: str
    local_path: str
    present: bool
    files: list[dict[str, object]] = field(default_factory=list)
    notes: str = ""

    def to_markdown(self) -> str:
        lines = [f"# {self.dataset_id} — inspection", ""]
        lines.append(f"- status: **{self.status}**")
        lines.append(f"- local_path: `{self.local_path}`")
        lines.append(f"- present: {self.present}")
        if self.notes:
            lines.append(f"- notes: {self.notes}")
        lines.append("")
        if self.files:
            lines.append("| file | size (bytes) |")
            lines.append("|---|---:|")
            for f in self.files:
                lines.append(f"| {f.get('path')} | {f.get('size')} |")
        return "\n".join(lines) + "\n"


class DatasetAdapter(ABC):
    """Base class for all dataset adapters.

    Subclasses implement dataset-specific methods only. Shared normalization
    (identity, aggregation, events) is provided here and lives in
    :mod:`src.normalization.pipeline`.
    """

    dataset_id: str = ""
    source: SourceDataset = SourceDataset.SYNTHETIC

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def raw_dir(self) -> Path:
        return self.settings.dataset_raw_dir(self.dataset_id)

    @property
    def interim_dir(self) -> Path:
        return self.settings.dataset_interim_dir(self.dataset_id)

    # ---- required dataset-specific behaviour -------------------------------
    @abstractmethod
    def inspect(self) -> InspectionReport:
        ...

    @abstractmethod
    def download(self, mode: str = "sample") -> DownloadResult:
        ...

    @abstractmethod
    def validate_raw(self) -> RawValidationResult:
        ...

    @abstractmethod
    def load_raw(self) -> RawBundle:
        ...

    # ---- shared normalization (do NOT override in dataset code) ------------
    def normalize_assets(self, bundle: RawBundle) -> list[Asset]:
        from src.normalization import pipeline

        return pipeline.build_assets(bundle, self.source)

    def normalize_edges(self, bundle: RawBundle, window_seconds: int | None = None) -> list[CommunicationEdge]:
        from src.normalization import pipeline

        win = window_seconds or self.settings.window_seconds
        assets = self.normalize_assets(bundle)
        return pipeline.build_edges(bundle, assets, self.source, win)

    def normalize_labels(self, bundle: RawBundle, assets: list[Asset] | None = None) -> list[AttackLabel]:
        from src.normalization import pipeline

        return pipeline.build_labels(bundle, assets or self.normalize_assets(bundle), self.source)

    def normalize_campaigns(self, bundle: RawBundle, assets: list[Asset] | None = None) -> list[Campaign]:
        from src.normalization import pipeline

        return pipeline.build_campaigns(bundle, assets or self.normalize_assets(bundle), self.source)

    def generate_graph_events(
        self,
        assets: list[Asset],
        edges: list[CommunicationEdge],
    ) -> list[GraphEvent]:
        from src.normalization import pipeline

        return pipeline.build_graph_events(assets, edges, self.source)

    def normalize(self, window_seconds: int | None = None) -> NormalizedData:
        bundle = self.load_raw()
        assets = self.normalize_assets(bundle)
        edges = self.normalize_edges(bundle, window_seconds)
        labels = self.normalize_labels(bundle, assets)
        campaigns = self.normalize_campaigns(bundle, assets)
        events = self.generate_graph_events(assets, edges)
        return NormalizedData(
            dataset_id=self.dataset_id,
            assets=assets,
            edges=edges,
            labels=labels,
            campaigns=campaigns,
            events=events,
            raw_observation_count=len(bundle.observations),
        )
