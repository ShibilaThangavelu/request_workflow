import streamlit as st

from workflow.branches import pending_approvals, approve_reply, reject_reply

st.title("4. Approvals")
st.caption("Human in the loop. Replies for complaints and urgent cases are written by the AI but NOT sent "
           "until a person approves them. Edit the text if needed, then approve or reject.")

held = pending_approvals()
if not held:
    st.success("Nothing is waiting for approval.")
for h in held:
    with st.container(border=True):
        st.markdown(f"**Case #{h['case_id']}** | {h['branch']} | priority {h['priority']}  \n"
                    f"To: `{h['to_addr']}`  \nSubject: {h['subject']}")
        st.caption("Customer request: " + h["request"])
        edited = st.text_area("Draft reply (editable)", value=h["body"], key=f"draft_{h['outbox_id']}", height=140)
        a1, a2, _ = st.columns([1, 1, 4])
        if a1.button("Approve and send", key=f"ok_{h['outbox_id']}", type="primary"):
            approve_reply(h["outbox_id"], edited if edited != h["body"] else None)
            st.rerun()
        if a2.button("Reject", key=f"no_{h['outbox_id']}"):
            reject_reply(h["outbox_id"])
            st.rerun()
