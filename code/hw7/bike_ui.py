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
    return """<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Citi Bike advisor</title>
  <style>
    :root { --ink:#102a43; --muted:#627d98; --blue:#1677ff; --teal:#12b886; --card:#ffffff; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; font-family:Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
      color:var(--ink); background:linear-gradient(135deg,#e8f7ff 0%,#f7fbff 48%,#e8fff6 100%); }
    .shell { max-width:980px; margin:0 auto; padding:56px 24px; }
    .hero { display:flex; align-items:center; gap:18px; margin-bottom:28px; }
    .mark { width:58px; height:58px; display:grid; place-items:center; border-radius:18px;
      color:white; font-size:28px; background:linear-gradient(135deg,var(--blue),var(--teal));
      box-shadow:0 12px 28px #1677ff35; }
    h1 { margin:0; font-size:clamp(32px,5vw,52px); letter-spacing:-1.8px; line-height:1; }
    .subtitle { margin:10px 0 0; color:var(--muted); font-size:16px; }
    .card { background:rgba(255,255,255,.88); border:1px solid #d9e8f2; border-radius:24px;
      padding:30px; box-shadow:0 20px 55px #164e6320; backdrop-filter:blur(10px); }
    .card h2 { margin:0 0 8px; font-size:22px; }
    .hint { margin:0 0 24px; color:var(--muted); }
    .field { margin:18px 0; }
    label { display:block; margin-bottom:8px; font-weight:700; font-size:14px; }
    input[type=file], input[type=url] { width:100%; border:1px solid #c5d8e5; border-radius:12px;
      background:#fff; color:var(--ink); padding:13px 14px; font:inherit; }
    input[type=file] { padding:10px 12px; }
    input:focus { outline:3px solid #1677ff28; border-color:var(--blue); }
    button { border:0; border-radius:12px; padding:14px 20px; color:#fff; font-weight:800;
      font-size:15px; cursor:pointer; background:linear-gradient(135deg,var(--blue),#0bbf9a);
      box-shadow:0 10px 20px #1677ff30; transition:transform .15s, box-shadow .15s; }
    button:hover { transform:translateY(-2px); box-shadow:0 14px 25px #1677ff40; }
    .footer { margin-top:20px; color:var(--muted); font-size:13px; text-align:center; }
  </style>
</head>
<body><main class='shell'>
  <header class='hero'><div class='mark'>🚲</div><div><h1>Citi Bike advisor</h1>
    <p class='subtitle'>A transparent trip-cost comparison for your next ride.</p></div></header>
  <section class='card'><h2>Compare your options</h2>
    <p class='hint'>Upload trip history and use the current pricing snapshot to get a grounded recommendation.</p>
    <form method='post' action='/run' enctype='multipart/form-data'>
      <div class='field'><label for='trip_csv'>Trip CSV</label>
        <input id='trip_csv' type='file' name='trip_csv' accept='.csv' required></div>
      <div class='field'><label for='pricing_url'>Pricing page URL</label>
        <input id='pricing_url' type='url' name='pricing_url' value='https://citibikenyc.com/plans-and-pricing' required></div>
      <button type='submit'>Run comparison&nbsp; →</button>
    </form>
  </section>
  <p class='footer'>Rental mobility analysis · bounded tools · cited pricing evidence</p>
</main></body></html>"""


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
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Comparison result</title><style>"
        ":root{--ink:#102a43;--muted:#627d98;--blue:#1677ff;--card:#fff}*{box-sizing:border-box}"
        "body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:var(--ink);background:linear-gradient(135deg,#e8f7ff,#f7fbff 48%,#e8fff6)}"
        ".shell{max-width:980px;margin:0 auto;padding:48px 24px}.badge{display:inline-block;padding:8px 12px;border-radius:999px;background:#dff8ed;color:#087f5b;font-weight:800;font-size:13px}"
        "h1{font-size:clamp(34px,6vw,58px);letter-spacing:-2px;margin:14px 0 10px}.lead{color:var(--muted);font-size:18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:26px}"
        ".card{background:rgba(255,255,255,.9);border:1px solid #d9e8f2;border-radius:22px;padding:24px;box-shadow:0 18px 45px #164e6320}.card h2{margin:0 0 14px}pre{white-space:pre-wrap;background:#102a43;color:#e8fff6;border-radius:14px;padding:16px;overflow:auto}.timeline{padding-left:22px}.timeline li{margin:12px 0;color:var(--muted)}.meta{margin-top:22px;color:var(--muted);font-size:13px;line-height:1.7}@media(max-width:720px){.grid{grid-template-columns:1fr}}"
        "</style></head><body><main class='shell'><span class='badge'>Live comparison complete</span>"
        f"<h1>{result['decision']}</h1><p class='lead'>{' '.join(result['justification'])}</p>"
        f"<div class='grid'><section class='card'><h2>Cost breakdown</h2><pre>{result['cost_breakdown']}</pre></section>"
        f"<section class='card'><h2>Timeline</h2><ol class='timeline'>{timeline}</ol></section></div>"
        f"<p class='meta'><b>Pricing source:</b> {citations['pricing_url']}<br><b>captured:</b> {citations['capture_timestamp']}<br>"
        f"<b>Snapshot SHA-256:</b> {citations['snapshot_sha256']}<br><b>Steps:</b> {result['metrics']['step_count']} · <b>Stop:</b> {result['metrics']['stop_reason']}</p></main></body></html>"
    )
