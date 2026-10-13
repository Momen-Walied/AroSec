"""In-memory shadow sink (evaluation; avoids large files)."""
from __future__ import annotations

from ai.contracts.shadow_records import ShadowInferenceRecordV1
from ai.shadow.sinks.base import ShadowSink


class InMemoryShadowSink(ShadowSink):
    def __init__(self) -> None:
        self.records: list[ShadowInferenceRecordV1] = []

    def write(self, record: ShadowInferenceRecordV1) -> None:
        self.records.append(record)
