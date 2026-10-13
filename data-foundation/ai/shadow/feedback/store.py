"""Local analyst feedback storage (append-only JSONL). No retraining is triggered."""
from __future__ import annotations

from pathlib import Path

from ai.shadow.feedback.schema import AnalystFeedbackV1


class FeedbackStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, feedback: AnalystFeedbackV1) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(feedback.canonical_json() + "\n")

    def read(self) -> list[AnalystFeedbackV1]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [AnalystFeedbackV1.model_validate_json(line)
                    for line in fh if line.strip()]
