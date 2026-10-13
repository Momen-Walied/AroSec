"""StateStore interface (transport/backend agnostic)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class StateStore(ABC):
    @abstractmethod
    def save(self, state: dict) -> None:
        ...

    @abstractmethod
    def load(self) -> dict | None:
        ...

    def close(self) -> None:  # pragma: no cover - default no-op
        return None
