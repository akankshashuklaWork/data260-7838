from pathlib import Path
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports/hw05"
SHOTS = HW / "screenshots"
OUT = HW / "Shukla_HW5.pdf"
COMMIT = "REPLACE_COMMIT"  # filled in by `--commit` argument below

import sys
if len(sys.argv) > 1:
    COMMIT = sys.argv[1]

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("Main", parent=styles["Heading2"], textColor=colors.black, fontName="Helvetica-Bold", fontSize=14, leading=17, spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle("Sub", parent=styles["Heading3"], textColor=colors.black, fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=8, spaceAfter=4))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=11, leading=14, spaceAfter=6))
styles.add(ParagraphStyle("Cap", parent=styles["BodyText"], fontSize=11, leading=14, spaceAfter=10, fontName="Helvetica-Bold"))
CODE = ParagraphStyle("Code", fontName="Courier", fontSize=8.5, leading=10.5, backColor=colors.whitesmoke, borderPadding=4, spaceAfter=10)


def p(t, s="Body"):
    return Paragraph(t, styles[s])


def code(t):
    import textwrap
    t = "\n".join(w for line in t.splitlines() for w in (textwrap.wrap(line, 105, subsequent_indent="    ") or [""]))
    return Preformatted(t, CODE)


def shot(name, caption, width=5.6):
    """Screenshot + caption together; skipped (and listed) if the file is missing."""
    f = SHOTS / name
    if not f.exists() and f.with_suffix(".jpg").exists():
        f = f.with_suffix(".jpg")
    if not f.exists():
        MISSING.append(name)
        return []
    w, h = ImageReader(str(f)).getSize()
    width = min(width, 6.0)
    height = width * h / w
    if height > 4.6:
        height = 4.6
        width = height * w / h
    return [KeepTogether([Image(str(f), width=width * inch, height=height * inch), p(caption, "Cap")])]


def scaled_image(name, width, max_height):
    """Load one report image without allowing it to force a page split."""
    f = SHOTS / name
    if not f.exists() and f.with_suffix(".jpg").exists():
        f = f.with_suffix(".jpg")
    if not f.exists():
        MISSING.append(name)
        return Spacer(1, 1)
    w, h = ImageReader(str(f)).getSize()
    height = width * h / w
    if height > max_height:
        height = max_height
        width = height * w / h
    return Image(str(f), width=width * inch, height=height * inch)


def paired_shot(input_name, output_name, caption):
    """Keep Inspector input and output visibly together as one labeled figure."""
    return [KeepTogether([
        scaled_image(input_name, 5.45, 1.80),
        Spacer(1, 4),
        scaled_image(output_name, 5.45, 2.45),
        p(caption, "Cap"),
    ])]


def redux_pair(ui_name, caption):
    """Current UI output next to the existing short Redux thunk/reducer view."""
    row = Table(
        [[scaled_image(ui_name, 2.70, 2.65),
          scaled_image("part2_home_redux_code_live.jpeg", 2.90, 2.65)]],
        colWidths=[2.85 * inch, 2.95 * inch],
        hAlign="LEFT",
    )
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [KeepTogether([row, p(caption, "Cap")])]


def table(data, widths):
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def cell(t):
    return Paragraph(t, ParagraphStyle("c", fontSize=9, leading=11))


def footer(c, d):
    c.saveState(); c.setFont("Helvetica", 9)
    c.drawString(.7 * inch, .45 * inch, "Akanksha Shukla | DATA-260 Homework 5")
    c.drawRightString(7.8 * inch, .45 * inch, f"Page {d.page}"); c.restoreState()


MISSING: list[str] = []
metrics = json.loads((HW / "raw/fault_injection_summary.json").read_text())
scen = json.loads((HW / "raw/agent_scenarios.json").read_text())
demos = (HW / "raw/part3_part5_demos.txt").read_text().rstrip()
tests = (HW / "raw/test_runner_output.txt").read_text().rstrip() if (HW / "raw/test_runner_output.txt").exists() else ""
dom = json.loads((HW / "raw/mcp_inspector_outputs.json").read_text())["domain_server"]["calls"]

S = [
    p("DATA 260 Homework 5 - Akanksha Shukla", "Main"),
    p("GitHub repository: https://github.com/akankshashuklaWork/data260-7838 (collaborators Sbnikitha and supriyaselvanganesan have been added)"),
    p("Final commit: tagged hw5 | Hardware: Apple M4 Pro, 48 GB RAM, macOS | Local model: qwen2:7b through Ollama"),
    table([["Value", "Result"], ["SID4", "7838"], ["PORT_BASE", "8638 (8000 + 7838 mod 900)"], ["PREFIX", "s7838"],
           ["SEED", "7838"], ["VERIFY_SEED", "267838"], ["DOMAIN_ID", "6 (7838 mod 8)"]], [1.6, 4.5]),

    p("Part 1 - Database, API and Redux client", "Main"),
    p("Database and API", "Sub"),
    p("I extended the HW4 FastAPI + MySQL service instead of starting a new one. The new table is <b>PropertyOwner</b> (id, first/last name, unique email, timestamps). "
      "<b>RentalHousingListing</b> keeps its unique listing code and available-units default, and its owner_id is a foreign key to PropertyOwner. "
      "The foreign key uses ON DELETE RESTRICT and the CRUD layer checks too, so deleting an owner who still has listings returns HTTP 409. "
      "There is no password column on the owner. Owner email format and listing code format are validated with Pydantic (422 on bad input), duplicates give 409 and missing records give 404. "
      "The relationship query is GET /owners/{owner_id}/listings."),
    *shot("part1_database_schema.png", "Figure 1.1 - MySQL schema for both tables"),
    *shot("part1_postman_login.png", "Figure 1.2 - Postman: login to get the token"),
    *shot("part1_postman_owner_create.png", "Figure 1.3 - Postman: create owner (POST /owners)"),
    *shot("part1_postman_owner_list_pagination.png", "Figure 1.4 - Postman: list owners with skip/limit"),
    *shot("part1_postman_owner_get_21.png", "Figure 1.5 - Postman: get one owner"),
    *shot("part1_postman_owner_update_21.png", "Figure 1.6 - Postman: update owner"),
    *shot("part1_postman_owner_delete_blocked_1.png", "Figure 1.7 - Postman: deleting an owner with listings is blocked (409)"),
    *shot("part1_postman_owner_delete_21.png", "Figure 1.8 - Postman: delete an owner with no listings"),
    *shot("part1_postman_validation_invalid_owner_email.png", "Figure 1.9 - Postman: invalid email is rejected (422)"),
    *shot("part1_postman_listing_list_pagination.png", "Figure 1.10 - Postman: list listings with pagination"),
    *shot("part1_postman_listing_get_5002.png", "Figure 1.11 - Postman: get one listing"),
    *shot("part1_postman_listing_create_5002.png", "Figure 1.12 - Postman: create listing"),
    *shot("part1_postman_listing_update_5002.png", "Figure 1.13 - Postman: update listing"),
    *shot("part1_postman_listing_delete_5002.png", "Figure 1.14 - Postman: delete listing"),
    *shot("part1_postman_owner_relationship_1_listings.png", "Figure 1.15 - Postman: relationship query, all listings of owner 1"),

    p("Redux client", "Sub"),
    p("The React data layer now uses Redux Toolkit. <b>listingsSlice.js</b> holds the listings, status and error, and has axios async thunks: fetchListings (GET), createListing (POST), updateListing (PUT /{id}) and deleteListing (DELETE /{id}), each with pending/fulfilled/rejected handling. "
      "The Home screen reads the list from the store, so it refreshes after any change."),
    *redux_pair("part2_redux_delete_result.png", "Figure 1.16 - Home: current Home list reads from Redux state (left); the Redux fetch thunk and reducer are shown at right."),
    *redux_pair("part2_redux_create_confirmation.png", "Figure 1.17 - Create: the current UI confirms Listing created (left); the Redux create thunk and reducer are shown at right."),
    *redux_pair("part2_redux_update_form_result.png", "Figure 1.18 - Update: listing 5004 shows its updated values (left); the Redux update thunk and reducer are shown at right."),
    *redux_pair("part2_redux_delete_result.png", "Figure 1.19 - Delete: the temporary listing is absent and the Redux count is 199 (left); the Redux delete thunk and reducer are shown at right."),

    p("Part 2 - MCP tool servers", "Main"),
    p("A. TheMealDB server (meals)", "Sub"),
    p("meals_server.py (FastMCP over STDIO, logging to stderr) has search_meals_by_name, meals_by_ingredient, random_meal and meal_details. An empty \"meals\": null result returns an empty list with a \"no matches\" message; network/JSON errors are raised as clean errors."),
    *paired_shot("part2_meals_search_by_name_input.png", "part2_meals_search_by_name.png", "Figure 2.1 - search_meals_by_name: input Arrabiata; returned meal cards."),
    *paired_shot("part2_meals_by_ingredient_input.png", "part2_meals_by_ingredient.png", "Figure 2.2 - meals_by_ingredient: input chicken; returned meal cards."),
    *paired_shot("part2_meals_random_input.png", "part2_meals_random.png", "Figure 2.3 - random_meal: no input; returned one full recipe."),
    *paired_shot("part2_meals_details_input.png", "part2_meals_details.png", "Figure 2.4 - meal_details: input id 53367; returned the full recipe."),
    p("B. Domain server (s7838-rental-domain)", "Sub"),
    p("It has exactly three tools - search, detail and aggregate - over the rental listings and owners. Every tool returns {ok, data, error}, with error null on success."),
    *paired_shot("part2_domain_search_success_input.png", "part2_domain_search_success.png", "Figure 2.5 - search valid call. Input: query San Jose, limit 2; output has ok true."),
    *paired_shot("part2_domain_search_invalid_input.png", "part2_domain_search_invalid.png", "Figure 2.6 - search rejected call. Input: blank query, limit 2; output has ok false and a validation error."),
    *paired_shot("part2_domain_detail_success_input.png", "part2_domain_detail_success.png", "Figure 2.7 - detail valid call. Input: listing_id 1; output has ok true and owner details."),
    *paired_shot("part2_domain_detail_invalid_input.png", "part2_domain_detail_invalid.png", "Figure 2.8 - detail rejected call. Input: listing_id 0; output has ok false and a validation error."),
    *paired_shot("part2_domain_aggregate_success_input.png", "part2_domain_aggregate_success.png", "Figure 2.9 - aggregate valid call. Input: owner_id 1; output has ok true with totals."),
    *paired_shot("part2_domain_aggregate_invalid_input.png", "part2_domain_aggregate_invalid.png", "Figure 2.10 - aggregate rejected call. Input: owner_id 0; output has ok false and a validation error."),

    p("Part 3 - Tool contracts under stress", "Main"),
    p("Rejected calls from Part 2B", "Sub"),
    table([[cell("<b>Tool</b>"), cell("<b>Expected input schema</b>"), cell("<b>Rejected input</b>"), cell("<b>Returned error</b>"), cell("<b>Why rejected</b>")],
           [cell("search"), cell('{query: string, min 2 chars; limit: int 1-25}'), cell(json.dumps(dom[3]["inputs"])), cell(dom[3]["output"]["error"]), cell("Empty query is shorter than 2 characters, so a search would match everything.")],
           [cell("detail"), cell('{listing_id: int &gt;= 1}'), cell(json.dumps(dom[4]["inputs"])), cell(dom[4]["output"]["error"]), cell("IDs start at 1; 0 can never name a listing.")],
           [cell("aggregate"), cell('{owner_id: int &gt;= 1}'), cell(json.dumps(dom[5]["inputs"])), cell(dom[5]["output"]["error"]), cell("Same reason: owner_id 0 is not a valid key.")]],
          [0.8, 1.4, 1.3, 1.6, 1.4]),
    p("All three rejections come back as an ok:false envelope with data null and a short message; nothing is raised.", "Body"),
    p("Timeouts and bounded retry", "Sub"),
    p("hw5_mcp/retry.py gives each attempt a 0.25 s timeout and allows 3 retries (4 attempts) with exponential backoff of 0.01, 0.02 and 0.04 s. Real output of the three required cases:"),
    code("\n".join(demos.splitlines()[:3])),
    p("Failure injection with VERIFY_SEED", "Sub"),
    p("A random generator seeded with VERIFY_SEED (267838) decides which attempts fail, so the same sequence repeats on every run. I ran 50 calls at each of 0%, 20% and 50% (150 calls); all records are in reports/hw05/raw/fault_injection_records.json."),
    table([["Injected failure rate", "Success rate", "Mean latency (ms)", "p99 latency (ms)"]] +
          [[f"{int(m['failure_rate']*100)}%", f"{m['success_rate']*100:.0f}%", f"{m['mean_latency_ms']:.2f}", f"{m['p99_latency_ms']:.2f}"] for m in metrics], [1.8, 1.4, 1.6, 1.4]),
    p("<br/>Note: latency here is a modelled cost (2.0 ms + 1.5 ms per attempt), not wall-clock time, because the backoff sleep is skipped in this experiment so it is repeatable.", "Body"),
    p("Is the policy good for an interactive assistant?", "Sub"),
    p("Mostly yes. Even at 50% failures the worst case is four attempts and 0.07 s of backoff, so a user never waits long, and the first two rates had no failed calls. The cost is that at 50% about 6% of calls still failed (3 of 50), so the assistant must handle a clean error. "
      "For batch work I would raise retries to about 6-8, lengthen the timeout to a few seconds, and use a longer capped backoff (for example 0.5 s doubling up to 30 s) with a little random jitter, because finishing every item matters more than speed. I would keep a cap so it cannot retry forever."),

    p("Part 4 - execute_tool and offline tests", "Main"),
    p("execute_tool(name, inputs) is the single entry point for the three domain tools. It validates the input, calls the tool, and always returns a JSON string in the {ok, data, error} form, catching any exception. "
      "The tests use an in-memory store (MemoryDomainStore) passed in as a parameter, so they run offline and without a model."),
    *shot("part4_test_runner_terminal.png", "Figure 4.1 - terminal running the Part 4 test runner (name visible)"),

    p("Part 5 - Safety rule, agent loop and reflection", "Main"),
    p("Safety rule", "Sub"),
    p("Rule: inside execute_tool, a search for the broad query \"all\" with a limit above 10 is blocked, to stop an assistant from exporting every listing. A limit of 10 or less is allowed."),
    code("\n".join(demos.splitlines()[4:])),
    p("Agent loop", "Sub"),
    p("run_agent(user_input) sends the request to the local Ollama model (qwen2:7b), which either answers or calls one of the three tools through execute_tool. A step counter stops the loop at max_steps. Every step, tool call, input, result and the final stop reason is appended to raw/agent_runs.jsonl. "
      "Two more offline tests were added to the Part 4 suite: the safety-rule block, and run_agent with MockModel stopping at max_steps (9/9 pass in total)."),
    p("Metrics (4 live Ollama scenarios)", "Sub"),
    table([["Scenario", "Steps", "Stop reason", "Tool calls"]] + [[cell(s["scenario"]), str(s["steps"]), cell(s["stop_reason"]), str(s["tool_calls"])] for s in scen], [3.2, 0.7, 1.7, 0.9]),
    p("<br/>Two things I noticed: in the owner-summary run the model passed the wrong input and the tool returned a validation error instead of made-up data, and in the \"export every listing\" run the model used a different query, so the safety rule was not triggered live. The block is shown by the offline test above.", "Body"),
    p("Reflection", "Sub"),
]
for para in (HW / "REFLECTION.md").read_text().split("\n\n")[1:]:
    S.append(p(para.strip().replace("`", "")))

S += [p("AI use", "Main")]
for para in (HW / "AI_USE.md").read_text().split("\n\n")[1:]:
    S.append(p(para.strip().replace("`", "")))

SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=.7 * inch, rightMargin=.7 * inch, topMargin=.7 * inch, bottomMargin=.7 * inch,
                  title="Shukla HW5").build(S, onFirstPage=footer, onLaterPages=footer)
print(OUT)
print("missing screenshots:", MISSING)
