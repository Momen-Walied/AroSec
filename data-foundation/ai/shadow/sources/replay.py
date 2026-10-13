"""Replay source over existing local v0.2 CommunicationObservation data (no downloads)."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ai.shadow.sources.base import ObservationSource
from src.config import get_settings
from src.normalization import io
from src.schemas.v2 import CommunicationObservation


class ReplayObservationSource(ObservationSource):
    def __init__(self, dataset_id: str = "unsw_iotraffic", window: str = "30s",
                 processed_dir: Path | None = None, limit: int | None = None) -> None:
        settings = get_settings()
        base = processed_dir or (settings.processed_dir / "v2" / "communication_observations")
        path = base / f"{dataset_id}_obs_{window}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"v0.2 observations not found: {path}. Run `build-v2` first.")
        df = io.read_parquet(path)
        records = io.frame_to_models(df, CommunicationObservation)
        records.sort(key=lambda o: (o.window_start, o.observation_id))
        self._records = records[:limit] if limit else records

    def __iter__(self) -> Iterator[CommunicationObservation]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)
