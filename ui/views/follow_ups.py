import pandas as pd
import streamlit as st

from common import read, due_state
from workflow.branches import check_reminders, resolve_case

st.title("5. Follow-ups")
st.caption("Every case gets a follow-up time (complaints: 2 hours). If a case is still open when that time passes, "
           "the system sends a reminder to the supervisor and drafts a customer update.")

b1, b2, _ = st.columns([1, 1.3, 3])
if b1.button("Run reminder check"):
    fired = check_reminders()
    st.session_state["reminder_msg"] = f"{len(fired)} reminder(s) fired." if fired else "Nothing is overdue yet."
if b2.button("Simulate 2 hours passing"):
    fired = check_reminders(extra_hours=2)
    st.session_state["reminder_msg"] = (
        f"2 hours later: {len(fired)} reminder(s) fired. Check the Team inbox (supervisor) and Approvals (customer update)."
        if fired else "2 hours later: nothing was due (cases resolved or already reminded).")
if st.session_state.get("reminder_msg"):
    st.info(st.session_state["reminder_msg"])

fu = read(
    "SELECT id AS case_id, branch, priority, follow_up, follow_up_due, reminder_sent, resolved_at FROM cases "
    "WHERE follow_up_due IS NOT NULL ORDER BY follow_up_due ASC LIMIT 50"
)
if fu.empty:
    st.caption("No follow-ups yet.")
else:
    def state_of(r):
        if pd.notna(r["resolved_at"]):
            return "Resolved"
        if pd.notna(r["reminder_sent"]) and int(r["reminder_sent"]) == 1:
            return "Reminder sent"
        return due_state(r["follow_up_due"])

    fu["state"] = fu.apply(state_of, axis=1)
    st.dataframe(fu[["case_id", "branch", "priority", "follow_up", "follow_up_due", "state"]], hide_index=True)

open_cases = read("SELECT id FROM cases WHERE resolved_at IS NULL ORDER BY id DESC LIMIT 50")
if not open_cases.empty:
    st.markdown("#### Close a case")
    r1, r2, _ = st.columns([2, 1, 3])
    pick = r1.selectbox("Case", open_cases["id"], format_func=lambda i: f"Case #{i}", key="resolve_pick")
    r2.write("")
    if r2.button("Mark resolved"):
        resolve_case(int(pick))
        st.rerun()
