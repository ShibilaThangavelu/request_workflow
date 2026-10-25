import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()
MODEL = "gemini-3.5-flash-lite"

PROMPT = """You classify customer requests for a service company.
Return JSON with exactly these fields:
- type: one of "Complaint", "General Enquiry", "Service Request"
- urgency: one of "low", "medium", "high"
- confidence: a number from 0 to 1
- reason: one short sentence

Definitions:
- Complaint: the customer is unhappy about something that went wrong.
- General Enquiry: the customer asks for information. Nothing needs to be done on their account.
- Service Request: the customer asks us to do or change something on their account.
Urgency rules:
- high: fraud or money taken without permission, a lost or stolen card, a complete loss of service or account access, or the customer says they need action immediately or today.
- medium: a problem that has gone on for days, happened more than once, or was not fixed after earlier contact, but the customer can still use the service. Also requests tied to a deadline or an upcoming trip.
- low: general questions, routine changes, and minor annoyances.
Do not use high for a bad experience alone. Anger or disappointment does not make a request high.
Confidence rules:
- Use 0.9 or higher only when the request clearly fits exactly one type.
- If the message is vague, has no clear request, or could fit more than one type, use a confidence below 0.6.

Request: {text}
"""

def classify(text):
    response = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(text=text),
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(response.text)

FAQ_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faq.txt")
try:
    FAQ = open(FAQ_PATH).read()
except OSError:
    FAQ = ""

REPLY_PROMPT = """You write short customer replies for an operations team.
Write one reply of at most 70 words to the customer request below.
Rules:
- Polite, plain language. Start with "Hi," and end with "Customer Care Team".
- What the reply must do: {instruction}
- Do not invent facts, names, prices or timeframes that are not in these instructions or the FAQ.

Customer request: {text}
{extra}"""

REPLY_INSTRUCTIONS = {
    "Complaint": "Apologise, show you understand the specific problem, confirm you received the complaint, and say it has been passed to a senior member of the team who will follow up. Do not give a timeframe.",
    "General Enquiry": "Answer using only the FAQ below. If the FAQ does not cover the question, say a team member will confirm the answer by email.",
    "Service Request": "Confirm you received the request, restate what they asked for using only their own words (add no details they did not give), and say it will be actioned within 1 business day.",
    "Reminder": "Apologise for the wait, say the case is still open and a senior member of the team is following it up, and say they will hear from the team again soon. Do not give a timeframe.",
    "Urgent Escalation": "Acknowledge the urgency, say the case has been escalated to a priority team, and say someone will contact them within 2 hours.",
}


def draft_reply(text, branch):
    """Return a short tailored reply for the branch, or None if no reply applies or the API fails."""
    if branch not in REPLY_INSTRUCTIONS:
        return None
    extra = ("FAQ:\n" + FAQ) if branch == "General Enquiry" else ""
    prompt = REPLY_PROMPT.format(instruction=REPLY_INSTRUCTIONS[branch], text=text, extra=extra)
    try:
        response = client.models.generate_content(
            model=MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text.strip()
    except Exception:
        return None


ENQUIRY_PROMPT = """You answer customer enquiries for a service company.
Customer enquiry: {text}

FAQ:
{faq}

Return JSON with exactly these fields:
- subtopic: 2 to 4 words naming what the enquiry is about, for example "student discount", "billing statements", "opening hours"
- reply: one customer reply of at most 70 words. Polite, plain language. Start with "Hi," and end with "Customer Care Team". Answer using only the FAQ above. If the FAQ does not cover the question, say a team member will confirm the answer by email. Do not invent facts, names, prices or timeframes."""


def draft_enquiry(text):
    """Classify the enquiry's sub-topic and draft an FAQ-based reply in one call.

    Returns (subtopic, reply); either is None if the API call or the JSON fails.
    """
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=ENQUIRY_PROMPT.format(text=text, faq=FAQ),
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3),
        )
        data = json.loads(response.text)
        subtopic = str(data.get("subtopic") or "").strip() or None
        reply = str(data.get("reply") or "").strip() or None
        return subtopic, reply
    except Exception:
        return None, None


DEPARTMENTS = ["Billing", "Account Services", "Technical Support", "Plan Changes", "Service Desk"]

SERVICE_PROMPT = """You triage service requests for a service company's operations team.
Customer request: {text}

Return JSON with exactly these fields:
- summary: one sentence stating what the customer wants done, including every specific detail they gave (for example a new address or a date). Add no details they did not give.
- department: exactly one of: Billing, Account Services, Technical Support, Plan Changes, Service Desk. Billing is for payments, invoices and refunds. Account Services is for changing personal or account details. Technical Support is for faults and setup help. Plan Changes is for upgrading, downgrading or cancelling a plan. Service Desk is for anything else.
- reply: one customer reply of at most 70 words. Polite, plain language. Start with "Hi," and end with "Customer Care Team". Confirm you received the request, restate what they asked for using only their own words, say it has been passed to the department you chose, and say it will be actioned within 1 business day. Do not invent facts, names, prices or timeframes."""


def draft_service_request(text):
    """Extract the request details, choose the department and draft the confirmation in one call.

    Returns (summary, department, reply); fields are None if the call or the JSON fails.
    The department is always one of DEPARTMENTS (Service Desk if the model drifts).
    """
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=SERVICE_PROMPT.format(text=text),
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3),
        )
        data = json.loads(response.text)
        summary = str(data.get("summary") or "").strip() or None
        department = str(data.get("department") or "").strip()
        if department not in DEPARTMENTS:
            department = "Service Desk"
        reply = str(data.get("reply") or "").strip() or None
        return summary, department, reply
    except Exception:
        return None, None, None


if __name__ == "__main__":
    print(classify("I was charged twice for my March bill and nobody has fixed it."))