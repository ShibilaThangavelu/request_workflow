import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from workflow.branches import process_request, DB_PATH, init_db, MIN_CONFIDENCE

st.set_page_config(page_title="Request Workflow", layout="wide")
init_db()

EXAMPLES = {
    "Write my own": "",
    "Complaint": "I was charged twice for my March bill and nobody has fixed it after three calls.",
    "General Enquiry": "Do you offer a student discount on your plans?",
    "Service Request": "Please update my address to 12 Smith Street, Richmond VIC 3121.",
    "Urgent": "My card was stolen an hour ago. Please block it immediately.",
    "Unclear": "Hi, about my thing from last week",
}

BANNER = {
    "Urgent Escalation": st.error,
    "Needs Human Review": st.warning,
    "Complaint": st.info,
    "Service Request": st.info,
    "General Enquiry": st.success,
}


def read(sql):
    with sqlite3.connect(DB_PATH) as db:
        return pd.read_sql_query(sql, db)


def due_state(value):
    due = datetime.fromisoformat(value)
    hours = (due - datetime.now()).total_seconds() / 3600
    if hours < 0:
        return "OVERDUE"
    return f"in {hours:.1f} hours" if hours < 48 else f"in {hours / 24:.1f} days"


# ---------- sidebar ----------
with st.sidebar:
    st.header("Request Workflow")
    st.caption("Classify, route, reply, notify, follow up, log.")
    choice = st.selectbox("Load an example", list(EXAMPLES))
    email = st.text_input("Customer email", "customer@example.com")
    with st.expander("How it works"):
        st.markdown(
            "1. Gemini labels the request: type, urgency, confidence, reason.\n"
            f"2. Code checks the answer. Invalid or confidence below {MIN_CONFIDENCE} goes to a person.\n"
            "3. Urgency high goes to Urgent Escalation; otherwise the branch for its type.\n"
            "4. The branch drafts a reply, notifies the right team and sets a follow-up.\n"
            "5. Everything is saved in the case log."
        )
    st.caption("Sending is simulated: messages are saved in an outbox, not emailed.")

# ---------- header and summary numbers ----------
st.title("Incoming Request Processing Workflow")

cases = read("SELECT branch, follow_up_due FROM cases")
due = pd.to_datetime(cases["follow_up_due"], errors="coerce")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Cases processed", len(cases))
k2.metric("Urgent escalations", int((cases["branch"] == "Urgent Escalation").sum()))
k3.metric("Waiting for a person", int((cases["branch"] == "Needs Human Review").sum()))
k4.metric("Overdue follow-ups", int((due < pd.Timestamp.now()).sum()))

st.divider()

# ---------- input ----------
st.subheader("New request")
text = st.text_area("Customer request", value=EXAMPLES[choice], key=f"text_{choice}", height=110)
if st.button("Process request", type="primary"):
    if not text.strip():
        st.warning("Please enter a request.")
    else:
        with st.spinner("Classifying, drafting a reply and notifying the team..."):
            st.session_state["out"] = process_request(
                text.strip(), customer_email=email.strip() or "customer@example.com"
            )
            st.session_state["request_text"] = text.strip()

# ---------- result ----------
out = st.session_state.get("out")
if out:
    r = out["result"]
    BANNER.get(out["branch"], st.info)(f"**{out['branch']}** | {out['status']} | Case #{out['case_id']}")
    st.caption("Request: " + st.session_state.get("request_text", ""))

    c1, c2, c3 = st.columns(3)
    c1.metric("Type", r.get("type") or "-")
    c2.metric("Urgency", r.get("urgency") or "-")
    conf = r.get("confidence")
    if isinstance(conf, (int, float)):
        c3.metric("Confidence", f"{conf:.2f}")
        st.progress(min(max(float(conf), 0.0), 1.0), text=f"Human review below {MIN_CONFIDENCE}")
    else:
        c3.metric("Confidence", "-")
    st.caption("Model reason: " + str(r.get("reason")))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Actions taken")
        for step in out["steps"]:
            st.markdown("- " + step)
    with right:
        st.markdown("#### Messages (simulated)")
        if not out["messages"]:
            st.info("No messages for this case.")
        for m in out["messages"]:
            with st.container(border=True):
                st.markdown(f"**{m['kind']}**  \nTo: `{m['to']}`  \nSubject: {m['subject']}")
                st.text(m["body"])

st.divider()

# ---------- records ----------
tab_log, tab_follow, tab_chart, tab_outbox = st.tabs(["Case log", "Follow-ups", "Cases by branch", "Outbox"])

with tab_log:
    log = read(
        "SELECT id, created_at, request, type, urgency, confidence, branch, status "
        "FROM cases ORDER BY id DESC LIMIT 25"
    )
    st.dataframe(log, hide_index=True)

with tab_follow:
    fu = read(
        "SELECT id, branch, follow_up, follow_up_due FROM cases "
        "WHERE follow_up_due IS NOT NULL ORDER BY follow_up_due ASC LIMIT 25"
    )
    if fu.empty:
        st.caption("No open follow-ups yet.")
    else:
        fu["state"] = fu["follow_up_due"].map(due_state)
        st.dataframe(fu, hide_index=True)

with tab_chart:
    counts = read("SELECT branch, COUNT(*) AS cases FROM cases GROUP BY branch")
    if counts.empty:
        st.caption("No cases yet.")
    else:
        st.bar_chart(counts.set_index("branch"))

with tab_outbox:
    outbox = read(
        "SELECT case_id, created_at, kind, to_addr, subject, status FROM outbox ORDER BY id DESC LIMIT 25"
    )
    st.dataframe(outbox, hide_index=True)
