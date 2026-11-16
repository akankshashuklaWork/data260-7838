"""Local LLM-as-judge built on DeepEval GEval (Part 2).

DeepEval's GEval turns a written rubric into a score by asking a judge model to follow explicit
evaluation steps. Here the judge model is a *local* Ollama model (never a hosted API): it is a
different model from the generator, runs at temperature 0 with the homework seed, and is called
with a hard timeout. Every score uses one 1-5 scale (1 = very poor, 5 = excellent), the same
scale the human labels use.

How the 1-5 scale is obtained: each criterion has a five-band rubric whose bands are the integers
1 to 5. DeepEval derives its score range from the rubric, so the judge answers with an integer in
[1, 5] and DeepEval stores (score - 1) / 4 in ``metric.score``; ``to_scale`` undoes that mapping.
"""

from __future__ import annotations

import os

# Telemetry stays off: nothing about this project is sent to any outside service.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_GRPC_LOGGING", "0")

import hashlib  # noqa: E402
import importlib.metadata  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from dataclasses import asdict, dataclass  # noqa: E402
from typing import Any  # noqa: E402

import ollama  # noqa: E402
from deepeval.metrics import GEval  # noqa: E402
from deepeval.metrics.g_eval import Rubric  # noqa: E402
from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase, LLMTestCaseParams  # noqa: E402

from .config import (  # noqa: E402
    JUDGE_CALL_TIMEOUT_S,
    JUDGE_HOST,
    JUDGE_MODEL,
    JUDGE_NUM_CTX,
    JUDGE_SEED,
    JUDGE_TEMPERATURE,
)

RUBRIC_VERSION = "hw10-v1"


class OllamaJudge(DeepEvalBaseLLM):
    """DeepEval model wrapper that sends every judge prompt to a local Ollama model."""

    def __init__(
        self,
        model: str = JUDGE_MODEL,
        temperature: float = JUDGE_TEMPERATURE,
        seed: int = JUDGE_SEED,
        timeout: float = JUDGE_CALL_TIMEOUT_S,
    ) -> None:
        self.model_name = model
        self.temperature = temperature
        self.seed = seed
        self.client = ollama.Client(host=JUDGE_HOST, timeout=timeout)  # the call cannot hang
        super().__init__(model)

    def load_model(self) -> OllamaJudge:
        return self

    def generate(self, prompt: str, schema: Any = None) -> Any:
        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": JUDGE_NUM_CTX,
            },
            "think": False,  # no hidden reasoning pass: shorter, more repeatable answers
        }
        if schema is not None:  # structured output: the reply must match DeepEval's JSON schema
            request["format"] = schema.model_json_schema()
        text = self.client.chat(**request)["message"]["content"]
        return schema.model_validate_json(text) if schema is not None else text

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        import asyncio

        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return f"ollama/{self.model_name}"


# --- Rubrics: five bands, the integers 1..5 ---------------------------------------------------
def _rubric(bands: list[str]) -> list[Rubric]:
    return [Rubric(score_range=(i, i), expected_outcome=text) for i, text in enumerate(bands, 1)]


PLAN_RUBRIC = _rubric(
    [
        "Plan is missing, unrelated to the question, or unusable.",
        "Mostly generic or partly off-topic; major needs of the question are not covered.",
        "Somewhat useful but vague or incomplete; a writer would have to guess several parts.",
        "Useful, relevant and ordered; only minor gaps or generic wording.",
        "Clear, specific, well ordered, and covers everything the question needs.",
    ]
)
HELPFULNESS_RUBRIC = _rubric(
    [
        "Not helpful: does not answer the question, is wrong, or contradicts the given facts.",
        "Weak: touches the topic but mostly vague, partly wrong, or invents specifics.",
        "Fair: answers part of the question; some generic filler or minor inaccuracy.",
        "Good: answers the question accurately and relevantly with small gaps.",
        "Excellent: accurate, relevant, concrete and clear; a renter could act on it directly.",
    ]
)

PLAN_STEPS = [
    "Read the renter's question in INPUT and decide what a good answer to it must cover.",
    "Read the numbered plan in ACTUAL_OUTPUT.",
    "Check that each step is relevant to the question, specific rather than generic filler, "
    "and ordered so that a writer could follow it.",
    "Check that the steps together cover the main needs of the question with nothing important "
    "missing.",
]


def _helpfulness_steps(subject: str, with_context: bool) -> list[str]:
    steps = [
        "Read the renter's question in INPUT.",
        f"Check that the {subject} in ACTUAL_OUTPUT answers that question directly and stays "
        "on topic.",
    ]
    if with_context:
        steps.append(
            "Compare every specific number or term in ACTUAL_OUTPUT with the facts in CONTEXT; "
            "a value that contradicts or is missing from CONTEXT counts as inaccurate."
        )
    else:
        steps.append(
            f"Check that the {subject} is accurate and sensible and does not invent precise "
            "figures or facts that the question gave no basis for."
        )
    steps.append(
        f"Decide whether a renter could act on the {subject}: is it concrete, useful and clear?"
    )
    return steps


@dataclass
class Score:
    """One judged criterion."""

    criterion: str
    score: int  # 1-5
    reason: str
    judge_ms: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_scale(deepeval_score: float) -> int:
    """DeepEval stores (raw - 1) / 4 for a 1..5 rubric; return the integer the judge gave."""
    return max(1, min(5, round(1 + 4 * float(deepeval_score))))


class LocalJudge:
    """Scores Plan Quality, Writer Helpfulness and Final Answer Helpfulness with GEval."""

    def __init__(self, model: OllamaJudge | None = None) -> None:
        self.llm = model or OllamaJudge()

    def settings(self) -> dict[str, Any]:
        """Everything needed to repeat a judge run (documented in the report)."""
        prompts = json.dumps(
            [PLAN_STEPS, _helpfulness_steps("answer", False), _helpfulness_steps("answer", True)]
        )
        return {
            "judge_model": self.llm.model_name,
            "runtime": "Ollama (local)",
            "temperature": self.llm.temperature,
            "seed": self.llm.seed,
            "num_ctx": JUDGE_NUM_CTX,
            "thinking": False,
            "scale": "1-5 integer (1 very poor, 5 excellent)",
            "framework": f"deepeval {importlib.metadata.version('deepeval')} GEval",
            "rubric_version": RUBRIC_VERSION,
            "rubric_hash": hashlib.sha256(prompts.encode()).hexdigest()[:12],
            "call_timeout_s": JUDGE_CALL_TIMEOUT_S,
        }

    def _measure(
        self, name: str, steps: list[str], rubric: list[Rubric], params: list, case: LLMTestCase
    ) -> Score:
        metric = GEval(
            name=name,
            evaluation_steps=steps,
            rubric=rubric,
            evaluation_params=params,
            model=self.llm,
            async_mode=False,  # one call at a time: simple and repeatable
            verbose_mode=False,
        )
        started = time.perf_counter()
        metric.measure(case, _show_indicator=False)
        return Score(
            name,
            to_scale(metric.score),
            (metric.reason or "").strip(),
            (time.perf_counter() - started) * 1000,
        )

    def plan_quality(self, question: str, plan: list[str]) -> Score:
        numbered = "\n".join(f"{i}. {step}" for i, step in enumerate(plan, 1))
        case = LLMTestCase(input=question, actual_output=numbered)
        params = [LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]
        return self._measure("Plan Quality", PLAN_STEPS, PLAN_RUBRIC, params, case)

    def helpfulness(self, which: str, question: str, answer: str, context: str = "") -> Score:
        """which = "writer" (judges the draft) or "final" (judges the final answer).

        Both use the same rubric and the same step wording on purpose: when the Reviewer passes the
        draft through unchanged, the two prompts are identical, so the Final-vs-Draft difference
        measures the change in the text and not a change in how the judge was asked.
        """
        name = "Writer Helpfulness" if which == "writer" else "Final Answer Helpfulness"
        params = [LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]
        case_args: dict[str, Any] = {"input": question, "actual_output": answer}
        if context:
            params.append(LLMTestCaseParams.CONTEXT)
            case_args["context"] = [context]
        steps = _helpfulness_steps("answer", bool(context))
        return self._measure(name, steps, HELPFULNESS_RUBRIC, params, LLMTestCase(**case_args))


def warm_up(judge: LocalJudge) -> float:
    """Load the model into memory once so the first real score is not slowed by a cold start."""
    started = time.perf_counter()
    judge.llm.generate("Reply with the single word: ready")
    return (time.perf_counter() - started) * 1000
