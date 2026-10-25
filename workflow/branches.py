import os
import sqlite3
import sys
from datetime import datetime, timedelta
from workflow.classifier import classify, draft_reply

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cases.db")
MIN_CONFIDENCE = 0.7
TYPES = {"Complaint", "General Enquiry", "Service Request"}
URGENCIES = {"low", "medium", "high"}

# Follow-up action per branch: (description, hours until due or None)
FOLLOW_UPS = {
    "Complaint": ("Customer Care specialist contacts the customer within 2 business days", 48),
    "General Enquiry": ("No follow-up needed: resolved with an automatic reply", None),
    "Service Request": ("SLA timer: Service Desk actions the request within 1 business day", 24),
    "Urgent Escalation": ("2-hour follow-up by the priority team; automatic resolution paused", 2),
    "Needs Human Review": ("A human agent reviews the case within 4 hours", 4),
}

NEW_COLUMNS = {"draft_reply": "TEXT", "follow_up": "TEXT", "follow_up_due": "TEXT"}

# Team that receives a routing notification per branch: (display name, sample address)
TEAMS = {
    "Complaint": ("Customer Care Team", "customer-care@sample-company.example"),
    "Service Request": ("Service Desk", "service-desk@sample-company.example"),
    "Urgent Escalation": ("On-call Supervisor", "supervisor@sample-company.example"),
    "Needs Human Review": ("Human Review Queue", "human-review@sample-company.example"),
}


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT, request TEXT, type TEXT, urgency TEXT,
                confidence REAL, reason TEXT, branch TEXT, steps TEXT, status TEXT)"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER, created_at TEXT, kind TEXT, to_addr TEXT,
                subject TEXT, body TEXT, status TEXT)"""
        )
        existing = {row[1] for row in db.execute("PRAGMA table_info(cases)")}
        for column, kind in NEW_COLUMNS.items():
            if column not in existing:
                db.execute("ALTER TABLE cases ADD COLUMN " + column + " " + kind)


def log_case(request, result, branch, steps, status, reply, follow_up, due):
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO cases (created_at, request, type, urgency, confidence, reason, branch, steps, status, "
            "draft_reply, follow_up, follow_up_due) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), request, result.get("type"), result.get("urgency"),
             result.get("confidence"), result.get("reason"), branch, " | ".join(steps), status,
             reply, follow_up, due),
        )
        return cur.lastrowid


def send_message(case_id, kind, to_addr, subject, body):
    """Simulated send: the message is stored in the outbox table, nothing leaves the computer."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO outbox (case_id, created_at, kind, to_addr, subject, body, status) VALUES (?,?,?,?,?,?,?)",
            (case_id, datetime.now().isoformat(timespec="seconds"), kind, to_addr, subject, body, "Sent (simulated)"),
        )


def build_notification(case_id, branch, request, result, follow_up, due):
    conf = result.get("confidence")
    lines = [
        "Case #" + str(case_id) + " | " + branch,
        "Request: " + request,
        "Type: " + str(result.get("type")) + " | Urgency: " + str(result.get("urgency"))
        + " | Confidence: " + (f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"),
        "Model reason: " + str(result.get("reason")),
        "Action needed: " + follow_up + (" (due " + due.replace("T", " ") + ")" if due else ""),
    ]
    return "\n".join(lines)


def reply_step(reply, what):
    if reply:
        return "Generated " + what
    return "Could not generate a reply (API error); queued for a manual reply"


def complaint(request, reply):
    steps = [
        reply_step(reply, "a tailored apology and acknowledgement reply"),
        "Routed to the Customer Care team",
    ]
    return steps, "Open - Customer Care"


def general_enquiry(request, reply):
    steps = [
        reply_step(reply, "an answer from the FAQ knowledge base"),
        "Logged as resolved",
    ]
    return steps, "Answered - automatic reply"


def service_request(request, reply):
    steps = [
        reply_step(reply, "a confirmation reply that restates the request"),
        "Created a ticket and routed it to the Service Desk",
    ]
    return steps, "Open - Service Desk"


def urgent_escalation(request, reply):
    steps = [
        reply_step(reply, "an urgent acknowledgement reply"),
        "Flagged as Priority 1, alerted the on-call supervisor and paused automatic resolution",
    ]
    return steps, "Escalated - Priority 1"


def needs_human_review(request, reply):
    steps = [
        "Held all automatic actions because the classification was uncertain or invalid",
        "Queued for a human agent with the model's reason attached",
    ]
    return steps, "Waiting - Human Review"


BRANCHES = {
    "Complaint": ("Complaint", complaint),
    "General Enquiry": ("General Enquiry", general_enquiry),
    "Service Request": ("Service Request", service_request),
}


BRANCH_FUNCTIONS = {
    "Complaint": complaint,
    "General Enquiry": general_enquiry,
    "Service Request": service_request,
    "Urgent Escalation": urgent_escalation,
    "Needs Human Review": needs_human_review,
}


def route(result):
    """Decide the branch from a classification result (no API call, so it can be tested offline)."""
    valid = (
        result.get("type") in TYPES
        and result.get("urgency") in URGENCIES
        and isinstance(result.get("confidence"), (int, float))
    )
    if not valid or result["confidence"] < MIN_CONFIDENCE:
        return "Needs Human Review"
    if result["urgency"] == "high":
        return "Urgent Escalation"
    return result["type"]


def process_request(request, customer_email="customer@example.com"):
    init_db()
    try:
        result = classify(request)
    except Exception as e:
        result = {"type": None, "urgency": None, "confidence": 0, "reason": "Classifier error: " + str(e)[:80]}

    branch = route(result)
    fn = BRANCH_FUNCTIONS[branch]

    reply = draft_reply(request, branch)
    steps, status = fn(request, reply)

    team = TEAMS.get(branch)
    if reply:
        steps.append("Sent the reply to " + customer_email + " (simulated)")
    if team:
        steps.append("Sent a routing notification to " + team[0] + " (simulated)")

    follow_up, hours = FOLLOW_UPS[branch]
    due = None
    if hours is not None:
        due = (datetime.now() + timedelta(hours=hours)).isoformat(timespec="minutes")
        steps.append("Set follow-up: " + follow_up + " (due " + due.replace("T", " ") + ")")
    else:
        steps.append("Follow-up: " + follow_up)

    case_id = log_case(request, result, branch, steps, status, reply, follow_up, due)

    messages = []
    if reply:
        messages.append({"kind": "Customer reply", "to": customer_email,
                         "subject": "Re: your request (case #" + str(case_id) + ")", "body": reply})
    if team:
        messages.append({"kind": "Internal notification", "to": team[1],
                         "subject": "[" + branch + "] Case #" + str(case_id),
                         "body": build_notification(case_id, branch, request, result, follow_up, due)})
    for m in messages:
        send_message(case_id, m["kind"], m["to"], m["subject"], m["body"])

    return {
        "case_id": case_id, "branch": branch, "steps": steps, "status": status,
        "result": result, "reply": reply, "follow_up": follow_up, "follow_up_due": due,
        "messages": messages,
    }


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "I was charged twice for my March bill."
    out = process_request(text)
    print(out["branch"], "| case", out["case_id"], "|", out["status"])
    for s in out["steps"]:
        print(" -", s)
    for m in out["messages"]:
        print("--", m["kind"], "to", m["to"], "|", m["subject"])
        print(m["body"])
