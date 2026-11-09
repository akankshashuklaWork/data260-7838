"""Reusable lessons stored in lessons.json (lesson_id, failure_pattern, correction, created_at, use_count)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

LESSONS_FILE = Path(__file__).with_name("lessons.json")


class LessonStore:
    def __init__(
        self, path: Path | None = None, lessons: list[dict[str, Any]] | None = None
    ) -> None:
        self.path = path
        self.lessons: list[dict[str, Any]] = lessons if lessons is not None else self._load()

    def _load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text()) if self.path and self.path.exists() else []

    def save(self) -> None:
        if self.path:
            self.path.write_text(json.dumps(self.lessons, indent=2) + "\n")

    def add(self, failure_pattern: str, correction: str) -> dict[str, Any]:
        lesson = {
            "lesson_id": f"lesson_{len(self.lessons) + 1:03d}",
            "failure_pattern": failure_pattern,
            "correction": correction,
            "created_at": date.today().isoformat(),
            "use_count": 0,
        }
        self.lessons.append(lesson)
        return lesson

    def relevant(self, info: dict[str, Any]) -> list[dict[str, Any]]:
        """Lessons whose failure pattern matches the kind of question: a listed property or unrelated."""
        scope = "listed property facts" if info["record"] else "unrelated topics"
        return [lesson for lesson in self.lessons if f"about {scope}" in lesson["failure_pattern"]]

    def copy_with(self, extra: list[dict[str, Any]]) -> "LessonStore":
        return LessonStore(None, [dict(item) for item in self.lessons + extra])
