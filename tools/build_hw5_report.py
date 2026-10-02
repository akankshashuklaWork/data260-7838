from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/hw05/report.pdf"
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=18, leading=22, spaceAfter=18))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=14, leading=17, spaceBefore=12, spaceAfter=7))
styles.add(ParagraphStyle(name="Sub", parent=styles["Heading3"], fontSize=12, leading=15, spaceBefore=8, spaceAfter=5))
styles.add(ParagraphStyle(name="Body11", parent=styles["BodyText"], fontSize=11, leading=15, spaceAfter=7))

def p(text, style="Body11"):
    return Paragraph(text, styles[style])

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 9); canvas.setFillColor(colors.grey)
    canvas.drawString(0.7 * inch, 0.45 * inch, "Akanksha Shukla | DATA-260 Homework 5")
    canvas.drawRightString(7.8 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()

story = [
    p("DATA 260 Homework 5", "ReportTitle"),
    p("Rental Housing Listings Extension, MCP Tools, and Safe Agent Harness", "Sub"),
    p("GitHub repository: https://github.com/akankshashuklaWork/data260-7838", "Body11"),
    p("Student: Akanksha Shukla", "Body11"),
    p("Hardware: MacBook Pro with Apple M4 Pro and 48 GB RAM. Local model: qwen2:7b through Ollama. Submission commit is recorded by reports/hw05/verification.json and should be replaced with the final tagged commit hash after tagging hw5.", "Body11"),
    p("Configuration", "Section"),
]
config = [["Value", "Result"], ["SID4", "7838"], ["PORT_BASE", "8638"], ["PREFIX", "s7838"], ["SEED", "7838"], ["VERIFY_SEED", "267838"], ["DOMAIN_ID", "6"]]
story.append(Table(config, colWidths=[1.7*inch, 4.8*inch], style=[("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f4e79")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#d9d9d9")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f2f6fa")]), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
story += [
    p("Part 1 Database and API", "Section"),
    p("The existing rental-housing service was extended in code/hw4_backend rather than copied into a new service. PropertyOwner is the related entity. RentalHousingListing now has a unique listing_code, available_units with a default of one, owner_id, and created_at/updated_at timestamps. The owner foreign key uses RESTRICT behavior, and the API returns HTTP 409 when an owner still has listings.", "Body11"),
    p("CRUD routes cover /owners and /listings with pagination, individual lookup, update, delete, Pydantic validation, unique-field conflict handling, and /owners/{owner_id}/listings for the relationship query.", "Body11"),
    p("Part 1 Redux Client", "Section"),
    p("The React data layer now uses Redux Toolkit in code/hw4_frontend/src/features/listings/listingsSlice.js and src/store/store.js. Axios thunks implement fetch, create, update, and delete; the Home screen reads from Redux state and updates after each successful mutation. Create and Update forms include owner selection and the unique listing code.", "Body11"),
    p("Part 2 MCP Servers", "Section"),
    p("code/hw5_mcp/meals_server.py defines four TheMealDB tools and sends all STDIO logging to stderr. code/hw5_mcp/domain_server.py exposes exactly three domain tools: search, detail, and aggregate. All domain responses reuse the {ok, data, error} envelope, and the SQLAlchemy adapter can read the existing s7838_rel database while offline tests use deterministic fixtures.", "Body11"),
    p("Part 3 Retry Metrics", "Section"),
]
metrics = [["Failure rate", "Calls", "Success", "Mean ms", "p99 ms"], ["0%", "50", "100.00%", "3.500", "3.500"], ["20%", "50", "100.00%", "3.770", "5.000"], ["50%", "50", "94.00%", "4.850", "8.000"]]
story.append(Table(metrics, colWidths=[1.3*inch, .8*inch, 1.2*inch, 1.2*inch, 1.2*inch], style=[("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f4e79")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#d9d9d9")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f2f6fa")]), ("ALIGN", (1,1), (-1,-1), "CENTER"), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
story += [
    p("The raw 150 records are in reports/hw05/raw/fault_injection_records.json. The experiment uses VERIFY_SEED 267838, a maximum of three retries, and bounded exponential backoff. The deterministic latency metric is documented in METRICS.md.", "Body11"),
    p("Part 4 Offline Tests and Part 5 Agent", "Section"),
    p("code/run_hw5_tests.py reports 9/9 passing tests, including valid and invalid inputs for all three domain tools, the safety-rule allow/block pair, and the max_steps MockModel test. execute_tool never raises to its caller and always returns a JSON string. The agent records tool calls, inputs, results, stop reasons, and summaries in reports/hw05/raw/agent_runs.jsonl.", "Body11"),
    p("Evidence status", "Section"),
    p("Completed machine-readable evidence includes verification.json, RUN_LOG.txt, METRICS.md, AI_USE.md, REFLECTION.md, raw retry records, MCP-style domain outputs, and the offline agent log. Live MCP Inspector screenshots and four Ollama scenario screenshots require the local mcp[cli] package, a running MCP Inspector, and a running Ollama service; those runtime-dependent artifacts are intentionally not represented as completed here.", "Body11"),
]
OUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUT), pagesize=letter, rightMargin=.7*inch, leftMargin=.7*inch, topMargin=.7*inch, bottomMargin=.7*inch, title="DATA 260 Homework 5").build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
