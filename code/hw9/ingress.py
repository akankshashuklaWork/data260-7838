"""Ingress endpoint: a semantic cache in front of the HW8 agent pipeline (Part 2).

On a miss the question follows the normal HW8 path (Kafka -> Planner -> Writer -> Reviewer, local
qwen2:7b). On a hit the stored final answer is returned without running the agents.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from hw8.common import log
from hw8.tracing import new_trace_id, write_span
from pydantic import BaseModel

from .config import DEFAULT_THRESHOLD
from .listing_db import ListingDatabase
from .pipeline_client import PipelineClient, PipelineError
from .semantic_cache import SemanticCache


def facts_for(listing: dict[str, Any]) -> str:
    """Record facts handed to the Writer so its answer depends on the database row."""
    return (
        f"{listing['property_title']} in {listing['property_location']} ({listing['property_category']}): "
        f"monthly rent ${listing['monthly_rent']:,}, security deposit ${listing['security_deposit']:,}, "
        f"pet policy: {listing['pet_policy']}."
    )


class QueryHandler:
    def __init__(self, cache: SemanticCache, db: ListingDatabase, pipeline: PipelineClient) -> None:
        self.cache, self.db, self.pipeline = cache, db, pipeline
        self.check_data_version = (
            True  # invalidation strategy of 3.5 (can be switched off to show stale hits)
        )
        self.hits = 0
        self.misses = 0
        self.errors = 0

    async def handle(
        self, question: str, threshold: float | None = None, trace_id: str | None = None
    ) -> dict[str, Any]:
        """Answer one question. The trace_id (made here when absent) is also the HW8 correlation_id."""
        trace_id = trace_id or new_trace_id()
        t_start = time.perf_counter()
        stamps = {"request_received": time.time()}
        limit = self.cache.threshold if threshold is None else threshold

        vector = self.cache.embed(question)
        stamps["embedded"] = time.time()
        embed_ms = (time.perf_counter() - t_start) * 1000
        entry, similarity = self.cache.lookup(vector, limit)
        stamps["lookup_done"] = time.time()
        lookup_ms = (time.perf_counter() - t_start) * 1000

        if entry and self.check_data_version and entry["dependency"] != "none":
            listing_id = int(entry["dependency"])
            current = self.db.get_listing(listing_id)
            if current and str(current["data_version"]) != entry["data_version"]:
                log(
                    "CACHE",
                    f"STALE entry for listing {listing_id}: stored v{entry['data_version']} "
                    f"!= current v{current['data_version']} -> invalidated, treating as miss",
                )
                self.cache.delete(entry["key"])
                entry = None
                stamps["invalidated"] = time.time()

        lookup_status = "hit" if entry else "miss"
        write_span(
            trace_id, "cache_lookup", stamps["request_received"], stamps["lookup_done"],
            service="ingress", result=lookup_status, similarity=round(similarity, 4),
            threshold=limit, embed_ms=round(embed_ms, 2), invalidated="invalidated" in stamps,
            question=question[:120],
        )  # fmt: skip

        if entry:
            self.hits += 1
            total_ms = (time.perf_counter() - t_start) * 1000
            log(
                "CACHE",
                f"HIT similarity={similarity:.4f} threshold={limit:.2f} "
                f"matched='{entry['query'][:60]}' latency_ms={total_ms:.1f} trace_id={trace_id}",
            )
            write_span(
                trace_id, "request", stamps["request_received"], time.time(), service="ingress",
                path="cache_hit", is_cached=True, similarity=round(similarity, 4),
            )  # fmt: skip
            return {
                "trace_id": trace_id,
                "answer": entry["answer"],
                "is_cached": True,
                "similarity": round(similarity, 4),
                "latency_ms": round(total_ms, 1),
                "lookup_ms": round(lookup_ms, 1),
                "matched_query": entry["query"],
                "data_version": entry["data_version"],
                "timestamps": stamps,
            }

        self.misses += 1
        log(
            "CACHE",
            f"MISS best_similarity={similarity:.4f} threshold={limit:.2f} -> running agent pipeline "
            f"trace_id={trace_id}",
        )
        listing = self.db.find_listing_in_text(question)
        context = facts_for(listing) if listing else ""
        stamps["pipeline_start"] = time.time()
        try:
            answer, pipeline_ms = await self.pipeline.ask(question, context, trace_id=trace_id)
        except (PipelineError, TimeoutError) as exc:
            self.errors += 1
            stage = exc.stage if isinstance(exc, PipelineError) else "pipeline_timeout"
            error = exc.error if isinstance(exc, PipelineError) else "no answer before the timeout"
            log("CACHE", f"FAILED stage={stage} error={error} trace_id={trace_id}")
            write_span(
                trace_id, "request", stamps["request_received"], time.time(), status="error",
                error=error, service="ingress", path="cache_miss", is_cached=False,
                failed_stage=stage,
            )  # fmt: skip
            return {
                "trace_id": trace_id,
                "error": error,
                "failed_stage": stage,
                "is_cached": False,
                "similarity": round(similarity, 4),
                "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
            }
        stamps["pipeline_done"] = time.time()
        marker = str(listing["data_version"]) if listing else "static"
        store_start = time.time()
        self.cache.put(question, vector, answer, marker, str(listing["id"]) if listing else "none")
        write_span(trace_id, "cache_store", store_start, time.time(), service="ingress")
        total_ms = (time.perf_counter() - t_start) * 1000
        log(
            "CACHE",
            f"stored answer (data_version={marker}) total_ms={total_ms:.1f} pipeline_ms={pipeline_ms:.1f}",
        )
        write_span(
            trace_id, "request", stamps["request_received"], time.time(), service="ingress",
            path="cache_miss", is_cached=False, similarity=round(similarity, 4),
        )  # fmt: skip
        return {
            "trace_id": trace_id,
            "answer": answer,
            "is_cached": False,
            "similarity": round(similarity, 4),
            "latency_ms": round(total_ms, 1),
            "lookup_ms": round(lookup_ms, 1),
            "pipeline_ms": round(pipeline_ms, 1),
            "matched_query": None,
            "data_version": marker,
            "timestamps": stamps,
        }


class AskRequest(BaseModel):
    question: str
    threshold: float | None = None


handler: QueryHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global handler
    pipeline = PipelineClient()
    await pipeline.start()
    handler = QueryHandler(SemanticCache(DEFAULT_THRESHOLD), ListingDatabase(), pipeline)
    handler.cache.embed("warm-up")  # load the embedding model now, not during the first request
    log(
        "INGRESS",
        f"Semantic cache ingress started at http://127.0.0.1:{os.getenv('INGRESS_PORT', '8638')}",
    )
    yield
    await pipeline.stop()


app = FastAPI(title="Rental Q&A semantic cache", lifespan=lifespan)


@app.post("/ask")
async def ask(request: AskRequest) -> Any:
    assert handler is not None
    result = await handler.handle(request.question, request.threshold)
    if "error" in result:  # the pipeline gave up: report the failing stage, keep the trace_id
        return JSONResponse(result, status_code=502)
    return result


@app.post("/reset")
async def reset() -> dict[str, Any]:
    """Empty the cache and the counters (used before a test run)."""
    assert handler is not None
    handler.hits = handler.misses = handler.errors = 0
    return {"cleared": handler.cache.clear()}


@app.get("/stats")
async def stats() -> dict[str, Any]:
    assert handler is not None
    total = handler.hits + handler.misses
    return {
        "hits": handler.hits,
        "misses": handler.misses,
        "errors": handler.errors,
        "hit_rate": round(handler.hits / total, 4) if total else 0.0,
        "error_rate": round(handler.errors / total, 4) if total else 0.0,
        "entries": handler.cache.count(),
    }
