"""SQLite shadow sink: stores edge and node records WITHOUT conflating them.

Idempotent per (intelligence_type, subject_id, window_start). No fused score column.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai.contracts.shadow_records import ShadowRecord
from ai.shadow.sinks.base import ShadowSink


class SqliteShadowSink(ShadowSink):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS shadow_records ("
            "intelligence_type TEXT NOT NULL, subject_id TEXT NOT NULL, window_start TEXT NOT NULL, "
            "anomaly_score REAL, severity TEXT, identity_method TEXT, "
            "reasons_json TEXT, record_json TEXT NOT NULL, "
            "PRIMARY KEY (intelligence_type, subject_id, window_start))"
        )
        self._conn.commit()

    def write(self, record: ShadowRecord) -> None:
        fw = record.feature_window
        ar = record.anomaly_result
        subject = getattr(fw, "relationship_id", None) or fw.asset_id
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO shadow_records VALUES (?,?,?,?,?,?,?,?)",
                (record.intelligence_type, subject, fw.window_start.isoformat(), ar.anomaly_score,
                 str(ar.severity), record.identity_method,
                 json.dumps([r.model_dump() for r in ar.reasons]), record.canonical_json()),
            )

    def close(self) -> None:
        self._conn.close()
