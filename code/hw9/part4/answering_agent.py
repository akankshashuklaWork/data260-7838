"""Answering Agent: answers rental questions with the local qwen2:7b model (temperature 0, seed 7838)."""

from __future__ import annotations

import time
from typing import Any

import ollama
from hw8.config import CONFIG

from . import reference
from .lessons import LessonStore

SYSTEM = (
    "You are a rental housing assistant. Answer in one or two short sentences. "
    "If you do not have reliable information, say: I don't have that information."
)


class AnsweringAgent:
    def __init__(self, lessons: LessonStore | None = None, track_usage: bool = False) -> None:
        self.lessons = lessons
        self.track_usage = (
            track_usage  # True only in demos; final test runs never modify lessons.json
        )
        self.client = ollama.Client(host="http://localhost:11434")

    def _chat(self, system: str, prompt: str) -> str:
        reply = self.client.chat(
            model=CONFIG.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            options={"temperature": 0, "seed": CONFIG.seed, "num_predict": 120},
        )
        return reply["message"]["content"].strip()

    def answer(
        self, question: str, feedback: str | None = None, previous: str | None = None
    ) -> dict[str, Any]:
        started = time.perf_counter()
        system, prompt = SYSTEM, question
        loaded: list[dict[str, Any]] = []
        if self.lessons:
            info = reference.classify(question)
            loaded = self.lessons.relevant(info)  # lessons are loaded BEFORE the answer is written
        if loaded:
            rules = "\n".join(f"- {lesson['correction']}" for lesson in loaded)
            system += "\nLessons from earlier mistakes:\n" + rules
            prompt += f"\nFollow these lessons:\n{rules}"
            if info["record"]:  # the lesson says to check the reference dataset first
                fact = reference.lookup(question)
                if fact:
                    prompt += f"\nReference fact: {fact}"
            if self.track_usage:
                for lesson in loaded:
                    lesson["use_count"] += 1
                self.lessons.save()
        if feedback:
            prompt += f"\nYour previous answer was: {previous}\nEvaluator feedback: {feedback}\nWrite a corrected answer."
        text = self._chat(system, prompt)
        return {
            "answer": text,
            "lessons_loaded": [lesson["lesson_id"] for lesson in loaded],
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
