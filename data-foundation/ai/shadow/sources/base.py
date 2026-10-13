"""ObservationSource interface (transport-agnostic)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from src.schemas.v2 import CommunicationObservation


class ObservationSource(ABC):
    @abstractmethod
    def __iter__(self) -> Iterator[CommunicationObservation]:
        ...

    def close(self) -> None:  # pragma: no cover - default no-op
        return None
