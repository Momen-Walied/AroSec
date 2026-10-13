"""In-memory list source (demos / tests)."""
from __future__ import annotations

from collections.abc import Iterator

from ai.shadow.sources.base import ObservationSource
from src.schemas.v2 import CommunicationObservation


class ListObservationSource(ObservationSource):
    def __init__(self, observations: list[CommunicationObservation]) -> None:
        self._records = list(observations)

    def __iter__(self) -> Iterator[CommunicationObservation]:
        return iter(self._records)
