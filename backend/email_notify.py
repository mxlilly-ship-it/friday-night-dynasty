"""Optional outbound email via Resend (invites, support, etc.)."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def email_send_configured() -> bool:
    return bool(
        os.environ.get("RESEND_API_KEY", "").strip()
        and os.environ.get("SUPPORT_FROM_EMAIL", "").strip()
    )


def _from_email() -> str:
    return os.environ.get("SUPPORT_FROM_EMAIL", "").strip()


def app_public_url() -> str:
    return (
        os.environ.get("FND_APP_URL")
        or os.environ.get("PUBLIC_APP_URL")
        or "https://fridaynightdynasty.com"
    ).strip().rstrip("/")


def send_email(*, to_email: str, subject: str, text: str, reply_to: Optional[str] = None) -> bool:
    """Send a plain-text email. Returns True if Resend accepted the message."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = _from_email()
    to_email = str(to_email or "").strip()
    if not api_key or not from_email or not to_email or "@" not in to_email:
        logger.info("Email not sent (not configured or invalid recipient): %s", subject)
        return False
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20.0,
        )
        if r.status_code >= 400:
            logger.error("Resend email failed (%s): %s", r.status_code, r.text)
            return False
        return True
    except Exception:
        logger.exception("Failed to send email: %s", subject)
        return False


def send_league_invite_email(
    *,
    to_email: str,
    league_name: str,
    inviter_label: str,
) -> bool:
    app_url = app_public_url()
    subject = f"You're invited to {league_name} on Friday Night Dynasty"
    text = "\n".join(
        [
            f"{inviter_label} invited you to join the multiplayer league \"{league_name}\" on Friday Night Dynasty.",
            "",
            "To accept:",
            "1. Sign in (or create an account) with this email address.",
            "2. Open Multiplayer from the title screen.",
            "3. Your league will appear once you're signed in — the commissioner will assign your team and PIN.",
            "",
            f"Play here: {app_url}",
            "",
            "If you weren't expecting this invite, you can ignore this email.",
        ]
    )
    return send_email(to_email=to_email, subject=subject, text=text)
