"""Small local UI for the HW7 bike advisor."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from .bike_agent import PRICING_URL, BikeTools, ReActBikeAgent

app = FastAPI(title="HW7 Citi Bike Membership Advisor")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<main><h1>Citi Bike membership advisor</h1><form method='post' action='/run' enctype='multipart/form-data'>
<label>Trip CSV <input type='file' name='trip_csv' accept='.csv' required></label><br>
<label>Pricing URL <input name='pricing_url' value='https://citibikenyc.com/plans-and-pricing' size='55'></label><br>
<button>Run comparison</button></form></main>"""


@app.post("/run", response_class=HTMLResponse)
async def run(trip_csv: UploadFile = File(...), pricing_url: str = Form(PRICING_URL)) -> str:
    """Save an uploaded CSV to a temp directory and render the concise tool timeline."""
    snapshot = (
        Path(__file__).resolve().parents[2] / "reports/hw07/pricing/citibike_pricing_snapshot.txt"
    )
    with tempfile.TemporaryDirectory() as directory:
        csv_path = Path(directory) / "uploaded.csv"
        csv_path.write_bytes(await trip_csv.read())
        result = ReActBikeAgent(BikeTools(csv_path, snapshot, pricing_url)).run()
    timeline = "".join(
        f"<li><b>{item['tool']}</b>: {item['rationale']}</li>" for item in result["timeline"]
    )
    citations = result["citations"]
    return (
        f"<main><h1>{result['decision']}</h1><p>{' '.join(result['justification'])}</p>"
        f"<h2>Cost breakdown</h2><pre>{result['cost_breakdown']}</pre><h2>Timeline</h2><ol>{timeline}</ol>"
        f"<p>Citation: {citations['pricing_url']} | snapshot SHA-256: {citations['snapshot_sha256']}</p>"
        f"<p>Steps: {result['metrics']['step_count']} | Stop: {result['metrics']['stop_reason']}</p></main>"
    )
