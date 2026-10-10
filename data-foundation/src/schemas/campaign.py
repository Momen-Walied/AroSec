"""Attack campaign schema v0.1.

For ground-truth datasets (e.g. CICAPT-IIoT) populate ONLY fields explicitly
supported by the dataset. Do NOT infer "probable objective"/"probable target"
during v0.1 unless explicitly labeled — ``unknown`` is acceptable and expected.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    AttackStage,
    ContractModel,
    SourceDataset,
    ensure_utc,
)


class ObservedPathStep(ContractModel):
    """One ordered step in an observed attack path (node and/or edge)."""

    step_index: int = Field(..., ge=0)
    asset_id: str | None = None
    edge_id: str | None = None
    timestamp: datetime | None = None
    note: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)


class Campaign(ContractModel):
    schema_version: str = SCHEMA_VERSION

    campaign_id: str

    start_time: datetime | None = None
    end_time: datetime | None = None

    entry_asset_id: str | None = None
    affected_asset_ids: list[str] = Field(default_factory=list)
    observed_path: list[ObservedPathStep] = Field(default_factory=list)
    attack_stages: list[AttackStage] = Field(default_factory=list)

    probable_target_asset_id: str | None = None
    probable_objective: str | None = None

    ground_truth_available: bool = False
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    dataset_source: SourceDataset

    @field_validator("start_time", "end_time")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)

    @field_validator("campaign_id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("campaign_id must be non-empty")
        return v

    @model_validator(mode="after")
    def _ordering(self) -> Campaign:
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("start_time must be <= end_time")
        return self

    @model_validator(mode="after")
    def _no_inferred_objective_without_ground_truth(self) -> Campaign:
        if not self.ground_truth_available:
            if self.probable_objective is not None or self.probable_target_asset_id is not None:
                raise ValueError(
                    "probable_objective / probable_target_asset_id must be null when "
                    "ground_truth_available is False (no inference in Data Foundation v0.1)"
                )
        return self
