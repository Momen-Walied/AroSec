"""Lightweight local experiment registry (JSON). No heavy infrastructure."""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

REGISTRY_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = REGISTRY_DIR / "registry.json"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REGISTRY_DIR,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def record_experiment(record: dict, path: Path | None = None) -> dict:
    path = path or REGISTRY_PATH
    data = {"experiments": []}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    entry = dict(record)
    entry.setdefault("git_commit", git_commit())
    entry.setdefault("recorded_at", datetime.now(UTC).isoformat())
    data.setdefault("experiments", []).append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return entry


def load_experiments(path: Path | None = None) -> list[dict]:
    path = path or REGISTRY_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("experiments", [])
