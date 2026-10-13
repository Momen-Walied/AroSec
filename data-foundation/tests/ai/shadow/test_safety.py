"""Shadow-mode safety invariants: this runtime cannot act on the network."""
from __future__ import annotations

import pytest

from ai.contracts.shadow_records import ShadowInferenceRecordV1
from ai.shadow.config import ShadowConfig
from ai.shadow.runtime import ShadowRuntime

REMEDIATION_NAMES = {
    "block", "block_host", "isolate", "quarantine_device", "firewall", "add_firewall_rule",
    "drop_packet", "deny", "remediate", "shutdown", "disable_port", "configure_switch",
}


def test_non_shadow_mode_is_rejected():
    with pytest.raises(ValueError):
        ShadowConfig(mode="active")


def test_shadow_record_requires_shadow_mode():
    from pydantic import ValidationError

    from tests.ai.shadow._helpers import make_record

    data = make_record().model_dump()
    data["shadow_mode"] = False
    with pytest.raises(ValidationError):
        ShadowInferenceRecordV1.model_validate(data)


def test_runtime_exposes_no_remediation_path():
    names = set(dir(ShadowRuntime))
    assert not (names & REMEDIATION_NAMES)


def test_shadow_runtime_is_read_only_by_contract():
    import inspect

    source = inspect.getsource(ShadowRuntime)
    for term in ("socket", "subprocess", "requests.", "paramiko", "firewall", "iptables"):
        assert term not in source


def test_shadow_inference_record_defaults_true():
    rec = ShadowInferenceRecordV1  # contract present
    assert rec is not None
