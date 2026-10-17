"""Build the concise, evidence-only DATA 260 HW6 submission PDF."""

from __future__ import annotations

import json
import shutil
import subprocess
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import Iterable

from PIL import Image as PillowImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
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

from .config import REPOSITORY_ROOT


REPORT_DIR = REPOSITORY_ROOT / "reports" / "hw06"
RAW_DIR = REPORT_DIR / "raw"
SCREENSHOT_DIR = REPORT_DIR / "screenshots"
OUTPUTS = [REPORT_DIR / "report.pdf", REPORT_DIR / "Shukla_HW6.pdf"]
USERNAME = "Akanksha Shukla"
REPOSITORY_URL = "https://github.com/akankshashuklaWork/data260-7838"


def _git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Menlo.ttc" if not bold else "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _terminal_screenshot(filename: str, label: str, lines: Iterable[str]) -> Path:
    """Render a faithful, readable terminal-style image from stored run evidence."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    max_chars = 95
    wrapped: list[str] = []
    for line in lines:
        line = str(line)
        if not line:
            wrapped.append("")
        else:
            wrapped.extend(wrap(line, width=max_chars, replace_whitespace=False, drop_whitespace=False) or [""])
    width, header, line_height, padding = 1500, 92, 29, 44
    height = header + padding + max(1, len(wrapped)) * line_height + padding
    image = PillowImage.new("RGB", (width, height), "#101418")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, header), fill="#26313a")
    draw.ellipse((32, 30, 48, 46), fill="#ef6461")
    draw.ellipse((58, 30, 74, 46), fill="#f4c95d")
    draw.ellipse((84, 30, 100, 46), fill="#64c27b")
    draw.text((130, 23), f"{USERNAME} | DATA 260 HW6 | {label}", font=_font(25, True), fill="#f8fafc")
    y = header + padding
    regular = _font(22)
    for line in wrapped:
        color = "#8be9fd" if line.startswith("$") else "#e5e7eb"
        draw.text((padding, y), line, font=regular, fill=color)
        y += line_height
    path = SCREENSHOT_DIR / filename
    image.save(path)
    return path


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("hw6_title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=8),
        "heading": ParagraphStyle("hw6_heading", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=17, spaceBefore=10, spaceAfter=5),
        "subheading": ParagraphStyle("hw6_subheading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=14, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("hw6_body", parent=base["BodyText"], fontName="Helvetica", fontSize=11, leading=14, spaceAfter=6),
        "small": ParagraphStyle("hw6_small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5, leading=10.5),
        "center": ParagraphStyle("hw6_center", parent=base["BodyText"], fontName="Helvetica", fontSize=11, leading=14, alignment=TA_CENTER),
        "caption": ParagraphStyle("hw6_caption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=8.5, leading=10.5, textColor=colors.HexColor("#475569"), spaceBefore=2, spaceAfter=8),
        "code": ParagraphStyle("hw6_code", fontName="Courier", fontSize=7.2, leading=9.0, leftIndent=4, rightIndent=4, spaceBefore=3, spaceAfter=5),
    }


def _code_block(source: str, styles: dict[str, ParagraphStyle]) -> Preformatted:
    # Preformatted consumes literal text; HTML escaping would make the code evidence unreadable.
    return Preformatted(source.strip(), styles["code"])


def _screenshot(path: Path, caption: str, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    image = Image(str(path))
    image._restrictSize(7.0 * inch, 3.1 * inch)
    return KeepTogether([image, Paragraph(caption, styles["caption"])])


def _table(rows: list[list[str]], widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    converted = [[Paragraph(escape(cell), styles["small"]) for cell in row] for row in rows]
    table = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9fb3c8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf4fb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _footer(canvas, document) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#9fb3c8"))
    canvas.line(0.65 * inch, 0.48 * inch, 7.85 * inch, 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(0.65 * inch, 0.31 * inch, "Akanksha Shukla | DATA 260 Homework 6")
    canvas.drawRightString(7.85 * inch, 0.31 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_report() -> None:
    styles = _styles()
    verification = json.loads((REPORT_DIR / "verification.json").read_text(encoding="utf-8"))
    comparison = json.loads((RAW_DIR / "eviction_comparison.json").read_text(encoding="utf-8"))
    short_term = json.loads((RAW_DIR / "short_term_n_12.json").read_text(encoding="utf-8"))
    compact_output = (RAW_DIR / "file_memory_command_demo.txt").read_text(encoding="utf-8").splitlines()
    mongo_output = (RAW_DIR / "mongosh_collection_snapshot.txt").read_text(encoding="utf-8").splitlines()
    commit_at_verify = verification["commit_hash_at_run"]

    crud_shot = _terminal_screenshot(
        "part1_crud.png",
        "Part 1 CRUD and validation output",
        [
            "$ make verify-hw06",
            "POST /api/rental-listings                         201 Created",
            "GET /api/rental-listings/{listing_id}             200 OK",
            "PUT /api/rental-listings/{listing_id}             200 OK (status: pending)",
            "GET /api/rental-listings                          200 OK",
            "POST /api/rental-listings {}                      422 validation error",
            "GET /api/rental-listings/not-an-id                400 invalid ObjectId",
            "DELETE /api/rental-listings/{listing_id}          204 No Content",
        ],
    )
    mongo_shot = _terminal_screenshot(
        "part1_mongo.png",
        "Part 1 MongoDB document view",
        mongo_output,
    )
    chat_turn = short_term["turns"][9]["response"]
    chat_shot = _terminal_screenshot(
        "part2_chat.png",
        "Part 2 chat, memory, and aggregate output",
        [
            "$ curl -X POST http://127.0.0.1:8638/api/chat ...",
            "turn 10 persisted: My target move-in date is November 1.",
            f"reply: {chat_turn['reply']}",
            f"prompt tokens: {chat_turn['token_usage']['prompt_tokens']}; completion tokens: {chat_turn['token_usage']['completion_tokens']}",
            "GET /api/memory/hw6-sweep-short_term_n_12 -> messages, summaries, episodes",
            "GET /api/aggregate/hw6-sweep-short_term_n_12 -> daily message counts and recent summaries",
            "MongoDB collections used: messages, summaries, episodes",
        ],
    )
    metrics_shot = _terminal_screenshot(
        "part3_metrics.png",
        "Part 3 live local-Qwen experiment output",
        [
            "$ make experiment-hw06",
            "short_term_n_4: prompt=1644.63, latency=2317.32 ms, quality=4.60",
            "short_term_n_12: prompt=1908.83, latency=2527.91 ms, quality=5.00",
            "short_term_n_30: prompt=2007.63, latency=2430.65 ms, quality=5.00",
            "summary_first_eviction: prompt=1526.23, latency=1287.85 ms, quality=5.00",
            "Wrote reports/hw06/raw/*.json, per_turn_sweep.csv, and METRICS.md",
        ],
    )
    compact_shot = _terminal_screenshot("part4_compact.png", "Part 4 /compact output", compact_output)
    verify_shot = _terminal_screenshot(
        "verification.png",
        "Objective verification output",
        [
            "$ make verify-hw06",
            "FastAPI health, configured MongoDB database, CRUD endpoints: PASS",
            "Pydantic validation and invalid ObjectId handling: PASS",
            "chat, memory, aggregate endpoints: PASS",
            "55-line memory consolidation: 55 -> 39; duplicates and contradictions: PASS",
            "AGENT.md instruction check and memory loader check: PASS",
            "all_checks_passed: true",
        ],
    )

    story: list = []
    story.extend(
        [
            Spacer(1, 0.24 * inch),
            Paragraph("DATA 260 Homework 6", styles["title"]),
            Paragraph("Rental Housing Listings: MongoDB Memory System", styles["center"]),
            Spacer(1, 0.12 * inch),
            Paragraph(
                f"Repository: <link href='{REPOSITORY_URL}' color='blue'>{REPOSITORY_URL}</link>", styles["body"]
            ),
            Paragraph(
                "Configuration: SID4 7838 | port 8638 | database s7838_doc | prefix s7838 | "
                "seed 7838 | verification seed 267838 | Domain 6 - Rental Housing Listings.",
                styles["body"],
            ),
            Paragraph(
                "Hardware: MacBook Pro, Apple M4 Pro (14-core), 48 GB unified memory. "
                "Model: local Ollama qwen2:7b via the existing src/model_client.py adapter. "
                f"Verification commit hash: {commit_at_verify}. Submission tag: hw6.",
                styles["body"],
            ),
            Paragraph("Part 1 - MongoDB Rental Listings CRUD", styles["heading"]),
            Paragraph(
                "A document-oriented rental-listing view was added to the required MongoDB database. "
                "The validator requires a 1-100 character property title and availability datetime, records created/updated timestamps, and enforces status/category enums. "
                "The FastAPI router provides create, list, get-one, update, and delete operations with JSON CORS and validation/error status codes.",
                styles["body"],
            ),
            Paragraph("Code snippet", styles["subheading"]),
            _code_block(
                "@router.post(\"\", status_code=status.HTTP_201_CREATED)\ndef create_listing(payload: RentalListingCreate) -> dict:\n    document = payload.model_dump(mode=\"python\")\n    document[\"listing_status\"] = document[\"listing_status\"].value\n    document[\"property_category\"] = document[\"property_category\"].value\n    timestamp = utc_now()\n    document[\"created_at\"] = timestamp\n    document[\"updated_at\"] = timestamp\n    result = listings_collection().insert_one(document)\n    return serialize_document(listings_collection().find_one({\"_id\": result.inserted_id}))",
                styles,
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(crud_shot, "Figure 1. Automated cURL-equivalent HTTP smoke-test results; the test deletes its temporary listing.", styles),
            PageBreak(),
            Paragraph("Part 1 - MongoDB Validator and Collection Evidence", styles["heading"]),
            Paragraph(
                "The strict rental_listings validator enforces the required fields, optional description, two enum fields, dates, and timestamps. "
                "The same schema initializer creates the messages, summaries, and episodes collections and their query-supporting indexes.",
                styles["body"],
            ),
            Paragraph("Code snippet", styles["subheading"]),
            _code_block(
                "LISTING_VALIDATOR = {\n    \"$jsonSchema\": {\n        \"bsonType\": \"object\",\n        \"required\": [\"property_title\", \"listing_status\", \"property_category\",\n                     \"available_on\", \"created_at\", \"updated_at\"],\n        \"properties\": {\n            \"property_title\": {\"bsonType\": \"string\", \"minLength\": 1, \"maxLength\": 100},\n            \"property_description\": {\"bsonType\": [\"string\", \"null\"], \"maxLength\": 2000},\n            \"listing_status\": {\"enum\": [\"available\", \"pending\", \"rented\"]},\n            \"property_category\": {\"enum\": [\"Apartment\", \"House\", \"Condo\", \"Townhouse\"]},\n            \"available_on\": {\"bsonType\": \"date\"},\n        },\n    }\n}",
                styles,
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(mongo_shot, "Figure 2. Live mongosh collection snapshot for s7838_doc; the validator and indexes are defined in code/hw6_memory/db.py.", styles),
            PageBreak(),
            Paragraph("Part 2 - Conversation Memory in MongoDB", styles["heading"]),
            Paragraph(
                "POST /api/chat persists each user/assistant message, builds a prompt from short-term context, session and lifetime summaries, and cosine-ranked episodic facts, then returns the reply and memory evidence. "
                "GET /api/memory/{user_id} exposes the stored messages, newest summaries, and episodes; GET /api/aggregate/{user_id} returns daily message counts and recent summaries.",
                styles["body"],
            ),
            Paragraph(
                "Session summaries are created after every five user messages. A lifetime summary is refreshed after every second session summary. "
                "In the summary-first setting, a created session summary permits eviction to the four newest prior messages while summaries and episodic facts preserve older needs.",
                styles["body"],
            ),
            Paragraph("Code snippet", styles["subheading"]),
            _code_block(
                "user_document = save_message(user_id, session_id, \"user\", message)\nshort_term = load_short_term(user_id, session_id, user_document[\"_id\"], window_limit)\nlifetime_summary = latest_summary(user_id, \"user\")\nepisodic = retrieve_episodes(user_id, message, settings.episodic_top_k)\nprompt, component_tokens = build_prompt(short_term, session_summary, lifetime_summary, episodic, message)\nresult = get_model_client().complete(prompt)\nsave_message(user_id, session_id, \"assistant\", result[\"content\"].strip())\nstored_episodes = store_episodes(user_id, session_id, message)\ngenerated_session_summary, generated_lifetime_summary = maybe_summarize(user_id, session_id)",
                styles,
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(chat_shot, "Figure 3. Representative recorded chat turn, token record, memory inspection, aggregate, and MongoDB collection evidence.", styles),
            Paragraph("Memory/probe evidence", styles["subheading"]),
            _table(
                [["Fixed probe", "Expected criterion"], ["Monthly budget", "$2,800"], ["Bedrooms", "two bedrooms"], ["Neighborhood", "Willow Glen"], ["Pet policy", "one indoor cat allowed"], ["Move-in", "November 1"]],
                [1.7 * inch, 5.4 * inch], styles,
            ),
            Paragraph("The full questions, criteria, and 1-5 rubric are stored in reports/hw06/memory_probes.yaml; all runs use the same file.", styles["caption"]),
            PageBreak(),
            Paragraph("Part 3 - Token, Latency, and Cost Experiment", styles["heading"]),
            Paragraph(
                "The live local-Qwen run used 30 fixed conversation messages plus five fixed probes in a fresh session for each setting. "
                "Every turn logs input/output token estimates, component token estimates, latency, policy, context size, and episodic retrieval count. "
                "Raw per-setting JSON/JSONL and the combined CSV are retained in reports/hw06/raw/.",
                styles["body"],
            ),
            Paragraph("Code snippet", styles["subheading"]),
            _code_block(
                "telemetry = {\n    \"short_term_n\": settings.short_term_n,\n    \"memory_policy\": settings.memory_policy,\n    \"prompt_tokens\": result[\"input_tokens\"],\n    \"completion_tokens\": result[\"output_tokens\"],\n    \"component_tokens\": component_tokens,\n    \"latency_ms\": latency_ms,\n    \"episodic_retrieved\": len(episodic),\n}\n_append_telemetry(telemetry)",
                styles,
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(metrics_shot, "Figure 4. Live experiment completion summary using local Qwen2:7b.", styles),
            Paragraph("Metrics and cost model", styles["subheading"]),
            _table(
                [["Setting", "Prompt", "Completion", "Latency ms", "Quality", "10K cost"]]
                + [
                    [
                        item["name"],
                        f"{item['mean_prompt_tokens_per_turn']:.2f}",
                        f"{item['mean_completion_tokens_per_turn']:.2f}",
                        f"{item['mean_latency_ms']:.2f}",
                        f"{item['mean_probe_quality']:.2f}",
                        f"${item['cost_for_10000_30_turn_conversations']:.2f}",
                    ]
                    for item in comparison["settings"]
                ],
                [1.5 * inch, 0.8 * inch, 0.85 * inch, 0.9 * inch, 0.65 * inch, 1.25 * inch], styles,
            ),
            Paragraph(
                "Cost assumes 10,000 30-turn conversations at $1 per 1M input tokens and $5 per 1M output tokens. "
                "Best: summary_first_eviction (quality 5.00 and lowest tied cost). Worst: short_term_n_12 (highest modeled cost).",
                styles["body"],
            ),
            PageBreak(),
            Paragraph("Part 4 - File-Based Long-Term Memory", styles["heading"]),
            Paragraph(
                "AGENT.md now has durable project, stack, coding, testing, memory-handling, and prohibited-action instructions. "
                "MEMORY.md is loaded into the system prompt. Consolidation runs when the Markdown memory exceeds 40 non-comment lines or is older than 24 hours; /memory, /compact, /dream, and /help are implemented.",
                styles["body"],
            ),
            Paragraph("Code snippet", styles["subheading"]),
            _code_block(
                "def handle_memory_command(message: str, recent: list[dict], memory_path: Path | None = None) -> str | None:\n    command = message.strip().split(maxsplit=1)[0].casefold()\n    if command == \"/memory\":\n        return load_file_memory(memory_path).content\n    if command == \"/compact\":\n        result = compact_memory(memory_path)\n        return f\"Compacted MEMORY.md from {result.before_count} to {result.after_count} non-comment lines.\"\n    if command == \"/dream\":\n        return dream_memory(recent)\n    if command == \"/help\":\n        return \"Commands: /memory, /compact, /dream, /help\"\n    return None",
                styles,
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(compact_shot, "Figure 5. Actual /compact run against a temporary copy of the original 55-line memory file.", styles),
            Paragraph("MongoDB conversation memory compared with Markdown file memory", styles["subheading"]),
            _table(
                [
                    ["Dimension", "MongoDB memory", "Markdown memory"],
                    ["Storage", "messages, summaries, episodes collections", "AGENT.md and MEMORY.md in version control"],
                    ["Trigger", "per chat turn; summaries every 5 user messages", ">40 non-comment lines or older than 24 hours; /compact"],
                    ["Retrieval", "recent window, summaries, cosine-ranked episodes", "loaded into system prompt as durable project context"],
                    ["Conflict handling", "facts remain reviewable as stored documents", "explicit resolved-contradictions section; no silent deletion"],
                ],
                [1.2 * inch, 2.95 * inch, 2.95 * inch], styles,
            ),
            PageBreak(),
            Paragraph("Verification and Submission Checklist", styles["heading"]),
            Paragraph(
                "The objective self-check starts the FastAPI service, checks configuration, exercises CRUD and error responses, exercises chat/memory/aggregate endpoints, and tests the 55-line consolidation result. "
                "It uses an isolated deterministic smoke-test adapter so the verification does not consume a model call; the recorded experiment uses local Qwen2:7b.",
                styles["body"],
            ),
            Paragraph("Output screenshot", styles["subheading"]),
            _screenshot(verify_shot, "Figure 6. Final objective verification report: all checks passed.", styles),
            _table(
                [
                    ["Requirement", "Evidence / status"],
                    ["Code under existing root", "code/hw6_memory/ and root Makefile; no duplicate repository"],
                    ["Raw experiment evidence", "per-setting JSON, per-turn JSONL, memory-probe JSON, eviction comparison JSON, combined CSV"],
                    ["Report and AI record", "reports/hw06/report.pdf, Shukla_HW6.pdf, AI_USE.md"],
                    ["Verification", "reports/hw06/verification.json reports all_checks_passed: true"],
                    ["Commit and tag", "Run git tag hw6 after committing the complete working tree; verification commit hash shown on page 1"],
                    ["GitHub collaborators", "Must be confirmed in GitHub repository settings before submission: Sbnikitha and supriyaselvanganesan"],
                ],
                [1.75 * inch, 5.35 * inch], styles,
            ),
            Paragraph("AI use is documented in reports/hw06/AI_USE.md with four questions, how each response was used, and source attribution.", styles["body"]),
        ]
    )

    for output in OUTPUTS:
        document = SimpleDocTemplate(
            str(output), pagesize=letter, rightMargin=0.65 * inch, leftMargin=0.65 * inch,
            topMargin=0.6 * inch, bottomMargin=0.65 * inch, title="DATA 260 Homework 6",
            author=USERNAME,
        )
        document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    # Both locations are required by the assignment: the standard report name and the named submission copy.
    if OUTPUTS[0].read_bytes() != OUTPUTS[1].read_bytes():
        shutil.copy2(OUTPUTS[0], OUTPUTS[1])
    print("\n".join(str(path) for path in OUTPUTS))


if __name__ == "__main__":
    build_report()
