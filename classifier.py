import json
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

Request: {text}
"""

def classify(text):
    response = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(text=text),
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(response.text)

if __name__ == "__main__":
    print(classify("I was charged twice for my March bill and nobody has fixed it."))