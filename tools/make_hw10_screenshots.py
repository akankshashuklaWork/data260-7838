"""Render the HW10 code and console-output screenshots used in the report.

Code images are taken straight from the repository files (with their real line numbers) and console
images from the saved files in reports/hw10/raw/console/, so the pictures cannot drift from the
code or the recorded output. Headless Chrome does the rendering.

    python tools/make_hw10_screenshots.py
"""

from __future__ import annotations

import html
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports/hw10/raw"
OUT = ROOT / "reports/hw10/screenshots"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH = 1240
CHARS_PER_LINE = 148  # wrap estimate at 12.5 px monospace
LINE_PX = 19

# (file name, window title, repository file, first line, last line)
CODE = [
    (
        "p1-code-caching.png",
        "code/hw10/dashboard.py - cached loaders",
        "code/hw10/dashboard.py",
        37,
        82,
    ),
    ("p2-code-geval.png", "code/hw10/judge.py - GEval metric", "code/hw10/judge.py", 190, 232),
    (
        "p2-code-evaluator.png",
        "code/hw10/evaluator.py - join and score",
        "code/hw10/evaluator.py",
        50,
        104,
    ),
    (
        "p3-code-validation.png",
        "code/hw10/validate_judge.py - statistics",
        "code/hw10/validate_judge.py",
        81,
        99,
    ),
    ("p4-code-tracing.png", "code/hw8/tracing.py - span writer", "code/hw8/tracing.py", 56, 93),
]
# (file name, window title, saved console file)
CONSOLE = [
    ("p4-console-traces.png", "$ python -m hw10.capture_traces", "02_capture_traces.txt"),
    ("p4-console-loadtest.png", "$ python -m hw10.loadtest", "03_loadtest.txt"),
    ("p4-console-latency.png", "$ python -m hw10.analyze_latency", "04_analyze_latency.txt"),
    ("p3-console-validate.png", "$ make validate-hw10", "07_validate_judge.txt"),
    ("p4-console-verify.png", "$ python -m hw10.verify_hw10", "05_verify.txt"),
]


def page(title: str, body: str, lines: int) -> tuple[str, int]:
    height = 44 + 28 + lines * LINE_PX + 24
    doc = f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:#1e1f26}}
.bar{{height:44px;background:#2b2d38;color:#d7d9e0;font:600 15px -apple-system,Helvetica,Arial;
display:flex;align-items:center;padding:0 18px;border-bottom:1px solid #3a3d4a}}
.dots span{{display:inline-block;width:12px;height:12px;border-radius:6px;margin-right:7px}}
pre{{margin:0;padding:14px 18px 10px;color:#e6e8ee;font:12.5px/{LINE_PX}px Menlo,Monaco,monospace;
white-space:pre-wrap;word-break:break-all}}
.n{{color:#6b7083;user-select:none}}
</style><div class="bar"><div class="dots"><span style="background:#ff5f56"></span>
<span style="background:#ffbd2e"></span><span style="background:#27c93f"></span></div>
{html.escape(title)}</div><pre>{body}</pre>"""
    return doc, height


def render(name: str, doc: str, height: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "shot.html"
        src.write_text(doc, encoding="utf-8")
        cmd = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            f"--window-size={WIDTH},{height}",
            f"--screenshot={OUT / name}",
            src.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    print("wrote", OUT / name)


def wrapped(text_lines: list[str]) -> int:
    return sum(max(1, math.ceil(len(x) / CHARS_PER_LINE)) for x in text_lines)


def main() -> int:
    for name, title, rel, first, last in CODE:
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()[first - 1 : last]
        body = "\n".join(
            f'<span class="n">{i:>4}  </span>{html.escape(text)}'
            for i, text in enumerate(lines, first)
        )
        doc, height = page(
            title, body, wrapped([f"{i:>4}  {t}" for i, t in enumerate(lines, first)])
        )
        render(name, doc, height)

    for name, title, filename in CONSOLE:
        lines = (RAW / "console" / filename).read_text(encoding="utf-8").splitlines()
        doc, height = page(title, html.escape("\n".join(lines)), wrapped(lines))
        render(name, doc, height)

    # Evaluator output for the example cache-miss trace, and the span lines of the cache-hit trace.
    examples = json.loads((RAW / "example_traces.json").read_text(encoding="utf-8"))
    miss_id = examples["cache_miss"]["trace_id"]
    hit_id = examples["cache_hit"]["trace_id"]

    for line in (RAW / "eval_results_reported.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("trace_id") == miss_id:
            view = {
                "trace_id": record["trace_id"],
                "question": record.get("question"),
                "scores": record["scores"],
                "improvement": record["improvement"],
                "judge": record.get("judge"),
                "evaluation_ms": record.get("evaluation_ms"),
            }
            text = json.dumps(view, indent=2).splitlines()
            doc, height = page(
                "evaluator output (data/hw10/eval_results.jsonl) for the cache-miss trace",
                html.escape("\n".join(text)),
                wrapped(text),
            )
            render("p2-console-evaluation.png", doc, height)
            break
    else:
        print("no evaluation record for the example trace", file=sys.stderr)
        return 1

    spans = [
        json.dumps(
            {
                k: s[k]
                for k in (
                    "trace_id",
                    "stage",
                    "start_iso",
                    "end_iso",
                    "duration_ms",
                    "status",
                    "error",
                )
            }
        )
        for s in map(
            json.loads, (RAW / "spans_reported.jsonl").read_text(encoding="utf-8").splitlines()
        )
        if s.get("trace_id") == hit_id
    ]
    doc, height = page(
        "span lines of the cache-hit trace (data/hw10/spans.jsonl)",
        html.escape("\n".join(spans)),
        wrapped(spans),
    )
    render("p4-console-hit-spans.png", doc, height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
