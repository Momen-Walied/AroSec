"""Shared schema primitives: enums, base model, canonical validators.

Every v0.1 contract inherits :class:`ContractModel`. Contracts are STRICT:
`extra="forbid"` means unknown fields are rejected — this is what keeps the
Network Team, AI Team, and Graph Intelligence on one stable interface.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

SCHEMA_VERSION = "0.1.0"

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


class ContractModel(BaseModel):
    """Base for all v0.1 contracts. Strict by design."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    def to_canonical_dict(self) -> dict[str, Any]:
        """JSON-serializable dict with datetimes normalized to UTC ISO-8601."""
        data = self.model_dump(mode="json")
        return _canonicalize(data)

    def canonical_json(self) -> str:
        return json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self, *fields: str) -> str:
        """Deterministic short hash over selected fields (or all if none given)."""
        data = self.to_canonical_dict()
        if fields:
            data = {k: data.get(k) for k in fields}
        return hashlib.sha1(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _canonicalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return to_utc_iso(value)
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    return value


# --------------------------------------------------------------------------- #
# Enums                                                                       #
# --------------------------------------------------------------------------- #
class SourceDataset(StrEnum):
    CICAPT_IIOT = "cicapt_iiot"
    X_IIOTID = "x_iiotid"
    UNSW_IOTRAFFIC = "unsw_iotraffic"
    EDGE_IIOTSET = "edge_iiotset"
    CICIOT2023 = "ciciot2023"
    SYNTHETIC = "synthetic"


class DatasetStatus(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    AVAILABLE = "AVAILABLE"
    DOWNLOADED = "DOWNLOADED"
    MANUAL_DOWNLOAD_REQUIRED = "MANUAL_DOWNLOAD_REQUIRED"
    FAILED = "FAILED"
    NORMALIZED = "NORMALIZED"


class AssetType(StrEnum):
    DEVICE = "device"
    INTERFACE = "interface"
    SERVICE = "service"
    SUBNET = "subnet"
    VLAN = "vlan"
    GATEWAY = "gateway"
    HOST = "host"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    PLC = "plc"
    HMI = "hmi"
    CAMERA = "camera"
    NVR = "nvr"
    ROUTER = "router"
    SWITCH = "switch"
    SERVER = "server"
    USER = "user"
    PROCESS = "process"
    UNKNOWN = "unknown"


class IdentityMethod(StrEnum):
    """v0.2 identity vocabulary (legacy v0.1 members retained for parsing)."""
    MANUAL_AUTHORITATIVE = "manual_authoritative"
    DATASET_DEVICE_ID = "dataset_device_id"
    MULTI_SIGNAL = "multi_signal"
    DHCP_MAC_CORRELATED = "dhcp_mac_correlated"
    MAC_BASED = "mac_based"
    DATASET_IP_FALLBACK = "dataset_ip_fallback"
    IP_ONLY_OBSERVATION = "ip_only_observation"
    DATASET_DERIVED = "dataset_derived"
    MAC_PINNED = "mac_pinned"
    HOSTNAME = "hostname"
    MANUAL = "manual"
    IP_ONLY = "ip_only"
    UNKNOWN = "unknown"


class IdentifierType(StrEnum):
    MAC = "mac"
    IP = "ip"
    HOSTNAME = "hostname"
    DEVICE_ID = "device_id"
    SERIAL = "serial"
    OTHER = "other"


class RelationshipType(StrEnum):
    COMMUNICATES_WITH = "COMMUNICATES_WITH"
    CONNECTED_TO = "CONNECTED_TO"
    MEMBER_OF = "MEMBER_OF"
    USES_PROTOCOL = "USES_PROTOCOL"
    AUTHENTICATES_TO = "AUTHENTICATES_TO"
    CONTROLS = "CONTROLS"
    DEPENDS_ON = "DEPENDS_ON"
    CAN_REACH = "CAN_REACH"


class Direction(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"
    UNKNOWN = "unknown"


class GraphEventType(StrEnum):
    ASSET_ADDED = "ASSET_ADDED"
    ASSET_UPDATED = "ASSET_UPDATED"
    EDGE_ADDED = "EDGE_ADDED"
    EDGE_UPDATED = "EDGE_UPDATED"
    EDGE_REMOVED = "EDGE_REMOVED"
    IDENTITY_UPDATED = "IDENTITY_UPDATED"
    IDENTITY_BINDING_ADDED = "IDENTITY_BINDING_ADDED"
    IDENTITY_BINDING_EXPIRED = "IDENTITY_BINDING_EXPIRED"
    RELATIONSHIP_ADDED = "RELATIONSHIP_ADDED"
    RELATIONSHIP_UPDATED = "RELATIONSHIP_UPDATED"
    COMMUNICATION_OBSERVED = "COMMUNICATION_OBSERVED"


class Criticality(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AttackCategory(StrEnum):
    """Unified internal attack taxonomy. Maps external labels into ONE space.

    Uncertainty is preserved as :attr:`UNKNOWN` — never silently forced.
    """
    BENIGN = "benign"
    DISCOVERY = "discovery"
    CREDENTIAL_ACCESS = "credential_access"
    INITIAL_ACCESS = "initial_access"
    LATERAL_MOVEMENT = "lateral_movement"
    COMMAND_AND_CONTROL = "command_and_control"
    COLLECTION = "collection"
    EXFILTRATION = "exfiltration"
    PERSISTENCE = "persistence"
    DEFENSE_EVASION = "defense_evasion"
    DOS = "dos"
    DDOS = "ddos"
    MALWARE = "malware"
    SPOOFING = "spoofing"
    INJECTION = "injection"
    MITM = "mitm"
    OTHER = "other"
    UNKNOWN = "unknown"


class AttackStage(StrEnum):
    """MITRE ATT&CK-style tactic stages for campaign reconstruction."""
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource_development"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"
    UNKNOWN = "unknown"


class TimeQuality(StrEnum):
    EXACT = "exact"
    COARSE = "coarse"
    RELATIVE = "relative"
    NONE = "none"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Shared validators                                                           #
# --------------------------------------------------------------------------- #
def normalize_ip(value: str) -> str:
    """Validate and canonicalize an IPv4/IPv6 address string."""
    if value is None:
        raise ValueError("ip address must not be null")
    text = str(value).strip()
    if text == "" or text in {"*", "null", "nan", "NaN"}:
        raise ValueError(f"empty/na sentinel not a valid ip: {value!r}")
    return str(ipaddress.ip_address(text))


def maybe_normalize_ip(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"*", "null", "nan", "none"}:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def normalize_mac(value: str) -> str:
    """Canonicalize a MAC to lowercase colon-separated (``aa:bb:cc:dd:ee:ff``)."""
    text = str(value).strip().lower().replace("-", ":").replace(".", "")
    if len(text) == 12 and ":" not in text:
        text = ":".join(text[i:i + 2] for i in range(0, 12, 2))
    if not _MAC_RE.match(text):
        raise ValueError(f"invalid MAC address: {value!r}")
    return text


def maybe_normalize_mac(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"*", "null", "nan", "none"}:
        return None
    try:
        return normalize_mac(text)
    except ValueError:
        return None


def ensure_utc(value: datetime | None) -> datetime | None:
    """Force tz-awareness in UTC. Naive datetimes are treated as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_utc_iso(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")  # type: ignore[union-attr]


class Ipv4OrV6Mixin(ContractModel):
    """Provides reusable field validators for network-ish contracts."""

    @field_validator("src_port", "dst_port", check_fields=False)
    @classmethod
    def _valid_port(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if not 0 <= int(v) <= 65535:
            raise ValueError(f"port out of range: {v}")
        return int(v)
