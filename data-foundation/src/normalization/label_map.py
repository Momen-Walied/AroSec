"""External-label -> unified taxonomy mapping.

Uncertain labels are mapped to ``unknown`` and their ``original_label`` is always
preserved by the caller. Confidence < 1.0 signals an uncertain mapping.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.schemas.base import AttackCategory, AttackStage

_UNKNOWN = (AttackCategory.UNKNOWN, AttackStage.UNKNOWN, 0.0)

MITRE_TECHNIQUE: dict[str, tuple[AttackCategory, AttackStage, str]] = {
    "T1021": (AttackCategory.LATERAL_MOVEMENT, AttackStage.LATERAL_MOVEMENT, "Remote Services"),
    "T1087": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "Account Discovery"),
    "T1016": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "System Network Configuration Discovery"),
    "T1033": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "System Owner/User Discovery"),
    "T1518": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "Software Discovery"),
    "T1069": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "Permission Groups Discovery"),
    "T1082": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "System Information Discovery"),
    "T1083": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "File and Directory Discovery"),
    "T1018": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "Remote System Discovery"),
    "T1552": (AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS, "Unsecured Credentials"),
    "T1555": (AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS, "Credentials from Password Stores"),
    "T1074": (AttackCategory.COLLECTION, AttackStage.COLLECTION, "Data Staged"),
    "T1005": (AttackCategory.COLLECTION, AttackStage.COLLECTION, "Data from Local System"),
    "T1119": (AttackCategory.COLLECTION, AttackStage.COLLECTION, "Automated Collection"),
    "T1113": (AttackCategory.COLLECTION, AttackStage.COLLECTION, "Screen Capture"),
    "T1115": (AttackCategory.COLLECTION, AttackStage.COLLECTION, "Clipboard Data"),
    "T1560": (AttackCategory.EXFILTRATION, AttackStage.EXFILTRATION, "Archive Collected Data"),
    "T1041": (AttackCategory.EXFILTRATION, AttackStage.EXFILTRATION, "Exfiltration Over C2 Channel"),
    "T1105": (AttackCategory.COMMAND_AND_CONTROL, AttackStage.COMMAND_AND_CONTROL, "Ingress Tool Transfer"),
    "T1546": (AttackCategory.PERSISTENCE, AttackStage.PERSISTENCE, "Event Triggered Execution"),
    "T1136": (AttackCategory.PERSISTENCE, AttackStage.PERSISTENCE, "Create Account"),
    "T1036": (AttackCategory.DEFENSE_EVASION, AttackStage.DEFENSE_EVASION, "Masquerading"),
    "T1485": (AttackCategory.DEFENSE_EVASION, AttackStage.IMPACT, "Data Destruction"),
    "T1071": (AttackCategory.COMMAND_AND_CONTROL, AttackStage.COMMAND_AND_CONTROL, "Application Layer Protocol"),
    "T1046": (AttackCategory.DISCOVERY, AttackStage.DISCOVERY, "Network Service Discovery"),
    "T1110": (AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS, "Brute Force"),
    "T1190": (AttackCategory.INITIAL_ACCESS, AttackStage.INITIAL_ACCESS, "Exploit Public-Facing Application"),
    "T1059": (AttackCategory.INITIAL_ACCESS, AttackStage.EXECUTION, "Command and Scripting Interpreter"),
}

_KEYWORD_RULES: list[tuple[str, AttackCategory, AttackStage]] = [
    ("lateral", AttackCategory.LATERAL_MOVEMENT, AttackStage.LATERAL_MOVEMENT),
    ("ddos", AttackCategory.DDOS, AttackStage.IMPACT),
    ("denial-of-service", AttackCategory.DOS, AttackStage.IMPACT),
    ("denial of service", AttackCategory.DOS, AttackStage.IMPACT),
    ("dos", AttackCategory.DOS, AttackStage.IMPACT),
    ("exfiltrat", AttackCategory.EXFILTRATION, AttackStage.EXFILTRATION),
    ("command-and-control", AttackCategory.COMMAND_AND_CONTROL, AttackStage.COMMAND_AND_CONTROL),
    ("command and control", AttackCategory.COMMAND_AND_CONTROL, AttackStage.COMMAND_AND_CONTROL),
    ("c2", AttackCategory.COMMAND_AND_CONTROL, AttackStage.COMMAND_AND_CONTROL),
    ("collection", AttackCategory.COLLECTION, AttackStage.COLLECTION),
    ("discovery", AttackCategory.DISCOVERY, AttackStage.DISCOVERY),
    ("scan", AttackCategory.DISCOVERY, AttackStage.DISCOVERY),
    ("recon", AttackCategory.DISCOVERY, AttackStage.DISCOVERY),
    ("brute", AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS),
    ("credential", AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS),
    ("password", AttackCategory.CREDENTIAL_ACCESS, AttackStage.CREDENTIAL_ACCESS),
    ("persistence", AttackCategory.PERSISTENCE, AttackStage.PERSISTENCE),
    ("backdoor", AttackCategory.PERSISTENCE, AttackStage.PERSISTENCE),
    ("defense-evasion", AttackCategory.DEFENSE_EVASION, AttackStage.DEFENSE_EVASION),
    ("defence-evasion", AttackCategory.DEFENSE_EVASION, AttackStage.DEFENSE_EVASION),
    ("evasion", AttackCategory.DEFENSE_EVASION, AttackStage.DEFENSE_EVASION),
    ("mitm", AttackCategory.MITM, AttackStage.COLLECTION),
    ("man-in-the-middle", AttackCategory.MITM, AttackStage.COLLECTION),
    ("spoof", AttackCategory.SPOOFING, AttackStage.IMPACT),
    ("injection", AttackCategory.INJECTION, AttackStage.EXECUTION),
    ("sql", AttackCategory.INJECTION, AttackStage.EXECUTION),
    ("xss", AttackCategory.INJECTION, AttackStage.EXECUTION),
    ("ransom", AttackCategory.MALWARE, AttackStage.IMPACT),
    ("malware", AttackCategory.MALWARE, AttackStage.EXECUTION),
    ("trojan", AttackCategory.MALWARE, AttackStage.EXECUTION),
    ("worm", AttackCategory.MALWARE, AttackStage.EXECUTION),
    ("botnet", AttackCategory.MALWARE, AttackStage.COMMAND_AND_CONTROL),
    ("upload", AttackCategory.COLLECTION, AttackStage.COLLECTION),
    ("fingerprint", AttackCategory.DISCOVERY, AttackStage.DISCOVERY),
]

_BENIGN = {"benign", "normal", "0", "false", "no", "-", "none"}


@dataclass(frozen=True)
class LabelMapping:
    category: AttackCategory
    stage: AttackStage
    technique: str | None
    is_lateral_movement: bool
    confidence: float


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_benign_label(original_label: str | None) -> bool:
    return _norm(original_label) in _BENIGN


def map_label(original_label: str | None, original_sub_label: str | None = None) -> LabelMapping:
    raw = _norm(original_label)
    sub = _norm(original_sub_label)
    combined = f"{raw} {sub}".strip()

    if not combined or is_benign_label(original_label):
        return LabelMapping(AttackCategory.BENIGN, AttackStage.UNKNOWN, None, False, 1.0)

    for token in re.findall(r"T\d{4}(?:\.\d{3})?", combined.upper()):
        base = token.split(".")[0]
        if base in MITRE_TECHNIQUE:
            cat, stage, name = MITRE_TECHNIQUE[base]
            return LabelMapping(cat, stage, token, cat == AttackCategory.LATERAL_MOVEMENT, 0.95)

    for needle, cat, stage in _KEYWORD_RULES:
        if needle in combined:
            exact = raw == needle or sub == needle or needle in {raw, sub}
            return LabelMapping(
                cat, stage, None, cat == AttackCategory.LATERAL_MOVEMENT, 0.85 if exact else 0.65
            )

    return LabelMapping(*_UNKNOWN, False, 0.0)  # type: ignore[arg-type]
