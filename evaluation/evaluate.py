import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sys
import time
import pandas as pd
from workflow.classifier import classify

split = sys.argv[1] if len(sys.argv) > 1 else "dev"
df = pd.read_csv("data/requests.csv")
df = df[df["split"] == split]

results = []
for _, row in df.iterrows():
    try:
        out = classify(row["text"])
    except Exception as e:
        out = {"type": "ERROR", "urgency": "ERROR", "confidence": 0, "reason": str(e)}
    results.append({
        "id": row["id"],
        "text": row["text"],
        "expected_type": row["type"],
        "got_type": out.get("type"),
        "expected_urgency": row["urgency"],
        "got_urgency": out.get("urgency"),
        "confidence": out.get("confidence"),
        "reason": out.get("reason"),
    })
    time.sleep(13)

res = pd.DataFrame(results)
res["type_ok"] = res["expected_type"] == res["got_type"]
res["urgency_ok"] = res["expected_urgency"] == res["got_urgency"]

print(f"Split: {split}, rows: {len(res)}")
print(f"Type accuracy: {res['type_ok'].mean():.0%}")
print(f"Urgency accuracy: {res['urgency_ok'].mean():.0%}")

wrong = res[~(res["type_ok"] & res["urgency_ok"])]
if len(wrong):
    print("\nRows it got wrong:")
    print(wrong[["id", "text", "expected_type", "got_type", "expected_urgency", "got_urgency", "reason"]].to_string())

res.to_csv(f"data/results/results_{split}.csv", index=False)
