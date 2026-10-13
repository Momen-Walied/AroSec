"""In-memory state store (tests / development)."""
from __future__ import annotations

import copy

from ai.shadow.state.base import StateStore


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._state: dict | None = None

    def save(self, state: dict) -> None:
        self._state = copy.deepcopy(state)

    def load(self) -> dict | None:
        return copy.deepcopy(self._state) if self._state is not None else None
