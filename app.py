import sqlite3
import pandas as pd
import streamlit as st
from branches import process_request, DB_PATH, init_db

st.set_page_config(page_title="Incoming Request Workflow", layout="wide")
st.title("Incoming Request Processing Workflow")
st.caption("Classify a request with Gemini, route it to a branch, and log the case.")

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

if st.button("Process request", type="primary"):
    if not text.strip():
        st.warning("Please enter a request.")
    else:
        with st.spinner("Classifying..."):
            out = process_request(text.strip())
        r = out["result"]
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        c1.metric("Branch", out["branch"])
        c2.metric("Type", r.get("type") or "-")
        c3.metric("Urgency", r.get("urgency") or "-")
        conf = r.get("confidence")
        c4.metric("Confidence", f"{conf:.2f}" if isinstance(conf, (int, float)) else "-")
        st.write("**Reason:**", r.get("reason"))
        st.subheader(f"Case #{out['case_id']}: {out['status']}")
        for i, step in enumerate(out["steps"], 1):
            st.write(f"{i}. {step}")

st.divider()
st.subheader("Case log")
with sqlite3.connect(DB_PATH) as db:
    log = pd.read_sql_query(
        "SELECT id, created_at, request, type, urgency, confidence, branch, status "
        "FROM cases ORDER BY id DESC LIMIT 20",
        db,
    )
st.dataframe(log, hide_index=True)