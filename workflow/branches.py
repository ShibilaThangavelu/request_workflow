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
    "Complaint": ("2-hour reminder: senior handler checks the complaint is being resolved", 2),
    "General Enquiry": ("No follow-up needed: resolved with an automatic reply", None),
    "Service Request": ("SLA timer: Service Desk actions the request within 1 business day", 24),
    "Urgent Escalation": ("2-hour follow-up by the priority team; automatic resolution paused", 2),
    "Needs Human Review": ("A human agent reviews the case within 4 hours", 4),
}

NEW_COLUMNS = {"draft_reply": "TEXT", "follow_up": "TEXT", "follow_up_due": "TEXT", "priority": "TEXT",
               "approval_status": "TEXT", "reminder_sent": "INTEGER DEFAULT 0", "resolved_at": "TEXT"}

# Branches whose customer reply is held until a person approves it (human in the loop)
APPROVAL_BRANCHES = {"Urgent Escalation"}

# Branches that get a drafted customer update when their 2-hour reminder fires (held for approval)
REMINDER_UPDATE_BRANCHES = {"Complaint", "Urgent Escalation"}

# Priority flag set on the case log entry, following the urgency column in the brief
PRIORITY = {
    "Complaint": "High",
    "General Enquiry": "Low",
    "Service Request": "Medium",
    "Urgent Escalation": "Critical",
    "Needs Human Review": "Pending review",
}

# Team that receives a routing notification per branch: (display name, sample address)
SUPERVISOR = ("On-call Supervisor", "supervisor@sample-company.example")

TEAMS = {
    "Complaint": ("Senior Handler", "senior-handler@sample-company.example"),
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


def log_case(request, result, branch, steps, status, reply, follow_up, due, priority, approval_status):
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO cases (created_at, request, type, urgency, confidence, reason, branch, steps, status, "
            "draft_reply, follow_up, follow_up_due, priority, approval_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), request, result.get("type"), result.get("urgency"),
             result.get("confidence"), result.get("reason"), branch, " | ".join(steps), status,
             reply, follow_up, due, priority, approval_status),
        )
        return cur.lastrowid


def send_message(case_id, kind, to_addr, subject, body, status="Sent (simulated)"):
    """Simulated send: the message is stored in the outbox table, nothing leaves the computer."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO outbox (case_id, created_at, kind, to_addr, subject, body, status) VALUES (?,?,?,?,?,?,?)",
            (case_id, datetime.now().isoformat(timespec="seconds"), kind, to_addr, subject, body, status),
        )


def build_notification(case_id, branch, request, result, follow_up, due, priority, ack=""):
    conf = result.get("confidence")
    lines = [
        "Case #" + str(case_id) + " | " + branch + " | PRIORITY: " + priority,
        "Request: " + request,
        "Type: " + str(result.get("type")) + " | Urgency: " + str(result.get("urgency"))
        + " | Confidence: " + (f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"),
        "Model reason: " + str(result.get("reason")),
        *(["Customer acknowledgement: " + ack] if ack else []),
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
        "Escalated to a senior handler",
        "Logged the case with a High priority flag",
    ]
    return steps, "Escalated - Senior Handler"


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
    needs_approval = branch in APPROVAL_BRANCHES and bool(reply)
    if reply and needs_approval:
        steps.append("Held the reply for human approval (not sent yet)")
    elif reply:
        steps.append("Sent the reply to " + customer_email + " (simulated)")
    if team:
        steps.append("Sent a routing notification to " + team[0] + " (simulated)")

    priority = PRIORITY[branch]
    follow_up, hours = FOLLOW_UPS[branch]
    due = None
    if hours is not None:
        due = (datetime.now() + timedelta(hours=hours)).isoformat(timespec="minutes")
        steps.append("Set follow-up: " + follow_up + " (due " + due.replace("T", " ") + ")")
    else:
        steps.append("Follow-up: " + follow_up)

    approval_status = "Pending approval" if needs_approval else "Not required"
    if not reply:
        ack_note = ""
    elif needs_approval:
        ack_note = "drafted, held for human approval (not yet sent)"
    else:
        ack_note = "sent to " + customer_email + " (simulated)"
    case_id = log_case(request, result, branch, steps, status, reply, follow_up, due, priority, approval_status)

    messages = []
    if reply:
        messages.append({"kind": "Customer reply", "to": customer_email,
                         "subject": "Re: your request (case #" + str(case_id) + ")", "body": reply,
                         "status": "Held - awaiting approval" if needs_approval else "Sent (simulated)"})
    if team:
        messages.append({"kind": "Internal notification", "to": team[1],
                         "subject": "[" + branch + "] Case #" + str(case_id),
                         "body": build_notification(case_id, branch, request, result, follow_up, due, priority, ack_note),
                         "status": "Sent (simulated)"})
    for m in messages:
        send_message(case_id, m["kind"], m["to"], m["subject"], m["body"], m["status"])

    return {
        "case_id": case_id, "branch": branch, "steps": steps, "status": status,
        "result": result, "reply": reply, "follow_up": follow_up, "follow_up_due": due,
        "messages": messages, "priority": priority, "needs_approval": needs_approval,
        "case_log": {
            "case_id": case_id, "logged_at": datetime.now().isoformat(timespec="seconds"),
            "branch": branch, "type": result.get("type"), "urgency": result.get("urgency"),
            "priority": priority, "status": status, "follow_up": follow_up, "follow_up_due": due,
        },
    }


# ---------- human approval ----------
def pending_approvals():
    """Customer replies that are held until a person approves them."""
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT o.id, o.case_id, c.branch, c.priority, c.request, o.to_addr, o.subject, o.body "
            "FROM outbox o JOIN cases c ON c.id = o.case_id "
            "WHERE o.status = 'Held - awaiting approval' ORDER BY o.id"
        ).fetchall()
    keys = ["outbox_id", "case_id", "branch", "priority", "request", "to_addr", "subject", "body"]
    return [dict(zip(keys, r)) for r in rows]


def approve_reply(outbox_id, edited_body=None):
    """Release a held reply (optionally edited) so it is 'sent' (simulated)."""
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT case_id, kind FROM outbox WHERE id = ?", (outbox_id,)).fetchone()
        if not row:
            return
        body = edited_body.strip() if edited_body and edited_body.strip() else None
        if body:
            db.execute("UPDATE outbox SET body = ?, status = 'Sent (simulated) - approved and edited' WHERE id = ?",
                       (body, outbox_id))
        else:
            db.execute("UPDATE outbox SET status = 'Sent (simulated) - approved' WHERE id = ?", (outbox_id,))
        if row[1] == "Customer reply":
            db.execute("UPDATE cases SET approval_status = 'Approved', "
                       "steps = steps || ' | A person approved the reply and it was sent (simulated)' WHERE id = ?",
                       (row[0],))


def reject_reply(outbox_id):
    """Block a held reply: it is not sent and the case is flagged for manual handling."""
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT case_id, kind FROM outbox WHERE id = ?", (outbox_id,)).fetchone()
        if not row:
            return
        db.execute("UPDATE outbox SET status = 'Rejected - not sent' WHERE id = ?", (outbox_id,))
        if row[1] == "Customer reply":
            db.execute("UPDATE cases SET approval_status = 'Rejected', "
                       "steps = steps || ' | A person rejected the AI reply: handle manually' WHERE id = ?",
                       (row[0],))


# ---------- follow-up reminders and resolving ----------
def resolve_case(case_id):
    """Close a case so no more reminders fire for it."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("UPDATE cases SET resolved_at = ?, status = 'Resolved' WHERE id = ?",
                   (datetime.now().isoformat(timespec="seconds"), case_id))


def check_reminders(extra_hours=0):
    """Fire reminders for open cases whose follow-up time has passed.

    For each overdue case this sends an escalation notification to the supervisor and, for complaints
    and urgent cases, queues an AI-drafted update to the customer (held for approval).
    extra_hours moves the clock forward so a demo can show a 2-hour reminder without waiting.
    Returns a list of the cases that fired.
    """
    init_db()
    cutoff = (datetime.now() + timedelta(hours=extra_hours)).isoformat(timespec="minutes")
    with sqlite3.connect(DB_PATH) as db:
        due = db.execute(
            "SELECT id, branch, request, priority, follow_up, follow_up_due FROM cases "
            "WHERE follow_up_due IS NOT NULL AND follow_up_due <= ? "
            "AND COALESCE(reminder_sent, 0) = 0 AND resolved_at IS NULL ORDER BY id",
            (cutoff,),
        ).fetchall()
        if not due:
            return []
        cust = {r[0]: r[1] for r in db.execute(
            "SELECT case_id, to_addr FROM outbox WHERE kind = 'Customer reply'")}
    fired = []
    for case_id, branch, request, priority, follow_up, follow_up_due in due:
        body = "\n".join([
            "OVERDUE FOLLOW-UP | Case #" + str(case_id) + " | " + branch + " | PRIORITY: " + priority,
            "Request: " + request,
            "Follow-up that was due: " + follow_up + " (due " + follow_up_due.replace("T", " ") + ")",
            "Action needed: check the case now. It is not yet resolved.",
        ])
        send_message(case_id, "Escalation reminder", SUPERVISOR[1],
                     "[REMINDER] Case #" + str(case_id) + " is overdue (" + branch + ")", body)
        update = None
        if branch in REMINDER_UPDATE_BRANCHES:
            update = draft_reply(request, "Reminder")
            if update:
                send_message(case_id, "Customer update (draft)", cust.get(case_id, "customer@example.com"),
                             "Update on your request (case #" + str(case_id) + ")", update,
                             "Held - awaiting approval")
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "UPDATE cases SET reminder_sent = 1, steps = steps || ? WHERE id = ?",
                (" | Reminder fired: escalation notification sent to the supervisor"
                 + (" and a draft customer update queued for approval" if update else ""), case_id),
            )
        fired.append({"case_id": case_id, "branch": branch, "customer_update_drafted": bool(update)})
    return fired


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "I was charged twice for my March bill."
    out = process_request(text)
    print(out["branch"], "| case", out["case_id"], "|", out["status"])
    for s in out["steps"]:
        print(" -", s)
    for m in out["messages"]:
        print("--", m["kind"], "to", m["to"], "|", m["subject"])
        print(m["body"])
