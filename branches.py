import sqlite3
import sys
from datetime import datetime
from classifier import classify

DB_PATH = "cases.db"
MIN_CONFIDENCE = 0.7
TYPES = {"Complaint", "General Enquiry", "Service Request"}
URGENCIES = {"low", "medium", "high"}


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT, request TEXT, type TEXT, urgency TEXT,
                confidence REAL, reason TEXT, branch TEXT, steps TEXT, status TEXT)"""
        )


def log_case(request, result, branch, steps, status):
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO cases (created_at, request, type, urgency, confidence, reason, branch, steps, status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), request, result.get("type"), result.get("urgency"),
             result.get("confidence"), result.get("reason"), branch, " | ".join(steps), status),
        )
        return cur.lastrowid


def complaint(request, result):
    steps = [
        "Drafted an apology reply: 'We are sorry about this. A Customer Care specialist will contact you within 2 business days.'",
        "Routed to the Customer Care team (target: 2 business days)",
    ]
    return steps, "Open - Customer Care"


def general_enquiry(request, result):
    steps = [
        "Drafted an answer from the FAQ template and sent it to the customer",
        "Suggested the Help Centre article that matches the question",
    ]
    return steps, "Answered - automatic reply"


def service_request(request, result):
    steps = [
        "Created a service ticket for: " + request[:60],
        "Sent a confirmation: 'We have received your request and will action it within 1 business day.'",
    ]
    return steps, "Open - Service Desk"


def urgent_escalation(request, result):
    steps = [
        "Flagged as Priority 1 and alerted the on-call team",
        "Sent a holding message: 'We have escalated this and someone will contact you shortly.'",
    ]
    return steps, "Escalated - Priority 1"


def needs_human_review(request, result):
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

    steps, status = fn(request, result)
    case_id = log_case(request, result, branch, steps, status)
    return {"case_id": case_id, "branch": branch, "steps": steps, "status": status, "result": result}


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "I was charged twice for my March bill."
    out = process_request(text)
    print(out["branch"], "| case", out["case_id"], "|", out["status"])
    for s in out["steps"]:
        print(" -", s)