"""Runtime configuration for the Vigilance Data Foundation.

Reads from environment / `.env`. All paths are resolved relative to the
repository root so the CLI works from any working directory.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DataMode = Literal["sample", "full"]
WindowSpec = Literal["5s", "30s", "60s"]

WINDOW_SECONDS: dict[str, int] = {"5s": 5, "30s": 30, "60s": 60}


class Settings(BaseSettings):
    """Central settings. Values come from env vars / .env (see .env.example)."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    data_mode: DataMode = "sample"

    raw_data_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    interim_dir: Path = Field(default=PROJECT_ROOT / "data" / "interim")
    processed_dir: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    reports_dir: Path = Field(default=PROJECT_ROOT / "reports")
    samples_dir: Path = Field(default=PROJECT_ROOT / "samples")
    configs_dir: Path = Field(default=PROJECT_ROOT / "configs")

    default_window: WindowSpec = "30s"
    enabled_windows: list[WindowSpec] = Field(default_factory=lambda: ["5s", "30s", "60s"])

    sample_max_flow_rows: int = 200_000
    sample_max_pcap_packets: int = 50_000
    sample_max_provenance_rows: int = 500_000

    http_timeout_seconds: int = 60
    allow_registration_gated: bool = False

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    @field_validator("enabled_windows", mode="before")
    @classmethod
    def _split_windows(cls, value: object) -> object:
        if isinstance(value, str):
            return [w.strip() for w in value.split(",") if w.strip()]
        return value

    @field_validator("raw_data_dir", "interim_dir", "processed_dir", "reports_dir",
                     "samples_dir", "configs_dir", mode="after")
    @classmethod
    def _absolutize(cls, value: Path) -> Path:
        if not value.is_absolute():
            return (PROJECT_ROOT / value).resolve()
        return value

    # ---- convenience accessors -------------------------------------------------
    @property
    def window_seconds(self) -> int:
        return WINDOW_SECONDS[self.default_window]

    def dataset_raw_dir(self, dataset_id: str) -> Path:
        return self.raw_data_dir / dataset_id

    def dataset_interim_dir(self, dataset_id: str) -> Path:
        return self.interim_dir / dataset_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
