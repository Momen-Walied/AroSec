"""SQLite durable state store (edge-gateway friendly).

Chosen because it is: single-file, zero-server, crash-safe (WAL + atomic commits),
CPU-friendly, trivially inspectable/backup-able, and already a Python stdlib module.
No Redis/Kafka/distributed state is required for shadow operation.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai.shadow.state.base import StateStore


class SqliteStateStore(StateStore):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("CREATE TABLE IF NOT EXISTS runtime_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._conn.commit()

    def save(self, state: dict) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO runtime_state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("builder", json.dumps(state)),
            )

    def load(self) -> dict | None:
        row = self._conn.execute("SELECT value FROM runtime_state WHERE key='builder'").fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        self._conn.close()
