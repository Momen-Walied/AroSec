"""JSONL / local-stream observation source (development)."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ai.shadow.sources.base import ObservationSource
from src.schemas.v2 import CommunicationObservation


class JsonlObservationSource(ObservationSource):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __iter__(self) -> Iterator[CommunicationObservation]:
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if text:
                    yield CommunicationObservation.model_validate_json(text)
