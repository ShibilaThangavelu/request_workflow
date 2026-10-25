"""Talks to the n8n workflow (hosted on n8n Cloud). Uses only the standard library."""
import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def webhook_url():
    return os.getenv("N8N_WEBHOOK_URL", "").strip()


def enabled():
    return bool(webhook_url())


def reminder_override():
    """Optional demo setting: fire the follow-up reminder after N minutes instead of 2 hours."""
    value = os.getenv("N8N_REMINDER_MINUTES", "").strip()
    return float(value) if value else None


def _post(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def run_workflow(payload, timeout=120):
    """Send a request to the n8n workflow and return its result (steps, messages, priority...)."""
    return _post(webhook_url(), payload, timeout)


def notify_resolved(resume_url, timeout=20):
    """Resume the paused n8n run for a case with {resolved: true}, which cancels its follow-up reminder."""
    if resume_url:
        _post(resume_url, {"resolved": True}, timeout)


def send_email(to, subject, body, case_id=None, timeout=30):
    """Ask n8n to email a reply that a person has just approved."""
    url = os.getenv("N8N_EMAIL_URL", "").strip()
    if not url:
        base = webhook_url()
        if not base.endswith("/request-workflow"):
            raise RuntimeError("Set N8N_EMAIL_URL or use a webhook URL ending in /request-workflow")
        url = base[: -len("request-workflow")] + "send-email"
    _post(url, {"to": to, "subject": subject, "body": body, "case_id": case_id}, timeout)
