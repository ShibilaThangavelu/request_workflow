import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from workflow.branches import process_request, DB_PATH, init_db

st.set_page_config(page_title="Incoming Request Workflow", layout="wide")
st.title("Incoming Request Processing Workflow")
st.caption(
    "Classify a request with Gemini, route it to a branch, draft a reply, notify the right team, "
    "set a follow-up and log the case. Sending is simulated: messages are saved in an outbox, not emailed."
)

init_db()

EXAMPLES = {
    "Write my own": "",
    "Complaint": "I was charged twice for my March bill and nobody has fixed it after three calls.",
    "General Enquiry": "Do you offer a student discount on your plans?",
    "Service Request": "Please update my address to 12 Smith Street, Richmond VIC 3121.",
    "Urgent": "My card was stolen an hour ago. Please block it immediately.",
    "Unclear": "Hi, about my thing from last week",
}

choice = st.selectbox("Load an example", list(EXAMPLES))
text = st.text_area("Customer request", value=EXAMPLES[choice], key=f"text_{choice}", height=120)
email = st.text_input("Customer email (the reply is sent here)", value="customer@example.com")

if st.button("Process request", type="primary"):
    if not text.strip():
        st.warning("Please enter a request.")
    else:
        with st.spinner("Classifying, drafting a reply and notifying the team..."):
            out = process_request(text.strip(), customer_email=email.strip() or "customer@example.com")
        r = out["result"]
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        c1.metric("Branch", out["branch"])
        c2.metric("Type", r.get("type") or "-")
        c3.metric("Urgency", r.get("urgency") or "-")
        conf = r.get("confidence")
        c4.metric("Confidence", f"{conf:.2f}" if isinstance(conf, (int, float)) else "-")
        st.write("**Reason:**", r.get("reason"))
        st.subheader(f"Case #{out['case_id']}: {out['status']}")
        left, right = st.columns(2)
        with left:
            st.markdown("**Actions taken**")
            for i, step in enumerate(out["steps"], 1):
                st.write(f"{i}. {step}")
        with right:
            st.markdown("**Messages sent (simulated)**")
            if not out["messages"]:
                st.warning("No messages for this case.")
            for m in out["messages"]:
                st.markdown(f"**{m['kind']}** to `{m['to']}`")
                st.caption(f"Subject: {m['subject']}")
                st.info(m["body"])

st.divider()
st.subheader("Follow-ups")
with sqlite3.connect(DB_PATH) as db:
    fu = pd.read_sql_query(
        "SELECT id, branch, follow_up, follow_up_due FROM cases "
        "WHERE follow_up_due IS NOT NULL ORDER BY follow_up_due ASC LIMIT 20",
        db,
    )


def due_state(value):
    due = datetime.fromisoformat(value)
    hours = (due - datetime.now()).total_seconds() / 3600
    if hours < 0:
        return "OVERDUE"
    return f"due in {hours:.1f} hours" if hours < 48 else f"due in {hours / 24:.1f} days"


if fu.empty:
    st.caption("No open follow-ups yet.")
else:
    fu["state"] = fu["follow_up_due"].map(due_state)
    st.dataframe(fu, hide_index=True)

with sqlite3.connect(DB_PATH) as db:
    log = pd.read_sql_query(
        "SELECT id, created_at, request, type, urgency, confidence, branch, status, follow_up_due "
        "FROM cases ORDER BY id DESC LIMIT 20",
        db,
    )
    counts = pd.read_sql_query("SELECT branch, COUNT(*) AS cases FROM cases GROUP BY branch", db)
    outbox = pd.read_sql_query(
        "SELECT case_id, created_at, kind, to_addr, subject, status FROM outbox ORDER BY id DESC LIMIT 10", db
    )

st.subheader("Cases by branch")
if counts.empty:
    st.caption("No cases yet.")
else:
    st.bar_chart(counts.set_index("branch"))

st.subheader("Case log")
st.dataframe(log, hide_index=True)

st.subheader("Outbox (simulated)")
st.dataframe(outbox, hide_index=True)
