"""Unified attack-label schema v0.1.

External datasets use inconsistent labels. This is ONE internal taxonomy.
Rules:
  * Never silently force an unsupported label into a category -> use ``UNKNOWN``.
  * Always preserve ``original_label`` / ``original_sub_label``.
  * Uncertainty is explicit via ``ground_truth_confidence``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    AttackCategory,
    AttackStage,
    ContractModel,
    SourceDataset,
    ensure_utc,
)


class AttackLabel(ContractModel):
    schema_version: str = SCHEMA_VERSION

    is_attack: bool
    attack_category: AttackCategory = AttackCategory.UNKNOWN
    attack_stage: AttackStage = AttackStage.UNKNOWN
    technique: str | None = None

    is_lateral_movement: bool = False

    campaign_id: str | None = None

    ground_truth_confidence: float = Field(1.0, ge=0.0, le=1.0)

    original_label: str | None = None
    original_sub_label: str | None = None

    dataset_source: SourceDataset

    # Optional linkage to the graph facts this label annotates.
    src_asset_id: str | None = None
    dst_asset_id: str | None = None
    edge_id: str | None = None
    event_time: datetime | None = None

    @field_validator("event_time")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)

    @field_validator("technique", "original_label", "original_sub_label", "campaign_id", mode="before")
    @classmethod
    def _coerce_str(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, float) and v != v:
            return None
        return str(v).strip() or None

    @model_validator(mode="after")
    def _category_consistency(self) -> AttackLabel:
        if not self.is_attack and self.attack_category != AttackCategory.BENIGN:
            raise ValueError(
                "is_attack=False requires attack_category='benign' "
                f"(got {self.attack_category!r})"
            )
        if self.is_attack and self.attack_category == AttackCategory.BENIGN:
            raise ValueError("is_attack=True cannot have attack_category='benign'")
        return self
