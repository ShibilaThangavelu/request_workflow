# Incoming Request Processing Workflow

An AI prototype that receives incoming customer requests, classifies each one by **type** and **urgency**, and runs a different multi-step remediation workflow for each type: routing, drafting a tailored reply, notifying the right team, logging, follow-up reminders, and human approval where the risk is high.

Built for the Firstsource Consultant (AI & Analytics) 5-day POC. Scope is deliberately narrow: three request types plus urgent and uncertain handling, working reliably from request to delivery.

Repo: https://github.com/ShibilaThangavelu/request_workflow | Demo: [add link]

## Overview

A request comes in (Streamlit form or command line), and the system:

1. **Classifies** it into a type and urgency with Gemini, returning JSON `{type, urgency, confidence, reason}`
2. **Branches** on that result and runs the steps for that branch
3. **Delivers** the result: a Slack notification to the right team and an email reply to the customer (Mailtrap sandbox)
4. **Logs** every case, with priority flag, follow-up due time and status, and shows it in the app

```
Streamlit form / CLI
        |
        v   POST webhook
   n8n workflow  --> Gemini classify --> Validate and route (Switch)
        |                                   |
        |      +------------+---------------+-----------------+----------------+
        |      v            v               v                 v                v
        |  Complaint   General Enquiry  Service Request  Urgent Escalation  Needs Human Review
        |      \            |               |                 |                /
        |       +-----> draft reply (Gemini) -> Slack team notification -> customer email*
        |                                   |
        |                       Wait until follow-up is due --> Slack reminder
        v
 Streamlit app: case log (SQLite), customer and team inboxes, approvals, follow-ups, dashboard
 (* Urgent Escalation replies are emailed only after a person approves them)
```

**Why this split:** n8n owns orchestration (branching, Slack, email, waiting for the follow-up time). The Streamlit app owns the front end, the case log and human approval. If n8n is not configured, the app runs the same logic in Python (`workflow/branches.py`) so the demo still works.

## The branches

| Branch | When | Automated steps | Priority and follow-up | Approval |
| --- | --- | --- | --- | --- |
| **Complaint** | Unhappy about something that went wrong | Tailored apology and acknowledgement emailed; escalated to a senior handler (Slack); case logged | High; 2-hour reminder | No, sent immediately |
| **General Enquiry** | Asks for information | Sub-topic classified; answer drafted from the FAQ and emailed; logged as Resolved | Low; none | No |
| **Service Request** | Asks us to do or change something | Request details extracted; routed to a department (Billing, Account Services, Technical Support, Plan Changes, Service Desk); confirmation emailed; ticket created | Medium; 1 business day SLA timer | No |
| **Urgent Escalation** | Urgency is high (fraud, stolen card, loss of service) | Urgent acknowledgement drafted; on-call supervisor alerted (Slack); Priority 1 flag; automatic resolution paused | Critical; 2 hours | **Yes**, reply held until approved, edited or rejected |
| **Needs Human Review** | Invalid output, API error or confidence below 0.7 | All automatic actions held; queued for a person with the model's reason | Pending review; 4 hours | n/a |

**Reminders:** when a follow-up time passes and the case is not resolved, n8n sends an escalation notice to the supervisor; for Complaint and Urgent cases it also drafts a customer update held for approval. Marking a case resolved in the app resumes the waiting n8n run and cancels the reminder.

**Classification rules:** urgency `high` always overrides type and goes to Urgent Escalation. Vague messages get low confidence and go to a human instead of guessing.

## Project structure

```
n8n/
  request_workflow.n8n.json   Workflow to import into n8n (Webhook, Gemini, Switch, Slack, Email, Wait)
  SETUP.md                    Credentials, Slack channel, Mailtrap, connecting the app
workflow/
  classifier.py               Gemini prompts: classify, tailored reply, FAQ enquiry, service request routing
  branches.py                 Routing rules, branch functions, SQLite case log, follow-ups, approvals
  n8n_client.py               App side of the n8n connection (run workflow, send email, resolve case)
ui/
  app.py                      Streamlit router
  views/                      1 Submit, 2 Customer inbox, 3 Team inbox, 4 Approvals, 5 Follow-ups, 6 Dashboard
evaluation/                   evaluate.py, evaluate_branches.py, generate_samples.py, test_gemini.py
data/
  requests.csv, edge_cases.csv  Labelled test requests (24 and 30)
  faq.txt                       Sample FAQ for the enquiry branch
  sample_inputs/                One sample request per branch (.txt and .json)
  sample_outputs/               The workflow's JSON output for each sample
  results/                      Evaluation outputs
screenshots/                  Output screenshots per branch (Slack, Mailtrap, n8n canvas, app)
```

## Setup

Prerequisites: Python 3.11+, a [Gemini API key](https://ai.google.dev), and (for the full demo) an n8n Cloud account, a Slack workspace and a Mailtrap sandbox inbox.

### 1. App

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set GEMINI_API_KEY
streamlit run ui/app.py
```

With no `N8N_WEBHOOK_URL` the sidebar shows "Engine: local Python" and everything runs locally (messages are simulated).

### 2. n8n (Slack and email)

1. Import `n8n/request_workflow.n8n.json` into n8n Cloud
2. Add credentials: Gemini API key (6 HTTP nodes), Slack access token (2 Slack nodes), SMTP for Mailtrap (2 email nodes)
3. Make sure the Slack channel name in the Slack nodes matches a channel your bot has joined
4. Publish the workflow, copy its **Production** webhook URL into `.env` as `N8N_WEBHOOK_URL`
5. Restart the app. The sidebar now shows "Engine: n8n workflow"

Full steps are in [`n8n/SETUP.md`](n8n/SETUP.md). Optional: `N8N_REMINDER_MINUTES=1` shortens the follow-up wait for demos.

### 3. Evaluate

```bash
python evaluation/evaluate.py test            # 24 labelled requests
python evaluation/evaluate_branches.py        # 30 harder cases through full routing
```

## Sample inputs and outputs

One example per branch. Each input is a JSON request in [`data/sample_inputs/`](data/sample_inputs); each output is the JSON the workflow returned, in [`data/sample_outputs/`](data/sample_outputs) (shown here trimmed to the key fields). They were produced by `python evaluation/generate_samples.py` with the local engine and a real Gemini call, so no Slack or email was sent. With n8n connected, the same result comes back from the webhook and the messages are actually delivered. Screenshots of the app, Slack, Mailtrap and the n8n run are in [`screenshots/`](screenshots).

| Branch | Input file | Full output file |
| --- | --- | --- |
| General Enquiry | [`01_general_enquiry.json`](data/sample_inputs/01_general_enquiry.json) | [`01_general_enquiry.json`](data/sample_outputs/01_general_enquiry.json) |
| Service Request | [`02_service_request.json`](data/sample_inputs/02_service_request.json) | [`02_service_request.json`](data/sample_outputs/02_service_request.json) |
| Complaint | [`03_complaint.json`](data/sample_inputs/03_complaint.json) | [`03_complaint.json`](data/sample_outputs/03_complaint.json) |
| Urgent Escalation | [`04_urgent_escalation.json`](data/sample_inputs/04_urgent_escalation.json) | [`04_urgent_escalation.json`](data/sample_outputs/04_urgent_escalation.json) |
| Needs Human Review | [`05_needs_human_review.json`](data/sample_inputs/05_needs_human_review.json) | [`05_needs_human_review.json`](data/sample_outputs/05_needs_human_review.json) |

### General Enquiry

**Input**

```json
{
  "request": "Do you offer a student discount on your plans?",
  "customer_email": "customer@example.com"
}
```

**Output (trimmed)**

```json
{
  "branch": "General Enquiry",
  "status": "Resolved",
  "priority": "Low",
  "classification": {
    "type": "General Enquiry",
    "urgency": "low",
    "confidence": 0.95,
    "reason": "The customer is asking for information about student discounts without requesting any changes to their account."
  },
  "subtopic": "student discount",
  "needs_approval": false,
  "steps": [
    "Classified the sub-topic: student discount",
    "Generated an answer from the FAQ knowledge base",
    "Logged as resolved",
    "Sent the reply to customer@example.com (simulated)",
    "Follow-up: No follow-up needed: resolved with an automatic reply"
  ],
  "reply": "Hi,\n\nYes, students get 10% off any plan with a valid student ID.\n\nCustomer Care Team",
  "follow_up": "No follow-up needed: resolved with an automatic reply"
}
```

### Service Request

**Input**

```json
{
  "request": "Please update my address to 12 Smith Street, Richmond VIC 3121.",
  "customer_email": "customer@example.com"
}
```

**Output (trimmed)**

```json
{
  "branch": "Service Request",
  "status": "Open - Account Services",
  "priority": "Medium",
  "classification": {
    "type": "Service Request",
    "urgency": "low",
    "confidence": 0.95,
    "reason": "The customer is asking to update their address on their account."
  },
  "department": "Account Services",
  "needs_approval": false,
  "steps": [
    "Extracted the request details: The customer wants to update their address to 12 Smith Street, Richmond VIC 3121.",
    "Generated a confirmation reply that restates the request",
    "Created a ticket and routed it to the Account Services team",
    "Sent the reply to customer@example.com (simulated)",
    "Sent a routing notification to Account Services (simulated)",
    "Set follow-up: SLA timer: the department actions the request within 1 business day (due 2026-10-26 13:16)"
  ],
  "reply": "Hi, we received your request to update your address to 12 Smith Street, Richmond VIC 3121. This has been passed to our Account Services team and will be actioned within 1 business day. Customer Care Team",
  "follow_up": "SLA timer: the department actions the request within 1 business day"
}
```

### Complaint

**Input**

```json
{
  "request": "I was charged twice for my March bill and nobody has fixed it after three calls.",
  "customer_email": "customer@example.com"
}
```

**Output (trimmed)**

```json
{
  "branch": "Complaint",
  "status": "Escalated - Senior Handler",
  "priority": "High",
  "classification": {
    "type": "Complaint",
    "urgency": "medium",
    "confidence": 0.95,
    "reason": "The customer is unhappy about a billing error that was not fixed after multiple previous contacts."
  },
  "needs_approval": false,
  "steps": [
    "Generated a tailored apology and acknowledgement reply",
    "Escalated to a senior handler",
    "Logged the case with a High priority flag",
    "Sent the reply to customer@example.com (simulated)",
    "Sent a routing notification to Senior Handler (simulated)",
    "Set follow-up: 2-hour reminder: senior handler checks the complaint is being resolved (due 2026-10-25 15:17)"
  ],
  "reply": "Hi,\n\nI am so sorry to hear you were charged twice for your March bill and that this has not been fixed after three calls. We have received your complaint and understand how frustrating this is. \n\nI have now passed this on to a senior member of our team, who will follow up with you.\n\nCustomer Care Team",
  "follow_up": "2-hour reminder: senior handler checks the complaint is being resolved"
}
```

### Urgent Escalation

**Input**

```json
{
  "request": "My card was stolen an hour ago. Please block it immediately.",
  "customer_email": "customer@example.com"
}
```

**Output (trimmed)**

```json
{
  "branch": "Urgent Escalation",
  "status": "Escalated - Priority 1",
  "priority": "Critical",
  "classification": {
    "type": "Service Request",
    "urgency": "high",
    "confidence": 0.95,
    "reason": "The customer is requesting an immediate card block due to a theft that occurred an hour ago."
  },
  "needs_approval": true,
  "steps": [
    "Generated an urgent acknowledgement reply",
    "Flagged as Priority 1, alerted the on-call supervisor and paused automatic resolution",
    "Held the reply for human approval (not sent yet)",
    "Sent a routing notification to On-call Supervisor (simulated)",
    "Set follow-up: 2-hour follow-up by the priority team; automatic resolution paused (due 2026-10-25 15:17)"
  ],
  "reply": "Hi,\n\nI understand this is very urgent, and I am sorry to hear your card was stolen. \n\nWe have escalated your case to our priority team right away. Someone will contact you within 2 hours to help secure your account. \n\nCustomer Care Team",
  "follow_up": "2-hour follow-up by the priority team; automatic resolution paused"
}
```

### Needs Human Review

**Input**

```json
{
  "request": "Hi, about my thing from last week",
  "customer_email": "customer@example.com"
}
```

**Output (trimmed)**

```json
{
  "branch": "Needs Human Review",
  "status": "Waiting - Human Review",
  "priority": "Pending review",
  "classification": {
    "type": "General Enquiry",
    "urgency": "low",
    "confidence": 0.4,
    "reason": "The message is too vague to determine what the customer is asking about."
  },
  "needs_approval": false,
  "steps": [
    "Held all automatic actions because the classification was uncertain or invalid",
    "Queued for a human agent with the model's reason attached",
    "Sent a routing notification to Human Review Queue (simulated)",
    "Set follow-up: A human agent reviews the case within 4 hours (due 2026-10-25 17:18)"
  ],
  "reply": null,
  "follow_up": "A human agent reviews the case within 4 hours"
}
```

## Results

24 synthetic labelled requests (AI-assisted, no real data): dev 15/16 type and urgency (measured before the confidence rules were added); held-out test, run once, 7/8 type and 6/8 urgency. Stress test of 30 harder requests (`data/edge_cases.csv`, labelled before running and run once): **28/30 sent to the right branch (93%)**, and 7 of 8 vague or mixed messages were correctly held for a person. Both misses went to a wrong automatic branch: a casual complaint about being charged twice went to Urgent Escalation, and "Thanks, that fixed it!" went to General Enquiry. Details in `data/results/results_edge.csv`.

## Known limitations

- **Small, synthetic test set.** The accuracy numbers are rough indications, not guarantees.
- **Confidence is self-reported** by the model, often high when it is wrong, and the 0.7 threshold is untuned.
- **FAQ is made-up sample content** and is passed to the model as text; there is no vector database or retrieval step yet.
- **Mailtrap is a sandbox.** Customer emails land in a test inbox, not real ones. In local mode, sending is simulated.
- **Reminder timing** depends on the n8n run staying active; short demo waits are set with `N8N_REMINDER_MINUTES`.
- **Next steps:** retrieval over a real knowledge base (vector database), real ticketing integration, a larger labelled set, and tuning the confidence threshold.

## Tools

Python, Gemini (`gemini-3.5-flash-lite`), n8n Cloud, Slack, Mailtrap, Streamlit, SQLite, pandas. Built with AI assistance (Claude).
