"""Shadow runtime configuration. Shadow-only: no remediation paths exist."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.config import PROJECT_ROOT

SHADOW_CONFIG_DIR = Path(__file__).resolve().parent / "configs"


@dataclass
class ShadowConfig:
    mode: str = "shadow"  # the ONLY supported mode
    dataset_id: str = "unsw_iotraffic"
    window_label: str = "30s"
    window_seconds: int = 30
    # CommunicationObservation is pre-windowed, so lateness tolerance is quantized to
    # whole windows. 30s tolerates a record arriving up to one window late; finer values
    # have no effect. Documented in docs/AI_SHADOW_INTEGRATION_V1.md.
    allowed_lateness_seconds: int = 30
    dedupe_capacity: int = 500_000

    # provisional operational threshold (NOT a final production threshold)
    shadow_threshold: float = 0.315

    model_bundle: Path = field(default_factory=lambda: SHADOW_CONFIG_DIR / "fusion_bundle.json")

    state_backend: str = "memory"       # memory | sqlite
    state_path: Path = field(default_factory=lambda: PROJECT_ROOT / "ai" / "shadow" / "runtime_state.sqlite")

    sink_backend: str = "jsonl"         # jsonl | sqlite
    sink_path: Path = field(default_factory=lambda: PROJECT_ROOT / "reports" / "ai" / "shadow_v1" / "shadow_output.jsonl")

    feedback_path: Path = field(default_factory=lambda: PROJECT_ROOT / "ai" / "shadow" / "feedback.jsonl")

    def __post_init__(self) -> None:
        if self.mode != "shadow":
            raise ValueError(f"only mode='shadow' is supported; got {self.mode!r}")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.allowed_lateness_seconds < 0:
            raise ValueError("allowed_lateness_seconds must be >= 0")
