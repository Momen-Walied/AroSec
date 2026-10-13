"""Config loader for Edge Behavior v1."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "configs"


@lru_cache(maxsize=8)
def load_config(name: str = "default") -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
