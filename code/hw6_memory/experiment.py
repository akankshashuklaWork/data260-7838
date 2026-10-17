"""Run the fixed HW6 memory-size sweep and write raw data plus summary metrics."""

from __future__ import annotations

import json
import os
import statistics
import time
from csv import DictWriter
from pathlib import Path
from typing import Any

import yaml

from .config import REPOSITORY_ROOT, get_settings
from .db import ensure_database_schema, episodes_collection, messages_collection, summaries_collection
from .memory import run_chat
from .model_adapter import get_model_client


RAW_DIR = REPOSITORY_ROOT / "reports" / "hw06" / "raw"
PROBES_PATH = REPOSITORY_ROOT / "reports" / "hw06" / "memory_probes.yaml"
RUN_LOG_PATH = REPOSITORY_ROOT / "reports" / "hw06" / "RUN_LOG.txt"

CONVERSATION = [
    "I am looking for a rental in San Jose.",
    "My budget is $2,800 per month before utilities.",
    "I need two bedrooms because I work from home.",
    "Willow Glen is my preferred neighborhood.",
    "I need one parking space for a compact car.",
    "I have one indoor cat, so the unit must allow pets.",
    "I want in-unit laundry if possible.",
    "A quiet street matters because I have video meetings.",
    "I prefer natural light in the living room.",
    "My target move-in date is November 1.",
    "I can consider an apartment, condo, or townhouse.",
    "I prefer a twelve-month lease.",
    "A balcony would be nice but is not required.",
    "I need reliable internet service.",
    "I prefer a non-smoking building.",
    "I would like a grocery store within walking distance.",
    "I can attend viewings on weekends.",
    "I prefer email updates about listings.",
    "I need secure package delivery.",
    "I would like recently updated appliances.",
    "I can provide proof of income when applying.",
    "I want transparent utility costs.",
    "I want to avoid a long commute.",
    "An elevator would help for an upper-floor unit.",
    "I need a clear pet policy before applying.",
    "I can move within thirty days if the unit is right.",
    "Please remember that two bedrooms are required, not optional.",
    "Willow Glen remains my first-choice neighborhood.",
    "Please keep my $2,800 monthly budget in mind.",
    "Summarize my most important rental requirements in one sentence.",
]

SETTINGS = [
    {"name": "short_term_n_4", "short_term_n": 4, "memory_policy": "none"},
    {"name": "short_term_n_12", "short_term_n": 12, "memory_policy": "none"},
    {"name": "short_term_n_30", "short_term_n": 30, "memory_policy": "none"},
    {"name": "summary_first_eviction", "short_term_n": 12, "memory_policy": "summary_first_eviction"},
]


def _configure_setting(setting: dict[str, Any], telemetry_path: Path) -> None:
    """Switch the same chat service to the requested fresh-session setting."""
    os.environ["HW6_SHORT_TERM_N"] = str(setting["short_term_n"])
    os.environ["HW6_MEMORY_POLICY"] = setting["memory_policy"]
    os.environ["HW6_TELEMETRY_PATH"] = str(telemetry_path)
    get_settings.cache_clear()
    get_model_client.cache_clear()
    ensure_database_schema()


def _score_probe(answer: str, criteria: list[str]) -> int:
    normalized = answer.casefold()
    matches = sum(criterion.casefold() in normalized for criterion in criteria)
    if matches == len(criteria):
        return 5
    if matches:
        return 3
    return 1


def _read_probes() -> list[dict[str, Any]]:
    return yaml.safe_load(PROBES_PATH.read_text(encoding="utf-8"))["probes"]


def _log(message: str) -> None:
    print(message)
    with RUN_LOG_PATH.open("a", encoding="utf-8") as output:
        output.write(message + "\n")


def run_setting(setting: dict[str, Any]) -> dict[str, Any]:
    """Run exactly 30 fixed service turns in a fresh session, then score five fixed probes."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    telemetry_path = RAW_DIR / f"{setting['name']}_telemetry.jsonl"
    telemetry_path.unlink(missing_ok=True)
    _configure_setting(setting, telemetry_path)
    user_id = f"hw6-sweep-{setting['name']}"
    session_id = f"session-{setting['name']}"
    messages_collection().delete_many({"user_id": user_id})
    summaries_collection().delete_many({"user_id": user_id})
    episodes_collection().delete_many({"user_id": user_id})
    turns: list[dict[str, Any]] = []
    probe_results: list[dict[str, Any]] = []
    for index, message in enumerate(CONVERSATION, start=1):
        body = run_chat(user_id, session_id, message)
        turns.append({"turn": index, "message": message, "response": body})
    for probe in _read_probes():
        body = run_chat(user_id, session_id, probe["question"])
        score = _score_probe(body["reply"], probe["expected_answer_criteria"])
        probe_results.append({"probe_id": probe["id"], "question": probe["question"], "answer": body["reply"], "score": score})

    telemetry = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = {
        "setting": setting,
        "conversation_messages": CONVERSATION,
        "turns": turns,
        "probes": probe_results,
        "telemetry": telemetry,
        "mean_prompt_tokens_per_turn": statistics.mean(item["response"]["token_usage"]["prompt_tokens"] for item in turns),
        "mean_completion_tokens_per_turn": statistics.mean(item["response"]["token_usage"]["completion_tokens"] for item in turns),
        "mean_latency_ms": statistics.mean(item["response"]["token_usage"]["latency_ms"] for item in turns),
        "mean_probe_quality": statistics.mean(item["score"] for item in probe_results),
    }
    (RAW_DIR / f"{setting['name']}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _cost_for_10000_conversations(result: dict[str, Any]) -> float:
    input_tokens = result["mean_prompt_tokens_per_turn"] * 30 * 10_000
    output_tokens = result["mean_completion_tokens_per_turn"] * 30 * 10_000
    return input_tokens / 1_000_000 + output_tokens * 5 / 1_000_000


def write_metrics(results: list[dict[str, Any]]) -> None:
    ordered = sorted(results, key=lambda item: (-item["mean_probe_quality"], _cost_for_10000_conversations(item)))
    best = ordered[0]
    worst = max(results, key=lambda item: (_cost_for_10000_conversations(item), -item["mean_probe_quality"]))
    lines = [
        "# HW6 Memory Cost Metrics",
        "",
        "The 30-message conversation and five fixed probes were run in fresh sessions for each setting. Token counts use the HW1 adapter's documented four-characters-per-token estimate.",
        "",
        "| Setting | Mean prompt tokens/turn | Mean completion tokens/turn | Mean latency (ms) | Probe quality (1-5) | Estimated cost for 10,000 30-turn conversations |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result['setting']['name']} | {result['mean_prompt_tokens_per_turn']:.2f} | {result['mean_completion_tokens_per_turn']:.2f} | {result['mean_latency_ms']:.2f} | {result['mean_probe_quality']:.2f} | ${_cost_for_10000_conversations(result):.2f} |"
        )
    lines.extend(
        [
            "",
            f"Best setting: **{best['setting']['name']}**. It had the highest mean probe quality; cost breaks ties among equally accurate settings.",
            f"Worst setting: **{worst['setting']['name']}**. It had the highest modeled 10,000-conversation cost; probe quality breaks cost ties.",
            "",
            "The summary_first_eviction policy keeps the latest four prior messages in the short-term window after summaries are available. Older detail remains in session/lifetime summaries and episodic facts, reducing prompt tokens while preserving durable requirements.",
        ]
    )
    (REPOSITORY_ROOT / "reports" / "hw06" / "METRICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    comparison = {
        "settings": [
            {
                "name": result["setting"]["name"],
                "mean_prompt_tokens_per_turn": result["mean_prompt_tokens_per_turn"],
                "mean_completion_tokens_per_turn": result["mean_completion_tokens_per_turn"],
                "mean_latency_ms": result["mean_latency_ms"],
                "mean_probe_quality": result["mean_probe_quality"],
                "cost_for_10000_30_turn_conversations": _cost_for_10000_conversations(result),
            }
            for result in results
        ],
        "best_setting": best["setting"]["name"],
        "worst_setting": worst["setting"]["name"],
    }
    (RAW_DIR / "eviction_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    probe_scores = {
        "scoring_method": "A score of 5 requires every fixed criterion, 3 requires at least one criterion, and 1 means no criterion was found.",
        "results": [
            {"setting": result["setting"]["name"], "probes": result["probes"]}
            for result in results
        ],
    }
    (RAW_DIR / "memory_probe_scores.json").write_text(json.dumps(probe_scores, indent=2) + "\n", encoding="utf-8")

    # Keep one spreadsheet-friendly export of every measured turn (30 conversation turns
    # plus five fixed probes per setting) alongside the full JSON response evidence.
    with (RAW_DIR / "per_turn_sweep.csv").open("w", newline="", encoding="utf-8") as output:
        fields = [
            "setting", "request_number", "phase", "prompt_tokens", "completion_tokens",
            "latency_ms", "short_term_n", "memory_policy", "episodic_retrieved",
        ]
        writer = DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for result in results:
            telemetry = result["telemetry"]
            for index, item in enumerate(telemetry, start=1):
                writer.writerow(
                    {
                        "setting": result["setting"]["name"],
                        "request_number": index,
                        "phase": "conversation" if index <= 30 else "probe",
                        "prompt_tokens": item["prompt_tokens"],
                        "completion_tokens": item["completion_tokens"],
                        "latency_ms": item["latency_ms"],
                        "short_term_n": item["short_term_n"],
                        "memory_policy": item["memory_policy"],
                        "episodic_retrieved": item["episodic_retrieved"],
                    }
                )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the fixed HW6 memory experiment.")
    parser.add_argument("--setting", choices=[item["name"] for item in SETTINGS])
    parser.add_argument("--write-metrics-only", action="store_true")
    args = parser.parse_args()
    if args.write_metrics_only:
        results = [
            json.loads((RAW_DIR / f"{setting['name']}.json").read_text(encoding="utf-8"))
            for setting in SETTINGS
        ]
        write_metrics(results)
        print("Refreshed reports/hw06/METRICS.md and aggregate raw comparison files")
        return
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.setting in (None, "short_term_n_4"):
        RUN_LOG_PATH.write_text("DATA 260 Homework 6 Run Log\n", encoding="utf-8")
    _log(f"Akanksha Shukla | HW6 memory experiment started {started}")
    _log("Model: qwen2:7b via local Ollama through src/model_client.py")
    _log("Database: s7838_doc | Seed: 7838 | Verify seed: 267838")
    results = []
    selected_settings = [item for item in SETTINGS if args.setting is None or item["name"] == args.setting]
    for setting in selected_settings:
        _log(f"Running {setting['name']} with SHORT_TERM_N={setting['short_term_n']} and policy={setting['memory_policy']}")
        result = run_setting(setting)
        results.append(result)
        _log(
            f"Completed {setting['name']}: prompt={result['mean_prompt_tokens_per_turn']:.2f}, "
            f"latency={result['mean_latency_ms']:.2f} ms, quality={result['mean_probe_quality']:.2f}"
        )
    existing_results = []
    for setting in SETTINGS:
        result_path = RAW_DIR / f"{setting['name']}.json"
        if result_path.exists():
            existing_results.append(json.loads(result_path.read_text(encoding="utf-8")))
    if len(existing_results) == len(SETTINGS):
        write_metrics(existing_results)
        _log("Wrote reports/hw06/raw/*.json and reports/hw06/METRICS.md")


if __name__ == "__main__":
    main()
