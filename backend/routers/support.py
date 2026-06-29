"""In-game contact / support form."""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.deps import optional_user
from backend.storage.db import db, init_db
from backend.storage.support import create_support_ticket
from backend.support_notify import notify_support_ticket, support_notify_configured

router = APIRouter()
logger = logging.getLogger(__name__)


class SupportContactRequest(BaseModel):
    category: Literal["question", "bug", "refund", "account", "other"]
    message: str = Field(..., min_length=10, max_length=4000)
    contact_email: Optional[str] = Field(default=None, max_length=320)
    page_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("contact_email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().lower()
        return s or None


class SupportContactResponse(BaseModel):
    ok: bool = True
    ticket_id: str
    message: str


@router.post("/contact", response_model=SupportContactResponse)
def support_contact_route(
    body: SupportContactRequest,
    request: Request,
    user=Depends(optional_user),
):
    init_db()
    contact_email = body.contact_email
    if not contact_email and user:
        with db() as conn:
            row = conn.execute("SELECT email, username FROM users WHERE id=?", (user["user_id"],)).fetchone()
        if row:
            contact_email = str(row["email"] or "").strip().lower()
            if not contact_email and "@" in str(row["username"] or ""):
                contact_email = str(row["username"]).strip().lower()
    if not contact_email:
        raise HTTPException(status_code=400, detail="Enter the email address where we should reply.")

    user_agent = (request.headers.get("user-agent") or "")[:500] or None

    try:
        ticket = create_support_ticket(
            category=body.category,
            message=body.message.strip(),
            contact_email=contact_email,
            user_id=user["user_id"] if user else None,
            page_url=(body.page_url or "").strip() or None,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ticket["message"] = body.message.strip()
    ticket["user_id"] = user["user_id"] if user else None
    ticket["page_url"] = (body.page_url or "").strip() or None
    notified = notify_support_ticket(ticket)
    if notified:
        with db() as conn:
            conn.execute(
                "UPDATE support_tickets SET notified=1 WHERE id=?",
                (ticket["ticket_id"],),
            )

    if body.category == "refund":
        hint = (
            "Refund request received. We will email you at "
            f"{contact_email}. Approved refunds are processed through Stripe and remove game access."
        )
    elif support_notify_configured():
        hint = f"Message sent. We will reply to {contact_email}."
    else:
        hint = (
            f"Message received (ticket {ticket['ticket_id'][:8]}). "
            f"We will reply to {contact_email}."
        )

    return SupportContactResponse(ticket_id=ticket["ticket_id"], message=hint)
