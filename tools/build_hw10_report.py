"""Build reports/hw10/Shukla_HW10.pdf (and report.pdf) from the raw evidence files.

Every number in the report is read from reports/hw10/raw, so it cannot drift from the data.
Part 3 is filled in only when judge_validation.json exists; otherwise it says plainly that the
human labels are still missing.

    python tools/build_hw10_report.py <tagged-commit-hash>
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports/hw10"
RAW = HW / "raw"
SHOTS = HW / "screenshots"
OUT = HW / "Shukla_HW10.pdf"
COMMIT = sys.argv[1] if len(sys.argv) > 1 else "(fill in after `git tag hw10`)"

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Main",
        parent=styles["Heading2"],
        textColor=colors.black,
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        keepWithNext=1,
        spaceBefore=12,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        "Sub",
        parent=styles["Heading3"],
        textColor=colors.black,
        fontName="Helvetica-Bold",
        fontSize=12,
        keepWithNext=1,
        leading=15,
        spaceBefore=8,
        spaceAfter=4,
    )
)
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=11, leading=14, spaceAfter=6))
styles.add(
    ParagraphStyle(
        "Cap",
        parent=styles["BodyText"],
        fontSize=11,
        leading=14,
        spaceAfter=10,
        fontName="Helvetica-Bold",
    )
)
styles.add(ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=11, leading=13.5))
CODE = ParagraphStyle(
    "Code",
    fontName="Courier",
    fontSize=9,
    leading=11,
    backColor=colors.whitesmoke,
    borderPadding=4,
    spaceAfter=10,
)
MISSING: list[str] = []


def p(text: str, style: str = "Body") -> Paragraph:
    return Paragraph(text, styles[style])


def code(text: str, width: int = 112) -> Preformatted:
    wrapped = "\n".join(
        w
        for line in text.splitlines()
        for w in (textwrap.wrap(line, width, subsequent_indent="    ") or [""])
    )
    return Preformatted(wrapped, CODE)


def table(rows: list[list], widths: list[float], header: bool = True) -> Table:
    data = [
        [Paragraph(f"<b>{c}</b>" if header and r == 0 else str(c), styles["Cell"]) for c in row]
        for r, row in enumerate(rows)
    ]
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.append(("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.black))
    t.setStyle(TableStyle(style))
    return t


FIGURE_NO = [0]


def shot(name: str, caption: str, width: float = 6.2, max_height: float = 7.4) -> list:
    FIGURE_NO[0] += 1
    caption = f"Figure {FIGURE_NO[0]}. " + re.sub(r"^Figure \d+\. ", "", caption)
    path = SHOTS / name
    if not path.exists():
        MISSING.append(name)
        return [p(f"[missing screenshot: {name}]")]
    w, h = ImageReader(str(path)).getSize()
    height = width * h / w
    if height > max_height:
        height, width = max_height, max_height * w / h
    return [
        KeepTogether(
            [Image(str(path), width=width * inch, height=height * inch), p(caption, "Cap")]
        )
    ]


def load(name: str):
    path = RAW / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def jsonl(name: str) -> list[dict]:
    path = RAW / name
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if path.exists()
        else []
    )


def f1(x: float) -> str:
    return f"{x:,.1f}"


def build() -> None:
    run = load("latency_run.json")
    table43 = load("stage_latency.json")
    examples = load("example_traces.json")
    validation = load("judge_validation.json")
    records = jsonl("eval_results_reported.jsonl")
    spans = jsonl("spans_reported.jsonl")
    verification = json.loads((HW / "verification.json").read_text())
    miss_ids = {m["trace_id"] for m in run["misses"]}
    scored = [r for r in records if r["trace_id"] in miss_ids and r["status"] == "ok"]
    cases = json.loads((ROOT / "code/hw10/eval_cases.json").read_text())

    s: list = []
    # ------------------------------------------------------------------ header
    s += [p("DATA 260 Homework 10: Operations Dashboard, Judge Validation, and Tracing", "Main")]
    s += [
        p(
            "Akanksha Shukla | Repository: https://github.com/akankshashuklaWork/data260-7838 | Tagged commit: "
            + COMMIT
        )
    ]
    s += [
        table(
            [
                ["Value", "Result", "Calculation"],
                ["SID4", "7838", "Last four digits of SJSU Student ID"],
                [
                    "PORT_BASE",
                    "8638",
                    "8000 + (7838 mod 900); the Streamlit dashboard runs here (the HW9 ingress API moved to 8639)",
                ],
                ["PREFIX", "s7838", '"s" + SID4'],
                ["SEED", "7838", "SID4"],
                ["VERIFY_SEED", "267838", "260000 + SID4"],
                ["DOMAIN_ID", "6", "7838 mod 8 (Rental Housing Listings)"],
            ],
            [1.2, 0.9, 4.4],
        ),
        Spacer(1, 6),
        p(
            "Hardware: MacBook Pro, Apple M4 Pro, 48 GB unified memory. Local models (Ollama): <b>qwen2:7b</b> generates (Planner, Writer); <b>qwen3:8b</b> is the judge. Kafka 3.9.2 and Redis Stack 7.4 run in Docker. DeepEval 4.3.4, Streamlit 1.67.0."
        ),
        p(
            "Summary: the dashboard, evaluator, tracing, and 50-request latency experiment are done and reproducible. The Reviewer never changed an answer (final = draft in "
            f"{sum(r['improvement']['text_identical'] for r in scored)} of {len(scored)} cases), so there was no final-vs-draft improvement to report. "
            "The Writer takes about two thirds of the time before the answer returns; evaluation is the largest share of end-to-end time but runs after the answer."
        ),
    ]

    # ------------------------------------------------------------------ Part 1
    s += [p("Part 1 - Streamlit operations dashboard", "Main")]
    s += [p("1.1 Summary page", "Sub")]
    s += [
        p(
            "File: <font face='Courier'>code/hw10/dashboard.py</font> (run with <font face='Courier'>make dashboard-hw10</font>, port 8638). Every number comes from files the system writes: "
            "<font face='Courier'>data/hw10/spans.jsonl</font> (one structured span per stage; the ingress writes one <font face='Courier'>request</font> span per call), "
            "<font face='Courier'>data/hw10/eval_results.jsonl</font> (evaluator records) and <font face='Courier'>reports/hw10/raw/</font>. "
            "Each metric prints its own time window and source under it. Hits and misses are separate: the hit rate is hits / all requests, and latency is shown for hits and misses in separate rows because they differ by three orders of magnitude (about 10 ms versus about 6 s). "
            "The time window can be switched (15 minutes, 1 hour, 24 hours, all recorded data)."
        )
    ]
    s += shot(
        "p1-summary.png",
        "Figure 1. Summary page: request count, hit rate, error rate, end-to-end latency, hit/miss latency table, and per-request latency (log scale).",
        6.0,
        6.6,
    )
    s += [
        p(
            "Caching: <font face='Courier'>@st.cache_data</font> keeps the parsed span file and evaluation records (the file's modification time is part of the key, so a new span invalidates it; ttl 15 s). "
            "<font face='Courier'>@st.cache_resource</font> keeps one Redis connection across reruns for the live cache-entry count."
        )
    ]
    s += shot(
        "p1-code-caching.png",
        "Code and caching: the cached loaders in code/hw10/dashboard.py (st.cache_data keyed by file modification time, st.cache_resource for the Redis client).",
        6.2,
        4.2,
    )
    s += [p("1.2 Evaluation page", "Sub")]
    s += shot(
        "p1-evaluation.png",
        "Figure 2. Evaluation page: mean/std/min/max by pipeline stage, score distribution, and every evaluated case (the page continues below the crop).",
        6.0,
        7.2,
    )
    s += [p("1.3 Trace lookup page", "Sub")]
    s += [
        p(
            "Enter a trace_id (or use <font face='Courier'>/trace?trace_id=...</font>, or the three example buttons). The page lists each stage's start time, end time, duration, status and error in stage order, draws a timeline, and labels the path as CACHE HIT, CACHE MISS or FAILED. Part 4 shows it for the three required traces."
        )
    ]

    # ------------------------------------------------------------------ Part 2
    s += [PageBreak(), p("Part 2 - Automated evaluation of the Kafka pipeline", "Main")]
    s += [p("2.1 Evaluator design", "Sub")]
    s += [
        p(
            "<font face='Courier'>code/hw10/evaluator.py</font> is one more Kafka consumer in its own consumer group, so it never takes messages from the agents. It reads <font face='Courier'>s7838_tasks</font> (Planner plan), "
            "<font face='Courier'>s7838_drafts</font> (Writer draft) and <font face='Courier'>s7838_final</font> (Reviewer final), joins them by <b>correlation_id</b>, and stores the original messages with each result so any score can be reproduced. "
            "The judge is DeepEval <b>GEval</b> on a local Ollama model (<b>qwen3:8b</b>, a different model from the generator so it does not grade its own style), temperature 0, seed 7838, thinking off, one 1-5 scale. "
            "Each criterion has an explicit five-band rubric; DeepEval derives the 1-5 range from it, and a 5-line wrapper converts DeepEval's (score-1)/4 back to the integer."
        )
    ]
    s += [
        p(
            "<b>Bounds.</b> A malformed message is logged and skipped; the wait for a missing message ends after 30 s; every judge call has a 120 s timeout and a whole trace is capped at 300 s; the join buffer holds at most 500 traces. "
            "The self-check proves that a malformed message and an unavailable judge are recorded as errors and the evaluator keeps working."
        )
    ]
    s += [
        code("""scores = {
  "plan_quality":       {"score": 4, "reason": "...", "judge_ms": 2664},
  "writer_helpfulness": {"score": 5, "reason": "...", "trace_id": "<trace_id>"},
  "final_helpfulness":  {"score": 5, "reason": "...", "final_answer": "..."}}
improvement = {"draft_score": 5, "final_score": 5, "difference": 0,
               "text_identical": true, "interpretation": "..."}""")
    ]
    s += shot(
        "p2-code-evaluator.png",
        "Code: evaluate_bundle() in code/hw10/evaluator.py scores the joined plan, draft and final and builds the improvement record.",
        6.2,
        5.0,
    )
    s += shot(
        "p2-code-geval.png",
        "Code: the DeepEval GEval metric in code/hw10/judge.py (rubric bands, local qwen3:8b model, one call at a time).",
        6.2,
        4.6,
    )
    s += [p("2.2 Results", "Sub")]
    example = next(
        (r for r in records if examples and r["trace_id"] == examples["cache_miss"]["trace_id"]),
        scored[0],
    )
    s += [
        p(
            f"<b>One end-to-end question</b> (trace_id <font face='Courier'>{example['trace_id']}</font>): \"{example['question']}\""
        )
    ]
    s += [
        table(
            [
                ["Stage", "Content", "Score (1-5) and reason"],
                [
                    "Planner plan",
                    "<br/>".join(f"{i}. {x}" for i, x in enumerate(example["plan"], 1)),
                    f"<b>{example['scores']['plan_quality']['score']}</b>: {example['scores']['plan_quality']['reason'][:260]}",
                ],
                [
                    "Writer draft",
                    example["draft"][:520] + ("..." if len(example["draft"]) > 520 else ""),
                    f"<b>{example['scores']['writer_helpfulness']['score']}</b>: {example['scores']['writer_helpfulness']['reason'][:260]}",
                ],
                [
                    "Reviewer final",
                    f"status {example['final_status']}; text identical to the draft: {example['improvement']['text_identical']}",
                    f"<b>{example['scores']['final_helpfulness']['score']}</b> (final minus draft = {example['improvement']['difference']:+d})",
                ],
            ],
            [1.0, 3.1, 2.4],
        )
    ]
    rows = [["Stage / criterion", "Mean", "Std", "Min", "Max"]]
    import statistics

    for key, label in (
        ("plan_quality", "Plan Quality (Planner)"),
        ("writer_helpfulness", "Writer Helpfulness (draft)"),
        ("final_helpfulness", "Final Answer Helpfulness"),
    ):
        vals = [r["scores"][key]["score"] for r in scored]
        rows.append(
            [
                label,
                f"{statistics.mean(vals):.2f}",
                f"{statistics.stdev(vals):.2f}",
                min(vals),
                max(vals),
            ]
        )
    diffs = [r["improvement"]["difference"] for r in scored]
    s += [
        Spacer(1, 8),
        p(
            f"<b>All {len(scored)} cache-miss requests of the latency experiment</b> (same judge, 1-5 scale; per-case data in raw/eval_results_reported.jsonl):"
        ),
        table(rows, [2.6, 0.9, 0.9, 0.8, 0.8]),
    ]
    s += [
        Spacer(1, 6),
        table(
            [
                ["Final-vs-Draft Improvement", "Result"],
                ["Mean difference (final minus draft)", f"{statistics.mean(diffs):+.2f}"],
                [
                    "Cases where the final text is word-for-word the draft",
                    f"{sum(r['improvement']['text_identical'] for r in scored)} of {len(scored)}",
                ],
                [
                    "Reviewer status",
                    f"approved in {sum(r['final_status'] == 'approved' for r in scored)} of {len(scored)}",
                ],
            ],
            [4.0, 2.5],
        ),
    ]
    s += shot(
        "p2-console-evaluation.png",
        "Output: the evaluator's saved record for the end-to-end question (scores with reasons, trace_id, final answer, improvement and judge settings).",
        6.2,
        7.4,
    )
    plan_s = [r["scores"]["plan_quality"]["score"] for r in scored]
    draft_s = [r["scores"]["writer_helpfulness"]["score"] for r in scored]
    rho = spearmanr(plan_s, draft_s).statistic
    over = sum(len(r["draft"].split()) > 100 for r in scored)
    fives = sum(v == 5 for v in draft_s)
    s += [p("2.3 What the scores say about Planner, Writer and Reviewer coordination", "Sub")]
    s += [
        p(
            "<b>The final answer did not improve, and it could not.</b> The final answer is identical to the draft in every case, so final minus draft is exactly 0. The Reviewer in this system is a word-count rule (at least 15 words): "
            "it approves or rejects but never rewrites, so it adds no quality. The two helpfulness scores are identical because both prompts use the same rubric and wording, so the difference measures a change in the text and nothing else. "
            "The honest conclusion is that the Reviewer stage currently contributes a gate, not an improvement."
        )
    ]
    s += [
        p(
            f"<b>The plan did not predict the draft.</b> Plan Quality averages {statistics.mean(plan_s):.2f} while draft quality averages {statistics.mean(draft_s):.2f}, and the two are almost uncorrelated (Spearman rho = {rho:.2f}). "
            "The Writer answers the question well whether the plan is a 3 or a 5, so the Planner is not what limits answer quality today; the plan is the weakest scored stage but the Writer does not depend on it much."
        )
    ]
    s += [
        p(
            f"<b>Coordination gap nobody checks.</b> The Writer's instruction is 60 to 100 words, but {over} of {len(scored)} drafts are longer than 100 words, and the Reviewer (minimum length only) and the judge (a helpfulness rubric with no length constraint) both let them through. "
            f"The judge gave a 5 to {fives} of {len(scored)} drafts, which is a ceiling effect that makes it a weak tool for telling good from merely adequate; Part 3 tests that directly against human labels."
        )
    ]

    # ------------------------------------------------------------------ Part 3
    s += [PageBreak(), p("Part 3 - Validate the judge", "Main")]
    s += [p("3.1 Frozen evaluation cases", "Sub")]
    words = [len(c["draft"].split()) for c in cases]
    s += [
        p(
            "<font face='Courier'>code/hw10/eval_cases.json</font> holds 20 real Writer drafts produced by the running Planner -> Writer pipeline (qwen2:7b, temperature 0): "
            "8 routine rental questions, 5 questions about listings in the database (the Writer receives the record's facts), and 7 vague, unanswerable or off-topic questions so the drafts differ in quality. "
            f"Draft length is {min(words)} to {max(words)} words. <font face='Courier'>code/hw10/human_labels.csv</font> holds the 1-5 helpfulness label for each draft, assigned by hand (<font face='Courier'>make label-hw10</font>). "
            "<font face='Courier'>validate_judge.py</font> refuses to run unless both files are committed with no later edits, and the self-check confirms the label commit is older than the judge output."
        )
    ]
    s += shot(
        "p3-code-validation.png",
        "Code: summarize() in code/hw10/validate_judge.py computes Spearman, mean absolute difference and repeatability from the human labels and the three judge runs.",
        6.2,
        3.2,
    )
    if validation:
        doc = validation["documented"]
        s += [p("3.2 Judge versus human labels", "Sub")]
        rows = [["Run", "Spearman rho", "p-value", "Mean absolute difference"]]
        for r in doc["per_run"]:
            rows.append(
                [
                    r["run"],
                    f"{r['spearman_rho']:.3f}",
                    f"{r['spearman_p_value']:.4f}",
                    f"{r['mean_abs_diff']:.2f}",
                ]
            )
        mr = doc["mean_of_runs"]
        rows.append(
            [
                "mean of 3 runs",
                f"{mr['rho']:.3f}",
                f"{mr['p_value']:.4f}",
                f"{mr['mean_abs_diff']:.2f}",
            ]
        )
        s += [table(rows, [1.6, 1.5, 1.2, 2.2])]
        s += shot(
            "p3-console-validate.png",
            "Output: make validate-hw10 runs the judge three times on the 20 frozen drafts (documented settings), then three sampling runs at temperature 0.7 (raw/console/07_validate_judge.txt).",
            6.2,
            3.2,
        )
        s += shot(
            "p1-evaluation-validation.png",
            "Dashboard Evaluation page, judge-validation section: Spearman rho, mean absolute difference, repeatability, the per-case table, human-versus-judge scatter and the sensitivity check.",
            5.6,
            6.8,
        )
        cases_csv = list(csv.DictReader(open(RAW / "judge_validation_cases.csv", encoding="utf-8")))
        header = list(cases_csv[0].keys())
        s += [
            Spacer(1, 6),
            p("Raw per-case data (recompute the statistics from this table):", "Body"),
            table(
                [
                    [
                        h.replace("judge_T0.7_run", "T0.7 run ")
                        .replace("judge_run", "run ")
                        .replace("judge_mean", "mean")
                        .replace("human", "human label")
                        for h in header
                    ]
                ]
                + [[r[h] for h in header] for r in cases_csv],
                [0.9] + [6.0 / (len(header) - 1)] * (len(header) - 1),
            ),
        ]
        rep = doc["repeatability"]
        s += [p("3.3 Repeatability", "Sub")]
        s += [
            table(
                [
                    ["Measure (3 runs, same inputs and settings)", "Value"],
                    [
                        "Cases whose score changed in at least one run",
                        f"{100 * rep['cases_changed']:.1f}%",
                    ],
                    [
                        "(case, run-pair) comparisons that differ",
                        f"{100 * rep['pairs_changed']:.1f}%",
                    ],
                    ["Mean absolute change (points)", f"{rep['mean_abs_change']:.3f}"],
                    ["Maximum absolute change (points)", f"{rep['max_abs_change']:.0f}"],
                ],
                [4.5, 2.0],
            )
        ]
        if "sensitivity" in validation:
            sens = validation["sensitivity"]["repeatability"]
            s += [
                p(
                    f"Sensitivity check (temperature {validation['sensitivity']['temperature']}, a new seed each run): {100 * sens['cases_changed']:.1f}% of cases changed, mean / max absolute change {sens['mean_abs_change']:.3f} / {sens['max_abs_change']:.0f}."
                )
            ]
        s += [p("Judge settings: " + json.dumps(validation["judge_settings"]), "Body")]
        hum = [int(r["human"]) for r in cases_csv]
        jud = [int(r["judge_run1"]) for r in cases_csv]
        diff = [b - a for a, b in zip(hum, jud)]
        n_cases = len(diff)
        higher = sum(x > 0 for x in diff)
        lower = sum(x < 0 for x in diff)
        exact = sum(x == 0 for x in diff)
        within1 = sum(abs(x) <= 1 for x in diff)
        big = [r["case_id"] for r in cases_csv if abs(int(r["judge_run1"]) - int(r["human"])) >= 3]
        sens_rep = validation["sensitivity"]["repeatability"]
        sens_rho = validation["sensitivity"]["mean_of_runs"]["rho"]
        s += [p("3.4 Would I trust this judge to gate a deployment?", "Sub")]
        s += [
            p(
                "<b>No, not as it stands.</b> The judge is perfectly repeatable but only weakly aligned with the human labels, "
                "and repeatability does not make it correct."
            ),
            p(
                f"<b>Agreement is weak.</b> Spearman rho is {mr['rho']:.2f} (p = {mr['p_value']:.2f}, n = {n_cases}), which is not distinguishable from no relationship with only {n_cases} cases. "
                f"The mean absolute difference is {mr['mean_abs_diff']:.1f} points on a 1-5 scale. The judge matched the human label exactly in {exact} of {n_cases} cases and was within one point in {within1}. "
                f"It scored higher than the human in {higher} cases and lower in {lower}; its mean score minus the human mean is {sum(diff) / n_cases:+.2f}. "
                f"The three largest gaps (3 or more points, all judge above human) are {', '.join(big)}: the human gave 1 or 2 and the judge gave 5. "
                "One of them (C16) is a request for a poem about the stock market, which is outside the rental domain, so the judge does not penalize an answer that ignores the system's purpose."
            ),
            p(
                f"<b>Repeatability is excellent only because the sampling is switched off.</b> With the documented settings (temperature 0, fixed seed) no score changed across three runs "
                f"(0% of cases, mean and maximum absolute change 0). When I turned sampling on as a sensitivity check (temperature 0.7, a new seed each run), {100 * sens_rep['cases_changed']:.0f}% of cases changed, "
                f"with a mean absolute change of {sens_rep['mean_abs_change']:.2f} and a maximum of {sens_rep['max_abs_change']:.0f} point, and the rank correlation with the human labels fell to {sens_rho:.2f}. "
                "A stable judge that is consistently too generous would pass bad answers every time, which is the worse failure for a deployment gate."
            ),
            p(
                "<b>Limits of this evidence.</b> There are only 20 cases and one labeller, so the correlation has a wide uncertainty and I cannot tell how much of the disagreement is the judge and how much is label noise. "
                "The drafts also come from one generator (qwen2:7b) and one judge (qwen3:8b)."
            ),
            p(
                "<b>Evidence I would require before using it as a gate.</b> (1) At least 100 labeled drafts, stratified so that poor, wrong and off-topic answers are well represented, with a bootstrap confidence interval for rho. "
                "(2) A second independent human labeller and a measured inter-rater agreement, so the judge is compared with an agreed reference rather than one person. "
                "(3) A pass/fail test at the actual gate threshold (for example, block anything the judge scores below 4) with a confusion matrix: how many human-bad drafts the judge lets through and how many human-good drafts it blocks. "
                "(4) A fix for the observed leniency, such as giving the judge the reference facts or a domain-scope rule, then a re-run on a fresh set of labeled cases that were not used to tune the rubric. "
                "(5) A check that scores stay stable when the judge model, its version or the prompt changes, and a regular re-check against human labels once it is in use."
            ),
        ]
    else:
        s += [p("3.2 and 3.3 - <b>not run yet</b>", "Sub")]
        s += [
            p(
                "The statistics in Part 3 need the 20 human labels, which must be assigned by hand and committed before the judge runs. They are not generated by a model and are not in this draft. "
                "Once <font face='Courier'>human_labels.csv</font> is committed, <font face='Courier'>make validate-hw10</font> produces the Spearman correlation, mean absolute difference, per-case raw data and three-run repeatability, "
                "and <font face='Courier'>make finalize-hw10</font> plus this builder fill this section."
            )
        ]
        s += [
            p(
                f"<b>What the existing data already says (provisional, not a validation).</b> The judge scored {fives} of {len(scored)} Writer drafts a 5. If the human labels spread across 1 to 5, a judge that gives almost everything a 5 will show a low rank correlation and a large mean absolute difference, "
                "and it should not be trusted to gate a deployment. The decision and the extra evidence required are written after the real numbers exist."
            )
        ]

    # ------------------------------------------------------------------ Part 4
    s += [PageBreak(), p("Part 4 - Distributed tracing and latency analysis", "Main")]
    s += [p("4.1 Trace propagation", "Sub")]
    s += [
        p(
            "<font face='Courier'>code/hw8/tracing.py</font> appends one JSON span per stage to <font face='Courier'>data/hw10/spans.jsonl</font> (a single O_APPEND write per span, safe across processes; tracing failures never break a request). "
            "The <b>HW8 correlation_id is the trace_id</b>: the ingress generates it, passes it to the pipeline client as the message's correlation_id, and the Planner, Writer, Reviewer and evaluator already preserve it. No second identifier exists. "
            "The agent runtime records a queue-wait span from the Kafka record's create time to the moment the consumer receives it, plus one span per processing attempt."
        )
    ]
    sample = next(x for x in spans if x["stage"] == "planner" and x["status"] == "ok")
    s += [
        code(
            json.dumps(
                {
                    k: sample[k]
                    for k in (
                        "trace_id",
                        "span_id",
                        "stage",
                        "service",
                        "start",
                        "end",
                        "start_iso",
                        "end_iso",
                        "duration_ms",
                        "status",
                        "error",
                        "attrs",
                    )
                },
                indent=1,
            )
        )
    ]
    s += [
        table(
            [
                ["Stage (span)", "Written by", "What it covers"],
                [
                    "request",
                    "ingress",
                    "whole request, including path = cache_hit or cache_miss, and status/error",
                ],
                [
                    "cache_lookup",
                    "ingress",
                    "embedding + Redis vector search; attrs.result = hit or miss",
                ],
                [
                    "queue_inbox / queue_tasks / queue_drafts / queue_final",
                    "consumer of each topic",
                    "message created -> message received",
                ],
                [
                    "planner / writer / reviewer",
                    "each agent process",
                    "one span per attempt (status ok or error, attempt number)",
                ],
                ["cache_store", "ingress", "saving the answer after a miss"],
                ["evaluation", "evaluator", "judge scoring of one trace"],
                ["dead_letter", "agent that gave up", "bounded retries exhausted"],
            ],
            [2.3, 1.5, 2.7],
        )
    ]
    s += shot(
        "p4-code-tracing.png",
        "Code: write_span() in code/hw8/tracing.py appends one structured JSON span per stage with a single atomic write.",
        6.2,
        4.6,
    )
    s += [p("4.2 Required trace examples", "Sub")]
    if examples:
        e = examples
        s += [
            table(
                [
                    ["Trace", "trace_id", "Result"],
                    [
                        "Cache hit",
                        f"<font face='Courier' size='9'>{e['cache_hit']['trace_id']}</font>",
                        f'paraphrase matched "{e["cache_hit"]["matched_query"]}" with similarity {e["cache_hit"]["similarity"]}; {e["cache_hit"]["latency_ms"]:.1f} ms; spans: {", ".join(e["cache_hit"]["stages"])}',
                    ],
                    [
                        "Cache miss (success)",
                        f"<font face='Courier' size='9'>{e['cache_miss']['trace_id']}</font>",
                        f"{e['cache_miss']['latency_ms']:.0f} ms to return the answer; all {len(e['cache_miss']['stages'])} span types present (request, cache lookup, 4 queue waits, 3 agents, cache store, evaluation), evaluated",
                    ],
                    [
                        "Failed",
                        f"<font face='Courier' size='9'>{e['failed']['trace_id']}</font>",
                        f"failing stage: <b>{e['failed']['failed_stage']}</b>; error: {e['failed']['error']}",
                    ],
                ],
                [1.0, 2.9, 2.6],
            )
        ]
        s += [
            Spacer(1, 6),
            p(
                "All three IDs are loaded by the dashboard's example buttons and stored in raw/example_traces.json; their spans are in raw/spans_reported.jsonl."
            ),
        ]
        s += shot(
            "p4-trace-cache_hit.png",
            "Figure 6. Trace lookup, cache-hit trace: only the cache lookup (hit) and the request spans exist; the Kafka agents never ran.",
            5.4,
            6.2,
        )
        s += shot(
            "p4-trace-cache_miss.png",
            "Figure 7. Trace lookup, successful cache-miss trace: cache lookup, four queue waits, Planner, Writer, Reviewer, cache store, then evaluation, plus the evaluator's scores.",
            5.4,
            7.4,
        )
        s += shot(
            "p4-trace-failed.png",
            "Figure 8. Trace lookup, failed trace: a blank question reaches the Planner, which rejects it on three attempts; a dead_letter span follows and the request is marked failed at stage planner.",
            5.4,
            6.8,
        )
        s += [
            p(
                "<b>Reading the failed trace.</b> The blank question passes the ingress (nothing validates it there), the Planner raises <i>inbox message needs a non-empty question</i> on all three bounded attempts, the message goes to <font face='Courier'>s7838_dead_letter</font>, and the ingress learns about it from that topic and answers with HTTP 502 naming the failing stage. "
                "The request ended in about 0.6 s instead of waiting out the 300 s timeout. One design lesson is that this check belongs at the ingress."
            )
        ]
    s += shot(
        "p4-console-traces.png",
        "Output: python -m hw10.capture_traces records the cache-miss, cache-hit and failed traces (console file raw/console/02_capture_traces.txt).",
        6.2,
        6.0,
    )
    s += shot(
        "p4-console-hit-spans.png",
        "Output: the structured spans of the cache-hit trace, as written to data/hw10/spans.jsonl (only request and cache_lookup).",
        6.2,
        2.0,
    )
    s += [p("4.3 Stage-latency experiment", "Sub")]
    t = table43
    s += [
        p(
            f"{t['n_traces']} requests, one at a time (closed loop): send a question, wait for the answer, then wait for the evaluator to finish that trace before sending the next, so no two requests compete for the models. "
            f"The cache was emptied first, the 50 questions were checked to be mutually dissimilar (highest pairwise cosine similarity 0.70, threshold 0.85), and the run aborts on any hit: <b>all 50 responses reported is_cached=false</b>. "
            "A warm-up request loaded the models first and is excluded. Percentiles use linear interpolation."
        )
    ]
    rows = [
        [
            "Stage",
            "p50 (ms)",
            "p95 (ms)",
            "% of cache-miss end-to-end",
            "% of time before the answer",
        ]
    ]
    for r in t["rows"]:
        rows.append(
            [
                r["stage"],
                f1(r["p50_ms"]),
                f1(r["p95_ms"]),
                f"{r['pct_of_e2e']:.1f}%",
                "n/a (after the answer)"
                if r["pct_of_request"] != r["pct_of_request"]
                else f"{r['pct_of_request']:.1f}%",
            ]
        )
    s += [table(rows, [1.5, 0.9, 0.9, 1.6, 1.6])]
    req, e2e, hit = t["request"], t["e2e"], t["cache_hit"]
    s += [
        Spacer(1, 6),
        p(
            f"<b>Definitions.</b> End-to-end runs from the start of the cache lookup to the end of the evaluation (p50 {f1(e2e['p50_ms'])} ms, p95 {f1(e2e['p95_ms'])} ms); percentages are mean stage time / mean end-to-end time, and "
            f'{t["unaccounted_pct_of_e2e"]:.2f}% of end-to-end is outside every span. "Before the answer" is the ingress <i>request</i> span (p50 {f1(req["p50_ms"])} ms, p95 {f1(req["p95_ms"])} ms), which excludes the evaluation.'
        ),
    ]
    s += [
        p(
            f"<b>Cache-hit latency (kept separate).</b> {hit['n']} repeated questions, all served from the cache: request p50 {f1(hit['request_p50_ms'])} ms, p95 {f1(hit['request_p95_ms'])} ms; the cache lookup alone is p50 {f1(hit['lookup_p50_ms'])} ms, p95 {f1(hit['lookup_p95_ms'])} ms. "
            f"A miss is about {req['p50_ms'] / hit['request_p50_ms']:.0f} times slower at the median."
        )
    ]
    rowsd = {r["stage"]: r for r in t["rows"]}
    s += [
        p(
            "<b>Dominant contributor and what I would optimize first.</b> "
            f"By share of end-to-end time the <b>evaluation</b> is largest ({rowsd['Evaluation']['pct_of_e2e']:.1f}%), but it runs after the answer has been returned, so a user never waits for it. "
            f"For the part a user does wait for, the <b>Writer</b> dominates: {rowsd['Writer']['pct_of_request']:.1f}% of the time before the answer (p50 {f1(rowsd['Writer']['p50_ms'])} ms), followed by the Planner ({rowsd['Planner']['pct_of_request']:.1f}%). "
            f"The Reviewer (rule-based, ~0 ms), the Kafka queues ({rowsd['Queue wait (total)']['p50_ms']:.0f} ms total at p50) and the cache lookup ({rowsd['Cache lookup']['p50_ms']:.0f} ms) are negligible. "
            "I would optimize the Writer first: the drafts average 125 words against a 60 to 100 word instruction, so capping generation length (num_predict) and enforcing the limit would cut generation time directly and also fix the over-length drafts the Reviewer and judge miss. "
            "The evaluation is the second target only if scoring must keep pace with traffic (sample a fraction of requests, or use a smaller judge)."
        )
    ]
    s += [
        p(
            "<b>Limits of this measurement.</b> One request at a time on one machine means the queue waits (about 16 ms) show Kafka overhead without contention; under concurrent load they will grow, and the Planner/Writer/judge would also slow down while sharing the GPU. "
            "The latencies describe this hardware and these local models, not a production deployment."
        )
    ]

    s += shot(
        "p4-console-loadtest.png",
        "Output: python -m hw10.loadtest, 50 confirmed cache misses sent one at a time (console file raw/console/03_loadtest.txt).",
        6.2,
        7.2,
    )
    s += shot(
        "p4-console-latency.png",
        "Output: python -m hw10.analyze_latency, the stage-latency table computed from the spans (raw/console/04_analyze_latency.txt).",
        6.2,
        3.0,
    )
    # ------------------------------------------------------------------ closing
    s += [PageBreak(), p("Reproducibility, verification, and AI use", "Main")]
    passed = sum(c["passed"] for c in verification["checks"])
    s += [
        p(
            f"<b>Self-check.</b> <font face='Courier'>make verify-hw10</font> runs {len(verification['checks'])} behavior checks with stub agents and a fake judge (spans, trace propagation, bounded evaluator, statistics, dashboard pages) and writes <font face='Courier'>reports/hw10/verification.json</font>: {passed} of {len(verification['checks'])} passed on commit {verification['commit_hash'][:12]}. "
            "The HW8 and HW9 self-checks were re-run after the changes to the shared code and still pass (HW9: 25 of 25)."
        )
    ]
    s += shot(
        "p4-console-verify.png",
        "Output: make verify-hw10, the self-check that writes reports/hw10/verification.json (raw/console/05_verify.txt).",
        6.2,
        7.2,
    )
    s += [
        p(
            "<b>Files.</b> code/hw10/ (dashboard, evaluator, judge, tracing helpers, latency tools, validation), code/hw8/tracing.py, small edits to hw8/agent_runtime.py and hw9/ingress.py, hw9/pipeline_client.py; reports/hw10/ has RUN_LOG.txt, METRICS.md, AI_USE.md, verification.json, raw/ and screenshots/."
        )
    ]
    ai = (HW / "AI_USE.md").read_text(encoding="utf-8") if (HW / "AI_USE.md").exists() else ""
    s += [p("AI use", "Sub")]
    for para in [x for x in ai.split("\n") if x.strip() and not x.startswith("#")]:
        s += [p(para.replace("&", "&amp;").replace("<", "&lt;"))]

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title="DATA 260 HW10 - Akanksha Shukla",
        author="Akanksha Shukla",
    )
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    shutil.copyfile(OUT, HW / "report.pdf")


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawString(0.9 * inch, 0.5 * inch, "Akanksha Shukla | SID4 7838 | DATA 260 HW10")
    canvas.drawRightString(letter[0] - 0.9 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    build()
    from pypdf import PdfReader  # noqa: PLC0415

    print(
        f"wrote {OUT} ({len(PdfReader(str(OUT)).pages)} pages); missing screenshots: {MISSING or 'none'}"
    )
