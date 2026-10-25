"""Run one sample request per branch and save the input and output as JSON.

Usage: python evaluation/generate_samples.py
Reads data/sample_inputs/*.txt, writes data/sample_inputs/*.json and data/sample_outputs/*.json.
Uses the local Python engine and a temporary database, so nothing is sent to Slack or email and
data/cases.db is not touched.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow import branches  # noqa: E402

branches.n8n_client.enabled = lambda: False  # force the local engine (the .env file may set N8N_WEBHOOK_URL)

branches.DB_PATH = os.path.join(tempfile.mkdtemp(), "samples.db")
branches.init_db()

inputs = ROOT / "data" / "sample_inputs"
outputs = ROOT / "data" / "sample_outputs"
outputs.mkdir(exist_ok=True)

for path in sorted(inputs.glob("*.txt")):
    request = path.read_text().strip()
    payload = {"request": request, "customer_email": "customer@example.com"}
    result = branches.process_request(request)
    (inputs / (path.stem + ".json")).write_text(json.dumps(payload, indent=2) + "\n")
    (outputs / (path.stem + ".json")).write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(path.stem, "->", result["branch"], "|", result["status"])
    time.sleep(20)  # stay under the free-tier rate limit
