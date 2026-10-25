import streamlit as st

from common import read, when, TEAM_BY_ADDRESS

st.title("3. Team inbox")
st.caption("The notifications each team receives (simulated), like a chat channel per team. "
           "Overdue reminders from the 2-hour follow-up show up here too.")

notes = read(
    "SELECT o.id, o.case_id, o.created_at, o.kind, o.to_addr, o.subject, o.body, c.priority "
    "FROM outbox o JOIN cases c ON c.id = o.case_id "
    "WHERE o.kind IN ('Internal notification', 'Escalation reminder') ORDER BY o.id DESC LIMIT 100"
)
notes["team"] = notes["to_addr"].map(TEAM_BY_ADDRESS).fillna("Other")
teams = list(dict.fromkeys(TEAM_BY_ADDRESS.values()))
labels = [f"{t} ({int((notes['team'] == t).sum())})" for t in teams]

for tab, team in zip(st.tabs(labels), teams):
    with tab:
        mine = notes[notes["team"] == team]
        if mine.empty:
            st.caption("No messages for this team yet.")
        for _, n in mine.iterrows():
            with st.chat_message("assistant"):
                tag = "REMINDER" if n["kind"] == "Escalation reminder" else "New case"
                st.markdown(f"**{tag}** | Case #{n['case_id']} | priority {n['priority']} | {when(n['created_at'])}")
                st.text(n["body"])
