import pandas as pd
import streamlit as st

from common import when
from workflow.branches import process_request, MIN_CONFIDENCE

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
    "Complaint": st.warning,
    "Service Request": st.info,
    "General Enquiry": st.success,
}

st.title("1. Submit a request")
st.caption("A customer request arrives here. The AI labels it, then runs the workflow for that type. "
           "This page shows what the system decided and did. The next pages show what the customer and the team received.")

c1, c2 = st.columns([1, 2])
choice = c1.selectbox("Load an example", list(EXAMPLES))
email = c2.text_input("Customer email", "customer@example.com")
text = st.text_area("Customer request", value=EXAMPLES[choice], key=f"text_{choice}", height=110)

if st.button("Process request", type="primary"):
    if not text.strip():
        st.warning("Please enter a request.")
    else:
        with st.spinner("Classifying, drafting a reply and notifying the team..."):
            st.session_state["out"] = process_request(text.strip(), customer_email=email.strip() or "customer@example.com")
            st.session_state["request_text"] = text.strip()

out = st.session_state.get("out")
if out and out.get("case_log"):
    r = out["result"]
    st.divider()
    BANNER.get(out["branch"], st.info)(f"**{out['branch']}** | {out['status']} | Case #{out['case_id']}")
    st.caption("Request: " + st.session_state.get("request_text", ""))

    st.markdown("#### Step 1: how the AI classified it")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Type", r.get("type") or "-")
    m2.metric("Urgency", r.get("urgency") or "-")
    conf = r.get("confidence")
    m3.metric("Confidence", f"{conf:.2f}" if isinstance(conf, (int, float)) else "-")
    m4.metric("Priority flag", out.get("priority", "-"))
    st.caption(f"Reason: {r.get('reason')}  |  Below {MIN_CONFIDENCE} confidence, a person reviews it instead.")

    st.markdown("#### Step 2: what the workflow did")
    for step in out["steps"]:
        st.markdown("- :green[✓] " + step)
    if out.get("needs_approval"):
        st.warning("The customer reply is HELD. Automatic resolution is paused until a person approves it on the Approvals page.")

    st.markdown("#### Step 3: case log entry")
    st.dataframe(pd.DataFrame([out["case_log"]]).T.rename(columns={0: "value"}).astype(str))

    st.markdown("#### Where to look next")
    st.page_link("views/customer_inbox.py", label="2. Customer inbox: the reply the customer gets")
    st.page_link("views/team_inbox.py", label="3. Team inbox: the notification the team gets")
    if out.get("needs_approval"):
        st.page_link("views/approvals.py", label="4. Approvals: release or edit the held reply")
    st.page_link("views/follow_ups.py", label="5. Follow-ups: the reminder that was set")
