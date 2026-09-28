import json, os, subprocess, sys
from pathlib import Path
import httpx

VERIFY_SEED = 267838
ROOT = Path(__file__).resolve().parents[2]

def main():
    checks = []
    try:
        r = httpx.get(f"http://127.0.0.1:{os.getenv('PORT_BASE', '8638')}/health", timeout=5)
        checks.append({"name": "FastAPI health endpoint", "passed": r.status_code == 200 and r.json().get("status") == "ok"})
    except Exception as exc:
        checks.append({"name": "FastAPI health endpoint", "passed": False, "error": str(exc)})
    checks.append({"name": "required backend package exists", "passed": (ROOT / "code/hw4_backend/main.py").exists()})
    result = {"homework": 4, "SID4": 7838, "commit_hash": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "SEED": 7838, "VERIFY_SEED": VERIFY_SEED, "checks": checks, "passed": all(c["passed"] for c in checks)}
    target = ROOT / "reports/hw04/verification.json"; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2)); sys.exit(0 if result["passed"] else 1)

if __name__ == "__main__": main()
