"""Optional email alerts for support tickets (Resend API)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_CATEGORY_LABELS = {
    "question": "General question",
    "bug": "Bug report",
    "refund": "Refund request",
    "account": "Account / login",
    "other": "Other",
}


def support_notify_configured() -> bool:
    return bool(
        os.environ.get("RESEND_API_KEY", "").strip()
        and os.environ.get("SUPPORT_NOTIFY_EMAIL", "").strip()
        and os.environ.get("SUPPORT_FROM_EMAIL", "").strip()
    )


def _notify_email() -> str:
    return os.environ.get("SUPPORT_NOTIFY_EMAIL", "mxlilly@gmail.com").strip()


def _from_email() -> str:
    return os.environ.get("SUPPORT_FROM_EMAIL", "").strip()


def notify_support_ticket(ticket: Dict[str, Any]) -> bool:
    """Send ticket details to the support inbox. Returns True if email was sent."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    to_email = _notify_email()
    from_email = _from_email()
    if not api_key or not from_email:
        logger.info(
            "Support ticket %s saved (email not configured — set RESEND_API_KEY, SUPPORT_FROM_EMAIL, SUPPORT_NOTIFY_EMAIL).",
            ticket.get("ticket_id"),
        )
        return False

    category = str(ticket.get("category") or "other")
    label = _CATEGORY_LABELS.get(category, category)
    subject = f"[FND Support] {label} — {ticket.get('contact_email', '')}"
    body = "\n".join(
        [
            f"Ticket ID: {ticket.get('ticket_id')}",
            f"Category: {label}",
            f"From: {ticket.get('contact_email')}",
            f"User ID: {ticket.get('user_id') or '(not signed in)'}",
            f"Page: {ticket.get('page_url') or '(unknown)'}",
            "",
            str(ticket.get("message") or ""),
            "",
            "---",
            f"User-Agent: {ticket.get('user_agent') or '(unknown)'}",
        ]
    )
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_email,
                "to": [to_email],
                "reply_to": ticket.get("contact_email"),
                "subject": subject,
                "text": body,
            },
            timeout=20.0,
        )
        if r.status_code >= 400:
            logger.error("Resend email failed (%s): %s", r.status_code, r.text)
            return False
        return True
    except Exception:
        logger.exception("Failed to send support notification email")
        return False
