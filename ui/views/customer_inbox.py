import streamlit as st

from common import read, when

st.title("2. Customer inbox")
st.caption("The emails customers receive (simulated). Complaints and urgent cases are held until a person approves them.")

mail = read(
    "SELECT o.id, o.case_id, o.created_at, o.kind, o.to_addr, o.subject, o.body, o.status, c.branch "
    "FROM outbox o JOIN cases c ON c.id = o.case_id "
    "WHERE o.kind IN ('Customer reply', 'Customer update (draft)') ORDER BY o.id DESC LIMIT 50"
)
if mail.empty:
    st.info("No emails yet. Submit a request first.")
for _, m in mail.iterrows():
    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.markdown(f"**{m['subject']}**  \nTo: `{m['to_addr']}`  |  {when(m['created_at'])}  |  {m['branch']}")
        status = m["status"]
        if status.startswith("Held"):
            right.warning("Held: needs approval")
        elif status.startswith("Rejected"):
            right.error("Rejected")
        else:
            right.success("Sent")
        st.text(m["body"])
