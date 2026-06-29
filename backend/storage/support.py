"""In-game support / contact form submissions."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.storage.db import db

logger = logging.getLogger(__name__)

SUPPORT_CATEGORIES = frozenset({"question", "bug", "refund", "account", "other"})


def create_support_ticket(
    *,
    category: str,
    message: str,
    contact_email: str,
    user_id: Optional[str] = None,
    page_url: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    category = str(category or "").strip().lower()
    if category not in SUPPORT_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    message = str(message or "").strip()
    if len(message) < 10:
        raise ValueError("Message must be at least 10 characters.")
    contact_email = str(contact_email or "").strip().lower()
    if not contact_email or "@" not in contact_email:
        raise ValueError("A valid contact email is required.")

    ticket_id = str(uuid.uuid4())
    now = int(time.time())
    with db() as conn:
        conn.execute(
            """
            INSERT INTO support_tickets (
              id, user_id, contact_email, category, message,
              page_url, user_agent, created_at, notified
            ) VALUES (?,?,?,?,?,?,?,?,0)
            """,
            (
                ticket_id,
                user_id,
                contact_email,
                category,
                message,
                page_url,
                user_agent,
                now,
            ),
        )
    return {
        "ticket_id": ticket_id,
        "created_at": now,
        "category": category,
        "contact_email": contact_email,
    }
