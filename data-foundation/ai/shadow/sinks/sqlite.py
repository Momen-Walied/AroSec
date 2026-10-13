"""SQLite shadow sink (local evaluation store). Idempotent per finalized window."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai.contracts.shadow_records import ShadowInferenceRecordV1
from ai.shadow.sinks.base import ShadowSink


class SqliteShadowSink(ShadowSink):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS shadow_records ("
            "relationship_id TEXT NOT NULL, window_start TEXT NOT NULL, "
            "anomaly_score REAL, severity TEXT, identity_method TEXT, "
            "alerts INTEGER, reasons_json TEXT, record_json TEXT NOT NULL, "
            "PRIMARY KEY (relationship_id, window_start))"
        )
        self._conn.commit()

    def write(self, record: ShadowInferenceRecordV1) -> None:
        fw = record.feature_window
        ar = record.anomaly_result
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO shadow_records VALUES (?,?,?,?,?,?,?,?)",
                (fw.relationship_id, fw.window_start.isoformat(), ar.anomaly_score,
                 str(ar.severity), record.identity_method, 0,
                 json.dumps([r.model_dump() for r in ar.reasons]),
                 record.canonical_json()),
            )

    def close(self) -> None:
        self._conn.close()
