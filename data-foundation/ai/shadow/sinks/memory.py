"""In-memory shadow sink (evaluation; avoids large files). Stores edge and node records."""
from __future__ import annotations

from ai.contracts.shadow_records import ShadowRecord
from ai.shadow.sinks.base import ShadowSink


class InMemoryShadowSink(ShadowSink):
    def __init__(self) -> None:
        self.records: list[ShadowRecord] = []

    def write(self, record: ShadowRecord) -> None:
        self.records.append(record)

    def edge_records(self) -> list:
        return [r for r in self.records if r.intelligence_type == "edge"]

    def node_records(self) -> list:
        return [r for r in self.records if r.intelligence_type == "node"]
