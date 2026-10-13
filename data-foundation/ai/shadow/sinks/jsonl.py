"""JSONL shadow sink (debugging / replay inspection). Edge/node and episodes separated."""
from __future__ import annotations

from pathlib import Path

from ai.contracts.shadow_records import EpisodeShadowRecordV1, ShadowRecord
from ai.shadow.sinks.base import ShadowSink


class JsonlShadowSink(ShadowSink):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")
        self._episodes_path = self.path.with_suffix(self.path.suffix + ".episodes.jsonl")
        self._eph = open(self._episodes_path, "w", encoding="utf-8")

    def write(self, record: ShadowRecord) -> None:
        self._fh.write(record.canonical_json() + "\n")

    def write_episode(self, record: EpisodeShadowRecordV1) -> None:
        self._eph.write(record.canonical_json() + "\n")

    def close(self) -> None:
        self._fh.close()
        self._eph.close()
