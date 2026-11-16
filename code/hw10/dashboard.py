"""Part 1: Streamlit operations dashboard for the Kafka agent pipeline and its semantic cache.

    PYTHONPATH=code streamlit run code/hw10/dashboard.py --server.port 8638

Three pages: Summary (health), Evaluation (judge results and judge validation), and Trace lookup
(one request's journey by trace_id). All numbers come from files this project writes:

    data/hw10/spans.jsonl         structured spans (ingress, Planner, Writer, Reviewer, evaluator)
    data/hw10/eval_results.jsonl  one record per evaluated trace (scores, reasons, messages)
    reports/hw10/raw/*.json|csv   judge validation and the example trace ids
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from hw8.tracing import read_spans, stage_sort_key

from hw10.config import CONFIG, EVAL_RESULTS, PREFIX, RAW_DIR, SPANS
from hw10.metrics import request_rows, summarize_requests
from hw10.validation_stats import spearman

st.set_page_config(
    page_title=f"{PREFIX} operations dashboard", page_icon=":bar_chart:", layout="wide"
)


# ---- cached loaders ------------------------------------------------------------------------
def _mtime(path: Path) -> float:
    return os.path.getmtime(path) if path.exists() else 0.0


@st.cache_data(ttl=15, show_spinner=False)
def load_spans(mtime: float) -> list[dict]:
    """Parse the span file once per change (the mtime is part of the cache key)."""
    return read_spans()


@st.cache_data(ttl=15, show_spinner=False)
def load_evaluations(mtime: float) -> list[dict]:
    if not EVAL_RESULTS.exists():
        return []
    records = []
    for line in EVAL_RESULTS.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


@st.cache_data(ttl=60, show_spinner=False)
def load_json(path: str, mtime: float):
    return json.loads(Path(path).read_text(encoding="utf-8")) if mtime else None


@st.cache_resource
def redis_client():
    """One Redis connection reused across reruns (an expensive, shareable resource)."""
    import redis

    client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1, socket_timeout=1)
    client.ping()
    return client


@st.cache_data(ttl=10, show_spinner=False)
def live_cache_entries() -> int | None:
    try:
        return sum(1 for _ in redis_client().scan_iter(match=f"{PREFIX}:cache:*", count=500))
    except Exception:  # noqa: BLE001 - Redis being down must not break the page
        return None


def fmt_ms(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value / 1000:.2f} s" if value >= 1000 else f"{value:.0f} ms"


def fmt_pct(value: float) -> str:
    return "n/a" if value is None or math.isnan(value) else f"{100 * value:.1f}%"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"


def header(title: str) -> None:
    st.title(title)
    st.caption(
        f"Akanksha Shukla  |  SID4 {CONFIG.sid4}  |  PREFIX {PREFIX}  |  DATA 260 HW10  |  "
        f"judge: local Ollama model, generator: {CONFIG.model}"
    )


# ---- page 1: summary -----------------------------------------------------------------------
WINDOWS = {
    "Last 15 minutes": 15 * 60,
    "Last hour": 3600,
    "Last 24 hours": 86400,
    "All recorded data": None,
}


def summary_page() -> None:
    header("Operations summary")
    spans = load_spans(_mtime(SPANS))
    if not spans:
        st.warning(f"No spans found at {SPANS}. Start the stack and send a request first.")
        return
    choice = st.sidebar.radio("Time window", list(WINDOWS), index=3)
    since = None if WINDOWS[choice] is None else time.time() - WINDOWS[choice]
    rows = request_rows(spans, since)
    stats = summarize_requests(rows)
    first = iso(rows[0]["start"]) if rows else "n/a"
    last = iso(rows[-1]["end"]) if rows else "n/a"
    window_text = f"{choice} (data from {first} to {last})"
    source = (
        "`data/hw10/spans.jsonl`: one `request` span per ingress call (written by `hw9/ingress.py`)"
    )

    left, mid, right, last_col = st.columns(4)
    left.metric("Requests", stats["requests"])
    left.caption(f"Window: {window_text}. Source: {source}.")
    mid.metric(
        "Semantic-cache hit rate",
        fmt_pct(stats["hit_rate"]),
        help="hits / all requests. A hit returns a stored answer without running the agents.",
    )
    mid.caption(
        f"{stats['hits']} hits vs {stats['misses']} misses. Window: {choice}. "
        "Source: `request` spans, `path` = cache_hit or cache_miss."
    )
    right.metric(
        "Error rate",
        fmt_pct(stats["error_rate"]),
        help="requests whose `request` span has status=error (dead-lettered or timed out) / all requests",
    )
    right.caption(f"{stats['errors']} failed requests. Window: {choice}. Source: `request` spans.")
    lat = stats["latency_all_ok"]
    last_col.metric(
        "End-to-end latency (p50 / p95)",
        f"{fmt_ms(lat['p50'])} / {fmt_ms(lat['p95'])}",
        help="Time from the request reaching the ingress to the answer being returned (hits and misses together).",
    )
    last_col.caption(
        f"{lat['n']} successful requests. Window: {choice}. Source: `request` span duration."
    )

    st.subheader("Cache hits and cache misses are different latency populations")
    table = pd.DataFrame(
        [
            {"Path": "Cache hit (answer from Redis)", **_lat_row(stats["latency_hit"])},
            {"Path": "Cache miss (full agent pipeline)", **_lat_row(stats["latency_miss"])},
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(
        f"Window: {choice}. Source: `request` span durations, successful requests only. "
        "A miss includes the cache lookup, three Kafka hops, the three agents, and storing the answer."
    )

    if rows:
        frame = pd.DataFrame(
            {
                "time": [datetime.fromtimestamp(r["start"], UTC) for r in rows],
                "latency_ms": [r["request_ms"] for r in rows],
                "path": [
                    "error" if r["status"] == "error" else r["path"].replace("cache_", "cache ")
                    for r in rows
                ],
                "trace_id": [r["trace_id"] for r in rows],
            }
        )
        chart = (
            alt.Chart(frame)
            .mark_circle(size=70, opacity=0.8)
            .encode(
                x=alt.X("time:T", title="request time (UTC)"),
                y=alt.Y(
                    "latency_ms:Q", scale=alt.Scale(type="log"), title="latency (ms, log scale)"
                ),
                color=alt.Color(
                    "path:N",
                    scale=alt.Scale(
                        domain=["cache hit", "cache miss", "error"],
                        range=["#2a9d8f", "#e9a23b", "#d1495b"],
                    ),
                    title="path",
                ),
                tooltip=["trace_id", "path", "latency_ms", "time"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, width="stretch")
        st.caption("Each dot is one request. Hits sit near the bottom, misses near the top.")

    entries = live_cache_entries()
    st.metric(
        "Entries now in the Redis semantic cache", "unavailable" if entries is None else entries
    )
    st.caption("Window: now (live). Source: Redis `SCAN s7838:cache:*`.")


def _lat_row(item: dict) -> dict:
    return {
        "Requests": item["n"],
        "Mean": fmt_ms(item["mean"]),
        "p50": fmt_ms(item["p50"]),
        "p95": fmt_ms(item["p95"]),
    }


# ---- page 2: evaluation --------------------------------------------------------------------
def evaluation_page() -> None:
    header("Evaluation results")
    records = [r for r in load_evaluations(_mtime(EVAL_RESULTS)) if r.get("status") == "ok"]
    st.subheader("Pipeline evaluation (Part 2): scores by stage and case")
    st.caption(
        "Source: `data/hw10/eval_results.jsonl`, written by the evaluator after the Planner plan, Writer draft "
        "and Reviewer final with the same correlation_id were joined. Window: every evaluated trace. "
        "Scale: 1 (very poor) to 5 (excellent), local judge model via DeepEval GEval."
    )
    if not records:
        st.info("No evaluation records yet. Start the evaluator and send a question.")
    else:
        frame = pd.DataFrame(
            [
                {
                    "trace_id": r["trace_id"],
                    "question": r["question"],
                    "Plan Quality (Planner)": r["scores"]["plan_quality"]["score"],
                    "Writer Helpfulness (draft)": r["scores"]["writer_helpfulness"]["score"],
                    "Final Answer Helpfulness": r["scores"]["final_helpfulness"]["score"],
                    "Final minus draft": r["improvement"]["difference"],
                    "Final == draft text": r["improvement"]["text_identical"],
                    "Reviewer status": r["final_status"],
                    "Evaluation time (ms)": r["evaluation_ms"],
                }
                for r in records
            ]
        )
        stages = [
            "Plan Quality (Planner)",
            "Writer Helpfulness (draft)",
            "Final Answer Helpfulness",
        ]
        summary = frame[stages].agg(["count", "mean", "std", "min", "max"]).T.round(2)
        st.markdown("**Average score by pipeline stage**")
        st.table(summary.style.format("{:.2f}"))
        long = frame.melt(
            id_vars=["trace_id"], value_vars=stages, var_name="stage", value_name="score"
        )
        counts = long.groupby(["stage", "score"]).size().reset_index(name="cases")
        st.altair_chart(
            alt.Chart(counts)
            .mark_bar()
            .encode(
                x=alt.X("score:O", title="score (1-5)"),
                y=alt.Y("cases:Q", title="number of cases"),
                color=alt.value("#2a9d8f"),
                column=alt.Column("stage:N", title=None, sort=stages),
                tooltip=["stage", "score", "cases"],
            )
            .properties(width=240, height=200),
        )
        st.markdown("**Every evaluated case**")
        shown = frame.drop(columns=["Evaluation time (ms)"]).copy()
        shown["question"] = shown["question"].str.slice(0, 60)
        st.table(shown.set_index("trace_id"))
        st.markdown("**What the scores suggest about Planner, Writer and Reviewer coordination**")
        for line in interpret(frame, stages):
            st.markdown(f"- {line}")

    st.divider()
    st.subheader("Judge validation (Part 3): judge versus human labels")
    validation = load_json(
        str(RAW_DIR / "judge_validation.json"), _mtime(RAW_DIR / "judge_validation.json")
    )
    if not validation:
        st.info(
            "Not run yet. After the 20 human labels are committed, run `make validate-hw10`; "
            "Spearman correlation, mean absolute difference and repeatability appear here."
        )
        return
    doc = validation["documented"]
    run1 = doc["per_run"][0]
    rep = doc["repeatability"]
    a, b, c, d = st.columns(4)
    a.metric("Spearman rho (human vs judge, run 1)", f"{run1['spearman_rho']:.3f}")
    a.caption(f"p = {run1['spearman_p_value']:.4f}, n = {run1['spearman_n']}")
    b.metric("Mean absolute difference", f"{run1['mean_abs_diff']:.2f} points")
    b.caption("average of |human - judge| over the 20 drafts, 1-5 scale")
    c.metric("Cases whose score changed across 3 runs", fmt_pct(rep["cases_changed"]))
    c.caption(f"{rep['pairs_changed'] * 100:.1f}% of run pairs differ")
    d.metric(
        "Mean / max absolute change", f"{rep['mean_abs_change']:.2f} / {rep['max_abs_change']:.0f}"
    )
    d.caption("over all case and run pairs, points on the 1-5 scale")
    settings = validation["judge_settings"]
    st.caption(
        f"Criterion: {validation['criterion']}. Judge: {settings['judge_model']} via {settings['runtime']}, "
        f"temperature {settings['temperature']}, seed {settings['seed']}, {settings['framework']}. "
        f"Source: `reports/hw10/raw/judge_validation.json` and `judge_validation_cases.csv`."
    )
    cases_path = RAW_DIR / "judge_validation_cases.csv"
    if cases_path.exists():
        cases = pd.read_csv(cases_path)
        st.dataframe(cases, hide_index=True, width="stretch")
        scatter = (
            alt.Chart(cases)
            .mark_circle(size=90, opacity=0.6)
            .encode(
                x=alt.X("human:Q", scale=alt.Scale(domain=[0.5, 5.5]), title="human label"),
                y=alt.Y(
                    "judge_run1:Q", scale=alt.Scale(domain=[0.5, 5.5]), title="judge score (run 1)"
                ),
                tooltip=["case_id", "human", "judge_run1", "judge_run2", "judge_run3"],
            )
            .properties(height=280, width=360)
        )
        st.altair_chart(scatter)
        # Recompute from the raw rows so the displayed statistics can be checked.
        recomputed = spearman(cases["human"].tolist(), cases["judge_run1"].tolist())
        st.caption(f"Recomputed from the per-case table: rho = {recomputed['rho']:.3f}.")
    if "sensitivity" in validation:
        s = validation["sensitivity"]
        st.markdown(
            f"**Sensitivity check (temperature {s['temperature']}, new seed each run):** cases changed "
            f"{fmt_pct(s['repeatability']['cases_changed'])}, mean / max absolute change "
            f"{s['repeatability']['mean_abs_change']:.2f} / {s['repeatability']['max_abs_change']:.0f}."
        )


def interpret(frame: pd.DataFrame, stages: list[str]) -> list[str]:
    """Plain statements generated from the displayed numbers (no model involved)."""
    n = len(frame)
    plan, writer, final = (frame[s] for s in stages)
    lines = [
        f"Across {n} evaluated requests the Planner's plans average {plan.mean():.2f}, the Writer's drafts "
        f"{writer.mean():.2f}, and the final answers {final.mean():.2f} (1-5 scale)."
    ]
    identical = int(frame["Final == draft text"].sum())
    lines.append(
        f"The Reviewer returned the Writer's text unchanged in {identical} of {n} cases, so the average "
        f"final-minus-draft difference is {frame['Final minus draft'].mean():+.2f}. The Reviewer is a "
        "word-count rule, not a rewriting agent, so it cannot improve an answer; it can only approve or reject."
    )
    if n >= 5 and plan.nunique() > 1 and writer.nunique() > 1:
        rho = spearman(plan.tolist(), writer.tolist())["rho"]
        lines.append(
            f"Plan quality and draft quality move together with Spearman rho = {rho:.2f} across the cases: "
            + (
                "better plans tend to come with better drafts."
                if rho >= 0.3
                else "the Writer's result does not clearly depend on the plan it was given."
            )
        )
    weakest = min(stages, key=lambda s: frame[s].mean())
    lines.append(
        f"The lowest-scoring stage is **{weakest}**, the first place to look when quality drops."
    )
    return lines


# ---- page 3: trace lookup ------------------------------------------------------------------
def trace_page() -> None:
    header("Trace lookup")
    st.caption(
        "Enter a trace_id (the HW8 correlation_id) to see the request's journey. Source: "
        "`data/hw10/spans.jsonl`; the evaluator's scores come from `data/hw10/eval_results.jsonl`."
    )
    if "trace_id" not in st.session_state:  # deep link: /trace?trace_id=<id>
        st.session_state["trace_id"] = str(st.query_params.get("trace_id", ""))
    examples = (
        load_json(str(RAW_DIR / "example_traces.json"), _mtime(RAW_DIR / "example_traces.json"))
        or {}
    )
    if examples:
        picks = {
            "Cache hit example": examples["cache_hit"]["trace_id"],
            "Cache miss example": examples["cache_miss"]["trace_id"],
            "Failed example": examples["failed"]["trace_id"],
        }
        cols = st.columns(len(picks))
        for col, (label, trace_id) in zip(cols, picks.items(), strict=True):
            if col.button(label, width="stretch"):
                st.session_state["trace_id"] = trace_id
    trace_id = st.text_input(
        "trace_id", key="trace_id", placeholder="e.g. 9ed2a35f-85fd-45b2-a472-2d5afe6df0ee"
    ).strip()
    if not trace_id:
        st.info("Type or paste a trace_id, or use one of the example buttons.")
        return
    spans = load_spans(_mtime(SPANS))
    found = sorted((s for s in spans if s["trace_id"] == trace_id), key=stage_sort_key)
    if not found:
        st.error(f"No spans for trace_id {trace_id!r}.")
        return

    stages_seen = {s["stage"] for s in found}
    request = next((s for s in found if s["stage"] == "request"), None)
    failed = [s for s in found if s["status"] == "error" and s["stage"] not in {"request"}]
    if request and request["status"] == "error":
        st.error(
            f"FAILED path: request failed at stage **{request['attrs'].get('failed_stage')}** "
            f"with error `{request['error']}`."
        )
    elif "planner" not in stages_seen:
        st.success("CACHE HIT path: answered from the semantic cache; the Kafka agents never ran.")
    else:
        st.info(
            "CACHE MISS path: the question went through the cache lookup, Kafka, and all three agents."
        )
    if failed and not (request and request["status"] == "error"):
        st.warning(f"{len(failed)} span(s) with status=error.")

    origin = min(s["start"] for s in found)
    frame = pd.DataFrame(
        [
            {
                "stage": s["stage"],
                "service": s["service"],
                "start": iso(s["start"]),
                "end": iso(s["end"]),
                "duration_ms": round(s["duration_ms"], 2),
                "status": s["status"],
                "error": s["error"] or "",
                "details": json.dumps(s["attrs"], default=str)[:160],
                "_from_ms": (s["start"] - origin) * 1000,
                "_to_ms": max((s["end"] - origin) * 1000, (s["start"] - origin) * 1000 + 0.6),
            }
            for s in found
        ]
    )
    st.dataframe(frame.drop(columns=["_from_ms", "_to_ms"]), hide_index=True, width="stretch")
    gantt = (
        alt.Chart(frame)
        .mark_bar(height=18)
        .encode(
            x=alt.X("_from_ms:Q", title="milliseconds since the first span started"),
            x2="_to_ms:Q",
            y=alt.Y("stage:N", sort=None, title=None),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(
                    domain=["ok", "error", "skipped"], range=["#2a9d8f", "#d1495b", "#999999"]
                ),
            ),
            tooltip=["stage", "start", "end", "duration_ms", "status", "error"],
        )
        .properties(height=max(120, 28 * len(frame)))
    )
    st.altair_chart(gantt, width="stretch")

    evaluation = next(
        (r for r in load_evaluations(_mtime(EVAL_RESULTS)) if r["trace_id"] == trace_id), None
    )
    if evaluation and evaluation.get("status") == "ok":
        st.markdown("**Evaluator scores for this trace** (1-5)")
        score_cols = st.columns(3)
        for col, key, title in zip(
            score_cols,
            ["plan_quality", "writer_helpfulness", "final_helpfulness"],
            ["Plan Quality", "Writer Helpfulness", "Final Answer Helpfulness"],
            strict=True,
        ):
            col.metric(title, evaluation["scores"][key]["score"])
            col.caption(evaluation["scores"][key]["reason"][:220])
        st.caption(evaluation["improvement"]["interpretation"])
    with st.expander("Raw spans (JSON)"):
        st.json(found)


pages = [
    st.Page(
        summary_page,
        title="Summary",
        icon=":material/monitoring:",
        default=True,
    ),
    st.Page(
        evaluation_page, title="Evaluation", icon=":material/fact_check:", url_path="evaluation"
    ),
    st.Page(trace_page, title="Trace lookup", icon=":material/search:", url_path="trace"),
]
if __name__ == "__main__":  # Streamlit runs the script as __main__; imports (tests) skip this
    st.navigation(pages).run()
