import streamlit as st

from common import read
from workflow.branches import pending_approvals

st.title("6. Dashboard")
st.caption("A summary of everything processed: volumes by branch, what is waiting, and the full case log.")

cases = read("SELECT * FROM cases")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cases processed", len(cases))
k2.metric("Urgent escalations", int((cases["branch"] == "Urgent Escalation").sum()) if len(cases) else 0)
k3.metric("Waiting for a person", int((cases["branch"] == "Needs Human Review").sum()) if len(cases) else 0)
k4.metric("Replies awaiting approval", len(pending_approvals()))
k5.metric("Reminders fired", int(cases["reminder_sent"].fillna(0).sum()) if len(cases) else 0)

st.markdown("#### Cases by branch")
counts = read("SELECT branch, COUNT(*) AS cases FROM cases GROUP BY branch")
if counts.empty:
    st.caption("No cases yet.")
else:
    st.bar_chart(counts.set_index("branch"))

st.markdown("#### Service requests by department")
by_dept = read("SELECT department, COUNT(*) AS cases FROM cases WHERE department IS NOT NULL GROUP BY department")
if by_dept.empty:
    st.caption("No service requests yet.")
else:
    st.bar_chart(by_dept.set_index("department"))

st.markdown("#### Case log")
log = read(
    "SELECT id, created_at, request, type, subtopic, department, urgency, priority, confidence, branch, status, approval_status "
    "FROM cases ORDER BY id DESC LIMIT 50"
)
st.dataframe(log, hide_index=True)
