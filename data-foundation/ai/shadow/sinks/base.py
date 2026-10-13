"""ShadowSink interface (edge and node records are stored separately)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ai.contracts.shadow_records import EpisodeShadowRecordV1, ShadowRecord


class ShadowSink(ABC):
    @abstractmethod
    def write(self, record: ShadowRecord) -> None:
        ...

    def write_episode(self, record: EpisodeShadowRecordV1) -> None:
        return None

    def close(self) -> None:  # pragma: no cover - default no-op
        return None
