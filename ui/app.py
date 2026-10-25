import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from workflow.branches import init_db, check_reminders

st.set_page_config(page_title="Request Workflow", layout="wide")
init_db()

# reminders that are already due fire automatically whenever a page loads
fired = check_reminders()
if fired:
    st.toast(f"{len(fired)} follow-up reminder(s) fired. See the Team inbox.")

pages = [
    st.Page("views/submit.py", title="1. Submit a request", default=True),
    st.Page("views/customer_inbox.py", title="2. Customer inbox"),
    st.Page("views/team_inbox.py", title="3. Team inbox"),
    st.Page("views/approvals.py", title="4. Approvals"),
    st.Page("views/follow_ups.py", title="5. Follow-ups"),
    st.Page("views/dashboard.py", title="6. Dashboard"),
]
page = st.navigation(pages)

with st.sidebar:
    st.divider()
    st.caption(
        "Incoming Request Processing Workflow. Submit a request, then follow it: what the customer "
        "receives, what the team receives, what a person must approve, and what is overdue. "
        "Sending is simulated: nothing is emailed."
    )

page.run()
