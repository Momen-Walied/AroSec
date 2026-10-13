"""ShadowSink interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ai.contracts.shadow_records import ShadowInferenceRecordV1


class ShadowSink(ABC):
    @abstractmethod
    def write(self, record: ShadowInferenceRecordV1) -> None:
        ...

    def close(self) -> None:  # pragma: no cover - default no-op
        return None
