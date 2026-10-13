"""In-memory shadow sink (evaluation; avoids large files). Edge/node/episodes separated."""
from __future__ import annotations

from ai.contracts.shadow_records import EpisodeShadowRecordV1, ShadowRecord
from ai.shadow.sinks.base import ShadowSink


class InMemoryShadowSink(ShadowSink):
    def __init__(self) -> None:
        self.records: list[ShadowRecord] = []
        self.episode_records: list[EpisodeShadowRecordV1] = []

    def write(self, record: ShadowRecord) -> None:
        self.records.append(record)

    def write_episode(self, record: EpisodeShadowRecordV1) -> None:
        self.episode_records.append(record)

    def edge_records(self) -> list:
        return [r for r in self.records if r.intelligence_type == "edge"]

    def node_records(self) -> list:
        return [r for r in self.records if r.intelligence_type == "node"]

    def episodes(self) -> list:
        return [r.episode for r in self.episode_records]
