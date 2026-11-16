"""Part 2: automated evaluator for the Planner -> Writer -> Reviewer Kafka pipeline.

The evaluator is one more Kafka consumer (its own consumer group, so it never steals messages
from the agents). It listens to the three topics that carry the pipeline's work:

    <PREFIX>_tasks   - the Planner's plan       } joined by correlation_id
    <PREFIX>_drafts  - the Writer's draft       }  (which is also the trace_id)
    <PREFIX>_final   - the Reviewer's final     }

When all three messages for one correlation_id are present it asks the local judge to score
Plan Quality, Writer Helpfulness and Final Answer Helpfulness (1-5 each), computes the
Final-vs-Draft Improvement, and appends one record to ``data/hw10/eval_results.jsonl``. The
original messages are stored in the record so the evaluation can be reproduced.

Bounds (a bad message or a dead judge must never hang the run): malformed messages are logged
and skipped, the wait for a missing message is capped by JOIN_TIMEOUT_S, every judge call has a
timeout, a whole case is capped by JUDGE_CASE_TIMEOUT_S, and the join buffer has a fixed size.

    PYTHONPATH=code python -m hw10.evaluator            # run until Ctrl-C
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from aiokafka import AIOKafkaConsumer
from hw8.common import log, start_with_retry, utc_iso
from hw8.tracing import write_span

from .collector import TOPIC_ROLE, Bundle, Collector, record_event
from .config import (
    CONFIG,
    EVAL_RESULTS,
    JUDGE_CASE_TIMEOUT_S,
    KAFKA_BOOTSTRAP,
)
from .judge import LocalJudge, Score, warm_up


def _append(path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def interpret_improvement(
    draft: str, final: str, draft_score: int, final_score: int, status: str
) -> str:
    """Plain-language reading of the Final-vs-Draft result (generated from the data, not by an LLM)."""
    diff = final_score - draft_score
    if final.strip() == draft.strip():
        return (
            f"No improvement was possible: the final answer is word-for-word the draft "
            f"(Reviewer status '{status}'). The Reviewer only applies a word-count rule and never "
            f"rewrites, so both scores come from the same text and the difference is {diff:+d}."
        )
    if diff > 0:
        return f"The final answer scored {diff} point(s) higher than the draft."
    if diff < 0:
        return f"The final answer scored {-diff} point(s) lower than the draft (it got worse)."
    return "The final answer differs from the draft but earned the same score (no measurable gain)."


def evaluate_bundle(judge: LocalJudge, bundle: Bundle) -> dict[str, Any]:
    """Score one complete bundle. Synchronous and self-contained so it can be run in a thread."""
    assert bundle.plan and bundle.draft and bundle.final
    question = str(bundle.plan.get("question") or bundle.draft.get("question") or "")
    context = str(bundle.plan.get("context") or "")
    plan = [str(step) for step in bundle.plan.get("plan", [])]
    draft = str(bundle.draft.get("draft", ""))
    final_answer = str(bundle.final.get("answer", ""))
    final_status = str(bundle.final.get("status", ""))

    plan_score = judge.plan_quality(question, plan)
    writer_score = judge.helpfulness("writer", question, draft, context)
    final_score = judge.helpfulness("final", question, final_answer, context)
    return {
        "question": question,
        "context": context,
        "plan": plan,
        "draft": draft,
        "final_answer": final_answer,
        "final_status": final_status,
        "scores": {
            "plan_quality": plan_score.as_dict(),
            "writer_helpfulness": {**writer_score.as_dict(), "trace_id": bundle.trace_id},
            "final_helpfulness": {**final_score.as_dict(), "final_answer": final_answer},
        },
        "improvement": {
            "draft_score": writer_score.score,
            "final_score": final_score.score,
            "difference": final_score.score - writer_score.score,
            "text_identical": final_answer.strip() == draft.strip(),
            "interpretation": interpret_improvement(
                draft, final_answer, writer_score.score, final_score.score, final_status
            ),
        },
    }


class Evaluator:
    def __init__(self, judge: LocalJudge | None = None) -> None:
        self.judge = judge or LocalJudge()
        self.collector = Collector()
        self.tasks: set[asyncio.Task] = set()
        self.slot = asyncio.Semaphore(1)  # the local model serves one judge call at a time

    # ---- evaluation ------------------------------------------------------------------------
    async def evaluate(self, bundle: Bundle) -> None:
        trace_id = bundle.trace_id
        if not await self.collector.wait_for_all(bundle):
            missing = bundle.missing()
            record_event("incomplete_join", trace_id=trace_id, missing=missing)
            now = time.time()
            write_span(
                trace_id, "evaluation", now, now, status="error",
                error=f"missing messages: {missing}", service="evaluator",
            )  # fmt: skip
            log("EVALUATOR", f"trace_id={trace_id} incomplete, missing={missing}")
            return
        async with self.slot:
            started = time.time()
            record: dict[str, Any] = {"trace_id": trace_id, "evaluated_at": utc_iso()}
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(evaluate_bundle, self.judge, bundle),
                    timeout=JUDGE_CASE_TIMEOUT_S,
                )
                record.update(status="ok", error=None, **result)
                error = None
            except Exception as exc:  # noqa: BLE001 - any judge failure is recorded, never fatal
                error = f"{type(exc).__name__}: {exc}"[:300]
                record.update(status="error", error=error)
            ended = time.time()
        record["evaluation_ms"] = round((ended - started) * 1000, 1)
        record["messages"] = {  # original content, so the evaluation can be reproduced
            "plan": bundle.plan,
            "draft": bundle.draft,
            "final": bundle.final,
        }
        record["judge"] = self.judge.settings()
        _append(EVAL_RESULTS, record)
        write_span(
            trace_id, "evaluation", started, ended,
            status="ok" if error is None else "error", error=error, service="evaluator",
            judge_model=self.judge.llm.model_name,
        )  # fmt: skip
        self.collector.bundles.pop(trace_id, None)
        scores = record.get("scores", {})
        summary = {k: v["score"] for k, v in scores.items()} if scores else error
        log(
            "EVALUATOR",
            f"trace_id={trace_id} evaluated in {record['evaluation_ms']:.0f}ms {summary}",
        )

    # ---- Kafka loop ------------------------------------------------------------------------
    async def run(self) -> None:
        consumer = AIOKafkaConsumer(
            *TOPIC_ROLE,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=f"{CONFIG.prefix}_evaluator_{uuid.uuid4().hex[:8]}",
            auto_offset_reset="latest",  # evaluate what flows through from now on
        )
        await start_with_retry(consumer, "EVALUATOR")
        warmup_ms = await asyncio.to_thread(warm_up, self.judge)
        log("EVALUATOR", f"Consumer is ready and listening... topics={list(TOPIC_ROLE)} "
            f"judge={self.judge.llm.model_name} warm_up_ms={warmup_ms:.0f}")  # fmt: skip
        try:
            async for msg in consumer:
                bundle = self.collector.add(msg.topic, msg.value)
                if bundle is not None and msg.topic == CONFIG.final_topic:
                    task = asyncio.create_task(self.evaluate(bundle))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
        finally:
            await consumer.stop()


def main() -> None:
    try:
        asyncio.run(Evaluator().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


__all__ = ["Bundle", "Evaluator", "Score", "evaluate_bundle", "interpret_improvement"]
