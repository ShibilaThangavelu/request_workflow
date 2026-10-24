# Incoming Request Processing Workflow

A prototype that reads a customer request, classifies its type and urgency with Gemini, runs a branch-specific remediation workflow, drafts a tailored reply, sets a follow-up and logs the case. Built for the Firstsource Consultant (AI & Analytics) POC, Pro-Code track.

Repo: https://github.com/ShibilaThangavelu/request_workflow | Demo recording: [add link]

## Workflow design
1. A request is entered in the Streamlit form (`app.py`) or on the command line.
2. `classifier.py` asks Gemini for JSON: `type`, `urgency`, `confidence`, `reason` (temperature 0).
3. `branches.py` validates the answer. Invalid output, an API error or confidence below 0.7 goes to **Needs Human Review**.
4. Otherwise `urgency = high` goes to **Urgent Escalation**; everything else goes to the branch for its type.
5. The branch generates a tailored reply (second Gemini call), runs its steps, sets a follow-up and writes the case to SQLite (`cases.db`).

## Classification logic
- **Complaint:** the customer is unhappy about something that went wrong. **General Enquiry:** asks for information. **Service Request:** asks us to do or change something.
- **Urgency:** high = fraud, a stolen card, loss of service or account access, or "immediately". Medium = a recurring or unresolved problem. Low = questions, routine changes, minor annoyances.
- Vague messages should get confidence below 0.6, which triggers human review.

## Remediation strategy
| Branch | Steps | Follow-up |
| --- | --- | --- |
| Complaint | Tailored apology reply; route to Customer Care | Specialist contact within 2 business days |
| General Enquiry | Answer from a sample FAQ (`faq.txt`); log as resolved | None |
| Service Request | Confirmation reply restating the request; create ticket and route to Service Desk | SLA timer, 1 business day |
| Urgent Escalation | Urgent acknowledgement; flag Priority 1, alert supervisor, pause auto-resolution | 2-hour follow-up |
| Needs Human Review | Hold automatic actions; queue for a human with the model's reason | Review within 4 hours |

Replies and routing are simulated: nothing is actually sent. The FAQ is made-up sample content.

## Tools used
Python, Google Gemini (`gemini-3.5-flash-lite`) via `google-genai`, Streamlit, SQLite, pandas. Built with AI assistance (Claude) for guidance and documentation.

## Setup and run
```
python3 -m venv .venv && source .venv/bin/activate
pip install streamlit pandas python-dotenv google-genai
echo "GEMINI_API_KEY=your-key" > .env      # key from aistudio.google.com
streamlit run app.py                        # web interface
python branches.py "your request"           # command line
python evaluate.py dev|test                 # accuracy on labelled requests
```

## One end-to-end example per branch (real output)
| Input | Branch and actions | Draft reply (start) |
| --- | --- | --- |
| "I was charged twice for my March bill and nobody has fixed it after three calls." | Complaint: reply drafted, routed to Customer Care, follow-up in 2 business days | "We are very sorry to hear that you were charged twice... A Customer Care specialist will contact you within 2 business days" |
| "Do you offer a student discount on your plans?" | General Enquiry: answered from FAQ, logged as resolved | "Students get 10% off any plan with a valid student ID." |
| "Please update my address to 12 Smith Street, Richmond VIC 3121." | Service Request: ticket created, routed to Service Desk, SLA 1 business day | "We have received your request to update your address to 12 Smith Street, Richmond VIC 3121." |
| "My card was stolen an hour ago. Please block it immediately." | Urgent Escalation: Priority 1, supervisor alerted, 2-hour follow-up | "Your case has been escalated to our priority team, and someone will contact you within 2 hours" |
| "Hi, about my thing from last week" | Needs Human Review: automatic actions held, review within 4 hours | No automatic reply |

## Results
24 synthetic labelled requests (`requests.csv`, written with AI help, no real data): 16 dev and 8 held-out test.
- Dev: 15/16 on type, 15/16 on urgency (measured before the confidence rules were added to the prompt).
- Held-out test, run once: 7/8 on type, 6/8 on urgency. The type miss was `ServiceRequest` (no space), which validation sends to human review.
- The sample is small, so treat these as rough indications.

## Limitations and next steps
Confidence is self-reported and often high even when wrong; the 0.7 threshold is untuned. Next: real email and ticketing integration, more labelled data, human approval of drafted replies.
