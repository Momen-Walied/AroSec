"""Graph Data Readiness contracts (Phase 4C).

AI/research-layer only. Describes structural ground truth, identity quality, readiness
status, and the Temporal GNN entry gate. No attack-stage semantics, no frozen-contract
changes, no neural dependency.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from src.schemas.base import ContractModel, ensure_utc

GROUND_TRUTH_SCHEMA = "structural_transition_ground_truth_v1"
READINESS_SCHEMA = "graph_data_readiness_v1"


class TransitionType(StrEnum):
    EXPECTED_STRUCTURAL_TRANSITION = "expected_structural_transition"
    UNUSUAL_STRUCTURAL_TRANSITION = "unusual_structural_transition"
    NORMAL_ROLE_CONSISTENT_NEW_EDGE = "normal_role_consistent_new_edge"
    ROLE_INCONSISTENT_NEW_EDGE = "role_inconsistent_new_edge"
    TOPOLOGY_REWIRING = "topology_rewiring"
    FANOUT_BURST = "fanout_burst"
    INBOUND_CONVERGENCE = "inbound_convergence"
    CHAIN_FORMATION = "chain_formation"
    PEER_SET_REPLACEMENT = "peer_set_replacement"
    CROSS_ZONE_COMMUNICATION = "cross_zone_communication"


class Expectedness(StrEnum):
    EXPECTED = "EXPECTED"
    UNUSUAL = "UNUSUAL"
    UNKNOWN = "UNKNOWN"


class ScenarioOrigin(StrEnum):
    LAB_CONTROLLED = "LAB_CONTROLLED"
    OPERATOR_CONFIRMED = "OPERATOR_CONFIRMED"
    SYNTHETIC = "SYNTHETIC"
    DATASET_LABEL = "DATASET_LABEL"


class GroundTruthSource(StrEnum):
    """Independent provenance for structural ground truth.

    Ground truth MUST come from an independent source, never from the anomaly outputs or
    telemetry patterns under evaluation.
    """

    LAB_ORCHESTRATOR = "LAB_ORCHESTRATOR"
    OPERATOR_ACTION_LOG = "OPERATOR_ACTION_LOG"
    EXPERIMENT_CONTROLLER = "EXPERIMENT_CONTROLLER"
    CHANGE_TICKET = "CHANGE_TICKET"
    DATASET_LABELS = "DATASET_LABELS"


class IdentityQualityLevel(StrEnum):
    LEVEL_0_IP_ONLY = "L0_ip_only"
    LEVEL_1_IP_MAC = "L1_ip_mac"
    LEVEL_2_MAC_DHCP_DNS_OUI = "L2_mac_dhcp_dns_oui"
    LEVEL_3_OPERATOR_CONFIRMED = "L3_operator_confirmed"


class ReadinessStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class StructuralTransitionGroundTruthV1(ContractModel):
    """Structural ground truth (NOT an attack label unless an experiment produced one)."""

    schema_version: str = GROUND_TRUTH_SCHEMA
    ground_truth_id: str
    scenario_id: str

    start_time: datetime
    end_time: datetime

    transition_type: TransitionType
    expectedness: Expectedness = Expectedness.UNKNOWN

    source_asset_ids: list[str] = Field(default_factory=list)
    destination_asset_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)

    zone_before: str | None = None
    zone_after: str | None = None
    role_context: dict = Field(default_factory=dict)

    scenario_origin: ScenarioOrigin
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    notes: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    # Independent provenance (amendment 2): ground truth must not be derived from the
    # anomaly outputs / scores / telemetry patterns under evaluation.
    ground_truth_source: GroundTruthSource | None = None
    ground_truth_recorded_at: datetime | None = None
    orchestrator_run_id: str | None = None
    operator_action_id: str | None = None

    attack_related: str = "unknown"   # true | false | unknown (NO attack stage here)

    @field_validator("start_time", "end_time", "ground_truth_recorded_at")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)


class DatasetIdentity(ContractModel):
    """Immutable identity of a capture package (amendment 3)."""

    schema_version: str = READINESS_SCHEMA
    dataset_id: str
    dataset_version: str
    capture_id: str | None = None
    lab_run_id: str | None = None
    schema_versions: dict = Field(default_factory=dict)
    generated_at: datetime | None = None
    source_manifests: list[str] = Field(default_factory=list)
    checksums: dict = Field(default_factory=dict)

    @field_validator("generated_at")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)


class DimensionResult(ContractModel):
    schema_version: str = READINESS_SCHEMA
    dimension: str
    status: ReadinessStatus
    critical: bool = True
    metrics: dict = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class ReadinessReportV1(ContractModel):
    schema_version: str = READINESS_SCHEMA
    dataset_id: str
    dataset_version: str | None = None
    dataset_identity: DatasetIdentity | None = None
    dimensions: list[DimensionResult] = Field(default_factory=list)
    overall_status: ReadinessStatus = ReadinessStatus.FAIL
    gnn_entry_gate_passed: bool = False
