"""Optional email alerts for support tickets (Resend API)."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.platform_config import platform_owner_emails

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


def _admin_notify_emails() -> List[str]:
    primary = _notify_email()
    if primary:
        return [primary]
    return sorted(platform_owner_emails())


def _send_admin_email(
    *,
    subject: str,
    body: str,
    reply_to: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None,
) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = _from_email()
    to_emails = _admin_notify_emails()
    if not api_key or not from_email or not to_emails:
        return False
    payload: Dict[str, Any] = {
        "from": from_email,
        "to": to_emails,
        "subject": subject,
        "text": body,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = attachments
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        if r.status_code >= 400:
            logger.error("Resend email failed (%s): %s", r.status_code, r.text)
            return False
        return True
    except Exception:
        logger.exception("Failed to send admin notification email")
        return False


def notify_league_start_request(request: Dict[str, Any]) -> bool:
    """Email platform admin about a new multiplayer league start request."""
    if not support_notify_configured() and not platform_owner_emails():
        logger.info(
            "League start request %s saved (email not configured).",
            request.get("request_id"),
        )
        return False

    contact = str(request.get("contact_email") or "")
    subject = f"[FND League Request] {request.get('state', '')} — {contact}"
    lines = [
        f"Request ID: {request.get('request_id')}",
        f"From: {contact}",
        f"User ID: {request.get('user_id') or '(not signed in)'}",
        f"League type: {request.get('league_type_label') or request.get('league_type')}",
        f"Estimated players: {request.get('estimated_players')}",
        f"State: {request.get('state')}",
    ]
    if request.get("notes"):
        lines.extend(["", "Notes:", str(request["notes"])])
    if request.get("file_name"):
        lines.extend(["", f"Attached file: {request['file_name']}"])
    lines.extend(["", "---", "Reply to the contact email to follow up."])
    body = "\n".join(lines)

    attachments: Optional[List[Dict[str, str]]] = None
    file_path = str(request.get("file_path") or "").strip()
    file_name = str(request.get("file_name") or "teams.json").strip()
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("ascii")
            attachments = [{"filename": file_name, "content": content}]
        except OSError:
            logger.exception("Could not read league start request file for email attachment")

    return _send_admin_email(subject=subject, body=body, reply_to=contact, attachments=attachments)
