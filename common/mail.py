import requests
from django.conf import settings

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


def send_email(*, to_email, subject, html_body, text_body=None):
    """Send email via Postmark. Returns True on success, False on failure."""
    if not settings.POSTMARK_SERVER_TOKEN:
        print(f"[Email] Postmark not configured, skipping: {subject} -> {to_email}")
        return False

    payload = {
        "From": settings.POSTMARK_FROM_EMAIL,
        "To": to_email,
        "Subject": subject,
        "HtmlBody": html_body,
        "MessageStream": "outbound",
        "ReplyTo": "team@unlikefraction.com",
    }
    if text_body:
        payload["TextBody"] = text_body

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": settings.POSTMARK_SERVER_TOKEN,
    }

    try:
        response = requests.post(POSTMARK_API_URL, json=payload, headers=headers, timeout=25)
        response.raise_for_status()
        print(f"[Email] Sent: {subject} -> {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed: {subject} -> {to_email}: {e}")
        return False
