import sqlite3
import sys
from datetime import datetime, timedelta
from classifier import classify, draft_reply

DB_PATH = "cases.db"
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


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT, request TEXT, type TEXT, urgency TEXT,
                confidence REAL, reason TEXT, branch TEXT, steps TEXT, status TEXT)"""
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


def process_request(request):
    init_db()
    try:
        result = classify(request)
    except Exception as e:
        result = {"type": None, "urgency": None, "confidence": 0, "reason": "Classifier error: " + str(e)[:80]}

    valid = (
        result.get("type") in TYPES
        and result.get("urgency") in URGENCIES
        and isinstance(result.get("confidence"), (int, float))
    )
    if not valid or result["confidence"] < MIN_CONFIDENCE:
        branch, fn = "Needs Human Review", needs_human_review
    elif result["urgency"] == "high":
        branch, fn = "Urgent Escalation", urgent_escalation
    else:
        branch, fn = BRANCHES[result["type"]]

    reply = draft_reply(request, branch)
    steps, status = fn(request, reply)

    follow_up, hours = FOLLOW_UPS[branch]
    due = None
    if hours is not None:
        due = (datetime.now() + timedelta(hours=hours)).isoformat(timespec="minutes")
        steps.append("Set follow-up: " + follow_up + " (due " + due.replace("T", " ") + ")")
    else:
        steps.append("Follow-up: " + follow_up)

    case_id = log_case(request, result, branch, steps, status, reply, follow_up, due)
    return {
        "case_id": case_id, "branch": branch, "steps": steps, "status": status,
        "result": result, "reply": reply, "follow_up": follow_up, "follow_up_due": due,
    }


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "I was charged twice for my March bill."
    out = process_request(text)
    print(out["branch"], "| case", out["case_id"], "|", out["status"])
    for s in out["steps"]:
        print(" -", s)
    if out["reply"]:
        print("Draft reply:")
        print(out["reply"])
