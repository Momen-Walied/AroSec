"""Asset schema v0.1 — a node in the temporal cyber graph.

Identity rules (CRITICAL):
  * ``asset_id`` is STABLE and MUST NOT simply equal an IP address.
  * IP addresses are *observations*, not permanent identity.
  * Missing attributes stay null — never fabricate MAC / vendor / device type.
  * Source provenance is always preserved via ``evidence_sources``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    AssetType,
    ContractModel,
    Criticality,
    IdentityMethod,
    SourceDataset,
    ensure_utc,
    maybe_normalize_ip,
    maybe_normalize_mac,
)


class Asset(ContractModel):
    schema_version: str = SCHEMA_VERSION

    asset_id: str = Field(..., description="Stable id, e.g. 'asset:cicapt:10.0.0.21'. Never a bare IP.")
    asset_type: AssetType = AssetType.UNKNOWN
    asset_type_confidence: float = Field(0.0, ge=0.0, le=1.0)

    ip_addresses: list[str] = Field(default_factory=list)
    mac_addresses: list[str] = Field(default_factory=list)

    hostname: str | None = None
    vendor: str | None = None

    vlan_id: int | None = Field(None, ge=0, le=4095)
    subnet: str | None = None

    criticality: Criticality = Criticality.UNKNOWN

    first_seen: datetime | None = None
    last_seen: datetime | None = None

    identity_confidence: float = Field(0.0, ge=0.0, le=1.0)
    identity_method: IdentityMethod = IdentityMethod.UNKNOWN
    identity_evidence: list[str] = Field(default_factory=list)

    evidence_sources: list[str] = Field(default_factory=list)
    evidence_id: str | None = None
    source_record_id: str | None = None
    dataset_source: SourceDataset

    # ------------------------------------------------------------------ #
    @field_validator("asset_id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("asset_id must start with 'asset:'")
        if not v[len("asset:"):].strip():
            raise ValueError("asset_id must have a non-empty key after 'asset:'")
        return v

    @field_validator("ip_addresses", mode="before")
    @classmethod
    def _clean_ips(cls, v: object) -> list[str]:
        if v is None:
            return []
        out: list[str] = []
        for item in v:  # type: ignore[union-attr]
            norm = maybe_normalize_ip(item)
            if norm is not None and norm not in out:
                out.append(norm)
        return out

    @field_validator("mac_addresses", mode="before")
    @classmethod
    def _clean_macs(cls, v: object) -> list[str]:
        if v is None:
            return []
        out: list[str] = []
        for item in v:  # type: ignore[union-attr]
            norm = maybe_normalize_mac(item)
            if norm is not None and norm not in out:
                out.append(norm)
        return out

    @field_validator("hostname", "vendor", "subnet", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in {"", "null", "nan", "none", "unknown", "*"}:
            return None
        return v

    @field_validator("first_seen", "last_seen")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _temporal_order(self) -> Asset:
        if self.first_seen and self.last_seen and self.first_seen > self.last_seen:
            raise ValueError("first_seen must be <= last_seen")
        return self

    @model_validator(mode="after")
    def _no_bare_ip_identity(self) -> Asset:
        if self.asset_id in self.ip_addresses:
            raise ValueError("asset_id must not be a bare IP address")
        return self
