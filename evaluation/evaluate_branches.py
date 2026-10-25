import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sys
import time
import pandas as pd
from workflow.classifier import classify
from workflow.branches import route

path = sys.argv[1] if len(sys.argv) > 1 else "data/edge_cases.csv"
df = pd.read_csv(path)

rows = []
for _, r in df.iterrows():
    try:
        result = classify(r["text"])
        error = False
    except Exception as e:
        result = {"type": None, "urgency": None, "confidence": 0, "reason": "API error: " + str(e)[:60]}
        error = True
    rows.append({
        "id": r["id"], "text": r["text"], "kind": r["kind"],
        "expected_branch": r["expected_branch"], "got_branch": route(result),
        "type": result.get("type"), "urgency": result.get("urgency"),
        "confidence": result.get("confidence"), "api_error": error, "reason": result.get("reason"),
    })
    print(f"{len(rows)}/{len(df)} done: {r['id']} -> {route(result)}", flush=True)
    time.sleep(13)

res = pd.DataFrame(rows)
res.to_csv("data/results/results_edge.csv", index=False)

ok = res[~res["api_error"]].copy()
ok["correct"] = ok["expected_branch"] == ok["got_branch"]
print(f"Rows: {len(res)}  API errors (excluded): {int(res['api_error'].sum())}")
print(f"Branch accuracy: {int(ok['correct'].sum())}/{len(ok)} = {ok['correct'].mean():.0%}")
print(ok.groupby("expected_branch")["correct"].agg(["sum", "count"]).to_string())
wrong = ok[~ok["correct"]]
safe = int((wrong["got_branch"] == "Needs Human Review").sum())
print(f"Misses: {len(wrong)} (sent to human review, safe: {safe}; wrong automatic branch: {len(wrong) - safe})")
for _, w in wrong.iterrows():
    print(w["id"], "|", w["text"][:60], "| expected", w["expected_branch"], "| got", w["got_branch"], "| conf", w["confidence"])
