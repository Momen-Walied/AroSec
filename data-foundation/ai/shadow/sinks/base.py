"""ShadowSink interface (edge and node records are stored separately)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ai.contracts.shadow_records import ShadowRecord


class ShadowSink(ABC):
    @abstractmethod
    def write(self, record: ShadowRecord) -> None:
        ...

    def close(self) -> None:  # pragma: no cover - default no-op
        return None
