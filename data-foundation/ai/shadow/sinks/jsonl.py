"""JSONL shadow sink (debugging / replay inspection)."""
from __future__ import annotations

from pathlib import Path

from ai.contracts.shadow_records import ShadowInferenceRecordV1
from ai.shadow.sinks.base import ShadowSink


class JsonlShadowSink(ShadowSink):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")

    def write(self, record: ShadowInferenceRecordV1) -> None:
        self._fh.write(record.canonical_json() + "\n")

    def close(self) -> None:
        self._fh.close()
